from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from .ab_supplier_claim_cycle import STATES, DECISIONS, DEPARTMENTS
from .ab_supplier import TAX_CLASSIFICATION, LEGACY_SUPPLIER_SECTION


class SupplierClaimHistory(models.Model):
    _name = 'ab_supplier_claim_cycle.history'
    _description = 'Supplier Claim Stage History'
    _order = 'id desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    event = fields.Selection([(e, e.title()) for e in ('created', 'submitted', 'resubmitted', 'decision', 'closed', 'archived', 'restored', 'migrated')] + [('secretarial_note', 'Secretarial Note'),
        ('imported_secretarial_note', 'Imported Secretarial Note')], required=True)
    from_state = fields.Selection(STATES)
    to_state = fields.Selection(STATES, required=True)
    department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS] + [('secretarial', 'Secretarial')])
    decision = fields.Selection(DECISIONS)
    inventory_decision = fields.Selection(DECISIONS)
    purchasing_decision = fields.Selection(DECISIONS)
    supplier_accounts_decision = fields.Selection(DECISIONS)
    bank_accounts_decision = fields.Selection(DECISIONS)
    tax_classification = fields.Selection(TAX_CLASSIFICATION)
    section = fields.Selection(LEGACY_SUPPLIER_SECTION)
    bracket_snapshot = fields.Json()
    reason = fields.Text()
    followup_date = fields.Date()
    review_round = fields.Integer(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    occurred_at = fields.Datetime(required=True)

    cheque_attachment = fields.Binary(
        compute='_compute_cheque_attachment', compute_sudo=False,
        help='Current cheque uploaded on this claim by the department that wrote the note.')
    cheque_filename = fields.Char(compute='_compute_cheque_attachment', compute_sudo=False)

    @api.depends('department', 'claim_id.cheque_attachment', 'claim_id.cheque_filename',
                 'claim_id.bank_cheque_attachment', 'claim_id.bank_cheque_filename')
    def _compute_cheque_attachment(self):
        for entry in self:
            attachment = filename = False
            if entry.department == 'supplier_accounts':
                attachment = entry.claim_id.cheque_attachment
                filename = entry.claim_id.cheque_filename
            elif entry.department == 'bank_accounts':
                attachment = entry.claim_id.bank_cheque_attachment
                filename = entry.claim_id.bank_cheque_filename
            entry.cheque_attachment = attachment
            entry.cheque_filename = (filename or 'cheque') if attachment else False

    display_note = fields.Text(string='Note', compute='_compute_display_note')

    @api.depends('reason', 'cheque_attachment')
    @api.depends_context('lang')
    def _compute_display_note(self):
        for entry in self:
            entry.display_note = (entry.reason if (entry.reason or '').strip()
                                  else _('Cheque attachment') if entry.cheque_attachment else False)

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
