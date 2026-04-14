import datetime

from odoo import api, fields, models
from odoo.tools.translate import _


class AbInventoryAdjustProduct(models.Model):
    _name = 'ab_inventory_adjust_product'
    _description = 'ab_inventory_adjust_product'

    header_id = fields.Many2one('ab_inventory_adjust_header', ondelete='cascade')
    product_id = fields.Many2one('ab_product')
    code = fields.Char(related='product_id.code')
    inv_qty = fields.Float(compute='_compute_inventory_analysis')
    act_qty = fields.Float(digits=(10, 2),
                           store=True,
                           readonly=False)
    price_count = fields.Integer(compute='_compute_inventory_analysis')
    adjusted_before = fields.Boolean(compute='_compute_adjusted_before')

    @api.depends('product_id')
    def _compute_inventory_analysis(self):
        for rec in self:
            inv_lines = self.env['ab_inventory_eplus'].search([
                ('product_id', '=', rec.product_id.id),
                ('store_id', '=', rec.header_id.store_id.id),
            ])
            qty = sum(line.qty for line in inv_lines)
            rec.inv_qty = qty

            rec.price_count = len(set(inv_lines.filtered(lambda r: r.qty > 0).mapped('sell_price')))

    @api.depends('product_id')
    def _compute_adjusted_before(self):
        for rec in self:
            adjusted_before = False
            exist = self.env['ab_inventory_adjust_line'].search([
                ('header_id.status', '=', 'done'),
                ('product_id', '=', rec.product_id.id),
                ('store_id', '=', rec.header_id.store_id.id),
                ('create_date', '>', datetime.date.today() - datetime.timedelta(days=self.header_id.last_adjust_days)),
            ])
            if exist:
                adjusted_before = True

            rec.adjusted_before = adjusted_before

    @api.onchange('act_qty')
    def _onchange_qty(self):
        if self.act_qty > 99999:
            # Display a warning message
            return {
                'warning': {
                    'title': "Quantity Warning",
                    'message': "The quantity cannot exceed 99999.",
                }
            }

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.act_qty = self.inv_qty
