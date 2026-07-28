# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbSalesLead(models.Model):
    _name = "ab_sales_lead"
    _description = "Sales Lead"
    _order = "create_date desc, id desc"

    lead_type = fields.Selection(
        selection=[
            ("lost_sales", "Lost Sale"),
            ("special_order", "Special Order"),
        ],
        required=True,
        default="lost_sales",
        index=True,
    )
    state = fields.Selection(
        selection=[
            ("new", "New"),
            ("in_review", "In Review"),
            ("contacted", "Contacted"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="new",
        index=True,
    )
    source = fields.Selection(
        selection=[
            ("pos", "POS"),
            ("manual", "Manual"),
        ],
        required=True,
        default="manual",
        index=True,
    )

    product_id = fields.Many2one("ab_product", required=True, index=True, ondelete="restrict")
    product_name = fields.Char(required=True, index=True)
    product_code = fields.Char(index=True)
    store_id = fields.Many2one("ab_store", index=True, ondelete="set null")
    user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
        ondelete="restrict",
    )

    customer_id = fields.Many2one("ab_customer", index=True, ondelete="set null")
    customer_name = fields.Char(index=True)
    customer_phone = fields.Char(index=True)
    customer_address = fields.Char()

    quantity = fields.Float(required=True, default=1.0)
    default_price = fields.Float(digits=(16, 2))
    total_balance = fields.Float(string="Total Balance")
    pos_balance = fields.Float(string="POS Store Balance")
    pos_search_query = fields.Char()
    pos_client_token = fields.Char(index=True)

    lost_reason = fields.Selection(
        selection=[
            ("not_available", "Product not available"),
            ("insufficient_quantity", "Insufficient quantity"),
            ("price_too_high", "Price too high"),
            ("customer_found_alternative", "Customer found alternative"),
            ("customer_refused_wait", "Customer refused to wait"),
            ("missing_product_info", "Missing product information"),
            ("other", "Other"),
        ],
    )
    needed_date = fields.Date()
    contact_preference = fields.Selection(
        selection=[
            ("phone", "Phone"),
            ("whatsapp", "WhatsApp"),
            ("in_store", "In Store"),
        ],
        default="phone",
    )
    notes = fields.Text()
    company_action_note = fields.Text()

    @api.depends("lead_type", "product_name", "customer_phone", "customer_name")
    def _compute_display_name(self):
        labels = dict(self._fields["lead_type"].selection)
        for rec in self:
            parts = [labels.get(rec.lead_type, rec.lead_type or _("Lead"))]
            if rec.product_name:
                parts.append(rec.product_name)
            contact = rec.customer_phone or rec.customer_name
            if contact:
                parts.append(contact)
            rec.display_name = " - ".join(parts)

    @api.constrains("lead_type", "customer_phone", "lost_reason", "notes", "quantity")
    def _check_required_details(self):
        for rec in self:
            if rec.quantity <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))
            if rec.lead_type == "special_order" and not (rec.customer_phone or "").strip():
                raise ValidationError(_("Customer phone is required for special orders."))
            if rec.lead_type == "lost_sales" and not rec.lost_reason and not (rec.notes or "").strip():
                raise ValidationError(_("Lost sales require a reason or note."))

    @api.model_create_multi
    def create(self, vals_list):
        Product = self.env["ab_product"]
        for vals in vals_list:
            product = Product.browse(vals.get("product_id") or []).exists()
            if product:
                if not vals.get("product_name"):
                    vals["product_name"] = product.name or product.product_card_name or ""
                if not vals.get("product_code"):
                    vals["product_code"] = product.code or ""
                if not vals.get("default_price"):
                    vals["default_price"] = product.default_price or 0.0
            vals.setdefault("source", "manual")
            vals.setdefault("user_id", self.env.uid)
        return super().create(vals_list)

    def action_set_in_review(self):
        self.write({"state": "in_review"})

    def action_set_contacted(self):
        self.write({"state": "contacted"})

    def action_set_closed(self):
        self.write({"state": "closed"})

    def action_set_cancelled(self):
        self.write({"state": "cancelled"})

    @api.model
    def pos_create_lead(self, payload=None):
        payload = payload or {}
        product_id = int(payload.get("product_id") or 0)
        product = self.env["ab_product"].browse(product_id).exists()
        if not product:
            raise ValidationError(_("Select a valid product."))

        def _int_or_false(value):
            try:
                parsed = int(value or 0)
            except Exception:
                parsed = 0
            return parsed or False

        def _float_or_zero(value):
            try:
                return float(value or 0.0)
            except Exception:
                return 0.0

        lead_type = payload.get("lead_type") or "lost_sales"
        if lead_type not in ("lost_sales", "special_order"):
            raise ValidationError(_("Select a valid lead type."))

        quantity = _float_or_zero(payload.get("quantity"))

        vals = {
            "lead_type": lead_type,
            "source": "pos",
            "product_id": product.id,
            "product_name": (payload.get("product_name") or product.name or product.product_card_name or "").strip(),
            "product_code": (payload.get("product_code") or product.code or "").strip(),
            "store_id": _int_or_false(payload.get("store_id")),
            "customer_id": _int_or_false(payload.get("customer_id")),
            "customer_name": (payload.get("customer_name") or "").strip(),
            "customer_phone": (payload.get("customer_phone") or "").strip(),
            "customer_address": (payload.get("customer_address") or "").strip(),
            "quantity": quantity,
            "default_price": _float_or_zero(payload.get("default_price") or product.default_price),
            "total_balance": _float_or_zero(payload.get("total_balance")),
            "pos_balance": _float_or_zero(payload.get("pos_balance")),
            "pos_search_query": (payload.get("pos_search_query") or "").strip(),
            "pos_client_token": (payload.get("pos_client_token") or "").strip(),
            "lost_reason": payload.get("lost_reason") or False,
            "needed_date": payload.get("needed_date") or False,
            "contact_preference": payload.get("contact_preference") or "phone",
            "notes": (payload.get("notes") or "").strip(),
        }
        record = self.create(vals)
        return {
            "id": record.id,
            "display_name": record.display_name,
            "message": _("Sales lead saved."),
        }

    @api.model
    def pos_item_report(self, product_id=None):
        try:
            product_id = int(product_id or 0)
        except Exception:
            product_id = 0
        product = self.env["ab_product"].browse(product_id).exists()
        if not product:
            raise ValidationError(_("Select a valid product."))

        try:
            product_serial = int(product.eplus_serial or 0)
        except Exception:
            product_serial = 0
        if not product_serial:
            return {
                "rows": [],
                "total_balance": 0.0,
                "total_last_30_days_sales": 0.0,
                "message": _("This product has no ePlus serial."),
            }

        today = fields.Date.context_today(self)
        date_from = today - timedelta(days=29)

        rows_by_store = {}
        Inventory = self.env["ab_sales_inventory"]
        inventory_lines = Inventory.search([
            ("product_eplus_serial", "=", product_serial),
            ("store_id", "!=", False),
        ])
        for line in inventory_lines:
            store = line.store_id
            if not store:
                continue
            bucket = rows_by_store.setdefault(store.id, {
                "store_id": store.id,
                "store_name": store.display_name,
                "store_code": store.code or "",
                "balance": 0.0,
                "last_30_days_sales": 0.0,
            })
            bucket["balance"] += float(line.balance or 0.0)

        SalesPerDay = self.env["ab_sales_per_day"]
        sales_lines = SalesPerDay.search([
            ("product_eplus_serial", "=", product_serial),
            ("sale_date", ">=", date_from),
            ("sale_date", "<=", today),
        ])
        for line in sales_lines:
            store = line.store_id
            if not store:
                continue
            bucket = rows_by_store.setdefault(store.id, {
                "store_id": store.id,
                "store_name": store.display_name,
                "store_code": store.code or "",
                "balance": 0.0,
                "last_30_days_sales": 0.0,
            })
            bucket["last_30_days_sales"] += float(line.sales_qty or 0.0)

        rows = sorted(
            rows_by_store.values(),
            key=lambda row: (
                -float(row["balance"] or 0.0),
                -float(row["last_30_days_sales"] or 0.0),
                row["store_name"] or row["store_code"] or "",
            ),
        )
        return {
            "rows": rows,
            "total_balance": sum(float(row["balance"] or 0.0) for row in rows),
            "total_last_30_days_sales": sum(float(row["last_30_days_sales"] or 0.0) for row in rows),
            "date_from": fields.Date.to_string(date_from),
            "date_to": fields.Date.to_string(today),
            "message": False,
        }
