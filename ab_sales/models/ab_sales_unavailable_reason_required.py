from odoo import models, _
from odoo.exceptions import UserError


class AbSalesHeaderUnavailableReasonRequired(models.Model):
    _inherit = "ab_sales_header"
    _UNAVAILABLE_REASON_DIFF = 0.025

    def _unavailable_lines_missing_reason(self):
        self.ensure_one()
        require_reason_lines = self.line_ids.filtered(
            lambda l: ((l.qty or 0.0) - (l.balance or 0.0)) > self._UNAVAILABLE_REASON_DIFF
        )
        return require_reason_lines.filtered(
            lambda l: (not l.unavailable_reason)
            or (l.unavailable_reason == "other" and not (l.unavailable_reason_other or "").strip())
        )

    def action_submit(self):
        for header in self:
            if not (header.pos_client_token or "").strip():
                raise UserError(_("Submit is only allowed for bills created from POS."))
            missing_lines = header._unavailable_lines_missing_reason()
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
