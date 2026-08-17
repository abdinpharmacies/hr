# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


MOVEMENT_GROUP_SELECTION = [
    ("sale", "Sales / Return"),
    ("purchase", "Purchase / Return"),
    ("transfer", "Transfer / From / To"),
]

MOVEMENT_SELECTION = [
    ("purchase", "Purchase"),
    ("purchase_return", "Purchase Return"),
    ("sale", "Sale"),
    ("sale_return", "Sale Return"),
    ("transfer_out", "Transfer Out"),
    ("transfer_in", "Transfer In"),
]


class AbStockReportProduct(models.Model):
    _inherit = "ab_product"

    def action_open_stock_movements_report(self):
        self.ensure_one()
        if not self.eplus_serial:
            raise UserError(_("This product is not linked to an EPlus item serial."))

        wizard = self.env["ab_stock_report_wizard"].create({
            "product_id": self.id,
            "limit": 10,
        })
        action = self.env.ref("ab_stock_report.action_ab_stock_report_wizard").sudo().read()[0]
        action.update({
            "res_id": wizard.id,
            "context": dict(self.env.context, default_product_id=self.id, default_limit=10),
        })
        return action


class AbStockReportWizard(models.TransientModel):
    _name = "ab_stock_report_wizard"
    _inherit = "ab_eplus_connect"
    _description = "Stock Movement Report Wizard"

    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        required=True,
        ondelete="cascade",
    )
    product_eplus_serial = fields.Integer(
        string="EPlus Serial",
        related="product_id.eplus_serial",
        readonly=True,
    )
    limit = fields.Integer(
        string="Last Movements",
        default=10,
    )
    from_date = fields.Date(
        string="From Date",
    )
    line_ids = fields.One2many(
        "ab_stock_report_wizard_line",
        "wizard_id",
        string="Movements",
        readonly=True,
    )
    sale_line_ids = fields.One2many(
        "ab_stock_report_wizard_line",
        "wizard_id",
        string="Sales / Return",
        readonly=True,
        domain=[("movement_group", "=", "sale")],
    )
    purchase_line_ids = fields.One2many(
        "ab_stock_report_wizard_line",
        "wizard_id",
        string="Purchase / Return",
        readonly=True,
        domain=[("movement_group", "=", "purchase")],
    )
    transfer_line_ids = fields.One2many(
        "ab_stock_report_wizard_line",
        "wizard_id",
        string="Transfer / From / To",
        readonly=True,
        domain=[("movement_group", "=", "transfer")],
    )
    line_count = fields.Integer(
        string="Movement Count",
        compute="_compute_line_count",
    )
    last_refresh = fields.Datetime(
        string="Last Refresh",
        readonly=True,
    )
    cache_state = fields.Char(
        string="Cache State",
        readonly=True,
    )
    active_tab = fields.Selection(
        MOVEMENT_GROUP_SELECTION,
        string="Active Tab",
        default="sale",
        readonly=True,
    )
    cache_payload = fields.Json(
        string="Wizard Cache",
        readonly=True,
        default=dict,
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("default_product_id") and not res.get("product_id"):
            res["product_id"] = self.env.context["default_product_id"]
        if not res.get("limit"):
            res["limit"] = 10
        return res

    def action_refresh_cache(self):
        self.ensure_one()
        self._force_fetch_from_bconnect(self.active_tab)
        self._load_cached_lines(self.active_tab)
        return self._open_action()

    def action_load_lines(self):
        self.ensure_one()
        return self.action_refresh_cache()

    def action_fetch_now(self):
        self.ensure_one()
        self._force_fetch_from_bconnect(self.active_tab)
        self._load_cached_lines(self.active_tab)
        return self._open_action()

    def action_fetch_sales(self):
        self.ensure_one()
        self.active_tab = "sale"
        self._load_or_fetch_group("sale")
        return self._open_action()

    def action_fetch_purchase(self):
        self.ensure_one()
        self.active_tab = "purchase"
        self._load_or_fetch_group("purchase")
        return self._open_action()

    def action_fetch_transfers(self):
        self.ensure_one()
        self.active_tab = "transfer"
        self._load_or_fetch_group("transfer")
        return self._open_action()

    def _load_or_fetch_group(self, movement_group):
        self.ensure_one()
        payload = dict(self.cache_payload or {})
        cache_entry = payload.get(movement_group)
        limit_value = self._normalize_limit()
        from_date_value = fields.Date.to_string(self.from_date) if self.from_date else False
        if (
            not cache_entry
            or cache_entry.get("limit") != limit_value
            or cache_entry.get("from_date") != from_date_value
            or "rows" not in cache_entry
        ):
            self._force_fetch_from_bconnect(movement_group)
        else:
            self.cache_state = _("Cached %s") % dict(MOVEMENT_GROUP_SELECTION).get(
                movement_group, movement_group,
            )
        self._load_cached_lines(movement_group)

    def _normalize_limit(self):
        return self.env["ab_stock_report_cache_line"]._normalize_limit(self.limit)

    def _open_action(self):
        self.ensure_one()
        action = self.env.ref("ab_stock_report.action_ab_stock_report_wizard").sudo().read()[0]
        action.update({
            "res_id": self.id,
            "context": dict(self.env.context, default_product_id=self.product_id.id, default_limit=self.limit),
        })
        return action

    def _bootstrap_from_cache(self):
        self.ensure_one()
        self._load_cached_lines(self.active_tab)

    def _force_fetch_from_bconnect(self, movement_group=None):
        self.ensure_one()
        if not movement_group:
            movement_group = self.active_tab
        cache_model = self.env["ab_stock_report_cache_line"]
        limit_value = self._normalize_limit()
        rows = cache_model._fetch_group_rows(
            self.product_eplus_serial,
            limit_value,
            movement_group=movement_group,
            from_date=self.from_date,
        )
        payload = dict(self.cache_payload or {})
        payload[movement_group] = {
            "limit": limit_value,
            "from_date": fields.Date.to_string(self.from_date) if self.from_date else False,
            "fetched_at": fields.Datetime.to_string(fields.Datetime.now()),
            "rows": [cache_model._row_to_json(row) for row in rows],
        }
        self.cache_payload = payload
        self.cache_state = _("Fetched %s from BConnect") % dict(
            MOVEMENT_GROUP_SELECTION,
        ).get(movement_group, movement_group)

    def _load_cached_lines(self, movement_group=None):
        self.ensure_one()
        movement_group = movement_group or self.active_tab
        cache_model = self.env["ab_stock_report_cache_line"]
        cache_entry = (self.cache_payload or {}).get(movement_group) or {}
        rows = cache_model._rows_from_json(cache_entry.get("rows", []))
        last_refresh = (
            fields.Datetime.to_datetime(cache_entry["fetched_at"])
            if cache_entry.get("fetched_at") else False
        )
        state = _("Cached %s") % dict(MOVEMENT_GROUP_SELECTION).get(
            movement_group, movement_group,
        ) if cache_entry else _("No cached movements yet")

        self.line_ids.unlink()
        if rows:
            display_fields = {
                "movement_group",
                "movement_type",
                "movement_datetime",
                "sale_price",
                "qty_large",
                "store_name",
                "supplier_name",
                "customer_name",
                "employee_name",
            }
            self.env["ab_stock_report_wizard_line"].create([
                {
                    **{key: value for key, value in row.items() if key in display_fields},
                    "wizard_id": self.id,
                }
                for row in rows
            ])

        self.write({
            "last_refresh": last_refresh,
            "cache_state": state,
        })


class AbStockReportWizardLine(models.TransientModel):
    _name = "ab_stock_report_wizard_line"
    _description = "Stock Movement Report Line"
    _order = "movement_datetime desc, id desc"

    wizard_id = fields.Many2one(
        "ab_stock_report_wizard",
        required=True,
        ondelete="cascade",
    )
    movement_group = fields.Selection(
        MOVEMENT_GROUP_SELECTION,
        string="Movement Group",
        readonly=True,
    )
    movement_datetime = fields.Datetime(
        string="Movement Date",
        readonly=True,
    )
    movement_type = fields.Selection(
        MOVEMENT_SELECTION,
        string="Movement Type",
        readonly=True,
    )
    sale_price = fields.Float(
        string="Sale Price",
        readonly=True,
        digits=(16, 4),
    )
    qty_large = fields.Float(
        string="Quantity in Large Unit",
        readonly=True,
        digits=(16, 4),
    )
    store_name = fields.Char(
        string="Store",
        readonly=True,
    )
    supplier_name = fields.Char(
        string="Supplier",
        readonly=True,
    )
    customer_name = fields.Char(
        string="Customer",
        readonly=True,
    )
    employee_name = fields.Char(
        string="Employee",
        readonly=True,
    )
