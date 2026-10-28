from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class NativeSaleCancelWizard(models.TransientModel):
    _name = 'ab_sales_native_cancel_wizard'
    _description = 'Cancel Pending Native Invoice'

    sale_id = fields.Many2one('ab_sales_header', required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can cancel pending native invoices.'))
        if not (self.reason or '').strip():
            raise ValidationError(_('Enter a cancellation reason.'))
        self.sale_id.action_cancel_native(self.reason)
        return {'type': 'ir.actions.act_window_close'}
