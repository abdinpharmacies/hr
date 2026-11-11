"""Backend boundary: live committed reads and native sales workflows."""
import math
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError
from .ab_sales_pos_backend import selected_server

class SalesInventoryBackend(models.Model):
    _inherit = 'ab_sales_inventory'

    def _backend_inventory_snapshot(self, store, product_serials=None):
        """Complete active catalog at one branch; committed read, no ORM writes."""
        params = [int(store.eplus_serial)]
        restriction = ''
        if product_serials is not None:
            serials = sorted({int(serial) for serial in product_serials if int(serial) > 0})
            if not serials:
                return []
            restriction = ' AND ic.itm_id IN (%s)' % ','.join('?' for serial in serials)
            params.extend(serials)
        with self.connect_eplus(server=selected_server(self, store), param_str='?', autocommit=False, propagate_error=True) as conn:
            with conn.cursor() as cur:
                # One committed statement; inactive/missing items do not masquerade as zero stock.
                cur.execute('''SELECT ic.itm_id, ic.itm_def_sell_price,
                    COALESCE(SUM(CAST(ics.itm_qty AS decimal(28,8)) / NULLIF(ic.itm_unit1_unit3,0)),0),
                    ic.itm_unit1_unit3
                    FROM item_catalog ic
                    LEFT JOIN Item_Class_Store ics ON ics.itm_id=ic.itm_id AND ics.sto_id=?
                    WHERE ic.itm_active=1''' + restriction + '''
                    GROUP BY ic.itm_id,ic.itm_def_sell_price,ic.itm_unit1_unit3 ORDER BY ic.itm_id''', tuple(params))
                rows = cur.fetchall()
        result = []
        for serial, price, qty, factor in rows:
            if not factor or float(factor) <= 0 or not all(math.isfinite(float(v or 0)) for v in (price, qty, factor)):
                raise UserError(_('Invalid product unit conversion in E-Plus.'))
            result.append({'product_eplus_serial': int(serial), 'store_eplus_serial': int(store.eplus_serial),
                           'balance': max(0.0, float(qty)), 'default_price': float(price or 0)})
        return result

    def _backend_product_balances(self, store, serials):
        """Refresh native inventory cache; return balances/prices, never stale zeros.

        Use committed reads with native POS timeouts and cache updates. Posting
        independently revalidates batch quantities. Caller commits ORM.
        """
        serials = sorted({int(serial) for serial in serials if int(serial) > 0})
        if len(serials) > 200:
            raise UserError(_('At most 200 products may be requested.'))
        if not serials:
            return []
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in', serials))
        if set(products.mapped('eplus_serial')) != set(serials):
            raise AccessError(_('Requested products are not accessible.'))
        balances = self.env['ab_sales_pos_api'].with_context(
            _ab_sales_backend_committed_read=True).pos_refresh_pos_balances(store.id, products.ids)
        if set(balances) != set(products.ids):
            raise UserError(_('Branch inventory is unavailable. Retry the refresh.'))
        inventory = self.search(fields.Domain('store_id', '=', store.id)
                                & fields.Domain('product_eplus_serial', 'in', serials))
        prices = {int(row.product_eplus_serial): row.default_price for row in inventory}
        if set(prices) != set(serials):
            raise UserError(_('Branch inventory is unavailable. Retry the refresh.'))
        by_serial = {product.eplus_serial: balances[product.id] for product in products}
        return [{'product_eplus_serial': serial, 'store_eplus_serial': store.eplus_serial,
                 'balance': by_serial[serial], 'default_price': prices[serial]}
                for serial in serials]
