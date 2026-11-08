import re
import secrets

from odoo import fields, models
from odoo.exceptions import AccessDenied, ValidationError

from odoo.addons.ab_website_sale_product.services.legacy_activation import LegacyCodeSecurity
from .auth_identity import normalize_identity


class LegacyCustomerActivation(models.Model):
    _inherit = 'ab_ecommerce_legacy_customer'

    def _portal_status(self, user, website):
        if user != self.env.user or user._is_public() or not user._is_portal() or user._is_internal():
            return {'linked': False, 'eligible': False}
        if website.company_id not in user.company_ids or (user.website_id and user.website_id != website):
            return {'linked': False, 'eligible': False}
        records = self.sudo()
        linked = records.search(fields.Domain('website_id', '=', website.id) & fields.Domain('partner_id', '=', user.partner_id.id), limit=1)
        if linked:
            return {'linked': True, 'eligible': False}
        phones = self.env['ab_storefront_auth_service']._identities(user).filtered(lambda item: item.kind == 'phone').mapped('value')
        eligible = bool(phones and records.search_count(
            fields.Domain('website_id', '=', website.id) & fields.Domain('phone', 'in', phones)
            & fields.Domain('partner_id', '=', False) & fields.Domain('code_hash', '!=', False) & fields.Domain('attempts', '<', 5) & fields.Domain('expires_at', '>', fields.Datetime.now()), limit=1,
        ))
        return {'linked': False, 'eligible': eligible}

    def _claim(self, user, website, phone, code, ip):
        if user != self.env.user or user._is_public() or not user._is_portal() or user._is_internal():
            raise AccessDenied()
        if website.company_id not in user.company_ids or (user.website_id and user.website_id != website):
            raise AccessDenied()
        service = self.env['ab_storefront_auth_service']
        if not service._rate_allow('legacy-claim-ip', ip, 30) or not service._rate_allow('legacy-claim-user', str(user.id), 10):
            return False
        try:
            phone = normalize_identity('phone', phone)
        except ValidationError:
            return False
        LegacyCodeSecurity(self.env)._lock(f'legacy-import-website:{website.id}')
        LegacyCodeSecurity(self.env)._lock(f'legacy-claim-partner:{website.id}:{user.partner_id.id}')
        LegacyCodeSecurity(self.env)._lock(f'legacy-phone:{website.id}:{phone}')
        records = self.sudo()
        if records.search_count(fields.Domain('website_id', '=', website.id) & fields.Domain('partner_id', '=', user.partner_id.id), limit=1):
            return False
        record = records.search(fields.Domain('website_id', '=', website.id) & fields.Domain('phone', '=', phone), limit=1)
        if not record or record.partner_id or not record.code_hash or not record.expires_at or record.expires_at <= fields.Datetime.now() or record.attempts >= 5:
            return False
        record.write({'attempts': record.attempts + 1})
        code = re.sub(r'[\s-]', '', str(code or ''))
        if not re.fullmatch(r'[0-9]{12}', code) or not secrets.compare_digest(record.code_hash, record._code_digest(code)):
            return False
        record.write({'partner_id': user.partner_id.id, 'claimed_user_id': user.id, 'claimed_at': fields.Datetime.now(), 'code_hash': False})
        return True
