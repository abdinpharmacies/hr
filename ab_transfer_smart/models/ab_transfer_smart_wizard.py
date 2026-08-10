# -*- coding: utf-8 -*-

import re
import io
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

SMART_GROUP_PURCHASE = "ab_transfer_smart.group_transfer_smart_purchase"
SMART_STAGE_PURCHASE_PREPARATION = "purchase_preparation"
SMART_LINE_SOURCE_WIZARD = "wizard"
MAX_PRODUCT_IMPORT_LINES = 1000


class AbTransferSmartWizard(models.Model):
    _name = "ab_transfer_smart_wizard"
    _description = "Smart Transfer Wizard"
    _order = "id desc"
    _rec_name = "display_name"

    display_name = fields.Char(
        string="Name",
        compute="_compute_display_name",
    )
    target_mode = fields.Selection(
        selection=[
            ("batch", "Batch"),
            ("single", "Single Transfer"),
        ],
        default="batch",
        required=True,
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("done", "Done"),
        ],
        default="draft",
        required=True,
        copy=False,
    )
    active = fields.Boolean(
        default=True,
        index=True,
    )
    source_header_id = fields.Many2one(
        "ab_transfer_header",
        string="Source Transfer",
        copy=False,
        ondelete="set null",
    )
    from_store_id = fields.Many2one(
        "ab_store",
        string="From Store",
        domain=lambda self: self._get_allowed_source_store_domain(),
        default=lambda self: self._default_from_store_id(),
        required=True,
    )
    to_stores_id = fields.Many2many(
        "ab_store",
        "ab_transfer_smart_wizard_to_store_rel",
        "wizard_id",
        "store_id",
        string="To Stores",
        required=True,
    )
    user_id = fields.Many2one(
        "ab_costcenter",
        string="User",
        default=lambda self: self._default_user_id(),
        required=True,
        readonly=True,
    )
    notes = fields.Char(
        string="Notes",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )
    target_product_ids = fields.Many2many(
        "ab_product",
        "ab_transfer_smart_wizard_product_rel",
        "wizard_id",
        "product_id",
        string="Target Products",
    )
    product_line_ids = fields.One2many(
        "ab_transfer_smart_product_line",
        "wizard_id",
        string="Products",
        copy=False,
    )
    product_import_text = fields.Text(
        string="Paste Products",
        copy=False,
        help="Paste product code and quantity from Excel, one product per line.",
    )
    fair_store_ids = fields.Many2many(
        "ab_store",
        "ab_transfer_smart_wizard_fair_store_rel",
        "wizard_id",
        "store_id",
        string="Fair Stores",
    )
    smart_product_domain = fields.Char(
        string="Product Filter",
        default="[]",
    )
    smart_days = fields.Integer(
        string="Smart Days",
        default=60,
        required=True,
    )
    smart_stock_method = fields.Selection(
        selection=[
            ("weighted", "Weighted Method"),
            ("normal", "Normal Method"),
        ],
        string="Stock Calculation Method",
        default="weighted",
        required=True,
    )
    dropout_coverage = fields.Integer(
        string="Dropout Coverage %",
        default=0,
        help="Exclude smart lines when destination stock covers this percentage of the planned quantity.",
    )
    items_per_header = fields.Integer(
        string="Items Per Header",
        default=40,
        required=True,
        copy=False,
        help="Maximum generated smart item lines per transfer header.",
    )
    allow_incomplete_sales_cache = fields.Boolean(
        string="Continue Without Complete Sales Cache",
        copy=False,
    )
    sales_cache_warning_message = fields.Text(
        string="Sales Cache Warning",
        copy=False,
        readonly=True,
    )
    sales_cache_missing_days_count = fields.Integer(
        string="Missing Sales Cache Days",
        copy=False,
        readonly=True,
    )
    sales_cache_warning_accepted_by = fields.Many2one(
        "res.users",
        string="Warning Accepted By",
        copy=False,
        readonly=True,
    )
    sales_cache_warning_accepted_at = fields.Datetime(
        string="Warning Accepted At",
        copy=False,
        readonly=True,
    )
    smart_export_sales_cache_warning_message = fields.Text(
        string="Export Sales Cache Warning",
        compute="_compute_smart_export_sales_cache_warning_message",
        readonly=True,
    )
    generated_header_ids = fields.One2many(
        "ab_transfer_header",
        "smart_wizard_id",
        string="Generated Transfers",
        copy=False,
    )
    generated_header_count = fields.Integer(
        string="Generated Transfers",
        compute="_compute_generated_header_count",
    )

    @api.depends("source_header_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.source_header_id:
                rec.display_name = _("Smart Wizard for %s") % rec.source_header_id.display_name
            elif rec.id:
                rec.display_name = _("Smart Wizard %s") % rec.id
            else:
                rec.display_name = _("New Smart Wizard")

    @api.depends("generated_header_ids")
    def _compute_generated_header_count(self):
        for rec in self:
            rec.generated_header_count = len(rec.generated_header_ids)

    def _compute_smart_export_sales_cache_warning_message(self):
        Header = self.env["ab_transfer_header"]
        for rec in self:
            missing_dates = rec._get_smart_export_missing_sales_cache_dates_readonly()
            rec.smart_export_sales_cache_warning_message = (
                Header._format_smart_export_sales_cache_warning_message(missing_dates)
                if missing_dates
                else False
            )

    @api.model
    def _get_allowed_source_store_ids(self):
        return self.env["ab_transfer_header"]._get_allowed_source_store_ids()

    @api.model
    def _get_allowed_source_store_domain(self):
        return self.env["ab_transfer_header"]._get_allowed_source_store_domain()

    @api.model
    def _default_from_store_id(self):
        return self.env["ab_transfer_header"]._default_from_store_id()

    @api.model
    def _default_user_id(self):
        return self.env["ab_transfer_header"]._default_user_id()

    @api.constrains("dropout_coverage")
    def _check_dropout_coverage(self):
        for rec in self:
            if rec.dropout_coverage < 0 or rec.dropout_coverage > 100:
                raise ValidationError(_("Dropout coverage must be between 0 and 100."))

    @api.constrains("items_per_header")
    def _check_items_per_header(self):
        for rec in self:
            if rec.items_per_header < 1:
                raise ValidationError(_("Items per header must be at least 1."))

    @api.constrains("product_line_ids")
    def _check_product_line_limit(self):
        for rec in self:
            if len(rec.product_line_ids) > 1000:
                raise ValidationError(_("Smart product lines are limited to 1000 products."))

    @api.constrains("product_line_ids", "product_line_ids.product_id")
    def _check_unique_product_lines(self):
        for rec in self:
            rec._ensure_unique_product_lines()

    @api.onchange("product_line_ids", "product_line_ids.product_id")
    def _onchange_unique_product_lines(self):
        for rec in self:
            rec._ensure_unique_product_lines()

    def _ensure_unique_product_lines(self):
        self.ensure_one()
        product_ids = self.product_line_ids.mapped("product_id").ids
        if len(product_ids) != len(set(product_ids)):
            raise ValidationError(
                _("Each product can be added once only. Update the existing line quantity instead.")
            )

    @api.constrains("from_store_id", "to_stores_id")
    def _check_to_stores(self):
        for rec in self:
            if rec.from_store_id and rec.from_store_id in rec.to_stores_id:
                raise ValidationError(_("Source store cannot be one of the destination stores."))

    def action_generate_transfers(self):
        self.ensure_one()
        self._validate_generation_values()
        self._ensure_smart_destination_caches()
        warning_action = self._get_sales_cache_warning_action()
        if warning_action:
            return warning_action
        validation_error_action = self._get_calculation_validation_error_action()
        if validation_error_action:
            return validation_error_action

        if self.target_mode == "single":
            return self._action_run_single_header_calculation()
        return self._action_generate_batch_transfers()

    def action_export_excel(self):
        self.ensure_one()
        self._validate_smart_export_values()
        missing_dates = self._get_smart_export_missing_sales_cache_dates_readonly()
        if missing_dates:
            warning_view = self.env.ref(
                "ab_transfer_smart.ab_transfer_smart_wizard_export_warning_view_form"
            )
            return {
                "type": "ir.actions.act_window",
                "name": _("Smart Transfer Excel Export"),
                "res_model": "ab_transfer_smart_wizard",
                "res_id": self.id,
                "view_mode": "form",
                "views": [(warning_view.id, "form")],
                "target": "new",
                "context": dict(self.env.context, smart_export_readonly=True),
            }
        return self._get_smart_export_excel_report_action(
            allow_incomplete_sales_cache=False
        )

    def action_export_excel_continue(self):
        self.ensure_one()
        self._validate_smart_export_values()
        return self._get_smart_export_excel_report_action(
            allow_incomplete_sales_cache=True
        )

    def _get_smart_export_excel_report_action(self, allow_incomplete_sales_cache):
        self.ensure_one()
        report = self.env.ref(
            "ab_transfer_smart.action_report_ab_transfer_smart_wizard_xlsx"
        )
        return report.with_context(
            smart_export_readonly=True,
            skip_smart_sales_cache_coverage=bool(allow_incomplete_sales_cache),
        ).report_action(
            self,
            data={
                "allow_incomplete_sales_cache": bool(allow_incomplete_sales_cache),
            },
            config=False,
        )

    def _validate_smart_export_values(self):
        self.ensure_one()
        self._validate_generation_values()
        for probe in self._get_smart_export_probe_headers():
            probe._validate_smart_transfer_header()

    def _prepare_smart_export_header_probe_vals(self, destination):
        self.ensure_one()
        return {
            **self._prepare_header_probe_vals(destination),
            "smart_dropout_coverage": self.dropout_coverage,
        }

    def _get_smart_export_probe_headers(self):
        self.ensure_one()
        Header = self.env["ab_transfer_header"]
        return [
            Header.new(self._prepare_smart_export_header_probe_vals(destination))
            for destination in self.to_stores_id
        ]

    def _get_smart_export_missing_sales_cache_dates_readonly(self):
        self.ensure_one()
        missing_dates = set()
        for probe in self._get_smart_export_probe_headers():
            if not probe._get_smart_other_branch_store_sql_ids():
                continue
            missing_dates.update(
                probe._get_smart_missing_sales_cache_dates_readonly()
            )
        return sorted(missing_dates)

    def action_accept_sales_cache_warning_and_generate(self):
        self.ensure_one()
        self.write({
            "allow_incomplete_sales_cache": True,
            "sales_cache_warning_accepted_by": self.env.user.id,
            "sales_cache_warning_accepted_at": fields.Datetime.now(),
        })
        return self.action_generate_transfers()

    def action_refresh_sales_cache_and_generate(self):
        self.ensure_one()
        if not self.env.user.has_group(SMART_GROUP_PURCHASE):
            raise AccessError(_("You are not allowed to refresh smart transfer cache."))

        self._validate_generation_values()
        missing_dates = self._get_missing_sales_cache_dates_for_destinations()
        SalesPerDay = self.env["ab_sales_per_day"].sudo()
        for sale_date in missing_dates:
            SalesPerDay.cron_sync_next_sales_day(
                start_date=sale_date,
                end_date=sale_date,
                force_resync=False,
            )

        remaining_dates = self._get_missing_sales_cache_dates_for_destinations()
        if remaining_dates:
            message = self.env["ab_transfer_header"]._format_smart_sales_cache_warning_message(
                remaining_dates
            )
            message += "\n\n" + _(
                "Sales cache refresh did not complete all required days. "
                "Check EPlus connectivity or retry the refresh."
            )
            self.write({
                "allow_incomplete_sales_cache": False,
                "sales_cache_warning_message": message,
                "sales_cache_missing_days_count": len(remaining_dates),
                "sales_cache_warning_accepted_by": False,
                "sales_cache_warning_accepted_at": False,
            })
            return self._reopen_wizard_action()

        self.write({
            "allow_incomplete_sales_cache": False,
            "sales_cache_warning_message": False,
            "sales_cache_missing_days_count": 0,
            "sales_cache_warning_accepted_by": False,
            "sales_cache_warning_accepted_at": False,
        })
        return self.action_generate_transfers()

    def action_open_generated_transfers(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Smart Transfers"),
            "res_model": "ab_transfer_header",
            "view_mode": "list,form",
            "domain": [("id", "in", self.generated_header_ids.ids)],
            "context": {"create": False},
        }

    def action_import_product_lines(self):
        self.ensure_one()
        if self.state == "done":
            raise UserError(_("Done wizards cannot import products."))
        imported, truncated = self._parse_product_import_text()
        if not imported:
            raise UserError(_("Paste product code and quantity before adding products."))

        created, updated = self._add_imported_product_lines(imported)

        self.product_import_text = False
        message = _(
            "Product lines added. Created: %(created)s, Updated: %(updated)s."
        ) % {"created": created, "updated": updated}
        notification_type = "success"
        if truncated:
            message = _(
                "Only 1000 product lines are allowed. Extra lines have been ignored."
            ) + "\n" + message
            notification_type = "warning"
        return self._smart_notification(
            _("Smart Products"),
            message,
            notification_type,
            next_action=self._smart_soft_reload_action(),
        )

    def _add_imported_product_lines(self, imported):
        self.ensure_one()
        existing_by_product = {
            line.product_id.id: line
            for line in self.product_line_ids
            if line.product_id
        }
        created = updated = 0
        for product, qty in imported:
            existing = existing_by_product.get(product.id)
            if existing:
                existing.write({"qty": qty})
                updated += 1
            else:
                self.env["ab_transfer_smart_product_line"].create({
                    "wizard_id": self.id,
                    "product_id": product.id,
                    "qty": qty,
                })
                created += 1
        return created, updated

    def action_archive(self):
        self._check_archive_allowed()
        generated_headers = self._get_generated_headers_for_archive()
        blocked_headers = generated_headers.filtered(
            lambda header: (
                    header.smart_stage != SMART_STAGE_PURCHASE_PREPARATION
                    or header.is_submitted
            )
        )
        if blocked_headers:
            blocked_names = ", ".join(blocked_headers[:5].mapped("display_name"))
            if len(blocked_headers) > 5:
                blocked_names += _(", and %s more") % (len(blocked_headers) - 5)
            raise UserError(
                _(
                    "You can only archive smart wizard transfers while all generated "
                    "transfers are in Purchase Preparation and not submitted. Blocked: %s"
                )
                % blocked_names
            )

        if generated_headers:
            generated_headers.sudo().write({"active": False})
        self.sudo().write({"active": False})
        return self._smart_notification(
            _("Smart Transfer Wizard"),
            _("Smart wizard and generated transfers archived."),
            "success",
            next_action=self._smart_soft_reload_action(),
        )

    def action_refresh_smart_cache(self):
        self.ensure_one()
        if not self.env.user.has_group(SMART_GROUP_PURCHASE):
            raise AccessError(_("You are not allowed to refresh smart transfer cache."))
        if self.state == "done":
            raise UserError(_("Done wizards cannot refresh smart cache."))
        if not self.to_stores_id:
            raise UserError(_("Please select at least one destination store."))
        result = self.env["ab_transfer_smart_stock_cache"].sudo().refresh_stores_cache(
            self.to_stores_id,
            force=True,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Smart Transfer Cache"),
                "message": _(
                    "Smart cache refreshed. Stores: %(stores)s, Stock rows: %(stock_rows)s, "
                    "Sales rows: %(sales_rows)s."
                )
                           % result,
                "type": "success",
                "sticky": False,
            },
        }

    def _check_archive_allowed(self):
        if not self.env.user.has_group(SMART_GROUP_PURCHASE):
            raise AccessError(_("You are not allowed to archive smart transfer wizards."))

    def _get_generated_headers_for_archive(self):
        Header = self.env["ab_transfer_header"]
        generated_headers = Header.browse()
        for rec in self.with_context(active_test=False):
            generated_headers |= rec.generated_header_ids.with_context(active_test=False)
        return generated_headers

    def _validate_generation_values(self):
        self.ensure_one()
        if self.state == "done":
            raise UserError(_("This wizard already generated transfers."))
        if not self.to_stores_id:
            raise UserError(_("Please select at least one destination store."))
        if self.from_store_id in self.to_stores_id:
            raise UserError(_("Source store cannot be one of the destination stores."))
        if self.smart_days < 1:
            raise UserError(_("Smart days must be at least 1."))
        if not self.smart_stock_method:
            raise UserError(_("Stock calculation method is required."))
        if self.items_per_header < 1:
            raise UserError(_("Items per header must be at least 1."))

    def _ensure_smart_destination_caches(self):
        self.ensure_one()
        return self.env["ab_transfer_smart_stock_cache"].sudo().refresh_stores_cache(
            self.to_stores_id,
            force=False,
        )

    def _get_calculation_validation_error_action(self):
        self.ensure_one()
        try:
            if self.target_mode == "single":
                if not self.source_header_id:
                    raise UserError(_("Source transfer is required for single transfer calculation."))
                self.source_header_id._validate_smart_transfer_header()
            else:
                Header = self.env["ab_transfer_header"]
                for destination in self.to_stores_id:
                    Header.new(self._prepare_header_probe_vals(destination))._validate_smart_transfer_header()
        except UserError as error:
            return self._smart_notification(
                _("Smart Transfer Calculation"),
                str(error),
                "danger",
            )
        return False

    def _get_sales_cache_warning_action(self):
        self.ensure_one()
        if self.allow_incomplete_sales_cache:
            return False

        missing_dates = self._get_missing_sales_cache_dates_for_destinations()
        if not missing_dates:
            return False

        message = self.env["ab_transfer_header"]._format_smart_sales_cache_warning_message(
            missing_dates
        )
        self.write({
            "sales_cache_warning_message": message,
            "sales_cache_missing_days_count": len(missing_dates),
        })
        return self._reopen_wizard_action()

    def _get_missing_sales_cache_dates_for_destinations(self):
        self.ensure_one()
        missing_dates = set()
        Header = self.env["ab_transfer_header"]
        for destination in self.to_stores_id:
            header = Header.new(self._prepare_header_probe_vals(destination))
            if not header._get_smart_other_branch_store_sql_ids():
                continue
            missing_dates.update(header._get_smart_missing_sales_cache_dates())
        return sorted(missing_dates)

    def _prepare_header_probe_vals(self, destination):
        self.ensure_one()
        return {
            "from_store_id": self.from_store_id.id,
            "to_store_id": destination.id,
            "user_id": self.user_id.id,
            "company_id": self.company_id.id,
            "smart_days": self.smart_days,
            "smart_stock_method": self.smart_stock_method,
            "smart_product_domain": self.smart_product_domain or "[]",
            "fair_store_ids": [(6, 0, self.fair_store_ids.ids)],
            "target_product_ids": [(6, 0, self.target_product_ids.ids)],
            "smart_product_line_ids": [
                (0, 0, self._prepare_header_product_line_vals(line))
                for line in self.product_line_ids
            ],
        }

    def _prepare_header_create_vals(self, destination):
        self.ensure_one()
        return {
            "from_store_id": self.from_store_id.id,
            "to_store_id": destination.id,
            "user_id": self.user_id.id,
            "notes": self.notes,
            "company_id": self.company_id.id,
            "smart_days": self.smart_days,
            "smart_stock_method": self.smart_stock_method,
            "smart_product_domain": self.smart_product_domain or "[]",
            "smart_dropout_coverage": self.dropout_coverage,
            "smart_wizard_id": self.id,
            "target_product_ids": [(6, 0, self.target_product_ids.ids)],
            "fair_store_ids": [(6, 0, self.fair_store_ids.ids)],
            "smart_product_line_ids": [
                (0, 0, self._prepare_header_product_line_vals(line))
                for line in self.product_line_ids
            ],
        }

    def _get_calculation_context(self):
        self.ensure_one()
        context = {
            "smart_dropout_coverage": self.dropout_coverage,
        }
        if self.allow_incomplete_sales_cache:
            context["skip_smart_sales_cache_coverage"] = True
        return context

    def _action_run_single_header_calculation(self):
        self.ensure_one()
        if not self.source_header_id:
            raise UserError(_("Source transfer is required for single transfer calculation."))
        self._sync_source_header_from_wizard()
        calculation_action = self.source_header_id.with_context(
            **self._get_calculation_context()
        ).action_smart_transfer_calculation()
        if self._is_danger_notification(calculation_action):
            return calculation_action
        self.write({"state": "done"})
        return {
            "type": "ir.actions.act_window",
            "name": _("Smart Transfer"),
            "res_model": "ab_transfer_header",
            "res_id": self.source_header_id.id,
            "view_mode": "form",
        }

    def _sync_source_header_from_wizard(self):
        self.ensure_one()
        self.source_header_id.write({
            "from_store_id": self.from_store_id.id,
            "to_store_id": self.to_stores_id[:1].id,
            "user_id": self.user_id.id,
            "notes": self.notes,
            "company_id": self.company_id.id,
            "smart_days": self.smart_days,
            "smart_stock_method": self.smart_stock_method,
            "smart_product_domain": self.smart_product_domain or "[]",
            "smart_dropout_coverage": self.dropout_coverage,
            "target_product_ids": [(6, 0, self.target_product_ids.ids)],
            "fair_store_ids": [(6, 0, self.fair_store_ids.ids)],
            "smart_product_line_ids": [
                (5, 0, 0),
                *[
                    (0, 0, self._prepare_header_product_line_vals(line))
                    for line in self.product_line_ids
                ],
            ],
        })

    def _action_generate_batch_transfers(self):
        self.ensure_one()
        Header = self.env["ab_transfer_header"]
        created_headers = Header.browse()
        for destination in self.to_stores_id:
            header = Header.create(self._prepare_header_create_vals(destination))
            calculation_action = header.with_context(
                **self._get_calculation_context()
            ).action_smart_transfer_calculation()
            if self._is_danger_notification(calculation_action):
                return calculation_action
            created_headers |= self._split_generated_header_by_items(header)

        self.write({
            "state": "done",
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Generated Smart Transfers"),
            "res_model": "ab_transfer_header",
            "view_mode": "list,form",
            "domain": [("id", "in", created_headers.ids)],
            "context": {"create": False},
        }

    def _split_generated_header_by_items(self, header):
        self.ensure_one()
        limit = int(self.items_per_header or 0)
        if limit < 1:
            raise UserError(_("Items per header must be at least 1."))

        Header = self.env["ab_transfer_header"]
        sorted_lines = header._sort_smart_lines_by_product_location(header.smart_line_ids)
        chunks = list(self._smart_location_line_chunks(sorted_lines, limit))
        if len(chunks) <= 1:
            return header

        created_headers = header
        self._apply_chunk_product_filter(header, chunks[0])
        for chunk in chunks[1:]:
            chunk_header = Header.create(
                self._prepare_chunk_header_create_vals(header.to_store_id, chunk)
            )
            chunk.write({"header_id": chunk_header.id})
            created_headers |= chunk_header
        return created_headers

    def _prepare_chunk_header_create_vals(self, destination, smart_lines):
        vals = self._prepare_header_create_vals(destination)
        vals.update(self._chunk_product_filter_vals(smart_lines))
        return vals

    def _apply_chunk_product_filter(self, header, smart_lines):
        header.write(self._chunk_product_filter_vals(smart_lines))

    @staticmethod
    def _chunk_product_filter_vals(smart_lines):
        explicit_lines = smart_lines.filtered(
            lambda line: line.source_type == SMART_LINE_SOURCE_WIZARD
        )
        return {
            "smart_product_domain": "[]",
            "target_product_ids": [(6, 0, smart_lines.mapped("product_id").ids)],
            "smart_product_line_ids": [
                (5, 0, 0),
                *[
                    (0, 0, {
                        "product_id": line.product_id.id,
                        "qty": line.qty or line.product_id.min_sale_purchase_qty or 1.0,
                    })
                    for line in explicit_lines
                    if line.product_id
                ],
            ],
        }

    @staticmethod
    def _prepare_header_product_line_vals(line):
        return {
            "product_id": line.product_id.id,
            "qty": line.qty or line.product_id.min_sale_purchase_qty or 1.0,
        }

    def _parse_product_import_text(self):
        self.ensure_one()
        parsed_rows = []
        truncated = False
        for index, raw_line in enumerate(io.StringIO(self.product_import_text or ""), start=1):
            line = (raw_line or "").strip()
            if not line:
                continue
            if len(parsed_rows) >= MAX_PRODUCT_IMPORT_LINES:
                truncated = True
                break
            code, qty = self._parse_product_import_line(line, index)
            parsed_rows.append((code, qty))

        return self._products_from_code_qty_rows(parsed_rows), truncated

    def _products_from_code_qty_rows(self, parsed_rows):
        codes = [code for code, _qty in parsed_rows]
        products = self.env["ab_product"].with_context(active_test=False).search([
            ("code", "in", codes),
        ])
        products_by_code = {}
        for product in products:
            code = (product.code or "").strip()
            if code and code not in products_by_code:
                products_by_code[code] = product

        missing = [code for code in codes if code not in products_by_code]
        if missing:
            raise UserError(
                _("Product code(s) were not found: %s")
                % ", ".join(missing[:20])
            )

        qty_by_product_id = {}
        for code, qty in parsed_rows:
            product = products_by_code[code]
            qty_by_product_id[product.id] = qty_by_product_id.get(product.id, 0.0) + qty
        return [
            (self.env["ab_product"].browse(product_id), qty)
            for product_id, qty in qty_by_product_id.items()
        ]

    @api.model
    def _parse_product_import_line(self, line, index):
        parts = [part.strip() for part in re.split(r"[\t,;]+", line) if part.strip()]
        if len(parts) < 2:
            parts = line.rsplit(None, 1)
        if len(parts) < 2:
            raise UserError(_("Line %(line)s must contain product code and quantity.") % {"line": index})

        code = parts[0].strip()
        qty_text = parts[1].strip().replace(",", ".")
        try:
            qty = float(qty_text)
        except (TypeError, ValueError):
            raise UserError(_("Line %(line)s has an invalid quantity: %(qty)s") % {
                "line": index,
                "qty": qty_text,
            })
        if qty <= 0.0:
            raise UserError(_("Line %(line)s quantity must be greater than zero.") % {"line": index})
        return code, qty

    @api.model
    def _smart_location_line_chunks(self, lines, size):
        start = 0
        current_location = None
        for index, line in enumerate(lines):
            location = self._smart_line_location_key(line)
            if index == start:
                current_location = location
                continue
            if location != current_location or index - start >= size:
                yield lines[start:index]
                start = index
                current_location = location
        if len(lines) > start:
            yield lines[start:]

    @staticmethod
    def _smart_line_location_key(line):
        return str(line.product_id.location or "").strip()

    @staticmethod
    def _smart_line_chunks(lines, size):
        for index in range(0, len(lines), size):
            yield lines[index:index + size]

    def _reopen_wizard_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Smart Transfer Wizard"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @staticmethod
    def _is_danger_notification(action):
        return (
                isinstance(action, dict)
                and action.get("type") == "ir.actions.client"
                and action.get("tag") == "display_notification"
                and (action.get("params") or {}).get("type") == "danger"
        )

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
