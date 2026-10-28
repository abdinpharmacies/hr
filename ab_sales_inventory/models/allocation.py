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
    uom_id = fields.Many2one('ab_uom', required=True, readonly=True, ondelete='restrict')
    sale_uom_id = fields.Many2one('ab_product_uom', readonly=True, ondelete='restrict')
    sale_qty = fields.Float(readonly=True, digits=(18, 8))
    unit_factor = fields.Float(readonly=True, digits=(18, 8))
    qty = fields.Integer(required=True, readonly=True)
    qty_smallest = fields.Integer(readonly=True)
    unit_price = fields.Float(readonly=True, digits=(18, 6))
    source_unit_price = fields.Float(readonly=True, digits=(18, 6))
    unit_cost = fields.Float(readonly=True, digits=(18, 6))
    inventory_movement_id = fields.Many2one('ab_inventory', readonly=True, ondelete='restrict')
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
        self = self.with_context(ab_sales_branch_scope=True)
        self.env['ab_sales_backend']._check_store(store.id)
        product.ensure_one()
        product.check_access('read')
        balances = self.env['ab_inventory_process'].get_source_balances(store.id, product_id=product.id)
        sources = self.env['ab_product_source'].sudo().browse([sid for sid, qty in balances.items() if qty > 0])
        rows = []
        today = fields.Date.context_today(self)
        for source in sources:
            if source.product_id != product or (source.exp_date and source.exp_date < today):
                continue
            small = Decimal(str(product.unit_s_id.unit_no or 0))
            medium = Decimal(str(product.unit_m_id.unit_no or 0))
            size = source.uom_id.unit_size
            factor = small if size == 'large' else small / medium if size == 'medium' and medium else Decimal(1) if size == 'small' else Decimal(0)
            if factor <= 0 or not all(math.isfinite(value) for value in (source.price, source.unit_cost)):
                raise ValidationError(_('The stock source has invalid unit or price values.'))
            rows.append({
                'source_id': source.id,
                'source_identity': source.source_identity,
                'qty': int(balances[source.id]),
                'price': source.price / float(factor),
                'cost': source.unit_cost / float(factor),
                'expiry': source.exp_date,
            })
        return rows

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
            factor = Decimal(qty_smallest) / Decimal(str(line.qty))
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
    def _post_sale_plan(self, sale, plans):
        created = self.browse()
        Shortage = self.env['ab_sales_stock_shortage']
        for plan in plans:
            line = plan['line']
            if plan['service']:
                line._set_native_stock_snapshot(plan, [])
                continue
            line_allocations = self.browse()
            for row in plan['allocations']:
                allocation = super(SalesStockAllocation, self.sudo()).create({
                    'operation_key': 'sale:%s:source:%s' % (line.id, row['source_id']),
                    'sale_line_id': line.id,
                    'store_id': sale.store_id.id,
                    'source_id': row['source_id'],
                    'uom_id': line.product_id.unit_s_id.id,
                    'sale_uom_id': line.uom_id.id,
                    'sale_qty': row['take'] / plan['factor'],
                    'unit_factor': plan['factor'],
                    'qty': row['take'],
                    'qty_smallest': row['take'],
                    'unit_price': line.sell_price,
                    'source_unit_price': row['price'],
                    'unit_cost': row['cost'],
                })
                movement = self.env['ab_inventory_process'].inventory_write(
                    allocation, row['take'], sale.store_id.id, sign=-1, status='saved')
                super(SalesStockAllocation, allocation).write({'inventory_movement_id': movement.id})
                line_allocations |= allocation.with_env(self.env)
                created |= allocation.with_env(self.env)
            if plan['shortage']:
                Shortage._create_from_plan(sale, plan)
            line._set_native_stock_snapshot(plan, line_allocations._snapshot())
        return created

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
            'inventory_movement_id': rec.inventory_movement_id.id,
        } for rec in self]

    @api.model
    def _post_return(self, line, qty):
        self = self.with_context(ab_sales_branch_scope=True)
        line.ensure_one()
        line.check_access('read')
        header = line.header_id
        store = self.env['ab_sales_backend']._check_store(header.store_id.id, cashier=True)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_cashier_screen')
        original = line.native_origin_line_id
        if (header.status != 'pending' or original.header_id != header.native_origin_id
                or not original.header_id.native_posted or original.header_id.store_id != store):
            raise ValidationError(_('A stock return must reference its posted original bill.'))
        qty = original.product_id._validate_stock_quantity(qty)
        store._lock_stock_scope()
        existing = self.sudo().search(fields.Domain('return_line_id', '=', line.id))
        if existing:
            if sum(rec.qty_smallest or rec.qty for rec in existing) != qty:
                raise ValidationError(_('The return already has different stock allocations.'))
            return
        allocations = self.sudo().search(fields.Domain([
            ('sale_line_id', '=', original.id), ('return_line_id', '=', False),
        ]))
        returned = self.sudo().search(fields.Domain('original_id', 'in', allocations.ids))
        totals = {}
        for returned_allocation in returned:
            totals[returned_allocation.original_id.id] = totals.get(returned_allocation.original_id.id, 0) + (
                returned_allocation.qty_smallest or returned_allocation.qty)
        if qty > sum((rec.qty_smallest or rec.qty) - totals.get(rec.id, 0) for rec in allocations):
            raise ValidationError(_('The return exceeds the original stock allocations.'))
        remaining = qty
        for original_allocation in allocations:
            original_qty = original_allocation.qty_smallest or original_allocation.qty
            take = min(remaining, original_qty - totals.get(original_allocation.id, 0))
            if take <= 0:
                continue
            allocation = super(SalesStockAllocation, self.sudo()).create({
                'operation_key': 'return:%s:allocation:%s' % (line.id, original_allocation.id),
                'sale_line_id': original.id,
                'return_line_id': line.id,
                'original_id': original_allocation.id,
                'store_id': store.id,
                'source_id': original_allocation.source_id.id,
                'uom_id': original_allocation.uom_id.id,
                'sale_uom_id': original_allocation.sale_uom_id.id or original.uom_id.id,
                'sale_qty': take / (original_allocation.unit_factor or original.native_unit_factor),
                'unit_factor': original_allocation.unit_factor or original.native_unit_factor,
                'qty': take,
                'qty_smallest': take,
                'unit_price': original_allocation.unit_price,
                'source_unit_price': original_allocation.source_unit_price,
                'unit_cost': original_allocation.unit_cost,
            })
            movement = self.env['ab_inventory_process'].inventory_write(
                allocation, take, store.id, sign=1, status='saved')
            super(SalesStockAllocation, allocation).write({'inventory_movement_id': movement.id})
            remaining -= take
            if not remaining:
                break


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
    sold_qty_smallest = fields.Integer(required=True, readonly=True)
    deducted_qty_smallest = fields.Integer(required=True, readonly=True)
    shortage_qty_smallest = fields.Integer(required=True, readonly=True)
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
    uom_id = fields.Many2one('ab_uom', required=True, readonly=True, ondelete='restrict')
    qty = fields.Integer(required=True, readonly=True)
    original_movement_id = fields.Many2one('ab_inventory', required=True, readonly=True, ondelete='restrict')
    inventory_movement_id = fields.Many2one('ab_inventory', readonly=True, ondelete='restrict')
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
        existing = self.sudo().search([('allocation_id', '=', allocation.id)], limit=1)
        if existing:
            return existing
        reversal = super(SalesStockReversal, self.sudo()).create({
            'allocation_id': allocation.id,
            'store_id': allocation.store_id.id,
            'source_id': allocation.source_id.id,
            'uom_id': allocation.uom_id.id,
            'qty': allocation.qty_smallest or allocation.qty,
            'original_movement_id': allocation.inventory_movement_id.id,
            'reversed_by_id': self.env.uid,
            'reversed_at': fields.Datetime.now(),
        })
        movement = self.env['ab_inventory_process'].inventory_write(
            reversal, reversal.qty, reversal.store_id.id, sign=1, status='saved')
        super(SalesStockReversal, reversal).write({'inventory_movement_id': movement.id})
        return reversal


class InventoryMovement(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(selection_add=[
        ('ab_sales_stock_allocation', 'Sales Stock Allocation'),
        ('ab_sales_stock_reversal', 'Sales Stock Reversal'),
    ], ondelete={
        'ab_sales_stock_allocation': 'set default',
        'ab_sales_stock_reversal': 'set default',
    })
