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

    def test_recovery_option_and_unknown_acknowledgement(self):
        page = self.url_open('/ab_storefront/auth/recover')
        self.assertIn('Recover via WhatsApp', page.text)
        response = self.url_open('/ab_storefront/auth/whatsapp/recover', data={'csrf_token': self.csrf(page), 'action': 'request', 'identifier': '01001234568'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('If an eligible account exists', response.text)
        self.assertIn('wa_recovery_code', response.text)
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
