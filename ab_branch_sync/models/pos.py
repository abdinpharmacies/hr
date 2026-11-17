"""Store-scoped synchronization for the branch POS status tag."""
import json

import requests

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BranchSyncPOS(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_central_prepare(self, store_id):
        """Prepare the selected branch with saved credentials, before PIN login."""
        store = self.env['ab_sales_backend']._check_branch_store_access(store_id)
        if 'ab_employee_access_sales_pos_api' in self.env.registry:
            self.env['ab_employee_access_sales_pos_api']._check_service_user(store)
        return self._prepare_central_store(store)

    @api.model
    def _prepare_central_store(self, store):
        journal = self.env['ab_branch_sync_operation'].sudo()
        if not all(journal._param(key) for key in ('url', 'database', 'api_key')):
            return {'state': 'not_configured', 'ready': False, 'synced': False,
                    'message': _('Configure a central HTTP or HTTPS URL, database, and API key.')}
        try:
            journal._check_enrolled_store(store)
            return {'state': 'online', 'ready': True, 'synced': False,
                    'message': _('Connected to central.')}
        except ValidationError:
            pass
        try:
            # Failed setup must not leave a partially authorized/ready branch.
            with self.env.cr.savepoint():
                replica = self.env['ab_replica_db'].get_current_from_config()
                replica.lock_for_update(allow_referencing=True)
                origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
                info = journal._request('connection', {'origin': origin})
                if (info.get('inventory_protocol') != 3
                        or info.get('replica_serial') != replica.db_serial
                        or store.code not in info.get('stores', [])):
                    raise ValidationError(_('Central connection details do not match this branch.'))
                journal._save_connection(info)
                # Readiness is installation-wide: initialize the complete
                # authenticated scope, not just the selected store.
                journal._refresh_snapshots()
                journal._check_enrolled_store(store)
            return {'state': 'online', 'ready': True, 'synced': True,
                    'message': _('Central stock synchronized.')}
        except requests.HTTPError as error:
            state = 'attention' if error.response is not None and error.response.status_code < 500 else 'offline'
            return {'state': state, 'ready': False, 'synced': False,
                    'message': _('Central rejected the connection. Check branch synchronization settings.')
                    if state == 'attention' else _('Central is unreachable. The last stock snapshot is retained.')}
        except requests.RequestException:
            return {'state': 'offline', 'ready': False, 'synced': False,
                    'message': _('Central is unreachable. The last stock snapshot is retained.')}
        except (ValidationError, ValueError, TypeError) as error:
            return {'state': 'attention', 'ready': False, 'synced': False,
                    'message': str(error) if isinstance(error, ValidationError)
                    else _('Central synchronization is incomplete. The previous stock snapshot is retained.')}

    @api.model
    def pos_central_sync(self, store_id, session_token=False, synchronize=False):
        try:
            interval = int(self.env['ir.config_parameter'].sudo().get_param('ab_central_branch_connection.pos_sync_interval_seconds', '10'))
            if not 1 <= interval <= 86400:
                interval = 10
        except (ValueError, TypeError):
            interval = 10
        result = self._pos_central_sync(store_id, session_token, synchronize)
        result['interval_seconds'] = interval
        return result

    @api.model
    def _pos_central_sync(self, store_id, session_token=False, synchronize=False):
        backend = self.env['ab_sales_backend']
        store = backend._check_branch_store_access(store_id)
        backend._check_employee_session(store, 'allow_pos_screen', token=session_token)
        preparation = self._prepare_central_store(store)
        if not preparation['ready'] or preparation['synced']:
            return preparation
        journal = self.env['ab_branch_sync_operation']
        origin = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        # Check the current replica and authorized scope before privileged queue/cache access.
        if (not journal._uses_central(store) or not journal._param('authorized')
                or journal._param('origin') != origin
                or store.code not in json.loads(journal._param('stores', '[]'))):
            return {'state': 'not_configured', 'synced': False,
                    'message': _('This branch is not connected to central.')}
        journal = journal.sudo()
        domain = (fields.Domain('direction', '=', 'out')
                  & fields.Domain('origin', '=', origin)
                  & fields.Domain('store_id', '=', store.id))
        result = {'state': 'online', 'synced': False,
                  'message': _('Connected to central.')}
        try:
            info = journal._request('connection', {'origin': origin})
            replica = self.env['ab_replica_db'].get_current_from_config()
            if (info.get('inventory_protocol') != 3 or info.get('origin') != origin
                    or info.get('replica_serial') != replica.db_serial
                    or store.code not in info.get('stores', [])):
                raise ValidationError(_('Central connection details do not match this branch.'))
            if synchronize:
                # Bound POS work; the existing retry cron handles the rest.
                operations = journal.search(domain & fields.Domain('state', 'in',
                    ['queued', 'uncertain', 'retryable']), order='serial,id')
                for operation in operations.filtered(lambda op: op.payload.get('version') == 3)[:10]:
                    operation._deliver()
                    if operation.state == 'uncertain':
                        return {'state': 'attention', 'synced': False,
                                'message': _('Central delivery is unconfirmed. Cached stock is retained.')}
                journal._refresh_snapshots(store_ids=store.ids)
                result.update(synced=True, message=_('Central stock synchronized.'))
        except requests.HTTPError as error:
            if error.response is not None and error.response.status_code < 500:
                return {'state': 'attention', 'synced': False,
                        'message': _('Central rejected the connection. Check branch synchronization settings.')}
            return {'state': 'offline', 'synced': False,
                    'message': _('Central is unreachable. The last stock snapshot is retained.')}
        except requests.RequestException:
            return {'state': 'offline', 'synced': False,
                    'message': _('Central is unreachable. The last stock snapshot is retained.')}
        except (ValidationError, ValueError, TypeError):
            return {'state': 'attention', 'synced': False,
                    'message': _('Central synchronization is incomplete. The previous stock snapshot is retained.')}
        if journal.search_count(domain & fields.Domain('state', '=', 'rejected'), limit=1):
            result['message'] = _('Connected to central. Some inventory operations need review.')
        elif journal.search_count(domain & fields.Domain('state', 'in',
                ['queued', 'uncertain', 'retryable']), limit=1):
            result['message'] = _('Connected to central. Inventory updates are still pending.')
        return result
