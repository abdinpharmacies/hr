"""Standard Odoo user API keys authorize the inventory transport."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class InventoryWriter(models.Model):
    _inherit = 'res.users'

    def _check_central_inventory_writer(self):
        self.ensure_one()
        if not self.active or not self.has_group('ab_central_sync.group_inventory_writer'):
            raise AccessError(_('An active Inventory Writer user is required.'))

    def _central_inventory_stores(self, replica):
        """The replica's sales settings are the sole transport store assignment."""
        self._check_central_inventory_writer()
        replica.ensure_one()
        stores = replica._sync_stores().filtered(
            lambda store: replica.active and store.active and store.allow_sale
            and store.company_id in self.company_ids)
        if not stores:
            raise AccessError(_('The replica has no active sales stores in the API user companies.'))
        return stores


class Replica(models.Model):
    _inherit = 'ab_replica_db'

    central_last_seen = fields.Datetime(readonly=True, copy=False)
    central_backlog = fields.Integer(readonly=True, copy=False)
    central_error = fields.Char(readonly=True, copy=False)

    def _sync_stores(self):
        self.ensure_one()
        return self.allowed_sales_store_ids

    @api.model
    def _authenticate_inventory_key(self, supplied):
        if not isinstance(supplied, str) or not supplied.startswith('Bearer '):
            raise AccessError(_('A user API key is required.'))
        key = supplied.removeprefix('Bearer ').strip()
        uid = self.env['res.users.apikeys']._check_credentials(scope='rpc', key=key) if key else False
        if not uid:
            raise AccessError(_('The user API key is invalid or expired.'))
        user = self.env['res.users'].browse(uid)
        user._check_central_inventory_writer()
        return user

    @api.model
    def _inventory_connection(self, user, serial, origin):
        replica = self.search(fields.Domain('db_serial', '=', serial) & fields.Domain('active', '=', True), limit=2)
        if len(replica) != 1:
            raise AccessError(_('The branch replica is missing or ambiguous.'))
        stores = user._central_inventory_stores(replica)
        if not stores or any(not store.code for store in stores):
            raise AccessError(_('The API user has no inventory access to this branch.'))
        default = replica.default_sales_store_id & stores or stores[:1]
        return replica, stores, {'version': 2, 'inventory_protocol': 3, 'authentication': 'user_api_key',
            'origin': origin, 'replica_serial': replica.db_serial,
            'stores': stores.mapped('code'), 'default_store': default.code}
