# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbPosApi(models.TransientModel):
    _name = "ab_pos.api"
    _description = "Ab POS API"

    create_date = fields.Datetime(readonly=True)

    @api.model
    def _require_models(self, *model_names):
        missing = [m for m in model_names if m not in self.env.registry]
        if missing:
            raise UserError(_("Missing required models: %s") % ", ".join(missing))

    @api.model
    def _safe_fields(self, model_name, desired_fields):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        result = [field for field in (desired_fields or []) if field in model_fields]
        if "id" not in result:
            result.insert(0, "id")
        return result

    @api.model
    def _safe_domain(self, model_name, domain):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        safe_domain = []
        for token in domain or []:
            if token in ("|", "&", "!"):
                safe_domain.append(token)
                continue
            if not isinstance(token, (list, tuple)) or len(token) < 3:
                continue
            field_name = token[0]
            if field_name in model_fields:
                safe_domain.append(tuple(token))
        return safe_domain

    @api.model
    def _filter_vals(self, model_name, vals):
        self._require_models(model_name)
        model_fields = self.env[model_name]._fields
        return {key: value for key, value in (vals or {}).items() if key in model_fields}

    @api.model
    def get_stores(self, limit=200):
        self._require_models("ab_store")
        Store = self.env["ab_store"]
        domain = self._safe_domain("ab_store", [("active", "=", True), ("allow_sale", "=", True)])
        fields_list = self._safe_fields("ab_store", ["name", "code"])
        return Store.search_read(domain, fields_list, limit=limit, order="name")

    @api.model
    def search_products(self, query="", limit=50):
        self._require_models("ab_product")
        Product = self.env["ab_product"]
        domain = [("active", "=", True), ("allow_sale", "=", True)]
        query = (query or "").strip()
        if query:
            domain = ["|", ("name", "ilike", query), ("code", "ilike", query)] + domain
        domain = self._safe_domain("ab_product", domain)
        fields_list = self._safe_fields(
            "ab_product",
            ["name", "product_card_name", "code", "default_price", "allow_sell_fraction"],
        )
        return Product.search_read(domain, fields_list, limit=limit, order="name")

    @api.model
    def search_customers(self, query="", limit=50):
        self._require_models("ab_customer")
        Customer = self.env["ab_customer"]
        domain = [("active", "=", True)]
        query = (query or "").strip()
        if query:
            domain = [
                "|",
                "|",
                ("name", "ilike", query),
                ("code", "ilike", query),
                ("mobile_phone", "ilike", query),
            ] + domain
        domain = self._safe_domain("ab_customer", domain)
        fields_list = self._safe_fields("ab_customer", ["name", "code", "mobile_phone", "work_phone", "address"])
        return Customer.search_read(domain, fields_list, limit=limit, order="name")

    @api.model
    def create_sale(self, payload):
        self._require_models("ab_sales_header", "ab_sales_line")
        payload = payload or {}
        store_id = payload.get("store_id")
        if not store_id:
            raise UserError(_("Store is required."))

        header_vals = {
            "store_id": int(store_id),
            "customer_id": int(payload["customer_id"]) if payload.get("customer_id") else False,
            "description": payload.get("description") or _("Created from Ab POS"),
        }
        header_vals = self._filter_vals("ab_sales_header", header_vals)
        header = self.env["ab_sales_header"].create(header_vals)

        lines = payload.get("lines") or []
        SalesLine = self.env["ab_sales_line"]
        for line in lines:
            line = line or {}
            product_id = line.get("product_id")
            if not product_id:
                continue

            qty_str = line.get("qty_str")
            if not qty_str:
                qty_str = str(line.get("qty") if line.get("qty") is not None else 1)

            line_vals = {
                "header_id": header.id,
                "product_id": int(product_id),
                "qty_str": qty_str,
            }
            if "sell_price" in line:
                line_vals["sell_price"] = line.get("sell_price")
            line_vals = self._filter_vals("ab_sales_line", line_vals)
            SalesLine.create(line_vals)

        return {"header_id": header.id}
