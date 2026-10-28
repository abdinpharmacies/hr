"""Backend boundary: live committed reads and native sales workflows."""
from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError
from .ab_sales_pos_backend import current_request, request_store, selected_server

class SalesReturnBackend(models.Model):
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

    def _load_return_lines(self, cur=None):
        """Load the selected store's invoice through normal ORM permissions."""
        if not current_request(self):
            return super()._load_return_lines(cur=cur)
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
        cursor = cur if cur is not None else self.get_connection().cursor()
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


    def _get_return_submission_connection(self):
        scope = current_request(self)
        if not scope:
            return super()._get_return_submission_connection()
        pooled = self.get_connection()
        while isinstance(pooled, ReturnConnection):
            pooled = pooled._connection
        factory = scope.connection_factories.get(id(pooled))
        if not factory:
            raise UserError(_('Branch submission could not be confirmed. Retry the original bill.'))
        # Preserve API branch checks on the fresh native transaction. Neither
        # this connection nor its cursors may reconnect or replay statements.
        connection = self._clone_external_connection(pooled, factory=factory)
        return ReturnConnection(connection, self)

    def _backend_invoice_date(self, store, invoice, require_saved=False):
        """Validate branch and status by committed read; no ORM changes."""
        server = selected_server(self, store)
        if not server:
            raise UserError(_('The branch E-Plus server is not configured.'))
        with self.connect_eplus(server=server, autocommit=False, charset='UTF-8', param_str='?', propagate_error=True) as conn:
            cur = conn.cursor()
            cur.execute('SELECT sth_id, sth_flag, sec_insert_date FROM sales_trans_h WHERE sth_id = ? AND sto_id = ?',
                        (int(invoice), int(store.eplus_serial)))
            source = cur.fetchone()
            if not source:
                raise UserError(_('Invoice does not belong to this branch.'))
            if require_saved and source[1] != 'C':
                raise UserError(_('Source invoice must be saved before posting a return.'))
            return source[2]

    def _backend_reconcile(self, evidence=None):
        """Recover by native return marker; no posting, caller commits lifecycle state.

        Owns and rolls back/closes a read/lock transaction. Incomplete/conflicting
        evidence raises without declaring a retry safe.
        """
        self.ensure_one()
        self.check_access('read')
        header = self
        evidence = evidence or {}
        def conflict(reason):
            raise UserError(reason)
        header = header.sudo()
        with header._return_attempt():
            connection = header._get_return_submission_connection()
            try:
                cur = connection.cursor()
                cur.execute('SET LOCK_TIMEOUT 5000')
                cur.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
                cur.execute(
                    'SELECT sth_id FROM sales_trans_h WITH (UPDLOCK, HOLDLOCK) WHERE sth_id = ? AND sto_id = ?',
                    (int(header.origin_header_id), int(header.sto_eplus_serial)))
                if not cur.fetchone():
                    raise AccessError(_('Return invoice does not match the request.'))
                recovered = header._find_committed_return(cur)
                if recovered:
                    evidence = evidence or {}
                    if any((evidence.get(name) and evidence[name] != recovered[name])
                           or (header[name] and header[name] != recovered[name]) for name in recovered):
                        conflict(_('The return, cash transaction and payment records do not form one complete transaction.'))
                    header._write_return_state(dict(recovered, status='saved', replication_posted=True,
                                                    push_message=False))
                    return True
                else:
                    # Missing markers cannot invalidate previously recorded success.
                    if (header.status == 'saved' or header.sales_return_id or header.f_transaction_id
                            or header.replication_posted or evidence):
                        conflict(_('The return, cash transaction and payment records do not form one complete transaction.'))
                    header._write_return_state({'status': 'prepending', 'sales_return_id': False,
                                                'f_transaction_id': False, 'replication_posted': False})
                    return False
            finally:
                try:
                    connection.rollback()  # Read/lock-only reconciliation never posts.
                finally:
                    connection.close()

    def _backend_legacy_reconcile(self, token, **journal):
        """Observe old return evidence via shared recovery; never submit."""
        return self.env['ab_sales_header']._backend_legacy_reconcile(
            token, kind='return', target=self, **journal)

    def _backend_prepare(self):
        """Read committed returnable quantities and update draft lines; caller commits."""
        return self.action_load_lines()

    def _backend_submit(self):
        """Delegate posting to native return transaction and installed extensions."""
        return self.action_push_to_eplus_return()


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
        'select d.std_id, d.itm_id, d.c_id, d.qnty, d.itm_unit, d.itm_sell, d.itm_cost, d.itm_aver_cost, d.itm_back, d.itm_nexist, case when ic.itm_id is not null then isnull(ic.itm_unit1_unit2, 1) end, case when ic.itm_id is not null then isnull(ic.itm_unit1_unit3, 1) end from sales_trans_d d join sales_trans_h h on h.sth_id = d.sth_id left join item_catalog ic on ic.itm_id = d.itm_id where d.sth_id = ? and h.sto_id = ? order by d.std_id',
        'select total_bill_net from sales_trans_h where sth_id = ? and sto_id = ?',
        'select sth_flag, sto_id from sales_trans_h where sth_id=? and sto_id=?',
        'select sth_id from sales_trans_h with (updlock, holdlock) where sth_id = ? and sto_id = ?',
        'select std_id, itm_id, c_id, qnty, itm_unit, itm_sell, itm_cost, itm_aver_cost, itm_back, itm_nexist '
        'from sales_trans_d where sth_id=? '
        'and exists (select 1 from sales_trans_h h where h.sth_id = sales_trans_d.sth_id and h.sto_id = ?) '
        'order by std_id',
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
