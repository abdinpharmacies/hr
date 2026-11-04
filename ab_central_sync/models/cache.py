"""Central balance snapshots and conservative branch reservations; no local ledger."""
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class SalesCache(models.Model):
    _inherit = 'ab_sales_inventory'

    central_revision = fields.Integer(readonly=True, copy=False)
    central_watermark = fields.Integer(readonly=True, copy=False)
    central_batches = fields.Json(readonly=True, copy=False)
    central_initialized = fields.Boolean(readonly=True, copy=False)
    _store_product_unique = models.Constraint('UNIQUE(store_id, product_id)', 'A product can have only one inventory record per branch.')

    @api.model
    def _central_rows(self, store, product):
        self.env['ab_sales_backend']._check_store(store.id)
        cache = self.sudo().search(fields.Domain('store_id', '=', store.id) & fields.Domain('product_id', '=', product.id), limit=1)
        if not cache and self.env['ab_central_sync_operation']._param('ready'):
            return []
        if not cache or not cache.central_initialized:
            raise ValidationError(_('Download the central stock snapshot before selling this product.'))
        rows = [dict(row) for row in cache.central_batches or []]
        origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        pending = self.env['ab_central_sync_operation'].sudo().with_context(active_test=False).search(
            fields.Domain('direction', '=', 'out') & fields.Domain('store_id', '=', store.id)
            & fields.Domain('origin', '=', origin) & fields.Domain('kind', '=', 'sale') & fields.Domain('serial', '>', cache.central_watermark))
        reservations = {}
        for operation in pending:
            for item in operation.payload.get('cache_reservations', []):
                if item['product_code'] == product.code:
                    for allocation in item['batches']:
                        key = allocation['source_id']
                        reservations[key] = reservations.get(key, 0) + allocation['qty']
        for row in rows:
            row['qty'] = max(0, row['qty'] - reservations.get(row['source_id'], 0))
            row['expiry'] = fields.Date.to_date(row['expiry']) if row.get('expiry') else False
        today = fields.Date.context_today(self)
        return [row for row in rows if not row['expiry'] or row['expiry'] >= today]

    @api.model
    def _accept_central_snapshot(self, store, snapshot):
        if not self.env.su:
            raise AccessError(_('Only the synchronization service can replace stock snapshots.'))
        if (snapshot.get('version') != 2 or snapshot.get('store') != store.code
                or snapshot.get('origin') != self.env['ir.config_parameter'].sudo().get_param('database.uuid')
                or type(snapshot.get('revision')) is not int or snapshot['revision'] < 1
                or type(snapshot.get('watermark')) is not int or snapshot['watermark'] < 0
                or not isinstance(snapshot.get('products'), list) or len(snapshot['products']) > 500
                or not snapshot.get('at')):
            raise ValidationError(_('Invalid central stock snapshot.'))
        store._lock_stock_scope()
        for item in snapshot['products']:
            if (not isinstance(item, dict) or not isinstance(item.get('batches'), list)
                    or not isinstance(item.get('code'), str) or not item['code']
                    or not all(isinstance(item.get(k), (int, float)) and math.isfinite(item[k]) and item[k] >= 0 for k in ('balance', 'default_price'))):
                raise ValidationError(_('Invalid central stock snapshot.'))
            source_ids = set()
            for batch in item['batches']:
                if (not isinstance(batch, dict) or type(batch.get('source_id')) is not int or batch['source_id'] <= 0 or batch['source_id'] in source_ids
                        or type(batch.get('qty')) is not int or batch['qty'] < 0
                        or not all(isinstance(batch.get(k), (int, float)) and math.isfinite(batch[k]) and batch[k] >= 0 for k in ('price', 'cost'))):
                    raise ValidationError(_('Invalid central stock snapshot.'))
                source_ids.add(batch['source_id'])
                if batch.get('expiry'):
                    fields.Date.to_date(batch['expiry'])
            product = self.env['ab_product'].with_context(active_test=False).search(fields.Domain('code', '=', item['code']), limit=2)
            if len(product) != 1:
                raise ValidationError(_('Synchronize the product catalog before stock snapshots.'))
            cache = self.search(fields.Domain('store_id', '=', store.id) & fields.Domain('product_id', '=', product.id), limit=1)
            if cache and cache.central_initialized and (cache.central_revision > snapshot['revision'] or cache.central_watermark > snapshot['watermark']):
                continue
            values = {'store_id': store.id, 'product_id': product.id, 'product_code': product.code,
                      'product_eplus_serial': product.eplus_serial, 'balance': item['balance'],
                      'default_price': item['default_price'], 'last_sync_at': snapshot['at'],
                      'central_revision': snapshot['revision'], 'central_watermark': snapshot['watermark'],
                      'central_batches': item['batches'], 'central_initialized': True}
            if cache:
                cache.write(values)
            else:
                self.create(values)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su and any(any(key.startswith('central_') for key in vals) for vals in vals_list):
            raise AccessError(_('Only the synchronization service can replace stock snapshots.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su and (any(key.startswith('central_') for key in vals) or self.filtered('central_initialized')):
            raise AccessError(_('Only the synchronization service can replace stock snapshots.'))
        return super().write(vals)

    def _backend_inventory_snapshot(self, store, product_serials=None):
        if not self.env['ab_central_sync_operation']._uses_central(store):
            return super()._backend_inventory_snapshot(store, product_serials=product_serials)
        self.env['ab_sales_backend']._check_store(store.id)
        domain = fields.Domain('active', '=', True)
        if product_serials is not None:
            domain &= fields.Domain('eplus_serial', 'in', product_serials)
        products = self.env['ab_product'].search(domain)
        balances = self.env['ab_sales_pos_api'].pos_refresh_pos_balances(store.id, products.ids)
        return [{'product_eplus_serial': p.eplus_serial, 'store_eplus_serial': store.eplus_serial,
                 'balance': balances[p.id], 'default_price': p.default_price} for p in products]

    def btn_update_balance_total(self):
        result = super().btn_update_balance_total()
        self.env['ab_central_sync_operation']._refresh_snapshots()
        return result

    def _get_working_balance_store_pairs(self, exclude_default=False, default_store=None):
        pairs = super()._get_working_balance_store_pairs(exclude_default=exclude_default, default_store=default_store)
        journal = self.env['ab_central_sync_operation']
        return [(store, serial) for store, serial in pairs if not journal._uses_central(store)]

    def btn_update_balance_per_pos(self):
        result = super().btn_update_balance_per_pos()
        self.env['ab_central_sync_operation']._refresh_snapshots()
        return result

    def btn_update_balance_default_sales_store(self):
        store = self._get_default_sales_store()
        if self.env['ab_central_sync_operation']._uses_central(store):
            return self.env['ab_central_sync_operation']._refresh_snapshots(store_ids=store.ids)
        return super().btn_update_balance_default_sales_store()


class Backend(models.Model):
    _inherit = 'ab_sales_backend'

    @api.model
    def _is_native(self, store_id):
        store = self.env['ab_store'].sudo().browse(int(store_id or 0))
        if self.env['ab_central_sync_operation']._uses_central(store):
            return True
        return super()._is_native(store_id)

    @api.model
    def _check_store(self, store_id, cashier=False):
        store = super()._check_store(store_id, cashier=cashier)
        journal = self.env['ab_central_sync_operation']
        if journal._uses_central(store, 'branch'):
            journal._check_enrolled_store(store)
        return store


class Allocation(models.Model):
    _inherit = 'ab_sales_stock_allocation'

    @api.model
    def _source_rows(self, store, product):
        if self.env['ab_central_sync_operation']._uses_central(store, 'branch'):
            return self.env['ab_sales_inventory']._central_rows(store, product)
        return super()._source_rows(store, product)

    @api.model
    def _post_sale_plan(self, sale, plans):
        if not self.env['ab_central_sync_operation']._uses_central(sale.store_id, 'branch'):
            return super()._post_sale_plan(sale, plans)
        for plan in plans:
            allocations = [{'source_id': row['source_id'], 'qty': row['take'],
                            'price': row['price'], 'cost': row['cost']} for row in plan['allocations']]
            plan['line']._set_native_stock_snapshot(plan, allocations)
        return self.browse()

    @api.model
    def _post_return(self, line, qty):
        if not self.env['ab_central_sync_operation']._uses_central(line.header_id.store_id, 'branch'):
            return super()._post_return(line, qty)
        previous = self.env['ab_sales_return_line'].search(
            fields.Domain('native_origin_line_id', '=', line.native_origin_line_id.id)
            & fields.Domain('header_id.native_posted', '=', True))
        if qty <= 0 or qty + sum(previous.mapped('native_stock_qty')) > line.native_origin_line_id.native_stock_qty:
            raise ValidationError(_('The return exceeds the original sold quantity.'))
        return self.browse()


class Sale(models.Model):
    _inherit = 'ab_sales_header'

    def _validate_native_stock_evidence(self):
        if not self.env['ab_central_sync_operation']._uses_central(self.store_id, 'branch'):
            return super()._validate_native_stock_evidence()
        for line in self.line_ids:
            data = self.native_totals['line_context'].get(str(line.id), {})
            if data.get('is_service'):
                continue
            if (sum(row['qty'] for row in line.native_allocations or []) != data.get('deducted_qty')
                    or line.native_requested_stock_qty != data.get('stock_qty')
                    or line.native_shortage_qty != data.get('shortage_qty')):
                raise ValidationError(_('The branch approval does not match its cached stock reservation.'))
        return True

    def _central_snapshot(self):
        result = super()._central_snapshot()
        if self.env['ab_central_sync_operation']._uses_central(self.store_id, 'branch'):
            result.pop('allocations', None)
            if 'metadata' in self._fields and isinstance(self.sudo().metadata, dict):
                replica_serial = self.sudo().metadata.get('source_db_serial')
                if type(replica_serial) is int and replica_serial > 0:
                    result['promotion_replica_serial'] = replica_serial
            result['cache_reservations'] = [{'source_line': str(line.id), 'product_code': line.product_id.code,
                                            'batches': line.native_allocations or []} for line in self.line_ids]
        return result


class POS(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def _native_product_balances(self, store, products):
        if not self.env['ab_central_sync_operation']._uses_central(store, 'branch'):
            return super()._native_product_balances(store, products)
        return {p.id: sum(row['qty'] for row in self.env['ab_sales_inventory']._central_rows(store, p))
                for p in products if not p.is_service}

    @api.model
    def _native_stocked_products(self, store_id):
        if not self.env['ab_central_sync_operation']._uses_central(self.env['ab_store'].browse(store_id), 'branch'):
            return super()._native_stocked_products(store_id)
        cache = self.env['ab_sales_inventory'].search(fields.Domain('store_id', '=', store_id)
                                                     & fields.Domain('central_initialized', '=', True))
        balances = self._native_product_balances(self.env['ab_store'].browse(store_id), cache.product_id)
        return cache.product_id.filtered(lambda p: balances.get(p.id, 0) > 0)


class BackendReads(models.Model):
    _inherit = 'ab_sales_header'

    @api.model
    def _backend_stock_lines(self, store, product_serials, crx=None):
        if not self.env['ab_sales_backend']._is_native(store.id):
            return super()._backend_stock_lines(store, product_serials, crx=crx)
        self.env['ab_sales_backend']._check_store(store.id)
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in', product_serials))
        if set(products.mapped('eplus_serial')) != set(product_serials):
            raise AccessError(_('Requested products are not accessible.'))
        return [dict(row, exp_date=fields.Date.to_string(row['exp_date']) if row['exp_date'] else '')
                for product in products for row in self.env['ab_sales_pos_api']._native_inventory_rows(store.id, product)]


class CustomerReads(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _backend_lookup_customer(self, store, phone):
        if self.env['ab_sales_backend']._is_native(store.id):
            return self.pos_customer_lookup(phone=phone, store_id=store.id)
        return super()._backend_lookup_customer(store, phone)

    def _backend_customer_values(self, store, reference=None, phone=None):
        if not self.env['ab_sales_backend']._is_native(store.id):
            return super()._backend_customer_values(store, reference=reference, phone=phone)
        self.env['ab_sales_backend']._check_store(store.id)
        # Missing replicated customers are not silently imported from the retired source.
        raise ValidationError(_('Synchronize the customer catalog before using this reference.'))


class DailySales(models.Model):
    _inherit = 'ab_sales_per_day'

    def _backend_sales_day(self, store, day):
        if not self.env['ab_sales_backend']._is_native(store.id):
            return super()._backend_sales_day(store, day)
        from datetime import datetime, time, timedelta
        self.env['ab_sales_backend']._check_store(store.id)
        start = datetime.combine(day, time.min)
        lines = self.env['ab_sales_line'].search(fields.Domain('header_id.store_id', '=', store.id)
            & fields.Domain('header_id.native_backend', '=', True) & fields.Domain('header_id.status', '=', 'saved')
            & fields.Domain('header_id.create_date', '>=', start) & fields.Domain('header_id.create_date', '<', start + timedelta(days=1)))
        returns = self.env['ab_sales_return_line']._read_group(
            fields.Domain('native_origin_line_id', 'in', lines.ids) & fields.Domain('header_id.native_posted', '=', True),
            ['native_origin_line_id'], ['native_stock_qty:sum'])
        returned = {line.id: qty for line, qty in returns}
        quantities = {}
        for line in lines:
            product = line.product_id
            factor = float(product._stock_unit_factor(product.uom_id)) if not product.is_service else 1
            quantities[product.id] = quantities.get(product.id, 0) + (line.native_requested_stock_qty - returned.get(line.id, 0)) / factor
        return [{'store_eplus_serial': store.eplus_serial, 'product_eplus_serial': product.eplus_serial,
                 'sales_qty': quantities[product.id], 'sale_date': str(day)} for product in lines.product_id]


class LegacyInvoiceReads(models.Model):
    _inherit = 'ab_sales_header'

    def _backend_invoice_statuses(self, store, serials):
        if self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id)
            raise ValidationError(_('Use native invoice references for this branch. Historical invoices require review.'))
        return super()._backend_invoice_statuses(store, serials)


class LegacyReturnReads(models.Model):
    _inherit = 'ab_sales_return_header'

    def _backend_invoice_date(self, store, invoice, require_saved=False):
        if self.env['ab_sales_backend']._is_native(store.id):
            self.env['ab_sales_backend']._check_store(store.id)
            raise ValidationError(_('Use native invoice references for this branch. Historical invoices require review.'))
        return super()._backend_invoice_date(store, invoice, require_saved=require_saved)


class SnapshotFreshness(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None, include_sync_metadata=False):
        result = super().pos_refresh_pos_balances(store_id=store_id, product_ids=product_ids,
                                                 include_sync_metadata=include_sync_metadata)
        if include_sync_metadata and self.env['ab_central_sync_operation']._uses_central(self.env['ab_store'].browse(store_id), 'branch'):
            caches = self.env['ab_sales_inventory'].search(fields.Domain('store_id', '=', store_id)
                & fields.Domain('product_id', 'in', list(result)))
            timestamps = {cache.product_id.id: fields.Datetime.to_string(cache.last_sync_at) for cache in caches}
            for product_id, values in result.items():
                values['last_sync_at'] = timestamps.get(product_id, False)
        return result


class SnapshotFreshnessUI(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def _attach_pos_sync_metadata(self, rows, store_id):
        if not self.env['ab_central_sync_operation']._uses_central(self.env['ab_store'].browse(store_id), 'branch'):
            return super()._attach_pos_sync_metadata(rows, store_id)
        self.env['ab_sales_backend']._check_store(store_id)
        caches = self.env['ab_sales_inventory'].search(fields.Domain('store_id', '=', store_id)
            & fields.Domain('product_id', 'in', [row.get('id') for row in rows if row.get('id')]))
        timestamps = {cache.product_id.id: fields.Datetime.to_string(cache.last_sync_at) for cache in caches}
        for row in rows:
            row['pos_balance_last_sync_at'] = timestamps.get(row.get('id'), False)
        return rows
