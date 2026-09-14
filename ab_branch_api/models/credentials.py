"""Authentication and metadata for native Odoo bearer credentials."""

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.base.models.res_users import KEY_CRYPT_CONTEXT, INDEX_SIZE


class BranchCredentials(models.AbstractModel):
    _inherit = 'ab_branch_api'

    def _credential_metadata(self, key):
        # Odoo intentionally keeps the key hash/index outside ORM fields.
        self.env.cr.execute('SELECT id, key, expiration_date FROM res_users_apikeys '
                            'WHERE user_id = %s AND index = %s AND (scope IS NULL OR scope = %s) '
                            "AND (expiration_date IS NULL OR expiration_date >= now() at time zone 'utc')",
                            (self.env.uid, key[:INDEX_SIZE], 'rpc'))
        for key_id, digest, expiration in self.env.cr.fetchall():
            if KEY_CRYPT_CONTEXT.verify(key, digest):
                return {'credential_id': key_id, 'expires_at': fields.Datetime.to_string(expiration) if expiration else False}
        raise AccessError(_('The credential does not belong to this integration user.'))

    @api.model
    def _authenticate_bearer(self):
        authorization = request.httprequest.headers.get('Authorization', '') if request else ''
        scheme, _, key = authorization.partition(' ')
        if scheme.lower() != 'bearer' or not key:
            raise AccessError(_('A bearer credential is required.'))
        owner = self.env['res.users.apikeys']._check_credentials(scope='rpc', key=key)
        user = self.env.user
        if not owner or owner != user.id:
            raise AccessError(_('The credential does not belong to this integration user.'))
        if (not user.active or user.share or not user.has_group('base.group_user')
                or user.has_group('base.group_system') or user.has_group('base.group_erp_manager')
                or user._is_superuser()):
            raise AccessError(_('Use an active internal non-administrator user.'))
        return key

    @api.model
    def get_connection_status(self, db_serial):
        result = self.get_capabilities(db_serial)
        result.update(self._credential_metadata(self._authenticate_bearer()))
        result.update({'user_id': self.env.uid, 'login': self.env.user.login})
        return result
