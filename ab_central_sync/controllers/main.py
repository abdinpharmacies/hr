"""Dedicated authenticated transport; no callcenter API or public ORM entrypoint."""
from psycopg2.errors import SerializationFailure, DeadlockDetected, UniqueViolation
from uuid import UUID

from odoo import api, fields, http, SUPERUSER_ID, _
from odoo.http import request
from odoo.modules.registry import Registry
from odoo.exceptions import AccessError, ValidationError, UserError, LockError
from ..models.operation import digest
from ..models.sales import REPLAY_ORIGIN


class CentralSync(http.Controller):
    @http.route('/ab_central_sync/v3/<string:action>', type='http', auth='none', methods=['POST'], csrf=False, save_session=False)
    def transport(self, action):
        for attempt in range(3):
            try:
                return self._dispatch(action)
            except (SerializationFailure, DeadlockDetected, UniqueViolation, LockError):
                if attempt == 2:
                    return request.make_json_response({'error': _('Retry transaction')}, status=503)

    def _dispatch(self, action):
        database = request.httprequest.headers.get('X-Odoo-Database', '')
        if action not in ('submit', 'retry', 'status', 'reconcile', 'connection', 'snapshot') or not database or not http.db_filter([database]):
            return request.make_json_response({'error': _('Unavailable endpoint')}, status=404)
        if request.httprequest.content_length is None or request.httprequest.content_length > 2_000_000:
            return request.make_json_response({'error': _('Invalid request size')}, status=413)
        try:
            payload = request.httprequest.get_json()
            if not isinstance(payload, dict):
                raise ValueError()
            origin = str(UUID(payload['origin']))
            with Registry(database).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                Journal = env['ab_central_sync_operation'].with_context(active_test=False)
                if Journal._param('role') != 'central':
                    raise AccessError('Disabled')
                supplied = request.httprequest.headers.get('Authorization', '')
                user = env['ab_replica_db']._authenticate_inventory_key(supplied)
                serial = int(request.httprequest.headers.get('X-Branch-Replica', '0'))
                replica, allowed_stores, info = env['ab_replica_db']._inventory_connection(user, serial, origin)
                replica.write({'central_last_seen': fields.Datetime.now()})
                if action == 'connection':
                    cr.commit()
                    return request.make_json_response(info)
                if not isinstance(payload.get('store'), str):
                    raise AccessError('Store forbidden')
                store = allowed_stores.filtered(lambda store: store.code == payload['store'])
                if len(store) != 1:
                    raise AccessError('Store unavailable')
                env['ab_inventory_process']._lock_stores([store.id])
                base = [('direction', '=', 'in'), ('origin', '=', origin), ('store_id', '=', store.id)]
                if action == 'snapshot':
                    result = Journal._central_stock_snapshot(store, origin, payload.get('after', 0), payload.get('codes'))
                elif action == 'reconcile':
                    after = payload.get('after', 0)
                    high = payload.get('high_water', 0)
                    if type(after) is not int or type(high) is not int or not 0 <= after <= high:
                        raise ValueError()
                    end = min(high, after + 1000)
                    rows = Journal.search(fields.Domain(base + [('serial', '>', after), ('serial', '<=', end)]))
                    seen = set(rows.mapped('serial'))
                    result = {'through': end, 'missing': [n for n in range(after + 1, end + 1) if n not in seen],
                              'failed': rows.filtered(lambda op: op.state != 'accepted').mapped('serial')}
                else:
                    token = str(UUID(payload['token']))
                    operation = Journal.search(fields.Domain(base + [('token', '=', token)]), limit=1)
                    if action in ('submit', 'retry'):
                        if not isinstance(payload.get('source_document'), str) or not payload['source_document']:
                            raise ValueError()
                        if payload.get('version') != 3 or type(payload.get('serial')) is not int or payload['serial'] <= 0:
                            raise ValueError()
                        fingerprint = digest(payload)
                        if operation and operation.payload_hash != fingerprint:
                            raise ValidationError('Operation identity has different content')
                        if not operation:
                            if Journal.search_count(fields.Domain(base + ['|', ('serial', '=', payload['serial']), '&', ('kind', '=', payload['kind']), ('source_document', '=', payload['source_document'])]), limit=1):
                                raise ValidationError('Serial or business event already belongs to another operation')
                            operation = Journal.create({'origin': origin, 'token': token, 'store_id': store.id,
                                'serial': payload['serial'], 'kind': payload['kind'], 'direction': 'in',
                                'payload': payload, 'payload_hash': fingerprint})
                        if action == 'retry' and operation.state == 'rejected':
                            if payload.get('version') != 3:
                                raise ValidationError(_('Legacy operations require reconciliation before retry.'))
                            operation.write({'state': 'retryable', 'error': False})
                        ordered = payload.get('version') == 3 or Journal.search_count(fields.Domain(base + [('serial', '<', operation.serial), ('state', '=', 'accepted')])) == operation.serial - 1
                        if operation.state in ('queued', 'retryable') and not ordered:
                            operation.write({'state': 'retryable', 'error': _('Earlier process serials must be accepted first.')})
                        if operation.state in ('queued', 'retryable') and ordered:
                            try:
                                with cr.savepoint():
                                    result = self._apply_as_inventory_writer(env, operation, user, replica, payload, store, token)
                                    operation.write({'state': 'accepted', 'result': result, 'error': False, 'accepted_at': fields.Datetime.now(),
                                                     'document_model': result['model'], 'document_id': result['id']})
                            except LockError:
                                raise
                            except (AccessError, ValidationError, UserError) as error:
                                operation.write({'state': 'retryable' if operation._dependency_pending() else 'rejected', 'error': str(error)})
                            operation.write({'attempts': operation.attempts + 1, 'history': ((operation.history or []) + [{'at': str(fields.Datetime.now()), 'state': operation.state, 'inventory_writer_id': user.id}])[-50:]})
                    result = {'token': token, 'state': operation.state if operation else 'not_found',
                              'payload_hash': operation.payload_hash if operation else False,
                              'result': operation.result if operation else False,
                              'message': operation.error if operation else False}
                failed = Journal.search(fields.Domain(base + [('state', '!=', 'accepted')]), order='serial', limit=1)
                replica.write({'central_backlog': Journal.search_count(fields.Domain(base + [('state', '!=', 'accepted')])),
                               'central_error': failed.error if failed else False})
                cr.commit()
            return request.make_json_response(result)
        except LockError:
            raise
        except (AccessError, ValidationError, UserError, ValueError, KeyError, TypeError):
            return request.make_json_response({'error': _('Invalid or unauthorized synchronization request')}, status=403)

    @http.route(['/ab_central_sync/v1/<string:action>', '/ab_central_sync/v2/<string:action>'], type='http', auth='none', methods=['POST'], csrf=False, save_session=False)
    def obsolete(self, action):
        return request.make_json_response({'error': _('Upgrade this branch to inventory protocol 3.')}, status=426)

    def _apply_as_inventory_writer(self, env, operation, user, replica, payload, store, token):
        if store not in user._central_inventory_stores():
            raise AccessError(_('The API user has no inventory access to this branch.'))
        actor_env = api.Environment(env.cr, user.id, {'allowed_company_ids': user.company_ids.ids})
        # This server-only ContextVar cannot be supplied through an ORM RPC context.
        origin_token = REPLAY_ORIGIN.set(dict(payload, replica_serial=replica.db_serial,
            inventory_writer_id=user.id, inventory_store_id=store.id))
        replay_session = False
        try:
            if payload['kind'] != 'sale_cancel' and 'ab_employee_access_sales_pos_session' in env.registry:
                employee_ref = payload.get('actor_employee') or payload.get('header', {}).get('employee_id')
                employee_id = operation.with_env(actor_env)._resolve('ab_hr_employee', employee_ref)
                profile = env['ab_employee_access'].search(fields.Domain('employee_id', '=', employee_id), limit=2)
                if not employee_id or len(profile) != 1:
                    raise ValidationError(_('Replicate the bill employee and profile before synchronization.'))
                # Preserve the branch employee on the mirrored bill. API-user scope,
                # not the employee PIN/profile permissions, authorizes this transport.
                replay_session = env['ab_employee_access_sales_pos_session'].create({
                    'employee_id': employee_id, 'profile_id': profile.id,
                    'role_id': profile.pos_role_id.id, 'service_user_id': user.id,
                    'store_id': store.id, 'device_uid': 'central-api:' + token,
                    'device_name': _('Central Synchronization'),
                })
                actor_env = api.Environment(env.cr, user.id, dict(actor_env.context,
                    **{name: replay_session.session_token for name in ('native_pos_hr_token',
                        'ab_return_session_token', 'native_cashier_session_token')}))
            actor_env['ab_sales_backend']._check_store(store.id)
            return operation._apply(actor_env['ab_sales_header'])
        finally:
            if replay_session:
                replay_session.close_session()
            REPLAY_ORIGIN.reset(origin_token)
