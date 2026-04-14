from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbdinInventoryEplusLine(models.Model):
    _name = 'ab_inventory_adjust_line'
    _description = 'ab_inventory_adjust_line'
    _order = 'product_id,c_id desc'

    header_id = fields.Many2one('ab_inventory_adjust_header', required=True, ondelete='cascade')
    inventory_line_id = fields.Many2one('ab_inventory_eplus', delegate=True, required=True, ondelete='cascade')
    new_qty = fields.Float(digits=(12, 3), required=True)
    new_sell_price = fields.Float(digits=(12, 3), required=True)
