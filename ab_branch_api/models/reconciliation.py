"""Transport journal recovery; backend observations belong to ab_sales."""
import hashlib
import json
import logging
from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import config
from .routing import api_request, current_request, request_store, STORE_UNSET
_logger = logging.getLogger(__name__)

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
                or header.store_id != operation.store_id
                or (operation.kind == 'sale' and header.pos_client_token != operation.token)):
            raise AccessError(_('The stored bill does not match the authorized branch operation.'))
        header.check_access(access)
        header.line_ids.check_access(access)
        return header

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
        if operation.kind == 'sale' and operation.sale_guard_version == 1:
            return self._reconcile_guarded_sale(operation)
        header = self._operation_header(operation, access='read')
        try:
            if operation.kind == 'return' and header.return_client_token:
                committed = header._backend_reconcile(operation.commit_evidence)
            else:
                committed = header._backend_legacy_reconcile(
                    operation.token, evidence=operation.commit_evidence,
                    recovery_enabled=operation.recovery_enabled,
                    processing=operation.state == 'processing', message=operation.message)
        except UserError as error:
            self._recovery_conflict(operation, str(error))
        if committed:
            result = (self._sale_result(header) if operation.kind == 'sale' else
                      self._return_snapshot(header, int(config.get('db_serial'))))
            operation.write({'state': 'done', 'result': result, 'message': '', 'reservation_key': False})
        else:
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
