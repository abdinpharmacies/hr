import math
from decimal import Decimal

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
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    source_id = fields.Many2one('ab_product_source', required=True, readonly=True, ondelete='restrict')
    uom_id = fields.Many2one('ab_uom', required=True, readonly=True, ondelete='restrict')
    qty = fields.Integer(required=True, readonly=True)
    unit_cost = fields.Float(readonly=True, digits=(18, 6))
    _operation_unique = models.Constraint('UNIQUE(operation_key)', 'Stock allocation operation keys must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Stock allocations are created only by cashier posting.'))

    def write(self, vals):
        raise AccessError(_('Posted stock allocations cannot be changed.'))

    def unlink(self):
        raise AccessError(_('Posted stock allocations cannot be deleted.'))

    @api.model
    def _source_rows(self, store, product):
        self.env['ab_sales_backend']._check_store(store.id)
        product.ensure_one()
        product.check_access('read')
        balances = self.env['ab_inventory_process'].get_source_balances(store.id, product_id=product.id)
        sources = self.env['ab_product_source'].sudo().browse([sid for sid, qty in balances.items() if qty > 0])
        rows = []
        today = fields.Date.context_today(self)
        for source in sources.sorted(lambda rec: (rec.exp_date or fields.Date.to_date('9999-12-31'), rec.id)):
            if source.product_id != product or (source.exp_date and source.exp_date < today):
                continue
            small = Decimal(str(product.unit_s_id.unit_no or 0))
            medium = Decimal(str(product.unit_m_id.unit_no or 0))
            size = source.uom_id.unit_size
            factor = small if size == 'large' else small / medium if size == 'medium' and medium else Decimal(1) if size == 'small' else Decimal(0)
            if factor <= 0 or not all(math.isfinite(value) for value in (source.price, source.unit_cost)):
                raise ValidationError(_('The stock source has invalid unit or price values.'))
            rows.append({'source_id': source.id, 'source_identity': source.source_identity,
                         'qty': balances[source.id], 'price': source.price / float(factor),
                         'cost': source.unit_cost / float(factor), 'expiry': source.exp_date})
        return rows

    @api.model
    def _post_sale(self, line):
        line.ensure_one()
        line.check_access('read')
        sale = line.header_id
        store = self.env['ab_sales_backend']._check_store(sale.store_id.id, cashier=True)
        self.env['ab_sales_backend']._check_employee_session(store, 'allow_cashier_screen')
        if not sale.native_backend or not sale.native_submitted or sale.status != 'pending':
            raise ValidationError(_('Only submitted native bills can post stock at the cashier.'))
        store._lock_stock_scope()
        snapshot = sale.native_totals['line_context'][str(line.id)]
        qty = line.product_id._to_stock_quantity(line.qty, line.uom_id)
        if qty != snapshot['stock_qty'] or line.product_id.unit_s_id.id != snapshot['stock_unit_id']:
            raise ValidationError(_('The stock unit mapping changed after bill submission.'))
        existing = self.sudo().search(fields.Domain([
            ('sale_line_id', '=', line.id), ('return_line_id', '=', False),
        ]))
        if existing:
            if sum(existing.mapped('qty')) != qty:
                raise ValidationError(_('The bill already has different stock allocations.'))
            return existing._snapshot()
        rows = self._source_rows(store, line.product_id)
        preferred_price = line.sell_price * line.qty / qty
        rows.sort(key=lambda row: (
            abs(row['price'] - preferred_price) > 0.000001, row['price'],
            row['expiry'] or fields.Date.to_date('9999-12-31'), row['source_id'],
        ))
        if sum(row['qty'] for row in rows) < qty:
            raise ValidationError(_('Insufficient stock at cashier posting. The bill remains pending.'))
        remaining = qty
        created = self.browse()
        with self.env.cr.savepoint():
            for row in rows:
                take = min(remaining, row['qty'])
                if not take:
                    break
                allocation = super(SalesStockAllocation, self.sudo()).create({
                    'operation_key': 'sale:%s:source:%s' % (line.id, row['source_id']),
                    'sale_line_id': line.id, 'store_id': store.id, 'source_id': row['source_id'],
                    'uom_id': line.product_id.unit_s_id.id, 'qty': take, 'unit_cost': row['cost'],
                })
                self.env['ab_inventory_process'].inventory_write(
                    allocation, take, store.id, sign=-1, status='saved')
                created |= allocation.with_env(self.env)
                remaining -= take
        return created._snapshot()

    def _snapshot(self):
        return [{'allocation_id': rec.id, 'source_id': rec.source_id.id, 'qty': rec.qty,
                 'unit_cost': rec.unit_cost} for rec in self]

    @api.model
    def _post_return(self, line, qty):
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
            if sum(existing.mapped('qty')) != qty:
                raise ValidationError(_('The return already has different stock allocations.'))
            return
        allocations = self.sudo().search(fields.Domain([
            ('sale_line_id', '=', original.id), ('return_line_id', '=', False),
        ]))
        returned = self.sudo()._read_group(fields.Domain('original_id', 'in', allocations.ids), ['original_id'], ['qty:sum'])
        totals = {allocation.id: count for allocation, count in returned}
        if qty > sum(rec.qty - totals.get(rec.id, 0) for rec in allocations):
            raise ValidationError(_('The return exceeds the original stock allocations.'))
        remaining = qty
        with self.env.cr.savepoint():
            for original_allocation in allocations:
                take = min(remaining, original_allocation.qty - totals.get(original_allocation.id, 0))
                if take <= 0:
                    continue
                allocation = super(SalesStockAllocation, self.sudo()).create({
                    'operation_key': 'return:%s:allocation:%s' % (line.id, original_allocation.id),
                    'sale_line_id': original.id, 'return_line_id': line.id, 'original_id': original_allocation.id,
                    'store_id': store.id, 'source_id': original_allocation.source_id.id,
                    'uom_id': original_allocation.uom_id.id, 'qty': take, 'unit_cost': original_allocation.unit_cost,
                })
                self.env['ab_inventory_process'].inventory_write(
                    allocation, take, store.id, sign=1, status='saved')
                remaining -= take
                if not remaining:
                    break


class InventoryMovement(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(selection_add=[('ab_sales_stock_allocation', 'Sales Stock Allocation')],
                                 ondelete={'ab_sales_stock_allocation': 'set default'})
