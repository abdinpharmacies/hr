"""Product UoM metadata for newly posted synchronization inventory allocations."""
import math

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class Allocation(models.Model):
    _inherit = 'ab_sales_stock_allocation'

    # Keep the historical relation for old, immutable allocations only.
    uom_id = fields.Many2one(required=False)
    stock_uom_id = fields.Many2one('ab_product_uom', string='Inventory Product Unit', readonly=True, ondelete='restrict')

    @api.model
    def _stock_unit_values(self, product):
        return {'uom_id': False, 'stock_uom_id': product._stock_reference_unit().id}

    @api.model
    def _source_rows(self, store, product):
        self.env['ab_sales_backend']._check_store(store.id)
        product.check_access('read')
        balances = self.env['ab_inventory_process'].with_context(ab_sales_branch_scope=True).get_source_balances(store.id, product_id=product.id)
        sources = self.env['ab_product_source'].sudo().browse([sid for sid, qty in balances.items() if qty > 0])
        if any(not math.isfinite(source.price) or not math.isfinite(source.unit_cost) for source in sources):
            raise ValidationError(_('The stock source has invalid unit or price values.'))
        today = fields.Date.context_today(self)
        factor = float(product._stock_unit_factor(product.uom_id))
        return [{'source_id': source.id, 'source_identity': source.source_identity,
                 'qty': int(balances[source.id]), 'price': source.price / factor,
                 'cost': source.unit_cost / factor, 'expiry': source.exp_date}
                for source in sources if source.product_id == product and (not source.exp_date or source.exp_date >= today)]


class InventoryProcess(models.AbstractModel):
    _inherit = 'ab_inventory_process'

    @api.model
    def _smallest_unit_qty(self, rec, qty, sign):
        allocation = rec.allocation_id if rec._name == 'ab_sales_stock_reversal' else rec
        if allocation._name == 'ab_sales_stock_allocation' and allocation.stock_uom_id:
            if isinstance(sign, bool) or sign not in (-1, 1):
                raise ValidationError(_('Inventory direction must be +1 or -1.'))
            return sign * allocation.sale_line_id.product_id._validate_stock_quantity(qty)
        return super()._smallest_unit_qty(rec, qty, sign)


class Reversal(models.Model):
    _inherit = 'ab_sales_stock_reversal'

    uom_id = fields.Many2one(required=False)
