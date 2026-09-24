from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from .ab_supplier_claim_cycle import STATES, DECISIONS, DEPARTMENTS


class SupplierClaimHistory(models.Model):
    _name = 'ab_supplier_claim_cycle.history'
    _description = 'Supplier Claim Stage History'
    _order = 'id desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    event = fields.Selection([(e, e.title()) for e in ('created', 'submitted', 'resubmitted', 'decision', 'closed', 'archived', 'restored')], required=True)
    from_state = fields.Selection(STATES)
    to_state = fields.Selection(STATES, required=True)
    department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS])
    decision = fields.Selection(DECISIONS)
    inventory_decision = fields.Selection(DECISIONS)
    purchasing_decision = fields.Selection(DECISIONS)
    supplier_accounts_decision = fields.Selection(DECISIONS)
    bank_accounts_decision = fields.Selection(DECISIONS)
    reason = fields.Text()
    followup_date = fields.Date()
    review_round = fields.Integer(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    occurred_at = fields.Datetime(required=True)

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('History is created only by workflow actions.'))

    @api.model
    def _append(self, vals_list):
        return super(SupplierClaimHistory, self.sudo()).create(vals_list)

    def write(self, vals):
        raise AccessError(_('Workflow history cannot be modified.'))

    @api.ondelete(at_uninstall=True)
    def _prevent_history_deletion(self):
        raise AccessError(_('Workflow history cannot be deleted.'))
