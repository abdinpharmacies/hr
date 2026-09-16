"""Sales adaptations owned by the API; ordinary branch calls retain their behavior."""
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

from .routing import current_request, request_store, selected_server


class ApiStockReader(models.Model):
    _inherit = 'ab_sales_header'

    @api.model
    def _read_store_stock(self, store, product_serials, crx=None):
        """Read committed batch stock; callers own display and price-cache updates."""
        if request_store(self) != store:
            raise AccessError(_('The SQL store does not match the authorized API store.'))
        store.ensure_one()
        store.check_access('read')
        if not store.active or not store.allow_sale or store.eplus_serial <= 0:
            raise UserError(_('An active sales store with an E-Plus serial is required.'))
        serials = sorted({int(serial) for serial in product_serials if int(serial) > 0})
        if not serials:
            return []
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in', serials))
        if set(products.mapped('eplus_serial')) != set(serials):
            raise AccessError(_('Requested products are not accessible.'))
        server = self._get_store_server(store)
        if crx is None:
            if not server:
                raise UserError(_('The selected store has no E-Plus server address.'))
            # Match the existing get_connection() lifetime: the connector owns
            # the connection. API scopes close their own pool at request exit.
            with self.connect_eplus(server=server, autocommit=False, charset='UTF-8', param_str='?') as connection:
                crx = connection.cursor()
        data = []
        for offset in range(0, len(serials), 200):
            batch = serials[offset:offset + 200]
            slots = ','.join(['?'] * len(batch))
            crx.execute(f'''
                SELECT ics.c_id AS source_id, ics.itm_id AS product_eplus_serial,
                       ics.sto_id AS store_eplus_serial, ics.sell_price AS price,
                       ics.itm_qty AS qty_in_small_unit,
                       ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS qty,
                       ics.pharm_price + ics.sell_tax AS cost, ics.itm_expiry_date AS exp_date
                  FROM Item_Class_Store ics
                  JOIN item_catalog ic ON ic.itm_id = ics.itm_id
                 WHERE ics.sto_id = ? AND ics.itm_id IN ({slots}) AND ics.itm_qty > 0
                 ORDER BY ics.itm_id, ics.itm_expiry_date, ics.c_id
            ''', tuple([int(store.eplus_serial)] + batch))
            names = ('source_id', 'product_eplus_serial', 'store_eplus_serial', 'price',
                     'qty_in_small_unit', 'qty', 'cost', 'exp_date')
            for row in crx.fetchall():
                values = row if isinstance(row, dict) else dict(zip(names, row))
                if (int(values['store_eplus_serial']) != store.eplus_serial
                        or int(values['product_eplus_serial']) not in batch):
                    raise AccessError(_('Stock rows do not belong to the selected store and products.'))
                qty = values['qty']
                if qty is None or not math.isfinite(float(qty)) or float(qty) <= 0:
                    raise UserError(_('Invalid product unit conversion in E-Plus.'))
                numeric = {name: float(values[name] or 0) for name in ('price', 'qty_in_small_unit', 'qty', 'cost')}
                if not all(math.isfinite(value) for value in numeric.values()):
                    raise UserError(_('E-Plus returned invalid stock values.'))
                data.append({**numeric, 'source_id': int(values['source_id']),
                             'product_eplus_serial': int(values['product_eplus_serial']),
                             'store_eplus_serial': int(values['store_eplus_serial']),
                             'exp_date': str(values['exp_date']) if values['exp_date'] else ''})
        return data


class ApiSaleInventory(models.Model):
    _inherit = 'ab_sales_line'

    def _recompute_inventory_json(self, crx=None):
        if not current_request(self):
            return super()._recompute_inventory_json(crx=crx)
        if not self.header_id:
            return
        if len(self.header_id) != 1:
            raise UserError(_("Can not get data for multiple headers"))
        store = self.header_id.store_id
        if request_store(self) != store:
            raise AccessError(_('The SQL store does not match the authorized API store.'))
        if crx is None:
            crx = self.header_id.get_connection().cursor()
        # Refresh the existing sales price cache separately from the stock reader.
        for product in self.product_id:
            self._update_default_price(crx, product, store)
        rows = self.env['ab_sales_header']._read_store_stock(
            store, self.product_id.mapped('eplus_serial'), crx=crx)
        by_product = {}
        for row in rows:
            if row['qty'] >= 0.01:
                by_product.setdefault(row['product_eplus_serial'], []).append(row)
        for line in self:
            if line.product_id:
                line.inventory_json = {'data': [dict(row, store_id=store.id, product_id=line.product_id.id)
                    for row in by_product.get(line.product_id.eplus_serial, [])]}


class ApiReturnWorkflow(models.Model):
    _inherit = 'ab_sales_return_header'

    def _get_store_server(self, store):
        if current_request(self):
            return selected_server(self, store)
        return super()._get_store_server(store)

    def get_connection(self):
        if not current_request(self):
            return super().get_connection()
        self.ensure_one()
        if request_store(self) != self.store_id:
            raise AccessError(_('The SQL store does not match the authorized API store.'))
        return ReturnConnection(super().get_connection(), self)

    def _get_invoice_status(self, cur, sth_id):
        if not current_request(self):
            return super()._get_invoice_status(cur, sth_id)
        if request_store(self) != self.store_id or int(sth_id) != self.origin_header_id:
            raise AccessError(_('Return invoice does not match the request.'))
        cur.execute(
            "SELECT sth_flag, sto_id FROM sales_trans_h WHERE sth_id=? AND sto_id=?",
            (sth_id, int(self.sto_eplus_serial))
        )
        status = cur.fetchone()
        if not status:
            return "Not Exist"
        elif status[0] == 'C':
            return "Saved"
        else:
            return "Pending"

    def action_load_lines(self):
        """Load the selected store's invoice through normal ORM permissions."""
        if not current_request(self):
            return super().action_load_lines()
        self.ensure_one()
        if request_store(self) != self.store_id:
            raise AccessError(_('The SQL store does not match the authorized API store.'))
        header = self
        store = self.store_id
        store.check_access('read')
        if not self.origin_header_id:
            raise UserError(_("Please enter sth_id (Original Invoice) first."))
        header.check_access('write')
        header.line_ids.check_access('write')
        if any(
                line.sth_id != header.origin_header_id or line.sto_id != store.eplus_serial
                for line in header.line_ids):
            raise AccessError(_('Return invoice does not match the request.'))
        if header.status == 'saved':
            raise UserError(_('Saved returns cannot be modified.'))
        if not store or not self._get_store_server(store):
            raise UserError(_('The selected store has no E-Plus server address.'))
        invoice = int(header.origin_header_id)
        # Committed reads: no NOLOCK for returnable quantities. The existing
        # posting transaction revalidates the invoice and available quantities.
        cursor = self.get_connection().cursor()
        cursor.execute('SELECT total_bill_net FROM sales_trans_h WHERE sth_id = ? AND sto_id = ?',
                       (invoice, int(store.eplus_serial)))
        source = cursor.fetchone()
        if not source:
            raise UserError(_('Invoice does not belong to this branch.'))
        total = float(source[0] or 0)
        cursor.execute('''
            SELECT d.std_id, d.itm_id, d.c_id, d.qnty, d.itm_unit,
                   d.itm_sell, d.itm_cost, d.itm_aver_cost, d.itm_back, d.itm_nexist,
                   CASE WHEN ic.itm_id IS NOT NULL THEN ISNULL(ic.itm_unit1_unit2, 1) END,
                   CASE WHEN ic.itm_id IS NOT NULL THEN ISNULL(ic.itm_unit1_unit3, 1) END
              FROM sales_trans_d d
              JOIN sales_trans_h h ON h.sth_id = d.sth_id
              LEFT JOIN item_catalog ic ON ic.itm_id = d.itm_id
             WHERE d.sth_id = ? AND h.sto_id = ?
             ORDER BY d.std_id
        ''', (invoice, int(store.eplus_serial)))
        rows = cursor.fetchall()
        if not rows:
            raise UserError(_('The source invoice has no returnable lines.'))
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in',
                                                   list({int(row[1]) for row in rows})))
        by_product = {}
        for product in products:
            by_product.setdefault(product.eplus_serial, self.env['ab_product'])
            by_product[product.eplus_serial] |= product
        source_header = self.env['ab_sales_header'].search(
            fields.Domain('eplus_serial', '=', invoice) & fields.Domain('store_id', '=', store.id),
            order='id desc', limit=1)
        source_header.line_ids.check_access('read')
        preferred = {}
        for line in source_header.line_ids:
            if line.uom_id:
                preferred.setdefault(line.product_id.eplus_serial, line.uom_id.id)
        existing = {line.std_id: line for line in header.line_ids}
        source_ids = [int(row[0]) for row in rows]
        if len(set(source_ids)) != len(source_ids) or set(existing) - set(source_ids):
            raise UserError(_('Return invoice lines changed. Review the source invoice before retrying.'))
        creates = []
        for (std_id, item_id, class_id, qty, unit, sell, cost, average_cost,
             returned, nonexistent, unit12, unit13) in rows:
            product = by_product.get(int(item_id), self.env['ab_product'])
            if len(product) != 1 or unit12 is None or unit13 is None:
                raise UserError(_('Return product is missing or ambiguous on this branch.'))
            unit12, unit13 = float(unit12 or 1), float(unit13 or 1)
            source_factor = header._factor_for_itm_unit(int(unit or 3), unit12, unit13)
            current = existing.get(int(std_id))
            if current and current.itm_eplus_id != int(item_id):
                raise UserError(_('Return product does not match the original invoice line.'))
            uom = current.uom_id if current and current.uom_id else header._find_uom_by_factor(
                product, source_factor, preferred_uom_id=preferred.get(int(item_id)))
            if not uom or uom.category_id != product.uom_category_id or uom.factor <= 0:
                raise UserError(_('Branch product unit is missing or ambiguous.'))
            uom.check_access('read')
            factor = float(uom.factor)
            sold = float(qty or 0)
            remaining = max(sold - float(returned or 0), 0)
            values = {
                'header_id': header.id, 'sale_line_id': int(std_id),
                'product_id': product.id, 'uom_id': uom.id,
                'source_itm_unit': int(unit or 3), 'source_uom_factor': source_factor,
                'item_unit1_unit2': unit12, 'item_unit1_unit3': unit13,
                'qty_sold_source': sold, 'max_returnable_source': remaining,
                'qty_sold': header._to_display_qty(sold, source_factor, factor),
                'max_returnable_qty': header._to_display_qty(remaining, source_factor, factor),
                'sell_price': header._to_display_price(float(sell or 0), source_factor, factor),
                'cost': header._to_display_price(float((average_cost if average_cost is not None else cost) or 0),
                                               source_factor, factor),
                'itm_eplus_id': int(item_id), 'sth_id': invoice, 'sto_id': int(store.eplus_serial),
                'c_id': int(class_id or 0), 'std_id': int(std_id), 'itm_nexist': float(nonexistent or 0),
            }
            if current:
                current.write(values)  # Retain the selected unit and qty_str.
            else:
                creates.append(values)
        if creates:
            self.env['ab_sales_return_line'].create(creates)
        header.total_sales_net = total
        return {'type': 'ir.actions.act_window', 'res_model': header._name, 'res_id': header.id,
                'view_mode': 'form', 'target': self.env.context.get('curr_target', 'current')}


class ReturnConnection:
    """Adapt only the legacy return header reads; keep its posting transaction."""

    def __init__(self, connection, header):
        self._connection = connection
        self._header = header

    def __getattr__(self, name):
        return getattr(self._connection, name)

    def cursor(self, *args, **kwargs):
        return ReturnCursor(self._connection.cursor(*args, **kwargs), self._header)


class ReturnCursor:
    # These two inline reads have no overridable helper in ab_sales. Keep this
    # exact allowlist synchronized with its posting method, without copying writes.
    _legacy_reads = {
        'select isnull(total_bill_net, 0) from sales_trans_h where sth_id = ?',
        'select isnull(sec_insert_date, 0) from sales_trans_h where sth_id = ?',
    }
    _scoped_reads = {
        'select total_bill_net from sales_trans_h where sth_id = ? and sto_id = ?',
        'select sth_flag, sto_id from sales_trans_h where sth_id=? and sto_id=?',
    }

    def __init__(self, cursor, header):
        self._cursor = cursor
        self._header = header

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def execute(self, sql, params=()):
        header = self._header
        if request_store(header) != header.store_id:
            raise AccessError(header.env._('The SQL store does not match the authorized API store.'))
        normalized = ' '.join(sql.lower().split())
        invoice, store = int(header.origin_header_id), int(header.sto_eplus_serial)
        if normalized in self._legacy_reads:
            if tuple(params) != (invoice,):
                raise AccessError(header.env._('Return invoice does not match the request.'))
            sql += ' AND sto_id = ?'
            params = (invoice, store)
        elif normalized.startswith('select ') and 'from sales_trans_h' in normalized:
            if normalized not in self._scoped_reads:
                raise UserError(header.env._('Unsupported return invoice query. Update the Branch API integration.'))
            if tuple(params) != (invoice, store):
                raise AccessError(header.env._('Return invoice does not match the request.'))
        self._cursor.execute(sql, params)
        return self
