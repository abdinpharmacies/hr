# -*- coding: utf-8 -*-
import ast
import logging
from datetime import timedelta

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
SMART_EXPECTED_BALANCE_STAGES = (
    SMART_STAGE_STORE_PREPARATION,
    SMART_STAGE_STORE_REVISION,
    SMART_STAGE_PRE_SUBMIT,
)
SMART_GROUP_PURCHASE = "ab_transfer_smart.group_transfer_smart_purchase"
SMART_GROUP_STORE_PREPARATION = "ab_transfer_smart.group_trnasfer_smart_store_preparation"
SMART_GROUP_STORE_REVISION = "ab_transfer_smart.group_trnasfer_smart_store_revision"
SMART_GROUP_STORE_MANAGER = "ab_transfer_smart.group_trnasfer_smart_store_manager"
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
            (SMART_STOCK_METHOD_WEIGHTED, "طريقة الوزن"),
            (SMART_STOCK_METHOD_NORMAL, "الطريقة العادية"),
        ],
        string="Stock Calculation Method",
        default=SMART_STOCK_METHOD_WEIGHTED,
        required=True,
        help=(
            "طريقة الوزن: (آخر شهر × 50%) + (الشهر السابق × 30%) + "
            "(الشهر الثالث × 20%) ثم القسمة على 30 وضرب Smart Days. "
            "الطريقة العادية: إجمالي مبيعات آخر 3 شهور ÷ 90 × Smart Days. "
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

    def action_clear_target_products(self):
        for rec in self:
            if rec.is_submitted:
                raise UserError(_("Submitted transfers cannot be edited."))
            rec.target_product_ids = [(5, 0, 0)]
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

    def get_smart_report_sorted_lines(self, lines):
        self.ensure_one()
        return self._sort_smart_lines_by_product_location(lines)

    def get_smart_report_transfer_date_text(self):
        self.ensure_one()
        transfer_date = self.sent_at or self.create_date
        return self._format_smart_report_datetime(transfer_date)

    def get_smart_report_printing_date_text(self):
        self.ensure_one()
        return self._format_smart_report_datetime(fields.Datetime.now())

    def _format_smart_report_datetime(self, value):
        return format_datetime(
            self.env,
            value,
            dt_format="yyyy-MM-dd HH:mm",
        ) if value else ""

    def action_open_smart_transfer_wizard(self):
        self.ensure_one()
        self._check_smart_group(SMART_GROUP_PURCHASE)
        self._check_smart_stage(SMART_STAGE_PURCHASE_PREPARATION)
        self._check_smart_not_submitted()
        wizard = self.env["ab_transfer_smart_wizard"].create(
            self._prepare_smart_transfer_wizard_vals()
        )
        return wizard._reopen_wizard_action()

    def _prepare_smart_transfer_wizard_vals(self):
        self.ensure_one()
        return {
            "target_mode": "batch",
            "source_header_id": self.id,
            "from_store_id": self.from_store_id.id,
            "to_stores_id": [(6, 0, self.to_store_id.ids)],
            "user_id": self.user_id.id,
            "notes": self.notes,
            "company_id": self.company_id.id,
            "target_product_ids": [(6, 0, self.target_product_ids.ids)],
            "fair_store_ids": [(6, 0, self.fair_store_ids.ids)],
            "smart_product_domain": self.smart_product_domain or "[]",
            "smart_days": self.smart_days,
            "smart_stock_method": self.smart_stock_method,
            "dropout_coverage": self.smart_dropout_coverage,
        }

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

            destination_rows = self._fetch_destination_smart_rows()
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
        self._validate_smart_source_stock_available(
            self.smart_line_ids.filtered(lambda line: not line.exclusion_reason)
        )
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
        if not self.is_submitted:
            self._check_smart_group(SMART_GROUP_STORE_REVISION)
            self._check_smart_stage(SMART_STAGE_PRE_SUBMIT)

        previous_stage = self.smart_stage
        if not self.is_submitted and self.smart_stage != SMART_STAGE_SUBMIT:
            self.write({"smart_stage": SMART_STAGE_SUBMIT})

        try:
            result = super().action_submit()
            return self._smart_soft_reload_action() if result is True else result
        except Exception:
            if not self.is_submitted and self.smart_stage != previous_stage:
                self.write({"smart_stage": previous_stage})
            raise

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
        domain_products = Product.browse()
        if not product_domain.is_true():
            try:
                domain_products = Product.search(product_domain)
            except Exception:
                raise UserError(_("Invalid product filter. Please review the filter conditions."))

        products = domain_products | self.target_product_ids
        if not products:
            raise UserError(_("Please add target products or set a product filter."))
        return products

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

    def _fetch_destination_smart_rows(self):
        self.ensure_one()
        destination_store_sql_id = self._get_smart_destination_store_sql_id()
        product_serials = self._get_smart_target_product_serials_with_source_stock()
        if not product_serials:
            return []

        self._ensure_smart_destination_cache()
        return self._read_smart_destination_cache_rows(
            product_serials,
            destination_store_sql_id,
        )

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

    def _get_smart_target_product_serials_with_source_stock(self):
        self.ensure_one()
        product_serials = []
        target_products_by_serial = {}
        for product in self._get_smart_candidate_products():
            try:
                product_serial = int(product.eplus_serial or 0)
            except (TypeError, ValueError):
                product_serial = 0
            if product_serial and product_serial not in target_products_by_serial:
                product_serials.append(product_serial)
                target_products_by_serial[product_serial] = product

        if not product_serials:
            raise UserError(_("Target products must have EPlus serials."))

        source_stock_by_serial = self._get_smart_source_stock_by_product_serial(target_products_by_serial)
        return [
            serial
            for serial in product_serials
            if source_stock_by_serial.get(serial, 0.0) > 0.0
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
            ("header_id.active", "=", True),
            ("header_id.smart_stage", "in", list(SMART_EXPECTED_BALANCE_STAGES)),
            ("header_id.is_submitted", "=", False),
            ("exclusion_reason", "=", False),
            ("product_id", "in", product_ids),
            ("from_store_id", "in", store_ids),
        ]
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

    def _apply_smart_transfer_rows(self, destination_rows):
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
        source_stock_by_serial = self._get_smart_source_stock_by_product_serial(required_products_by_serial)
        other_branches_context_by_serial = self._get_smart_other_branches_context_by_serial(
            required_products_by_serial
        )
        existing_lines_by_product = {
            line.product_id.id: line
            for line in self.smart_line_ids
            if line.product_id
        }

        result = {
            "created": 0,
            "updated": 0,
            "dropout_excluded": 0,
            "missing": 0,
            "no_stock": 0,
        }

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
            is_target_default_qty = bool(required_context.get("target_default_qty"))
            if is_target_default_qty:
                transfer_required_qty = destination_required_qty
            else:
                transfer_required_qty = self._calculate_smart_distributed_qty(
                    destination_required_qty,
                    other_required_qty,
                    source_stock_qty,
                )
            if transfer_required_qty <= 0:
                result["no_stock"] += 1
                continue

            line_vals = self._prepare_smart_line_vals(
                product,
                transfer_required_qty,
                source_stock_qty,
                required_context["destination_stock_qty"],
                required_context["month1_sales"],
                required_context["month2_sales"],
                required_context["month3_sales"],
                destination_required_qty,
                other_required_qty,
                total_required_qty,
                other_branches_context,
            )
            if not line_vals:
                result["no_stock"] += 1
                continue

            existing_line = existing_lines_by_product.get(product.id)
            if self._is_smart_dropout_coverage_excluded(
                    required_context["planned_qty"],
                    required_context["destination_stock_qty"],
            ):
                line_vals["exclusion_reason"] = "dropout_coverage"
                result["dropout_excluded"] += 1
            elif existing_line and existing_line.exclusion_reason == "dropout_coverage":
                line_vals["exclusion_reason"] = False

            if existing_line:
                existing_line.write(line_vals)
                result["updated"] += 1
            else:
                new_line = self.env["ab_transfer_smart_line"].create({
                    **line_vals,
                    "header_id": self.id,
                    "product_id": product.id,
                })
                existing_lines_by_product[product.id] = new_line
                result["created"] += 1

        return result

    def _get_smart_target_default_context_by_serial(
            self,
            rows,
            products_by_serial,
            existing_context_by_serial,
    ):
        self.ensure_one()
        target_serials = self._get_smart_product_serials(self.target_product_ids)
        if not target_serials:
            return {}

        rows_by_serial = {
            self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL): row
            for row in rows or []
            if self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
        }
        result = {}
        for product_serial in target_serials:
            if (
                    not product_serial
                    or product_serial in existing_context_by_serial
                    or product_serial not in products_by_serial
            ):
                continue

            row = rows_by_serial.get(product_serial)
            month1_sales = self._smart_row_float(row, SMART_ROW_LAST_MONTH_SALES)
            month2_sales = self._smart_row_float(row, SMART_ROW_PREVIOUS_MONTH_SALES)
            month3_sales = self._smart_row_float(row, SMART_ROW_THIRD_MONTH_SALES)

            result[product_serial] = {
                "planned_qty": 0.0,
                "required_qty": 1.0,
                "destination_stock_qty": self._smart_row_float(row, SMART_ROW_BRANCH_STOCK_QTY),
                "destination_coverage": 0.0,
                "month1_sales": month1_sales,
                "month2_sales": month2_sales,
                "month3_sales": month3_sales,
                "target_default_qty": True,
            }
        return result

    def _get_smart_products_by_eplus_serial(self, rows):
        product_serials = {
            self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
            for row in rows
            if self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
        }
        product_serials.update(self._get_smart_product_serials(self.target_product_ids))
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
            product_serial = self._smart_row_int(row, SMART_ROW_PRODUCT_SERIAL)
            if not product_serial or product_serial not in products_by_serial:
                continue

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
                continue

            required_context_by_serial[product_serial] = {
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
        wizard = self.env["ab_transfer_smart_wizard"].create({
            **self._prepare_smart_transfer_wizard_vals(),
            "target_mode": "single",
            "to_stores_id": [(6, 0, self.to_store_id.ids)],
            "allow_incomplete_sales_cache": False,
            "sales_cache_warning_message": message,
            "sales_cache_missing_days_count": len(missing_dates),
        })
        return wizard._reopen_wizard_action()

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

    def _validate_smart_sales_cache_coverage(self):
        self.ensure_one()
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
    ):
        self.ensure_one()
        if not product.uom_id:
            _logger.warning("Smart transfer skipped product without default UOM: %s", product.display_name)
            return {}

        source_rows = self._get_source_inventory_rows(product)
        selected = self._select_smart_source_row(source_rows, required_qty)
        if not selected:
            _logger.warning("Smart transfer skipped product without source stock: %s", product.display_name)
            return {}

        available_qty = float(source_stock_qty or 0.0)
        qty_before_int = min(required_qty, available_qty)
        if qty_before_int <= 0:
            return {}

        final_qty = self._calculate_smart_integer_qty(qty_before_int)
        if final_qty <= 0:
            return {}

        source_id = int(selected.get("source_id") or 0)
        expiry_date = str(selected.get("exp_date") or "").split(" ")[0]
        if not source_id or not expiry_date:
            _logger.warning(
                "Smart transfer skipped product with incomplete source row: product=%s source=%s expiry=%s",
                product.display_name,
                source_id,
                expiry_date,
            )
            return {}

        other_branches_context = other_branches_context or {}
        distribution_ratio = self._calculate_smart_distribution_ratio(
            final_qty,
            source_stock_qty,
        )
        return {
            "qty": final_qty,
            "expiry_date": expiry_date,
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

    def _get_source_inventory_rows(self, product):
        self.ensure_one()
        line = self.env["ab_transfer_smart_line"].new({
            "header_id": self.id,
            "product_id": product.id,
            "uom_id": product.uom_id.id if product.uom_id else False,
        })
        line._recompute_inventory_json()
        return [
            row
            for row in line._get_inventory_rows()
            if self._dict_float(row, "qty") > 0
        ]

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
            weighted_monthly_sales = (
                    (float(last_month_sales or 0.0) * SMART_WEIGHT_LAST_MONTH)
                    + (float(previous_month_sales or 0.0) * SMART_WEIGHT_PREVIOUS_MONTH)
                    + (float(third_month_sales or 0.0) * SMART_WEIGHT_THIRD_MONTH)
            )
            avg_daily_sales = weighted_monthly_sales / SMART_WEIGHTED_PERIOD_DAYS
            return avg_daily_sales * smart_days

        avg_daily_sales = float(total_3_months_sales or 0.0) / SMART_NORMAL_PERIOD_DAYS
        return avg_daily_sales * smart_days

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
