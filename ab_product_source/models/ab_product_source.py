import re

from odoo import api, fields, models
from odoo.tools.translate import _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError


class AbdinProductsSource(models.Model):
    _name = 'ab_product_source'
    _inherit = ['ab_product_template']
    _description = 'Products Source For Purchasing And Opening Balance'
    _rec_name = 'product_id'

    exp_date = fields.Date(
        default=lambda self: self._compute_default_exp_date())
    price = fields.Float(digits=(16, 3), required=True)

    purchase_price = fields.Float(required=True, digits=(16, 3))

    extra_discount_percentage = fields.Float(digits=(5, 3))

    bonus = fields.Integer()

    product_code = fields.Char(related='product_id.code')

    taxes_ids = fields.Many2many(comodel_name='ab_taxes', relation='ab_product_source_tax_rel',
                                 column1='source_id', column2='tax_id', string="Taxes", ondelete='restrict',
                                 required=True)

    unit_taxes_value = fields.Float(digits=(10, 3), compute='_compute_unit_taxes_value')

    unit_cost = fields.Float(digits=(16, 3), compute='_compute_unit_cost')

    source_model = fields.Char(index=True)
    no_delete = fields.Boolean(default=False)

    @api.depends_context('source_name')
    @api.depends(
        'product_id.name',
        'exp_date',
        'price',
        'uom_id.unit_size',
        'product_id.unit_l_id.unit_no',
        'product_id.unit_m_id.unit_no',
        'product_id.unit_s_id.unit_no',
    )
    def _compute_display_name(self):
        source_name = self.env.context.get('source_name')
        for rec in self:
            source_format = f"{rec.product_id.name} [{rec.id}]"
            if source_name == 'exp_date':
                source_format = f"{rec.exp_date} ({rec.convert_price(unit_size='large')} L.E.)"
            rec.display_name = source_format

    @api.model
    def _search_display_name(self, operator, value):
        name = value or ''
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        domain = [('product_id.name', '=ilike', new_name)]
        if name:
            product_ids = self.search(
                ['|', ('product_id.barcode_ids', '=ilike', name), ('product_id.code', '=ilike', name)]
            )
            if product_ids:
                domain = [('product_id.id', 'in', product_ids.ids)]
        return domain

    def _compute_unit_cost(self):
        for rec in self:
            discount_percent = rec.extra_discount_percentage / 100
            rec.unit_cost = rec.purchase_price * (1 - discount_percent) + rec.unit_taxes_value

    def _compute_default_exp_date(self):
        return fields.Date.today().replace(day=1, month=6) + relativedelta(years=3)

    @api.constrains('price')
    def constrains_price_cost(self):
        if self.env.context.get('eplus_replication'):
            return
        for rec in self:
            if rec.price < rec.unit_cost:
                raise ValidationError(
                    _(f'{rec.product_id.display_name} -- The cost of the product must be less than the selling price'))

    @api.depends('purchase_price', 'taxes_ids.percentage', 'taxes_ids.apply_on_total', 'extra_discount_percentage')
    def _compute_unit_taxes_value(self):
        for rec in self:
            extra_discount_percentage = rec.extra_discount_percentage / 100
            net_purchase_price = rec.purchase_price * (1 - extra_discount_percentage)

            taxes_on_purchase = sum(net_purchase_price * tax.percentage / 100
                                    for tax in rec.taxes_ids
                                    if not tax.apply_on_total)

            taxes_on_total = sum((net_purchase_price + taxes_on_purchase) * tax.percentage / 100
                                 for tax in rec.taxes_ids
                                 if tax.apply_on_total)

            rec.unit_taxes_value = taxes_on_purchase + taxes_on_total

    def convert_price(self, unit_size):
        unit_no = {'large': self.product_id.unit_l_id.unit_no,
                   'medium': self.product_id.unit_m_id.unit_no,
                   'small': self.product_id.unit_s_id.unit_no}
        large_unit_price = self.price * unit_no.get(self.uom_id.unit_size, 1)
        if unit_no.get(unit_size, 1):
            return large_unit_price / unit_no.get(unit_size, 1)
        else:
            return 0.0

    def convert_cost(self, unit_size):
        unit_no = {'large': 1,
                   'medium': self.product_id.unit_m_id.unit_no,
                   'small': self.product_id.unit_s_id.unit_no}
        large_unit_cost = self.unit_cost * unit_no.get(self.uom_id.unit_size, 1)
        if unit_no.get(unit_size, 1):
            return large_unit_cost / unit_no.get(unit_size, 1)
        else:
            return 0.0
