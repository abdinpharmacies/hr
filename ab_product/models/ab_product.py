import math

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError, ValidationError
import re


class AbdinProduct(models.Model):
    _name = 'ab_product'
    _description = 'Abdin Product'
    _inherits = {'ab_product_card': 'product_card_id'}

    product_card_id = fields.Many2one('ab_product_card', required=True, delegate=True, ondelete='restrict')
    product_card_name = fields.Char(related='product_card_id.name', readonly=False, string="Name")
    name = fields.Char(store=True, readonly=True, string="Full Name")
    default_price = fields.Float(digits=(16, 2), default=0)
    default_reference_price = fields.Float(digits=(16, 2), default=0,
                                           compute='_compute_default_reference',
                                           store=True,
                                           compute_sudo=True)
    default_cost = fields.Float(digits=(16, 2), default=0)
    default_reference_cost = fields.Float(digits=(16, 2), default=0,
                                          compute='_compute_default_reference',
                                          store=True,
                                          compute_sudo=True)
    tag_ids = fields.Many2many(comodel_name='ab_product_tag', relation='ab_product_product_tag', column1='product_id',
                               column2='tag_id')
    barcode_ids = fields.Many2many(comodel_name='ab_product_barcode', relation='ab_product_barcode_rel',
                                   column1='product_id', column2='barcode_id')
    unit_l_id = fields.Many2one('ab_uom', domain=[('unit_size', '=', 'large')], required=False)
    unit_m_id = fields.Many2one('ab_uom', domain=[('unit_size', '=', 'medium')], required=False)
    unit_s_id = fields.Many2one('ab_uom', domain=[('unit_size', '=', 'small')], required=False)
    uom_category_id = fields.Many2one('ab_product_uom_category', string='UoM Category')

    uom_id = fields.Many2one(
        'ab_product_uom',
        string='Default UoM In Sales',
        domain="[('category_id', '=', uom_category_id)]",
    )

    uom_pur_id = fields.Many2one(
        'ab_product_uom',
        string='Default UoM In Purchase',
        domain="[('category_id', '=', uom_category_id)]",
    )
    uom_ids = fields.Many2many('ab_uom', compute='_compute_uom_ids')
    allow_sale = fields.Boolean(default=True)
    allow_purchase = fields.Boolean(default=True)
    active = fields.Boolean(default=True)
    code = fields.Char(index=True)
    allow_sell_fraction = fields.Boolean(default=False)
    u_s_num = fields.Integer(default=1)
    u_s_name = fields.Char()

    product_search = fields.Char(compute='_compute_product_search', search='_search_product_search')

    @api.depends('default_price', 'default_cost', 'u_s_num')
    def _compute_default_reference(self):
        for rec in self:
            rec.default_reference_price = rec.default_price / (rec.u_s_num or 1)
            rec.default_reference_cost = rec.default_cost / (rec.u_s_num or 1)

    def _compute_product_search(self):
        for rec in self:
            rec.product_search = ''

    @api.model
    def _search_product_search(self, operator, val):
        domain = []
        if val:
            val = f"{val.replace('*', '%').replace('  ', '%')}%"
            domain = [('name', '=ilike', val)]

            any_result = self.search(domain, limit=1)
            if not any_result:
                val = val.replace(' ', '%')
                domain = [('name', '=ilike', val)]
            return domain
        return [(0, '=', 1)]

    @api.depends('unit_l_id', 'unit_m_id', 'unit_s_id')
    def _compute_uom_ids(self):
        for rec in self:
            rec.uom_ids = self.env['ab_uom'].sudo().search([('id', 'in', [
                rec.unit_l_id.id,
                rec.unit_m_id.id,
                rec.unit_s_id.id,
            ])])

    def qty_from_small(self, qty, unit_size):
        """
         :param unit_size: 'large', 'medium' or 'small'
         :param qty: absolute final inventory quantity
         :return: convert from small qty to other units.
         """
        if not (self and qty and unit_size):
            return 0

        self.ensure_one()
        unit_s_no = self.unit_s_id.unit_no
        unit_m_no = self.unit_m_id.unit_no
        if not (qty / unit_m_no).is_integer():
            raise ValidationError(_("CONVERTING FROM SMALL ERROR: SMALL QTY INCONSISTENT WITH MEDIUM QTY, "
                                    "Product ID: %d" % self.id))

        if unit_size == 'large':
            return qty / unit_s_no
        elif unit_size == 'medium':
            return qty * unit_m_no / unit_s_no
        else:  # 'small'
            return qty

    def qty_to_small(self, qty, unit_size):
        """
         :param unit_size: 'large', 'medium' or 'small'
         :param qty: absolute final inventory quantity
         :return: convert qty from other units to small.
         """
        if not (self and qty and unit_size):
            return 0

        self.ensure_one()
        unit_s_no = self.unit_s_id.unit_no
        unit_m_no = self.unit_m_id.unit_no
        # Consider Medium Unit
        if abs(int((qty * unit_m_no)) - qty * unit_m_no) > 0.1:
            raise ValidationError(_("CONVERTING TO SMALL ERROR: SMALL QTY INCONSISTENT WITH MEDIUM QTY, "
                                    "Product ID: %d" % self.id))

        if unit_size == 'large':
            qty_in_small = qty * unit_s_no
        elif unit_size == 'medium':
            qty_in_small = (qty * unit_s_no) / unit_m_no
        else:
            qty_in_small = qty

        # @todo FIX this
        qty_in_small = round(qty_in_small)

        return qty_in_small

    def btn_edit_product_main_data(self):
        self.ensure_one()
        return {
            'view_mode': 'form',
            'res_model': 'ab_product_card',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'res_id': self.product_card_id.id,
            'views': [[False, 'form']]
        }

    @api.model
    def _search_display_name(self, operator, value):
        name = value or ''
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        domain = [('name', '=ilike', new_name)]
        if name:
            product_ids = self.search(
                ['|', ('barcode_ids', '=ilike', name), ('code', '=ilike', name)]
            )
            if product_ids:
                domain = [('id', 'in', product_ids.ids)]
        return domain
