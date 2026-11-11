from odoo import _, fields, models


class ClaimErrorWizard(models.TransientModel):
    _name = 'ab_claim_error_wizard'
    _description = 'Claim Error Wizard'

    error_message = fields.Text(string='Error', readonly=True, required=True)

    def action_ok(self):
        return {'type': 'ir.actions.act_window_close'}
