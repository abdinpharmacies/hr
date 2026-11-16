from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .ab_supplier_claim_cycle import (
    CLAIM_STATES, PASSIVE_DECISIONS, SUPPLIER_SECTION, TAX_CLASSIFICATION,
)


PASSIVE_HISTORY_STATES = CLAIM_STATES + [
    ('operational_review', 'Operational Review'),
    ('financial_review', 'Financial Review'),
    ('secretarial_preparation', 'Secretarial Preparation'),
    ('bank_accounts', 'Bank Accounts'),
    ('returned_secretarial', 'Returned to Secretarial'),
    ('ready_to_close', 'Ready to Close'),
    ('tax_accounts', 'Taxes'),
    ('inventory', 'Inventory'),
    ('purchasing', 'Purchasing'),
    ('supplier_accounts', 'Supplier Accounts'),
]
PASSIVE_DEPARTMENTS = [
    ('inventory', 'Inventory'), ('purchasing', 'Purchasing'), ('tax', 'Tax'),
    ('supplier_accounts', 'Supplier Accounts'), ('bank_accounts', 'Bank Accounts'),
    ('secretarial', 'Secretarial'), ('tax_accounts', 'Taxes'),
]


class SupplierClaimHistory(models.Model):
    _name = 'ab_supplier_claim_cycle.history'
    _description = 'Supplier Claim Workflow History'
    _order = 'id desc'

    claim_id = fields.Many2one(
        'ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    event = fields.Selection([
        ('workflow_submitted', 'Workflow Submitted'),
        ('workflow_resubmitted', 'Workflow Resubmitted'),
        ('stage_decision', 'Stage Decision'),
        ('stage_invalidated', 'Stage Invalidated'),
        ('approval_removed', 'Approval Removed'),
        ('claim_updated', 'Claim Details Updated'),
        ('secretarial_note', 'Secretarial Note'),
        # Passive values keep already-created history readable.
        ('submitted', 'Submitted'), ('resubmitted', 'Resubmitted'),
        ('decision', 'Decision'), ('closed', 'Closed'), ('archived', 'Archived'),
        ('restored', 'Restored'), ('prepared', 'Prepared'),
        ('document_replaced', 'Document Replaced'),
        ('migration_exception', 'Migration Exception'), ('tax_finished', 'Taxes Finished'),
    ], required=True)
    from_state = fields.Selection(PASSIVE_HISTORY_STATES)
    to_state = fields.Selection(PASSIVE_HISTORY_STATES)
    decision = fields.Selection(PASSIVE_DECISIONS)
    reason = fields.Text()
    followup_date = fields.Date()
    review_round = fields.Integer(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    occurred_at = fields.Datetime(required=True)
    stage_state_id = fields.Many2one(
        'ab_supplier_claim_stage_state', readonly=True, ondelete='restrict', index=True)
    stage_name = fields.Char(readonly=True)
    stage_sequence = fields.Integer(readonly=True)
    display_note = fields.Text(string='Note', compute='_compute_display_note')

    # Passive audit columns retained without any fixed-department behavior.
    department = fields.Selection(PASSIVE_DEPARTMENTS)
    inventory_decision = fields.Selection(PASSIVE_DECISIONS)
    purchasing_decision = fields.Selection(PASSIVE_DECISIONS)
    supplier_accounts_decision = fields.Selection(PASSIVE_DECISIONS)
    bank_accounts_decision = fields.Selection(PASSIVE_DECISIONS)
    tax_decision = fields.Selection(PASSIVE_DECISIONS)
    document_revision = fields.Integer()
    return_destination = fields.Char()
    preparation_status = fields.Char()
    tax_classification = fields.Selection(TAX_CLASSIFICATION)
    section = fields.Selection(SUPPLIER_SECTION)
    notes = fields.Text(string='Department Notes')

    @api.depends('notes', 'reason')
    def _compute_display_note(self):
        for entry in self:
            entry.display_note = entry.notes or entry.reason or False

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('History is created only by workflow actions.'))

    @api.model
    def _append(self, vals_list):
        entries = super(SupplierClaimHistory, self.sudo()).create(vals_list)
        entries._sync_claim_chatter()
        return entries

    def _sync_claim_chatter(self):
        messages = self.env['mail.message'].sudo().search(
            fields.Domain('supplier_claim_history_id', 'in', self.ids))
        linked_ids = set(messages.mapped('supplier_claim_history_id').ids)
        names = (
            'event', 'from_state', 'to_state', 'stage_name', 'stage_sequence',
            'decision', 'reason', 'followup_date', 'review_round', 'document_revision',
        )
        for entry in self.filtered(lambda record: record.id not in linked_ids):
            paragraphs = []
            for name in names:
                value = entry[name]
                if value is False or value is None or value == '':
                    continue
                field = entry._fields[name]
                if field.type == 'selection':
                    value = dict(field._description_selection(entry.env)).get(value, value)
                paragraphs.append(Markup('<p><strong>%s</strong>: %s</p>') % (
                    field.get_description(entry.env)['string'], value))
            message = entry.claim_id._message_log(
                body=Markup('').join(paragraphs), author_id=entry.user_id.partner_id.id)
            message._link_supplier_claim_history(entry)

    def write(self, vals):
        raise AccessError(_('Workflow history cannot be modified.'))

    @api.ondelete(at_uninstall=True)
    def _prevent_history_deletion(self):
        raise AccessError(_('Workflow history cannot be deleted.'))
