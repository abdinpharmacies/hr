# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AbTransferPosApi(models.TransientModel):
    _name = "ab_transfer_pos_api"
    _description = "Transfer POS API"

    _transfer_types = {"1", "2", "3", "4"}

    @api.model
    def _require_models(self, *model_names):
        missing = [model_name for model_name in model_names if model_name not in self.env.registry]
        if missing:
            raise UserError(_("Missing required models: %s") % ", ".join(missing))

    @api.model
    def _filter_vals(self, model_name, vals):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        return {key: value for key, value in (vals or {}).items() if key in model_fields}

    @api.model
    def _format_transfer_notes(self, transfer_type, notes):
        transfer_type = str(transfer_type or "").strip()
        if transfer_type not in self._transfer_types:
            raise UserError(_("Transfer type is required."))
        return "%s %s" % (transfer_type, str(notes or ""))

    @api.model
    def _default_from_store(self):
        Header = self.env["ab_transfer_header"]
        store = Header._get_default_source_store()
        return store if store and store.exists() else self.env["ab_store"].browse()

    @api.model
    def _default_user(self):
        Header = self.env["ab_transfer_header"]
        user_id = Header._default_user_id()
        return self.env["ab_costcenter"].browse(user_id).exists() if user_id else self.env["ab_costcenter"].browse()

    @api.model
    def pos_defaults(self):
        self._require_models("ab_transfer_header")
        Header = self.env["ab_transfer_header"]
        store = self._default_from_store()
        user = self._default_user()
        return {
            "from_store": {
                "id": store.id if store else False,
                "name": store.display_name if store else "",
                "code": store.code if store else "",
            },
            "allowed_from_store_ids": Header._get_allowed_source_store_ids(),
            "user": {
                "id": user.id if user else False,
                "name": user.display_name if user else "",
                "code": user.code if user and "code" in user._fields else "",
            },
        }

    @api.model
    def _inventory_balance_by_product(self, from_store, products):
        if not from_store or not products:
            return {}

        product_by_serial = {}
        for product in products:
            try:
                serial = int(product.eplus_serial or 0)
            except Exception:
                serial = 0
            if serial:
                product_by_serial[serial] = product.id
        if not product_by_serial:
            return {}

        header = self.env["ab_transfer_header"].new({"from_store_id": from_store.id})
        balances = {product.id: 0.0 for product in products}
        placeholders = ", ".join(["?"] * len(product_by_serial))
        params = (header._get_ref_id(from_store, "From Store"), *product_by_serial.keys())
        query = f"""
            SELECT
                ics.itm_id,
                SUM(
                    CASE
                        WHEN ISNULL(ic.itm_unit1_unit3, 0) = 0 THEN 0
                        ELSE ISNULL(ics.itm_qty, 0) / ic.itm_unit1_unit3
                    END
                ) AS qty
            FROM Item_Class_Store ics
            INNER JOIN item_catalog ic ON ic.itm_id = ics.itm_id
            WHERE ics.sto_id = ?
              AND ics.itm_id IN ({placeholders})
              AND ISNULL(ics.itm_qty, 0) > 0
            GROUP BY ics.itm_id
        """
        try:
            with header._get_sql_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    for row in cursor.fetchall() or []:
                        product_id = product_by_serial.get(int(row[0] or 0))
                        if product_id:
                            balances[product_id] = float(row[1] or 0.0)
        except Exception:
            return balances
        return balances

    @api.model
    def _sales_style_product_search(self, search_term, from_store_id, limit):
        if "ab_sales_ui_api" not in self.env.registry:
            return []

        api = self.env["ab_sales_ui_api"]
        try:
            rows = api.search_products(
                query=search_term,
                limit=max(limit * 4, limit),
                has_balance=False,
                has_pos_balance=False,
                store_id=from_store_id or None,
            )
        except Exception:
            return []
        return rows if isinstance(rows, list) else []

    @api.model
    def _fallback_product_search(self, search_term, limit):
        domain = [("active", "=", True)]
        if search_term:
            domain = [
                "&",
                ("active", "=", True),
                "|",
                ("name", "ilike", search_term),
                ("code", "ilike", search_term),
            ]
        fields_list = [
            field_name
            for field_name in (
                "name",
                "product_card_name",
                "code",
                "default_price",
                "uom_id",
                "uom_category_id",
            )
            if field_name in self.env["ab_product"]._fields
        ]
        return self.env["ab_product"].search_read(domain, fields_list, limit=limit * 2, order="name")

    @api.model
    def _normalize_product_search_row(self, row, product, balance):
        uom_id = False
        uom_name = ""
        raw_uom = row.get("uom_id")
        if isinstance(raw_uom, (list, tuple)):
            uom_id = raw_uom[0] if raw_uom else False
            uom_name = raw_uom[1] if len(raw_uom) > 1 else ""
        elif raw_uom:
            uom_id = raw_uom

        if not uom_id and product.uom_id:
            uom_id = product.uom_id.id
            uom_name = product.uom_id.name or ""
        elif uom_id and not uom_name:
            uom = self.env["ab_product_uom"].browse(int(uom_id)).exists()
            uom_name = uom.name if uom else ""

        product_name = (
            row.get("name")
            or row.get("product_card_name")
            or product.display_name
            or product.name
            or ""
        )
        return {
            "id": product.id,
            "name": product_name,
            "product_card_name": row.get("product_card_name") or product_name,
            "code": row.get("code") or product.code or "",
            "balance": balance,
            "pos_balance": row.get("pos_balance", balance),
            "default_price": row.get("default_price", 0.0) or 0.0,
            "uom_id": uom_id,
            "uom_name": uom_name,
            "uom_category_id": product.uom_category_id.id if product.uom_category_id else False,
            "uom_factor": product.uom_id.factor if product.uom_id else 1.0,
            "is_pinned": bool(row.get("is_pinned")),
            "rank_source": row.get("rank_source") or "",
        }

    @api.model
    def pos_product_search(self, search=None, from_store_id=None, limit=24):
        self._require_models("ab_transfer_header", "ab_product")
        search_term = (search or "").strip()
        try:
            limit = int(limit or 24)
        except Exception:
            limit = 24
        limit = max(1, min(limit, 80))

        try:
            parsed_from_store_id = int(from_store_id or 0)
        except Exception:
            parsed_from_store_id = 0
        if parsed_from_store_id:
            from_store = self.env["ab_store"].browse(parsed_from_store_id).exists()
        else:
            from_store = self._default_from_store()

        rows = self._sales_style_product_search(search_term, from_store.id if from_store else False, limit)
        if not rows:
            rows = self._fallback_product_search(search_term, limit)

        product_ids = []
        seen_ids = set()
        for row in rows:
            product_id = int((row or {}).get("id") or 0)
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            product_ids.append(product_id)
            if len(product_ids) >= limit * 2:
                break

        products = self.env["ab_product"].browse(product_ids).exists()
        product_by_id = {product.id: product for product in products}
        balances = self._inventory_balance_by_product(from_store, products)
        result = []
        for row in rows:
            product_id = int((row or {}).get("id") or 0)
            product = product_by_id.get(product_id)
            if not product:
                continue
            balance = float(balances.get(product.id, 0.0) or 0.0)
            result.append(self._normalize_product_search_row(row, product, balance))
            if len(result) >= limit:
                break
        return result

    @api.model
    def pos_barcode_products(self, barcode=None, from_store_id=None):
        self._require_models("ab_transfer_header", "ab_product", "ab_product_barcode", "ab_product_barcode_temp")
        barcode = (barcode or "").strip()
        if not barcode:
            return []

        barcode_rows = self.env["ab_product_barcode"].search([("name", "=", barcode)])
        temp_rows = self.env["ab_product_barcode_temp"].search([("name", "=", barcode)])
        products = (barcode_rows.mapped("product_ids") | temp_rows.mapped("product_ids")).exists()
        if not products:
            return []

        try:
            parsed_from_store_id = int(from_store_id or 0)
        except Exception:
            parsed_from_store_id = 0
        if parsed_from_store_id:
            from_store = self.env["ab_store"].browse(parsed_from_store_id).exists()
        else:
            from_store = self._default_from_store()

        fields_list = [
            field_name
            for field_name in (
                "name",
                "product_card_name",
                "code",
                "default_price",
                "uom_id",
                "uom_category_id",
            )
            if field_name in self.env["ab_product"]._fields
        ]
        rows_by_id = {row["id"]: row for row in products.read(fields_list)}
        balances = self._inventory_balance_by_product(from_store, products)
        return [
            self._normalize_product_search_row(
                rows_by_id.get(product.id, {"id": product.id}),
                product,
                float(balances.get(product.id, 0.0) or 0.0),
            )
            for product in products
        ]

    @api.model
    def pos_link_barcode_temp(self, barcode=None, product_ids=None):
        self._require_models("ab_product", "ab_product_barcode_temp")
        barcode = (barcode or "").strip()
        if not barcode:
            raise UserError(_("Barcode is required."))

        ids = []
        for product_id in product_ids or []:
            try:
                product_id = int(product_id)
            except Exception:
                product_id = 0
            if product_id:
                ids.append(product_id)
        products = self.env["ab_product"].browse(list(set(ids))).exists() if ids else self.env["ab_product"]

        Barcode = self.env["ab_product_barcode_temp"]
        record = Barcode.search([("name", "=", barcode)], limit=1)
        if record:
            if products:
                record.write({"product_ids": [(6, 0, products.ids)]})
            else:
                record.write({"product_ids": [(5, 0, 0)]})
        elif products:
            record = Barcode.create({
                "name": barcode,
                "product_ids": [(6, 0, products.ids)],
            })
        else:
            return {
                "id": False,
                "product_ids": [],
            }

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

        record = self.env["ab_product_barcode_temp"].search([("name", "=", barcode)], limit=1)
        if not record:
            return []
        return record.product_ids.read(["display_name", "name", "code"])

    @api.model
    def pos_product_details(self, from_store_id, product_id):
        self._require_models("ab_transfer_header", "ab_transfer_line", "ab_product")
        try:
            from_store_id = int(from_store_id or 0)
            product_id = int(product_id or 0)
        except Exception:
            raise UserError(_("Invalid store or product."))
        if not from_store_id or not product_id:
            raise UserError(_("Source store and product are required."))

        header = self.env["ab_transfer_header"].new({"from_store_id": from_store_id})
        line = self.env["ab_transfer_line"].new({
            "header_id": header,
            "product_id": product_id,
        })
        line._recompute_inventory_json()
        line._apply_inventory_defaults()
        line._compute_inventory_metrics()
        line._compute_inventory_table_html()

        payload = line.inventory_json or {}
        rows = payload.get("data") or []
        balance = sum(float(row.get("qty") or 0.0) for row in rows)
        selected = line._get_selected_inventory_row()

        return {
            "product_id": line.product_id.id,
            "product_name": line.product_id.display_name or line.product_id.name or "",
            "product_code": line.product_id.code or "",
            "inventory_json": payload,
            "inventory_rows": rows,
            "inventory_table_html": line.inventory_table_html or "",
            "balance": balance,
            "class_id": int(selected.get("source_id") or 0),
            "expiry_date": str(selected.get("exp_date") or "").split(" ")[0],
            "sell_price": line.sell_price or 0.0,
            "cost": line.cost or 0.0,
            "purchase_price": line.purchase_price or 0.0,
            "tax_value": line.tax_value or 0.0,
            "uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
            "uom_name": line.product_id.uom_id.name if line.product_id.uom_id else "",
            "uom_category_id": line.product_id.uom_category_id.id if line.product_id.uom_category_id else False,
            "uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
            "default_uom_id": line.product_id.uom_id.id if line.product_id.uom_id else False,
            "default_uom_factor": line.product_id.uom_id.factor if line.product_id.uom_id else 1.0,
        }

    @api.model
    def _selection_label(self, record, field_name):
        value = record[field_name]
        selection = record._fields[field_name].selection
        if callable(selection):
            selection = selection(record)
        return dict(selection or []).get(value, value or "")

    @api.model
    def _product_display_name(self, product):
        if "product_card_name" in product._fields and product.product_card_name:
            return product.product_card_name
        return product.display_name or product.name or ""

    @api.model
    def _format_transfer_request(self, request):
        products = []
        for line in request.line_ids:
            product = line.product_id
            products.append({
                "line_id": line.id,
                "product_id": product.id,
                "product_name": self._product_display_name(product),
                "product_code": product.code if "code" in product._fields else "",
                "requested_qty": line.requested_qty or 0.0,
                "uom_name": line.uom_id.name if line.uom_id else "",
            })
        return {
            "id": request.id,
            "display_name": request.display_name,
            "from_store_id": request.from_store_id.id if request.from_store_id else False,
            "from_store_name": request.from_store_id.display_name if request.from_store_id else "",
            "to_store_id": request.to_store_id.id if request.to_store_id else False,
            "to_store_name": request.to_store_id.display_name if request.to_store_id else "",
            "create_date": fields.Datetime.to_string(request.create_date) if request.create_date else "",
            "state": request.state,
            "state_label": self._selection_label(request, "state"),
            "execution_state": request.execution_state,
            "execution_state_label": self._selection_label(request, "execution_state"),
            "items_count": len(request.line_ids),
            "total_requested_qty": request.total_requested_qty or 0.0,
            "products": products,
        }

    @api.model
    def _transfer_request_active_states(self):
        field = self.env["ab_transfer_request"]._fields["state"]
        selection = field.selection
        if callable(selection):
            selection = selection(self.env["ab_transfer_request"])
        values = {value for value, _label in selection or []}
        if "confirmed" in values:
            return ["confirmed"]
        return list(values - {"draft", "cancelled", "cancel"})

    @api.model
    def pos_pending_transfer_requests(self, from_store_id=None, to_store_id=None, limit=30):
        self._require_models("ab_transfer_request", "ab_transfer_request_line")
        try:
            to_store_id = int(to_store_id or 0)
            limit = int(limit or 30)
        except Exception:
            raise UserError(_("Invalid store or limit."))
        limit = max(1, min(limit, 80))
        if not to_store_id:
            raise UserError(_("Destination store is required before loading a transfer request."))

        to_store = self.env["ab_store"].browse(to_store_id).exists()
        if not to_store:
            raise UserError(_("Destination store is invalid."))

        active_states = self._transfer_request_active_states()
        if not active_states:
            return []

        requests = self.env["ab_transfer_request"].search(
            [
                ("state", "in", active_states),
                ("execution_state", "=", "pending"),
                ("from_store_id", "=", to_store.id),
                ("line_ids", "!=", False),
            ],
            limit=limit,
            order="create_date desc, id desc",
        )
        return [self._format_transfer_request(request) for request in requests]

    @api.model
    def _row_qty_in_uom(self, row, uom_factor):
        factor = float(uom_factor or 1.0) or 1.0
        qty_small = row.get("qty_in_small_unit")
        if qty_small not in (None, False, ""):
            return float(qty_small or 0.0) / factor
        return float(row.get("qty") or 0.0)

    @api.model
    def _row_expiry_date(self, row):
        exp_date = str(row.get("exp_date") or "").split(" ")[0]
        return exp_date or False

    @api.model
    def _validate_pos_transfer_request(self, request, to_store):
        if not request:
            raise UserError(_("Transfer request is invalid."))
        if request.state not in self._transfer_request_active_states():
            raise UserError(_("Only confirmed transfer requests can be loaded."))
        if request.execution_state != "pending":
            raise UserError(_("Only pending transfer requests can be loaded."))
        if request.from_store_id != to_store:
            raise UserError(_("The request requesting store must match the transfer destination store."))
        if not request.line_ids:
            raise UserError(_("Transfer request has no lines."))

    @api.model
    def _lock_transfer_request_for_submit(self, request_id):
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM ab_transfer_request WHERE id = %s FOR UPDATE NOWAIT",
                    [request_id],
                )
                row = self.env.cr.fetchone()
        except Exception:
            raise UserError(
                _("This transfer request is already being submitted by another user. Please refresh and try again.")
            )
        return self.env["ab_transfer_request"].browse(row[0]).exists() if row else self.env["ab_transfer_request"].browse()

    @api.model
    def _prepare_pos_request_line_allocation(self, request_line, from_store):
        product = request_line.product_id
        uom = request_line.uom_id or product.uom_id
        uom_factor = uom.factor if uom and uom.factor else 1.0
        header = self.env["ab_transfer_header"].new({"from_store_id": from_store.id})
        preview_line = self.env["ab_transfer_line"].new({
            "header_id": header,
            "product_id": product.id,
            "uom_id": uom.id if uom else False,
        })
        preview_line._recompute_inventory_json()
        inventory_rows = preview_line._get_inventory_rows()

        requested_qty = float(request_line.requested_qty or 0.0)
        remaining_qty = requested_qty
        available_qty = 0.0
        transfer_lines = []

        for row in inventory_rows:
            row_qty = self._row_qty_in_uom(row, uom_factor)
            class_id = int(row.get("source_id") or 0)
            expiry_date = self._row_expiry_date(row)
            if row_qty <= 0 or not class_id or not expiry_date:
                continue
            available_qty += row_qty
            if remaining_qty <= 0:
                continue
            line_qty = min(remaining_qty, row_qty)
            if line_qty <= 0:
                continue
            transfer_lines.append({
                "request_line_id": request_line.id,
                "product_id": product.id,
                "product_name": self._product_display_name(product),
                "product_code": product.code if "code" in product._fields else "",
                "qty": line_qty,
                "requested_qty": requested_qty,
                "available_qty": available_qty,
                "class_id": class_id,
                "expiry_date": expiry_date,
                "uom_id": uom.id if uom else False,
                "uom_name": uom.name if uom else "",
                "uom_category_id": product.uom_category_id.id if product.uom_category_id else False,
                "uom_factor": float(uom_factor or 1.0),
                "default_uom_id": product.uom_id.id if product.uom_id else False,
                "default_uom_factor": product.uom_id.factor if product.uom_id else 1.0,
                "sell_price": float(row.get("price") or 0.0),
                "cost": float(row.get("cost") or 0.0),
                "purchase_price": float(row.get("pharm_price") or 0.0),
                "tax_value": float(row.get("sell_tax") or 0.0),
                "balance": 0.0,
                "inventory_rows": inventory_rows,
                "inventory_table_html": "",
            })
            remaining_qty -= line_qty

        for line in transfer_lines:
            line["available_qty"] = available_qty
            line["balance"] = available_qty

        return {
            "available_qty": available_qty,
            "load_qty": min(requested_qty, available_qty),
            "transfer_lines": transfer_lines,
        }

    @api.model
    def pos_load_transfer_request(self, request_id, from_store_id=None, to_store_id=None):
        self._require_models("ab_transfer_header", "ab_transfer_line", "ab_transfer_request", "ab_transfer_request_line")
        try:
            request_id = int(request_id or 0)
            from_store_id = int(from_store_id or 0)
            to_store_id = int(to_store_id or 0)
        except Exception:
            raise UserError(_("Invalid transfer request or store."))
        if not request_id:
            raise UserError(_("Transfer request is required."))
        if not from_store_id:
            raise UserError(_("Source store is required before loading a transfer request."))
        if not to_store_id:
            raise UserError(_("Destination store is required before loading a transfer request."))

        request = self.env["ab_transfer_request"].browse(request_id).exists()
        from_store = self.env["ab_store"].browse(from_store_id).exists()
        to_store = self.env["ab_store"].browse(to_store_id).exists()
        if not from_store:
            raise UserError(_("Source store is invalid."))
        if not to_store:
            raise UserError(_("Destination store is invalid."))
        self._validate_pos_transfer_request(request, to_store)

        lines = []
        skipped_products = []
        for request_line in request.line_ids:
            allocation = self._prepare_pos_request_line_allocation(request_line, from_store)
            if allocation["transfer_lines"]:
                lines.extend(allocation["transfer_lines"])
            else:
                skipped_products.append(self._product_display_name(request_line.product_id))

        if not lines:
            raise UserError(_("No available source stock rows were found to load into this transfer."))

        return {
            "request": self._format_transfer_request(request),
            "lines": lines,
            "skipped_products": skipped_products,
        }

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        self._require_models("ab_transfer_header", "ab_transfer_line")
        if payload is None and kwargs:
            payload = kwargs
        if not payload or not isinstance(payload, dict):
            raise UserError(_("Invalid payload."))

        raw_header_vals = payload.get("header") or {}
        header_vals = self._filter_vals("ab_transfer_header", raw_header_vals)
        line_vals = payload.get("lines") or []
        header_vals["notes"] = self._format_transfer_notes(
            raw_header_vals.get("transfer_type") or raw_header_vals.get("notes_type"),
            raw_header_vals.get("notes"),
        )

        if not header_vals.get("from_store_id"):
            default_store = self._default_from_store()
            header_vals["from_store_id"] = default_store.id if default_store else False
        default_user = self._default_user()
        header_vals["user_id"] = default_user.id if default_user else False

        if not header_vals.get("from_store_id"):
            raise UserError(_("Source store is required."))
        if not header_vals.get("to_store_id"):
            raise UserError(_("Destination store is required."))
        if not header_vals.get("user_id"):
            raise UserError(_("User is required."))
        if not line_vals:
            raise UserError(_("At least one line is required."))

        transfer_request = self.env["ab_transfer_request"].browse()
        if header_vals.get("transfer_request_id"):
            self._require_models("ab_transfer_request")
            try:
                transfer_request_id = int(header_vals.get("transfer_request_id") or 0)
            except Exception:
                transfer_request_id = 0
            transfer_request = self._lock_transfer_request_for_submit(transfer_request_id)
            to_store = self.env["ab_store"].browse(int(header_vals.get("to_store_id") or 0)).exists()
            self._validate_pos_transfer_request(transfer_request, to_store)

        lines_to_create = []
        for line in line_vals:
            vals = self._filter_vals("ab_transfer_line", line or {})
            if not vals.get("product_id"):
                continue
            lines_to_create.append(vals)

        if not lines_to_create:
            raise UserError(_("At least one valid line is required."))

        header = self.env["ab_transfer_header"].create(header_vals)
        for vals in lines_to_create:
            vals["header_id"] = header.id
        self.env["ab_transfer_line"].create(lines_to_create)

        try:
            header.action_submit()
        except (UserError, ValidationError):
            raise

        if transfer_request:
            transfer_request.write({"execution_state": "done"})

        # return {
        #     "type": "ir.actions.act_window",
        #     "name": _("Transfer"),
        #     "res_model": "ab_transfer_header",
        #     "views": [(False, "form")],
        #     "view_mode": "form",
        #     "res_id": header.id,
        # }
