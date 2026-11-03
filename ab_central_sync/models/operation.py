"""Durable transport journal. Business effects stay in the existing sales models."""
import hashlib
import json
import logging
import uuid
from datetime import timedelta

import requests
from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


class CentralOperation(models.Model):
    _name = 'ab_central_sync_operation'
    _description = 'Central Synchronization Operation'
    _order = 'id desc'
    _rec_name = 'token'

    active = fields.Boolean(default=True)
    token = fields.Char(required=True, readonly=True, index=True)
    origin = fields.Char(required=True, readonly=True, index=True)
    direction = fields.Selection([('out', 'Outgoing'), ('in', 'Incoming')], required=True, readonly=True)
    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict')
    serial = fields.Integer(required=True, readonly=True)
    kind = fields.Selection([(x, x.replace('_', ' ').title()) for x in
                             ('sale', 'sale_settle', 'return', 'return_settle', 'sale_cancel')], required=True, readonly=True)
    state = fields.Selection([(x, x.title()) for x in
                              ('queued', 'processing', 'accepted', 'retryable', 'uncertain', 'rejected')], default='queued', readonly=True)
    payload = fields.Json(required=True, readonly=True)
    payload_hash = fields.Char(required=True, readonly=True)
    result = fields.Json(readonly=True)
    accepted_at = fields.Datetime(readonly=True)
    attempts = fields.Integer(readonly=True)
    next_retry = fields.Datetime(readonly=True)
    error = fields.Text(readonly=True)
    history = fields.Json(readonly=True)
    reconciliation = fields.Json(readonly=True)
    source_document = fields.Char(readonly=True, index=True)
    document_model = fields.Char(readonly=True)
    document_id = fields.Integer(readonly=True)
    _business_event = models.Constraint('UNIQUE(direction, origin, store_id, kind, source_document)', 'This business event already has a synchronization operation.')
    _identity = models.Constraint('UNIQUE(direction, origin, token)', 'Operation identity already exists.')
    _serial = models.Constraint('UNIQUE(direction, origin, store_id, serial)', 'Process serial already exists.')

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('The synchronization service maintains the journal.'))
        vals_list = [dict(vals, source_document=vals.get('payload', {}).get('source_document')) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.su or {'token', 'origin', 'direction', 'store_id', 'serial', 'kind', 'payload', 'payload_hash', 'source_document'} & vals.keys():
            raise AccessError(_('Operation payloads and identities are immutable.'))
        return super().write(vals)

    def action_archive(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        if any(operation.state != 'accepted' for operation in self):
            raise ValidationError(_('Only accepted operations can be archived.'))
        return super(CentralOperation, self.sudo()).action_archive()

    def action_unarchive(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        return super(CentralOperation, self.sudo()).action_unarchive()

    def unlink(self):
        raise AccessError(_('Archive synchronization operations instead of deleting them.'))

    @api.model
    def _param(self, key, default=False):
        return self.env['ir.config_parameter'].sudo().get_param('ab_central_sync.' + key, default)

    @api.model
    def _enqueue(self, document, kind, payload):
        if self._param('role') != 'branch':
            return
        document.check_access('read')
        store = document.store_id
        store.lock_for_update(allow_referencing=True)
        previous = self.sudo().with_context(active_test=False).search(fields.Domain([('direction', '=', 'out'), ('document_model', '=', document._name), ('document_id', '=', document.id), ('kind', '=', kind)]), limit=1)
        if previous:
            return previous
        origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        code = 'ab_central_sync.%s.%s' % (origin, store.id)
        Sequence = self.env['ir.sequence'].sudo()
        sequence = Sequence.search(fields.Domain([('code', '=', code)]), limit=1)
        if not sequence:
            sequence = Sequence.create({'name': code, 'code': code, 'implementation': 'no_gap', 'company_id': False})
        serial = int(sequence.next_by_id())
        token = str(uuid.uuid4())
        if 'ab_employee_access_sales_pos_api' in self.env.registry:
            token = next((self.env.context.get(key) for key in ('native_pos_hr_token', 'ab_return_session_token', 'native_cashier_session_token') if self.env.context.get(key)), False)
            session = self.env['ab_employee_access_sales_pos_api']._get_session(token, states=['active'])
            from .sales import reference
            payload['actor_employee'] = reference(session.employee_id)
        payload.update(version=1, origin=origin, token=token, serial=serial, kind=kind,
                       store=store.eplus_serial, actor=self.env.user.login,
                       occurred_at=fields.Datetime.to_string(fields.Datetime.now()))
        operation = self.sudo().create(dict(token=token, origin=origin, serial=serial, kind=kind,
            store_id=store.id, direction='out', payload=payload, payload_hash=digest(payload),
            document_model=document._name, document_id=document.id))
        registry, operation_id = self.env.registry, operation.id
        def deliver():
            try:
                with registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env[self._name].browse(operation_id)._deliver()
                    cr.commit()
            except Exception:
                # The original transaction is already durable. Never log payloads or secrets.
                _logger.warning('Central delivery deferred for operation %s', operation_id)
        self.env.cr.postcommit.add(deliver)
        return operation

    def _request(self, action, body):
        url = str(self._param('url', '')).rstrip('/')
        key, database = self._param('api_key'), self._param('database')
        if not url.startswith('https://') or not key or not database:
            raise ValidationError(_('Configure the central HTTPS URL, database, and API key.'))
        response = requests.post(url + '/ab_central_sync/v1/' + action,
            headers={'Authorization': 'Bearer ' + key, 'X-Odoo-Database': database},
            json=body, timeout=(5, 20), allow_redirects=False)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or result.get('error'):
            raise ValidationError(_('Central rejected the synchronization request.'))
        return result

    def _deliver(self):
        self.ensure_one()
        if self._param('role') != 'branch' or self.direction != 'out' or self.state in ('accepted', 'rejected'):
            return
        if not self.try_lock_for_update(allow_referencing=True):
            return
        self.invalidate_recordset()
        if self.state in ('accepted', 'rejected'):
            return
        now = fields.Datetime.now()
        try:
            query = {k: self.payload[k] for k in ('origin', 'token', 'store')}
            query['payload_hash'] = self.payload_hash
            result = self._request('status', query)
            if result.get('state') == 'not_found' or result.get('state') == 'retryable':
                result = self._request('submit', self.payload)
            if result.get('payload_hash') != self.payload_hash or result.get('token') != self.token or result.get('state') not in ('accepted', 'rejected', 'retryable'):
                raise ValidationError(_('Invalid central acknowledgment.'))
            values = {'state': result['state'], 'result': result, 'error': result.get('message', False)}
        except (requests.RequestException, ValueError, ValidationError):
            values = {'state': 'uncertain', 'error': _('Delivery could not be confirmed; status will be checked before replay.')}
        if values['state'] == 'accepted':
            values['accepted_at'] = now
        values.update(attempts=self.attempts + 1, next_retry=now + timedelta(minutes=15),
                      history=((self.history or []) + [{'at': str(now), 'state': values['state']}])[-50:])
        self.sudo().write(values)

    @api.model
    def _cron_retry(self):
        if self._param('role') != 'branch':
            return
        operations = self.sudo().search(fields.Domain([('direction', '=', 'out'), ('state', 'in', ['queued', 'uncertain', 'retryable']),
            '|', ('next_retry', '=', False), ('next_retry', '<=', fields.Datetime.now())]), order='serial,id', limit=20)
        for operation in operations:
            operation._deliver()
            self.env['ir.cron']._commit_progress(1)

    def action_reconcile(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        for operation in self.filtered(lambda op: op.direction == 'out'):
            latest = self.sudo().search(fields.Domain([('origin', '=', operation.origin), ('store_id', '=', operation.store_id.id), ('direction', '=', 'out')]), order='serial desc', limit=1)
            report = operation._request('reconcile', {'origin': operation.origin, 'store': operation.payload['store'], 'high_water': latest.serial, 'after': max(0, operation.serial - 1)})
            operation.sudo().write({'reconciliation': report})
        return True

    def action_retry(self):
        if not self.env.user.has_group('ab_central_sync.group_manager'):
            raise AccessError(_('Synchronization manager access is required.'))
        self.check_access('write')
        for operation in self:
            if operation.state != 'accepted':
                operation.sudo().write({'state': 'retryable', 'next_retry': False, 'error': False})
        return True
