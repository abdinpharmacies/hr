# -*- coding: utf-8 -*-
import logging
from xml.dom import ValidationErr

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError

PARAM_STR = "?"

_logger = logging.getLogger(__name__)


class AbSalesPosCustomerApi(models.TransientModel):
    _name = 'ab_sales_pos_api'
    _inherit = ["ab_sales_pos_api", "ab_eplus_connect"]

    @staticmethod
    def _normalize_phone(phone):
        return (phone or "").strip()

    @staticmethod
    def _is_valid_phone(phone):
        phone = (phone or "").strip()
        if len(phone) != 11:
            return False
        if not phone.isdigit():
            return False
        return phone.startswith(("010", "011", "012", "015"))

    @staticmethod
    def _is_valid_name(name):
        name = (name or "").strip()
        if not name:
            return False
        if " " not in name:
            return False
        return len(name.replace(" ", "")) >= 4

    @staticmethod
    def _is_valid_address(address):
        return len((address or "").strip()) >= 3

    @staticmethod
    def _fetchone_dict(cur):
        row = cur.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return row
        cols = [col[0] for col in (cur.description or [])]
        return {cols[idx]: row[idx] for idx in range(min(len(cols), len(row)))}

    def _local_customer_by_phone(self, phone):
        self._require_models("ab_customer")
        Customer = self.env["ab_customer"].sudo()
        return Customer.search(
            ["&", "|", ("mobile_phone", "=", phone), ("work_phone", "=", phone), ("active", "=", True)],
            limit=1,
        )

    def _bconnect_customer_by_phone(self, cur, phone):
        cur.execute(
            f"""
                SELECT TOP (1)
                    main.cust_code,
                    main.cust_name_ar AS cust_name_ar,
                    cd.cd_tel AS cust_mobile,
                    main.cust_tel,
                    cd.cd_address AS cust_address,
                    main.cust_def_sell_store,
                    CASE
                        WHEN main.sec_update_date IS NULL THEN main.sec_insert_date
                        ELSE main.sec_update_date
                    END AS last_update_date,
                    main.sec_insert_date,
                    main.cust_id AS eplus_serial,
                    CASE WHEN main.cust_active = '1' THEN 1 ELSE 0 END AS active
                FROM customer main join customer_delivery cd on cd.cd_cust_id = main.cust_id
                WHERE main.cust_active = 1
                  AND LTRIM(RTRIM(cd.cd_tel)) = {PARAM_STR}
                ORDER BY cd.cd_id
            """,
            (phone,),
        )
        return self._fetchone_dict(cur)

    def _bconnect_customer_by_id(self, cur, cust_id):
        cur.execute(
            f"""
                SELECT
                    main.cust_code,
                    main.cust_name_ar,
                    main.cust_mobile,
                    main.cust_tel,
                    main.cust_address,
                    main.cust_def_sell_store,
                    CASE
                        WHEN main.sec_update_date IS NULL THEN main.sec_insert_date
                        ELSE main.sec_update_date
                    END AS last_update_date,
                    main.sec_insert_date,
                    main.cust_id AS eplus_serial,
                    CASE WHEN main.cust_active = '1' THEN 1 ELSE 0 END AS active
                FROM customer main
                WHERE main.cust_id = {PARAM_STR}
            """,
            (int(cust_id),),
        )
        return self._fetchone_dict(cur)

    def _bconnect_find_customer_id_by_phone(self, cur, phone):
        cur.execute(
            f"""
                SELECT TOP (1) c.cust_id
                FROM dbo.Customer c WITH (NOLOCK)
                JOIN dbo.customer_delivery cd WITH (NOLOCK)
                  ON cd.cd_cust_id = c.cust_id
                WHERE c.cust_active = 1
                  AND LTRIM(RTRIM(cd.cd_tel)) = {PARAM_STR}
                ORDER BY c.cust_id
            """,
            (phone,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return int(row[0]) if row[0] else None

    def _coerce_store(self, store_id):
        if not store_id:
            return self.env["ab_store"]
        if isinstance(store_id, models.BaseModel):
            return store_id.exists()
        return self.env["ab_store"].browse(int(store_id)).exists()

    def _resolve_default_store_id(self, store_id, store_eplus_serial):
        Store = self.env["ab_store"]
        if store_eplus_serial:
            store = Store.search([("eplus_serial", "=", int(store_eplus_serial))], limit=1)
            if store:
                return store.id
        if store_id:
            store = store_id if isinstance(store_id, models.BaseModel) else Store.browse(int(store_id))
            store = store.exists()
            if store:
                return store.id
        return False

    def _get_store_server(self, store_id):
        if not store_id:
            raise UserError(_("Store is required."))
        store = store_id if isinstance(store_id, models.BaseModel) else self.env["ab_store"].browse(int(store_id))
        store = store.exists()
        if not store:
            raise UserError(_("Invalid store."))
        if not store.ip1:
            raise UserError(_("No IP for this store."))
        return store.ip1

    def _customer_vals_from_bconnect(self, row, store_id=None):
        store_eplus_serial = row.get("cust_def_sell_store")
        try:
            store_eplus_serial = int(store_eplus_serial) if store_eplus_serial is not None else False
        except Exception:
            pass
        default_store_id = self._resolve_default_store_id(store_id, store_eplus_serial)
        code = (row.get("cust_code") or "").strip()
        eplus_serial = row.get("eplus_serial")
        try:
            eplus_serial = int(eplus_serial) if eplus_serial is not None else False
        except Exception:
            pass
        if not code:
            code = str(eplus_serial or "")
        return {
            "code": code,
            "name": (row.get("cust_name_ar") or "").strip(),
            "address": (row.get("cust_address") or "").strip(),
            "default_store_id": default_store_id,
            "mobile_phone": (row.get("cust_mobile") or "").strip(),
            "work_phone": (row.get("cust_tel") or "").strip(),
            "last_update_date": row.get("last_update_date"),
            "eplus_serial": eplus_serial,
            "active": bool(row.get("active")) if row.get("active") is not None else True,
            "eplus_create_date": row.get("sec_insert_date"),
        }

    def _upsert_customer_from_bconnect(self, vals):
        self._require_models("ab_customer")
        Customer = self.env["ab_customer"].with_context(active_test=False).sudo()
        record = False
        eplus_serial = int(vals.get("eplus_serial") or 0)
        if eplus_serial:
            record = Customer.search([("eplus_serial", "=", eplus_serial)], limit=1)
        if not record:
            raise UserError("'Odoo Customers' needs replication, contact support")

        record.write(vals)
        return record

    @staticmethod
    def _customer_payload(customer):
        return {
            "id": customer.id,
            "name": customer.name or "",
            "code": customer.code or "",
            "mobile_phone": customer.mobile_phone or "",
            "work_phone": customer.work_phone or "",
            "address": customer.address or "",
            "eplus_serial": customer.eplus_serial or 0,
        }

    def _bconnect_pick_spare(self, cur, store_eplus_serial):
        cur.execute(
            f"""
                SELECT TOP (1) c.cust_id
                FROM dbo.Customer AS c WITH (NOLOCK)
                WHERE c.cust_code LIKE {PARAM_STR}
                  AND c.cust_def_sell_store = {PARAM_STR}
                ORDER BY c.cust_id
            """,
            ("spare%", int(store_eplus_serial)),
        )
        row = cur.fetchone()
        if not row:
            raise ValidationError(_(f"No spare customers in eplus store db {store_eplus_serial}! Contact support."))
        return int(row[0]) if row[0] else None

    @staticmethod
    def _bconnect_update_spare(cur, cust_id, phone, name, address, store_id):
        cur.execute(
            f"""
                UPDATE c
                SET    
                       c.cust_mobile = {PARAM_STR},
                       c.cust_tel = {PARAM_STR},
                       c.cust_name_ar = {PARAM_STR},
                       c.cust_address = {PARAM_STR},
                       c.cust_active = 1,
                       c.cust_code = CONVERT(varchar(50), c.cust_id),
                       c.cust_payment = 4,
                       c.cust_def_sell_store = {PARAM_STR},
                       c.cust_rec_name = 1,
                       c.cust_pay_perc = 100,
                       c.cust_max_credit = 11111111111.00,
                       c.pont2mony = 1
                FROM dbo.Customer AS c
                WHERE c.cust_id = {PARAM_STR}
            """,
            (phone, phone, name, address, int(store_id), int(cust_id)),
        )

    @staticmethod
    def _bconnect_upsert_delivery(cur, cust_id, phone, name, address):
        cur.execute(
            f"""
                SELECT TOP (1) cd_id
                FROM dbo.Customer_Delivery
                WHERE cd_cust_id = {PARAM_STR} AND cd_id = 1
            """,
            (int(cust_id),),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                f"""
                    UPDATE dbo.Customer_Delivery
                    SET cd_contact_person = {PARAM_STR},
                        cd_tel = {PARAM_STR},
                        cd_address = {PARAM_STR},
                        cd_notes = {PARAM_STR},
                        sec_update_uid = 1,
                        sec_update_date = GETDATE()
                    WHERE cd_cust_id = {PARAM_STR} AND cd_id = 1
                """,
                (name, phone, address, "Created from POS", int(cust_id)),
            )
            return
        cur.execute(
            f"""
                INSERT INTO dbo.Customer_Delivery (
                    cd_cust_id,
                    cd_id,
                    cd_contact_person,
                    cd_tel,
                    cd_address,
                    cd_notes,
                    sec_insert_uid,
                    sec_insert_date,
                    sec_update_uid,
                    sec_update_date
                ) VALUES (
                    {PARAM_STR},
                    1,
                    {PARAM_STR},
                    {PARAM_STR},
                    {PARAM_STR},
                    {PARAM_STR},
                    1,
                    GETDATE(),
                    1,
                    GETDATE()
                )
            """,
            (int(cust_id), name, phone, address, "Created from POS"),
        )

    @api.model
    def pos_customer_lookup(self, phone=None, store_id=None):
        self._require_models("ab_customer", "ab_store")
        phone = self._normalize_phone(phone)
        if not phone:
            raise UserError(_("Phone is required."))
        store = self._coerce_store(store_id) if store_id else False
        customer = self._local_customer_by_phone(phone)
        if customer:
            if store:
                store_server = self._get_store_server(store)
                with self.connect_eplus(
                        server=store_server,
                        param_str=PARAM_STR,
                        charset="CP1256",
                ) as conn:
                    cur = conn.cursor()
                    store_eplus_serial = store.eplus_serial
                    if not store_eplus_serial:
                        raise UserError("Store has no eplus_serial! Contact Support!")
                    cust_id = int(customer.eplus_serial or 0)
                    if not cust_id:
                        cust_id = self._bconnect_find_customer_id_by_phone(cur, phone)
                    if cust_id and store_eplus_serial:
                        if not customer.eplus_serial:
                            customer.sudo().write({"eplus_serial": cust_id})
            return {"status": "found", "customer": self._customer_payload(customer)}

        if not store:
            return {"status": "need_store", "message": _("Select a branch to search BConnect.")}

        store_server = self._get_store_server(store)
        with self.connect_eplus(
                server=store_server,
                param_str=PARAM_STR,
                charset="CP1256",
        ) as conn:
            cur = conn.cursor()
            row = self._bconnect_customer_by_phone(cur, phone)
            if row and store:
                store_eplus_serial = store.eplus_serial
                cust_id = row.get("eplus_serial")
                if cust_id and store_eplus_serial:
                    row["cust_def_sell_store"] = store_eplus_serial

        if not row:
            return {"status": "not_found"}

        vals = self._customer_vals_from_bconnect(row, store)
        customer = self._upsert_customer_from_bconnect(vals)
        return {"status": "found", "customer": self._customer_payload(customer)}

    @api.model
    def pos_customer_create(self, phone=None, name=None, address=None, store_id=None):
        self._require_models("ab_customer", "ab_store")
        phone = self._normalize_phone(phone)
        name = (name or "").strip()
        address = (address or "").strip()
        row = None
        store = self._coerce_store(store_id) if store_id else False

        if not self._is_valid_name(name):
            raise UserError(_("Customer name must contain at least two words."))
        if not self._is_valid_phone(phone):
            raise UserError(_("Phone must be 11 digits and start with 010, 011, 012, or 015."))
        if not self._is_valid_address(address):
            raise UserError(_("Address must be at least 3 characters."))
        store_server = self._get_store_server(store)
        with self.connect_eplus(
                server=store_server,
                param_str=PARAM_STR,
                charset="CP1256",
                autocommit=False,
        ) as conn:
            cur = conn.cursor()
            try:
                store_eplus_serial = store.eplus_serial
                if not store_eplus_serial:
                    raise UserError(_("No active store found in BConnect."))

                existing_id = self._bconnect_find_customer_id_by_phone(cur, phone)
                if existing_id:
                    row = self._bconnect_customer_by_id(cur, existing_id)
                    if row and store_eplus_serial:
                        row["cust_def_sell_store"] = store_eplus_serial
                    conn.commit()
                    vals = self._customer_vals_from_bconnect(row, store)
                    customer = self._upsert_customer_from_bconnect(vals)
                    return {"status": "found", "customer": self._customer_payload(customer)}

                spare_id = self._bconnect_pick_spare(cur, store_eplus_serial)
                if not spare_id:
                    raise UserError(_("No spare customers available for this store."))

                self._bconnect_update_spare(cur, spare_id, phone, name, address, store_eplus_serial)
                self._bconnect_upsert_delivery(cur, spare_id, phone, name, address)
                row = self._bconnect_customer_by_id(cur, spare_id)
                conn.commit()
            except Exception as exc:
                try:
                    conn.rollback()
                except Exception:
                    pass
                if isinstance(exc, UserError):
                    raise
                _logger.exception("BConnect customer creation failed")
                raise UserError(str(exc)) from exc

        if not row:
            raise UserError(_("Customer was created but could not be loaded."))

        vals = self._customer_vals_from_bconnect(row, store)
        customer = self._upsert_customer_from_bconnect(vals)
        return {"status": "created", "customer": self._customer_payload(customer)}
