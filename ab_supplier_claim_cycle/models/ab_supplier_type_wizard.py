from odoo import _, api, fields, models


class SupplierTypeSetupWizard(models.TransientModel):
    _name = 'ab.supplier.type.setup.wizard'
    _description = 'Supplier Type Setup Wizard'

    supplier_id = fields.Many2one('ab_costcenter', string='Supplier', required=True, readonly=True)
    claim_id = fields.Many2one('ab_supplier_claim_cycle', string='Claim', required=True, readonly=True)
    supplier_type = fields.Selection(
        selection=[
            ('advance_payment', 'Advance Payment'),
            ('withholding_tax', 'Withholding Tax'),
            ('non_taxable', 'Non-Taxable'),
        ],
        string='Supplier Type',
        required=True,
    )

    def action_confirm(self):
        self.claim_id.sudo().supplier_type = self.supplier_type
        return {'type': 'ir.actions.act_window_close'}
