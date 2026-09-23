from odoo import api, fields, models, _


class Inventory(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(selection_add=[
        ('ab_purchase_line', 'Purchase Line'),
        ('ab_purchase_notice_line', 'Purchase Notice Line'),
    ],
        required=True,
        ondelete={
            'ab_purchase_line': 'set default',
            'ab_purchase_notice_line': 'set default',
        })


