from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from markupsafe import Markup
from .ab_supplier_claim_cycle import (
    STATES, DECISIONS, DEPARTMENTS, TAX_CLASSIFICATION, SUPPLIER_SECTION,
)

HISTORY_STATES = STATES + [('tax_accounts', 'Taxes'), ('inventory', 'Inventory'), ('purchasing', 'Purchasing'), ('supplier_accounts', 'Supplier Accounts')]


class SupplierClaimHistory(models.Model):
    _name = 'ab_supplier_claim_cycle.history'
    _description = 'Supplier Claim Stage History'
    _order = 'id desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    event = fields.Selection([(e, e.title()) for e in ('submitted', 'resubmitted', 'decision', 'closed', 'archived', 'restored', 'prepared', 'document_replaced', 'migration_exception')] + [('secretarial_note', 'Secretarial Note'), ('tax_finished', 'Taxes Finished'), ('claim_updated', 'Claim Details Updated')], required=True)
    from_state = fields.Selection(HISTORY_STATES)
    to_state = fields.Selection(HISTORY_STATES, required=True)
    department = fields.Selection([(d, d.replace('_', ' ').title()) for d in DEPARTMENTS] + [('secretarial', 'Secretarial'), ('tax_accounts', 'Taxes')])
    decision = fields.Selection(DECISIONS)
    inventory_decision = fields.Selection(DECISIONS)
    purchasing_decision = fields.Selection(DECISIONS)
    supplier_accounts_decision = fields.Selection(DECISIONS)
    bank_accounts_decision = fields.Selection(DECISIONS)
    tax_decision = fields.Selection(DECISIONS)
    document_revision = fields.Integer()
    return_destination = fields.Char()
    preparation_status = fields.Char()
    tax_classification = fields.Selection(TAX_CLASSIFICATION)
    section = fields.Selection(SUPPLIER_SECTION)
    reason = fields.Text()
    notes = fields.Text(string='Department Notes')
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

    @api.depends('notes', 'reason', 'event', 'decision', 'cheque_attachment')
    @api.depends_context('lang')
    def _compute_display_note(self):
        for entry in self:
            # Read legacy notes without rewriting immutable history.
            note = entry.notes or (entry.reason if not (
                entry.event == 'decision' and entry.decision in ('rejected', 'deferred')) else False)
            entry.display_note = (note if (note or '').strip()
                                  else _('Cheque attachment') if entry.cheque_attachment else False)

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
        names = ('event', 'from_state', 'to_state', 'department', 'decision',
                 'reason', 'notes', 'followup_date', 'review_round', 'document_revision')
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
