import re
import logging
import secrets
from datetime import timedelta
from uuid import uuid4

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.ab_ecommerce_storefront.models.auth_identity import normalize_identity
from odoo.addons.ab_ecommerce_storefront.models.auth_service import AuthRateLimitError


class WhatsAppChannel(models.AbstractModel):
    _name = 'ab_storefront_auth_whatsapp'
    _inherit = 'ab_storefront_auth_channel'
    _description = 'Storefront WhatsApp Verification Channel'

    def _identity_kind(self):
        return 'whatsapp'

    def _enabled(self):
        return bool(self.env['ab_storefront_auth_service']._wa_transport())

    def _available_for(self, user):
        return self._enabled() and bool(self.env['ab_storefront_auth_service']._verified_whatsapp(user))

    def _prepare_recovery(self, service, challenge, token):
        transport = service._wa_transport()
        if transport:
            challenge.write({'wa_transport_id': transport.id})
            service._wa_queue(challenge, token)


class WhatsAppService(models.AbstractModel):
    _inherit = 'ab_storefront_auth_service'

    def _rate_allow_with_retry(self, action, subject, limit=None, window=3600):
        if action == 'recovery' and str(subject).startswith('+'):
            action = 'link-phone'
        elif action == 'recovery-ip':
            action = 'link-ip'
        return super()._rate_allow_with_retry(action, subject, limit, window)

    def _setting(self, name, default, minimum=1, maximum=86400):
        if self.env.context.get('wa_fixed_limits') and name in ('otp_expiration', 'otp_max_attempts', 'resend_cooldown'):
            return {'otp_expiration': 300, 'otp_max_attempts': 5, 'resend_cooldown': 60}[name]
        return super()._setting(name, default, minimum, maximum)

    def _channel_registry(self):
        return dict(super()._channel_registry(), whatsapp='ab_storefront_auth_whatsapp')

    def _wa_transport(self):
        website_id = request.website.id if request and hasattr(request, 'website') else self.env.context.get('website_id')
        if not website_id:
            return self.env['ab_storefront_whatsapp_transport'].sudo().browse()
        return self.env['ab_storefront_whatsapp_transport'].sudo().search([
            ('website_id', '=', website_id), ('enabled', '=', True),
            ('service_user_id.active', '=', True),
        ], limit=1)

    def _find(self, token, purposes, browser=None):
        challenge = super()._find(token, purposes, browser)
        if challenge and challenge.channel == 'whatsapp':
            if not browser:
                return challenge.browse()
            self.env.cr.execute('SELECT id FROM ab_storefront_auth_challenge WHERE id = %s FOR UPDATE', (challenge.id,))
            challenge = super()._find(token, purposes, browser)
            if not challenge:
                return challenge
            transport = self._wa_transport()
            if not transport or challenge.wa_transport_id != transport:
                return challenge.browse()
        return challenge

    def _wa_queue(self, challenge, token):
        transport = challenge.wa_transport_id
        language = challenge.user_id.lang if challenge.user_id else self.env.lang
        arabic = (language or '').startswith('ar')
        code = self._generate_otp(challenge, token)
        event = self._queue('whatsapp', {
            'destination': challenge.value.lstrip('+'), 'code': code,
            'template': transport.template_ar if arabic else transport.template_en,
            'language': transport.language_ar if arabic else transport.language_en,
        }, challenge)
        event.write({'wa_transport_id': transport.id, 'state': 'wa_pending', 'wa_scope_hash': transport._scope_hash(), 'wa_uuid': str(uuid4())})
        return event

    def _wa_invalidate(self, browser):
        self._lock('wa-browser:' + self._digest(browser))
        old = self.env['ab_storefront_auth_challenge'].sudo().search([
            ('browser_hash', '=', self._digest('browser:' + browser)),
            ('purpose', 'in', ['phone_signup', 'link']), ('used_at', '=', False),
        ])
        old.write({'used_at': fields.Datetime.now(), 'code_hash': False})
        self.env['ab_storefront_auth_event'].sudo().search([
            ('challenge_id', 'in', old.ids), ('channel', '=', 'whatsapp'),
            ('state', 'in', ['wa_pending', 'wa_leased']),
        ]).write({'state': 'done', 'payload': False})

    def _request_whatsapp_signup(self, phone, browser, ip):
        transport = self._wa_transport()
        if not transport:
            raise UserError(_('WhatsApp verification is unavailable. Choose Telegram or try again later.'))
        if not browser:
            raise ValidationError(_('The code or link is invalid or expired.'))
        if self.env['res.users']._get_signup_invitation_scope() != 'b2c':
            raise UserError(_('Signup is not allowed for uninvited users.'))
        phone = normalize_identity('phone', phone)
        for action, subject, limit, window in (
                ('link-ip', ip, 20, 3600), ('link-phone', phone, 5, 3600),
                ('wa-cooldown', phone, 1, 60)):
            allowed, retry = self._rate_allow_with_retry(action, subject, limit, window)
            if not allowed:
                raise AuthRateLimitError(retry)
        self._assert_available_identity(None, 'phone', phone)
        self._wa_invalidate(browser)
        challenge, token = self._new_challenge('phone_signup', browser=browser, value=phone, channel='whatsapp', ttl=300)
        challenge.write({'wa_transport_id': transport.id})
        self._wa_queue(challenge, token)
        return token

    def _verify_whatsapp_signup(self, token, browser, code):
        challenge = self._find(token, ['phone_signup'], browser)
        if not browser or not challenge or challenge.channel != 'whatsapp' or challenge.phone_verified:
            return False
        challenge.write({'attempts': challenge.attempts + 1})
        valid = (challenge.attempts <= 5 and isinstance(code, str)
                 and re.fullmatch(r'[0-9]{6}', code)
                 and secrets.compare_digest(challenge.code_hash or '', self._digest('otp:' + token + ':' + code)))
        if valid:
            challenge.write({'phone_verified': True, 'code_hash': False})
        elif challenge.attempts >= 5:
            challenge.write({'used_at': fields.Datetime.now(), 'code_hash': False})
        return bool(valid)

    def _finish_phone_signup(self, token, browser, values):
        challenge = self._find(token, ['phone_signup'], browser)
        if not challenge or challenge.channel != 'whatsapp':
            return super()._finish_phone_signup(token, browser, values)
        if not browser or not challenge.phone_verified:
            raise ValidationError(_('Verify your WhatsApp code first.'))
        self._lock('identity:phone:' + challenge.value)
        self._assert_available_identity(None, 'phone', challenge.value)
        if self.env['res.users']._get_signup_invitation_scope() != 'b2c':
            raise UserError(_('Signup is not allowed for uninvited users.'))
        with self.env.cr.savepoint():
            user = self.env['res.users'].sudo().with_context(no_reset_password=True)._signup_create_user(dict(
                values, login=challenge.value, phone=challenge.value,
                email=False, ab_signup_otp_pending=False,
                company_id=challenge.wa_transport_id.company_id.id,
                company_ids=[(6, 0, [challenge.wa_transport_id.company_id.id])],
            ))
            user.write({'email': False})
            self._set_identity(user, 'phone', challenge.value)
            self._set_identity(user, 'whatsapp', challenge.value)
            challenge.write({'user_id': user.id, 'used_at': fields.Datetime.now(), 'code_hash': False})
        return user

    def _request_recovery(self, channel, identifier, browser, ip):
        if channel != 'whatsapp':
            return super()._request_recovery(channel, identifier, browser, ip)
        transport = self._wa_transport()
        if not transport:
            return False
        token = super(WhatsAppService, self.with_context(wa_fixed_limits=True))._request_recovery(channel, identifier, browser, ip)
        if token:
            challenge = self.env['ab_storefront_auth_challenge'].sudo().search([('token_hash', '=', self._digest('token:' + token)), ('channel', '=', 'whatsapp')], limit=1)
            challenge.write({'wa_transport_id': transport.id, 'expires_at': fields.Datetime.now() + timedelta(seconds=300)})
            event = self.env['ab_storefront_auth_event'].sudo().search(fields.Domain('challenge_id', '=', challenge.id) & fields.Domain('channel', '=', 'recovery_request'), limit=1)
            self._process_event(event)
        return token

    def _verify_recovery(self, token, browser, code=None):
        challenge = self._find(token, ['otp', 'email_reset'], browser if code is not None else None)
        if not challenge or challenge.channel != 'whatsapp':
            return super()._verify_recovery(token, browser, code)
        if not browser:
            return False
        grant_token = super(WhatsAppService, self.with_context(wa_fixed_limits=True))._verify_recovery(token, browser, code)
        if grant_token:
            grant = self.env['ab_storefront_auth_challenge'].sudo().search([('token_hash', '=', self._digest('token:' + grant_token))], limit=1)
            grant.write({'channel': 'whatsapp', 'wa_transport_id': challenge.wa_transport_id.id})
        return grant_token

    def _prepare_recovery(self, challenge, payload):
        if challenge.channel != 'whatsapp':
            return super()._prepare_recovery(challenge, payload)
        transport = challenge.wa_transport_id
        if not transport.enabled or not transport.service_user_id.active:
            return
        scoped = self.with_context(website_id=transport.website_id.id)
        return super(WhatsAppService, scoped)._prepare_recovery(challenge, payload)

    def _verified_whatsapp(self, user):
        if not self._eligible_customer(user):
            return self.env['ab_storefront_auth_identity'].sudo().browse()
        identities = self._identities(user)
        identity = identities.filtered(lambda item: item.kind == 'whatsapp')
        if identity:
            return identity
        phone = identities.filtered(lambda item: item.kind == 'phone')
        if not phone or user.login != phone.value:
            return identity
        evidence = self.env['ab_storefront_auth_challenge'].sudo().search([
            ('purpose', '=', 'phone_signup'), ('channel', '=', 'whatsapp'),
            ('value', '=', phone.value), ('phone_verified', '=', True), ('used_at', '!=', False),
            ('wa_transport_id.company_id', '=', user.company_id.id),
            ('used_at', '>=', user.create_date.replace(microsecond=0)),
            ('used_at', '<=', user.create_date + timedelta(seconds=5)),
        ])
        evidence = evidence.filtered(lambda item: (
            (not user.website_id or item.wa_transport_id.website_id == user.website_id)
            and (not self._auth_website() or item.wa_transport_id.website_id == self._auth_website())
            and abs((item.used_at - phone.verified_at).total_seconds()) <= 1
            and (not item.user_id or item.user_id == user)))
        if len(evidence) == 1:
            self._set_identity(user, 'whatsapp', phone.value)
            identity = self._identities(user).filtered(lambda item: item.kind == 'whatsapp')
            identity.verified_at = phone.verified_at
        elif evidence:
            logging.getLogger(__name__).warning('WhatsApp signup evidence requires reverification: user=%s', user.id)
        return identity

    def _social_contacts(self, user):
        self._verified_whatsapp(user)
        return super()._social_contacts(user)

    def _recovery_destination(self, user, channel):
        if channel == 'whatsapp':
            self._verified_whatsapp(user)
        return super()._recovery_destination(user, channel)

    def _request_whatsapp_link(self, user, phone, browser, ip):
        if not self._eligible_customer(user) or not browser:
            raise ValidationError(_('The code or link is invalid or expired.'))
        transport = self._wa_transport()
        if not transport:
            raise UserError(_('WhatsApp verification is unavailable. Choose Telegram or try again later.'))
        phone = normalize_identity('whatsapp', phone)
        self._assert_available_identity(user, 'whatsapp', phone)
        for action, subject, limit, window in (
                ('link-ip', ip, 20, 3600), ('link-phone', phone, 5, 3600), ('wa-cooldown', phone, 1, 60)):
            allowed, retry = self._rate_allow_with_retry(action, subject, limit, window)
            if not allowed:
                raise AuthRateLimitError(retry)
        self._wa_invalidate(browser)
        challenge, token = self._new_challenge('link', user, browser, phone, 'whatsapp', ttl=300)
        challenge.wa_transport_id = transport
        self._wa_queue(challenge, token)
        return token

    def _finish_whatsapp_link(self, token, browser, user, code):
        challenge = self._find(token, ['link'], browser)
        if not challenge or challenge.channel != 'whatsapp' or challenge.user_id != user:
            return False
        if not self._verify_whatsapp_code(challenge, token, code):
            return False
        self._set_identity(user, 'whatsapp', challenge.value)
        if not user.partner_id.phone:
            user.partner_id.phone = challenge.value
        challenge.write({'used_at': fields.Datetime.now(), 'phone_verified': True, 'code_hash': False})
        return True

    def _verify_whatsapp_code(self, challenge, token, code):
        challenge.write({'attempts': challenge.attempts + 1})
        valid = (challenge.attempts <= 5 and isinstance(code, str)
                 and re.fullmatch(r'[0-9]{6}', code)
                 and secrets.compare_digest(challenge.code_hash or '', self._digest('otp:' + token + ':' + code)))
        if not valid and challenge.attempts >= 5:
            challenge.write({'used_at': fields.Datetime.now(), 'code_hash': False})
        return bool(valid)

    def _wa_deliverable(self, event):
        challenge = event.challenge_id
        transport = event.wa_transport_id
        if challenge:
            self.env.cr.execute('SELECT id FROM ab_storefront_auth_challenge WHERE id = %s FOR UPDATE', (challenge.id,))
            challenge.invalidate_recordset()
        return bool(transport.enabled and transport.service_user_id.active
                    and event.wa_scope_hash == transport._scope_hash()
                    and challenge and challenge.wa_transport_id == transport
                    and not challenge.used_at and not challenge.phone_verified
                    and challenge.expires_at > fields.Datetime.now() + timedelta(seconds=10)
                    and (not challenge.user_id or (
                        challenge.user_id.active and challenge.user_id.share
                        and challenge.user_id.company_id == transport.company_id
                        and (not challenge.user_id.website_id or challenge.user_id.website_id == transport.website_id)
                        and secrets.compare_digest(challenge.credential_stamp or '', self._credential_stamp(challenge.user_id)))))

