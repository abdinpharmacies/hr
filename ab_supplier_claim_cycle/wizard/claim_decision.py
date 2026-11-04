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
    return_destination = fields.Selection([('secretarial', 'Secretarial'), ('supplier_accounts', 'Supplier Accounts')])
    affects_tax = fields.Boolean(string='Affects Amount or Tax Information')
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
                            followup_date=self.followup_date, return_destination=self.return_destination, affects_tax=self.affects_tax)
        return {'type': 'ir.actions.act_window_close'}


class SupplierDocumentReplacement(models.TransientModel):
    _name = 'ab_supplier_claim_document_replacement'
    _description = 'Replace Supplier Document'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True)
    content = fields.Binary(required=True, attachment=False)
    filename = fields.Char(required=True)
    reason = fields.Text(required=True)
    change_amount = fields.Boolean()
    claim_amount = fields.Float(digits=(16, 2))
    can_edit_tax_classification = fields.Boolean(related='claim_id.can_edit_tax_classification', compute_sudo=False)
    change_tax_type = fields.Boolean()
    tax_classification = fields.Selection(related='claim_id.tax_classification', readonly=True)
    new_tax_classification = fields.Selection([
        ('through_supplier', 'Advance Payments'), ('tax_payment', 'Tax Payment'),
        ('withholding_tax', 'Withholding Tax'), ('non_tax_payment', 'Non-tax Payment')])

    def action_confirm(self):
        self.ensure_one()
        self.check_access('write')
        self.claim_id.action_replace_supplier_document(
            self.content, self.filename, self.reason,
            claim_amount=self.claim_amount if self.change_amount else None,
            tax_classification=self.new_tax_classification if self.change_tax_type else None)
        return {'type': 'ir.actions.act_window_close'}
