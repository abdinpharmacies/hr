"""Dedicated authenticated transport; no callcenter API or public ORM entrypoint."""
import hmac
import json
from psycopg2.errors import SerializationFailure, DeadlockDetected, UniqueViolation
from uuid import UUID

from odoo import api, fields, http, SUPERUSER_ID, _
from odoo.http import request
from odoo.modules.registry import Registry
from odoo.exceptions import AccessError, ValidationError, UserError, LockError
from ..models.operation import digest
from ..models.sales import REPLAY_ORIGIN


class CentralSync(http.Controller):
    @http.route('/ab_central_sync/v1/<string:action>', type='http', auth='none', methods=['POST'], csrf=False, save_session=False)
    def transport(self, action):
        for attempt in range(3):
            try:
                return self._dispatch(action)
            except (SerializationFailure, DeadlockDetected, UniqueViolation, LockError):
                if attempt == 2:
                    return request.make_json_response({'error': _('Retry transaction')}, status=503)

    def _dispatch(self, action):
        database = request.httprequest.headers.get('X-Odoo-Database', '')
        if action not in ('submit', 'status', 'reconcile') or not database or not http.db_filter([database]):
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
                peers = json.loads(Journal._param('peers', '{}'))
                peer = peers.get(origin, {})
                supplied = request.httprequest.headers.get('Authorization', '')
                key = peer.get('api_key', '')
                if not key or not hmac.compare_digest(supplied, 'Bearer ' + key):
                    raise AccessError('Invalid credentials')
                if type(payload.get('store')) is not int or payload['store'] not in peer.get('stores', []):
                    raise AccessError('Store forbidden')
                store = env['ab_store'].search(fields.Domain([('eplus_serial', '=', payload['store']), ('active', '=', True)]), limit=2)
                if len(store) != 1:
                    raise AccessError('Store unavailable')
                env['ab_inventory_process']._lock_stores([store.id])
                base = [('direction', '=', 'in'), ('origin', '=', origin), ('store_id', '=', store.id)]
                if action == 'reconcile':
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
                    if action == 'submit':
                        if not isinstance(payload.get('source_document'), str) or not payload['source_document']:
                            raise ValueError()
                        if payload.get('version') != 1 or type(payload.get('serial')) is not int or payload['serial'] <= 0:
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
                        previous = Journal.search_count(fields.Domain(base + [('serial', '<', operation.serial), ('state', '=', 'accepted')]))
                        ordered = previous == operation.serial - 1
                        if operation.state in ('queued', 'retryable') and not ordered:
                            operation.write({'state': 'retryable', 'error': _('Earlier process serials must be accepted first.')})
                        if operation.state in ('queued', 'retryable') and ordered:
                            mapping = peer.get('actors', {}).get(payload.get('actor'))
                            if not isinstance(mapping, dict):
                                raise AccessError('Explicit actor mapping required')
                            user = env['res.users'].search(fields.Domain([('login', '=', mapping.get('login')), ('active', '=', True)]), limit=1)
                            if not user or user.id == SUPERUSER_ID:
                                raise AccessError('Actor mapping required')
                            actor_env = api.Environment(cr, user.id, {})
                            replay_session = False
                            if 'ab_employee_access_sales_pos_session' in env.registry:
                                employee_ref = payload.get('actor_employee')
                                if not employee_ref or employee_ref not in mapping.get('employees', []):
                                    raise AccessError('Employee is not delegated to this origin and actor')
                                employee_id = Journal.with_env(actor_env)._resolve('ab_hr_employee', employee_ref)
                                profile = env['ab_employee_access'].search(fields.Domain([('employee_id', '=', employee_id), ('pos_allow_login', '=', True)]), limit=2)
                                if len(profile) != 1 or not profile._is_store_allowed_for_pos(store):
                                    raise AccessError('Employee profile does not permit this store')
                                profile.lock_for_update(allow_referencing=True)
                                actor_env['ab_employee_access_sales_pos_api']._check_service_user(store.with_env(actor_env))
                                # The configured origin credential and explicit employee delegation
                                # authenticate this integration session. Existing business methods
                                # still evaluate its central profile for every action.
                                replay_session = env['ab_employee_access_sales_pos_session'].create({
                                    'employee_id': employee_id, 'profile_id': profile.id,
                                    'role_id': profile.pos_role_id.id, 'service_user_id': user.id,
                                    'store_id': store.id, 'device_uid': 'central-sync:' + token,
                                    'device_name': _('Central Synchronization'),
                                })
                                actor_env = api.Environment(cr, user.id, {name: replay_session.session_token for name in ('native_pos_hr_token', 'ab_return_session_token', 'native_cashier_session_token')})
                            try:
                                with cr.savepoint():
                                    actor_env['ab_sales_backend']._check_store(store.id)
                                    origin_token = REPLAY_ORIGIN.set(dict(payload, replica_serial=peer.get('replica_serial')))
                                    try:
                                        result = operation._apply(actor_env['ab_sales_header'])
                                    finally:
                                        REPLAY_ORIGIN.reset(origin_token)
                                    operation.write({'state': 'accepted', 'result': result, 'error': False, 'accepted_at': fields.Datetime.now(),
                                                     'document_model': result['model'], 'document_id': result['id']})
                            except LockError:
                                raise
                            except (AccessError, ValidationError, UserError) as error:
                                operation.write({'state': 'rejected', 'error': str(error)})
                            finally:
                                if replay_session:
                                    replay_session.close_session()
                            operation.write({'attempts': operation.attempts + 1, 'history': ((operation.history or []) + [{'at': str(fields.Datetime.now()), 'state': operation.state}])[-50:]})
                    result = {'token': token, 'state': operation.state if operation else 'not_found',
                              'payload_hash': operation.payload_hash if operation else False,
                              'result': operation.result if operation else False,
                              'message': operation.error if operation else False}
                cr.commit()
            return request.make_json_response(result)
        except LockError:
            raise
        except (AccessError, ValidationError, UserError, ValueError, KeyError, TypeError):
            return request.make_json_response({'error': _('Invalid or unauthorized synchronization request')}, status=403)
