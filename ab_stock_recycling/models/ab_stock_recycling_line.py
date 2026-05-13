import datetime

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError

PLACEHOLDER = '?'

import logging

_logger = logging.getLogger(__name__)


class StockRecyclingLine(models.Model):
    _name = 'ab_stock_recycling_line'
    _description = 'ab_stock_recycling_line'
    header_id = fields.Many2one('ab_stock_recycling_header', required=True, ondelete='cascade', index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True)
    item_id = fields.Many2one('ab_product', required=True, index=True)
    item_code = fields.Char(related='item_id.code')
    item_price = fields.Float(related='item_id.default_price', string='Price')
    qty = fields.Float(default=0, digits=(16, 1), index=True, help="Quantity Before Distribution")
    sales_qty = fields.Float(default=0, digits=(16, 1))

    balance = fields.Float(default=0, digits=(16, 1))
    sales_x_qty = fields.Float(default=0, digits=(16, 1))
    last_trans_date = fields.Datetime(index=True)
    target_qty = fields.Float(compute='_compute_target_qty')

    exp_date = fields.Date()
    file_source = fields.Char()
    distributed_qty = fields.Float(default=0, digits=(16, 1), readonly=True, index=True)
    over_need_qty = fields.Float(compute='_compute_over_need_qty',
                                 help="=Quantity Before Distribution - Distributed Quantity")
    
    is_consumed = fields.Boolean(compute='_compute_is_consumed', search='_search_is_consumed')

    reason_for_keeping_item = fields.Selection([
        ("on_consignment", "On Consignment"),
        ("prescription_item", "Prescription Item"),
        ("seasonal_item", "Seasonal Item"),
        ("expected_fast_moving_item", "Expected Fast Moving Item")
    ], string="Reason For Keeping Item")

    notes = fields.Text(string="Notes")

    @api.depends('balance', 'over_need_qty')
    def _compute_target_qty(self):
        for rec in self:
            if rec.sales_x_qty:
                rec.target_qty = rec.over_need_qty
            else:
                rec.target_qty = rec.balance

    @api.depends('qty', 'distributed_qty')
    def _compute_is_consumed(self):
        for rec in self:
            rec.is_consumed = rec.qty == rec.distributed_qty

    def _search_is_consumed(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        self.env.cr.execute("select id from ab_stock_recycling_line where qty=distributed_qty")
        ids = [row[0] for row in self.env.cr.fetchall()]

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    @api.depends('qty', 'distributed_qty')
    def _compute_over_need_qty(self):
        for rec in self:
            rec.over_need_qty = rec.qty - rec.distributed_qty

    @api.depends('file_source', 'qty', 'exp_date')
    def _compute_display_name(self):
        for rec in self:
            file_source = rec.file_source or ''
            qty = rec.qty or ''
            exp_date = rec.exp_date or ''
            name_items = [
                _("Source:%s") % file_source,
                _("Target qty:%s") % qty,
                _("Exp:%s") % exp_date,
            ]
            rec.display_name = '/'.join(str(it) for it in name_items if it.split(":")[-1])
