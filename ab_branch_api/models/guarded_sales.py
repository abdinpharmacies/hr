"""Token/revision protocol for callcenter sales; posting belongs to ab_sales."""
import hashlib
import json
import logging

from odoo import models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config

from .routing import request_store

_logger = logging.getLogger(__name__)


class GuardedSales(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _guarded_sale_result(self, operation):
        header = self._operation_header(operation, access='read') if operation.record_id else False
        status = header.status if header else 'unknown'
        if operation.state == 'rejected' and status not in ('pending', 'saved'):
            status = 'rejected'
        elif operation.sale_prepared_revision != operation.request_revision and status not in ('pending', 'saved'):
            status = 'unknown'
        if status not in ('unknown', 'rejected', 'pending', 'saved'):
            status = 'unknown'
        message = '' if status in ('pending', 'saved') else operation.message or (header.push_message if header else '') or ''
        return {**self._identity(request_store(self), int(config.get('db_serial'))),
                'remote_callcenter': True, 'submission_guard_version': 1,
                'token': operation.token, 'request_revision': operation.request_revision,
                'branch_header_id': header.id if header else 0,
                'remote_header_id': header.id if header else 0,
                'eplus_serial': int(header.eplus_serial or 0) if header else 0,
                'status': status, 'message': message,
                'can_edit': status == 'rejected', 'can_retry': status in ('unknown', 'rejected')}

    def _finish_guarded_sale(self, operation, message=''):
        operation.invalidate_recordset()
        result = self._guarded_sale_result(operation)
        if message and result['status'] not in ('pending', 'saved'):
            result['message'] = message
        state = {'pending': 'done', 'saved': 'done', 'rejected': 'rejected'}.get(result['status'], 'uncertain')
        operation.write({'state': state, 'result': result, 'message': result['message']})
        self.env.cr.commit()
        _logger.info('Branch sale operation %s revision %s: %s, invoice %s',
                     operation.id, operation.request_revision, result['status'], result['eplus_serial'])
        return result

    def _submit_guarded_sale(self, db_serial, token, payload, revision, push):
        store = request_store(self)
        self._business_permissions('sale', post=True)
        if push is not True:
            raise UserError(_('Callcenter sale transport selection is no longer supported. Upgrade the callcenter module.'))
        if type(revision) is not int or revision < 1:
            raise UserError(_('A positive request revision is required.'))
        if not isinstance(payload, dict) or not isinstance(payload.get('header'), dict) or not isinstance(payload.get('lines'), list):
            raise UserError(_('Invalid sale payload.'))
        digest = hashlib.sha256(json.dumps({'payload': payload, 'push': True}, sort_keys=True, allow_nan=False).encode()).hexdigest()
        operation = self._operation(store, token, 'sale')
        header = self._operation_header(operation, access='read') if operation.record_id else False
        changed = bool(operation.payload_hash and operation.payload_hash != digest)
        if operation.payload_hash:
            if revision == operation.request_revision:
                if changed:
                    raise UserError(_('The request token was already used with different data.'))
            elif (revision != operation.request_revision + 1 or not changed
                  or operation.state != 'rejected' or (header and header.status != 'rejected')):
                raise UserError(_('Only a confirmed rejected bill can accept the next corrected revision.'))
        elif revision != 1:
            raise UserError(_('The first request revision must be one.'))
        if header and header.status in ('pending', 'saved'):
            if changed:
                raise UserError(_('The request token was already used with different data.'))
            operation.write({'sale_guard_version': 1})
            return self._finish_guarded_sale(operation)
        history = list(operation.attempt_history or [])
        if changed:
            history.append({'revision': operation.request_revision, 'payload_hash': operation.payload_hash,
                            'state': operation.state, 'message': operation.message or ''})
        # Legacy requests already built their unchanged header. New requests must
        # remember whether this revision completed preparation: a failed correction
        # must never silently post the previous revision's lines on the next retry.
        if header and not operation.sale_guard_version and not changed:
            operation.write({'sale_prepared_revision': revision})
        prepare = not header or changed or operation.sale_prepared_revision != revision
        operation.write({'sale_guard_version': 1, 'request_revision': revision,
                         'request_payload': payload, 'payload_hash': digest,
                         'state': 'processing', 'message': '', 'attempt_history': history})
        self.env.cr.commit()
        try:
            if prepare:
                # Preparation performs only Odoo changes and branch reads. Roll back
                # incomplete corrections without losing the original rejected header.
                with self.env.cr.savepoint():
                    header = self._prepare_sale_header(operation, payload, header=header)
                    operation.sale_prepared_revision = revision
                self.env.cr.commit()
        except (UserError, ValidationError) as error:
            self.env.cr.rollback()
            self.env.invalidate_all()
            operation.write({'state': 'rejected', 'message': str(error)})
            if operation.record_id:
                self._operation_header(operation, access='read').sudo()._write_submission_state({'status': 'rejected'})
            return self._finish_guarded_sale(operation, str(error))
        except Exception:
            self.env.cr.rollback()
            self.env.invalidate_all()
            return self._finish_guarded_sale(operation, _('Branch submission could not be confirmed. Retry the original bill.'))
        try:
            # No old PostingConnection wrapper: ab_sales owns its dedicated
            # connection, durable Unknown state and branch-scoped SQL recovery.
            with self._posting_scope(operation):
                header.action_submit()
        except (UserError, ValidationError) as error:
            self.env.cr.rollback()
            self.env.invalidate_all()
            header = self._operation_header(operation, access='read')
            if header.status in ('prepending', 'rejected'):
                header.sudo()._write_submission_state({'status': 'rejected', 'push_state': 'error', 'push_message': str(error)})
            return self._finish_guarded_sale(operation, str(error))
        except Exception:
            self.env.cr.rollback()
            self.env.invalidate_all()
            header = self._operation_header(operation, access='read')
            if header.status not in ('pending', 'saved'):
                header.sudo()._write_submission_state({'status': 'unknown'})
            return self._finish_guarded_sale(operation, _('Branch submission could not be confirmed. Retry the original bill.'))
        return self._finish_guarded_sale(operation)

    def _reconcile_guarded_sale(self, operation):
        """Observation may recover a committed invoice, but never post a new one."""
        if not operation.record_id:
            return self._finish_guarded_sale(operation)
        header = self._operation_header(operation, access='read')
        if header.status != 'unknown':
            return self._finish_guarded_sale(operation)
        try:
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
        except Exception:
            self.env.cr.rollback()
            self.env.invalidate_all()
            return self._finish_guarded_sale(operation, _('Branch submission could not be confirmed. Retry the original bill.'))
        return self._finish_guarded_sale(operation)
