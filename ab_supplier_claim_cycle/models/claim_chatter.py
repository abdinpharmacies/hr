from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class MailMessage(models.Model):
    _inherit = 'mail.message'

    supplier_claim_history_id = fields.Many2one(
        'ab_supplier_claim_cycle.history', readonly=True, copy=False, ondelete='restrict', index=True)
    supplier_claim_document_id = fields.Many2one(
        'ab_supplier_claim_document', readonly=True, copy=False, ondelete='restrict', index=True)

    _supplier_claim_history_unique = models.Constraint(
        'UNIQUE(supplier_claim_history_id)',
        'Each claim history entry can be linked to only one chatter message.',
    )
    _supplier_claim_document_unique = models.Constraint(
        'UNIQUE(supplier_claim_document_id)',
        'Each claim document can be linked to only one chatter message.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any(values.get('supplier_claim_history_id') or values.get('supplier_claim_document_id')
               for values in vals_list):
            raise AccessError(_('Claim audit messages are managed by the workflow.'))
        return super().create(vals_list)

    def write(self, vals):
        protected = {'body', 'subject', 'model', 'res_id', 'author_id', 'date',
                     'supplier_claim_history_id', 'supplier_claim_document_id',
                     'is_internal', 'subtype_id', 'message_type'}
        if (set(vals) & {'supplier_claim_history_id', 'supplier_claim_document_id'}
                or (set(vals) & protected and (
                    any(self.mapped('supplier_claim_history_id')) or any(self.mapped('supplier_claim_document_id'))))):
            raise AccessError(_('Claim audit messages are managed by the workflow.'))
        return super().write(vals)

    def _link_supplier_claim_history(self, entry):
        self.ensure_one()
        entry.ensure_one()
        if self.model != 'ab_supplier_claim_cycle' or self.res_id != entry.claim_id.id:
            raise AccessError(_('Claim audit messages are managed by the workflow.'))
        return super().write({'supplier_claim_history_id': entry.id, 'date': entry.occurred_at})

    def _link_supplier_claim_document(self, document):
        self.ensure_one()
        document.ensure_one()
        if self.model != 'ab_supplier_claim_cycle' or self.res_id != document.claim_id.id:
            raise AccessError(_('Claim audit messages are managed by the workflow.'))
        return super().write({'supplier_claim_document_id': document.id, 'date': document.occurred_at})

    @api.ondelete(at_uninstall=False)
    def _prevent_claim_audit_deletion(self):
        if any(self.mapped('supplier_claim_history_id')) or any(self.mapped('supplier_claim_document_id')):
            raise AccessError(_('Claim audit messages are managed by the workflow.'))
