import math
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SalesStockAllocation(models.Model):
    _name = 'ab_sales_stock_allocation'
    _description = 'Sales Stock Allocation'
    _order = 'id'

    operation_key = fields.Char(required=True, readonly=True, index=True)
    sale_line_id = fields.Many2one('ab_sales_line', required=True, readonly=True, ondelete='restrict', index=True)
    return_line_id = fields.Many2one('ab_sales_return_line', readonly=True, ondelete='restrict', index=True)
    original_id = fields.Many2one('ab_sales_stock_allocation', readonly=True, ondelete='restrict', index=True)
    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict', index=True)
    source_id = fields.Many2one('ab_product_source', required=True, readonly=True, ondelete='restrict')
    uom_id = fields.Many2one('ab_product_uom', required=True, readonly=True, ondelete='restrict')
    sale_uom_id = fields.Many2one('ab_product_uom', readonly=True, ondelete='restrict')
    sale_qty = fields.Float(readonly=True, digits=(18, 8))
    unit_factor = fields.Float(readonly=True, digits=(18, 8))
    qty = fields.Float(required=True, readonly=True, digits=(24, 8))
    qty_smallest = fields.Float(readonly=True, digits=(24, 8))
    unit_price = fields.Float(readonly=True, digits=(18, 6))
    source_unit_price = fields.Float(readonly=True, digits=(18, 6))
    unit_cost = fields.Float(readonly=True, digits=(18, 6))
    _operation_unique = models.Constraint('UNIQUE(operation_key)', 'Stock allocation operation keys must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Stock allocations are created only by sale approval.'))

    def write(self, vals):
        raise AccessError(_('Posted stock allocations cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Posted stock allocations cannot be deleted.'))

    @api.model
    def _price_key(self, value):
        try:
            amount = Decimal(str(value or 0))
        except Exception:
            raise ValidationError(_('The stock source has invalid unit or price values.')) from None
        if not amount.is_finite():
            raise ValidationError(_('The stock source has invalid unit or price values.'))
        return amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @api.model
    def _source_rows(self, store, product):
        raise AccessError(_('This store is unavailable for native sales.'))

    @api.model
    def _build_sale_plan(self, sale):
        sale.ensure_one()
        available_by_source = {}
        rows_by_product = {}
        plans = []
        for line in sale.line_ids.sorted('id'):
            service = bool(line.product_id.is_service)
            if service:
                plans.append({'line': line, 'service': True, 'qty': line.qty, 'factor': 1.0,
                              'allocations': [], 'shortage': 0})
                continue
            qty_smallest = line.product_id._to_stock_quantity(line.qty, line.uom_id)
            factor = line.product_id._stock_unit_factor(line.uom_id)
            target_price = self._price_key(Decimal(str(line.sell_price)) / factor)
            if line.product_id.id not in rows_by_product:
                rows = self._source_rows(sale.store_id, line.product_id)
                rows_by_product[line.product_id.id] = rows
                available_by_source.update({row['source_id']: row['qty'] for row in rows})
            matching = [row for row in rows_by_product[line.product_id.id]
                        if self._price_key(row['price']) == target_price]
            matching.sort(key=lambda row: (
                not bool(row['expiry']),
                row['expiry'] or fields.Date.to_date('9999-12-31'),
                row['source_id'],
            ))
            remaining = qty_smallest
            allocations = []
            for row in matching:
                available = available_by_source.get(row['source_id'], 0)
                take = min(remaining, available)
                if take <= 0:
                    continue
                allocations.append(dict(row, take=take))
                available_by_source[row['source_id']] = available - take
                remaining -= take
                if not remaining:
                    break
            plans.append({
                'line': line,
                'service': False,
                'qty': qty_smallest,
                'factor': float(factor),
                'allocations': allocations,
                'shortage': remaining,
            })
        return plans

    @api.model
    def _validate_shortage_reasons(self, plans):
        missing = []
        for plan in plans:
            line = plan['line']
            if not plan['shortage']:
                continue
            if not line.unavailable_reason or (
                    line.unavailable_reason == 'other'
                    and not (line.unavailable_reason_other or '').strip()):
                missing.append(line.product_id.display_name)
        if missing:
            raise ValidationError(_(
                "Products sold without matching stock require a reason. If reason is 'Other', details are required:\n%s"
            ) % '\n'.join('- %s' % name for name in missing))

    @api.model
    def _stock_unit_values(self, product):
        return {'uom_id': product._stock_reference_unit().id}

    @api.model
    def _stock_context_unit_id(self, product):
        values = self._stock_unit_values(product)
        return values.get('stock_uom_id') or values.get('uom_id')

    @api.model
    def _post_sale_plan(self, sale, plans):
        raise AccessError(_('This store is unavailable for native sales.'))

    def _snapshot(self):
        return [{
            'allocation_id': rec.id,
            'source_id': rec.source_id.id,
            'sale_uom_id': rec.sale_uom_id.id,
            'sale_qty': rec.sale_qty,
            'unit_factor': rec.unit_factor,
            'qty': rec.qty_smallest,
            'unit_price': rec.unit_price,
            'source_unit_price': rec.source_unit_price,
            'unit_cost': rec.unit_cost,
        } for rec in self]

    @api.model
    def _post_return(self, line, qty):
        raise AccessError(_('This store is unavailable for native sales.'))


class SalesStockShortage(models.Model):
    _name = 'ab_sales_stock_shortage'
    _description = 'Sold Without Stock'
    _order = 'id desc'

    sale_id = fields.Many2one('ab_sales_header', required=True, readonly=True, ondelete='restrict', index=True)
    sale_line_id = fields.Many2one('ab_sales_line', required=True, readonly=True, ondelete='restrict', index=True)
    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict', index=True)
    employee_id = fields.Many2one('ab_hr_employee', readonly=True, ondelete='restrict', index=True)
    product_id = fields.Many2one('ab_product', required=True, readonly=True, ondelete='restrict', index=True)
    uom_id = fields.Many2one('ab_product_uom', required=True, readonly=True, ondelete='restrict')
    unit_factor = fields.Float(required=True, readonly=True, digits=(18, 8))
    sold_qty = fields.Float(required=True, readonly=True, digits=(18, 8))
    deducted_qty = fields.Float(required=True, readonly=True, digits=(18, 8))
    shortage_qty = fields.Float(required=True, readonly=True, digits=(18, 8))
    sold_qty_smallest = fields.Float(required=True, readonly=True, digits=(24, 8))
    deducted_qty_smallest = fields.Float(required=True, readonly=True, digits=(24, 8))
    shortage_qty_smallest = fields.Float(required=True, readonly=True, digits=(24, 8))
    unit_price = fields.Float(required=True, readonly=True, digits=(18, 6))
    reason = fields.Selection([
        ('not_transferred', 'Not transferred yet from main store'),
        ('wrong_price', 'Wrong price in system'),
        ('stocktaking_error', 'Stocktaking error'),
        ('not_entered', 'Not entered by data entry yet'),
        ('promised_customer', 'Already told customer we will deliver product'),
        ('other', 'Other (please explain)'),
    ], required=True, readonly=True)
    reason_details = fields.Char(readonly=True)
    state = fields.Selection([('open', 'Open'), ('cancelled', 'Cancelled')], required=True, readonly=True, default='open')
    _sale_line_unique = models.Constraint('UNIQUE(sale_line_id)', 'Each sale line can have only one stock shortage.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Stock shortages are created only by sale approval.'))

    def write(self, vals):
        raise AccessError(_('Stock shortages cannot be changed directly.'))

    def unlink(self):
        raise AccessError(_('Stock shortages cannot be deleted.'))

    @api.model
    def _create_from_plan(self, sale, plan):
        line = plan['line']
        deducted = plan['qty'] - plan['shortage']
        employee = sale.pos_hr_employee_id if 'pos_hr_employee_id' in sale._fields else sale.employee_id
        return super(SalesStockShortage, self.sudo()).create({
            'sale_id': sale.id,
            'sale_line_id': line.id,
            'store_id': sale.store_id.id,
            'employee_id': employee.id,
            'product_id': line.product_id.id,
            'uom_id': line.uom_id.id,
            'unit_factor': plan['factor'],
            'sold_qty': line.qty,
            'deducted_qty': deducted / plan['factor'],
            'shortage_qty': plan['shortage'] / plan['factor'],
            'sold_qty_smallest': plan['qty'],
            'deducted_qty_smallest': deducted,
            'shortage_qty_smallest': plan['shortage'],
            'unit_price': line.sell_price,
            'reason': line.unavailable_reason,
            'reason_details': (line.unavailable_reason_other or '').strip() or False,
        })

    def _cancel(self):
        open_records = self.filtered(lambda rec: rec.state == 'open')
        if open_records:
            super(SalesStockShortage, open_records.sudo()).write({'state': 'cancelled'})


class SalesStockReversal(models.Model):
    _name = 'ab_sales_stock_reversal'
    _description = 'Sales Stock Reversal'
    _order = 'id'

    allocation_id = fields.Many2one('ab_sales_stock_allocation', required=True, readonly=True, ondelete='restrict', index=True)
    sale_id = fields.Many2one(related='allocation_id.sale_line_id.header_id', store=True, readonly=True)
    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict', index=True)
    source_id = fields.Many2one('ab_product_source', required=True, readonly=True, ondelete='restrict')
    uom_id = fields.Many2one('ab_product_uom', required=True, readonly=True, ondelete='restrict')
    qty = fields.Float(required=True, readonly=True, digits=(24, 8))
    reversed_by_id = fields.Many2one('res.users', required=True, readonly=True)
    reversed_at = fields.Datetime(required=True, readonly=True)
    _allocation_unique = models.Constraint('UNIQUE(allocation_id)', 'Each stock allocation can be reversed only once.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Stock reversals are created only by invoice cancellation.'))

    def write(self, vals):
        raise AccessError(_('Stock reversals cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Stock reversals cannot be deleted.'))

    @api.model
    def _reverse_allocation(self, allocation):
        raise AccessError(_('This store is unavailable for native sales.'))
