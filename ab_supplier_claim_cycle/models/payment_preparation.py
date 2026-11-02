from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from markupsafe import Markup


class SupplierClaimDocument(models.Model):
    _name = 'ab_supplier_claim_document'
    _description = 'Supplier Claim Document Revision'
    _order = 'id desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    kind = fields.Selection([(k, label) for k, label in (
        ('supplier_cheque', 'Supplier Cheque'), ('tax_review', 'Tax Review'),
        ('payment_request', 'Payment Request'), ('bank_cheque', 'Bank Document'),
        ('attachment', 'Attachment'))], required=True)
    content = fields.Binary(attachment=False, required=True)
    filename = fields.Char()
    revision = fields.Integer(required=True)
    reason = fields.Text(required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    occurred_at = fields.Datetime(required=True)

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Documents are recorded only by workflow actions.'))

    @api.model
    def _append(self, vals):
        documents = super(SupplierClaimDocument, self.sudo()).create(vals)
        documents._sync_claim_chatter()
        return documents

    def _sync_claim_chatter(self):
        messages = self.env['mail.message'].sudo().search(
            fields.Domain('supplier_claim_document_id', 'in', self.ids))
        linked_ids = set(messages.mapped('supplier_claim_document_id').ids)
        for document in self.filtered(lambda record: record.id not in linked_ids):
            kind = dict(document._fields['kind']._description_selection(document.env))[document.kind]
            reason = _('Document uploaded') if document.reason == 'Document uploaded' else document.reason
            body = Markup('<p><strong>%s</strong>: %s</p><p>%s: %s</p><p>%s</p><p><a href="%s">%s</a></p>') % (
                _('Document'), kind, _('Revision'), document.revision, reason,
                '/web/content/ab_supplier_claim_document/%s/content?download=true' % document.id,
                document.filename or _('Attachment'))
            message = document.claim_id._message_log(
                subject=_('Document recorded'), body=body, author_id=document.user_id.partner_id.id)
            message._link_supplier_claim_document(document)

    def write(self, vals):
        raise AccessError(_('Document history cannot be modified.'))

    @api.ondelete(at_uninstall=True)
    def _prevent_deletion(self):
        raise AccessError(_('Document history cannot be deleted.'))


class ResCompany(models.Model):
    _inherit = 'res.company'

    supplier_claim_secretarial_sla_days = fields.Integer(default=2, required=True)

    @api.constrains('supplier_claim_secretarial_sla_days')
    def _check_claim_sla(self):
        if any(company.supplier_claim_secretarial_sla_days <= 0 for company in self):
            raise ValidationError(_('The preparation SLA must be a positive number of working days.'))


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    supplier_claim_secretarial_sla_days = fields.Integer(
        related='company_id.supplier_claim_secretarial_sla_days', readonly=False)
