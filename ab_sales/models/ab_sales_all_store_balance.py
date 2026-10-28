"""The callcenter's bounded, read-only exception to branch API transport."""
from datetime import datetime
from decimal import Decimal
from contextlib import contextmanager
import logging
import math

from odoo import fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import config


_logger = logging.getLogger(__name__)

LIVE_QUERY_TIMEOUT = 2
SCHEDULED_QUERY_TIMEOUT = 120


class AllStoreBalance(models.AbstractModel):
    _name = 'ab_sales_all_store_balance'
    _inherit = 'ab_eplus_connect'
    _description = 'All Store Balance Reader'

    def _stores(self):
        # Explicit business exception: transfer balances are visible across branches,
        # independently of employee assignment and branch API registration.
        return self.env['ab_store'].sudo().with_context(active_test=False).search(fields.Domain('allow_transfer', '=', True))

    def _read(self, product_serials):
        serials = sorted({int(s) for s in product_serials or [] if s and int(s) > 0})
        stores = self._stores()
        mapped_stores = stores.filtered(lambda store: store.eplus_serial and store.eplus_serial > 0)
        unmapped_store_ids = (stores - mapped_stores).ids
        products = self.env['ab_product'].with_context(active_test=False).search(
            fields.Domain('eplus_serial', 'in', serials))
        if set(serials) - set(products.mapped('eplus_serial')):
            raise AccessError(self.env._('Some products are unavailable at the branch.'))
        result = {'totals': {s: 0.0 for s in serials}, 'balances': {}, 'metadata': {},
                  'success': True, 'fetched_at': False, 'unmapped_store_ids': unmapped_store_ids}
        rows = self.env['ab_sales_inventory'].sudo().search(
            fields.Domain('store_id', 'in', mapped_stores.ids)
            & fields.Domain('product_eplus_serial', 'in', serials), order='id desc')
        # Legacy duplicates represent snapshots, not additive stock. Prefer the newest.
        rows = rows.sorted(lambda r: (r.balance_refreshed_at or r.branch_refreshed_at
                                     or fields.Datetime.to_datetime('1970-01-01'), r.id), reverse=True)
        for row in rows:
            pair = (row.store_id.id, row.product_eplus_serial)
            if pair in result['balances']:
                continue
            result['balances'][pair] = row.balance
            timestamp = row.balance_refreshed_at or row.branch_refreshed_at
            result['metadata'][pair] = {
                'source': row.balance_source or ('branch_api' if row.branch_refreshed_at else 'cache'),
                'refreshed_at': fields.Datetime.to_string(timestamp) if timestamp else False,
            }
            result['totals'][row.product_eplus_serial] += row.balance
        result['available_serials'] = list({serial for _, serial in result['balances']})
        return result

    def _read_live(self, product):
        """Popup-only read; neither a successful read nor fallback saves stock."""
        product.ensure_one()
        product.check_access('read')
        serial = product.eplus_serial
        stores = self._stores().sorted('id')
        store_map, unavailable = {}, {}
        for store in stores:
            if store.eplus_serial <= 0:
                unavailable[store.id] = self.env._('This branch has no E-Plus ID.')
            elif store.eplus_serial in store_map:
                unavailable[store.id] = self.env._('Another branch uses this E-Plus ID.')
            else:
                store_map[store.eplus_serial] = store.id
        result = {'balances': {}, 'metadata': {}, 'initial_error': False,
                  'cached_fallback': False, 'unavailable_reasons': unavailable}
        if serial <= 0:
            result['unavailable_reasons'] = {
                store.id: self.env._('Some products are unavailable at the branch.') for store in stores}
            return result
        if not store_map:
            return result
        try:
            balances = self._query([serial], store_map, live=True)
        except AccessError:
            raise
        except Exception:
            # The connector wraps driver failures as Exception. Do not expose
            # connection details, or turn a failed read into confirmed zero stock.
            _logger.warning('Live all-store balance read failed; using saved balances', exc_info=True)
            snapshot = self._read([serial])
            result.update(initial_error=self.env._('Live B-Connect balances could not be loaded. Saved balances are shown where available.'),
                          cached_fallback=True)
            for store_id in store_map.values():
                pair = (store_id, serial)
                if pair in snapshot['balances']:
                    result['balances'][pair] = max(0.0, snapshot['balances'][pair])
                    result['metadata'][pair] = snapshot['metadata'][pair]
            return result
        fetched = fields.Datetime.to_string(fields.Datetime.now())
        for store_id in store_map.values():
            pair = (store_id, serial)
            result['balances'][pair] = max(0.0, balances.get(pair, 0.0))
            result['metadata'][pair] = {'source': 'eplus', 'refreshed_at': fetched}
        return result

    def _refresh(self, product_serials=None, scheduled=False):
        """Persistent refresh for existing scheduled/manual inventory operations."""
        started = datetime.utcnow()
        stores = self._stores().filtered(lambda s: s.eplus_serial > 0)
        if not stores:
            return True
        store_map = {s.eplus_serial: s.id for s in stores}
        if len(store_map) != len(stores):
            raise UserError(self.env._('The branch returned invalid stock data.'))
        serials = None if product_serials is None else sorted({int(s) for s in product_serials if int(s) > 0})
        if serials == []:
            return True
        if serials is not None:
            self._read(serials)  # Enforce product access before the explicit external read.
        balances = self._query(serials, store_map)
        inventory = self.env['ab_sales_inventory']
        by_store = {s.id: [] for s in stores}
        for (store_id, serial), balance in balances.items():
            by_store[store_id].append({'product_eplus_serial': serial, 'balance': balance})
        for store in stores.sorted('id'):
            rows = by_store[store.id]
            if serials is not None:
                found = {r['product_eplus_serial'] for r in rows}
                rows += [{'product_eplus_serial': serial, 'balance': 0.0}
                         for serial in serials if serial not in found]
            inventory._apply_balance_cache(store, rows, 'eplus', started,
                                           complete=serials is None, scheduled=scheduled)
        return True

    @contextmanager
    def _balance_cursor(self, conn, query_timeout):
        raw = conn._cn
        target = getattr(raw, '_conn', raw)
        attribute = 'query_timeout' if hasattr(target, 'query_timeout') else 'timeout'
        if not hasattr(target, attribute):
            raise UserError(self.env._('A bounded B-Connect query is unavailable.'))
        previous = getattr(target, attribute)
        try:
            setattr(target, attribute, query_timeout)
            if getattr(target, attribute) != query_timeout:
                raise UserError(self.env._('A bounded B-Connect query is unavailable.'))
            with raw.cursor() as cursor:
                yield cursor
        finally:
            setattr(target, attribute, previous)

    def _query(self, serials, store_map, *, live=False):
        """Committed informational reads; branch API remains authoritative at sale time."""
        batches = []
        store_serials = sorted(store_map)
        options = {'connect_timeout': 5, 'validation_timeout': 5}
        query_timeout = SCHEDULED_QUERY_TIMEOUT
        if live:
            server = config.get('bconnect_ip1')
            if not server:
                raise UserError(self.env._('The main B-Connect server is not configured.'))
            options.update(server=server, connect_timeout=2, validation_timeout=2)
            query_timeout = LIVE_QUERY_TIMEOUT
        query_failed = False
        with self.connect_eplus(param_str='%s', charset='CP1256',
                                propagate_error=True, **options) as conn:
            try:
                with self._balance_cursor(conn, query_timeout) as cursor:
                    for start in range(0, len(store_serials), 500):
                        store_batch = store_serials[start:start + 500]
                        for batch in ([None] if serials is None else
                                      [serials[i:i + 200] for i in range(0, len(serials), 200)]):
                            products_sql = ','.join(['%s'] * len(batch or []))
                            product_filter = f'stock.itm_id IN ({products_sql}) AND' if batch is not None else ''
                            stores_sql = ','.join(['%s'] * len(store_batch))
                            cursor.execute(f"""
                                SELECT stock.itm_id, stock.sto_id,
                                       SUM(CAST(CASE
                                                   WHEN item.itm_unit1_unit3 IS NULL
                                                        OR item.itm_unit1_unit3 <= 0
                                                        OR stock.itm_qty IS NULL THEN 0
                                                   ELSE stock.itm_qty / item.itm_unit1_unit3
                                                END AS decimal(18,2))),
                                       SUM(CASE WHEN item.itm_unit1_unit3 IS NULL
                                                      OR item.itm_unit1_unit3 <= 0
                                                      OR stock.itm_qty IS NULL THEN 1 ELSE 0 END)
                                FROM Item_Class_Store stock
                                LEFT JOIN Item_Catalog item ON item.itm_id = stock.itm_id
                                WHERE {product_filter} stock.sto_id IN ({stores_sql})
                                GROUP BY stock.itm_id, stock.sto_id
                            """, tuple((batch or []) + store_batch))
                            batches.append((batch, store_batch, cursor.fetchall()))
            except Exception:
                query_failed = True
        if query_failed:
            raise UserError(self.env._('The branch connection failed. Check its network address and availability.'))
        # Validate outside the connector context: it wraps any exception from its
        # caller as a database failure, even a normal Odoo validation error.
        balances = {}
        for batch, store_batch, rows in batches:
            for serial, store_serial, quantity, invalid in rows:
                serial = self._source_identifier(serial)
                store_serial = self._source_identifier(store_serial)
                if ((batch is not None and serial not in batch)
                        or store_serial not in store_batch or invalid or quantity is None
                        or isinstance(quantity, bool)):
                    raise UserError(self.env._('The branch returned invalid stock data.'))
                try:
                    quantity = float(quantity)
                except (TypeError, ValueError, OverflowError):
                    raise UserError(self.env._('The branch returned invalid stock data.')) from None
                if not math.isfinite(quantity):
                    raise UserError(self.env._('The branch returned invalid stock data.'))
                pair = (store_map[store_serial], serial)
                if pair in balances:
                    raise UserError(self.env._('The branch returned invalid stock data.'))
                balances[pair] = quantity
        return balances

    def _source_identifier(self, value):
        """SQL Server decimal(18,0) identifiers arrive as Decimal, not int."""
        if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
            raise UserError(self.env._('The branch returned invalid stock data.'))
        try:
            identifier = int(value)
        except (ValueError, OverflowError):
            raise UserError(self.env._('The branch returned invalid stock data.')) from None
        if identifier <= 0 or identifier != value:
            raise UserError(self.env._('The branch returned invalid stock data.'))
        return identifier
