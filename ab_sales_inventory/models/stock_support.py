"""Branch store scope and product units without a local inventory ledger."""
from decimal import Decimal, InvalidOperation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class ResUsers(models.Model):
    _inherit = 'res.users'

    inventory_store_ids = fields.Many2many(
        'ab_store', 'ab_inventory_user_store_rel', 'user_id', 'store_id',
        string='Inventory Stores',
    )

    def write(self, vals):
        if 'inventory_store_ids' in vals and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only administrators can assign inventory stores.'))
        return super().write(vals)


class Store(models.Model):
    _inherit = 'ab_store'

    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)

    @api.model_create_multi
    def create(self, vals_list):
        if any('company_id' in vals for vals in vals_list) and not self.env.is_system():
            raise AccessError(_('Only administrators can assign a store company.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'company_id' in vals and not self.env.is_system():
            raise AccessError(_('Only administrators can assign a store company.'))
        return super().write(vals)

    def _lock_stock_scope(self):
        self.sorted('id').lock_for_update(allow_referencing=True)


class Product(models.Model):
    _inherit = 'ab_product'

    def _validate_stock_quantity(self, qty):
        self.ensure_one()
        try:
            amount = Decimal(str(qty))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(_('Stock quantities must be positive reference-unit amounts.')) from None
        if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -8:
            raise ValidationError(_('Stock quantities must be positive reference-unit amounts with at most eight decimal places.'))
        return float(amount)

    def _stock_reference_unit(self):
        self.ensure_one()
        reference = self.uom_category_id.uom_ids.filtered(lambda unit: unit.active and unit.uom_type == 'reference')
        if len(reference) != 1 or reference.factor != 1:
            raise ValidationError(_('The product requires one active reference unit with factor 1.'))
        return reference

    def _stock_unit_factor(self, unit):
        self.ensure_one()
        if unit._name != 'ab_product_uom' or len(unit) != 1 or not unit.active or unit.category_id != self.uom_category_id:
            raise ValidationError(_('Select an active unit from the product unit category.'))
        factor = Decimal(str(unit.factor))
        if not factor.is_finite() or factor <= 0:
            raise ValidationError(_('Unit conversion factors must be positive and finite.'))
        return factor

    def _to_stock_quantity(self, qty, unit):
        return self._validate_stock_quantity(Decimal(str(qty)) * self._stock_unit_factor(unit))
