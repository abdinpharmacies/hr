# -*- coding: utf-8 -*-

import math
import textwrap
from datetime import datetime, time
from types import SimpleNamespace

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AbSalesUiApiBillWizardInherit(models.TransientModel):
    _inherit = "ab_sales_ui_api"

    @api.model
    def _bill_wizard_like(self, value):
        value = " ".join(str(value or "").strip().split())
        if not value:
            return ""
        return "%" + value.replace("*", "%").replace(" ", "%") + "%"

    @api.model
    def _bill_wizard_domain(self, product_query="", customer_query="", date_start=False, date_end=False,
                            eplus_serial=""):
        domain = fields.Domain("status", "in", ["pending", "saved"])
        is_search = False

        product_query = " ".join(str(product_query or "").strip().split())
        if product_query:
            is_search = True
            query_like = self._bill_wizard_like(product_query)
            Product = self.env["ab_product"]
            product_domain = fields.Domain("code", "=ilike", product_query) | fields.Domain("name", "=ilike",
                                                                                            query_like)
            if "product_card_name" in Product._fields:
                product_domain |= fields.Domain("product_card_name", "=ilike", query_like)
            product_ids = Product.search(list(product_domain), limit=400).ids
            if not product_ids:
                domain &= fields.Domain("id", "=", 0)
            else:
                domain &= fields.Domain("line_ids.product_id", "in", product_ids)

        customer_query = " ".join(str(customer_query or "").strip().split())
        if customer_query:
            is_search = True
            customer_like = self._bill_wizard_like(customer_query)
            customer_domain = (
                    fields.Domain("bill_customer_name", "=ilike", customer_like)
                    | fields.Domain("new_customer_name", "=ilike", customer_like)
                    | fields.Domain("bill_customer_phone", "=ilike", customer_like)
                    | fields.Domain("new_customer_phone", "=ilike", customer_like)
                    | fields.Domain("customer_id.name", "=ilike", customer_like)
                    | fields.Domain("customer_id.mobile_phone", "=ilike", customer_like)
                    | fields.Domain("customer_id.work_phone", "=ilike", customer_like)
                    | fields.Domain("customer_id.delivery_phone", "=ilike", customer_like)
            )
            domain &= customer_domain

        eplus_serial = str(eplus_serial or "").strip()
        if eplus_serial:
            is_search = True
            if not eplus_serial.isdigit():
                domain &= fields.Domain("id", "=", 0)
            else:
                domain &= fields.Domain("eplus_serial", "=", int(eplus_serial))

        start_date = False
        end_date = False
        if date_start:
            try:
                start_date = fields.Date.to_date(date_start)
            except Exception:
                start_date = False
        if date_end:
            try:
                end_date = fields.Date.to_date(date_end)
            except Exception:
                end_date = False

        if start_date or end_date:
            is_search = True
        if start_date and end_date and end_date < start_date:
            start_date, end_date = end_date, start_date
        if start_date:
            domain &= fields.Domain("create_date", ">=", datetime.combine(start_date, time.min))
        if end_date:
            domain &= fields.Domain("create_date", "<=", datetime.combine(end_date, time.max))

        return list(domain), is_search

    @api.model
    def _bill_wizard_compact_money(self, value):
        try:
            parsed = float(value or 0.0)
        except Exception:
            parsed = 0.0
        text = f"{parsed:.2f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    @api.model
    def _bill_wizard_align_pair(self, left, right, width):
        width = max(20, int(width or 48))
        left_text = str(left or "")
        right_text = str(right or "")
        max_right = max(1, width - 12)
        if len(right_text) > max_right:
            right_text = right_text[:max_right]
        max_left = max(1, width - len(right_text) - 1)
        if len(left_text) > max_left:
            left_text = left_text[:max_left]
        spaces = max(1, width - len(left_text) - len(right_text))
        return f"{left_text}{' ' * spaces}{right_text}"

    @api.model
    def _bill_wizard_truncate(self, value, max_len):
        text = str(value or "")
        max_len = int(max_len or 0)
        if max_len <= 0:
            return ""
        if len(text) <= max_len:
            return text
        if max_len <= 3:
            return text[:max_len]
        return text[: max_len - 3] + "..."

    @api.model
    def _bill_wizard_sales_customer_parts(self, header):
        customer_rec = getattr(header, "customer_id", False)
        customer_display = getattr(customer_rec, "display_name", "") if customer_rec else ""
        customer_name = (str(getattr(header, "bill_customer_name", "") or "").strip() or customer_display or "").strip()
        customer_phone = str(getattr(header, "bill_customer_phone", "") or "").strip()
        customer_address = str(getattr(header, "bill_customer_address", "") or "").strip()
        return customer_name, customer_phone, customer_address

    @api.model
    def _bill_wizard_return_source_header(self, return_header):
        if not return_header or not return_header.origin_header_id:
            return self.env["ab_sales_header"]
        domain = [("eplus_serial", "=", int(return_header.origin_header_id))]
        if return_header.store_id:
            domain.append(("store_id", "=", return_header.store_id.id))
        return self.env["ab_sales_header"].sudo().search(domain, order="id desc", limit=1)

    @api.model
    def _bill_wizard_header_customer_parts(self, header, record_type="sale"):
        if record_type == "return":
            source_header = self._bill_wizard_return_source_header(header)
            if source_header:
                return self._bill_wizard_sales_customer_parts(source_header)
            return self._bill_wizard_sales_customer_parts(header)
        return self._bill_wizard_sales_customer_parts(header)

    @api.model
    def _bill_wizard_decode_ref(self, header_id):
        try:
            parsed = int(header_id or 0)
        except Exception:
            parsed = 0
        if not parsed:
            raise UserError("Invalid bill id.")
        if parsed < 0:
            return "return", abs(parsed)
        return "sale", parsed

    @api.model
    def _bill_wizard_get_record_from_ref(self, header_id):
        record_type, record_id = self._bill_wizard_decode_ref(header_id)
        if record_type == "sale":
            return record_type, self._bill_wizard_get_readable_header(record_id)
        header = self.env["ab_sales_return_header"].browse(record_id).exists()
        if not header:
            raise UserError("Bill not found.")
        header.check_access_rights("read")
        header.check_access_rule("read")
        return record_type, header

    @api.model
    def _bill_wizard_header_serial_text(self, header, record_type="sale"):
        if record_type == "return":
            return str(header.origin_header_id or header.id or "")
        return str(header.eplus_serial or header.id or "")

    @api.model
    def _bill_wizard_extract_line_values(self, line):
        qty_raw = getattr(line, "qty", None)
        qty = float(qty_raw or 0.0)
        price = float(getattr(line, "sell_price", 0.0) or 0.0)
        net_amount = getattr(line, "net_amount", None)
        line_total = float(net_amount) if net_amount not in (None, False) else (qty * price)
        product = getattr(line, "product_id", False)
        product_name = (product.display_name or "").strip() if product else ""
        product_code = (getattr(line, "product_code", "") or (product.code if product else "") or "").strip()
        sold_without_balance = bool(
            getattr(line, "products_not_exist", False)
            or getattr(line, "itm_nexist", False)
        )
        return {
            "qty": qty,
            "price": price,
            "line_total": line_total,
            "product_name": product_name,
            "product_code": product_code,
            "sold_without_balance": sold_without_balance,
        }

    @api.model
    def _bill_wizard_receipt_total_value(self, header, record_type="sale", fallback_total=0.0):
        try:
            fallback_value = float(fallback_total or 0.0)
        except Exception:
            fallback_value = 0.0
        if record_type == "return":
            fields_to_try = ("total_return_value", "total_net_amount", "total_price")
        else:
            fields_to_try = ("total_net_amount", "total_price")
        for field_name in fields_to_try:
            value = getattr(header, field_name, None)
            if value in (None, False):
                continue
            try:
                return float(value)
            except Exception:
                continue
        return fallback_value

    @api.model
    def _bill_wizard_receipt_promo_data(
            self,
            header,
            record_type="sale",
            lines_total=0.0,
            receipt_total_value=0.0,
    ):
        promo_name = str(getattr(header, "applied_program_name", "") or "").strip()
        if not promo_name:
            promo_name = str(getattr(header, "selected_program_name", "") or "").strip()
        if not promo_name:
            programs = getattr(header, "applied_program_ids", False)
            if programs:
                try:
                    effective = programs.filtered(lambda p: header._program_is_effective(p))
                except Exception:
                    effective = programs
                program = effective[:1]
                if program:
                    promo_name = (program.display_name or program.name or "").strip()

        if record_type == "return":
            if not promo_name:
                source_header = self._bill_wizard_return_source_header(header)
                if source_header:
                    source_programs = getattr(source_header, "applied_program_ids", False)
                    if source_programs:
                        try:
                            source_effective = source_programs.filtered(lambda p: source_header._program_is_effective(p))
                        except Exception:
                            source_effective = source_programs
                        source_program = source_effective[:1]
                        if source_program:
                            promo_name = (source_program.display_name or source_program.name or "").strip()
            try:
                gross_value = max(0.0, float(lines_total or 0.0))
            except Exception:
                gross_value = 0.0
            try:
                paid_value = max(0.0, float(receipt_total_value or 0.0))
            except Exception:
                paid_value = 0.0
            lost_discount_value = max(0.0, gross_value - paid_value)
            return promo_name, "Lost Discount", lost_discount_value

        discount_value = 0.0
        promo_discount = getattr(header, "promo_discount_amount", None)
        if promo_discount not in (None, False, ""):
            try:
                discount_value = max(0.0, float(promo_discount))
            except Exception:
                discount_value = 0.0
        if discount_value <= 0.0:
            total_price = getattr(header, "total_price", None)
            total_net_amount = getattr(header, "total_net_amount", None)
            if total_price not in (None, False) and total_net_amount not in (None, False):
                try:
                    discount_value = max(0.0, float(total_price) - float(total_net_amount))
                except Exception:
                    discount_value = 0.0
        return promo_name, "Discount", discount_value

    @api.model
    def _bill_wizard_is_probably_pos_printer(self, printer_name):
        text = str(printer_name or "").strip().lower()
        if not text:
            return False
        thermal_markers = (
            "epson tm",
            "tm-t",
            "receipt",
            "pos",
            "80mm",
            "58mm",
            "slk",
            "xprinter",
            "xp-",
            "bixolon",
            "star tsp",
        )
        return any(marker in text for marker in thermal_markers)

    @api.model
    def _bill_wizard_build_print_text(
            self,
            header,
            lines,
            print_format="a4",
            receipt_header="",
            receipt_footer="",
            record_type="sale",
    ):
        width = 80 if print_format == "a4" else 44
        divider = "." * width
        out = []
        header_text = (receipt_header or "").strip()
        footer_text = (receipt_footer or "").strip()
        date_local = ""
        if header.create_date:
            dt_local = fields.Datetime.context_timestamp(self, header.create_date)
            date_local = dt_local.strftime("%Y-%m-%d %H:%M:%S")

        customer_name, _customer_phone, _customer_address = self._bill_wizard_header_customer_parts(
            header,
            record_type=record_type,
        )
        serial_text = self._bill_wizard_header_serial_text(header, record_type=record_type)
        if hasattr(header, 'employee_id') and header.employee_id:
            employee_name = header.employee_id.display_name
        elif header.create_uid:
            employee_name = header.create_uid.display_name
        else:
            employee_name = ''

        qty_col = 6 if width <= 48 else 9
        price_col = 7 if width <= 48 else 9
        total_col = 8 if width <= 48 else 9
        gaps = 3
        item_col = max(12, width - qty_col - price_col - total_col - gaps)

        def _line_with_amounts(item_label, qty_value="", price_value="", total_value=""):
            return (
                    str(item_label or "")[:item_col].ljust(item_col)
                    + " "
                    + str(qty_value or "")[:qty_col].rjust(qty_col)
                    + " "
                    + str(price_value or "")[:price_col].rjust(price_col)
                    + " "
                    + str(total_value or "")[:total_col].rjust(total_col)
            )

        if header_text:
            for header_line in header_text.splitlines():
                clean_line = str(header_line or "").strip()
                out.append(clean_line.center(width) if clean_line else "")
            out.append(divider)
        out.append(self._bill_wizard_align_pair("Date", date_local, width))
        out.append(self._bill_wizard_align_pair("Bill", serial_text, width))
        out.append(
            self._bill_wizard_align_pair("Store", header.store_id.display_name if header.store_id else "", width))
        if customer_name:
            out.append(self._bill_wizard_align_pair("Customer", customer_name, width))
        if employee_name:
            out.append(self._bill_wizard_align_pair("Employee", employee_name, width))
        out.append(divider)
        out.append(_line_with_amounts("Item", "Qty", "Price", "Total"))
        out.append(divider)

        total_value = 0.0
        item_count = 0
        for line in lines:
            line_data = self._bill_wizard_extract_line_values(line)
            qty = line_data["qty"]
            if record_type == "return" and math.isclose(qty, 0.0, rel_tol=0.0, abs_tol=1e-9):
                continue
            price = line_data["price"]
            line_total = line_data["line_total"]
            total_value += line_total
            item_count += 1
            product_name = line_data["product_name"]
            product_code = line_data["product_code"]
            wrapped_name = textwrap.wrap(product_name, width=item_col) if product_name else [""]
            if len(wrapped_name) > 3:
                wrapped_name = wrapped_name[:3]
                wrapped_name[-1] = self._bill_wizard_truncate(wrapped_name[-1], item_col)
            qty_text = self._bill_wizard_compact_money(qty)
            price_text = self._bill_wizard_compact_money(price)
            total_text = self._bill_wizard_compact_money(line_total)
            out.append(_line_with_amounts(wrapped_name[0], qty_text, price_text, total_text))
            for chunk in wrapped_name[1:]:
                out.append(str(chunk or "")[:item_col])
            if product_code:
                out.append(product_code[:width])
            out.append("")

        out.append(divider)
        receipt_total_value = self._bill_wizard_receipt_total_value(
            header,
            record_type=record_type,
            fallback_total=total_value,
        )
        promo_name, discount_label, promo_discount_value = self._bill_wizard_receipt_promo_data(
            header,
            record_type=record_type,
            lines_total=total_value,
            receipt_total_value=receipt_total_value,
        )
        total_label = "Pay to Customer" if record_type == "return" else "Total"
        out.append(self._bill_wizard_align_pair("Items", str(item_count), width))
        if promo_name:
            out.append(self._bill_wizard_align_pair("Promo", promo_name, width))
        if discount_label and promo_discount_value > 0.0:
            out.append(
                self._bill_wizard_align_pair(
                    discount_label,
                    "-" + self._bill_wizard_compact_money(promo_discount_value),
                    width,
                )
            )
        out.append(self._bill_wizard_align_pair(total_label, self._bill_wizard_compact_money(receipt_total_value), width))
        if footer_text:
            out.append(divider)
            out.extend(footer_text.splitlines())
        return "\n".join(out).strip()

    @api.model
    def _bill_wizard_build_print_html(
            self,
            header,
            lines,
            print_format="pos_80mm",
            receipt_header="",
            record_type="sale",
            printer_name="",
    ):
        is_pos = str(print_format or "").strip() == "pos_80mm"
        customer_name, _customer_phone, _customer_address = self._bill_wizard_header_customer_parts(
            header,
            record_type=record_type,
        )
        employee_text = (header.create_uid.display_name or "").strip() if header.create_uid else ""
        header_text = (receipt_header or "").strip()
        date_local = ""
        if header.create_date:
            dt_local = fields.Datetime.context_timestamp(self, header.create_date)
            date_local = dt_local.strftime("%Y-%m-%d %H:%M:%S")

        subtotal = 0.0
        item_count = 0
        rendered_rows = []
        for line in lines:
            line_data = self._bill_wizard_extract_line_values(line)
            qty = line_data["qty"]
            if record_type == "return" and math.isclose(qty, 0.0, rel_tol=0.0, abs_tol=1e-9):
                continue
            price = line_data["price"]
            line_total = line_data["line_total"]
            subtotal += line_total
            item_count += 1
            product_name = line_data["product_name"]
            product_code = line_data["product_code"]
            rendered_rows.append({
                "product_name": product_name,
                "product_code": product_code,
                "qty_text": self._bill_wizard_compact_money(qty),
                "price_text": self._bill_wizard_compact_money(price),
                "line_total_text": self._bill_wizard_compact_money(line_total),
            })

        receipt_total_value = self._bill_wizard_receipt_total_value(
            header,
            record_type=record_type,
            fallback_total=subtotal,
        )
        promo_name, discount_label, promo_discount_value = self._bill_wizard_receipt_promo_data(
            header,
            record_type=record_type,
            lines_total=subtotal,
            receipt_total_value=receipt_total_value,
        )
        total_text = self._bill_wizard_compact_money(receipt_total_value)
        total_label = "Pay to Customer" if record_type == "return" else "Total"
        template_xmlid = (
            "ab_sales.bill_wizard_receipt_print_html_pos"
            if is_pos else "ab_sales.bill_wizard_receipt_print_html_a4"
        )
        values = {
            "receipt_header": header_text,
            "date_value": date_local,
            "serial_text": self._bill_wizard_header_serial_text(header, record_type=record_type),
            "store_name": header.store_id.display_name if header.store_id else "",
            "customer_name": customer_name,
            "customer_phone": _customer_phone,
            "customer_address": _customer_address,
            "employee_name": employee_text,
            "lines": rendered_rows,
            "item_count": item_count,
            "promo_name": promo_name,
            "discount_label": discount_label,
            "promo_discount_text": self._bill_wizard_compact_money(promo_discount_value) if promo_discount_value > 0.0 else "",
            "total_label": total_label,
            "total_text": total_text,
            "printer_name": str(printer_name or "").strip(),
        }
        rendered = self.env["ir.qweb"]._render(template_xmlid, values)
        if isinstance(rendered, bytes):
            return rendered.decode("utf-8", errors="replace")
        return str(rendered)

    @api.model
    def _bill_wizard_prepare_print_content(self, header_id, print_format="a4"):
        record_type, header = self._bill_wizard_get_record_from_ref(header_id)
        settings = self.get_printer_settings()
        if record_type == "return":
            lines = self.env["ab_sales_return_line"].search(
                [("header_id", "=", header.id), ("qty", "!=", 0)],
                order="id asc",
            )
            receipt_header = "Sales Return Receipt"
        else:
            lines = self.env["ab_sales_line"].search([("header_id", "=", header.id)], order="id asc")
            receipt_header = settings.get("receipt_header") or "Sales Receipt"
        if not lines:
            raise UserError(_("No lines to print."))

        fmt = "pos_80mm" if str(print_format or "").strip() == "pos_80mm" else "a4"
        content = self._bill_wizard_build_print_text(
            header=header,
            lines=lines,
            print_format=fmt,
            receipt_header=receipt_header,
            receipt_footer=settings.get("receipt_footer") or "Thank you.",
            record_type=record_type,
        )
        return record_type, header, lines, fmt, settings, content

    @api.model
    def _bill_wizard_payload_float(self, value, default=0.0):
        try:
            return float(value)
        except Exception:
            return float(default or 0.0)

    @api.model
    def _bill_wizard_payload_datetime(self, value):
        if not value:
            return fields.Datetime.now()
        try:
            parsed = fields.Datetime.to_datetime(value)
            return parsed or fields.Datetime.now()
        except Exception:
            return fields.Datetime.now()

    @api.model
    def _bill_wizard_payload_header_proxy(self, header_payload):
        payload = header_payload if isinstance(header_payload, dict) else {}

        def _txt(*keys):
            for key in keys:
                value = str(payload.get(key) or "").strip()
                if value:
                    return value
            return ""

        store_name = _txt("store_name")
        store_id = int(self._bill_wizard_payload_float(payload.get("store_id"), default=0.0) or 0)
        customer_name = _txt("customer_name", "bill_customer_name", "new_customer_name")
        employee_name = _txt("employee_name")
        serial_text = _txt("eplus_serial", "invoice_number", "local_number", "id")
        origin_header_id = int(self._bill_wizard_payload_float(payload.get("origin_header_id"), default=0.0) or 0)

        store_proxy = SimpleNamespace(id=store_id, display_name=store_name) if store_name or store_id else False
        customer_proxy = SimpleNamespace(id=0, display_name=customer_name)
        employee_proxy = SimpleNamespace(id=0, display_name=employee_name) if employee_name else False

        header_id = int(self._bill_wizard_payload_float(payload.get("id"), default=0.0) or 0)
        total_price_raw = payload.get("total_price") if "total_price" in payload else None
        total_net_amount_raw = payload.get("total_net_amount") if "total_net_amount" in payload else None
        total_return_value_raw = payload.get("total_return_value") if "total_return_value" in payload else None
        promo_discount_amount_raw = payload.get("promo_discount_amount") if "promo_discount_amount" in payload else None
        return SimpleNamespace(
            id=header_id,
            eplus_serial=serial_text,
            origin_header_id=origin_header_id,
            create_date=self._bill_wizard_payload_datetime(payload.get("create_date")),
            store_id=store_proxy,
            customer_id=customer_proxy,
            create_uid=employee_proxy,
            employee_id=employee_proxy,
            bill_customer_name=_txt("bill_customer_name", "customer_name", "new_customer_name"),
            bill_customer_phone=_txt("bill_customer_phone", "customer_phone", "customer_mobile", "new_customer_phone"),
            bill_customer_address=_txt("bill_customer_address", "invoice_address", "customer_address",
                                       "new_customer_address"),
            customer_name=_txt("customer_name", "bill_customer_name", "new_customer_name"),
            customer_phone=_txt("customer_phone", "customer_mobile", "bill_customer_phone", "new_customer_phone"),
            customer_mobile=_txt("customer_mobile", "customer_phone", "bill_customer_phone", "new_customer_phone"),
            customer_address=_txt("customer_address", "bill_customer_address", "invoice_address",
                                  "new_customer_address"),
            total_price=(
                self._bill_wizard_payload_float(total_price_raw, default=0.0)
                if total_price_raw is not None and total_price_raw != ""
                else None
            ),
            total_net_amount=(
                self._bill_wizard_payload_float(total_net_amount_raw, default=0.0)
                if total_net_amount_raw is not None and total_net_amount_raw != ""
                else None
            ),
            total_return_value=(
                self._bill_wizard_payload_float(total_return_value_raw, default=0.0)
                if total_return_value_raw is not None and total_return_value_raw != ""
                else None
            ),
            promo_discount_amount=(
                self._bill_wizard_payload_float(promo_discount_amount_raw, default=0.0)
                if promo_discount_amount_raw is not None and promo_discount_amount_raw != ""
                else None
            ),
            applied_program_name=_txt("applied_program_name", "promo_name"),
            selected_program_name=_txt("selected_program_name"),
            invoice_address=_txt("invoice_address", "bill_customer_address", "customer_address",
                                 "new_customer_address"),
            new_customer_name=_txt("new_customer_name"),
            new_customer_phone=_txt("new_customer_phone"),
            new_customer_address=_txt("new_customer_address"),
        )

    @api.model
    def _bill_wizard_payload_line_proxies(self, lines_payload):
        proxies = []
        for raw_line in lines_payload if isinstance(lines_payload, list) else []:
            line = raw_line if isinstance(raw_line, dict) else {}
            qty = self._bill_wizard_payload_float(line.get("qty"), default=0.0)
            if not qty:
                qty = self._bill_wizard_payload_float(line.get("qty_str"), default=0.0)
            price = self._bill_wizard_payload_float(line.get("sell_price"), default=0.0)
            line_total = self._bill_wizard_payload_float(line.get("net_amount"), default=qty * price)
            product_name = str(line.get("product_name") or "").strip()
            product_code = str(line.get("product_code") or "").strip()
            product_proxy = SimpleNamespace(display_name=product_name, code=product_code) if (
                    product_name or product_code
            ) else False
            proxies.append(
                SimpleNamespace(
                    qty=qty,
                    sell_price=price,
                    net_amount=line_total,
                    product_id=product_proxy,
                    product_code=product_code,
                    products_not_exist=bool(line.get("sold_without_balance")),
                    itm_nexist=bool(line.get("sold_without_balance")),
                )
            )
        return proxies

    @api.model
    def _bill_wizard_prepare_payload_print_content(self, payload=None, print_format="a4"):
        payload = payload if isinstance(payload, dict) else {}
        header_payload = payload.get("header") if isinstance(payload.get("header"), dict) else {}
        lines_payload = payload.get("lines") if isinstance(payload.get("lines"), list) else []
        if not lines_payload:
            raise UserError(_("No lines to print."))

        settings = self.get_printer_settings()
        fmt = "pos_80mm" if str(print_format or "").strip() == "pos_80mm" else "a4"
        record_type = "return" if str(payload.get("document_type") or "").strip().lower() == "return" else "sale"
        header_proxy = self._bill_wizard_payload_header_proxy(header_payload)
        line_proxies = self._bill_wizard_payload_line_proxies(lines_payload)
        if not line_proxies:
            raise UserError(_("No lines to print."))

        receipt_header = "Sales Return Receipt" if record_type == "return" else (
                settings.get("receipt_header") or "Sales Receipt"
        )
        content = self._bill_wizard_build_print_text(
            header=header_proxy,
            lines=line_proxies,
            print_format=fmt,
            receipt_header=receipt_header,
            receipt_footer=settings.get("receipt_footer") or "Thank you.",
            record_type=record_type,
        )
        return record_type, header_proxy, line_proxies, fmt, settings, content, receipt_header

    @api.model
    def bill_wizard_render_print_text_from_payload(self, payload=None, print_format="a4"):
        _record_type, _header, _lines, fmt, _settings, content, _receipt_header = self._bill_wizard_prepare_payload_print_content(
            payload=payload,
            print_format=print_format,
        )
        return {
            "ok": True,
            "content": content,
            "print_format": fmt,
        }

    @api.model
    def bill_wizard_render_print_html_from_payload(self, payload=None, print_format="a4"):
        record_type, header, lines, fmt, _settings, _content, receipt_header = self._bill_wizard_prepare_payload_print_content(
            payload=payload,
            print_format=print_format,
        )
        html_content = self._bill_wizard_build_print_html(
            header=header,
            lines=lines,
            print_format=fmt,
            receipt_header=receipt_header,
            record_type=record_type,
            printer_name="",
        )
        return {
            "ok": True,
            "content": html_content,
            "print_format": fmt,
        }

    @api.model
    def bill_wizard_direct_print_from_payload(
            self,
            payload=None,
            print_format="a4",
            printer_name="",
            printer_id=0,
            selected_printer=None,
    ):
        record_type, header, lines, fmt, settings, content, receipt_header = self._bill_wizard_prepare_payload_print_content(
            payload=payload,
            print_format=print_format,
        )
        user_prefs = self._bill_wizard_get_user_print_preferences()
        selected_payload = selected_printer if isinstance(selected_printer, dict) else {}
        try:
            requested_printer_id = int(printer_id or selected_payload.get("id") or user_prefs.get("printer_id") or 0)
        except Exception:
            requested_printer_id = 0
        requested_printer_name = str(
            printer_name
            or selected_payload.get("label")
            or selected_payload.get("name")
            or user_prefs.get("printer_name")
            or settings.get("printer_name")
            or ""
        ).strip()
        selected_printer_rec = self._bill_wizard_resolve_selected_printer(
            printer_id=requested_printer_id,
            printer_name=requested_printer_name,
            print_format=fmt,
        )
        selected_printer_label = selected_printer_rec.build_display_label() if selected_printer_rec else requested_printer_name
        if not selected_printer_rec and requested_printer_id:
            selected_printer_label = ""
        selected_format = (
            selected_printer_rec.paper_size if selected_printer_rec and selected_printer_rec.paper_size in ("pos_80mm",
                                                                                                            "a4")
            else fmt
        )
        if (
                not selected_printer_rec
                and selected_format == "pos_80mm"
                and selected_printer_label
                and not self._bill_wizard_is_probably_pos_printer(selected_printer_label)
        ):
            raise UserError(_("POS 80mm format requires a thermal ESC/POS printer queue."))
        html_content = self._bill_wizard_build_print_html(
            header=header,
            lines=lines,
            print_format=selected_format,
            receipt_header=receipt_header,
            record_type=record_type,
            printer_name=selected_printer_label,
        )
        if selected_printer_rec:
            selected_printer_rec.dispatch_print_html(
                html_content,
                print_format=selected_format,
            )
        else:
            self._direct_print_html(
                html_content,
                printer_name=selected_printer_label,
                print_format=selected_format,
            )
        return {
            "ok": True,
            "printer_id": selected_printer_rec.id if selected_printer_rec else 0,
            "printer_name": selected_printer_label,
            "print_format": selected_format,
        }

    @api.model
    def _bill_wizard_header_payload(self, header, record_type="sale"):
        customer_name, customer_phone, customer_address = self._bill_wizard_header_customer_parts(
            header,
            record_type=record_type,
        )
        if record_type == "return":
            payload_id = -int(header.id)
            eplus_serial = int(header.origin_header_id or 0)
            number_of_products = int(len(header.line_ids))
            total_price = float(header.total_return_value or 0.0)
            total_net_amount = float(header.total_return_value or 0.0)
            notes = (header.notes or "").strip()
            can_return = False
            doc_type = "return"
        else:
            payload_id = int(header.id)
            eplus_serial = int(header.eplus_serial or 0)
            number_of_products = int(header.number_of_products or 0)
            total_price = float(header.total_price or 0.0)
            total_net_amount = float(header.total_net_amount or 0.0)
            notes = (header.description or "").strip()
            can_return = bool(header.eplus_serial and header.status in ("pending", "saved"))
            doc_type = "sale"
        return {
            "id": payload_id,
            "eplus_serial": eplus_serial,
            "status": header.status or "",
            "store_id": header.store_id.id if header.store_id else False,
            "store_name": header.store_id.display_name if header.store_id else "",
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_address": customer_address,
            "number_of_products": number_of_products,
            "total_price": total_price,
            "total_net_amount": total_net_amount,
            "notes": notes,
            "create_date": header.create_date,
            "created_uid": (
                f"{header.create_uid.display_name} ({header.create_uid.id})"
                if header.create_uid
                else ""
            ),
            "can_return": can_return,
            "document_type": doc_type,
        }

    @api.model
    def _bill_wizard_return_domain(
            self,
            product_query="",
            customer_query="",
            date_start=False,
            date_end=False,
            eplus_serial="",
    ):
        domain = fields.Domain("status", "in", ["pending", "saved"])
        is_search = False

        product_query = " ".join(str(product_query or "").strip().split())
        if product_query:
            is_search = True
            query_like = self._bill_wizard_like(product_query)
            Product = self.env["ab_product"]
            product_domain = fields.Domain("code", "=ilike", product_query) | fields.Domain("name", "=ilike",
                                                                                            query_like)
            if "product_card_name" in Product._fields:
                product_domain |= fields.Domain("product_card_name", "=ilike", query_like)
            product_ids = Product.search(list(product_domain), limit=400).ids
            if not product_ids:
                domain &= fields.Domain("id", "=", 0)
            else:
                domain &= fields.Domain("line_ids.product_id", "in", product_ids)

        customer_query = " ".join(str(customer_query or "").strip().split())
        if customer_query:
            is_search = True
            customer_like = self._bill_wizard_like(customer_query)
            source_domain = (
                    fields.Domain("bill_customer_name", "=ilike", customer_like)
                    | fields.Domain("new_customer_name", "=ilike", customer_like)
                    | fields.Domain("bill_customer_phone", "=ilike", customer_like)
                    | fields.Domain("new_customer_phone", "=ilike", customer_like)
                    | fields.Domain("customer_id.name", "=ilike", customer_like)
                    | fields.Domain("customer_id.mobile_phone", "=ilike", customer_like)
                    | fields.Domain("customer_id.work_phone", "=ilike", customer_like)
                    | fields.Domain("customer_id.delivery_phone", "=ilike", customer_like)
            )
            source_headers = self.env["ab_sales_header"].search(list(source_domain), limit=1200)
            serials = [int(s) for s in source_headers.mapped("eplus_serial") if s]
            if not serials:
                domain &= fields.Domain("id", "=", 0)
            else:
                domain &= fields.Domain("origin_header_id", "in", serials)

        eplus_serial = str(eplus_serial or "").strip()
        if eplus_serial:
            is_search = True
            if not eplus_serial.isdigit():
                domain &= fields.Domain("id", "=", 0)
            else:
                domain &= fields.Domain("origin_header_id", "=", int(eplus_serial))

        start_date = False
        end_date = False
        if date_start:
            try:
                start_date = fields.Date.to_date(date_start)
            except Exception:
                start_date = False
        if date_end:
            try:
                end_date = fields.Date.to_date(date_end)
            except Exception:
                end_date = False

        if start_date or end_date:
            is_search = True
        if start_date and end_date and end_date < start_date:
            start_date, end_date = end_date, start_date
        if start_date:
            domain &= fields.Domain("create_date", ">=", datetime.combine(start_date, time.min))
        if end_date:
            domain &= fields.Domain("create_date", "<=", datetime.combine(end_date, time.max))

        return list(domain), is_search

    @api.model
    def _bill_wizard_get_readable_header(self, header_id):
        try:
            header_id = int(header_id or 0)
        except Exception:
            header_id = 0
        if not header_id:
            raise UserError("Invalid bill id.")

        header = self.env["ab_sales_header"].browse(header_id).exists()
        if not header:
            raise UserError("Bill not found.")
        header.check_access_rights("read")
        header.check_access_rule("read")
        return header

    @api.model
    def bill_wizard_search(
            self,
            product_query="",
            customer_query="",
            date_start=False,
            date_end=False,
            eplus_serial="",
            page=1,
            per_page=20,
            query="",
            limit=0,
    ):
        legacy_query = (query or "").strip()
        if legacy_query and not any([product_query, customer_query, date_start, date_end, eplus_serial]):
            if legacy_query.isdigit():
                eplus_serial = legacy_query
            else:
                product_query = legacy_query

        domain, is_search = self._bill_wizard_domain(
            product_query=product_query,
            customer_query=customer_query,
            date_start=date_start,
            date_end=date_end,
            eplus_serial=eplus_serial,
        )
        return_domain, return_is_search = self._bill_wizard_return_domain(
            product_query=product_query,
            customer_query=customer_query,
            date_start=date_start,
            date_end=date_end,
            eplus_serial=eplus_serial,
        )
        is_search = bool(is_search or return_is_search)
        per_page = 20
        try:
            page = int(page or 1)
        except Exception:
            page = 1
        page = max(page, 1)

        Header = self.env["ab_sales_header"]
        ReturnHeader = self.env["ab_sales_return_header"]

        def _sort_key(pair):
            rec = pair[1]
            dt = rec.create_date
            if isinstance(dt, str):
                try:
                    dt = fields.Datetime.to_datetime(dt)
                except Exception:
                    dt = False
            return (dt or datetime.min, rec.id)

        if not is_search:
            sale_headers = Header.search(domain, order="create_date desc, id desc", limit=20, offset=0)
            return_headers = ReturnHeader.search(return_domain, order="create_date desc, id desc", limit=20, offset=0)
            merged = [("sale", h) for h in sale_headers] + [("return", h) for h in return_headers]
            merged.sort(key=_sort_key, reverse=True)
            merged = merged[:20]
            total_count = len(merged)
            page = 1
            page_count = 1
            headers_payload = [self._bill_wizard_header_payload(rec, record_type=rec_type) for rec_type, rec in merged]
        else:
            sale_count = Header.search_count(domain)
            return_count = ReturnHeader.search_count(return_domain)
            total_count = sale_count + return_count
            page_count = max(1, int(math.ceil(total_count / float(per_page)))) if total_count else 1
            if page > page_count:
                page = page_count
            offset = (page - 1) * per_page if total_count else 0
            fetch_limit = max(20, offset + per_page)
            sale_headers = Header.search(domain, order="create_date desc, id desc", limit=fetch_limit, offset=0)
            return_headers = ReturnHeader.search(return_domain, order="create_date desc, id desc", limit=fetch_limit,
                                                 offset=0)
            merged = [("sale", h) for h in sale_headers] + [("return", h) for h in return_headers]
            merged.sort(key=_sort_key, reverse=True)
            page_slice = merged[offset:offset + per_page]
            headers_payload = [self._bill_wizard_header_payload(rec, record_type=rec_type) for rec_type, rec in
                               page_slice]
        return {
            "items": headers_payload,
            "is_search": bool(is_search),
            "filters": {
                "product_query": (product_query or "").strip(),
                "customer_query": (customer_query or "").strip(),
                "date_start": date_start or False,
                "date_end": date_end or False,
                "eplus_serial": (eplus_serial or "").strip(),
            },
            "pagination": {
                "page": page,
                "per_page": per_page,
                "page_count": page_count,
                "total_count": total_count,
            },
        }

    @api.model
    def bill_wizard_details(self, header_id):
        record_type, header = self._bill_wizard_get_record_from_ref(header_id)
        if record_type == "return":
            lines = self.env["ab_sales_return_line"].search(
                [("header_id", "=", header.id), ("qty", "!=", 0)],
                order="id asc",
            )
        else:
            lines = self.env["ab_sales_line"].search([("header_id", "=", header.id)], order="id asc")
        line_items = []
        for line in lines:
            line_data = self._bill_wizard_extract_line_values(line)
            line_items.append(
                {
                    "line_id": int(line.id),
                    "product_id": line.product_id.id if line.product_id else False,
                    "product_name": line.product_id.display_name if line.product_id else "",
                    "product_code": line_data["product_code"],
                    "qty": line_data["qty"],
                    "sell_price": line_data["price"],
                    "net_amount": line_data["line_total"],
                    "balance": float(getattr(line, "balance", 0.0) or getattr(line, "max_returnable_qty", 0.0) or 0.0),
                    "unavailable_reason": getattr(line, "unavailable_reason", "") or "",
                    "unavailable_reason_other": getattr(line, "unavailable_reason_other", "") or "",
                    "sold_without_balance": line_data["sold_without_balance"],
                }
            )

        payload = self._bill_wizard_header_payload(header, record_type=record_type)
        payload["lines"] = line_items
        return payload

    @api.model
    def bill_wizard_update_notes(self, header_id, notes=""):
        record_type, header = self._bill_wizard_get_record_from_ref(header_id)
        clean_notes = (notes or "").strip()
        if record_type == "return":
            header.sudo().write({"notes": clean_notes})
        else:
            header.sudo().write({"description": clean_notes})
        return self._bill_wizard_header_payload(header.sudo(), record_type=record_type)

    @api.model
    def bill_wizard_open_return_action(self, header_id):
        record_type, header = self._bill_wizard_get_record_from_ref(header_id)
        if record_type != "sale":
            raise UserError("Return action is available for sales bills only.")
        if not header.eplus_serial:
            raise UserError("This bill has no ePlus serial.")
        try:
            return header.action_open_sales_return()
        except AccessError:
            raise UserError("You do not have access to sales return yet.")

    @api.model
    def bill_wizard_render_print_text(self, header_id, print_format="a4"):
        _record_type, _header, _lines, fmt, _settings, content = self._bill_wizard_prepare_print_content(
            header_id=header_id,
            print_format=print_format,
        )
        return {
            "ok": True,
            "content": content,
            "print_format": fmt,
        }

    @api.model
    def bill_wizard_render_print_html(self, header_id, print_format="a4"):
        record_type, header, lines, fmt, settings, _content = self._bill_wizard_prepare_print_content(
            header_id=header_id,
            print_format=print_format,
        )
        html_content = self._bill_wizard_build_print_html(
            header=header,
            lines=lines,
            print_format=fmt,
            receipt_header="Sales Return Receipt" if record_type == "return" else (
                    settings.get("receipt_header") or "Sales Receipt"
            ),
            record_type=record_type,
            printer_name="",
        )
        return {
            "ok": True,
            "content": html_content,
            "print_format": fmt,
        }

    @api.model
    def bill_wizard_direct_print(
            self,
            header_id,
            print_format="a4",
            printer_name="",
            printer_id=0,
            selected_printer=None,
    ):
        record_type, header, lines, fmt, settings, content = self._bill_wizard_prepare_print_content(
            header_id=header_id,
            print_format=print_format,
        )
        user_prefs = self._bill_wizard_get_user_print_preferences()
        selected_payload = selected_printer if isinstance(selected_printer, dict) else {}
        try:
            requested_printer_id = int(printer_id or selected_payload.get("id") or user_prefs.get("printer_id") or 0)
        except Exception:
            requested_printer_id = 0
        requested_printer_name = str(
            printer_name
            or selected_payload.get("label")
            or selected_payload.get("name")
            or user_prefs.get("printer_name")
            or settings.get("printer_name")
            or ""
        ).strip()
        selected_printer_rec = self._bill_wizard_resolve_selected_printer(
            printer_id=requested_printer_id,
            printer_name=requested_printer_name,
            print_format=fmt,
        )
        selected_printer_label = selected_printer_rec.build_display_label() if selected_printer_rec else requested_printer_name
        if not selected_printer_rec and requested_printer_id:
            selected_printer_label = ""
        selected_format = (
            selected_printer_rec.paper_size if selected_printer_rec and selected_printer_rec.paper_size in ("pos_80mm",
                                                                                                            "a4")
            else fmt
        )
        if (
                not selected_printer_rec
                and selected_format == "pos_80mm"
                and selected_printer_label
                and not self._bill_wizard_is_probably_pos_printer(selected_printer_label)
        ):
            raise UserError(_("POS 80mm format requires a thermal ESC/POS printer queue."))
        html_content = self._bill_wizard_build_print_html(
            header=header,
            lines=lines,
            print_format=selected_format,
            receipt_header="Sales Return Receipt" if record_type == "return" else (
                    settings.get("receipt_header") or "Sales Receipt"),
            record_type=record_type,
            printer_name=selected_printer_label,
        )
        if selected_printer_rec:
            selected_printer_rec.dispatch_print_html(
                html_content,
                print_format=selected_format,
            )
        else:
            self._direct_print_html(
                html_content,
                printer_name=selected_printer_label,
                print_format=selected_format,
            )
        return {
            "ok": True,
            "printer_id": selected_printer_rec.id if selected_printer_rec else 0,
            "printer_name": selected_printer_label,
            "print_format": selected_format,
        }
