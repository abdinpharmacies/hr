# -*- coding: utf-8 -*-
from datetime import timezone
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

SMART_STAGE_PURCHASE_PREPARATION = "purchase_preparation"
SMART_LINE_LOCKED_STAGES = ("pre_submit", "submit")
SMART_LINE_SOURCE_DOMAIN = "domain"
SMART_LINE_SOURCE_WIZARD = "wizard"
SMART_PREFETCHED_SOURCE_INVENTORY_CONTEXT_KEY = (
    "smart_prefetched_source_inventory_json_by_product"
)
SMART_PREFETCHED_SOURCE_INVENTORY_CACHE_KEY = (
    "ab_transfer_smart.prefetched_source_inventory_json_by_line"
)
EGYPT_TZ = ZoneInfo("Africa/Cairo")


class AbTransferSmartLine(models.Model):
    _name = "ab_transfer_smart_line"
    _inherit = "ab_transfer_line"
    _description = "Smart Transfer Line"
    _order = "smart_product_location, product_id, id"

    class_id = fields.Integer(
        string="Class ID",
        required=False,
        copy=False,
    )

    smart_stage = fields.Selection(
        related="header_id.smart_stage",
        string="Smart Stage",
        readonly=True,
    )

    source_type = fields.Selection(
        selection=[
            (SMART_LINE_SOURCE_WIZARD, "Wizard"),
            (SMART_LINE_SOURCE_DOMAIN, "Domain"),
        ],
        string="Source Type",
        default=SMART_LINE_SOURCE_DOMAIN,
        required=True,
        copy=False,
        index=True,
    )

    create_day = fields.Date(
        string="Create Day",
        compute="_compute_create_day",
        store=True,
        readonly=True,
        copy=False,
        index=True,
    )

    exclusion_reason = fields.Selection(
        selection=[
            ("expired", "Expired"),
            ("damaged", "Damaged"),
            ("wrong_balance", "Wrong Balance"),
            ("dropout_coverage", "Dropout Coverage"),
        ],
        string="Exclusion Reason",
        copy=False,
    )

    smart_original_qty = fields.Float(
        string="Original Smart Quantity",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_qty_exceeds_over_need = fields.Boolean(
        string="Quantity Exceeds Over Need",
        compute="_compute_smart_qty_exceeds_over_need",
        readonly=True,
    )
    smart_qty_exceeds_expected_stock = fields.Boolean(
        string="Quantity Exceeds Expected Stock",
        compute="_compute_smart_qty_exceeds_expected_stock",
        readonly=True,
    )

    @api.depends("product_id", "header_id.from_store_id")
    def _recompute_inventory_json(self):
        prefetched_by_line = self.env.cr.cache.get(
            SMART_PREFETCHED_SOURCE_INVENTORY_CACHE_KEY,
            {},
        )
        if not prefetched_by_line:
            return super()._recompute_inventory_json()

        remaining_lines = self.browse()
        for line in self:
            if line.id not in prefetched_by_line:
                remaining_lines |= line
                continue
            line.inventory_json = prefetched_by_line.pop(line.id)

        if remaining_lines:
            super(AbTransferSmartLine, remaining_lines)._recompute_inventory_json()

    def _cache_prefetched_source_inventory_json(self, inventory_by_line):
        prefetched_by_line = self.env.cr.cache.setdefault(
            SMART_PREFETCHED_SOURCE_INVENTORY_CACHE_KEY,
            {},
        )
        prefetched_by_line.update({
            int(line_id): payload
            for line_id, payload in (inventory_by_line or {}).items()
            if line_id
        })

    def _cache_context_source_inventory_json(self):
        prefetched_by_product = self.env.context.get(
            SMART_PREFETCHED_SOURCE_INVENTORY_CONTEXT_KEY
        )
        if not isinstance(prefetched_by_product, dict):
            return False
        inventory_by_line = {
            line.id: prefetched_by_product[line.product_id.id]
            for line in self
            if line.product_id.id in prefetched_by_product
        }
        if not inventory_by_line:
            return False
        self._cache_prefetched_source_inventory_json(inventory_by_line)
        return True

    def _clear_prefetched_source_inventory_json(self):
        prefetched_by_line = self.env.cr.cache.get(
            SMART_PREFETCHED_SOURCE_INVENTORY_CACHE_KEY,
            {},
        )
        for line_id in self.ids:
            prefetched_by_line.pop(line_id, None)

    @api.depends("create_date")
    def _compute_create_day(self):
        for rec in self:
            rec.create_day = rec._get_egypt_day_from_datetime(rec.create_date)

    @api.model
    def _get_egypt_day_from_datetime(self, value):
        dt_value = fields.Datetime.to_datetime(value) if value else fields.Datetime.now()
        if not dt_value:
            return False
        if dt_value.tzinfo is None:
            dt_value = dt_value.replace(tzinfo=timezone.utc)
        return dt_value.astimezone(EGYPT_TZ).date()

    @api.depends(
        "qty",
        "smart_original_qty",
        "smart_qty_before_int",
        "smart_source_stock_qty",
        "smart_total_need",
        "exclusion_reason",
    )
    def _compute_smart_qty_exceeds_over_need(self):
        for rec in self:
            allowed_over_qty = max(rec.smart_over_need_qty or 0.0, 0.0)
            max_qty = rec._get_smart_allowed_base_qty() + allowed_over_qty
            rec.smart_qty_exceeds_over_need = (
                not rec.exclusion_reason
                and float_compare(rec.qty or 0.0, max_qty, precision_digits=3) > 0
            )

    def _get_smart_allowed_base_qty(self):
        self.ensure_one()
        if self.smart_original_qty:
            return self.smart_original_qty
        if self.smart_qty_before_int:
            return self.qty or 0.0
        return self.smart_original_qty or 0.0

    @api.depends(
        "qty",
        "smart_expected_source_stock_qty",
        "exclusion_reason",
    )
    def _compute_smart_qty_exceeds_expected_stock(self):
        for rec in self:
            rec.smart_qty_exceeds_expected_stock = (
                not rec.exclusion_reason
                and float_compare(
                    rec.qty or 0.0,
                    rec.smart_expected_source_stock_qty or 0.0,
                    precision_digits=3,
                ) > 0
            )

    def _check_smart_line_editable(self):
        locked = self.filtered(
            lambda rec: rec.header_id.is_submitted
                        or rec.header_id.smart_stage in SMART_LINE_LOCKED_STAGES
        )
        if locked:
            raise ValidationError(_("Pre-submitted smart transfer lines cannot be edited."))

    def _check_smart_qty_editable(self):
        locked = self.filtered(
            lambda rec: rec.header_id.is_submitted
                        or rec.header_id.smart_stage != SMART_STAGE_PURCHASE_PREPARATION
        )
        if locked:
            raise ValidationError(
                _("Smart transfer quantities can only be edited during purchase preparation.")
            )

    def _check_smart_qty_value(self, new_qty):
        if float_compare(new_qty, 0.0, precision_digits=3) < 0:
            raise ValidationError(_("Smart transfer quantity cannot be negative."))

    def _check_smart_qty_write(self, vals):
        if (
                "smart_original_qty" in vals
                and not self.env.context.get("allow_smart_original_qty_write")
        ):
            raise ValidationError(_("Original smart quantity cannot be edited."))
        if "qty" not in vals:
            return

        new_qty = vals["qty"] or 0.0
        self._check_smart_qty_value(new_qty)
        self._check_smart_qty_editable()

    def _check_smart_qty_allowed_over(self):
        errors = []
        for rec in self.filtered(lambda line: not line.exclusion_reason):
            original_qty = rec._get_smart_allowed_base_qty()
            allowed_over_qty = max(rec.smart_over_need_qty or 0.0, 0.0)
            max_qty = original_qty + allowed_over_qty
            if float_compare(rec.qty or 0.0, max_qty, precision_digits=3) > 0:
                errors.append(
                    "%s | %s | %.3f | %.3f"
                    % (
                        rec.product_code or rec.product_id.code or "",
                        rec.product_id.name or rec.product_id.display_name or "",
                        rec.qty or 0.0,
                        allowed_over_qty,
                    )
                )

        if errors:
            raise ValidationError(
                _(
                    "Smart transfer quantity cannot exceed the allowed over for these lines:\n"
                    "code | name | qty | allowed_over_qty\n%s"
                )
                % "\n".join(errors)
            )

    @api.constrains(
        "header_id",
        "from_store_id",
        "to_store_id",
        "product_id",
        "source_type",
        "create_day",
        "exclusion_reason",
    )
    def _constrains_duplicate_transfer_lines(self):
        if (
                self.env.context.get("models_to_check")
                or self.env.context.get("module") == "ab_transfer_smart"
        ):
            return
        self._check_duplicate_transfer_lines()

    def _get_duplicate_transfer_line_key(self):
        self.ensure_one()
        if (
                not self.from_store_id
                or not self.to_store_id
                or not self.product_id
                or not self.source_type
                or not self.create_day
        ):
            return False
        return (
            self.from_store_id.id,
            self.to_store_id.id,
            self.product_id.id,
            self.source_type,
            self.create_day,
        )

    def _get_duplicate_check_lines(self):
        return self.filtered(
            lambda line: (
                    not line.exclusion_reason
                    and line.header_id.smart_stage != SMART_STAGE_PURCHASE_PREPARATION
                    and line._get_duplicate_transfer_line_key()
            )
        )

    def _check_duplicate_transfer_lines(self):
        check_lines = self._get_duplicate_check_lines()
        if not check_lines:
            return

        keys = set(check_lines.mapped(lambda line: line._get_duplicate_transfer_line_key()))
        from_store_ids = {key[0] for key in keys}
        to_store_ids = {key[1] for key in keys}
        product_ids = {key[2] for key in keys}
        source_types = {key[3] for key in keys}
        create_days = {key[4] for key in keys}

        candidates = self.search([
            ("from_store_id", "in", list(from_store_ids)),
            ("to_store_id", "in", list(to_store_ids)),
            ("product_id", "in", list(product_ids)),
            ("source_type", "in", list(source_types)),
            ("create_day", "in", list(create_days)),
            ("header_id.smart_stage", "!=", SMART_STAGE_PURCHASE_PREPARATION),
            ("exclusion_reason", "=", False),
        ])
        candidates_by_key = {}
        for line in candidates:
            key = line._get_duplicate_transfer_line_key()
            if key not in keys:
                continue
            candidates_by_key.setdefault(key, self.browse())
            candidates_by_key[key] |= line

        errors = []
        reported = set()
        for line in check_lines:
            key = line._get_duplicate_transfer_line_key()
            duplicate_lines = candidates_by_key.get(key, self.browse()) - line
            for duplicate in duplicate_lines:
                report_key = tuple(sorted((line.id, duplicate.id)))
                if report_key in reported:
                    continue
                reported.add(report_key)
                errors.append(line._format_duplicate_transfer_line_error(duplicate))

        if errors:
            raise ValidationError(
                _("Duplicated transfer products found:\n\n%s")
                % "\n\n".join(errors)
            )

    def _format_duplicate_transfer_line_error(self, duplicate):
        self.ensure_one()
        source_label = dict(self._fields["source_type"].selection).get(
            self.source_type,
            self.source_type,
        )
        create_day = (
            self.create_day.strftime("%d/%m/%Y")
            if self.create_day
            else ""
        )
        return _(
            "Code: %(code)s\n"
            "Product: %(product)s\n"
            "Qty: %(qty).3f\n"
            "Source: %(source)s\n"
            "Create Day: %(create_day)s\n"
            "Existing Transfer: %(transfer)s"
        ) % {
            "code": self.product_code or self.product_id.code or "",
            "product": self.product_id.name or self.product_id.display_name or "",
            "qty": self.qty or 0.0,
            "source": source_label,
            "create_day": create_day,
            "transfer": duplicate.header_id.display_name or duplicate.header_id.name or duplicate.header_id.id,
        }

    @api.model_create_multi
    def create(self, vals_list):
        header_ids = [vals.get("header_id") for vals in vals_list if vals.get("header_id")]
        if header_ids:
            headers = self.env["ab_transfer_header"].browse(header_ids).exists()
            locked = headers.filtered(
                lambda rec: rec.is_submitted or rec.smart_stage in SMART_LINE_LOCKED_STAGES
            )
            if locked:
                raise ValidationError(_("Pre-submitted smart transfer lines cannot be edited."))
        default_qty = self.default_get(["qty"]).get("qty", 1.0)
        for vals in vals_list:
            vals.pop("class_id", None)
            qty = vals.get("qty", default_qty) or 0.0
            self._check_smart_qty_value(qty)
            vals.setdefault("source_type", SMART_LINE_SOURCE_DOMAIN)
            vals.setdefault("smart_original_qty", qty)
        lines = self.browse()
        try:
            with self.env.cr.savepoint():
                lines = super().create(vals_list)
                if lines._cache_context_source_inventory_json():
                    lines.flush_recordset([
                        "inventory_json",
                        "sell_price",
                        "cost",
                        "purchase_price",
                        "tax_value",
                    ])
                lines._check_duplicate_transfer_lines()
        finally:
            lines._clear_prefetched_source_inventory_json()
        return lines

    def write(self, vals):
        vals = dict(vals or {})
        vals.pop("class_id", None)
        if not vals:
            return True
        allowed_system_fields = {"state", "is_submitted"}
        if vals and set(vals) - allowed_system_fields:
            self._check_smart_line_editable()
            self._check_smart_qty_write(vals)
        has_prefetched_inventory = self._cache_context_source_inventory_json()
        try:
            with self.env.cr.savepoint():
                result = super().write(vals)
                if has_prefetched_inventory:
                    self.flush_recordset([
                        "inventory_json",
                        "sell_price",
                        "cost",
                        "purchase_price",
                        "tax_value",
                    ])
                duplicate_fields = {
                    "product_id",
                    "header_id",
                    "source_type",
                    "exclusion_reason",
                }
                if duplicate_fields.intersection(vals):
                    self._check_duplicate_transfer_lines()
        finally:
            self._clear_prefetched_source_inventory_json()
        return result

    def unlink(self):
        self._check_smart_line_editable()
        return super().unlink()
