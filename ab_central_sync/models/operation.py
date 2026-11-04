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
    def _uses_central(self, store, role=None):
        current_role = self._param('role')
        if not store or current_role not in ('branch', 'central') or (role and current_role != role):
            return False
        if current_role == 'branch':
            replica = self.env['ab_replica_db'].get_current_from_config()
            return bool(replica and store in replica._sync_stores())
        replicas = self.env['ab_replica_db'].sudo().search(fields.Domain('central_ready', '=', True) & fields.Domain('central_key_hash', '!=', False))
        return any(store in replica._sync_stores() for replica in replicas)

    @api.model
    def _enqueue(self, document, kind, payload):
        if not self._uses_central(document.store_id, 'branch'):
            return
        if kind == 'sale' and not document.native_submitted:
            return
        self._check_enrolled_store(document.store_id)
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
        if kind != 'sale_cancel' and 'ab_employee_access_sales_pos_api' in self.env.registry:
            session_token = next((self.env.context.get(key) for key in ('native_pos_hr_token', 'ab_return_session_token', 'native_cashier_session_token') if self.env.context.get(key)), False)
            session = self.env['ab_employee_access_sales_pos_api']._get_session(session_token, states=['active'])
            from .sales import reference
            payload['actor_employee'] = reference(session.employee_id)
        payload.update(version=2, origin=origin, token=token, serial=serial, kind=kind,
                       store=store.code, actor=self.env.user.login,
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

    def _request(self, action, body, credential=None):
        url = str(self._param('url', '')).rstrip('/')
        key, database = credential or self._param('api_key'), self._param('database')
        if not url.startswith('https://') or not key or not database:
            raise ValidationError(_('Configure the central HTTPS URL, database, and API key.'))
        response = requests.post(url + '/ab_central_sync/v2/' + action,
            headers={'Authorization': 'Bearer ' + key, 'X-Odoo-Database': database},
            json=body, timeout=(5, 20), allow_redirects=False, verify=self._param('ca_bundle') or True)
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
        if values['state'] == 'accepted' and self.kind in ('sale', 'return', 'sale_cancel'):
            document = self.env[self.document_model].sudo().browse(self.document_id).exists()
            codes = document.line_ids.product_id.mapped('code') if document else []
            if codes:
                self._try_refresh_snapshots(store_ids=self.store_id.ids, product_codes=codes)

    @api.model
    def _cron_retry(self):
        if self._param('role') != 'branch':
            return
        self._try_refresh_snapshots()
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

    @api.model
    def _check_enrolled_store(self, store):
        codes = json.loads(self._param('stores', '[]'))
        origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        if not self._param('enrolled') or not self._param('ready') or self._param('origin') != origin or store.code not in codes:
            raise ValidationError(_('Connect this branch and download its stock snapshot before selling.'))

    @api.model
    def _check_enrollment_integrity(self, stores):
        if not stores:
            return
        domain = fields.Domain('store_id', 'in', stores.ids)
        if self.env['ab_sales_stock_allocation'].sudo().search_count(domain, limit=1):
            raise ValidationError(_('Reconcile existing local native stock movements before enabling central synchronization.'))
        sales = self.env['ab_sales_header'].sudo().with_context(active_test=False).search(
            domain & (fields.Domain('native_submitted', '=', True) | fields.Domain('native_posted', '=', True)))
        returns = self.env['ab_sales_return_header'].sudo().with_context(active_test=False).search(
            domain & fields.Domain('native_posted', '=', True))
        payments = self.env['ab_sales_native_payment'].sudo().search(domain)
        events = [('sale', sales), ('return', returns),
                  ('sale_settle', payments.filtered(lambda payment: not payment.return_id).sale_id),
                  ('return_settle', payments.return_id)]
        origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        for kind, documents in events:
            if not documents:
                continue
            operations = self.sudo().with_context(active_test=False).search(
                domain & fields.Domain('direction', '=', 'out') & fields.Domain('origin', '=', origin)
                & fields.Domain('kind', '=', kind) & fields.Domain('document_model', '=', documents._name)
                & fields.Domain('document_id', 'in', documents.ids))
            recorded = {(operation.document_id, operation.store_id.id) for operation in operations}
            if {(document.id, document.store_id.id) for document in documents} - recorded:
                raise ValidationError(_('Confirmed native transactions require reconciliation before enabling central synchronization.'))

    @api.model
    def _save_connection(self, info):
        if info.get('version') != 2 or info.get('origin') != self.env['ir.config_parameter'].sudo().get_param('database.uuid'):
            raise ValidationError(_('Invalid enrollment response.'))
        codes = info.get('stores', [])
        if (not isinstance(codes, list) or not codes or any(not isinstance(code, str) or not code for code in codes)
                or len(set(codes)) != len(codes) or type(info.get('replica_serial')) is not int
                or info['replica_serial'] <= 0):
            raise ValidationError(_('Invalid enrollment response.'))
        stores = self.env['ab_store'].sudo().search(fields.Domain('code', 'in', codes))
        if not codes or len(stores) != len(codes) or info.get('default_store') not in codes:
            raise ValidationError(_('Synchronize assigned stores before connecting.'))
        replica = self.env['ab_replica_db'].get_current_from_config()
        if not replica or replica.db_serial != info['replica_serial'] or set(replica._sync_stores().ids) != set(stores.ids):
            raise ValidationError(_('Replicate the branch identity and store assignments before connecting.'))
        previous_codes = json.loads(self._param('stores', '[]')) if self._param('enrolled') else []
        new_stores = stores.filtered(lambda store: store.code not in previous_codes)
        new_stores.lock_for_update(allow_referencing=True)
        self._check_enrollment_integrity(new_stores)
        params = self.env['ir.config_parameter'].sudo()
        if not self._param('enrolled') or new_stores:
            params.set_param('ab_central_sync.ready', False)
        params.set_param('ab_central_sync.stores', json.dumps(codes))
        params.set_param('ab_central_sync.origin', info['origin'])
        params.set_param('ab_central_sync.enrolled', True)

    @api.model
    def _refresh_snapshots(self, store_ids=None, product_codes=None):
        if self._param('role') != 'branch' or not self._param('enrolled'):
            return
        origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        codes = json.loads(self._param('stores', '[]'))
        stores = self.env['ab_store'].sudo().search(fields.Domain('code', 'in', codes))
        if store_ids is not None:
            stores = stores.filtered(lambda store: store.id in store_ids)
        for store in stores:
            after = 0
            while True:
                snapshot = self._request('snapshot', {'origin': origin, 'store': store.code, 'after': after, 'codes': product_codes})
                self.env['ab_sales_inventory'].sudo()._accept_central_snapshot(store, snapshot)
                next_after = snapshot.get('next')
                if next_after is None:
                    break
                if type(next_after) is not int or next_after <= after:
                    raise ValidationError(_('Invalid snapshot continuation.'))
                after = next_after
        if product_codes is None and store_ids is None:
            self.env['ir.config_parameter'].sudo().set_param('ab_central_sync.ready', True)

    @api.model
    def _try_refresh_snapshots(self, **kwargs):
        try:
            with self.env.cr.savepoint():
                self._refresh_snapshots(**kwargs)
        except (requests.RequestException, ValueError, ValidationError):
            self.env['ir.config_parameter'].sudo().set_param('ab_central_sync.connection_status', 'stock_error')

    @api.model
    def _sync_now(self):
        self._try_refresh_snapshots()
        operations = self.sudo().search(fields.Domain('direction', '=', 'out') & fields.Domain('state', 'in', ['queued', 'uncertain', 'retryable']), order='serial,id', limit=100)
        for operation in operations:
            operation._deliver()

    @api.model
    def _central_stock_snapshot(self, store, origin, after, codes=None):
        if not self.env.su or self._param('role') != 'central' or type(after) is not int or after < 0:
            raise AccessError(_('Invalid stock snapshot request.'))
        # Caller holds the same store lock as posting. Balance and accepted watermark
        # therefore describe a single ledger state, even if acknowledgment was lost.
        lock = self.env['ab_stock_integration_lock'].search(fields.Domain('store_id', '=', store.id), limit=1)
        operations = self.with_context(active_test=False).search(fields.Domain('direction', '=', 'in')
            & fields.Domain('origin', '=', origin) & fields.Domain('store_id', '=', store.id)
            & fields.Domain('state', '=', 'accepted'), order='serial desc', limit=1)
        stocked = self.env['ab_inventory']._read_group(
            fields.Domain('store_id', '=', store.id), ['product_id'], [])
        domain = fields.Domain('id', '>', after) & fields.Domain('id', 'in', [product.id for product, in stocked if product])
        if codes is not None:
            if not isinstance(codes, list) or len(codes) > 200 or any(not isinstance(code, str) for code in codes):
                raise ValidationError(_('Invalid product snapshot request.'))
            domain &= fields.Domain('code', 'in', codes)
        products = self.env['ab_product'].with_context(active_test=False).search(domain, order='id', limit=501)
        rows = []
        for product in products[:500]:
            batches = self.env['ab_sales_stock_allocation']._source_rows(store, product) if not product.is_service and product.active else []
            for batch in batches:
                batch['expiry'] = fields.Date.to_string(batch['expiry']) if batch['expiry'] else False
            rows.append({'code': product.code, 'balance': sum(row['qty'] for row in batches) / (float(product._stock_unit_factor(product.uom_id)) if batches else 1),
                         'default_price': product.default_price, 'batches': batches})
        return {'version': 2, 'origin': origin, 'store': store.code, 'revision': lock.revision,
                'watermark': operations.serial or 0, 'at': fields.Datetime.to_string(fields.Datetime.now()),
                'products': rows, 'next': products[499].id if len(products) > 500 else None}
