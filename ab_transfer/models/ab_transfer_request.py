# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.sql import column_exists, table_exists


class AbTransferRequest(models.Model):
    _name = "ab_transfer_request"
    _description = "Transfer Request"
    _order = "id desc"
    _rec_name = "display_name"

    display_name = fields.Char(
        string="Name",
        compute="_compute_display_name",
        store=True,
    )

    from_store_id = fields.Many2one(
        "ab_store",
        string="From Store",
        domain=lambda self: self._get_allowed_source_store_domain(),
        default=lambda self: self._default_from_store_id(),
        required=True,
    )

    to_store_id = fields.Many2one(
        "ab_store",
        string="Destination Branch",
        required=True,
    )

    user_id = fields.Many2one(
        "ab_costcenter",
        string="User",
        default=lambda self: self._default_user_id(),
        readonly=True,
    )

    notes = fields.Char(
        string="Notes",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    execution_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("done", "Done"),
        ],
        string="Execution State",
        default="pending",
        required=True,
        copy=False,
    )

    line_ids = fields.One2many(
        "ab_transfer_request_line",
        "request_id",
        string="Lines",
    )

    items_count = fields.Integer(
        string="Items Count",
        compute="_compute_totals",
        store=True,
    )

    total_requested_qty = fields.Float(
        string="Total Requested Quantity",
        digits=(16, 3),
        compute="_compute_totals",
        store=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    def _auto_init(self):
        result = super()._auto_init()
        if column_exists(self.env.cr, self._table, "execution_state"):
            self.env.cr.execute(
                """
                UPDATE ab_transfer_request
                SET execution_state = 'pending'
                WHERE execution_state IS NULL
                """
            )

            default_store_id = self._default_from_store_id()
            if default_store_id and table_exists(self.env.cr, "ab_transfer_request_line"):
                self.env.cr.execute(
                    """
                    UPDATE ab_transfer_request request
                    SET from_store_id = request.to_store_id
                    WHERE request.execution_state = 'pending'
                      AND request.state = 'confirmed'
                      AND request.from_store_id = %s
                      AND request.to_store_id IS NOT NULL
                      AND request.to_store_id != request.from_store_id
                      AND EXISTS (
                          SELECT 1
                          FROM ab_transfer_request_line line
                          WHERE line.request_id = request.id
                      )
                    """,
                    [default_store_id],
                )
        return result

    @api.model
    def _default_user_id(self):
        if "ab_hr_employee" not in self.env.registry:
            return False
        employee = self.env["ab_hr_employee"].sudo().search(
            [
                ("user_id", "=", self.env.user.id),
                ("costcenter_id", "!=", False),
            ],
            limit=1,
        )
        return employee.costcenter_id.id if employee and employee.costcenter_id else False

    @api.model
    def _get_allowed_source_store_ids(self):
        return self.env["ab_transfer_header"]._get_allowed_source_store_ids()

    @api.model
    def _get_allowed_source_store_domain(self):
        return self.env["ab_transfer_header"]._get_allowed_source_store_domain()

    @api.model
    def _get_default_source_store(self):
        return self.env["ab_transfer_header"]._get_default_source_store()

    @api.model
    def _default_from_store_id(self):
        return self.env["ab_transfer_header"]._default_from_store_id()

    @api.depends("from_store_id", "to_store_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = _("Transfer Request %s") % rec.id if rec.id else _("New Transfer Request")

    @api.depends("line_ids", "line_ids.requested_qty")
    def _compute_totals(self):
        for rec in self:
            rec.items_count = len(rec.line_ids)
            rec.total_requested_qty = sum(rec.line_ids.mapped("requested_qty"))

    def action_confirm(self):
        for rec in self:
            if rec.state == "cancelled":
                raise UserError(_("Cancelled transfer requests must be reset to draft before confirmation."))
            if not rec.line_ids:
                raise UserError(_("You cannot confirm a transfer request without lines."))
        self.write({"state": "confirmed"})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_draft(self):
        self.write({"state": "draft"})
        return True


class AbTransferRequestLine(models.Model):
    _name = "ab_transfer_request_line"
    _description = "Transfer Request Line"
    _order = "id desc"

    request_id = fields.Many2one(
        "ab_transfer_request",
        string="Transfer Request",
        required=True,
        ondelete="cascade",
    )

    to_store_id = fields.Many2one(
        "ab_store",
        string="Destination Branch",
        related="request_id.to_store_id",
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        required=True,
        domain=[("active", "=", True)],
    )

    requested_qty = fields.Float(
        string="Requested Quantity",
        required=True,
        digits=(16, 3),
        default=1.0,
    )

    uom_category_id = fields.Many2one(
        "ab_product_uom_category",
        string="UoM Category",
        related="product_id.uom_category_id",
        readonly=True,
    )

    uom_id = fields.Many2one(
        "ab_product_uom",
        string="UOM",
    )

    notes = fields.Char(
        string="Notes",
    )

    user_id = fields.Many2one(
        "ab_costcenter",
        string="User",
        related="request_id.user_id",
        store=True,
        readonly=True,
    )

    state = fields.Selection(
        related="request_id.state",
        store=True,
        string="Status",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="request_id.company_id",
        store=True,
        readonly=True,
    )

    @api.constrains("requested_qty")
    def _check_requested_qty(self):
        for rec in self:
            if rec.requested_qty <= 0:
                raise ValidationError(_("Requested quantity must be greater than zero."))

    @api.model_create_multi
    def create(self, vals_list):
        product_ids = [vals.get("product_id") for vals in vals_list if vals.get("product_id") and not vals.get("uom_id")]
        products = self.env["ab_product"].browse(product_ids).exists() if product_ids else self.env["ab_product"]
        product_by_id = {product.id: product for product in products}
        for vals in vals_list:
            product = product_by_id.get(vals.get("product_id"))
            if product and product.uom_id and not vals.get("uom_id"):
                vals["uom_id"] = product.uom_id.id
        return super().create(vals_list)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id and rec.product_id.uom_id and not rec.uom_id:
                rec.uom_id = rec.product_id.uom_id

    def name_get(self):
        result = []
        for rec in self:
            name = "%s - %s" % (
                rec.product_id.display_name if rec.product_id else _("Product"),
                rec.requested_qty or 0,
            )
            result.append((rec.id, name))
        return result


class AbTransferRequestPosApi(models.TransientModel):
    _name = "ab_transfer_request_pos_api"
    _description = "Transfer Request POS API"

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
    def _default_user(self):
        user_id = self.env["ab_transfer_request"]._default_user_id()
        return self.env["ab_costcenter"].browse(user_id).exists() if user_id else self.env["ab_costcenter"].browse()

    @api.model
    def pos_defaults(self):
        self._require_models("ab_transfer_request")
        Request = self.env["ab_transfer_request"]
        store = Request._get_default_source_store()
        user = self._default_user()
        return {
            "from_store": {
                "id": store.id if store else False,
                "name": store.display_name if store else "",
                "code": store.code if store else "",
            },
            "allowed_from_store_ids": Request._get_allowed_source_store_ids(),
            "user": {
                "id": user.id if user else False,
                "name": user.display_name if user else "",
                "code": user.code if user and "code" in user._fields else "",
            },
        }

    @api.model
    def _sales_style_product_search(self, search_term, limit):
        if "ab_sales_ui_api" not in self.env.registry:
            return []
        api = self.env["ab_sales_ui_api"]
        try:
            rows = api.search_products(
                query=search_term,
                limit=max(limit * 4, limit),
                has_balance=False,
                has_pos_balance=False,
                store_id=None,
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
    def _normalize_product_search_row(self, row, product):
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
            "default_price": row.get("default_price", 0.0) or 0.0,
            "uom_id": uom_id,
            "uom_name": uom_name,
            "uom_category_id": product.uom_category_id.id if product.uom_category_id else False,
        }

    @api.model
    def pos_product_search(self, search=None, limit=24):
        self._require_models("ab_product")
        search_term = (search or "").strip()
        try:
            limit = int(limit or 24)
        except Exception:
            limit = 24
        limit = max(1, min(limit, 80))

        rows = self._sales_style_product_search(search_term, limit)
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
        result = []
        for row in rows:
            product_id = int((row or {}).get("id") or 0)
            product = product_by_id.get(product_id)
            if not product:
                continue
            result.append(self._normalize_product_search_row(row, product))
            if len(result) >= limit:
                break
        return result

    @api.model
    def pos_submit(self, payload=None, **kwargs):
        self._require_models("ab_transfer_request", "ab_transfer_request_line")
        if payload is None and kwargs:
            payload = kwargs
        if not payload or not isinstance(payload, dict):
            raise UserError(_("Invalid payload."))

        raw_header_vals = payload.get("header") or {}
        header_vals = self._filter_vals("ab_transfer_request", raw_header_vals)
        line_vals = payload.get("lines") or []
        Request = self.env["ab_transfer_request"]
        default_store = Request._get_default_source_store()
        default_store_id = default_store.id if default_store else False

        if not header_vals.get("from_store_id"):
            header_vals["from_store_id"] = default_store.id if default_store else False
        if not header_vals.get("from_store_id"):
            raise UserError(_("Requesting store is required."))
        if not header_vals.get("to_store_id"):
            raise UserError(_("Destination branch is required."))
        if (
            default_store_id
            and int(header_vals.get("from_store_id") or 0) == default_store_id
            and int(header_vals.get("to_store_id") or 0) != default_store_id
        ):
            header_vals["from_store_id"] = header_vals["to_store_id"]
        if not header_vals.get("user_id"):
            default_user = self._default_user()
            header_vals["user_id"] = default_user.id if default_user else False
        if not line_vals:
            raise UserError(_("At least one line is required."))

        lines_to_create = []
        for line in line_vals:
            vals = self._filter_vals("ab_transfer_request_line", line or {})
            if not vals.get("product_id"):
                continue
            lines_to_create.append(vals)

        if not lines_to_create:
            raise UserError(_("At least one valid line is required."))

        header_vals["state"] = "draft"
        header_vals["execution_state"] = "pending"
        request = self.env["ab_transfer_request"].create(header_vals)
        for vals in lines_to_create:
            vals["request_id"] = request.id
        self.env["ab_transfer_request_line"].create(lines_to_create)
        request.action_confirm()

        return {
            "id": request.id,
            "display_name": request.display_name,
            "state": request.state,
        }
