# -*- coding: utf-8 -*-
import ast
import logging
import math
from datetime import timedelta, timezone

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare, format_datetime

_logger = logging.getLogger(__name__)

SMART_STOCK_METHOD_NORMAL = "normal"
SMART_STOCK_METHOD_WEIGHTED = "weighted"
SMART_NORMAL_PERIOD_DAYS = 90.0
SMART_WEIGHTED_PERIOD_DAYS = 30.0
SMART_WEIGHT_LAST_MONTH = 0.5
SMART_WEIGHT_PREVIOUS_MONTH = 0.3
SMART_WEIGHT_THIRD_MONTH = 0.2
SMART_ROW_PRODUCT_SERIAL = 0
SMART_ROW_BRANCH_STOCK_QTY = 4
SMART_ROW_LAST_MONTH_SALES = 5
SMART_ROW_PREVIOUS_MONTH_SALES = 6
SMART_ROW_THIRD_MONTH_SALES = 7
SMART_ROW_TOTAL_3_MONTHS_SALES = 8
SMART_TARGET_PRODUCT_LIMIT = 1000
SMART_STAGE_PURCHASE_PREPARATION = "purchase_preparation"
SMART_STAGE_STORE_PREPARATION = "store_preparation"
SMART_STAGE_STORE_REVISION = "store_revision"
SMART_STAGE_PRE_SUBMIT = "pre_submit"
SMART_STAGE_SUBMIT = "submit"
SMART_LINE_SOURCE_DOMAIN = "domain"
SMART_LINE_SOURCE_WIZARD = "wizard"
SMART_EXPECTED_BALANCE_STAGES = (
    SMART_STAGE_STORE_PREPARATION,
    SMART_STAGE_STORE_REVISION,
    SMART_STAGE_PRE_SUBMIT,
    SMART_STAGE_SUBMIT,
)
SMART_EXPORT_STAGES = (
    SMART_STAGE_PURCHASE_PREPARATION,
    SMART_STAGE_STORE_PREPARATION,
    SMART_STAGE_STORE_REVISION,
)
SMART_EXPORT_COMPANY_NAME = "مخزن عابدين فارما جروب للتجارة والتوزيع"
SMART_GROUP_PURCHASE = "ab_transfer_smart.group_transfer_smart_purchase"
SMART_GROUP_STORE_PREPARATION = "ab_transfer_smart.group_trnasfer_smart_store_preparation"
SMART_GROUP_STORE_REVISION = "ab_transfer_smart.group_trnasfer_smart_store_revision"
SMART_GROUP_STORE_MANAGER = "ab_transfer_smart.group_trnasfer_smart_store_manager"
SMART_SKIP_ZERO_SOURCE_STOCK_WARNING_CONTEXT_KEY = (
    "skip_smart_zero_source_stock_warning"
)
SMART_IGNORED_ZERO_SOURCE_PRODUCT_IDS_CONTEXT_KEY = (
    "smart_ignored_zero_source_product_ids"
)
SMART_TRANSFER_LINE_COPY_FIELDS = (
    "uom_id",
    "smart_source_stock_qty",
    "smart_qty_before_int",
    "smart_destination_stock_qty",
    "smart_month1_sales",
    "smart_month2_sales",
    "smart_month3_sales",
    "smart_other_stores_stock_qty",
    "smart_other_stores_month1_sales",
    "smart_other_stores_month2_sales",
    "smart_other_stores_month3_sales",
    "smart_need_destination_store",
    "smart_need_other_store",
    "smart_total_need",
    "smart_distribution_ratio",
)

class AbTransferHeader(models.Model):
    _inherit = "ab_transfer_header"

    active = fields.Boolean(
        default=True,
        index=True,
    )

    eplus_serial = fields.Integer(
        string="EPlus Serial",
        copy=False,
        readonly=True,
        index=True,
    )

    smart_stage = fields.Selection(
        selection=[
            (SMART_STAGE_PURCHASE_PREPARATION, "Purchase Preparation"),
            (SMART_STAGE_STORE_PREPARATION, "Store Preparation"),
            (SMART_STAGE_STORE_REVISION, "Store Revision"),
            (SMART_STAGE_PRE_SUBMIT, "Pre-Submit"),
            (SMART_STAGE_SUBMIT, "Submit"),
        ],
        string="Smart Stage",
        default=SMART_STAGE_PURCHASE_PREPARATION,
        required=True,
        copy=False,
    )

    smart_line_ids = fields.One2many(
        "ab_transfer_smart_line",
        "header_id",
        string="Smart Lines",
        copy=False,
    )
    smart_items_count = fields.Integer(
        string="Smart Items Count",
        compute="_compute_smart_items_count",
        store=True,
    )

    smart_wizard_id = fields.Many2one(
        "ab_transfer_smart_wizard",
        string="Smart Wizard",
        copy=False,
        ondelete="set null",
    )

    target_product_ids = fields.Many2many(
        comodel_name='ab_product',
        relation='ab_transfer_header_product_rel',
        column1='header_id',
        column2='product_id',
        string='Target Products')

    smart_product_line_ids = fields.One2many(
        "ab_transfer_smart_product_line",
        "header_id",
        string="Requested Products",
        copy=False,
    )

    fair_store_ids = fields.Many2many(
        comodel_name='ab_store',
        relation='ab_transfer_header_fair_store_rel',
        column1='header_id',
        column2='store_id',
        string='Fair Stores')

    smart_product_domain = fields.Char(
        string="Product Filter",
        default="[]",
        help="Build a product filter to include matching products in Smart Transfer.",
    )

    smart_days = fields.Integer(
        string="Smart Days",
        default=60,
        required=True,
    )
    smart_stock_method = fields.Selection(
        selection=[
            (SMART_STOCK_METHOD_WEIGHTED, "Weighted Method"),
            (SMART_STOCK_METHOD_NORMAL, "Normal Method"),
        ],
        string="Stock Calculation Method",
        default=SMART_STOCK_METHOD_WEIGHTED,
        required=True,
        help=(
            "Weighted method: last month x 50%, previous month x 30%, "
            "third month x 20%, then divide by 30 and multiply by Smart Days. "
            "Normal method: total sales for the last 3 months / 90 x Smart Days. "
            "After planning, destination stock is deducted and the result is capped by source stock."
        ),
    )
    smart_dropout_coverage = fields.Integer(
        string="Dropout Coverage %",
        default=0,
        copy=False,
        help="Exclude smart lines when destination stock covers this percentage of the planned quantity.",
    )
    @api.constrains("smart_days")
    def _check_smart_days(self):
        for rec in self:
            if rec.smart_days < 1:
                raise ValidationError(_("Smart days must be at least 1."))

    @api.constrains("smart_dropout_coverage")
    def _check_smart_dropout_coverage(self):
        for rec in self:
            if rec.smart_dropout_coverage < 0 or rec.smart_dropout_coverage > 100:
                raise ValidationError(_("Dropout coverage must be between 0 and 100."))

    @api.constrains("target_product_ids")
    def _check_target_product_limit(self):
        for rec in self:
            if len(rec.target_product_ids) > SMART_TARGET_PRODUCT_LIMIT:
                raise ValidationError(
                    _("Target products are limited to %s products.")
                    % SMART_TARGET_PRODUCT_LIMIT
                )

    @api.constrains("smart_product_line_ids")
    def _check_smart_product_line_limit(self):
        for rec in self:
            if len(rec.smart_product_line_ids) > SMART_TARGET_PRODUCT_LIMIT:
                raise ValidationError(
                    _("Smart product lines are limited to %s products.")
                    % SMART_TARGET_PRODUCT_LIMIT
                )

    @api.constrains("smart_product_line_ids", "smart_product_line_ids.product_id")
    def _check_unique_smart_product_lines(self):
        for rec in self:
            product_ids = rec.smart_product_line_ids.mapped("product_id").ids
            if len(product_ids) != len(set(product_ids)):
                raise ValidationError(
                    _("Each product can be added once only. Update the existing line quantity instead.")
                )

    @api.depends("smart_line_ids")
    def _compute_smart_items_count(self):
        for rec in self:
            rec.smart_items_count = len(rec.smart_line_ids)

    @api.model
    def get_transfer_dashboard_payload(self):
        payload = super().get_transfer_dashboard_payload()
        for action in payload.get("quick_actions", []):
            if action.get("key") == "smart_transfer":
                action["action"] = "ab_transfer_smart.ab_transfer_smart_wizard_action"
                break
        return payload

    def write(self, vals):
        vals = dict(vals or {})
        duplicate_check_fields = {"smart_stage", "from_store_id", "to_store_id"}
        previous_stage_by_id = {}
        if duplicate_check_fields.intersection(vals):
            previous_stage_by_id = {
                header.id: header.smart_stage
                for header in self
            }

        with self.env.cr.savepoint():
            result = super().write(vals)

            headers_to_check = self.browse()
            target_stages = {
                SMART_STAGE_STORE_PREPARATION,
                SMART_STAGE_STORE_REVISION,
                SMART_STAGE_PRE_SUBMIT,
                SMART_STAGE_SUBMIT,
            }
            if "smart_stage" in vals:
                headers_to_check |= self.filtered(
                    lambda header: (
                            previous_stage_by_id.get(header.id) == SMART_STAGE_PURCHASE_PREPARATION
                            and header.smart_stage in target_stages
                    )
                )
            if {"from_store_id", "to_store_id"}.intersection(vals):
                headers_to_check |= self.filtered(
                    lambda header: header.smart_stage != SMART_STAGE_PURCHASE_PREPARATION
                )
            if headers_to_check:
                headers_to_check.mapped("smart_line_ids")._check_duplicate_transfer_lines()

        return result

    def action_clear_target_products(self):
        for rec in self:
            if rec.is_submitted:
                raise UserError(_("Submitted transfers cannot be edited."))
            rec.target_product_ids = [(5, 0, 0)]
            rec.smart_product_line_ids.unlink()
        return self._smart_notification(
            _("Target Products"),
            _("Target products have been removed."),
            "success",
        )

    def action_open_smart_transfer_lines(self):
        self.ensure_one()
        list_view = self.env.ref("ab_transfer_smart.ab_transfer_smart_line_view_list")
        form_view = self.env.ref("ab_transfer_smart.ab_transfer_smart_line_view_form")
        search_view = self.env.ref("ab_transfer_smart.ab_transfer_smart_line_view_search")
        return {
            "type": "ir.actions.act_window",
            "name": _("Smart Transfer Data"),
            "res_model": "ab_transfer_smart_line",
            "view_mode": "list,form",
            "views": [(list_view.id, "list"), (form_view.id, "form")],
            "search_view_id": search_view.id,
            "domain": [("header_id", "=", self.id)],
            "context": {"default_header_id": self.id},
        }

    def action_print_smart_transfer_lines(self):
        self.ensure_one()
        return self.env.ref(
            "ab_transfer_smart.action_report_ab_transfer_smart_lines"
        ).report_action(self)

    def action_print_transfer_lines(self):
        self.ensure_one()
        return self.env.ref(
            "ab_transfer_smart.action_report_ab_transfer_lines"
        ).report_action(self)

    def _check_smart_export_allowed(self):
        self.ensure_one()
        if self.is_submitted or self.smart_stage not in SMART_EXPORT_STAGES:
            raise UserError(
                _("Smart Transfer Excel can only be exported before Pre-Submit.")
            )

    def _prepare_smart_export_probe_vals(self):
        self.ensure_one()
        return {
            "from_store_id": self.from_store_id.id,
            "to_store_id": self.to_store_id.id,
            "user_id": self.user_id.id,
            "company_id": self.company_id.id,
            "smart_days": self.smart_days,
            "smart_stock_method": self.smart_stock_method,
            "smart_product_domain": self.smart_product_domain or "[]",
            "smart_dropout_coverage": self.smart_dropout_coverage,
            "fair_store_ids": [(6, 0, self.fair_store_ids.ids)],
            "target_product_ids": [(6, 0, self.target_product_ids.ids)],
            "smart_product_line_ids": [
                (0, 0, {
                    "product_id": line.product_id.id,
                    "qty": line.qty or line.product_id.min_sale_purchase_qty or 1.0,
                })
                for line in self.smart_product_line_ids
            ],
        }

    def _get_smart_transfer_excel_rows(
            self,
            allow_incomplete_sales_cache=False,
            allow_empty=False,
    ):
        self.ensure_one()
        self._check_smart_export_allowed()
        source_rows_by_product = {}
        probe = self.env["ab_transfer_header"].new(
            self._prepare_smart_export_probe_vals()
        ).with_context(
            smart_export_readonly=True,
            skip_smart_sales_cache_coverage=bool(allow_incomplete_sales_cache),
            smart_export_source_rows_by_product=source_rows_by_product,
        )
        probe._validate_smart_transfer_header()

        missing_dates = []
        if probe._get_smart_other_branch_store_sql_ids():
            missing_dates = probe._get_smart_missing_sales_cache_dates_readonly()
        if missing_dates and not allow_incomplete_sales_cache:
            raise UserError(
                probe._format_smart_export_sales_cache_warning_message(missing_dates)
            )

        destination_rows = probe._fetch_destination_smart_rows_readonly()
        preview_rows, _ = probe._prepare_smart_transfer_preview_rows(destination_rows)
        if not preview_rows:
            if allow_empty:
                return []
            raise UserError(_("No items are needed for transfer."))

        export_rows = []
        for preview_row in preview_rows:
            product = preview_row["product"]
            line_vals = preview_row["line_vals"]
            source_rows = source_rows_by_product.get(product.id)
            if source_rows is None:
                source_rows = probe._get_source_inventory_rows(product)
                source_rows_by_product[product.id] = source_rows
            current_price_row = source_rows[0] if source_rows else {}
            month1_sales = float(line_vals.get("smart_month1_sales", 0.0) or 0.0)
            month2_sales = float(line_vals.get("smart_month2_sales", 0.0) or 0.0)
            month3_sales = float(line_vals.get("smart_month3_sales", 0.0) or 0.0)
            export_rows.append({
                "code": product.code or "",
                "product_name": product.name or "",
                "company": SMART_EXPORT_COMPANY_NAME,
                "purchase_unit": float(product.min_sale_purchase_qty or 0.0),
                "sell_price": float(current_price_row.get("price", 0.0) or 0.0),
                "purchase_price": float(current_price_row.get("pharm_price", 0.0) or 0.0),
                "source_stock": float(line_vals.get("smart_source_stock_qty", 0.0) or 0.0),
                "destination_stock": float(
                    line_vals.get("smart_destination_stock_qty", 0.0) or 0.0
                ),
                "sales_3_month": month1_sales + month2_sales + month3_sales,
                "moving_weighted_avg": probe._calculate_smart_weighted_monthly_sales(
                    month1_sales,
                    month2_sales,
                    month3_sales,
                ),
                "need": float(line_vals.get("qty", 0.0) or 0.0),
            })
        return export_rows

    def get_smart_report_sorted_lines(self, lines):
        self.ensure_one()
        return self._sort_smart_lines_by_product_location(lines)

    def get_smart_lines_for_report(self):
        self.ensure_one()
        return self.get_smart_report_sorted_lines(self.smart_line_ids)

    def get_transfer_lines_for_report(self):
        self.ensure_one()
        return self.get_smart_report_sorted_lines(self.line_ids)

    def get_smart_report_transfer_date_text(self):
        self.ensure_one()
        transfer_date = self.sent_at or self.create_date
        return self._format_smart_report_datetime(transfer_date)

    def get_smart_report_eplus_serial_text(self):
        self.ensure_one()
        if "eplus_serial" not in self._fields:
            return ""
        return str(self.eplus_serial or "")

    def get_smart_report_printing_date_text(self):
        self.ensure_one()
        return self._format_smart_report_datetime(fields.Datetime.now())

    def get_smart_report_uom_text(self, line):
        self.ensure_one()
        uom_name = line.uom_id.name or ""
        if uom_name.upper() == "BOX":
            return _("BOX")
        return uom_name

    def _format_smart_report_datetime(self, value):
        return format_datetime(
            self.env,
            value,
            dt_format="yyyy-MM-dd HH:mm",
        ) if value else ""

    def action_smart_refresh_destination_cache(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_PURCHASE)
        self._check_smart_stage(SMART_STAGE_PURCHASE_PREPARATION)
        self._check_smart_not_submitted()
        result = self._refresh_smart_destination_cache(force=True)
        return self._smart_notification(
            _("Smart Transfer Cache"),
            _(
                "Smart cache refreshed. Stores: %(stores)s, Stock rows: %(stock_rows)s, "
                "Sales rows: %(sales_rows)s."
            )
            % result,
            "success",
        )

    def action_smart_transfer_calculation(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_PURCHASE)
        self._check_smart_stage(SMART_STAGE_PURCHASE_PREPARATION)
        self._ensure_smart_destination_cache()
        try:
            self._validate_smart_transfer_header()
            warning_action = self._get_smart_sales_cache_warning_action_if_needed()
            if warning_action:
                return warning_action

            self._ensure_smart_source_cache()
            source_stock_context = self._get_smart_candidate_source_stock_context()
            if not self.env.context.get(
                    SMART_SKIP_ZERO_SOURCE_STOCK_WARNING_CONTEXT_KEY
            ):
                zero_stock_action = self._get_smart_zero_source_stock_warning_action(
                    source_stock_context
                )
                if zero_stock_action:
                    return zero_stock_action

            destination_rows = self._fetch_destination_smart_rows(
                source_stock_context=source_stock_context
            )
        except UserError as error:
            return self._smart_notification(
                _("Smart Transfer Calculation"),
                str(error),
                "danger",
            )

        result = self._apply_smart_transfer_rows(destination_rows)

        if not result["created"] and not result["updated"]:
            return self._smart_notification(
                _("Smart Transfer Calculation"),
                _("No items are needed for transfer."),
                "warning",
            )

        return self._smart_notification(
            _("Smart Transfer Calculation"),
            _(
                "Smart transfer completed. Created: %(created)s, Updated: %(updated)s, "
                "Dropout excluded: %(dropout_excluded)s, Skipped missing products: %(missing)s, "
                "Skipped no source stock: %(no_stock)s."
            )
            % result,
            "success",
        )

    def action_smart_apply_dropout_coverage(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_PURCHASE)
        self._check_smart_stage(SMART_STAGE_PURCHASE_PREPARATION)
        self._check_smart_not_submitted()
        if self.smart_dropout_coverage <= 0:
            raise UserError(_("Set Dropout Coverage % before applying dropout."))
        if not self.smart_line_ids:
            raise UserError(_("There are no smart lines to apply dropout coverage to."))

        result = self._apply_smart_dropout_coverage_to_lines()
        return self._smart_notification(
            _("Smart Transfer Dropout"),
            _(
                "Dropout coverage applied. Excluded: %(excluded)s, Cleared: %(cleared)s, "
                "Manual exclusions kept: %(manual_kept)s."
            )
            % result,
            "success",
        )

    def action_smart_to_store_preparation(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_PURCHASE)
        self._check_smart_stage(SMART_STAGE_PURCHASE_PREPARATION)
        self._check_smart_not_submitted()
        eligible_lines = self.smart_line_ids.filtered(
            lambda line: not line.exclusion_reason
        )
        eligible_lines._check_smart_qty_allowed_over()
        self._validate_smart_source_stock_available(eligible_lines)
        self.write({"smart_stage": SMART_STAGE_STORE_PREPARATION})
        return self._smart_notification(
            _("Smart Transfer Stage"),
            _("Smart transfer moved to Store Preparation."),
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_smart_to_store_revision(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_STORE_PREPARATION)
        self._check_smart_stage(SMART_STAGE_STORE_PREPARATION)
        self._check_smart_not_submitted()
        self.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        return self._smart_notification(
            _("Smart Transfer Stage"),
            _("Smart transfer moved to Store Revision."),
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_smart_pre_submit(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_STORE_REVISION)
        self._check_smart_stage(SMART_STAGE_STORE_REVISION)
        self._check_smart_not_submitted()
        result = self._copy_smart_lines_to_transfer_lines()
        self.write({"smart_stage": SMART_STAGE_PRE_SUBMIT})
        return self._smart_notification(
            _("Smart Transfer Pre-Submit"),
            _(
                "Pre-submit completed. Created: %(created)s, Updated: %(updated)s, "
                "Excluded: %(excluded)s."
            )
            % result,
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_smart_back_to_purchase_preparation(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_STORE_MANAGER)
        self._check_smart_stage(SMART_STAGE_STORE_PREPARATION)
        self._check_smart_not_submitted()
        self.write({"smart_stage": SMART_STAGE_PURCHASE_PREPARATION})
        return self._smart_notification(
            _("Smart Transfer Stage"),
            _("Smart transfer moved back to Purchase Preparation."),
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_smart_back_to_store_preparation(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_STORE_MANAGER)
        self._check_smart_stage(SMART_STAGE_STORE_REVISION)
        self._check_smart_not_submitted()
        self.write({"smart_stage": SMART_STAGE_STORE_PREPARATION})
        return self._smart_notification(
            _("Smart Transfer Stage"),
            _("Smart transfer moved back to Store Preparation."),
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_smart_back_to_store_revision(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_STORE_MANAGER)
        self._check_smart_stage(SMART_STAGE_PRE_SUBMIT)
        self._check_smart_not_submitted()
        removed_count = self._clear_smart_transfer_lines(sudo_unlink=True)
        self.write({"smart_stage": SMART_STAGE_STORE_REVISION})
        return self._smart_notification(
            _("Smart Transfer Stage"),
            _(
                "Smart transfer moved back to Store Revision. "
                "Transfer lines removed: %(removed)s."
            )
            % {"removed": removed_count},
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_submit(self):
        self.ensure_one()
        fast_transfer_immediate_submit = self.env.context.get("fast_transfer_immediate_submit")
        if not self.is_submitted and not fast_transfer_immediate_submit:
            self._check_smart_group(SMART_GROUP_STORE_REVISION)
            self._check_smart_stage(SMART_STAGE_PRE_SUBMIT)

        previous_stage = self.smart_stage
        if (
                not self.is_submitted
                and not fast_transfer_immediate_submit
                and self.smart_stage != SMART_STAGE_SUBMIT
        ):
            self.write({"smart_stage": SMART_STAGE_SUBMIT})

        try:
            result = super().action_submit()
            if self.is_submitted:
                self._mark_smart_transfer_request_done_after_submit()
                self._sync_smart_eplus_serial_from_sent_transfer()
            return self._smart_soft_reload_action() if result is True else result
        except Exception:
            if not self.is_submitted and self.smart_stage != previous_stage:
                self.write({"smart_stage": previous_stage})
            raise

    def _mark_smart_transfer_request_done_after_submit(self):
        self.ensure_one()
        if (
                self.transfer_request_id
                and self.transfer_request_id.execution_state != "done"
        ):
            self.transfer_request_id.write({"execution_state": "done"})

    def _sync_smart_eplus_serial_from_sent_transfer(self):
        self.ensure_one()
        if self.eplus_serial:
            return

        try:
            eplus_serial = self._find_smart_submitted_eplus_serial()
        except Exception:
            _logger.exception("Failed to read EPlus serial for smart transfer ID %s", self.id)
            return

        if eplus_serial:
            self._write_smart_eplus_serial_after_submit(eplus_serial)

    def _write_smart_eplus_serial_after_submit(self, eplus_serial):
        self.ensure_one()
        models.Model.write(self.sudo(), {"eplus_serial": eplus_serial})

    def _find_smart_submitted_eplus_serial(self):
        self.ensure_one()
        transfer_reference = "Odoo Transfer: %s" % self.display_name
        from_store_sql_id = self._get_ref_id(self.from_store_id, _("Source Store"))
        to_store_sql_id = self._get_ref_id(self.to_store_id, _("Destination Store"))
        with self._get_sql_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    SELECT TOP (1) stnh_id
                    FROM Store_Trans_h
                    WHERE stnh_f_Sto_id = ?
                      AND stnh_t_Sto_id = ?
                      AND stnh_notes LIKE ?
                    ORDER BY stnh_id DESC
                    """,
                    (
                        from_store_sql_id,
                        to_store_sql_id,
                        "%%%s%%" % transfer_reference,
                    ),
                )
                row = cursor.fetchone()
                return int(row[0]) if row and row[0] else 0
            finally:
                cursor.close()

    def _check_smart_group(self, group_xmlid):
        if not self.env.user.has_group(group_xmlid):
            raise AccessError(_("You are not allowed to perform this smart transfer action."))

    def _check_smart_stage(self, expected_stage):
        self.ensure_one()
        if self.smart_stage != expected_stage:
            raise UserError(
                _("This action is only allowed in the %(stage)s stage.")
                % {"stage": self._get_smart_stage_label(expected_stage)}
            )

    def _check_smart_not_submitted(self):
        self.ensure_one()
        if self.is_submitted:
            raise UserError(_("Submitted transfers cannot be edited."))

    def _get_smart_stage_label(self, stage):
        selection = dict(self._fields["smart_stage"].selection)
        return selection.get(stage, stage)

    def _copy_smart_lines_to_transfer_lines(self):
        self.ensure_one()
        smart_lines = self.smart_line_ids
        eligible_lines = smart_lines.filtered(lambda line: not line.exclusion_reason)
        eligible_lines = self._sort_smart_lines_by_product_location(eligible_lines)
        excluded_count = len(smart_lines) - len(eligible_lines)
        if not eligible_lines:
            raise UserError(_("There are no eligible smart lines to pre-submit."))

        self._validate_smart_source_stock_available(eligible_lines)

        vals_list = []
        for smart_line in eligible_lines:
            vals_list.extend(self._prepare_transfer_line_vals_list_from_smart_line(smart_line))

        self._clear_smart_transfer_lines()
        if vals_list:
            self.env["ab_transfer_line"].create(vals_list)

        result = {
            "created": len(vals_list),
            "updated": 0,
            "excluded": excluded_count,
        }
        return result

    def _validate_smart_source_stock_available(self, smart_lines):
        self.ensure_one()
        smart_lines = smart_lines.filtered(lambda line: line.product_id)
        if not smart_lines:
            return

        products = smart_lines.mapped("product_id")
        products_by_serial = {}
        product_serial_by_id = {}
        for product in products:
            product_serial = self._get_smart_product_serial(product)
            if not product_serial:
                continue
            products_by_serial.setdefault(product_serial, product)
            product_serial_by_id[product.id] = product_serial

        live_stock_by_serial = self._get_smart_source_stock_by_product_serial(products_by_serial)
        reserved_qty_by_key = self._read_smart_active_reserved_qty_by_product_store(
            products.ids,
            self.from_store_id.ids,
            exclude_header_ids=self.ids,
        )
        requested_qty_by_product = {}
        for line in smart_lines:
            requested_qty_by_product[line.product_id.id] = (
                requested_qty_by_product.get(line.product_id.id, 0.0)
                + float(line.qty or 0.0)
            )

        errors = []
        for product in products.sorted(lambda rec: (rec.display_name or rec.name or "").casefold()):
            requested_qty = requested_qty_by_product.get(product.id, 0.0)
            product_serial = product_serial_by_id.get(product.id)
            live_stock_qty = live_stock_by_serial.get(product_serial, 0.0)
            reserved_qty = reserved_qty_by_key.get((product.id, self.from_store_id.id), 0.0)
            available_qty = live_stock_qty - reserved_qty
            if float_compare(requested_qty, available_qty, precision_digits=3) <= 0:
                continue

            errors.append(
                _(
                    "%(product)s: live stock %(live).3f, already reserved %(reserved).3f, "
                    "available %(available).3f, requested %(requested).3f."
                )
                % {
                    "product": product.display_name,
                    "live": live_stock_qty,
                    "reserved": reserved_qty,
                    "available": available_qty,
                    "requested": requested_qty,
                }
            )

        if errors:
            raise UserError(
                _(
                    "Cannot continue because source stock is no longer available. "
                    "Some quantities are already reserved by active smart transfers:\n%s"
                )
                % "\n".join(errors)
            )

    def _clear_smart_transfer_lines(self, sudo_unlink=False):
        self.ensure_one()
        line_ids = self.sudo().line_ids if sudo_unlink else self.line_ids
        removed_count = len(line_ids)
        if line_ids:
            line_ids.unlink()
        return removed_count

    def _prepare_transfer_line_vals_list_from_smart_line(self, smart_line):
        self.ensure_one()
        vals = {
            "header_id": self.id,
            "product_id": smart_line.product_id.id,
        }
        target_fields = self.env["ab_transfer_line"]._fields
        for field_name in SMART_TRANSFER_LINE_COPY_FIELDS:
            if field_name not in smart_line._fields or field_name not in target_fields:
                continue
            field = smart_line._fields[field_name]
            value = smart_line[field_name]
            if field.type == "many2one":
                value = value.id
            vals[field_name] = value

        remaining_qty = float(smart_line.qty or 0.0)
        if float_compare(remaining_qty, 0.0, precision_digits=3) <= 0:
            return []

        vals_list = []
        for source_row in self._get_source_inventory_rows(smart_line.product_id):
            source_qty = self._dict_float(source_row, "qty")
            class_id = int(source_row.get("source_id") or 0)
            expiry_date = str(source_row.get("exp_date") or "").split(" ")[0]
            if (
                    float_compare(source_qty, 0.0, precision_digits=3) <= 0
                    or not class_id
                    or not expiry_date
            ):
                continue

            transfer_qty = min(remaining_qty, source_qty)
            if float_compare(transfer_qty, 0.0, precision_digits=3) <= 0:
                continue

            vals_list.append({
                **vals,
                "class_id": class_id,
                "qty": transfer_qty,
                "expiry_date": expiry_date,
            })
            remaining_qty -= transfer_qty
            if float_compare(remaining_qty, 0.0, precision_digits=3) <= 0:
                break

        if float_compare(remaining_qty, 0.0, precision_digits=3) > 0:
            raise UserError(
                _(
                    "Source stock is no longer enough for %(product)s. "
                    "Missing quantity: %(qty).3f."
                )
                % {
                    "product": smart_line.product_id.display_name,
                    "qty": remaining_qty,
                }
            )

        return vals_list

    def _validate_smart_transfer_header(self):
        self.ensure_one()
        if self.is_submitted:
            raise UserError(_("Submitted transfers cannot be recalculated."))
        if not self.from_store_id:
            raise UserError(_("Source store is required."))
        if not self.to_store_id:
            raise UserError(_("Destination store is required."))
        if self.from_store_id == self.to_store_id:
            raise UserError(_("Source store and destination store cannot be the same."))
        if self.smart_days < 1:
            raise UserError(_("Smart days must be at least 1."))
        if not self.smart_stock_method:
            raise UserError(_("Stock calculation method is required."))
        self._get_smart_candidate_products()

        self._get_ref_id(self.from_store_id, _("Source Store"))
        self._get_smart_destination_store_sql_id()
        self._validate_smart_source_connection()

    def _get_smart_product_filter_domain(self):
        self.ensure_one()
        try:
            parsed_domain = ast.literal_eval(self.smart_product_domain or "[]")
            return fields.Domain(parsed_domain)
        except (TypeError, ValueError, SyntaxError):
            raise UserError(_("Invalid product filter. Please review the filter conditions."))

    def _get_smart_candidate_products(self):
        self.ensure_one()
        Product = self.env["ab_product"]
        product_domain = self._get_smart_product_filter_domain()
        ignored_product_ids = self._get_smart_ignored_zero_source_product_ids()
        domain_products = Product.browse()
        if not product_domain.is_true():
            if ignored_product_ids:
                product_domain &= fields.Domain(
                    "id",
                    "not in",
                    list(ignored_product_ids),
                )
            try:
                domain_products = Product.search(product_domain)
            except Exception:
                raise UserError(_("Invalid product filter. Please review the filter conditions."))

        products = domain_products | self.target_product_ids | self.smart_product_line_ids.mapped("product_id")
        if ignored_product_ids:
            products -= Product.browse(ignored_product_ids)
        if not products and not ignored_product_ids:
            raise UserError(_("Please add target products or set a product filter."))
        return products

    def _get_smart_ignored_zero_source_product_ids(self):
        return {
            int(product_id)
            for product_id in self.env.context.get(
                SMART_IGNORED_ZERO_SOURCE_PRODUCT_IDS_CONTEXT_KEY,
                [],
            )
            if product_id
        }

    def _validate_smart_source_connection(self):
        self.ensure_one()
        with self._get_sql_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

    def _get_smart_destination_store_sql_id(self):
        self.ensure_one()
        destination_store = self.to_store_id
        destination_store_sql_id = destination_store.eplus_serial
        if destination_store_sql_id in (False, None, "", 0):
            raise UserError(
                _("Destination store EPlus serial is missing: %s")
                % destination_store.display_name
            )
        return int(destination_store_sql_id)

    def _fetch_destination_smart_rows(self, source_stock_context=None):
        self.ensure_one()
        destination_store_sql_id = self._get_smart_destination_store_sql_id()
        product_serials = self._get_smart_target_product_serials_with_source_stock(
            source_stock_context=source_stock_context
        )
        if not product_serials:
            return []

        self._ensure_smart_destination_cache()
        return self._read_smart_destination_cache_rows(
            product_serials,
            destination_store_sql_id,
        )

    def _fetch_destination_smart_rows_readonly(self):
        """Read today's cache when present and fall back to live SELECTs without caching."""
        self.ensure_one()
        destination_store_sql_id = self._get_smart_destination_store_sql_id()
        product_serials = sorted({
            int(serial)
            for serial in self._get_smart_target_product_serials_with_source_stock()
            if serial
        })
        if not product_serials:
            return []

        cache_date = fields.Date.context_today(self)
        StockCache = self.env["ab_transfer_smart_stock_cache"].sudo()
        SalesCache = self.env["ab_transfer_smart_sales_cache"].sudo()
        stock_cache_domain = [
            ("store_id", "=", self.to_store_id.id),
            ("cache_date", "=", cache_date),
        ]
        sales_cache_domain = [
            ("store_id", "=", self.to_store_id.id),
            ("cache_date", "=", cache_date),
        ]

        if StockCache.search_count(stock_cache_domain):
            stock_by_serial = {
                int(line.product_eplus_serial): float(line.stock_qty or 0.0)
                for line in StockCache.search([
                    *stock_cache_domain,
                    ("product_eplus_serial", "in", product_serials),
                ])
            }
        else:
            stock_by_serial = StockCache._fetch_store_stock_rows(self.to_store_id)

        if SalesCache.search_count(sales_cache_domain):
            sales_by_serial = {
                int(line.product_eplus_serial): {
                    "month1_sales": float(line.month1_sales or 0.0),
                    "month2_sales": float(line.month2_sales or 0.0),
                    "month3_sales": float(line.month3_sales or 0.0),
                }
                for line in SalesCache.search([
                    *sales_cache_domain,
                    ("product_eplus_serial", "in", product_serials),
                ])
            }
        else:
            sales_by_serial = SalesCache._fetch_store_sales_rows(self.to_store_id)

        rows = []
        for product_serial in product_serials:
            sales = sales_by_serial.get(product_serial, {})
            month1_sales = float(sales.get("month1_sales", 0.0) or 0.0)
            month2_sales = float(sales.get("month2_sales", 0.0) or 0.0)
            month3_sales = float(sales.get("month3_sales", 0.0) or 0.0)
            rows.append((
                product_serial,
                "",
                "",
                destination_store_sql_id,
                float(stock_by_serial.get(product_serial, 0.0) or 0.0),
                month1_sales,
                month2_sales,
                month3_sales,
                month1_sales + month2_sales + month3_sales,
            ))
        return rows

    def _ensure_smart_destination_cache(self):
        self.ensure_one()
        return self._refresh_smart_destination_cache(force=False)

    def _refresh_smart_destination_cache(self, force=False):
        self.ensure_one()
        if not self.to_store_id:
            raise UserError(_("Destination store is required."))
        return self.env["ab_transfer_smart_stock_cache"].sudo().refresh_stores_cache(
            self.to_store_id,
            force=force,
        )

    def _ensure_smart_source_cache(self):
        self.ensure_one()
        return self._refresh_smart_source_cache(force=False)

    def _refresh_smart_source_cache(self, force=False):
        self.ensure_one()
        if not self.from_store_id:
            raise UserError(_("Source store is required."))
        return self.env["ab_transfer_smart_source_stock_cache"].sudo().refresh_stores_cache(
            self.from_store_id,
            force=force,
        )

    def _read_smart_destination_cache_rows(self, product_serials, destination_store_sql_id):
        self.ensure_one()
        cache_date = fields.Date.context_today(self)
        serials = sorted({int(serial) for serial in product_serials if serial})
        if not serials:
            return []

        StockCache = self.env["ab_transfer_smart_stock_cache"].sudo()
        SalesCache = self.env["ab_transfer_smart_sales_cache"].sudo()
        stock_by_serial = {
            int(line.product_eplus_serial): float(line.stock_qty or 0.0)
            for line in StockCache.search([
                ("store_id", "=", self.to_store_id.id),
                ("cache_date", "=", cache_date),
                ("product_eplus_serial", "in", serials),
            ])
        }
        sales_by_serial = {
            int(line.product_eplus_serial): line
            for line in SalesCache.search([
                ("store_id", "=", self.to_store_id.id),
                ("cache_date", "=", cache_date),
                ("product_eplus_serial", "in", serials),
            ])
        }

        rows = []
        for product_serial in serials:
            sales_line = sales_by_serial.get(product_serial)
            month1_sales = float(sales_line.month1_sales or 0.0) if sales_line else 0.0
            month2_sales = float(sales_line.month2_sales or 0.0) if sales_line else 0.0
            month3_sales = float(sales_line.month3_sales or 0.0) if sales_line else 0.0
            rows.append((
                product_serial,
                "",
                "",
                destination_store_sql_id,
                stock_by_serial.get(product_serial, 0.0),
                month1_sales,
                month2_sales,
                month3_sales,
                month1_sales + month2_sales + month3_sales,
            ))
        return rows

    def _get_smart_candidate_source_stock_context(self):
        self.ensure_one()
        candidate_products = self._get_smart_candidate_products()
        if not candidate_products:
            return {
                "products_by_serial": {},
                "source_stock_by_serial": {},
            }

        target_products_by_serial = {}
        for product in candidate_products:
            try:
                product_serial = int(product.eplus_serial or 0)
            except (TypeError, ValueError):
                product_serial = 0
            if product_serial and product_serial not in target_products_by_serial:
                target_products_by_serial[product_serial] = product

        if not target_products_by_serial:
            raise UserError(_("Target products must have EPlus serials."))

        source_stock_by_serial = self._get_smart_source_opening_stock_by_product_serial(
            target_products_by_serial
        )
        return {
            "products_by_serial": target_products_by_serial,
            "source_stock_by_serial": source_stock_by_serial,
        }

    def _get_smart_zero_source_stock_products(self, source_stock_context=None):
        self.ensure_one()
        explicit_products = self._get_smart_explicit_zero_source_warning_products()
        if not explicit_products:
            return explicit_products

        source_stock_context = (
            source_stock_context
            or self._get_smart_candidate_source_stock_context()
        )
        products_by_serial = source_stock_context["products_by_serial"]
        source_stock_by_serial = source_stock_context["source_stock_by_serial"]
        explicit_product_ids = set(explicit_products.ids)
        return self.env["ab_product"].browse([
            product.id
            for serial, product in products_by_serial.items()
            if product.id in explicit_product_ids
            and float_compare(
                source_stock_by_serial.get(serial, 0.0),
                0.0,
                precision_digits=3,
            ) <= 0
        ])

    def _get_smart_explicit_zero_source_warning_products(self):
        self.ensure_one()
        return self.target_product_ids | self.smart_product_line_ids.mapped("product_id")

    def _get_smart_zero_source_stock_warning_action(
            self,
            source_stock_context=None,
            smart_wizard=None,
    ):
        self.ensure_one()
        zero_stock_products = self._get_smart_zero_source_stock_products(
            source_stock_context
        )
        if not zero_stock_products:
            return False
        return self.env["ab_transfer_smart_zero_stock_warning"]._open_warning(
            self.from_store_id,
            zero_stock_products,
            header=self if not smart_wizard else None,
            smart_wizard=smart_wizard,
        )

    def _get_smart_target_product_serials_with_source_stock(
            self,
            source_stock_context=None,
    ):
        self.ensure_one()
        source_stock_context = (
            source_stock_context
            or self._get_smart_candidate_source_stock_context()
        )
        target_products_by_serial = source_stock_context["products_by_serial"]
        source_stock_by_serial = source_stock_context["source_stock_by_serial"]
        explicit_product_serials = set(self._get_smart_explicit_product_qty_by_serial())
        return [
            serial
            for serial in target_products_by_serial
            if serial in explicit_product_serials
            or source_stock_by_serial.get(serial, 0.0) > 0.0
        ]

    @api.model
    def _read_smart_active_reserved_qty_by_product_store(
            self,
            product_ids,
            store_ids,
            exclude_header_ids=None,
    ):
        product_ids = [int(product_id) for product_id in product_ids or [] if product_id]
        store_ids = [int(store_id) for store_id in store_ids or [] if store_id]
        if not product_ids or not store_ids:
            return {}

        domain = [
            ("product_id", "in", product_ids),
            ("from_store_id", "in", store_ids),
        ] + self._get_smart_active_reservation_line_domain()
        if exclude_header_ids:
            domain.append(("header_id", "not in", exclude_header_ids))

        groups = self.env["ab_transfer_smart_line"].sudo().read_group(
            domain,
            ["qty:sum"],
            ["product_id", "from_store_id"],
            lazy=False,
        )

        result = {}
        for group in groups:
            product_id = self._group_many2one_id(group.get("product_id"))
            store_id = self._group_many2one_id(group.get("from_store_id"))
            if not product_id or not store_id:
                continue

            result[(product_id, store_id)] = float(group.get("qty", 0.0) or 0.0)
        return result

    @api.model
    def _get_smart_active_reservation_line_domain(self):
        today_start, tomorrow_start = self._get_smart_submitted_today_bounds()
        return [
            ("header_id.active", "=", True),
            ("header_id.smart_stage", "in", list(SMART_EXPECTED_BALANCE_STAGES)),
            ("exclusion_reason", "=", False),
            "|",
            ("header_id.is_submitted", "=", False),
            "&",
            ("header_id.is_submitted", "=", True),
            "&",
            ("header_id.sent_at", ">=", today_start),
            ("header_id.sent_at", "<", tomorrow_start),
        ]

    @api.model
    def _get_smart_submitted_today_bounds(self):
        local_now = fields.Datetime.context_timestamp(self, fields.Datetime.now())
        local_today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
        local_tomorrow_start = local_today_start + timedelta(days=1)
        today_start = local_today_start.astimezone(timezone.utc).replace(tzinfo=None)
        tomorrow_start = local_tomorrow_start.astimezone(timezone.utc).replace(tzinfo=None)
        return fields.Datetime.to_string(today_start), fields.Datetime.to_string(tomorrow_start)

    def _apply_smart_transfer_rows(self, destination_rows):
        self.ensure_one()
        preview_rows, result = self._prepare_smart_transfer_preview_rows(destination_rows)
        existing_lines_by_product = {
            line.product_id.id: line
            for line in self.smart_line_ids
            if line.product_id
        }
        create_vals_list = []

        for preview_row in preview_rows:
            product = preview_row["product"]
            line_vals = dict(preview_row["line_vals"])
            existing_line = existing_lines_by_product.get(product.id)
            if (
                    not preview_row["dropout_excluded"]
                    and existing_line
                    and existing_line.exclusion_reason == "dropout_coverage"
            ):
                line_vals["exclusion_reason"] = False

            if existing_line:
                existing_line.with_context(
                    allow_smart_original_qty_write=True
                ).write(line_vals)
                result["updated"] += 1
            else:
                create_vals_list.append({
                    **line_vals,
                    "header_id": self.id,
                    "product_id": product.id,
                })

        if create_vals_list:
            new_lines = self.env["ab_transfer_smart_line"].create(create_vals_list)
            result["created"] += len(new_lines)

        return result

    def _prepare_smart_transfer_preview_rows(self, destination_rows):
        """Calculate Smart Lines without creating or updating business records."""
        self.ensure_one()
        rows = destination_rows or []
        products_by_serial = self._get_smart_products_by_eplus_serial(rows)
        rows = self._sort_smart_rows_by_product_location(rows, products_by_serial)
        required_context_by_serial = self._get_smart_required_context_by_serial(rows, products_by_serial)
        required_context_by_serial.update(
            self._get_smart_target_default_context_by_serial(
                rows,
                products_by_serial,
                required_context_by_serial,
            )
        )
        required_products_by_serial = {
            serial: products_by_serial[serial]
            for serial in required_context_by_serial
        }
        source_stock_by_serial = self._get_smart_source_opening_stock_by_product_serial(
            required_products_by_serial
        )
        other_branches_context_by_serial = self._get_smart_other_branches_context_by_serial(
            required_products_by_serial
        )
        explicit_product_serials = set(self._get_smart_explicit_product_qty_by_serial())

        result = {
            "created": 0,
            "updated": 0,
            "dropout_excluded": 0,
            "missing": 0,
            "no_stock": 0,
        }
        preview_rows = []

        for row in rows:
            product_serial = self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
            if not product_serial:
                result["missing"] += 1
                _logger.warning("Smart transfer skipped SQL row without EPlus itm_id: %s", row)
                continue

            product = products_by_serial.get(product_serial)
            if not product:
                result["missing"] += 1
                _logger.warning(
                    "Smart transfer skipped missing Odoo product for EPlus itm_id: %s",
                    product_serial,
                )
                continue

            required_context = required_context_by_serial.get(product_serial)
            if not required_context:
                continue

            source_stock_qty = source_stock_by_serial.get(product_serial, 0.0)
            other_branches_context = other_branches_context_by_serial.get(product_serial, {})
            destination_required_qty = required_context["required_qty"]
            other_required_qty = other_branches_context.get("required_qty", 0.0)
            total_required_qty = destination_required_qty + other_required_qty
            manual_requested_qty = required_context.get("manual_requested_qty")
            is_target_default_qty = bool(required_context.get("target_default_qty"))
            if is_target_default_qty:
                computed_transfer_qty = destination_required_qty
            else:
                computed_transfer_qty = self._calculate_smart_distributed_qty(
                    destination_required_qty,
                    other_required_qty,
                    source_stock_qty,
                )
            if manual_requested_qty is not None:
                transfer_required_qty = manual_requested_qty
            else:
                transfer_required_qty = computed_transfer_qty
            if transfer_required_qty <= 0:
                result["no_stock"] += 1
                continue

            prepare_kwargs = {}
            if manual_requested_qty is not None:
                prepare_kwargs["manual_qty"] = manual_requested_qty
            line_vals = self._prepare_smart_line_vals(
                product,
                computed_transfer_qty,
                source_stock_qty,
                required_context["destination_stock_qty"],
                required_context["month1_sales"],
                required_context["month2_sales"],
                required_context["month3_sales"],
                destination_required_qty,
                other_required_qty,
                total_required_qty,
                other_branches_context,
                **prepare_kwargs,
            )
            if not line_vals:
                result["no_stock"] += 1
                continue

            line_vals["source_type"] = (
                SMART_LINE_SOURCE_WIZARD
                if product_serial in explicit_product_serials
                else SMART_LINE_SOURCE_DOMAIN
            )
            dropout_excluded = self._is_smart_dropout_coverage_excluded(
                    required_context["planned_qty"],
                    required_context["destination_stock_qty"],
            )
            if dropout_excluded:
                line_vals["exclusion_reason"] = "dropout_coverage"
                result["dropout_excluded"] += 1

            preview_rows.append({
                "product": product,
                "line_vals": line_vals,
                "dropout_excluded": dropout_excluded,
            })

        return preview_rows, result

    def _get_smart_explicit_product_qty_by_serial(self):
        self.ensure_one()
        qty_by_serial = {}
        for line in self.smart_product_line_ids:
            product_serial = self._get_smart_product_serial(line.product_id)
            if product_serial:
                qty_by_serial[product_serial] = (
                    qty_by_serial.get(product_serial, 0.0)
                    + float(line.qty or 0.0)
                )
        return qty_by_serial

    def _get_smart_target_product_min_qty_by_serial(self):
        self.ensure_one()
        qty_by_serial = {}

        for product in self.target_product_ids:
            product_serial = self._get_smart_product_serial(product)
            if product_serial:
                qty_by_serial[product_serial] = float(product.min_sale_purchase_qty or 1.0)
        return qty_by_serial

    def _get_smart_target_default_context_by_serial(
            self,
            rows,
            products_by_serial,
            existing_context_by_serial,
    ):
        self.ensure_one()
        explicit_qty_by_serial = self._get_smart_explicit_product_qty_by_serial()
        if not explicit_qty_by_serial:
            explicit_qty_by_serial = {}
        target_min_qty_by_serial = self._get_smart_target_product_min_qty_by_serial()
        if not explicit_qty_by_serial and not target_min_qty_by_serial:
            return {}

        rows_by_serial = {
            self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL): row
            for row in rows or []
            if self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
        }
        result = {}
        requested_serials = set(explicit_qty_by_serial) | set(target_min_qty_by_serial)
        for product_serial in requested_serials:
            if (
                    not product_serial
                    or product_serial not in products_by_serial
            ):
                continue
            requested_qty = explicit_qty_by_serial.get(product_serial)
            if requested_qty is not None:
                context = existing_context_by_serial.get(product_serial)
                if context:
                    result[product_serial] = {
                        **context,
                        "manual_requested_qty": requested_qty,
                    }
                    continue

                row = rows_by_serial.get(product_serial)
                context = self._get_smart_required_context_from_row(
                    row,
                    products_by_serial,
                    include_non_positive=True,
                )
                if not context:
                    context = {
                        "planned_qty": 0.0,
                        "required_qty": 0.0,
                        "destination_stock_qty": 0.0,
                        "destination_coverage": 0.0,
                        "month1_sales": 0.0,
                        "month2_sales": 0.0,
                        "month3_sales": 0.0,
                    }
                context["manual_requested_qty"] = requested_qty
                result[product_serial] = context
                continue

            if requested_qty is None:
                if product_serial in existing_context_by_serial:
                    continue
                requested_qty = target_min_qty_by_serial[product_serial]

            row = rows_by_serial.get(product_serial)
            month1_sales = self._smart_row_float(row, SMART_ROW_LAST_MONTH_SALES)
            month2_sales = self._smart_row_float(row, SMART_ROW_PREVIOUS_MONTH_SALES)
            month3_sales = self._smart_row_float(row, SMART_ROW_THIRD_MONTH_SALES)

            result[product_serial] = {
                "planned_qty": requested_qty,
                "required_qty": requested_qty,
                "destination_stock_qty": self._smart_row_float(row, SMART_ROW_BRANCH_STOCK_QTY),
                "destination_coverage": 0.0,
                "month1_sales": month1_sales,
                "month2_sales": month2_sales,
                "month3_sales": month3_sales,
                "target_default_qty": True,
            }
        return result

    def _get_smart_required_context_from_row(
            self,
            row,
            products_by_serial,
            include_non_positive=False,
    ):
        product_serial = self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
        if not product_serial or product_serial not in products_by_serial:
            return {}

        destination_stock_qty = self._smart_row_float(row, SMART_ROW_BRANCH_STOCK_QTY)
        last_month_sales = self._smart_row_float(row, SMART_ROW_LAST_MONTH_SALES)
        previous_month_sales = self._smart_row_float(row, SMART_ROW_PREVIOUS_MONTH_SALES)
        third_month_sales = self._smart_row_float(row, SMART_ROW_THIRD_MONTH_SALES)
        total_3_months_sales = self._smart_row_float(row, SMART_ROW_TOTAL_3_MONTHS_SALES)
        planned_qty = self._calculate_smart_planned_qty(
            total_3_months_sales,
            self.smart_days,
            method=self.smart_stock_method,
            last_month_sales=last_month_sales,
            previous_month_sales=previous_month_sales,
            third_month_sales=third_month_sales,
        )
        required_qty = planned_qty - destination_stock_qty
        if required_qty <= 0:
            if not include_non_positive:
                return {}
            required_qty = 0.0

        return {
            "planned_qty": planned_qty,
            "required_qty": required_qty,
            "destination_stock_qty": destination_stock_qty,
            "destination_coverage": self._calculate_smart_destination_coverage(
                planned_qty,
                destination_stock_qty,
            ),
            "month1_sales": last_month_sales,
            "month2_sales": previous_month_sales,
            "month3_sales": third_month_sales,
        }

    def _get_smart_products_by_eplus_serial(self, rows):
        product_serials = {
            self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
            for row in rows
            if self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
        }
        product_serials.update(self._get_smart_explicit_product_qty_by_serial())
        product_serials.update(self._get_smart_target_product_min_qty_by_serial())
        if not product_serials:
            return {}

        products_by_serial = {}
        for product in self._get_smart_candidate_products():
            try:
                product_serial = int(product.eplus_serial or 0)
            except (TypeError, ValueError):
                product_serial = 0
            if product_serial in product_serials and product_serial not in products_by_serial:
                products_by_serial[product_serial] = product
        return products_by_serial

    @api.model
    def _get_smart_product_serial(self, product):
        try:
            return int(product.eplus_serial or 0)
        except (TypeError, ValueError):
            return 0

    @api.model
    def _get_smart_product_serials(self, products):
        serials = set()
        for product in products:
            product_serial = self._get_smart_product_serial(product)
            if product_serial:
                serials.add(product_serial)
        return serials

    @api.model
    def _smart_product_location_sort_key(self, product):
        location = str(product.location or "").strip() if product else ""
        name = str(product.display_name or product.name or "").strip() if product else ""
        return (
            not bool(location),
            location.casefold(),
            name.casefold(),
        )

    @api.model
    def _sort_smart_lines_by_product_location(self, lines):
        return lines.sorted(
            key=lambda line: self._smart_product_location_sort_key(line.product_id)
        )

    def _sort_smart_rows_by_product_location(self, rows, products_by_serial):
        return sorted(
            rows or [],
            key=lambda row: self._smart_product_location_sort_key(
                products_by_serial.get(self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL))
            ),
        )

    def _get_smart_required_context_by_serial(self, rows, products_by_serial):
        required_context_by_serial = {}
        for row in rows:
            context = self._get_smart_required_context_from_row(row, products_by_serial)
            if not context:
                continue
            product_serial = self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
            required_context_by_serial[product_serial] = context
        return required_context_by_serial

    def _get_smart_other_branches_context_by_serial(self, products_by_serial):
        self.ensure_one()
        branch_sql_ids = self._get_smart_other_branch_store_sql_ids()
        product_serials = [serial for serial in products_by_serial if serial]
        if not branch_sql_ids or not product_serials:
            return {}

        self._validate_smart_sales_cache_coverage()
        store_by_sql_id = self._get_smart_cache_store_by_sql_id(branch_sql_ids)
        store_ids = sorted(store.id for store in store_by_sql_id.values())
        if not store_ids:
            return {}

        periods = self._get_smart_sales_cache_periods()
        month1_sales = self._read_smart_cached_sales(
            store_ids,
            product_serials,
            periods["month1_start"],
            periods["month1_end"],
        )
        month2_sales = self._read_smart_cached_sales(
            store_ids,
            product_serials,
            periods["month2_start"],
            periods["month2_end"],
        )
        month3_sales = self._read_smart_cached_sales(
            store_ids,
            product_serials,
            periods["month3_start"],
            periods["month3_end"],
        )
        stock_by_key = self._read_smart_cached_stock(store_ids, product_serials)

        result = {}
        for product_serial in product_serials:
            for store_id in store_ids:
                key = (product_serial, store_id)
                branch_stock_qty = stock_by_key.get(key, 0.0)
                store_month1_sales = month1_sales.get(key, 0.0)
                store_month2_sales = month2_sales.get(key, 0.0)
                store_month3_sales = month3_sales.get(key, 0.0)
                total_3_months_sales = store_month1_sales + store_month2_sales + store_month3_sales
                branch_need = self._calculate_smart_required_qty(
                    total_3_months_sales,
                    branch_stock_qty,
                    self.smart_days,
                    method=self.smart_stock_method,
                    last_month_sales=store_month1_sales,
                    previous_month_sales=store_month2_sales,
                    third_month_sales=store_month3_sales,
                )
                context = result.setdefault(product_serial, {
                    "required_qty": 0.0,
                    "stock_qty": 0.0,
                    "month1_sales": 0.0,
                    "month2_sales": 0.0,
                    "month3_sales": 0.0,
                })
                context["stock_qty"] += branch_stock_qty
                context["month1_sales"] += store_month1_sales
                context["month2_sales"] += store_month2_sales
                context["month3_sales"] += store_month3_sales
                if branch_need > 0:
                    context["required_qty"] += branch_need
        return result

    def _get_smart_sales_cache_warning_action_if_needed(self):
        self.ensure_one()
        if self.env.context.get("skip_smart_sales_cache_coverage"):
            return False
        if not self._get_smart_other_branch_store_sql_ids():
            return False

        missing_dates = self._get_smart_missing_sales_cache_dates()
        if not missing_dates:
            return False

        message = self._format_smart_sales_cache_warning_message(missing_dates)
        return self._smart_notification(
            _("Smart Transfer Calculation"),
            message,
            "warning",
        )

    def _get_smart_sales_cache_periods(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        month1_end = today - timedelta(days=1)
        month1_start = month1_end - timedelta(days=29)
        month2_end = month1_start - timedelta(days=1)
        month2_start = month2_end - timedelta(days=29)
        month3_end = month2_start - timedelta(days=1)
        month3_start = month3_end - timedelta(days=29)
        return {
            "month1_start": month1_start,
            "month1_end": month1_end,
            "month2_start": month2_start,
            "month2_end": month2_end,
            "month3_start": month3_start,
            "month3_end": month3_end,
            "window_start": month3_start,
            "window_end": month1_end,
        }

    def _get_smart_missing_sales_cache_dates(self):
        self.ensure_one()
        periods = self._get_smart_sales_cache_periods()
        start_date = periods["window_start"]
        end_date = periods["window_end"]
        self.env["ab_sales_per_day"].sudo()._ensure_sync_states(start_date, end_date)
        return self._get_smart_missing_sales_cache_dates_readonly()

    def _get_smart_missing_sales_cache_dates_readonly(self):
        self.ensure_one()
        periods = self._get_smart_sales_cache_periods()
        start_date = periods["window_start"]
        end_date = periods["window_end"]
        states = self.env["ab_sales_per_day_sync_state"].sudo().search([
            ("sale_date", ">=", start_date),
            ("sale_date", "<=", end_date),
            ("state", "=", "done"),
        ])
        done_dates = {
            fields.Date.to_date(value)
            for value in states.mapped("sale_date")
        }
        missing_dates = []
        current = start_date
        while current <= end_date:
            if current not in done_dates:
                missing_dates.append(current)
            current += timedelta(days=1)
        return missing_dates

    @api.model
    def _format_smart_sales_cache_warning_message(self, missing_dates):
        missing_dates = missing_dates or []
        preview = ", ".join(fields.Date.to_string(day) for day in missing_dates[:5])
        if len(missing_dates) > 5:
            preview = _("%s, and %s more") % (preview, len(missing_dates) - 5)
        return _(
            "Smart Transfer sales cache is not ready for other branches. "
            "Missing synced sales days: %s. You can continue for workflow testing, "
            "but smart quantities may be inaccurate."
        ) % preview

    @api.model
    def _format_smart_export_sales_cache_warning_message(self, missing_dates):
        missing_dates = missing_dates or []
        preview = ", ".join(fields.Date.to_string(day) for day in missing_dates[:5])
        if len(missing_dates) > 5:
            preview = _("%s, and %s more") % (preview, len(missing_dates) - 5)
        return _(
            "Smart Transfer sales cache is incomplete. Missing synced sales days: %s. "
            "Choose Cancel Export to stop, or Continue Anyway to export with available "
            "cached sales data. Continuing does not record an acceptance or override."
        ) % preview

    def _validate_smart_sales_cache_coverage(self):
        self.ensure_one()
        if self.env.context.get("smart_export_readonly"):
            missing_dates = self._get_smart_missing_sales_cache_dates_readonly()
        else:
            missing_dates = self._get_smart_missing_sales_cache_dates()
        if missing_dates:
            message = self._format_smart_sales_cache_warning_message(missing_dates)
            if self.env.context.get("skip_smart_sales_cache_coverage"):
                _logger.warning(
                    "Smart transfer sales cache coverage was accepted with missing days: %s",
                    ", ".join(fields.Date.to_string(day) for day in missing_dates[:5]),
                )
                return
            raise UserError(message)

    def _get_smart_cache_store_by_sql_id(self, branch_sql_ids):
        stores = self.env["ab_store"].sudo().search([
            ("eplus_serial", "in", branch_sql_ids),
        ])
        result = {}
        for store in stores:
            try:
                store_sql_id = int(store.eplus_serial or 0)
            except (TypeError, ValueError):
                store_sql_id = 0
            if store_sql_id and store_sql_id in branch_sql_ids:
                result[store_sql_id] = store
        return result

    def _read_smart_cached_sales(self, store_ids, product_serials, start_date, end_date):
        groups = self.env["ab_sales_per_day"].sudo().read_group(
            [
                ("store_id", "in", store_ids),
                ("product_eplus_serial", "in", product_serials),
                ("sale_date", ">=", start_date),
                ("sale_date", "<=", end_date),
            ],
            ["sales_qty:sum"],
            ["product_eplus_serial", "store_id"],
            lazy=False,
        )
        result = {}
        for group in groups:
            product_serial = self._group_int(group.get("product_eplus_serial"))
            store_id = self._group_many2one_id(group.get("store_id"))
            if product_serial and store_id:
                result[(product_serial, store_id)] = float(group.get("sales_qty", 0.0) or 0.0)
        return result

    def _read_smart_cached_stock(self, store_ids, product_serials):
        groups = self.env["ab_sales_inventory"].sudo().read_group(
            [
                ("store_id", "in", store_ids),
                ("product_eplus_serial", "in", product_serials),
            ],
            ["balance:sum"],
            ["product_eplus_serial", "store_id"],
            lazy=False,
        )
        result = {}
        for group in groups:
            product_serial = self._group_int(group.get("product_eplus_serial"))
            store_id = self._group_many2one_id(group.get("store_id"))
            if product_serial and store_id:
                result[(product_serial, store_id)] = float(group.get("balance", 0.0) or 0.0)
        return result

    def _get_smart_other_branch_store_sql_ids(self):
        self.ensure_one()
        branch_stores = self.fair_store_ids
        use_sale_store_fallback = not branch_stores
        if not branch_stores:
            branch_stores = self.env["ab_store"].search([("allow_sale", "=", True)])

        excluded_store_ids = {self.from_store_id.id, self.to_store_id.id}
        excluded_sql_ids = {
            self._get_ref_id(self.from_store_id, _("Source Store")),
            self._get_ref_id(self.to_store_id, _("Destination Store")),
        }
        branch_sql_ids = []
        for store in branch_stores:
            if store.id in excluded_store_ids:
                continue
            if use_sale_store_fallback and store.eplus_serial in (False, None, "", 0):
                continue
            store_sql_id = self._get_ref_id(store, _("Fair Store"))
            if store_sql_id in excluded_sql_ids:
                continue
            branch_sql_ids.append(store_sql_id)
        return sorted(set(branch_sql_ids))

    @staticmethod
    def _get_smart_other_branches_product_chunk_size(branch_sql_ids):
        max_sql_parameters = 1800
        branch_count = len(branch_sql_ids or [])
        if branch_count >= max_sql_parameters:
            raise UserError(_("Too many fair stores are selected for Smart Transfer."))
        return max(1, min(900, max_sql_parameters - branch_count))

    def _get_smart_source_opening_stock_by_product_serial(self, products_by_serial):
        self.ensure_one()
        product_serials = [int(serial) for serial in products_by_serial if serial]
        if not product_serials:
            return {}

        SourceCache = self.env["ab_transfer_smart_source_stock_cache"].sudo()
        stock_by_serial = SourceCache.read_store_cache_rows(
            self.from_store_id,
            product_serials,
        )
        if stock_by_serial or not self.env.context.get("smart_export_readonly"):
            return stock_by_serial

        return self._get_smart_source_stock_by_product_serial(products_by_serial)

    def _get_smart_source_stock_by_product_serial(self, products_by_serial):
        self.ensure_one()
        product_serials = [serial for serial in products_by_serial if serial]
        if not product_serials:
            return {}

        from_store_sql_id = self._get_ref_id(self.from_store_id, _("Source Store"))
        source_stock_by_serial = {}
        with self._get_sql_connection() as conn:
            with conn.cursor() as cursor:
                for chunk in self._smart_chunks(product_serials, 900):
                    placeholders = ", ".join(["?"] * len(chunk))
                    cursor.execute(
                        f"""
                        SELECT
                            ics.itm_id,
                            SUM(
                                CASE
                                    WHEN ISNULL(ic.itm_unit1_unit3, 0) = 0 THEN 0
                                    ELSE ISNULL(ics.itm_qty, 0) / ic.itm_unit1_unit3
                                END
                            ) AS source_stock_qty
                        FROM Item_Class_Store ics
                        INNER JOIN item_catalog ic ON ic.itm_id = ics.itm_id
                        WHERE ics.sto_id = ?
                          AND ics.itm_id IN ({placeholders})
                          AND ISNULL(ic.itm_active, 1) = 1
                        GROUP BY ics.itm_id
                        """,
                        (from_store_sql_id, *chunk),
                    )
                    for row in cursor.fetchall() or []:
                        source_stock_by_serial[int(row[0] or 0)] = float(row[1] or 0.0)
        return source_stock_by_serial

    def _prepare_smart_line_vals(
            self,
            product,
            required_qty,
            source_stock_qty,
            destination_stock_qty,
            month1_sales,
            month2_sales,
            month3_sales,
            destination_required_qty,
            other_required_qty,
            total_required_qty,
            other_branches_context=None,
            manual_qty=None,
    ):
        self.ensure_one()
        if not product.uom_id:
            _logger.warning("Smart transfer skipped product without default UOM: %s", product.display_name)
            return {}

        available_qty = float(source_stock_qty or 0.0)
        original_qty_before_int = min(required_qty, available_qty)
        if manual_qty is None:
            qty_before_int = original_qty_before_int
            if qty_before_int <= 0:
                return {}
            final_qty = self._calculate_smart_integer_qty(qty_before_int)
            final_qty = self._round_smart_qty_to_min_sale_purchase_qty(
                product,
                final_qty,
            )
        else:
            final_qty = float(manual_qty or 0.0)
            qty_before_int = original_qty_before_int
        if final_qty <= 0:
            return {}

        other_branches_context = other_branches_context or {}
        distribution_ratio = self._calculate_smart_distribution_ratio(
            final_qty,
            source_stock_qty,
        )
        vals = {
            "qty": final_qty,
            "uom_id": product.uom_id.id,
            "smart_source_stock_qty": source_stock_qty,
            "smart_qty_before_int": qty_before_int,
            "smart_destination_stock_qty": destination_stock_qty,
            "smart_month1_sales": month1_sales,
            "smart_month2_sales": month2_sales,
            "smart_month3_sales": month3_sales,
            "smart_other_stores_stock_qty": other_branches_context.get("stock_qty", 0.0),
            "smart_other_stores_month1_sales": other_branches_context.get("month1_sales", 0.0),
            "smart_other_stores_month2_sales": other_branches_context.get("month2_sales", 0.0),
            "smart_other_stores_month3_sales": other_branches_context.get("month3_sales", 0.0),
            "smart_need_destination_store": destination_required_qty,
            "smart_need_other_store": other_required_qty,
            "smart_total_need": total_required_qty,
            "smart_distribution_ratio": distribution_ratio,
        }
        if manual_qty is not None:
            vals["smart_original_qty"] = (
                self._calculate_smart_integer_qty(original_qty_before_int)
                if original_qty_before_int > 0
                else 0.0
            )
        return vals

    def _get_smart_source_inventory_rows_by_product(self, products_by_serial):
        self.ensure_one()
        products_by_serial = {
            int(serial): product
            for serial, product in (products_by_serial or {}).items()
            if serial and product
        }
        rows_by_product = {
            product.id: []
            for product in products_by_serial.values()
        }
        if not products_by_serial:
            return rows_by_product

        from_store_sql_id = self._get_ref_id(
            self.from_store_id,
            _("Source Store"),
        )
        try:
            with self._get_sql_connection() as conn:
                with conn.cursor() as cursor:
                    for chunk in self._smart_chunks(
                            list(products_by_serial),
                            900,
                    ):
                        placeholders = ", ".join(["?"] * len(chunk))
                        cursor.execute(
                            f"""
                            SELECT
                                ics.c_id,
                                ics.itm_id,
                                ics.sto_id,
                                ISNULL(ics.sell_price, 0),
                                ISNULL(ics.itm_qty, 0),
                                CASE
                                    WHEN ISNULL(ic.itm_unit1_unit3, 0) = 0 THEN 0
                                    ELSE ISNULL(ics.itm_qty, 0) / ic.itm_unit1_unit3
                                END,
                                ISNULL(ics.pharm_price, 0),
                                ISNULL(ics.sell_tax, 0),
                                ics.itm_expiry_date,
                                ISNULL(ic.itm_purchase_unit, 1),
                                ISNULL(ic.itm_unit1_unit2, 1),
                                ISNULL(ic.itm_unit1_unit3, 1)
                            FROM Item_Class_Store ics
                            INNER JOIN item_catalog ic ON ic.itm_id = ics.itm_id
                            WHERE ics.sto_id = ?
                              AND ics.itm_id IN ({placeholders})
                              AND ISNULL(ics.itm_qty, 0) > 0
                            ORDER BY ics.itm_id, ics.itm_expiry_date, ics.c_id
                            """,
                            (from_store_sql_id, *chunk),
                        )
                        for row in cursor.fetchall() or []:
                            product = products_by_serial.get(int(row[1] or 0))
                            inventory_row = self._prepare_smart_source_inventory_row(
                                row,
                                product,
                            )
                            if product and inventory_row:
                                rows_by_product[product.id].append(inventory_row)
        except Exception:
            _logger.exception(
                "Failed to batch-read Smart Transfer source inventory for store %s",
                self.from_store_id.id,
            )
        return rows_by_product

    def _prepare_smart_source_inventory_row(self, row, product):
        self.ensure_one()
        if not product:
            return {}
        try:
            purchase_unit = int(row[9] or 1)
            unit1_unit2 = int(row[10] or 1)
            unit1_unit3 = int(row[11] or 1)
            if purchase_unit == 2:
                unit_factor = float(unit1_unit2 or 1)
            elif purchase_unit == 3:
                unit_factor = float(unit1_unit3 or 1)
            else:
                unit_factor = 1.0

            qty = float(row[5] or 0.0)
            if qty < 0.01:
                return {}

            pharm_price = float(row[6] or 0.0) * unit_factor
            sell_tax = float(row[7] or 0.0) * unit_factor
            return {
                "store_id": self.from_store_id.id,
                "store_eplus_serial": int(row[2] or 0),
                "product_id": product.id,
                "product_eplus_serial": int(row[1] or 0),
                "qty": qty,
                "qty_in_small_unit": float(row[4] or 0.0),
                "price": float(row[3] or 0.0) * unit_factor,
                "cost": pharm_price,
                "sell_tax": sell_tax,
                "pharm_price": pharm_price,
                "source_id": int(row[0] or 0),
                "exp_date": str(row[8] or ""),
            }
        except Exception:
            return {}

    def _get_source_inventory_rows(self, product):
        self.ensure_one()
        rows_cache = self.env.context.get(
            "smart_source_inventory_rows_cache"
        )
        products_by_serial = self.env.context.get(
            "smart_source_inventory_products_by_serial"
        )
        if isinstance(rows_cache, dict) and isinstance(products_by_serial, dict):
            if product.id not in rows_cache:
                rows_cache.update(
                    self._get_smart_source_inventory_rows_by_product(
                        products_by_serial
                    )
                )
            return rows_cache.get(product.id, [])

        product_serial = self._get_smart_product_serial(product)
        if not product_serial:
            return []
        rows_by_product = self._get_smart_source_inventory_rows_by_product({
            product_serial: product,
        })
        return rows_by_product.get(product.id, [])

    def _select_smart_source_row(self, source_rows, required_qty):
        rows = source_rows or []
        if not rows:
            return {}
        for row in rows:
            if self._dict_float(row, "qty") >= required_qty:
                return row
        return max(rows, key=lambda row: self._dict_float(row, "qty"))

    def _apply_smart_dropout_coverage_to_lines(self):
        self.ensure_one()
        result = {
            "excluded": 0,
            "cleared": 0,
            "manual_kept": 0,
        }
        for line in self.smart_line_ids:
            planned_qty = self._calculate_smart_line_planned_qty(line)
            should_exclude = self._is_smart_dropout_coverage_excluded(
                planned_qty,
                line.smart_destination_stock_qty,
            )
            if should_exclude:
                if not line.exclusion_reason:
                    line.write({"exclusion_reason": "dropout_coverage"})
                    result["excluded"] += 1
                elif line.exclusion_reason != "dropout_coverage":
                    result["manual_kept"] += 1
                continue

            if line.exclusion_reason == "dropout_coverage":
                line.write({"exclusion_reason": False})
                result["cleared"] += 1
        return result

    def _calculate_smart_line_planned_qty(self, smart_line):
        self.ensure_one()
        total_3_months_sales = (
            float(smart_line.smart_month1_sales or 0.0)
            + float(smart_line.smart_month2_sales or 0.0)
            + float(smart_line.smart_month3_sales or 0.0)
        )
        return self._calculate_smart_planned_qty(
            total_3_months_sales,
            self.smart_days,
            method=self.smart_stock_method,
            last_month_sales=smart_line.smart_month1_sales,
            previous_month_sales=smart_line.smart_month2_sales,
            third_month_sales=smart_line.smart_month3_sales,
        )

    def _get_smart_dropout_coverage(self):
        self.ensure_one()
        context_coverage = self.env.context.get("smart_dropout_coverage")
        if context_coverage is not None:
            try:
                return float(context_coverage or 0.0)
            except (TypeError, ValueError):
                return 0.0
        return float(self.smart_dropout_coverage or 0.0)

    def _is_smart_dropout_coverage_excluded(self, planned_qty, destination_stock_qty):
        self.ensure_one()
        dropout_coverage = self._get_smart_dropout_coverage()
        if dropout_coverage <= 0.0:
            return False
        return self._calculate_smart_destination_coverage(
            planned_qty,
            destination_stock_qty,
        ) >= dropout_coverage

    @api.model
    def _calculate_smart_destination_coverage(self, planned_qty, destination_stock_qty):
        planned_qty = float(planned_qty or 0.0)
        if planned_qty <= 0.0:
            return 0.0
        return (float(destination_stock_qty or 0.0) / planned_qty) * 100.0

    @api.model
    def _calculate_smart_required_qty(
            self,
            total_3_months_sales,
            branch_stock_qty,
            smart_days,
            method=SMART_STOCK_METHOD_NORMAL,
            last_month_sales=0.0,
            previous_month_sales=0.0,
            third_month_sales=0.0,
    ):
        planned_qty = self._calculate_smart_planned_qty(
            total_3_months_sales=total_3_months_sales,
            smart_days=smart_days,
            method=method,
            last_month_sales=last_month_sales,
            previous_month_sales=previous_month_sales,
            third_month_sales=third_month_sales,
        )
        return planned_qty - float(branch_stock_qty or 0.0)

    @api.model
    def _calculate_smart_distributed_qty(
            self,
            destination_required_qty,
            other_branches_required_qty,
            source_stock_qty,
    ):
        destination_required_qty = max(float(destination_required_qty or 0.0), 0.0)
        other_branches_required_qty = max(float(other_branches_required_qty or 0.0), 0.0)
        source_stock_qty = max(float(source_stock_qty or 0.0), 0.0)
        if destination_required_qty <= 0.0 or source_stock_qty <= 0.0:
            return 0.0

        total_required_qty = destination_required_qty + other_branches_required_qty
        if source_stock_qty >= total_required_qty:
            return destination_required_qty

        return destination_required_qty * (source_stock_qty / total_required_qty)

    @api.model
    def _calculate_smart_integer_qty(self, qty):
        qty = max(float(qty or 0.0), 0.0)
        if 0.0 < qty < 1.0:
            return 1
        return int(qty)

    @api.model
    def _round_smart_qty_to_min_sale_purchase_qty(self, product, qty):
        min_qty = float(product.min_sale_purchase_qty or 1.0)
        qty = float(qty or 0.0)
        if min_qty <= 1.0 or qty <= 0.0:
            return qty
        return math.ceil(qty / min_qty) * min_qty

    @api.model
    def _calculate_smart_distribution_ratio(
            self,
            qty,
            source_stock_qty,
    ):
        qty = max(float(qty or 0.0), 0.0)
        source_stock_qty = max(float(source_stock_qty or 0.0), 0.0)
        if source_stock_qty <= 0.0:
            return 0.0

        return qty / source_stock_qty

    @api.model
    def _calculate_smart_planned_qty(
            self,
            total_3_months_sales,
            smart_days,
            method=SMART_STOCK_METHOD_NORMAL,
            last_month_sales=0.0,
            previous_month_sales=0.0,
            third_month_sales=0.0,
    ):
        smart_days = float(smart_days or 0.0)
        if method == SMART_STOCK_METHOD_WEIGHTED:
            weighted_monthly_sales = self._calculate_smart_weighted_monthly_sales(
                last_month_sales,
                previous_month_sales,
                third_month_sales,
            )
            avg_daily_sales = weighted_monthly_sales / SMART_WEIGHTED_PERIOD_DAYS
            return avg_daily_sales * smart_days

        avg_daily_sales = float(total_3_months_sales or 0.0) / SMART_NORMAL_PERIOD_DAYS
        return avg_daily_sales * smart_days

    @api.model
    def _calculate_smart_weighted_monthly_sales(
            self,
            last_month_sales,
            previous_month_sales,
            third_month_sales,
    ):
        return (
                (float(last_month_sales or 0.0) * SMART_WEIGHT_LAST_MONTH)
                + (float(previous_month_sales or 0.0) * SMART_WEIGHT_PREVIOUS_MONTH)
                + (float(third_month_sales or 0.0) * SMART_WEIGHT_THIRD_MONTH)
        )

    @api.model
    def _get_smart_stock_method_help(self, method):
        if method == SMART_STOCK_METHOD_WEIGHTED:
            return _(
                "Weighted method: last month 50%, previous month 30%, third month 20%. "
                "The weighted month is divided by 30 and multiplied by Smart Days."
            )
        return _(
            "Normal method: total sales for the last 3 months is divided by 90 and "
            "multiplied by Smart Days."
        )

    @staticmethod
    def _smart_row_text(row, index):
        try:
            value = row[index]
        except (IndexError, TypeError):
            return ""
        return str(value or "").strip()

    @staticmethod
    def _smart_row_float(row, index):
        try:
            value = row[index]
        except (IndexError, TypeError):
            return 0.0
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _smart_row_int(row, index):
        try:
            value = row[index]
        except (IndexError, TypeError):
            return 0
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _group_int(value):
        try:
            if isinstance(value, (list, tuple)):
                value = value[0]
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _group_many2one_id(value):
        if isinstance(value, (list, tuple)) and value:
            try:
                return int(value[0] or 0)
            except (TypeError, ValueError):
                return 0
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _dict_float(values, key):
        try:
            return float((values or {}).get(key) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _smart_chunks(values, size):
        for index in range(0, len(values), size):
            yield values[index:index + size]

    @staticmethod
    def _smart_soft_reload_action():
        return {
            "type": "ir.actions.client",
            "tag": "soft_reload",
        }

    @staticmethod
    def _smart_notification(title, message, notification_type, next_action=None):
        action = {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
        if next_action:
            action["params"]["next"] = next_action
        return action
