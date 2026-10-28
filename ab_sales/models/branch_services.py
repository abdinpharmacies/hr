"""Branch API operations with a read-only central aggregate balance exception."""
import hashlib
import json
import math
import logging
from datetime import datetime, timedelta
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
        started = datetime.utcnow()
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
        self.env['ab_sales_inventory']._apply_api_balances(store, result, fetched, started=started)
        saved = self.env['ab_sales_inventory']._branch_sync_metadata(store, serials)
        return [dict(row, balance=saved[row['product_eplus_serial']]['balance']) for row in result]

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

    def _branch_sync_metadata(self, store, serials):
        store.check_access('read')
        rows = self.search(fields.Domain('store_id', '=', store.id)
                           & fields.Domain('product_eplus_serial', 'in', list(serials)))
        rows = rows.sorted(lambda r: (r.balance_refreshed_at or r.branch_refreshed_at or datetime.min, r.id))
        return {row.product_eplus_serial: {'balance': row.balance,
                'last_sync_at': fields.Datetime.to_string(row.balance_refreshed_at or row.branch_refreshed_at) if (row.balance_refreshed_at or row.branch_refreshed_at) else False}
                for row in rows}

    balance_refreshed_at = fields.Datetime(string='Balance Refreshed At', readonly=True)
    balance_source = fields.Selection([('eplus', 'E-Plus'), ('branch_api', 'Branch API')],
                                      string='Balance Source', readonly=True)

    def _apply_api_balances(self, store, rows, fetched, complete=False, *, started=None, scheduled=False):
        client = self.env['ab_sales_branch_client']
        client._config(store)
        client._validate_balance_rows(store, rows)
        fetched = fields.Datetime.to_datetime(fetched)
        if not fetched:
            raise UserError(_('The branch returned invalid stock data.'))
        self._apply_balance_cache(store, rows, 'branch_api', started or fetched,
                                  fetched=fetched, complete=complete, scheduled=scheduled)

    def _apply_balance_cache(self, store, rows, source, started, *, fetched=False,
                             complete=False, scheduled=False):
        """Private writer: callers must authorize and validate the complete response first.

        Local receipt time controls freshness; local request start orders responses.
        Provider timestamps remain diagnostic and cannot override a newer local save.
        """
        if not store.sudo().try_lock_for_update():
            raise UserError(_('A stock refresh is already running. Please retry.'))
        # A lock alone cannot prevent phantom inserts with Odoo's REPEATABLE READ.
        # Touch the row version without changing any branch/business value. A writer
        # with an older DB snapshot must then retry the entire transaction.
        self.env.cr.execute('UPDATE ab_store SET id = id WHERE id = %s', [store.id])
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)
        Inventory = self.sudo()
        domain = fields.Domain('store_id', '=', store.id)
        serials = {r['product_eplus_serial'] for r in rows}
        if not complete:
            domain &= fields.Domain('product_eplus_serial', 'in', list(serials))
        existing = Inventory.search(domain)
        existing.invalidate_recordset(['balance_refreshed_at', 'branch_refreshed_at', 'balance', 'default_price'])
        by_serial = {}
        for record in existing:
            by_serial.setdefault(record.product_eplus_serial, Inventory.browse())
            by_serial[record.product_eplus_serial] |= record
        products = Inventory._product_lookup_by_eplus_serial(serials)
        updates = {r['product_eplus_serial']: r for r in rows}
        if complete:
            updates.update({serial: {'balance': 0.0} for serial in by_serial if serial not in updates})
        creates = []
        for serial, row in updates.items():
            records = by_serial.get(serial, Inventory.browse())
            timestamps = [r.balance_refreshed_at or r.branch_refreshed_at for r in records]
            latest = max((t for t in timestamps if t), default=False)
            if latest and (latest > started or (scheduled and latest > cutoff)):
                continue
            values = {'balance': row['balance'], 'balance_refreshed_at': now, 'balance_source': source}
            if serial in products:
                values.update(Inventory._product_sync_vals(serial, products))
            if source == 'branch_api':
                values['branch_refreshed_at'] = fetched
                if 'default_price' in row:
                    values['default_price'] = row['default_price']
                    for record in records:
                        if record.default_price != row['default_price']:
                            _logger.info('Branch price cache store=%s product=%s old_price=%s new_price=%s changed_by=%s change_date=%s',
                                         store.id, serial, record.default_price, row['default_price'], self.env.uid, now)
            if records:
                records.write(values)
            elif serial in products:
                creates.append(dict(values, store_id=store.id, product_eplus_serial=serial))
        if creates:
            Inventory.create(creates)

    def _api_refresh_stores(self, stores, *, scheduled=False):
        client = self.env['ab_sales_branch_client']
        if not stores:
            raise UserError(_('No authorized branches are configured.'))
        snapshots = []
        for store in stores:
            started = datetime.utcnow()
            rows, fetched = client._pages(store, 'get_inventory_snapshot')
            client._validate_balance_rows(store, rows)
            snapshots.append((store, rows, fetched, started))
        for store, rows, fetched, started in snapshots:
            self._apply_api_balances(store, rows, fetched, complete=True, started=started, scheduled=scheduled)
        return True

    def btn_update_balance_total(self):
        return self._api_refresh_stores(self.env['ab_sales_branch_client']._stores())

    def btn_update_balance_per_pos(self):
        try:
            return self.env['ab_sales_all_store_balance']._refresh(scheduled=True)
        except (AccessError, UserError):
            self.env.cr.rollback()
            _logger.warning('Scheduled all-store balance refresh unavailable; saved balances retained')
            return True

    def btn_update_balance_default_sales_store(self):
        store = self._get_default_sales_store()
        if not store:
            return True
        return self._api_refresh_stores(store, scheduled=True)


class ApiSalesDay(models.Model):
    _inherit = 'ab_sales_per_day'

    def _fetch_remote_sales_day(self, sale_date):
        client = self.env['ab_sales_branch_client']
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


    @api.onchange('store_id')
    def _onchange_store_id(self):
        for header in self:
            if header.store_id and header.line_ids:
                header.line_ids._recompute_inventory_json()
        return

    @api.model
    def cron_update_status_from_store(self):
        client = self.env['ab_sales_branch_client']
        self.refresh_bill_statuses()
        return True


class ApiPosServices(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_cached_balance_totals(self, product_ids=None, store_id=None, include_sync_metadata=False):
        """All-store display totals come exclusively from the persistent inventory cache."""
        products = self.env['ab_product'].browse([int(p) for p in product_ids or []]).exists()
        products.check_access('read')
        snapshot = self.env['ab_sales_all_store_balance']._read(products.mapped('eplus_serial'))
        if include_sync_metadata:
            return {p.id: {'total_balance': snapshot['totals'].get(p.eplus_serial, 0.0),
                           'total_refresh_success': p.eplus_serial in snapshot['available_serials'],
                           'total_refreshed_at': snapshot['fetched_at']} for p in products}
        return {p.id: snapshot['totals'].get(p.eplus_serial, 0.0) for p in products}

    @api.model
    def pos_refresh_search_balances(self, store_id=None, product_ids=None):
        totals = self.pos_cached_balance_totals(product_ids, store_id, include_sync_metadata=True)
        products = self.env['ab_product'].browse(list(totals))
        store = self.env['ab_store'].browse(int(store_id or 0)).exists()
        if not store:
            return totals
        self.env['ab_sales_ui_api']._inventory_balance_store_ids(store.id)
        client = self.env['ab_sales_branch_client']
        success = False
        try:
            with self.env.cr.savepoint():
                client._balances(store, products.mapped('eplus_serial'))
            success = True
        except (UserError, AccessError):
            _logger.info('Selected branch balance refresh unavailable for store=%s', store.id)
        totals = self.pos_cached_balance_totals(product_ids, store_id, include_sync_metadata=True)
        metadata = self.env['ab_sales_inventory']._branch_sync_metadata(store, products.mapped('eplus_serial'))
        return {p.id: dict(metadata.get(p.eplus_serial, {}), refresh_success=success,
                           **totals[p.id]) for p in products}

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None, include_sync_metadata=False):
        self.env['ab_sales_ui_api']._inventory_balance_store_ids(store_id)
        if not include_sync_metadata:
            return self._refresh_selected_balances(store_id, product_ids, False)
        totals = self.pos_cached_balance_totals(product_ids, store_id, include_sync_metadata=True)
        try:
            with self.env.cr.savepoint():
                return self._refresh_selected_balances(store_id, product_ids, True)
        except (UserError, AccessError):
            products = self.env['ab_product'].browse(list(totals))
            store = self.env['ab_store'].browse(int(store_id or 0)).exists()
            metadata = self.env['ab_sales_inventory']._branch_sync_metadata(store, products.mapped('eplus_serial'))
            return {p.id: dict(metadata.get(p.eplus_serial, {}), refresh_success=False,
                               **totals[p.id]) for p in products}

    @api.model
    def _refresh_selected_balances(self, store_id=None, product_ids=None, include_sync_metadata=False):
        client = self.env['ab_sales_branch_client']
        store = self.env['ab_store'].browse(int(store_id or 0)).exists()
        products = self.env['ab_product'].browse([int(p) for p in product_ids or []]).exists()
        products.check_access('read')
        self.env['ab_sales_ui_api']._inventory_balance_store_ids(store.id)
        rows = client._balances(store, products.mapped('eplus_serial'))
        by_serial = {r['product_eplus_serial']: r['balance'] for r in rows}
        result = {p.id: by_serial[p.eplus_serial] for p in products if p.eplus_serial in by_serial}
        if include_sync_metadata:
            # Use the existing validated branch API, including successful empty
            # snapshots. These display reads never change the cashier's line.
            inventory = self.env['ab_sales_inventory']
            serials = products.mapped('eplus_serial')
            before_stock = inventory._branch_sync_metadata(store, serials)
            stock_rows = client._stock(store, serials)
            stock_by_serial = {}
            for row in stock_rows:
                stock_by_serial.setdefault(row['product_eplus_serial'], []).append(row)
            metadata = self.env['ab_sales_inventory']._branch_sync_metadata(store, products.mapped('eplus_serial'))
            totals = self.pos_cached_balance_totals(products.ids, store.id, include_sync_metadata=True)
            result = {}
            for product in products:
                serial = product.eplus_serial
                if serial not in metadata:
                    continue
                details = dict(metadata[serial], refresh_success=True, **totals[product.id])
                result[product.id] = details
                # The stock API has no snapshot timestamp. Keep the badges if
                # the cache changed while the live stock request was in flight.
                if details['last_sync_at'] != before_stock.get(serial, {}).get('last_sync_at'):
                    continue
                payload = {'data': [dict(row, store_id=store.id, product_id=product.id)
                                    for row in stock_by_serial.get(serial, [])]}
                details.update(inventory_json=payload,
                               available_prices=self._available_prices_from_inventory(product, payload),
                               is_priced=bool(product.is_priced))
            return result
        result['_refreshed_at'] = fields.Datetime.to_string(fields.Datetime.now())
        return result

    def _api_customer(self, store, result):
        self.env['ab_sales_branch_client']._config(store)._validate_identity(result)
        customer = result.get('customer')
        if not customer:
            return result
        if not int(customer.get('eplus_serial') or 0):
            raise UserError(_('The branch returned an invalid customer.'))
        values = {k: customer[k] for k in ('name', 'code', 'mobile_phone', 'work_phone', 'address', 'eplus_serial') if k in customer}
        self.env['ab_customer'].check_access('read')
        Customer = self.env['ab_customer'].sudo().with_context(active_test=False)
        record = Customer.search([('eplus_serial', '=', values['eplus_serial'])], limit=2)
        if len(record) > 1:
            raise UserError(_('The customer reference is ambiguous.'))
        if record:
            self.env['ab_customer'].browse(record.id).check_access('read')
            if not record.active:
                raise UserError(_('The customer is archived in callcenter. Review the customer before using it.'))
            record.write(values)
        else:
            record = Customer.create(dict(values, default_store_id=store.id))
        record = self.env['ab_customer'].browse(record.id)
        record.check_access('read')
        return dict(result, customer=self._customer_payload(record))

    @api.model
    def pos_customer_lookup(self, phone=None, store_id=None):
        if not store_id:
            return {'status': 'need_store', 'message': _('Select a branch to search BConnect.')}
        client = self.env['ab_sales_branch_client']
        store = self.env['ab_store'].browse(int(store_id or 0)).exists()
        client._config(store)
        phone = self._normalize_phone(phone)
        if not phone:
            raise UserError(_('Enter a phone number.'))
        Customer = self.env['ab_customer']
        Customer.check_access('read')
        phone_domain = (fields.Domain('mobile_phone', '=', phone)
                        | fields.Domain('work_phone', '=', phone)
                        | fields.Domain('delivery_phone', '=', phone))
        customer = Customer.search(fields.Domain('active', '=', True) & phone_domain, limit=1)
        if customer:
            return {'status': 'found', 'customer': self._customer_payload(customer)}
        return self._api_customer(store, client._call(store, 'lookup_customer', phone))

    @api.model
    def pos_customer_create(self, phone=None, name=None, address=None, store_id=None):
        client = self.env['ab_sales_branch_client']
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
        snapshot = self.env['ab_sales_all_store_balance']._read(product_serials)
        rows = []
        unmapped_ids = set(snapshot.get('unmapped_store_ids', []))
        for store in self.env['ab_sales_all_store_balance']._stores():
            for serial in sorted(snapshot['totals']):
                balance = snapshot['balances'].get((store.id, serial))
                rows.append((store.display_name, str(serial), str(balance) if balance is not None else '—',
                             _('This branch has no E-Plus ID.') if store.id in unmapped_ids else
                             _('Cached balance') if balance is not None else _('Unavailable')))
        return self.env['ir.qweb']._render('ab_sales.callcenter_product_store_balance_html', {'rows': rows})


class ApiProductSearch(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def search_products(self, *args, **kwargs):
        rows = super().search_products(*args, **kwargs)
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
