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
        if "smart_original_qty" in vals:
            raise ValidationError(_("Original smart quantity cannot be edited."))
        if "qty" not in vals:
            return

        new_qty = vals["qty"] or 0.0
        self._check_smart_qty_value(new_qty)
        self._check_smart_qty_editable()
        for rec in self:
            if float_compare(new_qty, rec.qty or 0.0, precision_digits=3) <= 0:
                continue

            original_qty = rec.smart_original_qty or rec.qty or 0.0
            allowed_over_qty = (rec.smart_source_stock_qty or 0.0) - (
                    rec.smart_total_need or 0.0
            )
            max_qty = original_qty + max(allowed_over_qty, 0.0)
            if float_compare(new_qty, max_qty, precision_digits=3) > 0:
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
