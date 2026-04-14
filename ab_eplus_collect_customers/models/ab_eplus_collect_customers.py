# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from odoo.tools import config

_logger = logging.getLogger(__name__)
# @formatter:off
PARAM_STR = "?"
EPLUS_SERVER_IP = config.get("bconnect_ip1")

MAIN_SPARE_CUST_SQL = """
    SELECT c.cust_id,
           c.cust_mobile,
           c.cust_tel,
           c.cust_name_ar,
           c.cust_address,
           c.cust_active,
           c.cust_code,
           c.cust_payment,
           c.cust_def_sell_store,
           c.cust_rec_name,
           c.cust_pay_perc,
           c.cust_max_credit,
           c.pont2mony
    FROM dbo.Customer AS c
    WHERE c.cust_code LIKE {PARAM_STR}
      AND c.cust_def_sell_store = {PARAM_STR}
"""

STORE_CUSTOMERS_BY_IDS_SQL = """
    SELECT c.cust_id,
           c.cust_mobile,
           c.cust_tel,
           c.cust_name_ar,
           c.cust_address,
           c.cust_active,
           c.cust_code,
           c.cust_payment,
           c.cust_def_sell_store,
           c.cust_rec_name,
           c.cust_pay_perc,
           c.cust_max_credit,
           c.pont2mony
    FROM dbo.Customer AS c
    WHERE c.cust_id IN ({placeholders})
"""

EPLUS_SPARE_UPDATE_SQL = """
    UPDATE c
    SET c.cust_mobile = {PARAM_STR},
        c.cust_tel = {PARAM_STR},
        c.cust_name_ar = {PARAM_STR},
        c.cust_address = {PARAM_STR},
        c.cust_active = {PARAM_STR},
        c.cust_code = {PARAM_STR},
        c.cust_payment = {PARAM_STR},
        c.cust_def_sell_store = {PARAM_STR},
        c.cust_rec_name = {PARAM_STR},
        c.cust_pay_perc = {PARAM_STR},
        c.cust_max_credit = {PARAM_STR},
        c.pont2mony = {PARAM_STR},
        c.sec_update_date = GETDATE()
    FROM dbo.Customer AS c
    WHERE c.cust_id = {PARAM_STR}
      AND c.cust_code LIKE 'spare%'
"""

EPLUS_DELIVERY_EXISTS_SQL = """
    SELECT TOP(1) 1
    FROM dbo.Customer_Delivery
    WHERE LTRIM(RTRIM(cd_tel)) = {PARAM_STR}
"""

EPLUS_DELIVERY_NEXT_ID_SQL = """
    SELECT ISNULL(MAX(cd_id), 0) + 1
    FROM dbo.Customer_Delivery
    WHERE cd_cust_id = {PARAM_STR}
"""

EPLUS_DELIVERY_INSERT_SQL = """
    INSERT INTO dbo.Customer_Delivery (cd_cust_id,
                                       cd_id,
                                       cd_contact_person,
                                       cd_tel,
                                       cd_address,
                                       cd_notes,
                                       sec_insert_uid,
                                       sec_insert_date,
                                       sec_update_uid,
                                       sec_update_date)
    VALUES ({PARAM_STR},
            {PARAM_STR},
            {PARAM_STR},
            {PARAM_STR},
            {PARAM_STR},
            {PARAM_STR},
            1,
            GETDATE(),
            1,
            GETDATE())
"""
# @formatter:on


class AbEplusCollectCustomers(models.AbstractModel):
    _name = "ab_eplus_collect_customers"
    _description = "Collect spare customers from ePlus branch servers"
    _inherit = ["ab_eplus_connect"]

    @api.model
    def update_customers_on_main_from_stores(self, store_ids=None, server=EPLUS_SERVER_IP):
        stores = self._get_stores(store_ids)
        if not stores:
            _logger.info("No stores available for spare customer collection.")
            return 0

        _logger.info("Starting spare customer collection for %s stores.", len(stores))
        with self.connect_eplus(server=server, param_str=PARAM_STR, charset="CP1256") as main_conn:
            with main_conn.cursor(as_dict=True) as main_cur:
                processed = 0
                for store in stores:
                    try:
                        store_serial = int(store.eplus_serial or 0)
                        if not store.ip1 or not store_serial:
                            _logger.warning(
                                "Skipping store %s (ip1=%s, eplus_serial=%s).",
                                store.display_name,
                                store.ip1,
                                store.eplus_serial,
                            )
                            continue
                        processed += self._collect_store_spares(store, store_serial, main_cur)
                    except Exception as ex:
                        _logger.error(f"Pass this branch {store.display_name} {store.ip1}: {repr(ex)}")

        _logger.info("Completed spare customer collection. Rows processed: %s", processed)
        return processed

    def _get_stores(self, store_ids=None):
        Store = self.env["ab_store"].sudo()
        if store_ids:
            if isinstance(store_ids, models.BaseModel):
                return store_ids.exists()
            return Store.browse(store_ids).exists()
        return Store.search(
            [
                ("ip1", "!=", False),
                ("eplus_serial", "!=", False),
            ]
        )

    def _collect_store_spares(self, store, store_serial, main_cur):
        main_spares = self._fetch_main_spares(main_cur, store_serial)
        if not main_spares:
            _logger.info("No spare customers on main server for store %s.", store.display_name)
            return 0

        cust_ids = list(main_spares.keys())
        count = 0
        _logger.info("Collecting spare customers from store %s (%s).", store.display_name, store.ip1)
        with self.connect_eplus(server=store.ip1, param_str=PARAM_STR, charset="CP1256") as store_conn:
            with store_conn.cursor(as_dict=True) as store_cur:
                for chunk in self._chunked(cust_ids, 900):
                    placeholders = ",".join([PARAM_STR] * len(chunk))
                    store_cur.execute(
                        STORE_CUSTOMERS_BY_IDS_SQL.format(placeholders=placeholders),
                        tuple(chunk),
                    )
                    rows = store_cur.fetchall()
                    if not rows:
                        continue
                    for row in rows:
                        if not isinstance(row, dict):
                            row = self._row_to_dict(store_cur, row)
                        cust_id = self._to_int(row.get("cust_id"))
                        if not cust_id:
                            continue
                        main_row = main_spares.get(cust_id)
                        if not main_row:
                            continue
                        if not str(row.get('cust_code')).startswith('spare'):
                            self._update_main_from_store(main_cur, row, store_serial)
                            self._insert_delivery_if_missing(main_cur, cust_id)
                            count += 1

        return count

    def _fetch_main_spares(self, main_cur, store_serial):
        main_cur.execute(
            MAIN_SPARE_CUST_SQL.format(PARAM_STR=PARAM_STR),
            ("spare%", int(store_serial)),
        )
        rows = main_cur.fetchall() or []
        spares = {}
        for row in rows:
            if not isinstance(row, dict):
                row = self._row_to_dict(main_cur, row)
            cust_id = self._to_int(row.get("cust_id"))
            if cust_id:
                spares[cust_id] = row
        return spares

    @staticmethod
    def _chunked(items, size):
        for idx in range(0, len(items), size):
            yield items[idx: idx + size]

    @staticmethod
    def _row_to_dict(cur, row):
        cols = [col[0] for col in (cur.description or [])]
        return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}

    @staticmethod
    def _norm_text(value):
        return (value or "").strip()

    @staticmethod
    def _to_int(value):
        try:
            return int(value) if value is not None else None
        except Exception:
            return None

    @staticmethod
    def _to_float(value):
        try:
            return round(float(value), 2) if value is not None else None
        except Exception:
            return None

    def _update_main_from_store(self, main_cur, row, store_serial):
        cust_id = self._to_int(row.get("cust_id"))
        if not cust_id:
            return False

        mobile = self._norm_text(row.get("cust_mobile"))
        tel = self._norm_text(row.get("cust_tel")) or self._norm_text(row.get("cust_mobile"))
        name = self._norm_text(row.get("cust_name_ar"))
        address = self._norm_text(row.get("cust_address"))
        active = 1 if self._to_int(row.get("cust_active")) else 0
        code = self._norm_text(row.get("cust_code"))
        payment = self._to_int(row.get("cust_payment")) or 0
        def_store = self._to_int(row.get("cust_def_sell_store")) or int(store_serial)
        rec_name = self._to_int(row.get("cust_rec_name")) or 0
        pay_perc = self._to_int(row.get("cust_pay_perc")) or 0
        max_credit = self._to_float(row.get("cust_max_credit")) or 0.0
        pont2mony = self._to_int(row.get("pont2mony")) or 0

        main_cur.execute(
            EPLUS_SPARE_UPDATE_SQL.format(PARAM_STR=PARAM_STR),
            (
                mobile,
                tel,
                name,
                address,
                active,
                code,
                payment,
                def_store,
                rec_name,
                pay_perc,
                max_credit,
                pont2mony,
                cust_id,
            ),
        )

        return True

    def _insert_delivery_if_missing(self, main_cur, cust_id):
        main_cur.execute(
            f"""
                SELECT cust_mobile, cust_tel, cust_name_ar, cust_address, cust_active
                FROM dbo.Customer
                WHERE cust_id = {PARAM_STR}
            """,
            (int(cust_id),),
        )
        row = main_cur.fetchone()
        if not row:
            return
        if not isinstance(row, dict):
            row = self._row_to_dict(main_cur, row)

        cust_active = self._norm_text(row.get("cust_active"))
        if int(cust_active) != 1:
            return

        mobile = self._norm_text(row.get("cust_mobile"))
        tel = self._norm_text(row.get("cust_tel"))
        name = self._norm_text(row.get("cust_name_ar"))
        address = self._norm_text(row.get("cust_address"))
        phone = mobile or tel
        if not phone:
            return

        main_cur.execute(EPLUS_DELIVERY_EXISTS_SQL.format(PARAM_STR=PARAM_STR), (phone,))
        if main_cur.fetchone():
            return
        main_cur.execute(EPLUS_DELIVERY_NEXT_ID_SQL.format(PARAM_STR=PARAM_STR), (int(cust_id),))
        row = main_cur.fetchone()
        next_cd_id = int(row[0]) if row and row[0] else 1
        main_cur.execute(
            EPLUS_DELIVERY_INSERT_SQL.format(PARAM_STR=PARAM_STR),
            (
                int(cust_id),
                next_cd_id,
                name,
                phone,
                address,
                "Collected from store",
            ),
        )
