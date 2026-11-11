# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


DIRECT_STATUS_SELECTION = [
    ("not_checked", "Not Checked"),
    ("pending", "Pending"),
    ("running", "Running"),
    ("success", "Success"),
    ("missing_ip", "Missing IP"),
    ("failed", "Failed"),
    ("cancelled", "Cancelled"),
]

MOVEMENT_GROUP_SELECTION = [
    ("sale", "Sales / Return"),
    ("purchase", "Purchase / Return"),
    ("transfer", "Transfer / From / To"),
    ("store_balance", "Store Balances & Sales"),
]

MOVEMENT_SELECTION = [
    ("purchase", "Purchase"),
    ("purchase_return", "Purchase Return"),
    ("sale", "Sale"),
    ("sale_return", "Sale Return"),
    ("transfer_out", "Transfer Out"),
    ("transfer_in", "Transfer In"),
]

DATE_RANGE_BATCH_SIZE = 100
FETCH_MODE_LIMITED = "limited"
FETCH_MODE_DATE_RANGE = "date-range"
STORE_BALANCE_STORE_DOMAIN = [
    ("active", "=", True),
    ("eplus_serial", "!=", False),
    ("has_working_balance", "=", True),
]


def _format_number_without_trailing_zeros(value):
    if value in (False, None, ""):
        return "0"
    try:
        number = float(value)
    except Exception:
        return "0"
    if abs(number) < 0.00005:
        return "0"
    return f"{number:.4f}".rstrip("0").rstrip(".")


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
            "context": dict(
                self.env.context,
                default_product_id=self.id,
                default_limit=10,
                dialog_size="extra-large",
            ),
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
    store_balance_line_ids = fields.One2many(
        "ab_stock_report_store_balance_wizard_line",
        "wizard_id",
        string="Store Balances & Sales",
        readonly=True,
    )
    store_balance_filter_store_id = fields.Many2one(
        "ab_store",
        string="Branch",
        domain=STORE_BALANCE_STORE_DOMAIN,
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
    can_load_more = fields.Boolean(
        string="Can Load More",
        compute="_compute_can_load_more",
    )
    has_loaded_lines = fields.Boolean(
        string="Has Loaded Lines",
        compute="_compute_ui_state",
    )
    is_empty_result = fields.Boolean(
        string="Is Empty Result",
        compute="_compute_ui_state",
    )
    active_tab_label = fields.Char(
        string="Movement Family",
        compute="_compute_ui_state",
    )
    cache_source_label = fields.Char(
        string="Cache Source",
        readonly=True,
    )
    cache_progress_label = fields.Char(
        string="Cache Progress",
        readonly=True,
    )
    cache_source_display = fields.Selection(
        [
            ("wizard_cache", "Loaded from Wizard Cache"),
            ("bconnect", "Fetched from BConnect"),
        ],
        string="Cache Source Display",
        compute="_compute_ui_state",
    )
    cache_progress_display = fields.Selection(
        [
            ("more", "More movements available"),
            ("all", "All movements loaded"),
            ("latest", "Latest movements loaded"),
            ("empty", "No movements found"),
            ("none", "No cached movements yet"),
        ],
        string="Cache Progress Display",
        compute="_compute_ui_state",
    )
    loaded_rows_label = fields.Char(
        string="Loaded Rows",
        compute="_compute_ui_state",
    )
    store_balance_count = fields.Integer(
        string="Store Count",
        compute="_compute_store_balance_state",
    )
    store_balance_last_main_update = fields.Datetime(
        string="Main Updated At",
        compute="_compute_store_balance_state",
    )
    store_balance_progress_label = fields.Char(
        string="Refresh Progress",
        compute="_compute_store_balance_state",
    )
    store_balance_active_job_id = fields.Many2one(
        "ab_stock_report_store_balance_job",
        string="Active Direct Update",
        compute="_compute_store_balance_state",
    )

    @api.depends("line_ids")
    def _compute_line_count(self):
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    def _compute_can_load_more(self):
        for wizard in self:
            cache_entry = wizard._get_cache_entry(wizard.active_tab)
            wizard.can_load_more = bool(
                wizard.from_date
                and cache_entry
                and cache_entry.get("fetch_mode") == FETCH_MODE_DATE_RANGE
                and cache_entry.get("has_more")
            )

    @api.depends("active_tab", "line_ids", "line_count", "cache_payload", "from_date", "can_load_more")
    def _compute_ui_state(self):
        tab_labels = dict(MOVEMENT_GROUP_SELECTION)
        for wizard in self:
            cache_entry = wizard._get_cache_entry(wizard.active_tab)
            wizard.has_loaded_lines = bool(wizard.line_ids)
            wizard.is_empty_result = bool(cache_entry.get("empty"))
            wizard.active_tab_label = _(tab_labels.get(wizard.active_tab, ""))
            wizard.cache_source_display = wizard._cache_source_display_key(wizard.cache_source_label)
            wizard.cache_progress_display = wizard._cache_progress_display_key(wizard.cache_progress_label)
            wizard.loaded_rows_label = _("%s movements loaded") % (wizard.line_count or 0)

    def _cache_source_display_key(self, label):
        source_keys = {
            "Loaded from Wizard Cache": "wizard_cache",
            "Fetched from BConnect": "bconnect",
        }
        return source_keys.get(label) or False

    def _cache_progress_display_key(self, label):
        progress_keys = {
            "More movements available": "more",
            "All movements loaded": "all",
            "Latest movements loaded": "latest",
            "No movements found": "empty",
            "No cached movements yet": "none",
        }
        return progress_keys.get(label) or False

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
        self._load_cached_lines(self.active_tab, loaded_from_cache=False)
        return self._soft_reload_action()

    def action_load_lines(self):
        self.ensure_one()
        return self.action_refresh_cache()

    def action_fetch_now(self):
        self.ensure_one()
        self._force_fetch_from_bconnect(self.active_tab)
        self._load_cached_lines(self.active_tab, loaded_from_cache=False)
        return self._soft_reload_action()

    def action_clear_from_date(self):
        self.ensure_one()
        self.from_date = False
        return self._soft_reload_action()

    def action_fetch_sales(self):
        self.ensure_one()
        self.active_tab = "sale"
        self._load_or_fetch_group("sale")
        return self._soft_reload_action()

    def action_fetch_purchase(self):
        self.ensure_one()
        self.active_tab = "purchase"
        self._load_or_fetch_group("purchase")
        return self._soft_reload_action()

    def action_fetch_transfers(self):
        self.ensure_one()
        self.active_tab = "transfer"
        self._load_or_fetch_group("transfer")
        return self._soft_reload_action()

    def action_fetch_store_balances(self):
        self.ensure_one()
        self.active_tab = "store_balance"
        cache_model = self.env["ab_stock_report_store_balance_cache"].sudo()
        if not cache_model.has_main_cache_for_product(self.product_id):
            cache_model.refresh_main_server(self.product_id)
        else:
            cache_model._get_or_create_rows(self.product_id)
        self._load_store_balance_lines()
        return self._soft_reload_action()

    def action_refresh_store_balance_main(self):
        self.ensure_one()
        self.active_tab = "store_balance"
        self.env["ab_stock_report_store_balance_cache"].sudo().refresh_main_server(self.product_id)
        self._load_store_balance_lines()
        return self._soft_reload_action()

    def action_update_all_store_balances(self):
        self.ensure_one()
        self.active_tab = "store_balance"
        self.env["ab_stock_report_store_balance_job"].sudo().enqueue_for_product(self.product_id)
        self._load_store_balance_lines()
        return self._soft_reload_action()

    def action_cancel_store_balance_update(self):
        self.ensure_one()
        self._active_store_balance_job().request_cancel()
        self._load_store_balance_lines()
        return self._soft_reload_action()

    def action_refresh_store_balance_progress(self):
        self.ensure_one()
        self._load_store_balance_lines()
        return self._soft_reload_action()

    def action_clear_store_balance_filter(self):
        self.ensure_one()
        self.store_balance_filter_store_id = False
        self._load_store_balance_lines()
        return self._soft_reload_action()

    @api.onchange("store_balance_filter_store_id")
    def _onchange_store_balance_filter_store_id(self):
        for wizard in self:
            if wizard.id and wizard.active_tab == "store_balance":
                wizard._load_store_balance_lines()

    def action_load_more(self):
        self.ensure_one()
        if not self.from_date:
            return self._soft_reload_action()
        movement_group = self.active_tab
        cache_entry = self._get_cache_entry(movement_group)
        loaded_from_cache = True
        if not cache_entry or cache_entry.get("fetch_mode") != FETCH_MODE_DATE_RANGE:
            self._force_fetch_from_bconnect(movement_group)
            loaded_from_cache = False
        elif cache_entry.get("has_more"):
            self._fetch_next_date_range_batch(movement_group)
            loaded_from_cache = False
        self._load_cached_lines(movement_group, loaded_from_cache=loaded_from_cache)
        return self._soft_reload_action()

    def _load_or_fetch_group(self, movement_group):
        self.ensure_one()
        if movement_group == "store_balance":
            self.action_fetch_store_balances()
            return
        cache_entry = self._get_cache_entry(movement_group)
        loaded_from_cache = True
        if not self._cache_entry_matches_current_request(cache_entry, movement_group):
            self._force_fetch_from_bconnect(movement_group)
            loaded_from_cache = False
        else:
            self.cache_state = self._build_cache_state(
                movement_group,
                cache_entry,
                loaded_from_cache=True,
            )
        self._load_cached_lines(movement_group, loaded_from_cache=loaded_from_cache)

    def _normalize_limit(self):
        return self.env["ab_stock_report_cache_line"]._normalize_limit(self.limit)

    def _get_fetch_mode(self):
        return FETCH_MODE_DATE_RANGE if self.from_date else FETCH_MODE_LIMITED

    def _get_cache_entry(self, movement_group):
        self.ensure_one()
        return (self.cache_payload or {}).get(movement_group) or {}

    def _cache_entry_matches_current_request(self, cache_entry, movement_group):
        self.ensure_one()
        if not cache_entry or "rows" not in cache_entry:
            return False
        fetch_mode = self._get_fetch_mode()
        from_date_value = fields.Date.to_string(self.from_date) if self.from_date else False
        if cache_entry.get("movement_group") != movement_group:
            return False
        if cache_entry.get("product_serial") != self.product_eplus_serial:
            return False
        if cache_entry.get("fetch_mode") != fetch_mode:
            return False
        if cache_entry.get("from_date") != from_date_value:
            return False
        if fetch_mode == FETCH_MODE_LIMITED:
            return cache_entry.get("limit") == self._normalize_limit()
        return cache_entry.get("batch_size") == DATE_RANGE_BATCH_SIZE

    def _open_action(self):
        self.ensure_one()
        action = self.env.ref("ab_stock_report.action_ab_stock_report_wizard").sudo().read()[0]
        action.update({
            "res_id": self.id,
            "context": dict(
                self.env.context,
                default_product_id=self.product_id.id,
                default_limit=self.limit,
                dialog_size="extra-large",
            ),
        })
        return action

    def _soft_reload_action(self):
        self.ensure_one()
        return self._open_action()

    def _bootstrap_from_cache(self):
        self.ensure_one()
        if self.active_tab == "store_balance":
            self._load_store_balance_lines()
        else:
            self._load_cached_lines(self.active_tab)

    def _force_fetch_from_bconnect(self, movement_group=None):
        self.ensure_one()
        if not movement_group:
            movement_group = self.active_tab
        cache_model = self.env["ab_stock_report_cache_line"]
        fetch_mode = self._get_fetch_mode()
        limit_value = self._normalize_limit()
        fetch_limit = DATE_RANGE_BATCH_SIZE + 1 if fetch_mode == FETCH_MODE_DATE_RANGE else limit_value
        rows = cache_model._fetch_group_rows(
            self.product_eplus_serial,
            fetch_limit,
            movement_group=movement_group,
            from_date=self.from_date,
        )
        has_more = False
        if fetch_mode == FETCH_MODE_DATE_RANGE:
            has_more = len(rows) > DATE_RANGE_BATCH_SIZE
            rows = rows[:DATE_RANGE_BATCH_SIZE]
        payload = dict(self.cache_payload or {})
        payload[movement_group] = {
            "movement_group": movement_group,
            "product_serial": self.product_eplus_serial,
            "limit": limit_value,
            "from_date": fields.Date.to_string(self.from_date) if self.from_date else False,
            "fetched_at": fields.Datetime.to_string(fields.Datetime.now()),
            "fetch_mode": fetch_mode,
            "batch_size": DATE_RANGE_BATCH_SIZE if fetch_mode == FETCH_MODE_DATE_RANGE else False,
            "offset": len(rows) if fetch_mode == FETCH_MODE_DATE_RANGE else 0,
            "has_more": has_more,
            "empty": not bool(rows),
            "rows": [cache_model._row_to_json(row) for row in rows],
        }
        self.cache_payload = payload
        self.cache_state = self._build_cache_state(movement_group, payload[movement_group])

    def _fetch_next_date_range_batch(self, movement_group):
        self.ensure_one()
        cache_model = self.env["ab_stock_report_cache_line"]
        payload = dict(self.cache_payload or {})
        cache_entry = dict(payload.get(movement_group) or {})
        rows = cache_model._fetch_group_rows(
            self.product_eplus_serial,
            DATE_RANGE_BATCH_SIZE + 1,
            movement_group=movement_group,
            from_date=self.from_date,
            offset=int(cache_entry.get("offset") or len(cache_entry.get("rows") or [])),
        )
        has_more = len(rows) > DATE_RANGE_BATCH_SIZE
        new_rows = rows[:DATE_RANGE_BATCH_SIZE]
        loaded_rows = list(cache_entry.get("rows") or [])
        loaded_rows.extend(cache_model._row_to_json(row) for row in new_rows)
        cache_entry.update({
            "fetched_at": fields.Datetime.to_string(fields.Datetime.now()),
            "rows": loaded_rows,
            "offset": len(loaded_rows),
            "has_more": has_more,
            "empty": not bool(loaded_rows),
        })
        payload[movement_group] = cache_entry
        self.cache_payload = payload
        self.cache_state = self._build_cache_state(movement_group, cache_entry)

    def _load_cached_lines(self, movement_group=None, loaded_from_cache=True):
        self.ensure_one()
        movement_group = movement_group or self.active_tab
        cache_model = self.env["ab_stock_report_cache_line"]
        cache_entry = (self.cache_payload or {}).get(movement_group) or {}
        rows = cache_model._rows_from_json(cache_entry.get("rows", []))
        last_refresh = (
            fields.Datetime.to_datetime(cache_entry["fetched_at"])
            if cache_entry.get("fetched_at") else False
        )
        state = self._build_cache_state(
            movement_group,
            cache_entry,
            loaded_from_cache=loaded_from_cache,
        ) if cache_entry else _("No cached movements yet")
        source_label, progress_label = self._build_cache_badges(
            cache_entry,
            loaded_from_cache=loaded_from_cache,
        )

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
            "cache_source_label": source_label,
            "cache_progress_label": progress_label,
        })

    def _load_store_balance_lines(self):
        self.ensure_one()
        cache_rows = self.env["ab_stock_report_store_balance_cache"].sudo()._get_or_create_rows(self.product_id)
        self.store_balance_line_ids.unlink()
        lines = self.env["ab_stock_report_store_balance_wizard_line"].create([
            {
                "wizard_id": self.id,
                "cache_id": cache.id,
                "store_id": cache.store_id.id,
                "main_balance": cache.main_balance,
                "direct_balance": cache.direct_balance,
                "difference": cache.difference,
                "sales_days_61_90": cache.sales_days_61_90,
                "sales_days_31_60": cache.sales_days_31_60,
                "sales_last_30_days": cache.sales_last_30_days,
                "sales_total_90_days": cache.sales_total_90_days,
                "direct_status": cache.direct_status,
                "direct_updated_at": cache.direct_updated_at,
                "latest_error": cache.latest_error,
            }
            for cache in cache_rows
        ])
        self.store_balance_line_ids = [(6, 0, lines.ids)]
        last_main = max((dt for dt in cache_rows.mapped("main_updated_at") if dt), default=False)
        self.write({
            "last_refresh": last_main,
            "cache_state": _("Store balances loaded from cache."),
            "cache_source_label": _("Loaded from Wizard Cache"),
            "cache_progress_label": _("Latest movements loaded"),
        })

    def _active_store_balance_job(self):
        self.ensure_one()
        return self.env["ab_stock_report_store_balance_job"].sudo().search([
            ("product_id", "=", self.product_id.id),
            ("state", "in", ("pending", "running", "cancel_requested")),
        ], order="requested_at desc, id desc", limit=1)

    @api.depends("store_balance_line_ids", "product_id")
    def _compute_store_balance_state(self):
        for wizard in self:
            wizard.store_balance_count = len(wizard.store_balance_line_ids)
            dates = [line.cache_id.main_updated_at for line in wizard.store_balance_line_ids if line.cache_id.main_updated_at]
            wizard.store_balance_last_main_update = max(dates) if dates else False
            job = wizard._active_store_balance_job()
            wizard.store_balance_active_job_id = job
            if job:
                state_selection = dict(
                    self.env["ab_stock_report_store_balance_job"]
                    .with_context(lang=self.env.context.get("lang"))
                    .fields_get(["state"])["state"]["selection"]
                )
                wizard.store_balance_progress_label = wizard._format_store_balance_progress(
                    state_selection.get(job.state, job.state),
                    job.completed_count,
                    job.total_count,
                    job.succeeded_count,
                    job.failed_count,
                )
            else:
                wizard.store_balance_progress_label = wizard._store_balance_text("No direct update is running.")

    def _is_arabic_context(self):
        return str(self.env.context.get("lang") or "").startswith("ar")

    def _store_balance_text(self, source):
        if self._is_arabic_context():
            return {
                "No direct update is running.": "لا يوجد تحديث مباشر قيد التشغيل.",
                "stores": "فرع",
                "succeeded": "ناجح",
                "failed": "فشل",
            }.get(source, source)
        return _(source)

    def _format_store_balance_progress(self, state, done, total, succeeded, failed):
        return _("%(state)s: %(done)s/%(total)s %(stores)s, %(ok)s %(succeeded)s, %(bad)s %(failed)s") % {
            "state": state,
            "done": done,
            "total": total,
            "stores": self._store_balance_text("stores"),
            "ok": succeeded,
            "succeeded": self._store_balance_text("succeeded"),
            "bad": failed,
            "failed": self._store_balance_text("failed"),
        }

    def _build_cache_badges(self, cache_entry, loaded_from_cache=False):
        if not cache_entry:
            return "", _("No cached movements yet")
        if cache_entry.get("empty"):
            return "", _("No movements found")

        source_label = _("Loaded from Wizard Cache") if loaded_from_cache else _("Fetched from BConnect")
        if cache_entry.get("fetch_mode") == FETCH_MODE_DATE_RANGE:
            progress_label = (
                _("More movements available")
                if cache_entry.get("has_more")
                else _("All movements loaded")
            )
        else:
            progress_label = _("Latest movements loaded")
        return source_label, progress_label

    def _build_cache_state(self, movement_group, cache_entry, loaded_from_cache=False):
        label = dict(MOVEMENT_GROUP_SELECTION).get(movement_group, movement_group)
        if not cache_entry:
            return _("No cached movements yet")
        if cache_entry.get("empty"):
            return _("No movements found")

        parts = []
        if loaded_from_cache:
            parts.append(_("Loaded from Wizard Cache"))
        else:
            parts.append(_("Fetched from BConnect"))

        if cache_entry.get("fetch_mode") == FETCH_MODE_DATE_RANGE:
            if cache_entry.get("has_more"):
                parts.append(_("More movements available"))
            else:
                parts.append(_("All movements loaded"))
        else:
            parts.append(_("Latest movements loaded"))

        return "%s - %s" % (label, " - ".join(parts))


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
    sale_price_display = fields.Char(
        string="Sale Price",
        compute="_compute_number_display",
    )
    qty_large = fields.Float(
        string="Quantity in Large Unit",
        readonly=True,
        digits=(16, 4),
    )
    qty_large_display = fields.Char(
        string="Quantity in Large Unit",
        compute="_compute_number_display",
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

    @api.depends("sale_price", "qty_large")
    def _compute_number_display(self):
        for line in self:
            line.sale_price_display = _format_number_without_trailing_zeros(line.sale_price)
            line.qty_large_display = _format_number_without_trailing_zeros(line.qty_large)


class AbStockReportStoreBalanceWizardLine(models.TransientModel):
    _name = "ab_stock_report_store_balance_wizard_line"
    _description = "Stock Report Store Balance Wizard Line"
    _order = "store_id, id"

    wizard_id = fields.Many2one(
        "ab_stock_report_wizard",
        required=True,
        ondelete="cascade",
    )
    cache_id = fields.Many2one(
        "ab_stock_report_store_balance_cache",
        string="Cache Row",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        readonly=True,
    )
    main_balance = fields.Float(string="Main Server Balance", readonly=True, digits=(16, 4))
    direct_balance = fields.Float(string="Direct Store Balance", readonly=True, digits=(16, 4))
    difference = fields.Float(string="Difference", readonly=True, digits=(16, 4))
    sales_days_61_90 = fields.Float(string="Days 61-90", readonly=True, digits=(16, 4))
    sales_days_31_60 = fields.Float(string="Days 31-60", readonly=True, digits=(16, 4))
    sales_last_30_days = fields.Float(string="Last 30 Days", readonly=True, digits=(16, 4))
    sales_total_90_days = fields.Float(string="Total 90 Days", readonly=True, digits=(16, 4))
    main_balance_display = fields.Char(
        string="Main Server Balance",
        compute="_compute_number_display",
    )
    direct_balance_display = fields.Char(
        string="Direct Store Balance",
        compute="_compute_number_display",
    )
    difference_display = fields.Char(
        string="Difference",
        compute="_compute_number_display",
    )
    sales_days_61_90_display = fields.Char(
        string="Days 61-90",
        compute="_compute_number_display",
    )
    sales_days_31_60_display = fields.Char(
        string="Days 31-60",
        compute="_compute_number_display",
    )
    sales_last_30_days_display = fields.Char(
        string="Last 30 Days",
        compute="_compute_number_display",
    )
    sales_total_90_days_display = fields.Char(
        string="Total 90 Days",
        compute="_compute_number_display",
    )
    direct_status = fields.Selection(
        DIRECT_STATUS_SELECTION,
        string="Direct Status",
        readonly=True,
    )
    direct_updated_at = fields.Datetime(string="Direct Updated At", readonly=True)
    latest_error = fields.Text(string="Latest Error", readonly=True)

    @api.depends(
        "main_balance",
        "direct_balance",
        "difference",
        "sales_days_61_90",
        "sales_days_31_60",
        "sales_last_30_days",
        "sales_total_90_days",
    )
    def _compute_number_display(self):
        for line in self:
            line.main_balance_display = line._format_balance_number(line.main_balance)
            line.direct_balance_display = line._format_balance_number(line.direct_balance)
            line.difference_display = line._format_balance_number(line.difference)
            line.sales_days_61_90_display = line._format_balance_number(line.sales_days_61_90)
            line.sales_days_31_60_display = line._format_balance_number(line.sales_days_31_60)
            line.sales_last_30_days_display = line._format_balance_number(line.sales_last_30_days)
            line.sales_total_90_days_display = line._format_balance_number(line.sales_total_90_days)

    @staticmethod
    def _format_balance_number(value):
        return _format_number_without_trailing_zeros(value)

    def action_refresh_direct_balance(self):
        self.ensure_one()
        self.cache_id.sudo().refresh_direct_balance()
        wizard = self.wizard_id
        wizard.active_tab = "store_balance"
        wizard._load_store_balance_lines()
        return wizard._soft_reload_action()
