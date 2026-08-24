from odoo import fields, models


class SupplierTypeSetupWizard(models.TransientModel):
    _inherit = 'ab_supplier_type_setup_wizard'

    supplier_section = fields.Selection(
        selection=[
            ('medicine', 'Medicine'),
            ('cosmetics', 'Cosmetics'),
            ('medical_preparations', 'Medical Preparations'),
            ('supplies', 'Supplies'),
            ('imported_medicine', 'Imported Medicine'),
            ('imported_cosmetics', 'Imported Cosmetics'),
        ],
        string='Section',
    )

    def action_confirm(self):
        self.claim_id.sudo().write({
            'supplier_type': self.supplier_type,
            'supplier_section': self.supplier_section,
        })
        return {'type': 'ir.actions.act_window_close'}
