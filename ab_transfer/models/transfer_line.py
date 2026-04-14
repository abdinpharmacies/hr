# -*- coding: utf-8 -*-
import json
from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError


class TransferLine(models.Model):
    _name = 'ab_transfer_line'
    _description = 'ab_transfer_line'
    _inherit = ['ab_product_template']

    header_id = fields.Many2one(
        'ab_transfer_header', required=True, ondelete='cascade')
    source_id = fields.Many2one('ab_product_source', required=True)
    # exp_date = fields.Date(related='inventory_id.source_id.exp_date')
    balance = fields.Float(compute='_compute_balance', string='Total Balance')
    balance_per_price = fields.Float(compute='_compute_balance', string='Balance')

    price = fields.Float(compute='_compute_price')
    cost = fields.Float(compute='_compute_cost')
    line_price = fields.Float(compute='_compute_price')
    line_cost = fields.Float(compute='_compute_cost')
    header_status = fields.Selection(related='header_id.status')
    qty_rejected = fields.Float(default=0)
    rejected_reason = fields.Selection(selection=[(
        'wrong_product', 'Wrong Product'), ('wrong_quantity', 'Wrong Quantity')])
    source_id_domain = fields.Char(
        compute="_compute_source_id_domain", readonly=True, store=False)
    uom_id_domain = fields.Char(
        compute="_compute_uom_id_domain", readonly=True, store=False)

    @api.depends('product_id')
    def _compute_uom_id_domain(self):
        for rec in self:
            domain = rec._get_uom_id_domain()
            rec.uom_id_domain = json.dumps(domain)

    def _get_uom_id_domain(self):
        uom_list = [self.product_id.unit_l_id.id]
        if self.product_id.unit_m_id.unit_no > 1:
            uom_list.append(self.product_id.unit_m_id.id)
        if self.product_id.unit_s_id.unit_no > 1:
            uom_list.append(self.product_id.unit_s_id.id)

        return [('id', 'in', uom_list)]

    @api.depends('header_id.store_id', 'product_id', 'uom_id', 'source_id')
    def _compute_balance(self):
        for rec in self:
            inventory = self.env['ab_inventory'].search([
                ('store_id', '=', rec.header_id.store_id.id),
                ('product_id', '=', rec.product_id.id),
                ('status', '=ilike', 'pending_main'),
            ])

            inventory_per_price = self.env['ab_inventory'].search([
                ('store_id', '=', rec.header_id.store_id.id),
                ('product_id', '=', rec.product_id.id),
                ('source_id.price', '=', rec.source_id.price),
                ('source_id.exp_date', '=', rec.source_id.exp_date),
                ('status', '=ilike', 'pending_main'),
            ])

            balance_s_unit = sum(inv.qty for inv in inventory)
            balance_per_price_s_unit = sum(inv.qty for inv in inventory_per_price)

            unit_s_no = rec.product_id.unit_s_id.unit_no
            unit_m_no = rec.product_id.unit_m_id.unit_no
            balance = 0
            balance_per_price = 0
            if rec.uom_id.unit_size == 'large':
                balance_per_price = balance_per_price_s_unit / unit_s_no
                balance = balance_s_unit / unit_s_no
            if rec.uom_id.unit_size == 'medium':
                balance = balance_s_unit * unit_m_no / unit_s_no
                balance_per_price = balance_per_price_s_unit * unit_m_no / unit_s_no
            if rec.uom_id.unit_size == 'small':
                balance = balance_s_unit
                balance_per_price = balance_per_price_s_unit

            rec.balance = unit_s_no and balance or 0

            rec.balance_per_price = balance_per_price

    @api.depends('header_id', 'product_id')
    def _compute_source_id_domain(self):
        for rec in self:
            if rec.product_id and rec.header_id.store_id:
                self._cr.execute("""
                select min(ps.id),ps.product_id,inv.store_id,ps.price,ps.exp_date,sum(inv.qty)
                from ab_product_source ps
                join ab_inventory inv
                on ps.id = inv.source_id
                where inv.store_id=%s and ps.product_id=%s and inv.status ='pending_main'
                group by ps.product_id,inv.store_id,ps.price,ps.exp_date having sum(inv.qty)>0""",
                                 (rec.header_id.store_id.id, rec.product_id.id))
                source_ids = self._cr.fetchall()
                source_ids = [rec[0] for rec in source_ids]
            else:
                source_ids = []
            rec.source_id_domain = json.dumps(
                [('id', 'in', source_ids)]
            )

    @api.onchange('product_id')
    def _default_source_id_uom_id(self):
        for rec in self:
            if rec.product_id and rec.header_id.store_id:
                rec.uom_id = rec.product_id.unit_l_id.id
                self._cr.execute("""
                select min(ps.id),ps.product_id,inv.source_id,inv.store_id,sum(inv.qty)
                from ab_product_source ps join ab_inventory inv on ps.id = inv.source_id
                where inv.store_id=%s and ps.product_id=%s and inv.status ='pending_main'
                group by ps.product_id,inv.source_id,inv.store_id having sum(inv.qty)>0""",
                                 (rec.header_id.store_id.id, rec.product_id.id))
                source_ids = self._cr.fetchall()
                source_ids = [rec[0] for rec in source_ids]
                rec.source_id = source_ids and source_ids[0] or []

    @api.depends('qty', 'uom_id', 'source_id')
    def _compute_cost(self):
        for rec in self:
            rec.cost = 0.0
            rec.line_cost = 0.0
            if rec.uom_id.unit_size:
                unit_cost = rec.source_id.convert_cost(rec.uom_id.unit_size)
                rec.cost = unit_cost
                rec.line_cost = unit_cost * rec.qty

    @api.depends('qty', 'uom_id', 'source_id')
    def _compute_price(self):
        for rec in self:
            rec.price = 0.0
            rec.line_price = 0.0
            if rec.uom_id.unit_size:
                unit_price = rec.source_id.convert_price(rec.uom_id.unit_size)
                rec.price = unit_price
                rec.line_price = unit_price * rec.qty

    @api.onchange('qty')
    def _onchange_qty_redistribute_wiz(self):
        for rec in self:
            if rec.balance_per_price < rec.qty:
                print("yes, please open wizard ...")
