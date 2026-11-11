"""A central URL/database and standard Odoo user API key are sufficient."""
import requests

from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Replica(models.Model):
    _inherit = 'ab_replica_db'

    def _sync_stores(self):
        self.ensure_one()
        return self.allowed_sales_store_ids


class CentralOperation(models.Model):
    _inherit = 'ab_branch_sync_operation'

    def action_connect_central(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage connections.'))
        params = self.env['ir.config_parameter'].sudo()
        notification_type = 'success'
        try:
            info = self._request('connection', {'origin': params.get_param('database.uuid')})
            self._save_connection(info)
            self._refresh_snapshots()
            params.set_param('ab_branch_sync.connection_status', 'connected')
            message = _('Connected. This installation reconnects automatically after restarts.')
        except ValidationError as error:
            params.set_param('ab_branch_sync.connection_status', 'attention')
            notification_type = 'warning'
            message = str(error)
        except (requests.RequestException, ValueError):
            params.set_param('ab_branch_sync.connection_status', 'attention')
            notification_type = 'warning'
            message = _('Connection failed. Check the central address, database, user API key and inventory access.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Branch Synchronization'), 'message': message,
            'type': notification_type, 'sticky': True}}

    def action_sync_now(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage connections.'))
        if not self._param('authorized'):
            raise ValidationError(_('Connect to central before synchronizing.'))
        notification_type = 'success'
        try:
            self._sync_now()
            self._refresh_snapshots()
            pending = self.sudo().search_count(
                fields.Domain('direction', '=', 'out') & fields.Domain('state', '!=', 'accepted'), limit=1)
            notification_type = 'warning' if pending else 'success'
            message = (_('Stock refreshed. Some outgoing operations still need attention.')
                       if pending else _('Central synchronization completed.'))
        except ValidationError as error:
            self.env['ir.config_parameter'].sudo().set_param('ab_branch_sync.connection_status', 'stock_error')
            notification_type = 'warning'
            message = str(error)
        except (requests.RequestException, ValueError):
            self.env['ir.config_parameter'].sudo().set_param('ab_branch_sync.connection_status', 'stock_error')
            notification_type = 'warning'
            message = _('Synchronization failed. Check the central connection and retry.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Branch Synchronization'), 'message': message,
            'type': notification_type, 'sticky': notification_type != 'success',
            'next': {'type': 'ir.actions.client', 'tag': 'reload'}}}
