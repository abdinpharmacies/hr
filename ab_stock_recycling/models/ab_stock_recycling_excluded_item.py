from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class ExcludedItems(models.Model):
    _name = 'ab_stock_recycling_excluded_item'
    _description = 'ab_stock_recycling_excluded_item'

    item_id = fields.Many2one('ab_product')
    item_code = fields.Char(related='item_id.code')
    exclusion_reason = fields.Selection(
        selection=[
            ('custom', 'Custom'),
            ('new_item', 'New Item'),
            ('xxx', 'XXX'),
            ('@', '@'),
        ], default='custom')

    _ab_stock_recycling_excluded_item_item_id_unique = models.Constraint(
        'UNIQUE(item_id)',
        'ITEM CAN NOT BE DUPLICATED!',
    )
