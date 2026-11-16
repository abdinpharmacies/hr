from odoo import _, fields, http
from odoo.exceptions import UserError
from odoo.http import request
from werkzeug.exceptions import Forbidden

from odoo.addons.ab_ecommerce_storefront.controllers.auth import AbStorefrontAuth
from odoo.addons.ab_ecommerce_storefront.controllers.auth_security import StorefrontAuthSecurity


class WhatsAppSignupConfig(AbStorefrontAuth):
    def get_auth_signup_config(self):
        result = super().get_auth_signup_config()
        result['ab_whatsapp_enabled'] = request.env['ab_storefront_auth_whatsapp'].sudo()._enabled()
        return result


class WhatsAppAuthentication(StorefrontAuthSecurity):
    @http.route('/ab_storefront/auth/whatsapp', type='http', auth='public', website=True, sitemap=False, methods=['GET', 'POST'], csrf=True)
    def whatsapp(self, **post):
        self._secure()
        if request.session.uid:
            raise Forbidden()
        service = self._service()
        browser = self._browser()
        token = request.session.get('ab_wa_signup', '')
        values = {'error': False, 'retry_after': 0, 'verified': False,
                  'name': request.session.get('ab_wa_name', ''),
                  'phone': request.session.get('ab_wa_phone', ''), 'delivery_state': False}
        if request.httprequest.method == 'POST':
            action = post.get('action')
            try:
                if action in ('start', 'resend'):
                    name = (post.get('name', '') if action == 'start' else values['name']).strip()[:100]
                    phone = post.get('login', '') if action == 'start' else values['phone']
                    if not name:
                        raise UserError(_('Please fill in this field.'))
                    token = service._request_whatsapp_signup(phone, browser, self._ip())
                    challenge = service._find(token, ['phone_signup'], browser)
                    request.session.update(ab_wa_signup=token, ab_wa_name=name, ab_wa_phone=challenge.value)
                    values.update(name=name, phone=challenge.value, retry_after=60)
                elif action == 'verify':
                    if not service._rate_allow('verify-ip', self._ip(), 60) or not service._verify_whatsapp_signup(token, browser, post.get('code', '')):
                        raise UserError(_('The code or link is invalid or expired.'))
                elif action == 'cancel':
                    service._wa_invalidate(browser)
                    request.session.pop('ab_wa_signup', None)
                    return request.redirect('/web/signup?from_phone=1', 303)
                elif action == 'signup':
                    password = self._password(post)
                    with request.env.cr.savepoint():
                        user = service._finish_phone_signup(token, browser, {'name': values['name'], 'password': password, 'lang': request.env.lang})
                    request.env.cr.commit()
                    request.session.authenticate(request.env, {'login': user.login, 'password': password, 'type': 'password'})
                    request.session.pop('ab_wa_signup', None)
                    request.session.pop('ab_wa_name', None)
                    request.session.pop('ab_wa_phone', None)
                    if request.session.get('pre_uid'):
                        return request.redirect(user._mfa_url(), 303)
                    return request.redirect('/my/home', 303)
            except UserError as error:
                values['error'] = error.args[0]
                values['retry_after'] = getattr(error, 'retry_after', 0)
        challenge = service._find(token, ['phone_signup'], browser)
        values['verified'] = bool(challenge and challenge.channel == 'whatsapp' and challenge.phone_verified)
        values['active'] = bool(challenge and challenge.channel == 'whatsapp')
        if values['active']:
            event = request.env['ab_storefront_auth_event'].sudo().search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')], limit=1)
            values['delivery_state'] = event.state
            remaining = 60 - int((fields.Datetime.now() - challenge.create_date).total_seconds())
            values['retry_after'] = max(values['retry_after'], remaining, 0)
        return self._render('whatsapp_signup', values)

    def _render(self, template, values):
        if template == 'whatsapp_signup':
            values['ab_auth_security'] = True
            response = request.render('ab_storefront_whatsapp_auth.whatsapp_signup', values)
            response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'"})
            return response
        if template == 'auth_recovery':
            service = self._service()
            if service._channel('whatsapp')._enabled() and 'whatsapp' not in values['available_channels']:
                if not request.session.uid or service._channel('whatsapp')._available_for(request.env.user):
                    values['available_channels'].append('whatsapp')
        return super()._render(template, values)

    @http.route('/ab_storefront/auth/whatsapp/recover', type='http', auth='public', website=True, sitemap=False, methods=['POST'], csrf=True)
    def whatsapp_recover(self, **post):
        self._secure()
        if request.env['ir.config_parameter'].sudo().get_param('auth_signup.reset_password', 'False') != 'True':
            raise Forbidden()
        service = self._service()
        browser = self._browser()
        values = {'step': 'otp', 'error': False, 'message': False, 'available_channels': ['email', 'whatsapp'], 'telegram_enabled': False}
        action = post.get('action', 'request')
        if action in ('request', 'resend'):
            identifier = post.get('identifier', '') if action == 'request' else request.session.get('ab_wa_recovery_phone', '')
            request.session['ab_wa_recovery_phone'] = identifier[:254]
            token = service._request_recovery('whatsapp', identifier, browser, self._ip())
            if token:
                request.session['ab_wa_recovery_token'] = token
            values['message'] = _('If an eligible account exists, you will receive recovery instructions shortly.')
        elif action == 'otp':
            grant = service._verify_recovery(request.session.get('ab_wa_recovery_token', ''), browser, post.get('code', '')) if service._rate_allow('verify-ip', self._ip(), 60) else False
            if grant:
                request.session['ab_auth_grant'] = grant
                values['step'] = 'password'
            else:
                values['error'] = _('The code or link is invalid or expired.')
        else:
            raise Forbidden()
        response = request.render('ab_storefront_whatsapp_auth.whatsapp_recovery', values)
        response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'"})
        return response
