# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

SMART_STAGE_PURCHASE_PREPARATION = "purchase_preparation"
SMART_LINE_LOCKED_STAGES = ("pre_submit", "submit")


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
        for rec in self:
            original_qty = rec._get_smart_allowed_base_qty()
            allowed_over_qty = rec.smart_over_need_qty or 0.0
            max_qty = original_qty + max(allowed_over_qty, 0.0)
            if float_compare(rec.qty or 0.0, max_qty, precision_digits=3) > 0:
                raise ValidationError(
                    _(
                        "Smart transfer quantity cannot exceed %(max_qty).3f. "
                        "Allowed over quantity is %(allowed_over_qty).3f."
                    )
                    % {
                        "max_qty": max_qty,
                        "allowed_over_qty": max(allowed_over_qty, 0.0),
                    }
                )

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
            vals.setdefault("smart_original_qty", qty)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals or {})
        vals.pop("class_id", None)
        if not vals:
            return True
        allowed_system_fields = {"state", "is_submitted"}
        if vals and set(vals) - allowed_system_fields:
            self._check_smart_line_editable()
            self._check_smart_qty_write(vals)
        return super().write(vals)

    def unlink(self):
        self._check_smart_line_editable()
        return super().unlink()
