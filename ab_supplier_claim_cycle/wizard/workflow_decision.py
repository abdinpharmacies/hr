from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SupplierClaimStageDecisionWizard(models.TransientModel):
    _name = 'ab_supplier_claim_stage_decision'
    _description = 'Supplier Claim Stage Decision'

    stage_state_id = fields.Many2one(
        'ab_supplier_claim_stage_state', required=True, readonly=True, ondelete='cascade')
    decision = fields.Selection([
        ('rejected', 'Reject Stage'),
        ('deferred', 'Defer Stage'),
        ('undo', 'Remove Approval'),
    ], required=True, readonly=True)
    reason = fields.Text(required=True)
    followup_date = fields.Date(string='Follow-up Date')

    def action_confirm(self):
        self.ensure_one()
        self.check_access('write')
        reason = (self.reason or '').strip()
        if not reason:
            raise ValidationError(_('A reason is required.'))
        stage_state = self.stage_state_id
        if self.decision == 'undo':
            if not stage_state.can_admin_undo:
                raise AccessError(_('Only a Claim Administrator can remove this approval.'))
            stage_state.claim_id.action_admin_remove_approval(stage_state, reason)
        else:
            if not stage_state.can_decide:
                raise AccessError(_('You cannot decide this stage.'))
            stage_state.claim_id._action_stage_decision(
                stage_state, self.decision, reason=reason,
                followup_date=self.followup_date,
            )
        return {'type': 'ir.actions.act_window_close'}

