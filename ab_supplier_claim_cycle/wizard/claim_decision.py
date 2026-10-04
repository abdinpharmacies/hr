from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError

from ..models.ab_supplier_claim_cycle import DEPARTMENTS


class SupplierClaimDecisionWizard(models.TransientModel):
    _name = 'ab_supplier_claim_cycle.decision.wizard'
    _description = 'Supplier Claim Decision'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, readonly=True, ondelete='cascade')
    department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS],
                                  required=True, readonly=True)
    decision = fields.Selection([('rejected', 'Rejected'), ('deferred', 'Deferred')],
                                required=True, readonly=True)
    # Required by the form and confirmation, allowing an initially empty popup.
    reason = fields.Text()
    followup_date = fields.Date(string='Follow-up Date')
    review_round = fields.Integer(readonly=True, required=True)
    history_revision = fields.Integer(readonly=True, required=True)

    def action_confirm(self):
        self.ensure_one()
        self.check_access('write')
        claim = self.claim_id
        claim._require_role(self.department)
        claim._prepare_action()
        if (claim.review_round != self.review_round
                or max(claim.history_ids.ids, default=0) != self.history_revision):
            raise UserError(_('The claim has changed. Close this dialog and open it again.'))
        if not (self.reason or '').strip():
            raise ValidationError(_('A reason is required for rejection or deferral.'))
        claim.action_decide(self.department, self.decision, reason=self.reason,
                            followup_date=self.followup_date)
        return {'type': 'ir.actions.act_window_close'}
