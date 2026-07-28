from odoo import models, _
from odoo.exceptions import UserError


class AbSalesHeaderUnavailableReasonRequired(models.Model):
    _inherit = "ab_sales_header"
    _UNAVAILABLE_REASON_DIFF = 0.025

    def _line_qty_in_balance_uom(self, line):
        """Return the line quantity normalized to the product balance UoM."""
        qty = float(line.qty or 0.0)
        line_uom = line.uom_id
        base_uom = line.product_id.uom_id

        selected_factor = float(line_uom.factor or 0.0) if line_uom else 0.0
        base_factor = float(base_uom.factor or 0.0) if base_uom else 0.0

        if selected_factor <= 0:
            selected_factor = base_factor or 1.0
        if base_factor <= 0:
            base_factor = selected_factor or 1.0

        return qty * selected_factor / base_factor

    def _unavailable_lines_missing_reason(self):
        self.ensure_one()
        require_reason_lines = self.line_ids.filtered(
            lambda l: (
                              self._line_qty_in_balance_uom(l) - float(l.balance or 0.0)
                      ) > self._UNAVAILABLE_REASON_DIFF
        )
        return require_reason_lines.filtered(
            lambda l: (not l.unavailable_reason)
                      or (l.unavailable_reason == "other" and not (l.unavailable_reason_other or "").strip())
        )

    def action_submit(self):
        self.ensure_one()
        if not (self.pos_client_token or "").strip():
            raise UserError(_("Submit is only allowed for bills created from POS."))
        missing_lines = self._unavailable_lines_missing_reason()
        if missing_lines:
            labels = []
            for line in missing_lines:
                product_name = line.product_id.display_name if line.product_id else _("Unknown product")
                labels.append("- %s" % product_name)
            raise UserError(_(
                "Products where requested qty exceeds available balance require a reason before submit.\n"
                "If reason is 'Other', details are required.\n\n"
                "Missing lines:\n%s"
            ) % "\n".join(labels))
        return super().action_submit()
