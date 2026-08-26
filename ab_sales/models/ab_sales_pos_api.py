# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AbSalesPosApi(models.TransientModel):
    _name = "ab_sales_pos_api"
    _description = "Sales POS API"

    @api.model
    def pos_default_employee(self):
        """
        Return the employee linked to the current user for POS defaults.

        The response contains only the employee id and display name, or
        `False` when the current user has no matching employee record.
        """
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
    def _pos_draft_cache_key(self, cache_key=None):
        key = str(cache_key or "").strip()
        return key or "ab_sales_pos_cache_v1_%s" % self.env.uid

    @api.model
    def _pos_draft_employee(self, employee_id=None, pos_hr_session_token=None):
        employee = self.env["ab_hr_employee"]
        token = str(pos_hr_session_token or "").strip()
        if token and "ab_employee_access_sales_pos_session" in self.env.registry:
            session = self.env["ab_employee_access_sales_pos_api"]._get_session(
                token,
                states=["active", "locked"],
                required=False,
            )
            if session and session.service_user_id.id == self.env.uid:
                return session.employee_id
            return employee

        try:
            parsed_employee_id = int(employee_id or 0)
        except Exception:
            parsed_employee_id = 0
        if not parsed_employee_id:
            return employee

        if "ab_employee_access_sales_pos_session" in self.env.registry:
            return employee

        return self.env["ab_hr_employee"].sudo().browse(parsed_employee_id).exists()[:1]

    @api.model
    def _pos_draft_cache_record(
            self,
            cache_key=None,
            employee_id=None,
            pos_hr_session_token=None,
            create=False,
    ):
        self._require_models("ab_sales_pos_draft_cache", "ab_hr_employee")
        key = self._pos_draft_cache_key(cache_key)
        employee = self._pos_draft_employee(
            employee_id=employee_id,
            pos_hr_session_token=pos_hr_session_token,
        )
        employee_scope_key = int(employee.id or 0)
        Cache = self.env["ab_sales_pos_draft_cache"].sudo()
        record = Cache.search(
            [
                ("user_id", "=", self.env.uid),
                ("employee_scope_key", "=", employee_scope_key),
                ("cache_key", "=", key),
            ],
            limit=1,
        )
        if not record and create:
            record = Cache.create(
                {
                    "user_id": self.env.uid,
                    "employee_id": employee.id or False,
                    "employee_scope_key": employee_scope_key,
                    "cache_key": key,
                    "selected_id": "",
                    "last_synced_at": fields.Datetime.now(),
                    "bills_json": [],
                }
            )
        return record, key, employee

    @api.model
    def pos_load_draft_cache(self, cache_key=None, employee_id=None, pos_hr_session_token=None):
        record, key, employee = self._pos_draft_cache_record(
            cache_key=cache_key,
            employee_id=employee_id,
            pos_hr_session_token=pos_hr_session_token,
        )
        bills = record.bills_json if record and isinstance(record.bills_json, list) else []
        bills = self._pos_draft_cache_with_product_pricing_flags(bills)
        return {
            "cache_key": key,
            "employee_id": employee.id or False,
            "bills": bills,
            "selected_id": record.selected_id if record else "",
            "last_synced_at": record.last_synced_at if record else False,
            "updated_at": record.write_date if record else False,
        }

    @api.model
    def _pos_draft_cache_with_product_pricing_flags(self, bills):
        if not isinstance(bills, list) or "ab_product" not in self.env.registry:
            return bills

        product_ids = set()
        for bill in bills:
            if not isinstance(bill, dict):
                continue
            for line in bill.get("lines") or []:
                if not isinstance(line, dict):
                    continue
                try:
                    product_id = int(line.get("product_id") or 0)
                except Exception:
                    product_id = 0
                if product_id:
                    product_ids.add(product_id)
        if not product_ids:
            return bills

        products = self.env["ab_product"].sudo().browse(list(product_ids)).exists().read([
            "is_priced",
            "only_default_sales_uom",
            "uom_id",
        ])
        uom_ids = []
        product_flags = {}
        for row in products:
            uom_val = row.get("uom_id") or False
            uom_id = uom_val[0] if isinstance(uom_val, (list, tuple)) and uom_val else False
            if uom_id:
                uom_ids.append(uom_id)
            product_flags[row["id"]] = {
                "is_priced": bool(row.get("is_priced")),
                "only_default_sales_uom": bool(row.get("only_default_sales_uom")),
                "uom_id": uom_id,
                "uom_name": uom_val[1] if isinstance(uom_val, (list, tuple)) and len(uom_val) > 1 else "",
            }
        uom_factor_by_id = {}
        if uom_ids:
            uoms = self.env["ab_product_uom"].sudo().browse(list(set(uom_ids))).read(["factor"])
            uom_factor_by_id = {int(uom["id"]): float(uom.get("factor") or 1.0) for uom in uoms}
        for bill in bills:
            if not isinstance(bill, dict):
                continue
            for line in bill.get("lines") or []:
                if not isinstance(line, dict):
                    continue
                try:
                    product_id = int(line.get("product_id") or 0)
                except Exception:
                    product_id = 0
                flags = product_flags.get(product_id)
                if flags:
                    uom_id = flags["uom_id"]
                    uom_factor = uom_factor_by_id.get(uom_id, 1.0) if uom_id else 1.0
                    line["product_is_priced"] = flags["is_priced"]
                    line["only_default_sales_uom"] = flags["only_default_sales_uom"]
                    line["default_uom_id"] = uom_id or line.get("default_uom_id") or False
                    line["default_uom_name"] = flags["uom_name"] or line.get("default_uom_name") or ""
                    line["default_uom_factor"] = uom_factor
                    if flags["only_default_sales_uom"] and uom_id:
                        line["uom_id"] = uom_id
                        line["uom_name"] = flags["uom_name"]
                        line["uom_factor"] = uom_factor
        return bills

    @api.model
    def pos_save_draft_cache(
            self,
            cache_key=None,
            bills=None,
            selected_id=None,
            employee_id=None,
            pos_hr_session_token=None,
    ):
        record, key, employee = self._pos_draft_cache_record(
            cache_key=cache_key,
            employee_id=employee_id,
            pos_hr_session_token=pos_hr_session_token,
            create=True,
        )
        safe_bills = bills if isinstance(bills, list) else []
        selected = str(selected_id or "").strip()
        now = fields.Datetime.now()
        record.write(
            {
                "cache_key": key,
                "employee_id": employee.id or False,
                "selected_id": selected,
                "last_synced_at": now,
                "bills_json": safe_bills,
            }
        )
        return {
            "cache_key": key,
            "employee_id": employee.id or False,
            "count": len(safe_bills),
            "selected_id": selected,
            "last_synced_at": record.last_synced_at,
            "updated_at": record.write_date,
        }

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
    def _empty_promo_payload(self, total_net_amount=0.0):
        total_net_amount = float(total_net_amount or 0.0)
        return {
            "available_programs": [],
            "applied_program_id": False,
            "applied_program_name": "",
            "selected_program_id": False,
            "selected_program_name": "",
            "promo_message": "",
            "promo_discount_amount": 0.0,
            "amount_total_after_promo": total_net_amount,
            "total_net_amount": total_net_amount,
        }

    @api.model
    def pos_promotions(self, store_id=None, lines=None, applied_program_id=None, manual_clear=False):
        """
        Base fallback when `ab_sales_promo` is not installed.
        Returns a valid empty promo payload with net total equal to line total.
        """
        self._require_models("ab_sales_header", "ab_sales_line")
        try:
            store_id = int(store_id or 0)
        except Exception:
            store_id = 0
        if not store_id:
            return self._empty_promo_payload()

        line_commands = []
        for line in lines or []:
            try:
                product_id = int(line.get("product_id") or 0)
            except Exception:
                product_id = 0
            if not product_id:
                continue
            qty_str = line.get("qty_str") or "1"
            try:
                sell_price = float(line.get("sell_price") or 0.0)
            except Exception:
                sell_price = 0.0
            uom_id = line.get("uom_id") or False
            if isinstance(uom_id, (list, tuple)):
                uom_id = uom_id[0] if uom_id else False
            try:
                uom_id = int(uom_id) if uom_id else False
            except Exception:
                uom_id = False
            line_commands.append(
                (0, 0, {
                    "product_id": product_id,
                    "qty_str": qty_str,
                    "sell_price": sell_price,
                    "uom_id": uom_id,
                })
            )

        if not line_commands:
            return self._empty_promo_payload()

        header = self.env["ab_sales_header"].new({
            "store_id": store_id,
            "line_ids": line_commands,
        })
        total = 0.0
        if header.line_ids:
            header.line_ids._compute_qty()
            header.line_ids._compute_amount()
            total = float(
                sum(float(line.price_subtotal or (line.qty or 0.0) * (line.sell_price or 0.0)) for line in
                    header.line_ids)
            )
        return self._empty_promo_payload(total_net_amount=total)

    @api.model
    def pos_product_details(self, store_id, product_id):
        """
        Return POS product details for a store-specific product selection.

        The payload includes balances, pricing, UoM information, available
        prices, and the rendered inventory table, with a reduced fallback
        payload when detailed inventory computation is not available.
        """
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
                total_by_serial, pos_by_serial = self.env[
                    "ab_sales_ui_api"]._inventory_total_and_pos_balances_by_serial(
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
                "is_priced": bool(line.product_id.is_priced),
                "inventory_table_html": line.inventory_table_html or "",
                "uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "uom_name": line.product_id.uom_id.name if line.product_id.uom_id else "",
                "uom_category_id": line.product_id.uom_category_id.id if line.product_id.uom_category_id else False,
                "uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "default_uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "default_uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "only_default_sales_uom": bool(line.product_id.only_default_sales_uom),
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
                "is_priced": bool(line.product_id.is_priced),
                "inventory_table_html": "",
                "uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "uom_name": line.product_id.uom_id.name if line.product_id.uom_id else "",
                "uom_category_id": line.product_id.uom_category_id.id if line.product_id.uom_category_id else False,
                "uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "default_uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
                "default_uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
                "only_default_sales_uom": bool(line.product_id.only_default_sales_uom),
                "default_price": self._store_default_price(store_id, line.product_id),
            }

    @api.model
    def pos_barcode_products(self, barcode=None, store_id=None):
        """
        Return products linked to the given barcode.

        The method searches both the permanent barcode model and the temporary
        barcode model, merges the related products, reads the POS fields needed
        by the client, and adds `balance` and `pos_balance` values when store
        inventory data is available.
        """
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
            "is_priced",
            "allow_sell_fraction",
            "eplus_serial",
            "uom_id",
            "uom_category_id",
            "only_default_sales_uom",
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
        """
        Create or update a temporary barcode to product mapping.

        Existing temporary mappings are replaced with the provided product ids.
        When no products are supplied, an existing mapping is cleared and a new
        one is not created.
        """
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
        """
        Return products linked to a temporary barcode entry.

        The result is a lightweight list of product names and codes used by the
        POS client when a barcode exists only in the temporary mapping table.
        """
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
            if not isinstance(row, dict):
                continue
            price = row.get("price")
            qty = row.get("qty") or 0.0
            if price is None:
                continue
            try:
                price = float(price)
                qty = float(qty or 0.0)
            except Exception:
                continue
            if qty < 0.01:
                continue
            price_qty[price] = price_qty.get(price, 0.0) + qty

        default_price = float(line.product_id.default_price or 0.0)
        default_qty = price_qty.pop(default_price, 0.0) if price_qty else 0.0

        items = [{
            "price": default_price,
            "qty": default_qty,
            "is_default": True,
            "badge_key": "default",
        }]

        for price in sorted(price_qty.keys()):
            items.append({
                "price": price,
                "qty": price_qty[price],
                "is_default": False,
                "badge_key": "price-%s" % price,
            })

        if not line.product_id.is_priced and items:
            highest_price = max(float(item.get("price") or 0.0) for item in items)
            for item in items:
                item["price"] = highest_price

        return items

    @api.model
    def _pos_fill_inventory_json_for_price_validation(self, header, vals):
        if not header or vals.get("inventory_json") or not vals.get("product_id"):
            return vals

        line_vals = {
            "header_id": header.id,
            "product_id": int(vals.get("product_id")),
            "qty_str": vals.get("qty_str") or "1",
            "sell_price": vals.get("sell_price") or 0.0,
            "uom_id": vals.get("uom_id") or False,
            "inventory_json": {},
        }
        line = self.env["ab_sales_line"].new(line_vals)
        if line.product_id.is_priced and line._sell_price_matches_price_badges():
            return vals

        line._recompute_inventory_json()
        payload = line.inventory_json or {}
        if isinstance(payload, dict):
            vals["inventory_json"] = payload
        return vals

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
            # Persist the local bill first so a later remote timeout does not
            # erase the Odoo record for the same transaction.
            self.env.cr.commit()
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
    def _pos_remote_submit_response(self, header, duplicate_token=False, message=None):
        header = header.exists()
        if not header:
            return {
                "remote_callcenter": True,
                "duplicate_token": bool(duplicate_token),
                "branch_header_id": 0,
                "remote_header_id": 0,
                "status": "",
                "eplus_serial": 0,
                "message": message or _("Remote invoice was not found."),
            }

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
        response = {
            "remote_callcenter": True,
            "duplicate_token": bool(duplicate_token),
            "branch_header_id": int(header.id or 0),
            "remote_header_id": int(header.id or 0),
            "status": header.status or "",
            "eplus_serial": int(header.eplus_serial or 0),
            "message": message or _("Remote branch invoice created."),
        }
        if duplicate_token:
            response["existing_header"] = {
                "id": int(header.id or 0),
                "eplus_serial": int(header.eplus_serial or 0),
                "status": header.status or "",
                "store": {
                    "id": int(header.store_id.id or 0) if header.store_id else 0,
                    "name": header.store_id.display_name if header.store_id else "",
                    "code": header.store_id.code if header.store_id else "",
                },
                "customer": {
                    "name": customer_name,
                    "phone": customer_phone,
                    "address": customer_address,
                    "code": header.customer_code or "",
                },
                "create_date": fields.Datetime.to_string(header.create_date) if header.create_date else "",
                "totals": {
                    "total_price": float(header.total_price or 0.0),
                    "total_net_amount": float(header.total_net_amount or 0.0),
                    "number_of_products": int(header.number_of_products or len(header.line_ids)),
                },
                "line_count": int(len(header.line_ids)),
            }
        return response

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
    def _pos_line_uom_id(self, product, uom_val=False):
        if not product:
            return False

        default_uom_id = product.uom_id.id if product.uom_id else False
        if product.only_default_sales_uom:
            return default_uom_id

        if isinstance(uom_val, (list, tuple)):
            uom_val = uom_val[0] if uom_val else False
        try:
            uom_id = int(uom_val) if uom_val else 0
        except Exception:
            uom_id = 0
        return uom_id or default_uom_id

    @api.model
    def _pos_apply_payload_promotion(self, header, payload):
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

    @api.model
    def _pos_create_prepending_header_from_payload(self, payload):
        self._require_models("ab_sales_header", "ab_sales_line", "ab_product")

        header_vals = self._filter_vals("ab_sales_header", payload.get("header") or {})
        if not header_vals.get("employee_id"):
            header_vals.pop("employee_id", None)
        line_vals = payload.get("lines") or []
        token = (header_vals.get("pos_client_token") or "").strip()
        on_existing_token = (payload.get("on_existing_token") or "").strip().lower()
        if token:
            existing = self.env["ab_sales_header"].search([("pos_client_token", "=", token)], limit=1)
            if existing:
                return existing, True, on_existing_token
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
        self.env["ab_sales_header"].new(header_vals)._validate_new_customer()
        try:
            with self.env.cr.savepoint():
                header = self.env["ab_sales_header"].create(header_vals)
        except (UserError, ValidationError):
            raise
        except Exception:
            if token:
                existing = self.env["ab_sales_header"].search([("pos_client_token", "=", token)], limit=1)
                if existing:
                    return existing, True, on_existing_token
            raise

        product_ids = []
        for line in line_vals:
            try:
                pid = int((line or {}).get("product_id") or 0)
            except Exception:
                pid = 0
            if pid:
                product_ids.append(pid)
        products = self.env["ab_product"].browse(list(set(product_ids))).exists() if product_ids else self.env[
            "ab_product"]
        product_by_id = {product.id: product for product in products}

        lines_to_create = []
        for line in line_vals:
            vals = self._filter_vals("ab_sales_line", line or {})
            if not vals.get("product_id"):
                continue
            product_id = int(vals.get("product_id"))
            vals["uom_id"] = self._pos_line_uom_id(product_by_id.get(product_id), vals.get("uom_id"))
            vals["header_id"] = header.id
            vals["qty_str"] = vals.get("qty_str") or "1"
            self._pos_fill_inventory_json_for_price_validation(header, vals)
            lines_to_create.append(vals)

        if lines_to_create:
            self.env["ab_sales_line"].create(lines_to_create)

        self._pos_apply_payload_promotion(header, payload)
        self._fill_lines_balance_from_offline(header)
        return header, False, on_existing_token

    @api.model
    def _pos_callcenter_remote_config(self, payload):
        if not self.env.user.has_group("ab_sales.group_call_center"):
            return self.env["ab_sales_branch_rpc_config"]
        header_vals = payload.get("header") or {}
        try:
            store_id = int(header_vals.get("store_id") or 0)
        except Exception:
            store_id = 0
        if not store_id:
            raise UserError(_("Store is required."))
        config = self.env["ab_sales_branch_rpc_config"].sudo().search([
            ("store_id", "=", store_id),
            ("active", "=", True),
        ], limit=1)
        if not config:
            raise UserError(_("No active branch RPC configuration was found for the selected store."))
        return config

    @api.model
    def _pos_submit_to_branch_rpc(self, payload):
        config = self._pos_callcenter_remote_config(payload)
        if not config:
            return False

        header_vals = payload.get("header") or {}
        token = (header_vals.get("pos_client_token") or "").strip()
        push_to_eplus = bool(config.push_to_eplus_on_submit)
        log = self.env["ab_sales_callcenter_rpc_log"].sudo().create({
            "rpc_config_id": config.id,
            "store_id": config.store_id.id,
            "payload_token": token,
            "push_to_eplus_requested": push_to_eplus,
            "state": "started",
            "submitted_by_id": self.env.uid,
            "submitted_at": fields.Datetime.now(),
        })
        self.env.cr.commit()

        try:
            response = config._execute_kw(
                "ab_sales_pos_api",
                "pos_submit_from_callcenter",
                [payload, push_to_eplus],
            )
            if not isinstance(response, dict):
                raise UserError(_("Branch RPC submit returned an invalid response."))
            log.write({
                "state": "success",
                "remote_header_id": int(
                    response.get("branch_header_id") or response.get("remote_header_id") or 0
                ),
                "remote_status": response.get("status") or "",
                "remote_eplus_serial": int(response.get("eplus_serial") or 0),
                "response_message": response.get("message") or "",
            })
            self.env.cr.commit()
            return response
        except Exception as error:
            log.write({
                "state": "error",
                "error_message": str(error),
            })
            self.env.cr.commit()
            raise

    @api.model
    def _pos_push_callcenter_header_to_eplus(self, header):
        header = header.exists()
        if not header:
            raise UserError(_("Remote branch invoice was not found before E-Plus push."))
        if header.status in ("pending", "saved"):
            return _("Remote branch invoice was already pushed to E-Plus.")
        if header.status != "prepending":
            raise UserError(_("Remote branch invoice must be prepending before E-Plus push."))
        header.with_context(pos_submit=True, from_callcenter_rpc=True).action_push_to_eplus()
        header.invalidate_recordset(["status", "eplus_serial", "push_state", "push_message"])
        return _("Remote branch invoice pushed to E-Plus.")

    @api.model
    def pos_submit_from_callcenter(self, payload=None, push_to_eplus=False, **kwargs):
        if payload is None and kwargs:
            payload = kwargs
        if not payload or not isinstance(payload, dict):
            raise UserError(_("Invalid payload."))

        header, duplicate_token, _on_existing_token = (
            self.with_context(from_callcenter_rpc=True)._pos_create_prepending_header_from_payload(payload)
        )
        push_requested = bool(push_to_eplus)
        if push_requested:
            message = self._pos_push_callcenter_header_to_eplus(header)
        else:
            message = (
                _("An invoice already exists with the same token.")
                if duplicate_token
                else _("Remote branch invoice created.")
            )
        return self._pos_remote_submit_response(header, duplicate_token=duplicate_token, message=message)

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        """
        Create and submit a sales header from a POS payload.

        The method validates the header, handles duplicate client tokens,
        creates sales lines with default UoMs when needed, applies a promotion
        when provided, fills offline balances, and returns the submit action or
        the created header metadata.
        """
        if payload is None and kwargs:
            payload = kwargs
        if not payload or not isinstance(payload, dict):
            raise UserError(_("Invalid payload."))

        remote_response = self._pos_submit_to_branch_rpc(payload)
        if remote_response:
            return remote_response

        header, duplicate_token, on_existing_token = self._pos_create_prepending_header_from_payload(payload)
        if duplicate_token:
            if on_existing_token == "warn":
                return self._pos_existing_header_payload(header)
            return self._pos_existing_header_action(header)
        return self._pos_submit_response(header.with_context(pos_submit=True), apply_submit=True)
