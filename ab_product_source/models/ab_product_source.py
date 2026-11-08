import re

from odoo import api, fields, models, _
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

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.product_id.display_name} [{rec.id}]"

    def _name_search(self, name='', domain=None, operator='ilike', limit=None, order=None):
        domain = fields.Domain(domain or [])
        pattern = r"\*|  "
        new_name = re.sub(pattern, "%", name) + '%'
        name_domain = fields.Domain('product_id.name', '=ilike', new_name)
        if name:
            product_domain = (
                fields.Domain('product_id.barcode_ids', '=ilike', name)
                | fields.Domain('product_id.code', '=ilike', name)
            )
            product_ids = self.search(product_domain)
            if product_ids:
                name_domain = fields.Domain('id', 'in', product_ids.ids)
        return self._search(domain & name_domain, limit=limit, order=order)

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

    def convert_price(self, to_unit):
        self.ensure_one()
        if not self.uom_id or not to_unit or self.uom_id.category_id != to_unit.category_id:
            return 0.0
        return self.price * to_unit.factor / self.uom_id.factor

    def convert_cost(self, to_unit):
        self.ensure_one()
        if not self.uom_id or not to_unit or self.uom_id.category_id != to_unit.category_id:
            return 0.0
        return self.unit_cost * to_unit.factor / self.uom_id.factor
