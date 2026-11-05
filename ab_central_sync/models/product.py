"""Inventory quantities use the product UoM category reference, without legacy packs."""
from decimal import Decimal

from odoo import models, _
from odoo.exceptions import ValidationError


class Product(models.Model):
    _inherit = 'ab_product'

    def _stock_reference_unit(self):
        self.ensure_one()
        reference = self.uom_category_id.uom_ids.filtered(lambda unit: unit.active and unit.uom_type == 'reference')
        if len(reference) != 1 or reference.factor != 1:
            raise ValidationError(_('The product requires one active reference unit with factor 1.'))
        return reference

    def _stock_unit_factor(self, unit):
        self.ensure_one()
        if unit._name != 'ab_product_uom':
            raise ValidationError(_('Stock conversion requires a product unit of measure.'))
        self.check_access('read')
        unit.check_access('read')
        reference = self._stock_reference_unit()
        if len(unit) != 1 or not unit.active or unit.category_id != reference.category_id:
            raise ValidationError(_('Select an active unit from the product unit category.'))
        factor = Decimal(str(unit.factor))
        if not factor.is_finite() or factor <= 0:
            raise ValidationError(_('Unit conversion factors must be positive and finite.'))
        return factor
