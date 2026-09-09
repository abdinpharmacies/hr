"""Enrollment UI and metadata for native Odoo bearer credentials."""
from datetime import timedelta
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.http import request
from odoo.addons.base.models.res_users import KEY_CRYPT_CONTEXT, INDEX_SIZE


class BranchCredentials(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _credential_metadata(self, key):
        # Odoo intentionally keeps the key hash/index outside ORM fields.
        self.env.cr.execute('SELECT id, key, expiration_date FROM res_users_apikeys '
                            'WHERE user_id = %s AND index = %s AND (scope IS NULL OR scope = %s)',
                            (self.env.uid, key[:INDEX_SIZE], 'rpc'))
        for key_id, digest, expiration in self.env.cr.fetchall():
            if KEY_CRYPT_CONTEXT.verify(key, digest):
                return {'credential_id': key_id, 'expires_at': fields.Datetime.to_string(expiration) if expiration else False}
        raise AccessError(_('The credential does not belong to this integration user.'))

    @api.model
    def get_connection_status(self, store_serial):
        result = self.get_capabilities(store_serial)
        if self.env.user.has_group('base.group_system'):
            raise AccessError(_('Use a dedicated non-administrator integration user.'))
        authorization = request.httprequest.headers.get('Authorization', '') if request else ''
        scheme, _, key = authorization.partition(' ')
        if scheme.lower() != 'bearer' or not key:
            raise AccessError(_('A bearer credential is required.'))
        result.update(self._credential_metadata(key))
        result.update({'user_id': self.env.uid, 'login': self.env.user.login,
                       'programmatic_keys': self.env['ir.config_parameter'].sudo().get_param(
                           'base.enable_programmatic_api_keys') in ('True', 'true', '1')})
        return result

    @api.model
    def revoke_credential(self, store_serial, key):
        self._scope(store_serial)
        keys = self.env['res.users.apikeys']
        uid = keys._check_credentials(scope='rpc', key=key)
        if uid and uid != self.env.uid:
            raise AccessError(_('The credential does not belong to this integration user.'))
        if not uid:
            return True  # Already revoked or expired: retirement is safe to retry.
        return bool(keys.revoke(key))


class BranchEnrollment(models.TransientModel):
    _name = 'ab_branch_api_enrollment'
    _description = 'Prepare Callcenter Connection'

    user_id = fields.Many2one('res.users', required=True, domain=[('share', '=', False)])
    store_id = fields.Many2one('ab_store', required=True)
    allow_post = fields.Boolean(string='Allow Posting')
    allow_cost = fields.Boolean(string='Allow Cost')
    enable_programmatic = fields.Boolean(string='Enable database-wide programmatic API key management', required=True)
    generated_key = fields.Char(compute='_compute_generated_key')
    database_name = fields.Char(compute='_compute_generated_key')

    @api.depends_context('branch_generated_key')
    def _compute_generated_key(self):
        for wizard in self:
            wizard.generated_key = self.env.context.get('branch_generated_key', False)
            wizard.database_name = self.env.cr.dbname

    def action_generate(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Settings administrator access is required.'))
        user = self.user_id
        if (not user.active or user.share or user.has_group('base.group_system')
                or not user.has_group('ab_branch_api.group_branch_api')):
            raise UserError(_('Choose an active non-administrator internal user with the Branch API User role.'))
        if not self.enable_programmatic:
            raise UserError(_('Confirm database-wide programmatic API key management.'))
        binding = self.env['ab_branch_api_access'].with_context(active_test=False).search(
            fields.Domain('user_id', '=', user.id) & fields.Domain('store_id', '=', self.store_id.id), limit=1)
        values = {'active': True, 'allow_post': self.allow_post, 'allow_cost': self.allow_cost}
        if binding:
            binding.write(values)
        else:
            self.env['ab_branch_api_access'].create(dict(values, user_id=user.id, store_id=self.store_id.id))
        self.env['ir.config_parameter'].sudo().set_param('base.enable_programmatic_api_keys', True)
        key = self.env['res.users.apikeys'].with_user(user)._generate(
            'rpc', 'Branch API enrollment %s' % uuid4(), fields.Datetime.now() + timedelta(days=90))
        # Secret exists only in the response/browser context, never in transient storage.
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': 'new', 'context': {'branch_generated_key': key}}
