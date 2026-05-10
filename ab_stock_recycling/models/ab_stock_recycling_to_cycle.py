from odoo import api, fields, models, _


class AbStockRecyclingToCycle(models.Model):
    _name = 'ab_stock_recycling_to_cycle'
    _description = 'ab_stock_recycling_to_cycle'

    product_id = fields.Many2one('ab_product')
    qty = fields.Float(digits=(10, 2))
    store_id = fields.Many2one('ab_store')
    cycle_date = fields.Date()
    cycle_type = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')])
    is_done = fields.Boolean()
