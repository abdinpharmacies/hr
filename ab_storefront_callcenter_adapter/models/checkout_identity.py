import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError

from .adapter import _CAPTURE
from .chat import opaque


class Endpoint(models.Model):
    _inherit = 'ab_storefront_callcenter_endpoint'

    guest_metadata_enabled = fields.Boolean(string='Enable verified checkout identity after receiver upgrade')


class Submission(models.Model):
    _inherit = 'ab_storefront_submission'

    callcenter_origin = fields.Selection([('guest', 'Guest'), ('account', 'Account')], readonly=True)
    callcenter_visitor_identity = fields.Char(readonly=True)
    callcenter_account_identity = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not _CAPTURE.get() and any(any(key.startswith('callcenter_') for key in values) for values in values_list):
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if not _CAPTURE.get() and any(key.startswith('callcenter_') for key in values):
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    @api.model
    def _issue(self, kind, website, owner_hash, order=None):
        submission = super()._issue(kind, website, owner_hash, order)
        endpoint = self.env['ab_storefront_callcenter_endpoint'].sudo().search([
            ('website_id', '=', website.id), ('company_id', '=', website.company_id.id),
            ('enabled', '=', True), ('guest_metadata_enabled', '=', True),
        ], limit=1)
        if endpoint:
            account = not self.env.user._is_public() and owner_hash == hashlib.sha256(f'user:{self.env.uid}'.encode()).hexdigest()
            from odoo.http import request
            guest = request.session.get('ab_submission_owner') if request else False
            trusted_guest = guest and owner_hash == hashlib.sha256(('guest:' + guest).encode()).hexdigest()
            if account or trusted_guest:
                flag = _CAPTURE.set(True)
                try:
                    submission.write({'callcenter_origin': 'account' if account else 'guest',
                        'callcenter_account_identity': opaque(endpoint.source, 'account:' + str(self.env.uid)) if account else False,
                        'callcenter_visitor_identity': opaque(endpoint.source, 'checkout:' + owner_hash) if trusted_guest else False})
                finally:
                    _CAPTURE.reset(flag)
        return submission
