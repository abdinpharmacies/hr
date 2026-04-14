# -*- coding: utf-8 -*-

from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

PARAM_STR = "?"


class AbSalesCashierApi(models.TransientModel):
    _name = "ab_sales_cashier_api"
    _description = "Sales Cashier API"
    _inherit = ["ab_eplus_connect"]

    _POLL_MIN_PARAM = "ab_sales.cashier_poll_min_seconds"
    _POLL_MAX_PARAM = "ab_sales.cashier_poll_max_seconds"

    @api.model
    def _require_cashier_access(self):
        user = self.env.user
        if (
                user.has_group("base.group_system")
                or user.has_group("ab_sales.group_ab_sales_manager")
                or user.has_group("ab_sales.group_ab_sales_cashier")
        ):
            return
        raise AccessError(_("You do not have access to the cashier screen."))

    @api.model
    def _safe_int(self, value, default=0):
        try:
            return int(value)
        except Exception:
            return default

    @api.model
    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return default

    @api.model
    def _poll_range_seconds(self):
        params = self.env["ir.config_parameter"].sudo()
        min_seconds = self._safe_int(params.get_param(self._POLL_MIN_PARAM, "5"), 5)
        max_seconds = self._safe_int(params.get_param(self._POLL_MAX_PARAM, "20"), 20)
        min_seconds = max(2, min_seconds)
        max_seconds = max(min_seconds, min(120, max_seconds))
        return min_seconds, max_seconds

    @api.model
    def _serialize_datetime(self, value):
        if not value:
            return False
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        return str(value)

    @api.model
    def _store_domain_for_cashier(self):
        header_model = self.env["ab_sales_header"]
        domain = [("allow_sale", "=", True)]
        allowed_store_ids = header_model._get_allowed_store_ids()
        if allowed_store_ids:
            domain.append(("id", "in", allowed_store_ids))
        return domain

    @api.model
    def _default_store_id_for_cashier(self):
        return self.env["ab_sales_header"]._get_default_store_id()

    @api.model
    def _get_cashier_store_settings(self):
        header_model = self.env["ab_sales_header"]
        return {
            "allowed_store_ids": [int(x) for x in (header_model._get_allowed_store_ids() or [])],
            "default_store_id": self._safe_int(header_model._get_default_store_id(), 0),
        }

    @api.model
    def _get_cashier_employee_eplus_id(self):
        emp_id = 0
        try:
            emp_id = self.env["ab_sales_header"]._get_eplus_emp_id()
        except Exception:
            emp_id = 0
        return self._safe_int(emp_id, 0) or 1

    @api.model
    def _coerce_store(self, store_id=None, required=False, require_connection=False):
        Store = self.env["ab_store"].sudo()
        domain = self._store_domain_for_cashier()
        parsed_store_id = self._safe_int(store_id, 0)

        store = Store.browse()
        if parsed_store_id:
            store = Store.search(domain + [("id", "=", parsed_store_id)], limit=1)
        else:
            default_store_id = self._safe_int(self._default_store_id_for_cashier(), 0)
            if default_store_id:
                store = Store.search(domain + [("id", "=", default_store_id)], limit=1)
            if not store:
                store = Store.search(domain, limit=1)

        if required and not store:
            raise UserError(_("No sales store is available for cashier."))

        if store and require_connection:
            if not store.ip1:
                raise UserError(_("Store %s has no IP configured.") % (store.display_name,))
            if not store.eplus_serial:
                raise UserError(_("Store %s has no eplus serial configured.") % (store.display_name,))
        return store

    @api.model
    def _bconnect_flag_to_status(self, flag):
        value = (flag or "").strip().upper()
        if value == "P":
            return "pending"
        if value == "C":
            return "saved"
        return value.lower() if value else ""

    @api.model
    def _normalize_document_type(self, document_type):
        value = str(document_type or "sale").strip().lower()
        return "return" if value == "return" else "sale"

    @api.model
    def _arabic_char_count(self, text):
        return sum(1 for ch in str(text or "") if "\u0600" <= ch <= "\u06FF")

    @api.model
    def _mojibake_penalty(self, text):
        s = str(text or "")
        penalty = 0
        for token in ("Ù", "Ø", "Ã", "Â", "\ufffd", "�"):
            penalty += s.count(token) * 3
        for token in (
                "ط¢", "ط§", "ط¹", "ط¨", "طھ", "ط«", "ط­", "ط®", "ط¯", "ط°", "ط±", "ط²", "ط³", "ط´",
                "طµ", "ط¶", "ط·", "ط¸", "طº", "ظ„", "ظ…", "ظ†", "ظٹ", "ظ‡", "آ",
        ):
            penalty += s.count(token)
        for ch in ("€", "¢", "™"):
            penalty += s.count(ch) * 2
        return penalty

    @api.model
    def _repair_arabic_mojibake(self, value):
        text = str(value or "").strip()
        if not text:
            return ""

        candidates = [text]
        transforms = (
            ("cp1256", "utf-8"),
            ("latin-1", "utf-8"),
            ("cp1252", "utf-8"),
            ("latin-1", "cp1256"),
        )
        for src, dst in transforms:
            try:
                converted = text.encode(src, errors="ignore").decode(dst, errors="ignore").strip()
            except Exception:
                converted = ""
            if converted and converted not in candidates:
                candidates.append(converted)

        def _quality(candidate):
            arabic_count = self._arabic_char_count(candidate)
            penalty = self._mojibake_penalty(candidate)
            return (arabic_count * 4) - penalty

        best = max(candidates, key=_quality)
        if _quality(best) > _quality(text):
            return best
        return text

    @api.model
    def _clean_text(self, value):
        return self._repair_arabic_mojibake(value)

    @api.model
    def _payload_sort_datetime(self, payload_row):
        value = payload_row.get("create_date") or payload_row.get("write_date")
        try:
            parsed = fields.Datetime.to_datetime(value)
            return parsed or datetime.min
        except Exception:
            return datetime.min

    @api.model
    def _build_sale_header_payload(
            self,
            invoice_id,
            status="pending",
            create_date=False,
            write_date=False,
            customer_name="",
            customer_phone="",
            total_amount=0.0,
            total_price=0.0,
            total_net_amount=0.0,
            promo_discount_amount=0.0,
            applied_program_name="",
            selected_program_name="",
            item_count=0,
            store_name="",
            note="",
    ):
        return {
            "id": self._safe_int(invoice_id, 0),
            "invoice_number": self._safe_int(invoice_id, 0),
            "status": (str(status or "").strip().lower() or "pending"),
            "create_date": self._serialize_datetime(create_date),
            "write_date": self._serialize_datetime(write_date or create_date),
            "customer_name": self._clean_text(customer_name),
            "customer_phone": self._clean_text(customer_phone),
            "total_amount": self._safe_float(total_amount, 0.0),
            "total_price": self._safe_float(total_price, 0.0),
            "total_net_amount": self._safe_float(total_net_amount, 0.0),
            "promo_discount_amount": self._safe_float(promo_discount_amount, 0.0),
            "applied_program_name": self._clean_text(applied_program_name),
            "selected_program_name": self._clean_text(selected_program_name),
            "item_count": self._safe_int(item_count, 0),
            "store_name": self._clean_text(store_name),
            "note": self._clean_text(note),
            "payment_method": "",
            "document_type": "sale",
        }

    @api.model
    def _build_sale_line_payload(
            self,
            line_id=0,
            product_name="",
            product_code="",
            qty=0.0,
            qty_str="",
            uom_name="",
            sell_price=0.0,
            net_amount=0.0,
    ):
        qty_value = self._safe_float(qty, 0.0)
        sell_price_value = self._safe_float(sell_price, 0.0)
        net_amount_value = self._safe_float(net_amount, 0.0)
        if not net_amount_value:
            net_amount_value = qty_value * sell_price_value
        return {
            "id": self._safe_int(line_id, 0),
            "product_name": self._clean_text(product_name),
            "product_code": self._clean_text(product_code),
            "qty": qty_value,
            "qty_str": str(qty_str or qty_value),
            "uom_name": self._clean_text(uom_name),
            "sell_price": sell_price_value,
            "net_amount": net_amount_value,
        }

    @api.model
    def _sale_customer_from_odoo_header(self, header):
        customer_name = (
                header.bill_customer_name
                or header.new_customer_name
                or (header.customer_id and header.customer_id.display_name)
                or ""
        )
        customer_phone = (
                header.bill_customer_phone
                or header.new_customer_phone
                or header.customer_mobile
                or header.customer_phone
                or ""
        )
        return (self._clean_text(customer_name), self._clean_text(customer_phone))

    @api.model
    def _pending_sale_header_payload_from_odoo(self, header):
        customer_name, customer_phone = self._sale_customer_from_odoo_header(header)
        total_price = self._safe_float(getattr(header, "total_price", 0.0), 0.0)
        total_net_amount = self._safe_float(getattr(header, "total_net_amount", 0.0) or total_price, 0.0)
        total_amount = total_net_amount
        if not total_amount and header.line_ids:
            total_amount = sum(self._safe_float(line.net_amount, 0.0) for line in header.line_ids)
            total_net_amount = total_amount
            if not total_price:
                total_price = total_amount
        promo_discount_amount = self._safe_float(getattr(header, "promo_discount_amount", 0.0), 0.0)
        applied_program_name = ""
        selected_program_name = ""
        programs = getattr(header, "applied_program_ids", False)
        if programs:
            program = programs[:1]
            applied_program_name = (program.display_name or program.name or "").strip()
            selected_program_name = applied_program_name
        item_count = self._safe_int(header.number_of_products, 0) or len(header.line_ids)
        return self._build_sale_header_payload(
            invoice_id=int(header.eplus_serial or 0),
            status=(header.status or "pending"),
            create_date=header.create_date,
            write_date=header.write_date or header.create_date,
            customer_name=customer_name,
            customer_phone=customer_phone,
            total_amount=total_amount,
            total_price=total_price,
            total_net_amount=total_net_amount,
            promo_discount_amount=promo_discount_amount,
            applied_program_name=applied_program_name,
            selected_program_name=selected_program_name,
            item_count=item_count,
            store_name=header.store_id.display_name if header.store_id else "",
            note=header.description or "",
        )

    @api.model
    def _pending_sale_header_payload_from_bconnect(self, row, store):
        invoice_id = self._safe_int(row.get("sth_id"), 0)
        create_date = row.get("sec_insert_date")
        write_date = row.get("sec_update_date") or create_date
        total_price = self._safe_float(row.get("total_bill"), 0.0)
        total_net_amount = self._safe_float(row.get("total_bill_net"), 0.0) or total_price
        total_amount = total_net_amount or total_price
        return self._build_sale_header_payload(
            invoice_id=invoice_id,
            status=self._bconnect_flag_to_status(row.get("sth_flag")),
            create_date=create_date,
            write_date=write_date,
            customer_name=row.get("customer_name") or "",
            customer_phone=row.get("customer_phone") or "",
            total_amount=total_amount,
            total_price=total_price,
            total_net_amount=total_net_amount,
            item_count=self._safe_int(row.get("no_of_items"), 0),
            store_name=store.display_name if store else "",
            note=row.get("sth_notice") or "",
        )

    @api.model
    def _source_sale_header_for_return(self, return_header):
        if not return_header or not return_header.origin_header_id:
            return self.env["ab_sales_header"].sudo().browse()
        domain = [("eplus_serial", "=", int(return_header.origin_header_id))]
        if return_header.store_id:
            domain.append(("store_id", "=", return_header.store_id.id))
        return self.env["ab_sales_header"].sudo().search(domain, order="id desc", limit=1)

    @api.model
    def _pending_return_header_payload_from_odoo(self, return_header):
        source_header = self._source_sale_header_for_return(return_header)
        customer_name = _("Sales Return")
        customer_phone = ""
        if source_header:
            customer_name = (
                source_header.bill_customer_name
                or source_header.new_customer_name
                or (source_header.customer_id and source_header.customer_id.display_name)
                or customer_name
            )
            customer_phone = (
                source_header.bill_customer_phone
                or source_header.new_customer_phone
                or source_header.customer_mobile
                or source_header.customer_phone
                or ""
            )
        total_amount = self._safe_float(
            return_header.total_return_value or return_header.total_sales_net,
            0.0,
        )
        if not total_amount:
            total_amount = sum(self._safe_float(line.line_value, 0.0) for line in return_header.line_ids)
        invoice_number = return_header.origin_header_id or return_header.id
        return {
            "id": int(return_header.id),
            "invoice_number": str(invoice_number),
            "status": (return_header.status or "").strip().lower() or "pending",
            "create_date": self._serialize_datetime(return_header.create_date),
            "write_date": self._serialize_datetime(return_header.write_date or return_header.create_date),
            "customer_name": self._clean_text(customer_name) or _("Sales Return"),
            "customer_phone": self._clean_text(customer_phone),
            "total_amount": total_amount,
            "item_count": len(return_header.line_ids),
            "store_name": self._clean_text(return_header.store_id.display_name if return_header.store_id else ""),
            "note": self._clean_text(return_header.notes or ""),
            "payment_method": "",
            "document_type": "return",
        }

    @api.model
    def _return_line_payload_from_odoo(self, line):
        qty = self._safe_float(line.qty, 0.0)
        sell_price = self._safe_float(line.sell_price, 0.0)
        net_amount = self._safe_float(line.line_value, 0.0)
        if not net_amount:
            net_amount = qty * sell_price
        product_name = line.product_id.display_name if line.product_id else ""
        product_code = ""
        if line.product_id:
            if "code" in line.product_id._fields:
                product_code = line.product_id.code or ""
            elif "default_code" in line.product_id._fields:
                product_code = line.product_id.default_code or ""
        if not product_code and line.itm_eplus_id:
            product_code = str(int(line.itm_eplus_id))
        if not product_name:
            product_name = product_code or str(line.id)
        return {
            "id": int(line.id),
            "product_name": self._clean_text(product_name),
            "product_code": self._clean_text(product_code),
            "qty": qty,
            "qty_str": line.qty_str or str(qty),
            "uom_name": self._clean_text(line.uom_id.display_name if line.uom_id else ""),
            "sell_price": sell_price,
            "net_amount": net_amount,
        }

    @api.model
    def _sale_line_payload_from_odoo(self, line):
        product_name = line.product_id.display_name if line.product_id else ""
        product_code = (line.product_code or "").strip()
        if not product_code and line.product_id:
            if "code" in line.product_id._fields:
                product_code = line.product_id.code or ""
            elif "default_code" in line.product_id._fields:
                product_code = line.product_id.default_code or ""
        if not product_name:
            product_name = product_code or str(line.id)
        qty = self._safe_float(line.qty, 0.0)
        sell_price = self._safe_float(line.sell_price, 0.0)
        net_amount = self._safe_float(line.net_amount, qty * sell_price)
        return self._build_sale_line_payload(
            line_id=line.id,
            product_name=product_name,
            product_code=product_code,
            qty=qty,
            qty_str=str(qty),
            uom_name=line.uom_id.display_name if line.uom_id else "",
            sell_price=sell_price,
            net_amount=net_amount,
        )

    @api.model
    def _fetch_pending_return_headers_from_odoo(self, store, limit):
        ReturnHeader = self.env["ab_sales_return_header"].sudo()
        return ReturnHeader.search(
            [
                ("status", "=", "pending"),
                ("store_id", "=", store.id),
            ],
            order="create_date desc, id desc",
            limit=int(limit),
        )

    @api.model
    def _get_cashier_return_header(self, store, return_id, pending_only=False):
        domain = [
            ("id", "=", int(return_id)),
            ("store_id", "=", store.id),
        ]
        if pending_only:
            domain.append(("status", "=", "pending"))
        return self.env["ab_sales_return_header"].sudo().search(domain, limit=1)

    @api.model
    def _fetch_pending_sale_headers_from_odoo(self, store, limit):
        return self.env["ab_sales_header"].sudo().search(
            [
                ("status", "=", "pending"),
                ("store_id", "=", store.id),
                ("eplus_serial", "!=", False),
            ],
            order="create_date desc, id desc",
            limit=int(limit),
        )

    @api.model
    def _get_cashier_sale_header_from_odoo(self, store, invoice_id, pending_only=False):
        domain = [
            ("store_id", "=", store.id),
            ("eplus_serial", "=", int(invoice_id)),
        ]
        if pending_only:
            domain.append(("status", "=", "pending"))
        return self.env["ab_sales_header"].sudo().search(domain, order="id desc", limit=1)

    @api.model
    def _get_cashier_sale_header_for_print(self, store, invoice_id):
        Header = self.env["ab_sales_header"].sudo()
        invoice_serial = int(invoice_id)
        if store:
            header = self._get_cashier_sale_header_from_odoo(store=store, invoice_id=invoice_serial, pending_only=False)
            if header:
                return header
        # Fallback to any store so cashier uses the same Odoo bill as Bill Wizard.
        return Header.search(
            [("eplus_serial", "=", invoice_serial)],
            order="id desc",
            limit=1,
        )

    @api.model
    def _line_payload_from_bconnect(self, row):
        qty = self._safe_float(row.get("qnty"), 0.0)
        sell_price = self._safe_float(row.get("itm_sell"), 0.0)
        net_amount = self._safe_float(row.get("line_total_net"), 0.0)
        if not net_amount:
            net_amount = (qty * sell_price) - self._safe_float(row.get("itm_dis_mon"), 0.0)
        itm_unit = self._safe_int(row.get("itm_unit"), 0)
        return self._build_sale_line_payload(
            line_id=self._safe_int(row.get("std_id"), 0),
            product_name=row.get("product_name") or "",
            product_code=row.get("itm_code") or str(self._safe_int(row.get("itm_id"), 0)),
            qty=qty,
            qty_str=str(qty),
            uom_name=str(itm_unit) if itm_unit else "",
            sell_price=sell_price,
            net_amount=net_amount,
        )

    @api.model
    def _fetch_pending_headers_from_bconnect(self, store, limit):
        sql = f"""
            SELECT TOP ({int(limit)})
                h.sth_id,
                h.sth_flag,
                h.no_of_items,
                h.total_bill,
                h.total_bill_net,
                h.sth_notice,
                h.sec_insert_date,
                h.sec_update_date,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(c.cust_name_ar)), ''),
                    ''
                ) AS customer_name,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(cd.cd_tel)), ''),
                    NULLIF(LTRIM(RTRIM(c.cust_mobile)), ''),
                    NULLIF(LTRIM(RTRIM(c.cust_tel)), ''),
                    ''
                ) AS customer_phone
            FROM sales_trans_h h WITH (NOLOCK)
            LEFT JOIN customer c WITH (NOLOCK)
                ON c.cust_id = h.cust_id
            LEFT JOIN customer_delivery cd WITH (NOLOCK)
                ON cd.cd_cust_id = c.cust_id AND cd.cd_id = 1
            WHERE h.sth_flag = 'P'
              AND h.sto_id = {PARAM_STR}
            ORDER BY h.sec_insert_date DESC, h.sth_id DESC
        """
        with self.connect_eplus(
                server=store.ip1,
                param_str=PARAM_STR,
                charset="CP1256",
                propagate_error=True,
        ) as conn:
            with conn.cursor(as_dict=True) as cur:
                cur.execute(sql, (int(store.eplus_serial),))
                return cur.fetchall() or []

    @api.model
    def _fetch_invoice_snapshot_header_from_bconnect(self, store, invoice_id):
        sql = f"""
            SELECT TOP (1)
                h.sth_id,
                h.sth_flag,
                h.no_of_items,
                h.total_bill,
                h.total_bill_net,
                h.sth_notice,
                h.sec_insert_date,
                h.sec_update_date,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(c.cust_name_ar)), ''),
                    ''
                ) AS customer_name,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(cd.cd_tel)), ''),
                    NULLIF(LTRIM(RTRIM(c.cust_mobile)), ''),
                    NULLIF(LTRIM(RTRIM(c.cust_tel)), ''),
                    ''
                ) AS customer_phone
            FROM sales_trans_h h WITH (NOLOCK)
            LEFT JOIN customer c WITH (NOLOCK)
                ON c.cust_id = h.cust_id
            LEFT JOIN customer_delivery cd WITH (NOLOCK)
                ON cd.cd_cust_id = c.cust_id AND cd.cd_id = 1
            WHERE h.sth_id = {PARAM_STR}
              AND h.sto_id = {PARAM_STR}
        """
        with self.connect_eplus(
                server=store.ip1,
                param_str=PARAM_STR,
                charset="CP1256",
                propagate_error=True,
        ) as conn:
            with conn.cursor(as_dict=True) as cur:
                cur.execute(sql, (int(invoice_id), int(store.eplus_serial)))
                rows = cur.fetchall() or []
                return rows[0] if rows else {}

    @api.model
    def _fetch_pending_lines_from_bconnect(self, store, invoice_id):
        sql = f"""
            SELECT
                d.std_id,
                d.itm_id,
                d.qnty,
                d.itm_sell,
                d.itm_dis_mon,
                d.itm_unit,
                i.itm_code,
                COALESCE(
                    NULLIF(LTRIM(RTRIM(i.itm_name_ar)), ''),
                    CONVERT(varchar(32), d.itm_id)
                ) AS product_name,
                (ISNULL(d.qnty, 0) * ISNULL(d.itm_sell, 0)) - ISNULL(d.itm_dis_mon, 0) AS line_total_net
            FROM sales_trans_d d WITH (NOLOCK)
            LEFT JOIN item_catalog i WITH (NOLOCK)
                ON i.itm_id = d.itm_id
            WHERE d.sth_id = {PARAM_STR}
            ORDER BY d.std_id
        """
        with self.connect_eplus(
                server=store.ip1,
                param_str=PARAM_STR,
                charset="CP1256",
                propagate_error=True,
        ) as conn:
            with conn.cursor(as_dict=True) as cur:
                cur.execute(sql, (int(invoice_id),))
                return cur.fetchall() or []

    @api.model
    def _pending_sales_source_odoo(self, store, limit):
        headers = self._fetch_pending_sale_headers_from_odoo(store=store, limit=limit)
        payload = []
        invoice_ids = set()
        for header in headers:
            serial = self._safe_int(header.eplus_serial, 0)
            if not serial:
                continue
            if serial in invoice_ids:
                # Keep newest (ordered desc) and skip duplicates with same eplus serial.
                continue
            row = self._pending_sale_header_payload_from_odoo(header)
            if not row.get("id"):
                continue
            payload.append(row)
            invoice_ids.add(int(row["id"]))
        return payload, invoice_ids

    @api.model
    def _pending_sales_source_bconnect(self, store, limit, excluded_invoice_ids=None):
        excluded = {self._safe_int(x, 0) for x in (excluded_invoice_ids or set())}
        excluded.discard(0)
        rows = self._fetch_pending_headers_from_bconnect(store=store, limit=limit)
        payload = []
        for row in rows:
            normalized = self._pending_sale_header_payload_from_bconnect(row, store)
            invoice_id = self._safe_int(normalized.get("id"), 0)
            if not invoice_id:
                continue
            if invoice_id in excluded:
                continue
            payload.append(normalized)
        return payload

    @api.model
    def _pending_returns_source_odoo(self, store, limit):
        return_headers = self._fetch_pending_return_headers_from_odoo(store=store, limit=limit)
        return [self._pending_return_header_payload_from_odoo(header) for header in return_headers]

    @api.model
    def _sale_snapshot_source_odoo(self, store, invoice_id):
        header = self._get_cashier_sale_header_from_odoo(store=store, invoice_id=invoice_id, pending_only=False)
        if not header:
            return {}
        snapshot = self._pending_sale_header_payload_from_odoo(header)
        lines = [self._sale_line_payload_from_odoo(line) for line in header.line_ids.sorted("id")]
        snapshot["lines"] = lines
        snapshot["line_count"] = len(lines)
        if not snapshot["total_amount"] and lines:
            snapshot["total_amount"] = sum(self._safe_float(line.get("net_amount"), 0.0) for line in lines)
        return snapshot

    @api.model
    def _sale_snapshot_source_bconnect(self, store, invoice_id):
        header_row = self._fetch_invoice_snapshot_header_from_bconnect(store=store, invoice_id=invoice_id)
        if not header_row:
            return {}
        lines_rows = self._fetch_pending_lines_from_bconnect(store=store, invoice_id=invoice_id)
        snapshot = self._pending_sale_header_payload_from_bconnect(header_row, store)
        snapshot["lines"] = [self._line_payload_from_bconnect(row) for row in lines_rows]
        snapshot["line_count"] = len(snapshot["lines"])
        if not snapshot["total_amount"] and snapshot["lines"]:
            snapshot["total_amount"] = sum(line.get("net_amount", 0.0) for line in snapshot["lines"])
        return snapshot

    @api.model
    def _fetch_store_wallets_from_bconnect(self, store):
        with self.connect_eplus(
                server=store.ip1,
                param_str=PARAM_STR,
                charset="CP1256",
                propagate_error=True,
        ) as conn:
            with conn.cursor(as_dict=True) as cur:
                sql = f"""
                    SELECT
                        fcs_id,
                        LTRIM(RTRIM(ISNULL(fcs_name_ar, ''))) AS wallet_name,
                        ISNULL(fcs_current_balance, 0) AS wallet_balance
                    FROM F_Cash_Store WITH (NOLOCK)
                    WHERE ISNULL(fcs_active, 0) = 1
                      AND ISNULL(fcs_type, 0) = 1
                    ORDER BY fcs_id
                """
                cur.execute(sql)
                rows = cur.fetchall() or []
                wallets = []
                for row in rows:
                    wallet_id = self._safe_int(row.get("fcs_id"), 0)
                    if not wallet_id:
                        continue
                    wallets.append({
                        "id": wallet_id,
                        "name": (row.get("wallet_name") or str(wallet_id)).strip() or str(wallet_id),
                        "balance": self._safe_float(row.get("wallet_balance"), 0.0),
                    })
                return wallets

    @api.model
    def _save_pending_invoice_in_bconnect(self, store, invoice_id, wallet_id):
        current_flag = ""
        collected_amount = 0.0
        result_status = "not_found"
        wallet_id = self._safe_int(wallet_id, 0)
        if not wallet_id:
            raise UserError(_("Wallet is required."))

        select_sql = f"""
            SELECT TOP (1)
                sth_flag,
                total_bill_net,
                total_bill,
                cust_id,
                sto_id,
                sth_pc_name
            FROM sales_trans_h WITH (UPDLOCK, ROWLOCK)
            WHERE sth_id = {PARAM_STR}
              AND sto_id = {PARAM_STR}
        """
        update_header_sql = f"""
            UPDATE sales_trans_h WITH (ROWLOCK)
               SET sth_flag = 'C',
                   sth_cash = {PARAM_STR},
                   sth_rest = 0,
                   sec_update_uid = {PARAM_STR},
                   sth_user_save_pend = {PARAM_STR},
                   sec_update_date = GETDATE(),
                   delivery_date = GETDATE()
             WHERE sth_id = {PARAM_STR}
               AND sto_id = {PARAM_STR}
        """
        with self.connect_eplus(
                server=store.ip1,
                param_str=PARAM_STR,
                charset="CP1256",
                autocommit=False,
                propagate_error=True,
        ) as conn:
            try:
                with conn.cursor(as_dict=True) as cur:
                    cur.execute(select_sql, (int(invoice_id), int(store.eplus_serial)))
                    rows = cur.fetchall() or []
                    header_row = rows[0] if rows else {}
                    if rows:
                        current_flag = (header_row.get("sth_flag") or "").strip().upper()
                    if not rows:
                        result_status = "not_found"
                    elif current_flag == "C":
                        result_status = "already_saved"
                    elif current_flag != "P":
                        result_status = "invalid_status"
                    else:
                        total_bill_net = self._safe_float(header_row.get("total_bill_net"), 0.0)
                        total_bill = self._safe_float(header_row.get("total_bill"), 0.0)
                        collected_amount = total_bill_net or total_bill
                        points_discount_value = max(0.0, total_bill - total_bill_net)
                        cashier_emp_id = self._get_cashier_employee_eplus_id()
                        cust_id = self._safe_int(header_row.get("cust_id"), 0)
                        sto_eplus_serial = self._safe_int(header_row.get("sto_id"), int(store.eplus_serial))
                        pc_name = (header_row.get("sth_pc_name") or self.env.user.login or "ODOO").strip()
                        eplus_version = "13.0.86"

                        wallet_where = [
                            f"fcs_id = {PARAM_STR}",
                            "ISNULL(fcs_active, 0) = 1",
                            "ISNULL(fcs_type, 0) = 1",
                        ]
                        wallet_params = [int(wallet_id)]

                        cur.execute(
                            f"""
                                SELECT TOP (1) fcs_id
                                FROM F_Cash_Store WITH (UPDLOCK, ROWLOCK)
                                WHERE {' AND '.join(wallet_where)}
                            """,
                            tuple(wallet_params),
                        )
                        wallet_rows = cur.fetchall() or []
                        if not wallet_rows:
                            raise UserError(_("Selected wallet was not found for this store."))

                        cur.execute(
                            update_header_sql,
                            (
                                collected_amount,
                                cashier_emp_id,
                                cashier_emp_id,
                                int(invoice_id),
                                int(store.eplus_serial),
                            ),
                        )

                        cur.execute(
                            f"""
                                INSERT INTO r_sales_trans_f (sth_id)
                                SELECT {PARAM_STR}
                                 WHERE NOT EXISTS (
                                    SELECT 1
                                      FROM r_sales_trans_f WITH (NOLOCK)
                                     WHERE sth_id = {PARAM_STR}
                                )
                            """,
                            (int(invoice_id), int(invoice_id)),
                        )

                        cur.execute(
                            f"""
                                UPDATE sales_trans_d WITH (ROWLOCK)
                                   SET sec_update_date = GETDATE(),
                                       sec_update_uid = {PARAM_STR}
                                 WHERE sth_id = {PARAM_STR}
                            """,
                            (cashier_emp_id, int(invoice_id)),
                        )

                        cur.execute(
                            f"""
                                UPDATE F_Cash_Store WITH (ROWLOCK)
                                   SET fcs_current_balance = ISNULL(fcs_current_balance, 0) + {PARAM_STR}
                                 WHERE {' AND '.join(wallet_where)}
                            """,
                            tuple([collected_amount] + wallet_params),
                        )

                        collect_note = _("Sales collection for invoice #%s") % (int(invoice_id),)
                        cur.execute(
                            f"""
                                INSERT INTO F_Transaction_Header (
                                    fh_trans_type, fh_trans_type2, fh_code,
                                    fh_value, fh_From_type, fh_from_id,
                                    fh_to_type, fh_to_id, fh_notes,
                                    sec_insert_uid, fh_actual_date,
                                    fh_computer, fh_actual_cashier_id,
                                    fh_form_type, fh_sto_id, fh_cost_sto_id
                                )
                                VALUES (1, 1, '', {PARAM_STR},
                                        '1', {PARAM_STR},
                                        '3', {PARAM_STR}, {PARAM_STR},
                                        {PARAM_STR}, GETDATE(),
                                        {PARAM_STR}, {PARAM_STR},
                                        1, {PARAM_STR}, 0)
                            """,
                            (
                                collected_amount,
                                cust_id,
                                int(wallet_id),
                                collect_note,
                                cashier_emp_id,
                                pc_name,
                                cashier_emp_id,
                                sto_eplus_serial,
                            ),
                        )
                        cur.execute("SELECT CAST(@@IDENTITY AS BIGINT) AS fh_id")
                        trx_rows = cur.fetchall() or []
                        fh_id = self._safe_int(trx_rows[0].get("fh_id") if trx_rows else 0, 0)
                        if fh_id:
                            cur.execute(
                                f"""
                                    UPDATE F_Transaction_Header
                                       SET fh_code = fh_id
                                     WHERE fh_id = {PARAM_STR}
                                       AND (fh_code = '' OR fh_code IS NULL)
                                """,
                                (int(fh_id),),
                            )
                            cur.execute(
                                f"""
                                    UPDATE sales_trans_h WITH (ROWLOCK)
                                       SET fh_id = {PARAM_STR}
                                     WHERE sth_id = {PARAM_STR}
                                       AND sto_id = {PARAM_STR}
                                """,
                                (int(fh_id), int(invoice_id), int(store.eplus_serial)),
                            )

                        if cust_id > 0:
                            cur.execute(
                                f"""
                                    UPDATE customer
                                       SET cust_curr_points = cust_curr_points - ({PARAM_STR} * ISNULL(pont2mony, 0))
                                     WHERE cust_curr_points > 0
                                       AND cust_id = {PARAM_STR}
                                """,
                                (
                                    points_discount_value,
                                    cust_id,
                                ),
                            )

                        cur.execute(
                            f"""
                                INSERT INTO sales_trans_payment (
                                    stp_sto_id, stp_sth_id, stp_pt_id, stp_fcs_id,
                                    stp_value, stp_version, stp_pc_name, stp_insert_uid
                                )
                                VALUES (
                                    {PARAM_STR}, {PARAM_STR}, 1, {PARAM_STR},
                                    {PARAM_STR}, {PARAM_STR}, {PARAM_STR}, {PARAM_STR}
                                )
                            """,
                            (
                                sto_eplus_serial,
                                int(invoice_id),
                                int(wallet_id),
                                collected_amount,
                                eplus_version,
                                pc_name,
                                cashier_emp_id,
                            ),
                        )

                        auto_doc_note = _("Sales invoice close #%s") % (int(invoice_id),)
                        cur.execute(
                            f"""
                                INSERT INTO F_Auto_Doc_h (
                                    fah_type, fah_sto_id, fah_form_name, fah_form_id,
                                    fah_form_notes, fah_total_value, fah_description,
                                    fah_ePlus_version, fah_starting_doc, sec_insert_uid,
                                    fah_form_text, fah_computer_name
                                )
                                VALUES (
                                    'PendingSalesBill', {PARAM_STR}, 'View_All_Pending_Sales_Bills_ar', {PARAM_STR},
                                    '', 0, {PARAM_STR},
                                    {PARAM_STR}, 0, {PARAM_STR},
                                    'Pending Sales Bills', {PARAM_STR}
                                )
                            """,
                            (
                                sto_eplus_serial,
                                int(invoice_id),
                                auto_doc_note,
                                eplus_version,
                                cashier_emp_id,
                                pc_name,
                            ),
                        )
                        cur.execute("SELECT CAST(@@IDENTITY AS BIGINT) AS fah_id")
                        auto_doc_rows = cur.fetchall() or []
                        fah_id = self._safe_int(auto_doc_rows[0].get("fah_id") if auto_doc_rows else 0, 0)
                        if fah_id:
                            cur.execute(
                                f"""
                                    INSERT INTO F_Auto_Doc_d (
                                        fad_fah_id, fad_group_id, fad_value,
                                        fad_D_Account_id, fad_D_Account_name, fad_D_object, fad_D_object_id,
                                        fad_C_Account_id, fad_C_Account_name, fad_C_object, fad_C_object_id,
                                        sec_insert_uid
                                    )
                                    VALUES (
                                        {PARAM_STR}, 4, {PARAM_STR},
                                        ISNULL((SELECT TOP (1) fcs_ac_id FROM F_Cash_Store WITH (NOLOCK) WHERE fcs_id = {PARAM_STR}), 0),
                                        'Cashier', 'Cshr', {PARAM_STR},
                                        168, 'PendingSales', '0', 0,
                                        {PARAM_STR}
                                    )
                                """,
                                (
                                    int(fah_id),
                                    collected_amount,
                                    int(wallet_id),
                                    int(wallet_id),
                                    cashier_emp_id,
                                ),
                            )
                            cur.execute(
                                f"""
                                    UPDATE F_Auto_Doc_h
                                       SET fah_total_value = {PARAM_STR}
                                     WHERE fah_id = {PARAM_STR}
                                """,
                                (collected_amount, int(fah_id)),
                            )

                        result_status = "saved"
                if result_status == "saved":
                    conn.commit()
                else:
                    conn.rollback()
            except Exception:
                conn.rollback()
                raise
        return result_status, current_flag, collected_amount

    @api.model
    def _save_pending_return_in_odoo(self, store, return_id):
        return_header = self._get_cashier_return_header(store=store, return_id=return_id, pending_only=False)
        if not return_header:
            return "not_found", "", 0.0
        status = (return_header.status or "").strip().lower()
        amount = self._safe_float(return_header.total_return_value or return_header.total_sales_net, 0.0)

        if status == "saved":
            return "already_saved", status, amount
        if status != "pending":
            return "invalid_status", status, amount

        # Run in sudo mode to bypass ACL for cashier users.
        return_header.sudo().action_push_to_eplus_return()
        return "saved", "saved", amount

    @api.model
    def _sync_odoo_header_status(self, store, invoice_id):
        Header = self.env["ab_sales_header"].sudo()
        headers = Header.search([
            ("store_id", "=", store.id),
            ("eplus_serial", "=", int(invoice_id)),
            ("status", "=", "pending"),
        ])
        if headers:
            headers.write({"status": "saved"})

    @api.model
    def get_cashier_bootstrap(self):
        self._require_cashier_access()
        min_seconds, max_seconds = self._poll_range_seconds()
        printer = {}
        if "ab_sales_ui_api" in self.env.registry:
            printer = self.env["ab_sales_ui_api"].sudo().get_printer_settings()
        store_settings = self._get_cashier_store_settings()
        return {
            "branch_name": self.env.company.display_name or self.env.company.name or "",
            "device_name": self.env.user.name or "",
            "poll_min_seconds": min_seconds,
            "poll_max_seconds": max_seconds,
            "printer_name": printer.get("printer_name", ""),
            "receipt_header": printer.get("receipt_header", ""),
            "receipt_footer": printer.get("receipt_footer", ""),
            "allowed_store_ids": store_settings["allowed_store_ids"],
            "default_store_id": store_settings["default_store_id"] or False,
            "server_time": fields.Datetime.now(),
        }

    @api.model
    def get_pending_invoices(self, limit=300, store_id=None):
        self._require_cashier_access()
        limit = self._safe_int(limit, 300)
        limit = max(20, min(2000, limit))
        store = self._coerce_store(store_id=store_id, required=True, require_connection=True)
        # Source priority for sales:
        # 1) Odoo ab_sales_header/ab_sales_line
        # 2) BConnect sales_trans_h/sales_trans_d (fallback only)
        sale_payload_odoo, covered_invoice_ids = self._pending_sales_source_odoo(store=store, limit=limit)
        sale_payload_bconnect = self._pending_sales_source_bconnect(
            store=store,
            limit=limit,
            excluded_invoice_ids=covered_invoice_ids,
        )
        sale_payload = sale_payload_odoo + sale_payload_bconnect
        return_payload = self._pending_returns_source_odoo(store=store, limit=limit)
        payload = sale_payload + return_payload
        payload.sort(key=self._payload_sort_datetime, reverse=True)
        payload = payload[:limit]
        return {
            "invoices": payload,
            "total_pending": len(payload),
            "store_id": store.id,
            "store_name": store.display_name,
            "server_time": fields.Datetime.now(),
        }

    @api.model
    def get_invoice_snapshot(self, invoice_id, store_id=None, document_type="sale"):
        self._require_cashier_access()
        invoice_id = self._safe_int(invoice_id, 0)
        if not invoice_id:
            raise UserError(_("Invalid invoice id."))
        store = self._coerce_store(store_id=store_id, required=True, require_connection=True)
        document_type = self._normalize_document_type(document_type)
        if document_type == "return":
            return_header = self._get_cashier_return_header(store=store, return_id=invoice_id, pending_only=False)
            if not return_header:
                raise UserError(_("Return document not found."))
            snapshot = self._pending_return_header_payload_from_odoo(return_header)
            lines = [self._return_line_payload_from_odoo(line) for line in return_header.line_ids.sorted("id")]
            snapshot["lines"] = lines
            snapshot["line_count"] = len(lines)
            if not snapshot["total_amount"] and lines:
                snapshot["total_amount"] = sum(self._safe_float(line.get("net_amount"), 0.0) for line in lines)
            return snapshot

        snapshot = self._sale_snapshot_source_odoo(store=store, invoice_id=invoice_id)
        if snapshot:
            return snapshot

        snapshot = self._sale_snapshot_source_bconnect(store=store, invoice_id=invoice_id)
        if not snapshot:
            raise UserError(_("Invoice not found."))
        return snapshot

    @api.model
    def get_invoice_print_ref(self, invoice_id, store_id=None, document_type="sale"):
        self._require_cashier_access()
        invoice_id = self._safe_int(invoice_id, 0)
        if not invoice_id:
            raise UserError(_("Invalid invoice id."))
        document_type = self._normalize_document_type(document_type)
        store = self.env["ab_store"].sudo().browse()
        parsed_store_id = self._safe_int(store_id, 0)
        if parsed_store_id:
            store = self._coerce_store(store_id=parsed_store_id, required=False, require_connection=False)
        if document_type == "return":
            if store:
                return_header = self._get_cashier_return_header(store=store, return_id=invoice_id, pending_only=False)
            else:
                return_header = self.env["ab_sales_return_header"].sudo().search([("id", "=", invoice_id)], limit=1)
            if not return_header:
                raise UserError(_("Return document not found."))
            return {
                "header_ref": -int(return_header.id),
                "document_type": "return",
            }

        sale_header = self._get_cashier_sale_header_for_print(store=store, invoice_id=invoice_id)
        if not sale_header:
            return {
                "header_ref": False,
                "document_type": "sale",
            }
        return {
            "header_ref": int(sale_header.id),
            "document_type": "sale",
        }

    @api.model
    def get_store_wallets(self, store_id=None):
        self._require_cashier_access()
        store = self._coerce_store(store_id=store_id, required=True, require_connection=True)
        wallets = self._fetch_store_wallets_from_bconnect(store=store)
        return {
            "wallets": wallets,
            "default_wallet_id": wallets[0]["id"] if wallets else False,
            "store_id": store.id,
            "store_name": store.display_name,
        }

    @api.model
    def save_pending_invoice(self, invoice_id, request_id=None, store_id=None, wallet_id=None, document_type="sale"):
        self._require_cashier_access()
        invoice_id = self._safe_int(invoice_id, 0)
        if not invoice_id:
            raise UserError(_("Invalid invoice id."))
        store = self._coerce_store(store_id=store_id, required=True, require_connection=True)
        document_type = self._normalize_document_type(document_type)
        status = ""
        current_flag = ""
        collected_amount = 0.0
        if document_type == "return":
            result = self._save_pending_return_in_odoo(
                store=store,
                return_id=invoice_id,
            )
            if not isinstance(result, (tuple, list)) or len(result) < 3:
                raise UserError(_("Unexpected return save response."))
            status, current_flag, collected_amount = result[0], result[1], result[2]
        else:
            status, current_flag, collected_amount = self._save_pending_invoice_in_bconnect(
                store=store,
                invoice_id=invoice_id,
                wallet_id=wallet_id,
            )

        if status == "not_found":
            raise UserError(_("Invoice not found."))

        if status == "saved":
            if document_type == "sale":
                self._sync_odoo_header_status(store=store, invoice_id=invoice_id)
            result_wallet_id = self._safe_int(wallet_id, 0) or False
            if document_type != "sale":
                result_wallet_id = False
            return {
                "status": "saved",
                "invoice_id": invoice_id,
                "request_id": request_id or "",
                "saved_at": fields.Datetime.now(),
                "store_id": store.id,
                "wallet_id": result_wallet_id,
                "document_type": document_type,
                "collected_amount": collected_amount,
            }

        if status == "already_saved":
            result_wallet_id = self._safe_int(wallet_id, 0) or False
            if document_type != "sale":
                result_wallet_id = False
            return {
                "status": "already_saved",
                "invoice_id": invoice_id,
                "request_id": request_id or "",
                "saved_at": fields.Datetime.now(),
                "store_id": store.id,
                "wallet_id": result_wallet_id,
                "document_type": document_type,
            }

        return {
            "status": "invalid_status",
            "invoice_id": invoice_id,
            "request_id": request_id or "",
            "current_status": current_flag or "",
            "store_id": store.id,
            "document_type": document_type,
        }
