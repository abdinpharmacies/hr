"""One-time enrollment on existing replica records; credentials are never replicated."""
import hashlib
import hmac
import secrets
from datetime import timedelta

import requests
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


def secret_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Replica(models.Model):
    _inherit = 'ab_replica_db'

    central_origin = fields.Char(readonly=True, copy=False, groups='base.group_system', index=True)
    central_key_hash = fields.Char(readonly=True, copy=False, groups='base.group_system')
    central_pair_hash = fields.Char(readonly=True, copy=False, groups='base.group_system', index=True)
    central_pair_expires = fields.Datetime(readonly=True, copy=False, groups='base.group_system')
    central_store_ids = fields.Many2many('ab_store', 'ab_central_sync_replica_store_rel', 'replica_id', 'store_id', string='Synchronization Stores', groups='base.group_system')
    central_default_store_id = fields.Many2one('ab_store', string='Synchronization Default Store', groups='base.group_system')
    central_ready = fields.Boolean(string='Opening balances and return history reviewed', groups='base.group_system')
    central_last_seen = fields.Datetime(readonly=True, copy=False)
    central_backlog = fields.Integer(readonly=True, copy=False)
    central_error = fields.Char(readonly=True, copy=False)
    _central_origin_unique = models.Constraint('UNIQUE(central_origin)', 'A branch installation can enroll only once.')

    @api.model_create_multi
    def create(self, vals_list):
        if any(any(key.startswith('central_') for key in vals) for vals in vals_list) and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage enrollment.'))
        return super().create(vals_list)

    def write(self, vals):
        if any(key.startswith('central_') for key in vals) and not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage enrollment.'))
        if {'allowed_sales_store_ids', 'default_sales_store_id', 'central_store_ids', 'central_default_store_id'} & vals.keys():
            journal = self.env['ab_central_sync_operation']
            local = self.get_current_from_config()
            enrolled_local = journal._param('role') == 'branch' and journal._param('enrolled') and bool(local) and local in self
            if self.filtered('central_key_hash') or enrolled_local:
                raise ValidationError(_('Revoke the connection before changing an enrolled branch store assignment.'))
        return super().write(vals)

    @api.constrains('central_store_ids', 'central_default_store_id', 'allowed_sales_store_ids')
    def _check_sync_scope(self):
        for replica in self:
            if replica.central_store_ids - replica.allowed_sales_store_ids:
                raise ValidationError(_('Synchronization stores must belong to the replica.'))
            if replica.central_store_ids and replica.central_default_store_id not in replica.central_store_ids:
                raise ValidationError(_('Select a default store within the synchronization scope.'))

    def _sync_stores(self):
        self.ensure_one()
        return self.central_store_ids or self.allowed_sales_store_ids

    def _check_central_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage enrollment.'))
        if self.env['ab_central_sync_operation']._param('role') != 'central':
            raise ValidationError(_('Configure this installation as central first.'))

    def action_pairing_code(self):
        self.ensure_one()
        self._check_central_admin()
        if not self.central_ready or not self._sync_stores() or not (self.central_default_store_id or self.default_sales_store_id):
            raise ValidationError(_('Review opening balances, return history, and assigned stores before enrollment.'))
        if any(not store.code for store in self._sync_stores()):
            raise ValidationError(_('Every assigned store requires a stable code.'))
        code = secrets.token_urlsafe(24)
        self.write({'central_pair_hash': secret_hash(code),
                    'central_pair_expires': fields.Datetime.now() + timedelta(minutes=15)})
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Pairing code (valid for 15 minutes)'), 'message': code, 'sticky': True}}

    def action_revoke_central(self):
        self._check_central_admin()
        self.write({'central_key_hash': False, 'central_pair_hash': False, 'central_pair_expires': False})
        return True

    @api.model
    def _enroll(self, payload):
        code, key = payload.get('code', ''), payload.get('key', '')
        if not isinstance(code, str) or not isinstance(key, str) or len(key) < 40:
            raise AccessError(_('Invalid enrollment.'))
        replica = self.search(fields.Domain('central_pair_hash', '=', secret_hash(code)), limit=1)
        if not replica:
            raise AccessError(_('Invalid enrollment.'))
        replica.lock_for_update(allow_referencing=True)
        replica.invalidate_recordset()
        if not replica.central_ready or not replica.central_pair_expires or replica.central_pair_expires < fields.Datetime.now():
            raise AccessError(_('The pairing code has expired.'))
        if replica.central_origin and replica.central_origin != payload['origin']:
            raise AccessError(_('This replica belongs to another branch installation.'))
        replica.write({'central_origin': payload['origin'], 'central_key_hash': secret_hash(key),
                       'central_pair_hash': False, 'central_pair_expires': False})
        return replica

    @api.model
    def _authenticate(self, origin, supplied):
        replica = self.search(fields.Domain('central_origin', '=', origin), limit=1)
        if not replica or not replica.central_ready or not replica.central_key_hash or not hmac.compare_digest(
                replica.central_key_hash, secret_hash(supplied.removeprefix('Bearer '))):
            raise AccessError(_('Invalid branch credentials.'))
        return replica

    def _connection_info(self):
        self.ensure_one()
        return {'version': 2, 'origin': self.central_origin, 'replica_serial': self.db_serial,
                'stores': self._sync_stores().mapped('code'), 'default_store': (self.central_default_store_id or self.default_sales_store_id).code}


class Settings(models.TransientModel):
    _inherit = 'res.config.settings'

    central_role = fields.Selection([('central', 'Central'), ('branch', 'Branch')],
                                   config_parameter='ab_central_sync.role', groups='base.group_system')
    central_url = fields.Char(string='Central URL', config_parameter='ab_central_sync.url', groups='base.group_system')
    central_database = fields.Char(string='Central Database', config_parameter='ab_central_sync.database', groups='base.group_system')
    central_ca_bundle = fields.Char(string='Central CA Bundle', config_parameter='ab_central_sync.ca_bundle', groups='base.group_system')
    central_pairing_code = fields.Char(string='Pairing Code', groups='base.group_system')
    central_connection = fields.Char(string='Connection', compute='_compute_central_connection')

    def _compute_central_connection(self):
        journal = self.env['ab_central_sync_operation']
        for record in self:
            status = journal._param('connection_status')
            record.central_connection = {'connected': _('Connected'),
                'attention': _('Connection or initial stock download needs attention'),
                'stock_error': _('Stock refresh needs attention')}.get(status, _('Not connected'))

    def set_values(self):
        journal = self.env['ab_central_sync_operation']
        current = journal._param('role')
        for settings in self:
            if current and settings.central_role != current and (journal._param('enrolled') or journal.sudo().search_count([], limit=1)):
                raise ValidationError(_('An enrolled installation with synchronization history cannot change its role.'))
        return super().set_values()

    def action_connect_central(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage enrollment.'))
        self.set_values()
        Journal = self.env['ab_central_sync_operation']
        if Journal._param('role') != 'branch':
            raise ValidationError(_('Select the branch role before connecting.'))
        Params = self.env['ir.config_parameter'].sudo()
        candidate = Journal._param('candidate_key')
        if self.central_pairing_code and Journal._param('candidate_code_hash') != secret_hash(self.central_pairing_code):
            candidate = secrets.token_urlsafe(48)
            Params.set_param('ab_central_sync.candidate_key', candidate)
            Params.set_param('ab_central_sync.candidate_code_hash', secret_hash(self.central_pairing_code))
        key = candidate or Journal._param('api_key')
        if not key:
            raise ValidationError(_('Enter a pairing code generated on central.'))
        origin = Params.get_param('database.uuid')
        try:
            # A lost pairing response is recovered using the already persisted credential.
            try:
                info = Journal._request('connection', {'origin': origin}, credential=key)
            except (requests.RequestException, ValueError, ValidationError):
                info = Journal._request('pair', {'origin': origin, 'code': self.central_pairing_code or '', 'key': key}, credential=key)
            Journal._save_connection(info)
            Params.set_param('ab_central_sync.api_key', key)
            Params.set_param('ab_central_sync.candidate_key', False)
            Params.set_param('ab_central_sync.candidate_code_hash', False)
            Journal._refresh_snapshots()
            Params.set_param('ab_central_sync.connection_status', 'connected')
            message = _('Connected. This installation reconnects automatically after restarts.')
        except (requests.RequestException, ValueError, ValidationError) as error:
            Params.set_param('ab_central_sync.connection_status', 'attention')
            message = _('Connection or stock download is incomplete. Check the central address, catalog, and pairing code, then retry.')
        self.central_pairing_code = False
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Central Synchronization'), 'message': message, 'sticky': True}}

    def action_sync_now(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can manage enrollment.'))
        self.env['ab_central_sync_operation']._sync_now()
        return True
