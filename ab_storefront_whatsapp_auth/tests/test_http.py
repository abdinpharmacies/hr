import json
import re
from datetime import timedelta

from odoo import fields

from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged('post_install', '-at_install')
class TestWhatsAppHTTP(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.lang_en').active = True
        cls.website = cls.env.ref('website.default_website')
        cls.website.write({'language_ids': [(4, cls.env.ref('base.lang_en').id), (4, cls.env.ref('base.lang_ar').id)], 'default_lang_id': cls.env.ref('base.lang_en').id})
        params = cls.env['ir.config_parameter'].sudo()
        params.set_param('ab_storefront_auth.development', 'True')
        params.set_param('auth_signup.reset_password', 'True')
        params.set_param('auth_signup.invitation_scope', 'b2c')
        cls.worker = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'HTTP auth worker', 'login': 'http.wa.worker@example.test',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('ab_storefront_whatsapp_auth.group_auth_transport').id])],
        })
        transport_values = {
            'name': 'HTTP test sender', 'website_id': cls.website.id, 'service_user_id': cls.worker.id,
            'sender': '123456', 'template_en': 'auth_en', 'template_ar': 'auth_ar', 'enabled': True,
        }
        cls.transport = cls.env['ab_storefront_whatsapp_transport'].search([('website_id', '=', cls.website.id)], limit=1)
        if cls.transport:
            cls.transport.write(transport_values)
        else:
            cls.transport = cls.env['ab_storefront_whatsapp_transport'].create(transport_values)

    def csrf(self, response):
        self.assertEqual(response.status_code, 200, response.text[:500])
        return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text).group(1)

    def test_signup_form_and_complete_account(self):
        page = self.url_open('/web/signup')
        self.assertIn('data-ab-whatsapp-start', page.text)
        started = self.url_open('/ab_storefront/auth/whatsapp', data={'csrf_token': self.csrf(page), 'action': 'start', 'name': 'HTTP WhatsApp customer', 'login': '01001234567'})
        self.assertIn('wa_code', started.text)
        event = self.env['ab_storefront_auth_event'].sudo().search([('channel', '=', 'whatsapp')], order='id desc', limit=1)
        service = self.env['ab_storefront_auth_service'].sudo()
        code = json.loads(service._cipher().decrypt(event.payload.encode()).decode())['code']
        verified = self.url_open('/ab_storefront/auth/whatsapp', data={'csrf_token': self.csrf(started), 'action': 'verify', 'code': code})
        self.assertIn('Phone verified.', verified.text)
        self.assertIn('name="password"', verified.text)
        completed = self.url_open('/ab_storefront/auth/whatsapp', data={'csrf_token': self.csrf(verified), 'action': 'signup', 'password': 'Strong9!Pass', 'confirm_password': 'Strong9!Pass'})
        self.assertEqual(completed.status_code, 200)
        user = self.env['res.users'].sudo().search([('login', '=', '+201001234567')])
        self.assertTrue(user)
        self.assertFalse(user.ab_signup_otp_pending)
        self.assertFalse(user._ab_device_protected())
        self.assertFalse(self.env['ab_storefront_auth_identity'].sudo().search_count([('user_id', '=', user.id), ('kind', '=', 'telegram')]))

        self.url_open('/web/session/logout?redirect=/web/login')
        login = self.url_open('/web/login')
        reset_url = re.search(r'href="([^"]*/web/reset_password[^"]*)"', login.text).group(1).replace('&amp;', '&')
        recovery = self.url_open(reset_url)
        self.assertIn('recovery_identifier', recovery.text)
        chosen = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(recovery), 'action': 'identify', 'identifier': user.login})
        self.assertIn('Recover via WhatsApp', chosen.text)
        self.assertNotIn('Recover via Telegram', chosen.text)
        self.assertNotIn(user.login, chosen.text)
        sent = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(chosen), 'action': 'request', 'channel': 'whatsapp'})
        self.assertIn('security_code', sent.text)
        self.assertIn('security_code', self.url_open('/ab_storefront/auth/recover').text)
        event = self.env['ab_storefront_auth_event'].sudo().search([('channel', '=', 'whatsapp')], order='id desc', limit=1)
        payload = json.loads(service._cipher().decrypt(event.payload.encode()).decode())
        self.assertEqual(payload['destination'], '201001234567')
        verified = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(sent), 'action': 'otp', 'code': payload['code']})
        self.assertIn('name="action" value="password"', verified.text)
        reset = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(verified), 'action': 'password', 'password': 'Replacement9!Pass', 'confirm_password': 'Replacement9!Pass'})
        self.assertIn('Your password has been reset successfully', reset.text)
        login = self.url_open('/web/login')
        self.url_open('/web/login', data={'csrf_token': self.csrf(login), 'login': user.login, 'password': 'Strong9!Pass'})
        self.assertEqual(self.url_open('/my/home', allow_redirects=False).status_code, 303)
        login = self.url_open('/web/login')
        self.url_open('/web/login', data={'csrf_token': self.csrf(login), 'login': user.login, 'password': 'Replacement9!Pass'})
        self.assertEqual(self.url_open('/my/home', allow_redirects=False).status_code, 200)

    def test_recovery_option_and_unknown_acknowledgement(self):
        page = self.url_open('/web/reset_password')
        self.assertIn('recovery_identifier', page.text)
        self.assertNotIn('Recover via WhatsApp', page.text)
        response = self.url_open('/ab_storefront/auth/whatsapp/recover', data={'csrf_token': self.csrf(page), 'action': 'request', 'identifier': '01001234568'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('No verified recovery channels', response.text)
        self.assertNotIn('Recover via WhatsApp', response.text)
        self.assertEqual(self.url_open('/ab_storefront/auth/whatsapp/recover', data={'action': 'request'}).status_code, 400)

    def test_exchange_rejects_browser_sessions_and_http(self):
        response = self.url_open('/ab_storefront/auth/exchange/v1/lease', data=json.dumps({'source': 'forged'}), headers={'Content-Type': 'application/json'})
        self.assertIn(response.status_code, (401, 403))

    def test_arabic_screen_and_browser_phone_mode(self):
        page = self.url_open('/ar/ab_storefront/auth/whatsapp')
        self.assertEqual(page.status_code, 200)
        self.assertIn('التحقق من الهاتف عبر واتساب', page.text)
        self.browser_js('/web/signup', """
            const input = document.querySelector('input[name="login"]');
            input.value = '01001234567';
            input.dispatchEvent(new Event('input', {bubbles: true}));
            const button = document.querySelector('[data-ab-whatsapp-start]');
            if (!button || button.classList.contains('d-none')) { throw new Error('WhatsApp button hidden for phone'); }
            const previous = button.previousElementSibling;
            if (!previous.matches('[data-ab-auth-submit]')) { throw new Error('WhatsApp placement incorrect'); }
            input.value = 'email@example.test';
            input.dispatchEvent(new Event('input', {bubbles: true}));
            if (!button.classList.contains('d-none')) { throw new Error('WhatsApp visible for email'); }
            console.log('test successful');
        """, ready="document.querySelector('[data-ab-whatsapp-start]')?.dataset.abWhatsappReady === 'true'")

    def test_native_bearer_scope_and_https(self):
        key = self.env['res.users.apikeys'].with_user(self.worker)._generate(None, 'Authentication HTTP test', fields.Datetime.now() + timedelta(hours=1))
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key, 'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': self.base_url().split('://', 1)[1]}
        response = self.url_open('/ab_storefront/auth/exchange/v1/lease', data=json.dumps({'source': self.transport.source}), headers=headers)
        self.assertEqual(response.status_code, 200, response.text[:300])
        self.assertIsNone(response.json())
        response = self.url_open('/ab_storefront/auth/exchange/v1/lease', data=json.dumps({'source': 'forged'}), headers=headers)
        self.assertEqual(response.status_code, 403)
        headers.pop('X-Forwarded-Proto')
        response = self.url_open('/ab_storefront/auth/exchange/v1/lease', data=json.dumps({'source': self.transport.source}), headers=headers)
        self.assertEqual(response.status_code, 403)

    def test_whatsapp_survives_login_to_signup_navigation(self):
        self.browser_js('/web/login', """
            (async () => {
                document.querySelector('[data-ab-auth-nav="signup"]').click();
                for (let attempt = 0; attempt < 100; attempt++) {
                    if (document.querySelector('[data-ab-whatsapp-start]')?.dataset.abWhatsappReady === 'true') {
                        break;
                    }
                    await new Promise(resolve => setTimeout(resolve, 50));
                }
                const form = document.querySelector('form.oe_signup_form');
                const button = form?.querySelector('[data-ab-whatsapp-start]');
                if (!button) { throw new Error('WhatsApp missing after signup navigation'); }
                form.elements.name.value = 'Navigation test';
                form.elements.login.value = '01001234567';
                form.elements.login.dispatchEvent(new Event('input', {bubbles: true}));
                if (getComputedStyle(button).display === 'none') { throw new Error('WhatsApp hidden after navigation'); }
                button.focus();
                if (document.activeElement !== button) { throw new Error('WhatsApp cannot receive keyboard focus'); }
                const nativeSubmit = HTMLFormElement.prototype.submit;
                let submitted;
                HTMLFormElement.prototype.submit = function () {
                    submitted = {action: this.getAttribute('action'), values: Object.fromEntries(new FormData(this))};
                };
                try {
                    button.click();
                } finally {
                    HTMLFormElement.prototype.submit = nativeSubmit;
                }
                if (!submitted?.action.endsWith('/ab_storefront/auth/whatsapp') || submitted.values.login !== '01001234567' || submitted.values.action !== 'start') {
                    throw new Error('WhatsApp submission not handled after navigation');
                }
                console.log('test successful');
            })();
        """, ready="document.querySelector('.ab-auth-page')?.dataset.abWhatsappReady === 'true'")

    def test_contact_link_requires_password_and_ignores_forged_target(self):
        customer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Link customer', 'login': 'wa.link@example.test', 'password': 'Original9!Pass',
            'phone': '+201112345678', 'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.authenticate(customer.login, 'Original9!Pass')
        page = self.url_open('/ab_storefront/auth/whatsapp/link')
        denied = self.url_open('/ab_storefront/auth/whatsapp/link', data={'csrf_token': self.csrf(page), 'action': 'start', 'phone': '01001234567', 'current_password': 'incorrect'})
        self.assertIn('The current password is incorrect', denied.text)
        self.assertFalse(self.env['ab_storefront_auth_challenge'].sudo().search_count([('user_id', '=', customer.id), ('channel', '=', 'whatsapp')]))
        started = self.url_open('/ab_storefront/auth/whatsapp/link', data={'csrf_token': self.csrf(denied), 'action': 'start', 'phone': '01001234567', 'current_password': 'Original9!Pass', 'user_id': self.worker.id})
        event = self.env['ab_storefront_auth_event'].sudo().search([('channel', '=', 'whatsapp')], order='id desc', limit=1)
        self.assertEqual(event.challenge_id.user_id, customer)
        service = self.env['ab_storefront_auth_service'].sudo()
        code = json.loads(service._cipher().decrypt(event.payload.encode()).decode())['code']
        completed = self.url_open('/ab_storefront/auth/whatsapp/link', data={'csrf_token': self.csrf(started), 'action': 'verify', 'code': code, 'user_id': self.worker.id})
        self.assertIn('Account security', completed.text)
        self.assertEqual(service._identities(customer).filtered(lambda item: item.kind == 'whatsapp').value, '+201001234567')
        self.assertEqual(customer.phone, '+201112345678')
        self.assertFalse(service._identities(self.worker))

    def test_social_contact_mobile_english_and_arabic(self):
        self.patch(type(self.env['ab_storefront_auth_telegram']), '_enabled', lambda adapter: True)
        login = 'Layout9!Customer'
        self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Layout customer', 'login': login, 'password': login,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.browser_size = '390x844'
        for url, direction in (('/my/authentication', 'ltr'), ('/ar/my/authentication', 'rtl')):
            with self.subTest(direction=direction):
                self.browser_js(url, """
                    const contacts = [...document.querySelectorAll('.ab-security-social')];
                    if (document.querySelectorAll('.ab-security-methods .ab-security-method').length !== 4) { throw new Error('Security card layout differs by channel'); }
                    if (contacts.length !== 2) { throw new Error('Missing social contacts'); }
                    if (!contacts[0].textContent.includes(%s)) { throw new Error('Contact action is not translated'); }
                    if (getComputedStyle(document.body).direction !== %s) { throw new Error('Incorrect language direction'); }
                    for (const contact of contacts) {
                        const button = contact.querySelector('a.ab-security-verify-button');
                        if (!button || !button.textContent.trim() || !button.querySelector('.fa')) { throw new Error('Missing accessible action'); }
                        button.focus();
                        if (document.activeElement !== button) { throw new Error('Action cannot receive keyboard focus'); }
                        const rect = button.getBoundingClientRect();
                        if (rect.left < 0 || rect.right > innerWidth + 1) { throw new Error('Contact action overflows mobile viewport'); }
                    }
                    console.log('test successful');
                """ % (json.dumps("إضافة" if direction == "rtl" else "Add"), json.dumps(direction)), login=login, ready="document.querySelectorAll('.ab-security-social').length === 2")

    def test_verified_profile_icons(self):
        login = 'Icons9!Customer'
        customer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Icon customer', 'login': login, 'password': login,
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        self.env['ab_storefront_auth_service'].sudo()._set_identity(customer, 'whatsapp', '+201001234567')
        self.browser_js('/my/home', """
            const contact = document.querySelector('.ab-social-contact');
            const verified = contact?.querySelector('.ab-contact-verified');
            const action = contact?.querySelector('a.is-icon');
            if (!verified?.querySelector('.fa-check-circle')) { throw new Error('Verified check missing'); }
            if (getComputedStyle(verified).color !== 'rgb(19, 108, 56)') { throw new Error('Verified check is not green'); }
            if (!action?.querySelector('.fa-refresh') || !action.querySelector('.visually-hidden')?.textContent.trim()) { throw new Error('Accessible change icon missing'); }
            action.focus();
            if (document.activeElement !== action) { throw new Error('Change action cannot receive focus'); }
            console.log('test successful');
        """, login=login, ready="Boolean(document.querySelector('.ab-social-contact a.is-icon'))")

        self.browser_js('/my/authentication', """
            const whatsapp = document.querySelector('.ab-security-social:has(.is-whatsapp)');
            if (document.querySelectorAll('.ab-security-methods .ab-security-method').length !== 4) { throw new Error('Missing channel cards'); }
            if (!whatsapp?.querySelector('.ab-security-status.is-success .fa-check-circle')) { throw new Error('Verified channel badge differs'); }
            if (!whatsapp.querySelector('.ab-security-method-icon .fa-whatsapp')) { throw new Error('Channel card icon missing'); }
            if (!whatsapp.querySelector('a.ab-security-verify-button .fa-refresh')) { throw new Error('Channel card change action missing'); }
            console.log('test successful');
        """, login=login, ready="document.querySelectorAll('.ab-security-social').length === 2")

    def test_native_reset_token_remains_available(self):
        customer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Native reset customer', 'login': 'wa.native@example.test', 'password': 'Original9!Pass',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        customer.partner_id.signup_prepare(signup_type='reset')
        token = customer.partner_id._generate_signup_token()
        page = self.url_open('/web/reset_password?token=' + token)
        self.assertEqual(page.status_code, 200)
        self.assertIn('name="password"', page.text)
        self.assertNotIn('recovery_identifier', page.text)

    def test_signed_in_recovery_ignores_other_account_identifier(self):
        customer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Signed in customer', 'login': 'wa.signed@example.test', 'password': 'Original9!Pass',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        service = self.env['ab_storefront_auth_service'].sudo()
        service._set_identity(customer, 'whatsapp', '+201001234567')
        self.authenticate(customer.login, 'Original9!Pass')
        page = self.url_open('/ab_storefront/auth/recover')
        self.assertIn('Recover via WhatsApp', page.text)
        chosen = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(page), 'action': 'identify', 'identifier': self.worker.login})
        self.assertIn('Recover via WhatsApp', chosen.text)
        sent = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(chosen), 'action': 'request', 'channel': 'whatsapp', 'identifier': self.worker.login})
        self.assertIn('security_code', sent.text)
        challenge = self.env['ab_storefront_auth_challenge'].sudo().search([('purpose', '=', 'otp')], order='id desc', limit=1)
        self.assertEqual(challenge.user_id, customer)
        self.assertEqual(challenge.value, '+201001234567')

    def test_switch_resend_and_forged_channel(self):
        self.patch(type(self.env['ab_storefront_auth_telegram']), '_enabled', lambda adapter: True)
        self.patch(type(self.env['ab_storefront_auth_telegram']), '_deliver', lambda adapter, payload: None)
        customer = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Channel customer', 'login': 'wa.channels@example.test', 'password': 'Original9!Pass',
            'group_ids': [(6, 0, [self.env.ref('base.group_portal').id])],
        })
        service = self.env['ab_storefront_auth_service'].sudo()
        service._set_identity(customer, 'whatsapp', '+201001234567')
        service._set_identity(customer, 'telegram', '910009', '910009', '+201112345678')
        page = self.url_open('/web/reset_password')
        chosen = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(page), 'action': 'identify', 'identifier': customer.login})
        denied = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(chosen), 'action': 'request', 'channel': 'forged'})
        self.assertIn('Invalid recovery channel', denied.text)
        sent = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(denied), 'action': 'request', 'channel': 'whatsapp'})
        first = self.env['ab_storefront_auth_challenge'].sudo().search([('user_id', '=', customer.id), ('purpose', '=', 'otp')], order='id desc', limit=1)
        switched = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(sent), 'action': 'switch'})
        self.assertIn('Recover via Telegram', switched.text)
        first.invalidate_recordset()
        self.assertTrue(first.used_at)
        self.env['ab_storefront_auth_rate'].sudo().search([]).write({'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        sent = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(switched), 'action': 'request', 'channel': 'telegram'})
        second = self.env['ab_storefront_auth_challenge'].sudo().search([('user_id', '=', customer.id), ('purpose', '=', 'otp')], order='id desc', limit=1)
        resent = self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(sent), 'action': 'resend', 'channel': 'whatsapp'})
        self.assertIn('security_code', resent.text)
        self.assertEqual(self.env['ab_storefront_auth_challenge'].sudo().search([('user_id', '=', customer.id), ('purpose', '=', 'otp')], order='id desc', limit=1), second)
        self.assertEqual(second.channel, 'telegram')
        self.assertEqual(second.value, '910009')
        self.env['ab_storefront_auth_rate'].sudo().search([]).write({'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        self.url_open('/ab_storefront/auth/recover', data={'csrf_token': self.csrf(resent), 'action': 'resend', 'channel': 'whatsapp'})
        second.invalidate_recordset()
        self.assertTrue(second.used_at)
        latest = self.env['ab_storefront_auth_challenge'].sudo().search([('user_id', '=', customer.id), ('purpose', '=', 'otp')], order='id desc', limit=1)
        self.assertEqual(latest.channel, 'telegram')
        self.assertEqual(latest.value, '910009')

    def test_signup_channel_colors_and_phone_validation(self):
        self.patch(type(self.env['ab_storefront_auth_telegram']), '_enabled', lambda adapter: True)
        self.browser_js('/web/signup', """
            (async () => {
            const form = document.querySelector('form.oe_signup_form');
            const input = form.elements.login;
            const whatsapp = form.querySelector('[data-ab-whatsapp-start]');
            const telegram = form.querySelector('[data-ab-auth-submit]');
            for (const value of ['0122848978', '+20 122 848 978', '٠١٢٢٨٤٨٩٧٨']) {
                input.value = value;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                if (!telegram.disabled || !whatsapp.disabled) { throw new Error('Incomplete phone enables a channel'); }
            }
            for (const value of ['01228489786', '+20 122 848 9786', '٠١٢٢٨٤٨٩٧٨٦']) {
                input.value = value;
                input.dispatchEvent(new Event('input', {bubbles: true}));
                if (telegram.disabled || whatsapp.disabled) { throw new Error('Valid phone disables a channel'); }
            }
            await new Promise(resolve => setTimeout(resolve, 300));
            if (getComputedStyle(telegram).backgroundColor !== 'rgb(9, 107, 154)') { throw new Error('Telegram button is not blue'); }
            if (getComputedStyle(whatsapp).backgroundColor !== 'rgb(19, 108, 56)') { throw new Error('WhatsApp button is not green'); }
            input.value = 'email@example.test';
            input.dispatchEvent(new Event('input', {bubbles: true}));
            if (!whatsapp.classList.contains('d-none')) { throw new Error('WhatsApp visible in email mode'); }
            console.log('test successful');
            })();
        """, ready="document.querySelector('[data-ab-whatsapp-start]')?.dataset.abWhatsappReady === 'true'")
