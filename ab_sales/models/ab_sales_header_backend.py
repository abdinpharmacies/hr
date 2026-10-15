"""Backend boundary: live committed reads and native sales workflows."""
import math
import hashlib
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import config
from odoo.addons.ab_eplus_connect.models.ab_eplus_connect import ConnectionProxy
from .ab_sales_pos_backend import current_request, request_store, selected_server, pin_server

class SalesHeaderBackend(models.Model):
    _inherit = 'ab_sales_header'

    @api.model
    def _backend_stock_lines(self, store, product_serials, crx=None):
        """Read committed batch stock; callers own display and price-cache updates."""
        if current_request(self) and request_store(self) != store:
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
            with self.connect_eplus(server=server, autocommit=False, charset='UTF-8', param_str='?', propagate_error=True) as connection:
                return self._backend_stock_lines(store, serials, crx=connection.cursor())
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


    def _get_store_server(self, store):
        return pin_server(self, store, super()._get_store_server(store))


    def _get_submission_connection(self):
        scope = current_request(self)
        if not scope:
            return super()._get_submission_connection()
        pooled = self.get_connection()
        if not isinstance(pooled, ConnectionProxy):
            return pooled
        factory = scope.connection_factories.get(id(pooled))
        if not factory:
            raise UserError(_('Branch submission could not be confirmed. Retry the original bill.'))
        # The API read pool disables reconnect. Native sales still need a new
        # physical session, with neither reconnection nor statement replay.
        return ConnectionProxy(factory(), wrap_dict_cursor=pooled._wrap_dict_cursor)

    def _backend_invoice_statuses(self, store, serials):
        """Branch-filtered committed status read; no lifecycle updates or commits."""
        data = []
        serials = sorted({int(serial) for serial in serials if int(serial) > 0})
        if not serials:
            return data
        with self.connect_eplus(server=selected_server(self, store), param_str='?',
                                autocommit=False, propagate_error=True) as conn:
            with conn.cursor() as cur:
                for offset in range(0, len(serials), 200):
                    batch = serials[offset:offset + 200]
                    cur.execute('SELECT sth_id,sth_flag FROM sales_trans_h WHERE sto_id=? AND sth_id IN ('
                                + ','.join('?' for serial in batch) + ')', (store.eplus_serial, *batch))
                    for serial, flag in cur.fetchall():
                        if int(serial) not in batch:
                            raise AccessError(_('Invoice does not belong to this branch.'))
                        data.append({'invoice': int(serial),
                                     'status': 'saved' if (flag or '').strip() == 'C' else 'pending'})
        return data

    def _backend_submit(self):
        """Native submit, including installed extensions and transaction ownership."""
        return self.action_submit()

    def _backend_reconcile(self):
        """Recover an Unknown sale from committed rows only; never submit.

        Updates lifecycle fields under bounded elevation; caller commits Odoo.
        Owns a fresh external read/lock transaction, always rolled back/closed.
        Failures propagate and leave the outcome unknown.
        """
        self.ensure_one()
        self.check_access('read')
        header = self
        if header.status != 'unknown':
            return
        with header._submission_attempt():
            connection = header._get_submission_connection()
            try:
                cur = connection.cursor()
                serial = header._find_committed_eplus_invoice(cur)
                if serial:
                    cur.execute('''SELECT h.sth_flag, h.no_of_items,
                        (SELECT COUNT(*) FROM sales_trans_d d WITH (UPDLOCK, HOLDLOCK) WHERE d.sth_id=h.sth_id)
                        FROM sales_trans_h h WITH (UPDLOCK, HOLDLOCK) WHERE h.sth_id=? AND h.sto_id=?''',
                        (serial, int(header.store_id.eplus_serial)))
                    row = cur.fetchone()
                    if not row or row[0] not in ('P', 'C') or not row[2] or int(row[1] or 0) != int(row[2]):
                        raise UserError(_('The branch invoice is incomplete; the original bill remains Unknown.'))
                    header.sudo()._write_submission_state({'eplus_serial': serial,
                        'status': 'saved' if row[0] == 'C' else 'pending', 'push_state': 'success', 'push_message': ''})
            finally:
                try:
                    connection.rollback()
                finally:
                    connection.close()

    def _backend_legacy_reconcile(self, token, evidence=None, recovery_enabled=False,
                                  processing=False, message='', kind='sale', target=None):
        """Observe historical journal evidence, never post a business transaction.

        The target header is access-checked by the caller. Only lifecycle fields
        are elevated. Owns a fresh locked external session, rolled back on exit;
        caller journals the boolean outcome and commits PostgreSQL.
        """
        header = target if target is not None else self
        header.ensure_one()
        header.check_access('read')
        if current_request(self) and request_store(self) != header.store_id:
            raise AccessError(_('The SQL store does not match the authorized API store.'))
        def conflict(reason):
            raise UserError(reason)
        connection = (header._get_submission_connection() if kind == 'sale'
                      else header._get_return_submission_connection())
        resource = 'ab_branch_api:' + hashlib.sha256(
            (self.env.cr.dbname + ':' + token).encode()).hexdigest()
        try:
            lock_cursor = connection.cursor()
            lock_cursor.execute("""DECLARE @result int;
                EXEC @result = sys.sp_getapplock @Resource=?, @LockMode='Exclusive',
                    @LockOwner='Session', @LockTimeout=0;
                SELECT @result;""", (resource,))
            row = lock_cursor.fetchone()
            if not row or int(row[0]) < 0:
                raise UserError(_('The branch is still processing this request. Retry shortly using the same bill.'))
            cur = connection.cursor()
            cur.execute('SET LOCK_TIMEOUT 5000')
            # READCOMMITTEDLOCK explicitly excludes dirty rows, including under RCSI.
            # The session application lock excludes still-running protected submissions.
            evidence = evidence or {}
            committed = False
            if kind == 'sale':
                marker = int(config.get('db_serial')) * 1_000_000_000 + header.id
                serial_hint = int(evidence.get('eplus_serial') or header.eplus_serial or 0)
                cur.execute('''SELECT h.sth_id, h.sth_flag, h.no_of_items,
                        (SELECT COUNT(*) FROM sales_trans_d d WITH (READCOMMITTEDLOCK)
                         WHERE d.sth_id=h.sth_id), h.temp_col6
                    FROM sales_trans_h h WITH (READCOMMITTEDLOCK)
                    WHERE (h.temp_col6=? OR (h.sth_id=? AND h.sth_id>0)) AND h.sto_id=?''',
                    (marker, serial_hint, int(header.store_id.eplus_serial)))
                rows = cur.fetchall()
                if rows:
                    if len(rows) != 1:
                        conflict(_('More than one invoice matches the stored request.'))
                    if int(rows[0][0] or 0) <= 0 or int(rows[0][4] or 0) != marker:
                        conflict(_('The invoice identifier or request marker does not match the stored bill.'))
                    if not rows[0][3] or int(rows[0][2] or 0) != int(rows[0][3]):
                        conflict(_('Invoice %(invoice)s has %(header)s declared lines but %(details)s stored detail rows.') % {
                            'invoice': rows[0][0], 'header': rows[0][2], 'details': rows[0][3]})
                    if evidence.get('eplus_serial') and evidence['eplus_serial'] != int(rows[0][0]):
                        conflict(_('The invoice does not match the transaction identifier recorded before commit.'))
                    serial, flag = rows[0][:2]
                    # Only the original operation's lifecycle/transaction fields are
                    # finalized here, just as in the existing posting workflow.
                    # Pending/Saved records remain read-only to ordinary ORM edits.
                    header.sudo()._write_submission_state({'active': True, 'pos_client_token': token,
                                  'eplus_serial': int(serial), 'status': 'saved' if flag == 'C' else 'pending',
                                  'push_state': 'success', 'push_message': _('Branch sale submitted.')})
                    committed = True
                elif header.eplus_serial and not recovery_enabled:
                    # Legacy local identifiers alone cannot prove an external rollback.
                    conflict(_('The legacy bill has an invoice identifier, but no matching branch invoice was found.'))
            else:
                # A return has no external request marker. New postings journal BOTH
                # generated identifiers before committing; legacy ambiguous returns stay blocked.
                if not recovery_enabled:
                    conflict(_('This older return has no commit journal to establish whether it was posted.'))
                if evidence:
                    cur.execute('''SELECT r.sr_id FROM sales_return r WITH (READCOMMITTEDLOCK)
                        JOIN sales_trans_h h WITH (READCOMMITTEDLOCK) ON h.sth_id=r.sth_id
                        WHERE r.sr_id=? AND r.sth_id=? AND h.sto_id=?''',
                        (evidence['sales_return_id'], int(header.origin_header_id), int(header.store_id.eplus_serial)))
                    returns = cur.fetchall()
                    cur.execute('''SELECT fh_id FROM F_Transaction_Header WITH (READCOMMITTEDLOCK)
                        WHERE fh_id=? AND fh_sto_id=? AND fh_trans_type=1 AND fh_trans_type2=2''',
                        (evidence['f_transaction_id'], int(header.store_id.eplus_serial)))
                    finance = cur.fetchall()
                    cur.execute('''SELECT srp_sr_id FROM sales_return_payment WITH (READCOMMITTEDLOCK)
                        WHERE srp_sr_id=? AND srp_sto_id=? AND srp_sr_type=2''',
                        (evidence['sales_return_id'], int(header.store_id.eplus_serial)))
                    payments = cur.fetchall()
                    if returns or finance or payments:
                        if len(returns) != 1 or len(finance) != 1 or len(payments) != 1:
                            conflict(_('The return, cash transaction and payment records do not form one complete transaction.'))
                        header.sudo()._write_return_state({'sales_return_id': evidence['sales_return_id'],
                                             'f_transaction_id': evidence['f_transaction_id'],
                                             'status': 'saved'})
                        committed = True
            if committed:
                return True
            if processing and not recovery_enabled:
                conflict(_('This older request is still marked as processing and has no recovery journal.'))
            values = {'status': 'prepending'}
            if kind == 'sale':
                values.update(active=True, pos_client_token=token, eplus_serial=False,
                              push_state='error', push_message=message or '')
            else:
                values.update(sales_return_id=False, f_transaction_id=False)
            # A failed commit may have left Pending/Saved in PostgreSQL. Restore
            # only lifecycle fields after proving external rollback; a later
            # submit still checks ordinary draft header/line write permission.
            if kind == 'sale':
                header.sudo()._write_submission_state(values)
            else:
                header.sudo()._write_return_state(values)
            return False
        finally:
            try:
                connection.rollback()
                connection.cursor().execute(
                    "EXEC sys.sp_releaseapplock @Resource=?, @LockOwner='Session'", (resource,))
            finally:
                connection.close()


class SalesBackendLineInventory(models.Model):
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
        rows = self.env['ab_sales_header']._backend_stock_lines(
            store, self.product_id.mapped('eplus_serial'), crx=crx)
        by_product = {}
        for row in rows:
            if row['qty'] >= 0.01:
                by_product.setdefault(row['product_eplus_serial'], []).append(row)
        for line in self:
            if line.product_id:
                line.inventory_json = {'data': [dict(row, store_id=store.id, product_id=line.product_id.id)
                    for row in by_product.get(line.product_id.eplus_serial, [])]}


