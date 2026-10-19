from decimal import Decimal, InvalidOperation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Product(models.Model):
    _inherit = 'ab_product'

    stock_sales_unit_id = fields.Many2one(
        'ab_product_uom', string='Sales Unit for One Stock Unit', ondelete='restrict',
        domain="[('category_id', '=', uom_category_id)]",
        help='Select the sales unit equivalent to one smallest inventory unit.',
    )
    stock_sales_reference_unit_id = fields.Many2one(
        'ab_product_uom', string='Stock Conversion Sales Unit', ondelete='restrict',
        domain="[('category_id', '=', uom_category_id)]",
    )
    stock_units_per_reference_unit = fields.Integer(
        string='Smallest Stock Units per Sales Unit', default=1,
    )

    def _validate_stock_quantity(self, qty):
        self.ensure_one()
        try:
            amount = Decimal(str(qty))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(_('Stock quantities must be positive whole smallest units.')) from None
        if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
            raise ValidationError(_('Stock quantities must be positive whole smallest units.'))
        return int(amount)

    def _stock_unit_factor(self, unit):
        self.ensure_one()
        self.check_access('read')
        unit.check_access('read')
        smallest = self.stock_sales_unit_id or self.stock_sales_reference_unit_id
        if (not unit or not smallest or not self.unit_s_id or self.unit_s_id.unit_size != 'small'
                or unit.category_id != smallest.category_id or unit.category_id != self.uom_category_id):
            raise ValidationError(_('Configure the sales unit equivalent to one smallest stock unit.'))
        values = [Decimal(str(value)) for value in (unit.factor, smallest.factor)]
        if any(not value.is_finite() or value <= 0 for value in values):
            raise ValidationError(_('Unit conversion factors must be positive and finite.'))
        multiplier = 1 if self.stock_sales_unit_id else self.stock_units_per_reference_unit
        if multiplier <= 0:
            raise ValidationError(_('Unit conversion factors must be positive and finite.'))
        return values[0] * multiplier / values[1]

    def _to_stock_quantity(self, qty, unit):
        self.ensure_one()
        return self._validate_stock_quantity(Decimal(str(qty)) * self._stock_unit_factor(unit))

    @api.constrains('stock_sales_unit_id', 'stock_sales_reference_unit_id',
                    'stock_units_per_reference_unit', 'uom_category_id')
    def _check_stock_sales_unit(self):
        for product in self:
            if product.stock_sales_unit_id and product.stock_sales_reference_unit_id:
                raise ValidationError(_('Choose either a smallest sales unit or a reference sales unit mapping.'))
            unit = product.stock_sales_unit_id or product.stock_sales_reference_unit_id
            if unit:
                product._stock_unit_factor(unit)

    @api.model_create_multi
    def create(self, vals_list):
        mapping_fields = {'stock_sales_unit_id', 'stock_sales_reference_unit_id', 'stock_units_per_reference_unit'}
        if any(mapping_fields & vals.keys() for vals in vals_list):
            self._check_mapping_manager()
        return super().create(vals_list)

    def _check_mapping_manager(self):
        if not (self.env.is_system() or self.env.user.has_group('ab_inventory.group_inventory_manager')):
            raise AccessError(_('Only inventory managers can configure stock unit mappings.'))

    def write(self, vals):
        mapping_fields = {'stock_sales_unit_id', 'stock_sales_reference_unit_id', 'stock_units_per_reference_unit'}
        if mapping_fields & vals.keys():
            self._check_mapping_manager()
            self.check_access('write')
            self.lock_for_update(allow_referencing=True)
            changed = self.filtered(lambda product: any(
                (product[key].id if product._fields[key].type == 'many2one' else product[key]) != vals[key]
                for key in mapping_fields & vals.keys()))
            if changed and self.env['ab_inventory'].sudo().search_count(fields.Domain('product_id', 'in', changed.ids), limit=1):
                raise ValidationError(_('Stock unit mappings cannot change after inventory activity.'))
        return super().write(vals)
