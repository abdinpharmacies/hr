# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError


class AbSalesPosApi(models.TransientModel):
    _name = "ab_sales_pos_api"
    _description = "Sales POS API"

    @api.model
    def pos_default_employee(self):
        self._require_models("ab_hr_employee")
        employee = self.env["ab_hr_employee"].sudo().search(
            [("user_id", "=", self.env.user.id)],
            limit=1,
        )
        if not employee:
            return False
        return {
            "id": employee.id,
            "name": employee.display_name or employee.name or "",
        }

    @api.model
    def _require_models(self, *model_names):
        missing = [m for m in model_names if m not in self.env.registry]
        if missing:
            raise UserError(_("Missing required models: %s") % ", ".join(missing))

    @api.model
    def _filter_vals(self, model_name, vals):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        return {key: value for key, value in (vals or {}).items() if key in model_fields}

    @api.model
    def _store_default_price(self, store_id, product):
        if not product:
            return 0.0
        try:
            store_id = int(store_id)
        except Exception:
            store_id = 0
        try:
            serial = int(product.eplus_serial or 0)
        except Exception:
            serial = 0
        if store_id and serial and "ab_sales_inventory" in self.env.registry:
            inv = self.env["ab_sales_inventory"].sudo().search([
                ("store_id", "=", store_id),
                ("product_eplus_serial", "=", serial),
            ], limit=1)
            if inv and inv.default_price:
                try:
                    return float(inv.default_price or 0.0)
                except Exception:
                    return 0.0
        try:
            return float(product.default_price or 0.0)
        except Exception:
            return 0.0

    @api.model
    def pos_product_details(self, store_id, product_id):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_product")
        try:
            store_id = int(store_id)
            product_id = int(product_id)
        except Exception:
            raise UserError(_("Invalid store or product."))
        if not store_id or not product_id:
            raise UserError(_("Store and product are required."))

        header = self.env["ab_sales_header"].new({"store_id": store_id})
        line = self.env["ab_sales_line"].new({
            "header_id": header,
            "product_id": product_id,
            "qty_str": "1",
        })

        total_balance = 0.0
        pos_balance = 0.0
        if "ab_sales_ui_api" in self.env.registry and line.product_id and line.product_id.eplus_serial:
            try:
                serial = int(line.product_id.eplus_serial or 0)
            except Exception:
                serial = 0
            if serial:
                total_by_serial, pos_by_serial = self.env["ab_sales_ui_api"]._inventory_total_and_pos_balances_by_serial(
                    [serial],
                    store_id,
                )
                total_balance = float(total_by_serial.get(serial, 0.0) or 0.0)
                pos_balance = float(pos_by_serial.get(serial, 0.0) or 0.0)

        try:
            line._recompute_inventory_json()
            line._compute_inventory_data()
            line._compute_available_prices_html()
            line._compute_inventory_table_html()
            line._compute_sell_price()
            store_default_price = self._store_default_price(store_id, line.product_id)
            line.sell_price = store_default_price
            line._compute_net_amount()

            return {
                "balance": line.balance or 0.0,
                "total_balance": total_balance,
                "pos_balance": pos_balance,
                "cost": line.cost or 0.0,
                "sell_price": store_default_price,
                "available_prices": self._available_prices_list(line),
                "inventory_table_html": line.inventory_table_html or "",
                "uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "uom_name": line.product_id.uom_id.name if line.product_id.uom_id else "",
                "uom_category_id": line.product_id.uom_category_id.id if line.product_id.uom_category_id else False,
                "uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "default_uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "default_uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "default_price": store_default_price,
            }
        except Exception:
            balance = 0.0
            if "ab_sales_inventory" in self.env.registry:
                try:
                    serial = int(line.product_id.eplus_serial or 0) if line.product_id else 0
                except Exception:
                    serial = 0
                if serial:
                    inv = self.env["ab_sales_inventory"].sudo().search(
                        [("store_id", "=", store_id), ("product_eplus_serial", "=", serial)],
                        limit=1,
                    )
                    if inv:
                        balance = inv.balance or 0.0
            return {
                "balance": balance,
                "total_balance": total_balance,
                "pos_balance": pos_balance,
                "cost": 0.0,
                "sell_price": self._store_default_price(store_id, line.product_id),
                "available_prices": [],
                "inventory_table_html": "",
                "uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "uom_name": line.product_id.uom_id.name if line.product_id.uom_id else "",
                "uom_category_id": line.product_id.uom_category_id.id if line.product_id.uom_category_id else False,
                "uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "default_uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "default_uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "default_price": self._store_default_price(store_id, line.product_id),
            }

    @api.model
    def pos_barcode_products(self, barcode=None, store_id=None):
        self._require_models("ab_product", "ab_product_barcode", "ab_product_barcode_temp")
        barcode = (barcode or "").strip()
        if not barcode:
            return []

        barcode_rows = self.env["ab_product_barcode"].search([("name", "=", barcode)])
        temp_rows = self.env["ab_product_barcode_temp"].search([("name", "=", barcode)])
        product_ids = (barcode_rows.mapped("product_ids") | temp_rows.mapped("product_ids")).ids
        if not product_ids:
            return []

        fields_list = [
            "name",
            "product_card_name",
            "code",
            "default_price",
            "allow_sell_fraction",
            "eplus_serial",
            "uom_id",
            "uom_category_id",
        ]
        products = self.env["ab_product"].browse(product_ids).read(fields_list)
        serials = [int(p.get("eplus_serial") or 0) for p in products if p.get("eplus_serial")]
        try:
            store_id = int(store_id) if store_id else None
        except Exception:
            store_id = None

        total_by_serial = {}
        pos_by_serial = {}
        if serials and "ab_sales_ui_api" in self.env.registry:
            total_by_serial, pos_by_serial = self.env["ab_sales_ui_api"]._inventory_total_and_pos_balances_by_serial(
                serials, store_id
            )

        for product in products:
            serial = int(product.get("eplus_serial") or 0)
            product["balance"] = float(total_by_serial.get(serial, 0.0) or 0.0)
            product["pos_balance"] = float(pos_by_serial.get(serial, 0.0) or 0.0)
        return products

    @api.model
    def pos_link_barcode_temp(self, barcode=None, product_ids=None):
        self._require_models("ab_product", "ab_product_barcode_temp")
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Barcode is required."))
        ids = []
        for pid in product_ids or []:
            try:
                pid = int(pid)
            except Exception:
                pid = 0
            if pid:
                ids.append(pid)
        products = self.env["ab_product"].browse(list(set(ids))).exists() if ids else self.env["ab_product"]
        Barcode = self.env["ab_product_barcode_temp"]
        record = Barcode.search([("name", "=", barcode)], limit=1)
        if record:
            if products:
                record.write({"product_ids": [(6, 0, products.ids)]})
            else:
                record.write({"product_ids": [(5, 0, 0)]})
        else:
            if not products:
                return {
                    "id": False,
                    "product_ids": [],
                }
            record = Barcode.create({
                "name": barcode,
                "product_ids": [(6, 0, products.ids)],
            })
        return {
            "id": record.id,
            "product_ids": record.product_ids.ids,
        }

    @api.model
    def pos_barcode_temp_products(self, barcode=None):
        self._require_models("ab_product", "ab_product_barcode_temp")
        barcode = (barcode or "").strip()
        if not barcode:
            return []

        Barcode = self.env["ab_product_barcode_temp"]
        record = Barcode.search([("name", "=", barcode)], limit=1)
        if not record:
            return []
        return record.product_ids.read(["display_name", "name", "code"])

    @api.model
    def _available_prices_list(self, line):
        if not line or not line.product_id:
            return []

        payload = line.inventory_json or {}
        if not isinstance(payload, dict):
            payload = {}
        rows = payload.get("data") or []

        price_qty = {}
        for row in rows:
            price = row.get("price")
            qty = row.get("qty") or 0.0
            if price is None:
                continue
            if float(qty) < 0.01:
                continue
            price_qty[float(price)] = price_qty.get(float(price), 0.0) + float(qty)

        default_price = float(line.product_id.default_price or 0.0)
        default_qty = price_qty.pop(default_price, 0.0) if price_qty else 0.0

        items = [{
            "price": default_price,
            "qty": default_qty,
            "is_default": True,
        }]

        for price in sorted(price_qty.keys()):
            items.append({
                "price": price,
                "qty": price_qty[price],
                "is_default": False,
            })

        return items

    @api.model
    def _fill_lines_balance_from_offline(self, header):
        if not header or not header.store_id:
            return
        if "ab_sales_ui_api" not in self.env.registry:
            return

        serials = []
        for line in header.line_ids:
            payload = line.inventory_json or {}
            if isinstance(payload, dict) and payload.get("data"):
                continue
            serial = int(line.product_id.eplus_serial or 0) if line.product_id else 0
            if serial:
                serials.append(serial)
        if not serials:
            return

        _total, pos_balances = self.env["ab_sales_ui_api"]._inventory_total_and_pos_balances_by_serial(
            serials, header.store_id.id
        )
        for line in header.line_ids:
            payload = line.inventory_json or {}
            if isinstance(payload, dict) and payload.get("data"):
                continue
            serial = int(line.product_id.eplus_serial or 0) if line.product_id else 0
            if not serial:
                continue
            balance = float(pos_balances.get(serial, 0.0) or 0.0)
            line.inventory_json = {
                "data": [{
                    "product_eplus_serial": serial,
                    "qty": balance,
                    "price": line.sell_price or line.product_id.default_price or 0.0,
                    "cost": 0.0,
                }],
            }

    @api.model
    def _pos_submit_response(self, header, apply_submit=True):
        if not header:
            return {}
        if apply_submit:
            action = header.action_submit()
            if isinstance(action, dict) and action.get("type"):
                action["pos_header_id"] = header.id
                return action
        return {
            "id": header.id,
            "status": header.status,
            "eplus_serial": header.eplus_serial,
        }

    @api.model
    def _pos_unavailable_action(self, header):
        return None

    @api.model
    def _pos_existing_header_action(self, header):
        return {
            "type": "ir.actions.act_window",
            "name": _("Sales Header"),
            "res_model": "ab_sales_header",
            "view_mode": "form",
            "res_id": header.id,
            "pos_header_id": header.id,
        }

    @api.model
    def _pos_existing_header_payload(self, header, max_lines=12):
        header = header.exists()
        if not header:
            return {
                "duplicate_token": True,
                "message": _("Existing invoice not found."),
                "existing_header": {},
            }

        lines = header.line_ids.sorted(key=lambda l: l.id)[:max_lines]
        line_items = []
        for line in lines:
            product = line.product_id
            line_items.append({
                "id": line.id,
                "product_name": product.display_name if product else "",
                "product_code": line.product_code or (product.code if product else ""),
                "qty": line.qty or 0.0,
                "qty_str": line.qty_str or "",
                "uom_name": line.uom_id.name if line.uom_id else "",
                "sell_price": line.sell_price or 0.0,
                "net_amount": line.net_amount or 0.0,
            })

        customer_name = (
            header.customer_id.display_name
            if header.customer_id
            else header.bill_customer_name
            or header.new_customer_name
            or ""
        )
        customer_phone = (
            header.customer_phone
            or header.customer_mobile
            or header.bill_customer_phone
            or header.new_customer_phone
            or ""
        )
        customer_address = (
            header.customer_address
            or header.bill_customer_address
            or header.new_customer_address
            or ""
        )

        return {
            "duplicate_token": True,
            "message": _("An invoice already exists with the same token."),
            "existing_header": {
                "id": header.id,
                "eplus_serial": header.eplus_serial or 0,
                "status": header.status or "",
                "store": {
                    "id": header.store_id.id if header.store_id else False,
                    "name": header.store_id.display_name if header.store_id else "",
                    "code": header.store_id.code if header.store_id else "",
                },
                "customer": {
                    "name": customer_name,
                    "phone": customer_phone,
                    "address": customer_address,
                    "code": header.customer_code or "",
                },
                "totals": {
                    "total_price": header.total_price or 0.0,
                    "total_net_amount": header.total_net_amount or 0.0,
                    "number_of_products": header.number_of_products or len(header.line_ids),
                },
                "line_count": len(header.line_ids),
                "lines_truncated": len(header.line_ids) > len(line_items),
                "lines": line_items,
                "create_date": header.create_date,
            },
        }

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_product")
        if payload is None and kwargs:
            payload = kwargs
        if not payload or not isinstance(payload, dict):
            raise UserError(_("Invalid payload."))

        header_vals = self._filter_vals("ab_sales_header", payload.get("header") or {})
        if not header_vals.get("employee_id"):
            header_vals.pop("employee_id", None)
        line_vals = payload.get("lines") or []
        token = (header_vals.get("pos_client_token") or "").strip()
        on_existing_token = (payload.get("on_existing_token") or "").strip().lower()
        if token:
            existing = self.env["ab_sales_header"].search([("pos_client_token", "=", token)], limit=1)
            if existing:
                if on_existing_token == "warn":
                    return self._pos_existing_header_payload(existing)
                return self._pos_existing_header_action(existing)
            header_vals["pos_client_token"] = token
        else:
            header_vals.pop("pos_client_token", None)
        if not header_vals.get("store_id"):
            raise UserError(_("Store is required."))
        allowed_store_ids = self.env["ab_sales_header"]._get_allowed_store_ids()
        if allowed_store_ids:
            store = self.env["ab_store"].browse(int(header_vals["store_id"])).exists()
            if store and store.id not in allowed_store_ids:
                raise UserError(_("Store %s is not allowed for sales.") % (store.display_name,))
        try:
            header = self.env["ab_sales_header"].create(header_vals)
        except (UserError, ValidationError):
            raise
        except Exception:
            if token:
                existing = self.env["ab_sales_header"].search([("pos_client_token", "=", token)], limit=1)
                if existing:
                    if on_existing_token == "warn":
                        return self._pos_existing_header_payload(existing)
                    return self._pos_existing_header_action(existing)
            raise

        product_ids = []
        for line in line_vals:
            try:
                pid = int((line or {}).get("product_id") or 0)
            except Exception:
                pid = 0
            if pid:
                product_ids.append(pid)
        products = self.env["ab_product"].browse(list(set(product_ids))).exists() if product_ids else self.env["ab_product"]
        default_uom_by_product = {p.id: (p.uom_id.id if p.uom_id else False) for p in products}

        lines_to_create = []
        for line in line_vals:
            vals = self._filter_vals("ab_sales_line", line or {})
            if not vals.get("product_id"):
                continue
            product_id = int(vals.get("product_id"))
            uom_val = vals.get("uom_id")
            if isinstance(uom_val, (list, tuple)):
                uom_val = uom_val[0] if uom_val else False
            try:
                uom_val = int(uom_val) if uom_val else 0
            except Exception:
                uom_val = 0
            if not uom_val:
                vals["uom_id"] = default_uom_by_product.get(product_id) or False
            else:
                vals["uom_id"] = uom_val
            vals["header_id"] = header.id
            vals["qty_str"] = vals.get("qty_str") or "1"
            lines_to_create.append(vals)

        if lines_to_create:
            self.env["ab_sales_line"].create(lines_to_create)

        applied_program_id = payload.get("applied_program_id")
        if applied_program_id and "applied_program_ids" in header._fields:
            if isinstance(applied_program_id, (list, tuple)) and applied_program_id:
                applied_program_id = applied_program_id[0]
            try:
                promo_id = int(applied_program_id)
            except Exception:
                promo_id = 0
            if promo_id:
                header.applied_program_ids = [(6, 0, [promo_id])]
                if hasattr(header, "btn_apply_promotion"):
                    header.btn_apply_promotion()

        self._fill_lines_balance_from_offline(header)
        return self._pos_submit_response(header.with_context(pos_submit=True), apply_submit=True)
