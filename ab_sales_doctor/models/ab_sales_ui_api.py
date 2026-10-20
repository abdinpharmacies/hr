import math

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbSalesUiApi(models.TransientModel):
    _inherit = "ab_sales_ui_api"

    @api.model
    def _doctor_product_search_domain(self, doctor_id, query="", item_type="all"):
        Product = self.env["ab_product"]
        item_type = self._normalize_item_type_filter(item_type)
        domain = [
            ("doctor_id", "=", doctor_id),
            ("active", "=", True),
            ("product_id.active", "=", True),
        ]
        if item_type != "all":
            domain.append(("product_id.is_medicine", "=", item_type == "medicine"))
        raw_query = (query or "").strip()
        if not raw_query:
            return domain

        query_like = raw_query.replace("*", "%").replace(" ", "%") + "%"
        clauses = [
            ("product_id.code", "=ilike", raw_query),
            ("product_id.name", "=ilike", query_like),
        ]
        if "product_card_name" in Product._fields:
            clauses.append(("product_id.product_card_name", "=ilike", query_like))
        return (["|"] * (len(clauses) - 1)) + clauses + domain

    @api.model
    def _normalize_bill_wizard_doctor_ids(self, doctor_ids=None):
        if isinstance(doctor_ids, (int, str)):
            doctor_ids = [doctor_ids]
        elif not isinstance(doctor_ids, (list, tuple, set)):
            doctor_ids = []

        normalized = []
        seen = set()
        for doctor_id in doctor_ids:
            if isinstance(doctor_id, dict):
                doctor_id = doctor_id.get("id")
            try:
                doctor_id = int(doctor_id or 0)
            except Exception:
                doctor_id = 0
            if doctor_id > 0 and doctor_id not in seen:
                seen.add(doctor_id)
                normalized.append(doctor_id)
        if not normalized:
            return []
        return self.env["ab_doctor"].with_context(active_test=False).browse(normalized).exists().ids

    @api.model
    def _attach_uom_factors_to_doctor_rows(self, rows):
        rows = rows or []
        uom_ids = []
        for row in rows:
            uom_val = row.get("uom_id")
            if isinstance(uom_val, (list, tuple)):
                uom_val = uom_val[0] if uom_val else 0
            try:
                uom_id = int(uom_val or 0)
            except Exception:
                uom_id = 0
            if uom_id:
                uom_ids.append(uom_id)
        if not uom_ids:
            return rows

        uoms = self.env["ab_product_uom"].browse(list(set(uom_ids))).read(["factor"])
        factor_by_id = {int(uom["id"]): float(uom.get("factor") or 1.0) for uom in uoms}
        for row in rows:
            uom_val = row.get("uom_id")
            if isinstance(uom_val, (list, tuple)):
                uom_val = uom_val[0] if uom_val else 0
            try:
                uom_id = int(uom_val or 0)
            except Exception:
                uom_id = 0
            factor = factor_by_id.get(uom_id, 1.0)
            row["uom_factor"] = factor
            row["default_uom_factor"] = factor
        return rows

    @api.model
    def doctor_prescription_products(self, doctor_id=None, query="", limit=24, store_id=None, header_id=None,
                                     item_type="all", min_price=None, max_price=None,
                                     has_balance=False, has_pos_balance=False):
        price_bounds = self._product_price_bounds(min_price, max_price)
        self._require_models("ab_product_doctor_prescription", "ab_product", "ab_product_uom")
        item_type = self._normalize_item_type_filter(item_type)
        try:
            doctor_id = int(doctor_id or 0)
        except Exception:
            doctor_id = 0
        if not doctor_id:
            return []

        doctor = self.env["ab_doctor"].browse(doctor_id).exists()
        if not doctor:
            raise UserError(_("Invalid doctor."))

        try:
            limit = max(1, min(120, int(limit or 24)))
        except Exception:
            limit = 24
        store_id = self._resolve_store_id(header_id=header_id, store_id=store_id)

        fields_list = self._safe_fields(
            "ab_product",
            [
                "name",
                "product_card_name",
                "code",
                "is_service",
                "default_price",
                "allow_sell_fraction",
                "eplus_serial",
                "uom_id",
                "uom_category_id",
            ],
        )
        domain = fields.Domain(self._doctor_product_search_domain(doctor.id, query=query, item_type=item_type))
        if price_bounds is not None:
            domain &= fields.Domain("product_id", "any", self._product_price_domain(price_bounds))
        prescriptions = self.env["ab_product_doctor_prescription"].search(
            domain,
            # Price searches apply balance eligibility before limiting results.
            limit=limit if price_bounds is None else None,
            order="write_date desc, id desc",
        )
        product_ids = []
        seen = set()
        for product in prescriptions.mapped("product_id"):
            if product.id in seen:
                continue
            seen.add(product.id)
            product_ids.append(product.id)
        if not product_ids:
            return []

        products = self.env["ab_product"].browse(product_ids).read(fields_list)
        self._attach_uom_factors_to_doctor_rows(products)
        by_id = {int(row["id"]): row for row in products if row.get("id")}

        serials = []
        for pid in product_ids:
            row = by_id.get(pid)
            try:
                serials.append(int(row.get("eplus_serial") or 0) if row else 0)
            except Exception:
                serials.append(0)
        total_balance_by_serial, pos_balance_by_serial = self._inventory_total_and_pos_balances_by_serial(
            serials,
            store_id=store_id,
        )

        rows = []
        for pid in product_ids:
            row = by_id.get(pid)
            if not row or not self._product_price_matches(row, price_bounds):
                continue
            try:
                serial = int(row.get("eplus_serial") or 0)
            except Exception:
                serial = 0
            total_balance = float(total_balance_by_serial.get(serial, 0.0) or 0.0) if serial else 0.0
            pos_balance = float(pos_balance_by_serial.get(serial, 0.0) or 0.0) if serial else 0.0
            row["balance"] = total_balance
            row["has_balance"] = bool(total_balance > 0)
            row["pos_balance"] = pos_balance
            row["has_pos_balance"] = bool(pos_balance > 0)
            if price_bounds is not None:
                service_match = bool(query and row.get("is_service"))
                if has_balance and not row["has_balance"] and not service_match:
                    continue
                if has_pos_balance and not row["has_pos_balance"] and not service_match:
                    continue
            row["is_doctor_prescription_product"] = True
            row["is_pinned"] = True
            row["rank_source"] = "doctor_prescription"
            row["customer_order_count_3m"] = 0
            row["is_top_customer"] = False
            row["branch_order_count_30d"] = 0
            row["is_top_branch"] = False
            rows.append(row)
            if len(rows) >= limit:
                break
        return rows[:limit]

