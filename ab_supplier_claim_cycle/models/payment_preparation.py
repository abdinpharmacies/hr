from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SupplierClaimDocument(models.Model):
    _name = 'ab_supplier_claim_document'
    _description = 'Supplier Claim Document Revision'
    _order = 'id desc'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, ondelete='restrict', index=True)
    kind = fields.Selection([(k, label) for k, label in (
        ('supplier_cheque', 'Supplier Cheque'), ('tax_review', 'Tax Review'),
        ('payment_request', 'Payment Request'), ('bank_cheque', 'Bank Document'))], required=True)
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
        return super(SupplierClaimDocument, self.sudo()).create(vals)

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
