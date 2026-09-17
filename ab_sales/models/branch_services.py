"""API-only stock, customers and background synchronization."""
import hashlib
import json
import math
import logging
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


_logger = logging.getLogger(__name__)


class BranchServices(models.AbstractModel):
    _inherit = 'ab_sales_branch_client'

    def _stores(self):
        configs = self.env['ab_sales_branch_rpc_config'].sudo().search([('active', '=', True)])
        ids = configs.store_id.ids
        allowed = self.env['ab_sales_header']._get_allowed_store_ids()
        if allowed:
            ids = list(set(ids) & set(allowed))
        return self.env['ab_store'].search(fields.Domain('id', 'in', ids)
            & fields.Domain('active', '=', True) & fields.Domain('allow_sale', '=', True))

    def _pages(self, store, method, *args):
        token, offset, rows = False, 0, []
        while True:
            response = self._call(store, method, *args, token, offset)
            if token and token != response.get('token'):
                raise UserError(_('The branch returned an invalid snapshot.'))
            token = response['token']
            rows.extend(response['data'])
            next_offset = response.get('next_offset')
            if next_offset is False:
                if len(rows) != response.get('total_count'):
                    raise UserError(_('The branch returned an incomplete snapshot.'))
                return rows, response['fetched_at']
            if type(next_offset) is not int or next_offset <= offset or next_offset != len(rows):
                raise UserError(_('The branch returned an invalid snapshot.'))
            offset = next_offset

    def _balances(self, store, serials):
        serials = sorted({int(s) for s in serials if s})
        result, fetched = [], False
        for offset in range(0, len(serials), 200):
            batch = serials[offset:offset + 200]
            response = self._call(store, 'get_product_balances', batch)
            rows = response['data']
            self._validate_balance_rows(store, rows)
            if {r['product_eplus_serial'] for r in rows} != set(batch):
                raise UserError(_('Some products are unavailable at the branch.'))
            result.extend(rows)
            fetched = response['fetched_at']
        self.env['ab_sales_inventory']._apply_api_balances(store, result, fetched)
        return result

    def _validate_balance_rows(self, store, rows):
        serials = set()
        for row in rows:
            serial = row.get('product_eplus_serial')
            if (type(serial) is not int or serial <= 0 or serial in serials
                    or row.get('store_eplus_serial') != store.eplus_serial
                    or any(not math.isfinite(float(row.get(k))) or float(row[k]) < 0
                           for k in ('balance', 'default_price'))):
                raise UserError(_('The branch returned invalid stock data.'))
            serials.add(serial)


class ApiInventory(models.Model):
    _inherit = 'ab_sales_inventory'
    branch_refreshed_at = fields.Datetime(string='Branch Refreshed At', readonly=True)

    def _apply_api_balances(self, store, rows, fetched, complete=False):
        client = self.env['ab_sales_branch_client']
        client._config(store)  # Validate before scoped elevation, even for cron callers.
        client._validate_balance_rows(store, rows)
        Inventory = self.sudo()
        serials = [r['product_eplus_serial'] for r in rows]
        existing = Inventory.search([('store_id', '=', store.id)])
        by_serial = {r.product_eplus_serial: r for r in existing}
        products = Inventory._product_lookup_by_eplus_serial(serials)
        creates = []
        for row in rows:
            serial = row['product_eplus_serial']
            values = {**Inventory._product_sync_vals(serial, products), 'balance': row['balance'],
                      'default_price': row['default_price'], 'branch_refreshed_at': fetched}
            if serial in by_serial:
                old_price = by_serial[serial].default_price
                if old_price != values['default_price']:
                    _logger.info('Branch price cache store=%s product=%s old_price=%s new_price=%s changed_by=%s change_date=%s',
                                 store.id, serial, old_price, values['default_price'], self.env.uid, fetched)
                existing.filtered(lambda r: r.product_eplus_serial == serial).write(values)
            else:
                creates.append(dict(values, store_id=store.id, product_eplus_serial=serial))
        if creates:
            Inventory.create(creates)
        if complete:
            missing = existing.filtered(lambda r: r.product_eplus_serial not in set(serials))
            missing.write({'balance': 0, 'branch_refreshed_at': fetched})

    def _api_refresh_stores(self, stores):
        client = self.env['ab_sales_branch_client']
        if not stores:
            raise UserError(_('No authorized branches are configured.'))
        snapshots = []
        for store in stores:
            rows, fetched = client._pages(store, 'get_inventory_snapshot')
            client._validate_balance_rows(store, rows)
            snapshots.append((store, rows, fetched))
        for store, rows, fetched in snapshots:
            self._apply_api_balances(store, rows, fetched, complete=True)
        return True

    def btn_update_balance_total(self):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().btn_update_balance_total()
        return self._api_refresh_stores(self.env['ab_sales_branch_client']._stores())

    def btn_update_balance_per_pos(self):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().btn_update_balance_per_pos()
        return self._api_refresh_stores(self.env['ab_sales_branch_client']._stores())

    def btn_update_balance_default_sales_store(self):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().btn_update_balance_default_sales_store()
        store = self._get_default_sales_store()
        return self._api_refresh_stores(store or self.env['ab_sales_branch_client']._stores())


class ApiSalesDay(models.Model):
    _inherit = 'ab_sales_per_day'

    def _fetch_remote_sales_day(self, sale_date):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super()._fetch_remote_sales_day(sale_date)
        stores = client._stores()
        if not stores:
            raise UserError(_('No authorized branches are configured.'))
        result = []
        for store in stores:
            rows, _fetched = client._pages(store, 'get_sales_day', str(sale_date))
            seen = set()
            for row in rows:
                serial = row.get('product_eplus_serial')
                if (row.get('store_eplus_serial') != store.eplus_serial or row.get('sale_date') != str(sale_date)
                        or type(serial) is not int or serial <= 0 or serial in seen
                        or not math.isfinite(float(row.get('sales_qty')))):
                    raise UserError(_('The branch returned invalid sales data.'))
                seen.add(serial)
                result.append(dict(row, store_id=store.id))
        products = self._products_by_eplus_serial([r['product_eplus_serial'] for r in result])
        return [dict(row, product_id=products.get(row['product_eplus_serial'])) for row in result]

    def _replace_sales_day(self, sale_date, rows):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super()._replace_sales_day(sale_date, rows)
        stores = client._stores()
        if not stores:
            raise UserError(_('No authorized branches are configured.'))
        # All branch snapshots were validated before entering this transaction.
        self.search([('sale_date', '=', sale_date), ('store_id', 'in', stores.ids)]).unlink()
        values = [{k: row[k] for k in ('store_id', 'product_eplus_serial', 'product_id', 'sales_qty')}
                  for row in rows]
        if values:
            self.create([dict(v, sale_date=sale_date, sync_at=fields.Datetime.now()) for v in values])
        return len(values)


class ApiSalesHeader(models.Model):
    _inherit = 'ab_sales_header'

    def get_connection(self):
        if self.env['ab_sales_branch_client']._is_callcenter():
            raise AccessError(_('Callcenter sales must use the branch API.'))
        return super().get_connection()

    @api.onchange('store_id')
    def _onchange_store_id(self):
        if self.env['ab_sales_branch_client']._is_callcenter():
            for header in self:
                if header.store_id and header.line_ids:
                    header.line_ids._recompute_inventory_json()
            return
        return super()._onchange_store_id()

    @api.model
    def cron_update_status_from_store(self):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().cron_update_status_from_store()
        Log = self.env['ab_sales_callcenter_rpc_log']
        for store in client._stores():
            try:
                # Roll back this branch's refresh on an invalid/failed request,
                # while allowing healthy branches to continue. No submission replay.
                with self.env.cr.savepoint():
                    config = client._config(store)
                    logs = Log.search(
                        fields.Domain('rpc_config_id', '=', config.id) & fields.Domain('store_id', '=', store.id)
                        & fields.Domain('state', '=', 'success') & fields.Domain('payload_token', '!=', False)
                        & fields.Domain('remote_header_id', '>', 0)
                        & fields.Domain('remote_status', 'in', ['prepending', 'pending']))
                    by_token = {}
                    for log in logs:
                        by_token.setdefault(log.payload_token, Log.browse())
                        by_token[log.payload_token] |= log
                    tokens = sorted(by_token)
                    for offset in range(0, len(tokens), 200):
                        batch = tokens[offset:offset + 200]
                        response = client._call(store, 'get_sale_statuses', batch)
                        if not isinstance(response.get('data'), list):
                            raise UserError(_('The branch returned invalid invoice status.'))
                        seen, updates = set(), []
                        for row in response['data']:
                            if not isinstance(row, dict):
                                raise UserError(_('The branch returned invalid invoice status.'))
                            token = row.get('token')
                            if (not isinstance(token, str) or token not in batch or token in seen
                                    or type(row.get('branch_header_id')) is not int
                                    or type(row.get('eplus_serial')) is not int or row['eplus_serial'] < 0
                                    or row.get('status') not in ('prepending', 'pending', 'saved')
                                    or (row['status'] != 'prepending' and not row['eplus_serial'])):
                                raise UserError(_('The branch returned invalid invoice status.'))
                            tracked = by_token[token]
                            if any(log.remote_header_id != row['branch_header_id']
                                   or (log.remote_eplus_serial and log.remote_eplus_serial != row['eplus_serial'])
                                   or (log.remote_status == 'pending' and row['status'] == 'prepending')
                                   for log in tracked):
                                raise UserError(_('The branch returned invalid invoice status.'))
                            seen.add(token)
                            updates.append((tracked, row))
                        for tracked, row in updates:
                            tracked.write({'remote_status': row['status'], 'remote_eplus_serial': row['eplus_serial']})
            except (UserError, AccessError):
                _logger.warning('Call-center order status refresh failed for store %s; previous statuses retained.', store.id)
        return True


class ApiPosServices(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().pos_refresh_pos_balances(store_id=store_id, product_ids=product_ids)
        store = self.env['ab_store'].browse(int(store_id or 0)).exists()
        products = self.env['ab_product'].browse([int(p) for p in product_ids or []]).exists()
        products.check_access('read')
        rows = client._balances(store, products.mapped('eplus_serial'))
        by_serial = {r['product_eplus_serial']: r['balance'] for r in rows}
        result = {p.id: by_serial[p.eplus_serial] for p in products if p.eplus_serial in by_serial}
        result['_refreshed_at'] = fields.Datetime.to_string(fields.Datetime.now())
        return result

    def _api_customer(self, store, result):
        customer = result.get('customer')
        if not customer:
            return result
        if not int(customer.get('eplus_serial') or 0):
            raise UserError(_('The branch returned an invalid customer.'))
        values = {k: customer[k] for k in ('name', 'code', 'mobile_phone', 'work_phone', 'address', 'eplus_serial') if k in customer}
        values['default_store_id'] = store.id
        self.env['ab_customer'].check_access('read')
        Customer = self.env['ab_customer'].sudo().with_context(active_test=False)
        record = Customer.search([('eplus_serial', '=', values['eplus_serial'])], limit=2)
        if len(record) > 1:
            raise UserError(_('The customer reference is ambiguous.'))
        if record:
            record.write(values)
        else:
            record = Customer.create(values)
        return dict(result, customer=self._customer_payload(record))

    @api.model
    def pos_customer_lookup(self, phone=None, store_id=None):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().pos_customer_lookup(phone=phone, store_id=store_id)
        store = self.env['ab_store'].browse(int(store_id or 0)).exists()
        client._config(store)
        return self._api_customer(store, client._call(store, 'lookup_customer', phone))

    @api.model
    def pos_customer_create(self, phone=None, name=None, address=None, store_id=None):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().pos_customer_create(phone=phone, name=name, address=address, store_id=store_id)
        store = self.env['ab_store'].browse(int(store_id or 0)).exists()
        config = client._config(store)
        validated = self._validate_new_customer_payload(phone=phone, name=name, address=address)
        # Deterministic token survives browser closure/retries without persisting personal data in logs.
        digest = hashlib.sha256(json.dumps([self.env.cr.dbname, self.env.uid, store.id, validated],
                                          sort_keys=True).encode()).hexdigest()
        token = 'customer-' + digest
        Log = self.env['ab_sales_callcenter_rpc_log'].sudo()
        log = Log.search([('payload_token', '=', token), ('submitted_by_id', '=', self.env.uid)], limit=1)
        if log:
            status = client._call(store, 'get_operation_status', token)
            if status['state'] == 'done':
                return self._api_customer(store, status['result'])
            if status['state'] not in ('not_found', 'draft'):
                raise UserError(_('Operation outcome needs reconciliation. Check the branch before retrying.'))
        else:
            log = Log.create({'rpc_config_id': config.id, 'store_id': store.id, 'payload_token': token,
                              'submitted_by_id': self.env.uid, 'submitted_at': fields.Datetime.now()})
        self.env.cr.commit()
        try:
            result = client._call(store, 'create_customer', token, validated['phone'], validated['name'], validated['address'])
            log.write({'state': 'success'})
            self.env.cr.commit()
            return self._api_customer(store, result)
        except Exception:
            self.env.cr.rollback()
            log.write({'state': 'error', 'error_message': _('Check the branch operation status before retrying.')})
            self.env.cr.commit()
            raise


class ApiProductBalances(models.Model):
    _inherit = 'ab_product'

    def _get_all_stores_balance_html(self, product_serials=None):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super()._get_all_stores_balance_html(product_serials)
        rows = []
        for store in client._stores():
            try:
                data = client._balances(store, product_serials or [])
                for row in data:
                    rows.append((store.display_name, str(row['product_eplus_serial']), str(row['balance']), _('Current')))
            except (UserError, AccessError):
                cached = self.env['ab_sales_inventory'].search([('store_id', '=', store.id),
                            ('product_eplus_serial', 'in', product_serials or [])])
                for serial in product_serials or []:
                    line = cached.filtered(lambda r: r.product_eplus_serial == serial)[:1]
                    rows.append((store.display_name, str(serial), str(line.balance) if line else '—',
                                 _('Unavailable; last refresh: %s') % (line.branch_refreshed_at or '—')))
        return self.env['ir.qweb']._render('ab_sales.callcenter_product_store_balance_html', {'rows': rows})


class ApiProductSearch(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def search_products(self, *args, **kwargs):
        rows = super().search_products(*args, **kwargs)
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return rows
        store_id = self._resolve_store_id(header_id=kwargs.get('header_id'), store_id=kwargs.get('store_id'))
        if store_id:
            serials = self.env['ab_product'].browse([r['id'] for r in rows]).mapped('eplus_serial')
            cache = self.env['ab_sales_inventory'].search([('store_id', '=', store_id), ('product_eplus_serial', 'in', serials)])
            by_serial = {r.product_eplus_serial: r for r in cache}
            products = {p.id: p.eplus_serial for p in self.env['ab_product'].browse([r['id'] for r in rows])}
            for row in rows:
                cached = by_serial.get(products[row['id']])
                row['pos_balance_stale'] = True
                row['pos_balance_refreshed_at'] = fields.Datetime.to_string(cached.branch_refreshed_at) if cached and cached.branch_refreshed_at else False
                if not cached:
                    row['pos_balance'] = None
        return rows
