import math
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Taxes(models.Model):
    _name = 'ab_taxes'
    _description = 'ab_taxes'
    name = fields.Char()
    percentage = fields.Float()
    status = fields.Selection(selection=[('purchase', 'Purchase'), ('sales', 'Sales'), ('all', 'All')],
                              default='purchase')
    active = fields.Boolean(default=True)
    apply_on_total = fields.Boolean()

    inventory_cost = fields.Boolean(string='Included in Inventory Cost', default=True)

    @api.constrains('percentage')
    def _check_percentage(self):
        if any(not math.isfinite(tax.percentage) or abs(tax.percentage) > 100 for tax in self):
            raise ValidationError(_('Tax percentages must be finite and between -100 and 100.'))

    def _compute_purchase_values(self, purchase_price, qty=1, bonus=0, discount=0, policy=None):
        self.check_access('read')
        values = [purchase_price, qty, bonus, discount]
        if any(not math.isfinite(value) or value < 0 for value in values) or discount > 100:
            raise ValidationError(_('Purchase prices and quantities must be finite and non-negative; discounts must be between 0 and 100.'))
        if policy:
            policy.ensure_one()
            policy.check_access('read')
            if policy.company_id != self.env.company:
                raise ValidationError(_('The purchase tax policy must belong to the current company.'))
        digits = policy.rounding_digits if policy else 3
        tax_bonus = policy.tax_bonus if policy else True
        before_discount = policy.discount_timing == 'after_tax' if policy else False
        quantum = Decimal(1).scaleb(-digits)
        def rounded(value):
            return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
        base = purchase_price if before_discount else purchase_price * (1 - discount / 100)
        quantity = qty + bonus if tax_bonus else qty
        ordinary = sum(base * tax.percentage / 100 for tax in self if not tax.apply_on_total)
        components = []
        for tax in self.sorted('id'):
            unit = (base + ordinary if tax.apply_on_total else base) * tax.percentage / 100
            components.append({'id': tax.id, 'name': tax.name, 'percentage': tax.percentage,
                               'apply_on_total': tax.apply_on_total, 'inventory_cost': tax.inventory_cost,
                               'unit_amount': unit, 'amount': rounded(unit * quantity)})
        raw_untaxed = purchase_price * qty * (1 - discount / 100)
        untaxed = rounded(raw_untaxed)
        tax_total = sum(item['amount'] for item in components)
        inventory_tax = sum(item['amount'] for item in components if item['inventory_cost'])
        if untaxed + tax_total < 0 or untaxed + inventory_tax < 0:
            raise ValidationError(_('Tax calculations cannot produce negative purchase or inventory values.'))
        gross_quantity = qty + bonus
        return {'untaxed': untaxed, 'total_tax': rounded(tax_total),
                'inventory_tax': rounded(inventory_tax), 'separate_tax': rounded(tax_total - inventory_tax),
                'total': rounded(untaxed + tax_total),
                'unit_tax': sum(item['unit_amount'] for item in components),
                'unit_cost': purchase_price * (1 - discount / 100) + sum(item['unit_amount'] for item in components if item['inventory_cost']),
                'stock_unit_cost': (untaxed + inventory_tax) / gross_quantity if gross_quantity else 0,
                'components': components, 'rounding': rounded(untaxed + tax_total - raw_untaxed - sum(item['unit_amount'] * quantity for item in components)),
                'policy': {'id': policy.id if policy else False, 'rounding_digits': digits,
                           'tax_bonus': tax_bonus, 'discount_timing': 'after_tax' if before_discount else 'before_tax',
                           'approval_reference': policy.approval_reference if policy else False}}


class PurchaseTaxPolicy(models.Model):
    _name = 'ab_purchase_tax_policy'
    _description = 'Purchase Tax Policy'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    tax_bonus = fields.Boolean(string='Tax Bonus Quantities', default=True)
    discount_timing = fields.Selection([('before_tax', 'Discount Before Tax'), ('after_tax', 'Discount After Tax')], required=True, default='before_tax')
    rounding_digits = fields.Integer(default=3, required=True)
    approval_reference = fields.Char(string='Finance Approval Reference', required=True)

    @api.constrains('rounding_digits', 'approval_reference')
    def _check_policy(self):
        for policy in self:
            if policy.rounding_digits not in range(7) or not (policy.approval_reference or '').strip():
                raise ValidationError(_('Provide a finance approval reference and rounding digits between 0 and 6.'))
