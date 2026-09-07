from odoo import _, fields, models
from odoo.exceptions import ValidationError
from .workflow_guard import WORKFLOW_WRITE_TOKEN


class CheckDeliveryWizard(models.TransientModel):
    _name = 'ab_check_delivery_wizard'
    _description = 'Check Delivery Status Wizard'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True)
    check_delivery_status = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('bank_transfer', 'Bank Transfer'),
            ('check_delivered', 'Issue Check'),
            ('mixed', 'Mixed (Bank Transfer + Cheque)'),
        ],
        string='Cheque Delivery Status',
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        self.claim_id._check_can_act_current_stage()
        if self.claim_id.status != 'sign_check':
            raise ValidationError(_('Cheque confirmation is only available at Sign Check.'))
        if not self.check_delivery_status:
            raise ValidationError(_('Cheque Delivery Status is required.'))
        vals = {
            'check_delivery_status': self.check_delivery_status,
        }
        if self.check_delivery_status in ('check_delivered', 'mixed'):
            vals['sub_delivery_status'] = 'shipped'
        else:
            vals['sub_delivery_status'] = False
        self.claim_id.with_context(supplier_claim_internal_write=WORKFLOW_WRITE_TOKEN).write(vals)
        self.claim_id._move_to_next_stage()
        return {'type': 'ir.actions.act_window_close'}
