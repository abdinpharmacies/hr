from odoo import api, fields, models, _


class Inventory(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(selection_add=[
        ('ab_purchase_ob_line', 'Opening Balance Line'),
    ],
        required=True,
        ondelete={
            'ab_purchase_ob_line': 'set default',
        })
