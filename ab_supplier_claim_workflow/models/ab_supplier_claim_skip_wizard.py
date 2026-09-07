from odoo import fields, models


class SupplierClaimSkipWizard(models.TransientModel):
    _name = 'ab_supplier_claim_skip_wizard'
    _description = 'Skip Inventory and Purchase Reviews'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, readonly=True)
    reason = fields.Text(string='Skip Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        return self.claim_id._skip_inventory_purchase(self.reason)
