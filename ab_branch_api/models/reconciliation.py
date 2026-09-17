"""Branch-owned recovery across the PostgreSQL / SQL Server commit boundary.

No business SQL is replayed here. Committed, branch-scoped evidence decides
whether to return the original result or permit the existing posting workflow.
"""
from contextlib import contextmanager
import hashlib
import json
import logging

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import config

from .routing import api_request, current_request, request_store, STORE_UNSET
from .sales_workflow import ReturnConnection

_logger = logging.getLogger(__name__)


class PostingConnection:
    """Journal identifiers durably BEFORE the business connection may commit."""

    def __init__(self, connection, provider, operation):
        self.connection = connection
        self.provider = provider
        self.operation = operation
        # A session lock also survives a lost Odoo worker while SQL is running.
        # Closing the request's physical connection releases it, including on errors.
        self.resource = 'ab_branch_api:' + hashlib.sha256(
            (provider.env.cr.dbname + ':' + operation.token).encode()).hexdigest()
        cur = connection.cursor()
        cur.execute("""DECLARE @result int;
            EXEC @result = sys.sp_getapplock @Resource=?, @LockMode='Exclusive',
                @LockOwner='Session', @LockTimeout=0;
            SELECT @result;""", (self.resource,))
        row = cur.fetchone()
        if not row or int(row[0]) < 0:
            raise UserError(provider.env._('The branch is still processing this request. Retry shortly using the same bill.'))

    def release(self):
        # Roll back unfinished work before admitting another worker. Explicitly
        # release session locks even when the ODBC driver pools closed sessions.
        self.connection.rollback()
        self.connection.cursor().execute(
            "EXEC sys.sp_releaseapplock @Resource=?, @LockOwner='Session'", (self.resource,))

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def commit(self):
        scope = current_request(self.provider)
        if scope.posting_operation == self.operation and self.operation.kind == 'return':
            # The inherited return workflow also commits replication entries and
            # repricing after its stock/cash commit. Keep them in ONE transaction
            # for API requests, so recovery never skips a required later phase.
            raw = self.connection
            while isinstance(raw, ReturnConnection):
                raw = raw._connection
            scope.deferred_commits[id(raw)] = self
            return
        return self._commit_now()

    def _commit_now(self):
        scope = current_request(self.provider)
        if scope.posting_operation == self.operation:
            # Posting has already moved the bill to Pending/Saved, where normal
            # record rules forbid edits. Journaling only reads its identifiers.
            header = self.provider._operation_header(self.operation, access='read')
            if self.operation.kind == 'sale':
                evidence = {'eplus_serial': int(header.eplus_serial or 0)}
            else:
                evidence = {'sales_return_id': int(header.sales_return_id or 0),
                            'f_transaction_id': int(header.f_transaction_id or 0)}
            if not all(evidence.values()):
                raise UserError(self.provider.env._('The branch could not record the posting identifiers. Retry using the same bill.'))
            self.operation.write({'commit_evidence': evidence})
            self.provider.env.cr.commit()
        return self.connection.commit()


class BranchRecovery(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _lock_operation(self, token):
        scope = current_request(self)
        lock = int.from_bytes(hashlib.sha256(('ab_branch_api:' + token).encode()).digest()[:8],
                              'big', signed=True)
        if lock in scope.operation_locks:
            return
        # Unlike a row lock this protects the whole request across business commits.
        self.env.cr.execute('SELECT pg_try_advisory_lock(%s)', (lock,))
        if not self.env.cr.fetchone()[0]:
            raise UserError(_('The branch is still processing this request. Retry shortly using the same bill.'))
        scope.operation_locks.add(lock)
        self.env.cr.commit()  # Start a fresh repeatable-read snapshot after locking.
        self.env.invalidate_all()

    def _operation_header(self, operation, access='write'):
        model = 'ab_sales_header' if operation.kind == 'sale' else 'ab_sales_return_header'
        header = self.env[model].browse(operation.record_id).exists()
        if (not header or operation.user_id.id != self.env.uid
                or operation.store_id != request_store(self)
                or header.store_id != operation.store_id):
            raise AccessError(_('The stored bill does not match the authorized branch operation.'))
        header.check_access(access)
        header.line_ids.check_access(access)
        return header

    @contextmanager
    def _posting_scope(self, operation):
        scope = current_request(self)
        previous = scope.posting_operation
        scope.posting_operation = operation if operation.kind in ('sale', 'return') else None
        try:
            yield
            if scope.posting_operation and operation.kind == 'return':
                # All existing business methods have completed, including their
                # replication/repricing extensions. Only now cross the boundary.
                if len(scope.deferred_commits) != 1:
                    raise UserError(_('The branch could not record the posting identifiers. Retry using the same bill.'))
                for connection in scope.deferred_commits.values():
                    connection._commit_now()
        finally:
            scope.deferred_commits.clear()
            scope.posting_operation = previous

    def _guard_connection(self, connection, operation):
        scope = current_request(self)
        key = (id(connection), operation.id)
        if key not in scope.guarded:
            scope.guarded[key] = PostingConnection(connection, self, operation)
        return scope.guarded[key]

    def _prepare_post(self, operation, payload):
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if operation.payload_hash and operation.payload_hash != digest:
            raise UserError(_('The request token was already used with different data.'))
        if operation.state in ('processing', 'uncertain', 'retryable'):
            self._reconcile_post(operation)

    def _sale_result(self, header):
        return {**self._identity(header.store_id, int(config.get('db_serial'))),
                'remote_callcenter': True, 'branch_header_id': header.id,
                'remote_header_id': header.id, 'status': header.status,
                'eplus_serial': int(header.eplus_serial or 0), 'pos_header_id': False,
                'message': _('Branch sale submitted.')}

    def _reconcile_post(self, operation):
        header = self._operation_header(operation, access='read')
        connection = self._guard_connection(header.get_connection(), operation)
        cur = connection.cursor()
        cur.execute('SET LOCK_TIMEOUT 5000')
        # READCOMMITTEDLOCK explicitly excludes dirty rows, including under RCSI.
        # The session application lock excludes still-running protected submissions.
        evidence = operation.commit_evidence or {}
        committed = False
        if operation.kind == 'sale':
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
                    self._recovery_conflict(operation, _('More than one invoice matches the stored request.'))
                if int(rows[0][0] or 0) <= 0 or int(rows[0][4] or 0) != marker:
                    self._recovery_conflict(operation, _('The invoice identifier or request marker does not match the stored bill.'))
                if not rows[0][3] or int(rows[0][2] or 0) != int(rows[0][3]):
                    self._recovery_conflict(operation, _('Invoice %(invoice)s has %(header)s declared lines but %(details)s stored detail rows.') % {
                        'invoice': rows[0][0], 'header': rows[0][2], 'details': rows[0][3]})
                if evidence.get('eplus_serial') and evidence['eplus_serial'] != int(rows[0][0]):
                    self._recovery_conflict(operation, _('The invoice does not match the transaction identifier recorded before commit.'))
                serial, flag = rows[0][:2]
                # Only the original operation's lifecycle/transaction fields are
                # finalized here, just as in the existing posting workflow.
                # Pending/Saved records remain read-only to ordinary ORM edits.
                header.sudo().write({'active': True, 'pos_client_token': operation.token,
                              'eplus_serial': int(serial), 'status': 'saved' if flag == 'C' else 'pending',
                              'push_state': 'success', 'push_message': _('Branch sale submitted.')})
                committed = True
            elif header.eplus_serial and not operation.recovery_enabled:
                # Legacy local identifiers alone cannot prove an external rollback.
                self._recovery_conflict(operation, _('The legacy bill has an invoice identifier, but no matching branch invoice was found.'))
        else:
            # A return has no external request marker. New postings journal BOTH
            # generated identifiers before committing; legacy ambiguous returns stay blocked.
            if not operation.recovery_enabled:
                self._recovery_conflict(operation, _('This older return has no commit journal to establish whether it was posted.'))
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
                        self._recovery_conflict(operation, _('The return, cash transaction and payment records do not form one complete transaction.'))
                    header.sudo().write({'sales_return_id': evidence['sales_return_id'],
                                         'f_transaction_id': evidence['f_transaction_id'],
                                         'status': 'saved'})
                    committed = True
        if committed:
            result = (self._sale_result(header) if operation.kind == 'sale' else
                      self._return_snapshot(header, int(config.get('db_serial'))))
            operation.write({'state': 'done', 'result': result, 'message': '', 'reservation_key': False})
            _logger.info('Recovered branch API %s operation %s: external transaction %s',
                         operation.kind, operation.id, header.eplus_serial if operation.kind == 'sale' else header.sales_return_id)
        else:
            if operation.state == 'processing' and not operation.recovery_enabled:
                self._recovery_conflict(operation, _('This older request is still marked as processing and has no recovery journal.'))
            values = {'status': 'prepending'}
            if operation.kind == 'sale':
                values.update(active=True, pos_client_token=operation.token, eplus_serial=False,
                              push_state='error', push_message=operation.message or '')
            else:
                values.update(sales_return_id=False, f_transaction_id=False)
            # A failed commit may have left Pending/Saved in PostgreSQL. Restore
            # only lifecycle fields after proving external rollback; a later
            # submit still checks ordinary draft header/line write permission.
            header.sudo().write(values)
            operation.write({'state': 'retryable', 'result': False})
        self.env.cr.commit()

    def _recovery_conflict(self, operation, reason):
        _logger.warning('Branch API recovery blocked: operation=%s kind=%s store=%s reason=%s',
                        operation.id, operation.kind, operation.store_id.id, reason)
        raise UserError(_('Branch operation %(operation)s could not be reconciled: %(reason)s No bill was resubmitted.') % {
            'operation': operation.id, 'reason': reason})

    @api.model
    @api_request
    def reconcile_operation(self, db_serial, token, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        status = self.get_operation_status(db_serial, token, store_eplus_serial=store_eplus_serial)
        if status['state'] == 'not_found':
            return status
        operation = self.env['ab_branch_api_operation'].sudo().search([
            ('token', '=', token), ('user_id', '=', self.env.uid), ('store_id', '=', store.id)], limit=1)
        self._business_permissions(operation.kind, post=True)
        if operation.kind not in ('sale', 'return'):
            return status
        operation = self._operation(store, token, operation.kind)
        if operation.state in ('processing', 'uncertain'):
            self._reconcile_post(operation)
        return self.get_operation_status(db_serial, token, store_eplus_serial=store_eplus_serial)


class RecoverableSale(models.Model):
    _inherit = 'ab_sales_header'

    def get_connection(self):
        connection = super().get_connection()
        scope = current_request(self)
        if scope and scope.posting_operation:
            return self.env['ab_branch_api']._guard_connection(connection, scope.posting_operation)
        return connection


class RecoverableReturn(models.Model):
    _inherit = 'ab_sales_return_header'

    def get_connection(self):
        connection = super().get_connection()
        scope = current_request(self)
        if scope and scope.posting_operation:
            return self.env['ab_branch_api']._guard_connection(connection, scope.posting_operation)
        return connection
