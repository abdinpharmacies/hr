from odoo import api, fields, models, _


class StockDist(models.Model):
    _name = 'ab_stock_recycling_dist'
    _description = 'ab_stock_recycling_dist'

    to_store_id = fields.Many2one('ab_store')
    from_store_id = fields.Many2one('ab_store')
    item_id = fields.Many2one('ab_product')
    item_code = fields.Char(related='item_id.code')
    item_price = fields.Float(related='item_id.default_price', string='Price')
    qty = fields.Float(default=0, digits=(16, 1))
    stock_line_id = fields.Many2one('ab_stock_recycling_line', string='From Stock', ondelete='cascade')
    need_line_id = fields.Many2one('ab_stock_recycling_need', string='According To Need', ondelete='cascade')
    header_id = fields.Many2one('ab_stock_recycling_header', required=True, ondelete='cascade')
    file_source = fields.Char()
