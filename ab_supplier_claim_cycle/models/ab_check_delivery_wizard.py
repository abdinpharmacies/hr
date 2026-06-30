from odoo import _, fields, models
from odoo.exceptions import ValidationError


class CheckDeliveryWizard(models.TransientModel):
    _name = 'ab.check.delivery.wizard'
    _description = 'Check Delivery Status Wizard'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True)
    check_delivery_status = fields.Selection(
        selection=[('cash', 'Cash'), ('bank_transfer', 'Bank Transfer'),
                   ('check_delivered', 'Issue Check Delivery')],
        string='Cheque Delivery Status',
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        if not self.check_delivery_status:
            raise ValidationError(_('Cheque Delivery Status is required.'))
        self.claim_id.with_context(supplier_claim_internal_write=True).write({
            'check_delivery_status': self.check_delivery_status,
        })
        self.claim_id._move_to_next_stage()
        return {'type': 'ir.actions.act_window_close'}
