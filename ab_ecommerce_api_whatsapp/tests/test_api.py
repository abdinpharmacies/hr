import json

from odoo.tests import tagged
from odoo.tests.common import HttpCase
from odoo.addons.ab_ecommerce_api.controllers.common import OPERATIONS
from odoo.addons.ab_ecommerce_api_whatsapp.controllers.api import WhatsAppApi


@tagged('post_install', '-at_install')
class TestWhatsAppApi(HttpCase):
    def test_phone_channel_defaults_and_recovery_contract(self):
        definitions = [item for item in OPERATIONS if item['operation_id'] == 'phone_start']
        self.assertEqual(definitions[-1]['payload']['properties']['channel']['enum'], ['telegram', 'whatsapp'])
        self.assertNotIn('channel', definitions[-1]['payload']['required'])
        definitions = [item for item in OPERATIONS if item['operation_id'] == 'recovery']
        self.assertIn('whatsapp', definitions[-1]['payload']['properties']['channel']['enum'])
        self.assertFalse(definitions[-1]['authenticated'])

    def test_optional_endpoint_validation(self):
        result = self.url_open('/api/v1/auth/phone/verify', data=json.dumps({}), headers={'Content-Type': 'application/json'})
        self.assertIn(result.status_code, (400, 403))

    def test_whatsapp_signup_and_recovery_end_to_end(self):
        from unittest.mock import patch

        website = self.env.ref('website.default_website')
        self.env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2c')
        worker = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'API auth worker', 'login': 'api.wa.worker@example.test',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id, self.env.ref('ab_storefront_whatsapp_auth.group_auth_transport').id])],
        })
        transport_values = {
            'name': 'API sender', 'website_id': website.id, 'service_user_id': worker.id,
            'sender': '123456', 'template_en': 'api_en', 'template_ar': 'api_ar', 'enabled': True,
        }
        transport = self.env['ab_storefront_whatsapp_transport'].search([('website_id', '=', website.id)], limit=1)
        if transport:
            transport.write(transport_values)
        else:
            self.env['ab_storefront_whatsapp_transport'].create(transport_values)

        def post(path, values):
            return self.url_open('/api/v1' + path, data=json.dumps(values), headers={'Content-Type': 'application/json'})

        response = post('/auth/phone/start', {'phone': '01001234569', 'channel': 'whatsapp'})
        self.assertEqual(response.status_code, 200, response.text)
        proof = response.json()['data']
        event = self.env['ab_storefront_auth_event'].sudo().search([('channel', '=', 'whatsapp')], order='id desc', limit=1)
        service = self.env['ab_storefront_auth_service'].sudo().with_context(website_id=website.id, lang='en_US')
        code = json.loads(service._cipher().decrypt(event.payload.encode()).decode())['code']
        verified = post('/auth/phone/verify', {'challenge_token': proof['challenge_token'], 'browser_token': proof['browser_token'], 'code': code})
        self.assertTrue(verified.json()['data']['verified'])
        complete = post('/auth/phone/complete', {'challenge_token': proof['challenge_token'], 'browser_token': proof['browser_token'], 'name': 'API WhatsApp customer', 'password': 'Strong9!Pass'})
        self.assertEqual(complete.status_code, 201, complete.text)
        self.assertIn('access_token', complete.json()['data'])
        recovery = post('/auth/recovery', {'channel': 'whatsapp', 'identifier': '01001234569'})
        self.assertEqual(recovery.status_code, 200, recovery.text)
        proof = recovery.json()['data']
        self.assertTrue(proof['accepted'])
        service._process_queue()
        event = self.env['ab_storefront_auth_event'].sudo().search([('channel', '=', 'whatsapp')], order='id desc', limit=1)
        code = json.loads(service._cipher().decrypt(event.payload.encode()).decode())['code']
        verified = post('/auth/recovery/verify', {'challenge_token': proof['challenge_token'], 'browser_token': proof['browser_token'], 'code': code})
        self.assertTrue(verified.json()['data']['verified'], verified.text)
        grant = verified.json()['data']['grant_token']
        reset = post('/auth/recovery/reset', {'grant_token': grant, 'browser_token': proof['browser_token'], 'password': 'Changed9!Pass'})
        self.assertEqual(reset.status_code, 200, reset.text)
        self.assertTrue(reset.json()['data']['reset'])
        expired = self.url_open('/api/v1/me', headers={'Authorization': 'Bearer ' + complete.json()['data']['access_token']})
        self.assertEqual(expired.status_code, 401)
        with patch.object(type(self.env['ab_storefront_auth_telegram']), '_enabled', return_value=True):
            default = post('/auth/phone/start', {'phone': '01001234570'})
            explicit = post('/auth/phone/start', {'phone': '01001234571', 'channel': 'telegram'})
        self.assertEqual(explicit.status_code, 200, explicit.text)
        self.assertEqual(default.status_code, 200, default.text)
        self.assertTrue(default.json()['data']['verification_url'].startswith('https://t.me/'))
