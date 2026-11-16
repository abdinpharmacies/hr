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
        return super()._render(template, values)

    @http.route('/ab_storefront/auth/whatsapp/recover', type='http', auth='public', website=True, sitemap=False, methods=['GET', 'POST'], csrf=True)
    def whatsapp_recover(self, **post):
        if request.httprequest.method == 'POST' and post.get('identifier'):
            post['action'] = 'identify'
        return self.recover(**post)

    @http.route('/ab_storefront/auth/whatsapp/link', type='http', auth='user', website=True, sitemap=False, methods=['GET', 'POST'], csrf=True)
    def whatsapp_link(self, **post):
        self._secure()
        user = request.env.user
        service = self._service()
        if not service._eligible_customer(user):
            raise Forbidden()
        browser = self._browser()
        token = request.session.get('ab_wa_link', '')
        challenge = service._find(token, ['link'], browser)
        if challenge and (challenge.user_id != user or challenge.channel != 'whatsapp'):
            challenge = challenge.browse()
        values = {'error': False, 'phone': challenge.value if challenge else user.phone or '', 'active': bool(challenge)}
        if request.httprequest.method == 'POST':
            try:
                action = post.get('action')
                if action in ('start', 'resend'):
                    self._confirm_password(user, post)
                    phone = challenge.value if action == 'resend' and challenge else post.get('phone', '')
                    token = service._request_whatsapp_link(user, phone, browser, self._ip())
                    request.session['ab_wa_link'] = token
                    values.update(active=True, phone=phone)
                elif action == 'verify':
                    if (not service._rate_allow('verify-ip', self._ip(), 60)
                            or not service._finish_whatsapp_link(token, browser, user, post.get('code', ''))):
                        raise UserError(_('The code or link is invalid or expired.'))
                    request.session.pop('ab_wa_link', None)
                    return request.redirect('/my/authentication', 303)
                else:
                    raise Forbidden()
            except UserError as error:
                values['error'] = error.args[0]
        response = request.render('ab_storefront_whatsapp_auth.whatsapp_link', values)
        response.headers.update({'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "frame-ancestors 'none'"})
        return response
