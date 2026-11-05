"""A central URL/database and standard Odoo user API key are sufficient."""
import requests

from odoo import fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Replica(models.Model):
    _inherit = 'ab_replica_db'

    def _sync_stores(self):
        self.ensure_one()
        return self.allowed_sales_store_ids


class Settings(models.TransientModel):
    _inherit = 'res.config.settings'

    central_url = fields.Char(string='Central URL', config_parameter='ab_branch_sync.url', groups='base.group_system')
    central_database = fields.Char(string='Central Database', config_parameter='ab_branch_sync.database', groups='base.group_system')
    central_api_key = fields.Char(string='Inventory Writer API Key', config_parameter='ab_branch_sync.api_key', groups='base.group_system')
    central_connection = fields.Char(string='Connection', compute='_compute_central_connection')

    def set_values(self):
        params = self.env['ir.config_parameter'].sudo()
        previous = [params.get_param('ab_branch_sync.' + key) or '' for key in ('url', 'database', 'api_key')]
        result = super().set_values()
        current = [params.get_param('ab_branch_sync.' + key) or '' for key in ('url', 'database', 'api_key')]
        if previous != current:
            params.set_param('ab_branch_sync.authorized', False)
            params.set_param('ab_branch_sync.ready', False)
            params.set_param('ab_branch_sync.connection_status', 'attention')
        return result

    def _compute_central_connection(self):
        journal = self.env['ab_branch_sync_operation']
        for record in self:
            record.central_connection = {'connected': _('Connected'),
                'attention': _('Connection or initial stock download needs attention'),
                'stock_error': _('Stock refresh needs attention')}.get(journal._param('connection_status'), _('Not connected'))

    def action_connect_central(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage connections.'))
        self.set_values()
        journal = self.env['ab_branch_sync_operation']
        params = self.env['ir.config_parameter'].sudo()
        try:
            info = journal._request('connection', {'origin': params.get_param('database.uuid')})
            journal._save_connection(info)
            journal._refresh_snapshots()
            params.set_param('ab_branch_sync.connection_status', 'connected')
            message = _('Connected. This installation reconnects automatically after restarts.')
        except ValidationError as error:
            params.set_param('ab_branch_sync.connection_status', 'attention')
            message = str(error)
        except (requests.RequestException, ValueError):
            params.set_param('ab_branch_sync.connection_status', 'attention')
            message = _('Connection failed. Check the central address, database, user API key and inventory access.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Branch Synchronization'), 'message': message, 'sticky': True}}

    def action_sync_now(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage connections.'))
        self.env['ab_branch_sync_operation']._sync_now()
        self.env['ab_branch_sync_operation']._refresh_snapshots()
        return True
