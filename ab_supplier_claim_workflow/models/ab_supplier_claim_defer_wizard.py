from odoo import _, fields, models
from odoo.exceptions import UserError


class SupplierClaimDeferWizard(models.TransientModel):
    _name = 'ab_supplier_claim_defer_wizard'
    _description = 'Supplier Claim Defer Wizard'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, readonly=True)
    stage_key = fields.Char(required=True, readonly=True)
    expected_completion_date = fields.Date(string='Expected Completion Date', required=True)
    deferral_reason = fields.Text(string='Deferral Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        claim = self.claim_id
        date_field = claim._get_defer_expected_date_field(self.stage_key)
        reason_field = claim._get_defer_reason_field(self.stage_key)
        if not date_field or not reason_field:
            raise UserError(_("Deferral is only available during department review stages."))
        claim.write({
            date_field: self.expected_completion_date,
            reason_field: self.deferral_reason,
        })
        return claim.action_defer()
