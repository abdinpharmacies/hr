import datetime
import logging
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

PLACEHOLDER = '%s'

_logger = logging.getLogger(__name__)


class StockNeed(models.Model):
    _name = 'ab_stock_recycling_need'
    _description = 'ab_stock_recycling_need'
    _order = 'qty DESC'

    store_id = fields.Many2one('ab_store', required=True, index=True)
    item_id = fields.Many2one('ab_product', required=True, index=True)
    item_code = fields.Char(related='item_id.code')
    item_price = fields.Float(related='item_id.default_price', string='Item Price')
    item_cost = fields.Float(related='item_id.default_cost', string='Item Cost')
    supplier_id = fields.Many2one(related='item_id.company_id')
    parent_item_id = fields.Many2one('ab_product', related='item_id', string='Parent Item', store=True)
    parent_item_code = fields.Char(related='parent_item_id.code', string='Parent Code')
    qty = fields.Float(default=0, digits=(16, 1))
    balance = fields.Float(default=0, digits=(16, 1))
    sales_qty = fields.Float(default=0, digits=(16, 1))
    header_id = fields.Many2one('ab_stock_recycling_header', required=True, ondelete='cascade', index=True)
    given_qty = fields.Float(default=0, digits=(16, 1), readonly=True)
    total_price = fields.Float(compute='_compute_total_need_price')

    @api.depends('sales_qty', 'balance', 'qty')
    def _compute_display_name(self):
        for rec in self:
            name_items = [f"Sales:{rec.sales_qty}", f"Balance:{rec.balance}", f"Need:{rec.qty}"]
            rec.display_name = '/'.join(str(it) for it in name_items if it)

    @api.depends('item_price', 'qty')
    def _compute_total_need_price(self):
        for rec in self:
            rec.total_price = rec.item_price * rec.qty
