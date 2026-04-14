from odoo import api, fields, models
from odoo.tools.translate import _


class InventoryEplus(models.Model):
    _name = 'ab_inventory_eplus'
    _description = 'ab_inventory_eplus'

    product_id = fields.Many2one('ab_product', required=True, index=True)
    code = fields.Char(related='product_id.code')
    store_id = fields.Many2one('ab_store', required=True, index=True)
    c_id = fields.Integer(required=True, index=True)
    qty = fields.Float(digits=(12, 3), required=True)
    sell_price = fields.Float(digits=(12, 3), required=True, readonly=True)
    pharm_price = fields.Float(digits=(12, 3), required=True, readonly=True)
    sell_tax = fields.Float(digits=(12, 3), required=True, readonly=True)
    cost = fields.Float(digits=(12, 3), required=True)
    itm_expiry_date = fields.Datetime()
    last_update_date = fields.Datetime(index=True)
