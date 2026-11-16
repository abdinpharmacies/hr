import json
import secrets
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from unittest.mock import patch
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from lxml import etree


@tagged('post_install', '-at_install')
class TestWhatsAppAuthentication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env['website'].search([], limit=1)
        cls.company = cls.website.company_id
        cls.env['ir.config_parameter'].sudo().set_param('auth_signup.invitation_scope', 'b2c')
        cls.worker = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Authentication worker', 'login': 'wa.worker@example.test',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.env.ref('ab_storefront_whatsapp_auth.group_auth_transport').id])],
        })
        transport_values = {
            'name': 'Test sender', 'website_id': cls.website.id, 'service_user_id': cls.worker.id,
            'sender': '123456', 'template_en': 'test_auth_en', 'template_ar': 'test_auth_ar',
            'enabled': True,
        }
        cls.transport = cls.env['ab_storefront_whatsapp_transport'].search([('website_id', '=', cls.website.id)], limit=1)
        if cls.transport:
            cls.transport.write(transport_values)
        else:
            cls.transport = cls.env['ab_storefront_whatsapp_transport'].create(transport_values)
        cls.customer = cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Verified customer', 'login': 'wa.customer@example.test', 'password': 'Original9!Pass',
            'company_id': cls.company.id, 'company_ids': [(6, 0, [cls.company.id])],
            'group_ids': [(6, 0, [cls.env.ref('base.group_portal').id])],
        })

    def setUp(self):
        super().setUp()
        self.service = self.env['ab_storefront_auth_service'].with_context(website_id=self.website.id, lang='en_US').sudo()
        self.browser = secrets.token_urlsafe(32)
        self.phone = '+201001234567'
        self.exchange = self.transport.with_user(self.worker)

    def start(self):
        token = self.service._request_whatsapp_signup(self.phone, self.browser, '192.0.2.1')
        challenge = self.service._find(token, ['phone_signup'], self.browser)
        event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        payload = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())
        return token, challenge, event, payload['code']

    def test_signup_one_code_no_telegram_and_no_second_otp(self):
        token, challenge, event, code = self.start()
        self.assertNotIn(code, event.payload)
        self.assertTrue(self.service._verify_whatsapp_signup(token, self.browser, code))
        user = self.service._finish_phone_signup(token, self.browser, {'name': 'WhatsApp customer', 'password': 'Strong9!Pass'})
        self.assertEqual(set(self.service._identities(user).mapped('kind')), {'phone', 'whatsapp'})
        self.assertFalse(user.ab_signup_otp_pending)
        self.assertFalse(user._ab_device_protected())
        self.assertTrue(challenge.used_at)
        with self.assertRaises(UserError):
            self.service._finish_phone_signup(token, self.browser, {'name': 'Replay'})

    def test_completion_requires_code(self):
        token, challenge, event, code = self.start()
        with self.assertRaises(UserError):
            self.service._finish_phone_signup(token, self.browser, {'name': 'Unverified'})
        self.assertFalse(challenge.used_at)

    def test_wrong_browser_purpose_and_empty_browser(self):
        token, challenge, event, code = self.start()
        self.assertFalse(self.service._verify_whatsapp_signup(token, 'wrong-browser', code))
        self.assertFalse(self.service._verify_whatsapp_signup(token, '', code))
        self.assertFalse(self.service._verify_recovery(token, self.browser, code))
        self.assertFalse(challenge.phone_verified)

    def test_expiry_and_attempt_exhaustion(self):
        token, challenge, event, code = self.start()
        for index in range(5):
            self.assertFalse(self.service._verify_whatsapp_signup(token, self.browser, 'bad'))
        self.assertTrue(challenge.used_at)
        self.assertFalse(self.service._verify_whatsapp_signup(token, self.browser, code))

    def test_expired_code(self):
        token, challenge, event, code = self.start()
        challenge.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self.assertFalse(self.service._verify_whatsapp_signup(token, self.browser, code))
        self.assertIsNone(self.exchange._exchange('lease', {}))
        self.assertFalse(event.payload)

    def test_resend_supersedes_old_and_cancels_unsent(self):
        token, challenge, event, code = self.start()
        with self.assertRaises(UserError):
            self.service._request_whatsapp_signup(self.phone, self.browser, '192.0.2.1')
        key = self.service._digest('rate:wa-cooldown:' + self.phone)
        self.env['ab_storefront_auth_rate'].search([('key', '=', key)]).expires_at = fields.Datetime.now() - timedelta(seconds=1)
        replacement = self.service._request_whatsapp_signup(self.phone, self.browser, '192.0.2.1')
        self.assertNotEqual(token, replacement)
        self.assertTrue(challenge.used_at)
        self.assertFalse(event.payload)
        self.assertFalse(self.service._verify_whatsapp_signup(token, self.browser, code))

    def test_duplicate_and_archived_phone_rejected(self):
        self.service._set_identity(self.customer, 'phone', self.phone)
        self.customer.active = False
        with self.assertRaises(UserError):
            self.start()

    def test_ownership_rechecked_at_completion(self):
        token, challenge, event, code = self.start()
        self.assertTrue(self.service._verify_whatsapp_signup(token, self.browser, code))
        self.service._set_identity(self.customer, 'phone', self.phone)
        with self.assertRaises(UserError):
            self.service._finish_phone_signup(token, self.browser, {'name': 'Duplicate'})
        self.assertFalse(challenge.used_at)

    def test_disabled_channel_and_wrong_website_fail_closed(self):
        token, challenge, event, code = self.start()
        self.assertFalse(self.service.with_context(website_id=False)._verify_whatsapp_signup(token, self.browser, code))
        self.transport.enabled = False
        self.assertFalse(self.service._verify_whatsapp_signup(token, self.browser, code))
        with self.assertRaises(UserError):
            self.start()

    def test_worker_has_no_orm_access_and_other_actors_denied(self):
        token, challenge, event, code = self.start()
        for model in ('ab_storefront_auth_challenge', 'ab_storefront_auth_event', 'ab_storefront_whatsapp_transport'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.worker).search([])
        with self.assertRaises(AccessError):
            self.transport.with_user(self.customer)._exchange('lease', {})
        lease = self.exchange._exchange('lease', {})
        self.assertTrue(lease)
        with self.assertRaises(AccessError):
            self.exchange._exchange('dispatch', dict(lease, lease='forged'))

    def test_lease_dispatch_report_and_status_idempotence(self):
        token, challenge, event, code = self.start()
        lease = self.exchange._exchange('lease', {})
        self.assertNotIn('code', lease)
        job = self.exchange._exchange('dispatch', lease)
        self.assertEqual(job['code'], code)
        self.assertIsNone(self.exchange._exchange('dispatch', lease))
        self.exchange._exchange('report', dict(lease, status='accepted', reference='wamid.test'))
        self.assertEqual(event.state, 'wa_accepted')
        self.assertFalse(event.payload)
        for state in ('read', 'delivered', 'accepted', 'failed', 'read'):
            self.exchange._exchange('status', {'delivery': event.wa_uuid, 'reference': 'wamid.test', 'status': state})
        self.assertEqual(event.state, 'wa_read')
        self.assertFalse(challenge.phone_verified)

    def test_dispatch_crash_unknown_outcome_no_retry(self):
        token, challenge, event, code = self.start()
        lease = self.exchange._exchange('lease', {})
        self.exchange._exchange('dispatch', lease)
        event.wa_lease_until = fields.Datetime.now() - timedelta(seconds=1)
        self.assertIsNone(self.exchange._exchange('lease', {}))
        self.assertEqual(event.state, 'wa_unknown')
        self.assertFalse(event.payload)

    def test_revoked_service_account_cannot_dispatch(self):
        token, challenge, event, code = self.start()
        lease = self.exchange._exchange('lease', {})
        self.worker.active = False
        with self.assertRaises(AccessError):
            self.exchange._exchange('dispatch', lease)

    def test_recovery_verified_phone_and_password_stamp(self):
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        token = self.service._request_recovery('whatsapp', self.phone, self.browser, '192.0.2.1')
        self.service._process_queue()
        challenge = self.service._find(token, ['otp'], self.browser)
        self.assertEqual(challenge.user_id, self.customer)
        event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        code = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())['code']
        stamp = self.service._credential_stamp(self.customer)
        grant = self.service._verify_recovery(token, self.browser, code)
        self.assertTrue(grant)
        self.assertTrue(self.service._reset_password(grant, self.browser, 'NewStrong9!Pass'))
        self.assertNotEqual(stamp, self.service._credential_stamp(self.customer))
        self.assertFalse(self.service._reset_password(grant, self.browser, 'Replay9!Pass'))

    def test_partner_only_recovery_decoy(self):
        self.env['res.partner'].create({'name': 'Order contact only', 'phone': self.phone})
        token = self.service._request_recovery('whatsapp', self.phone, self.browser, '192.0.2.1')
        self.service._process_queue()
        challenge = self.service._find(token, ['otp'], self.browser)
        self.assertFalse(challenge.user_id)
        self.assertFalse(self.env['ab_storefront_auth_event'].search_count([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')]))
        self.assertFalse(self.service._verify_recovery(token, self.browser, '123456'))

    def test_cancel_blocks_dispatch(self):
        token, challenge, event, code = self.start()
        lease = self.exchange._exchange('lease', {})
        self.service._wa_invalidate(self.browser)
        self.assertIsNone(self.exchange._exchange('dispatch', lease))
        self.assertFalse(event.payload)

    def test_shared_phone_and_ip_limits(self):
        for index in range(5):
            self.assertTrue(self.service._rate_allow('recovery', self.phone, 5))
        with self.assertRaises(UserError):
            self.start()
        for index in range(20):
            self.service._rate_allow('link-ip', '192.0.2.5', 20)
        self.assertFalse(self.service._rate_allow('recovery-ip', '192.0.2.5', 20))

    def test_config_change_invalidates_dispatch_scope(self):
        token, challenge, event, code = self.start()
        lease = self.exchange._exchange('lease', {})
        self.transport.sender = '999999'
        self.assertIsNone(self.exchange._exchange('dispatch', lease))
        self.assertFalse(event.payload)

    def test_wrong_worker_and_company_are_denied(self):
        token, challenge, event, code = self.start()
        intruder = self.worker.copy({'name': 'Other worker', 'login': 'wa.intruder@example.test'})
        with self.assertRaises(AccessError):
            self.transport.with_user(intruder)._exchange('lease', {})
        other_company = self.env['res.company'].create({'name': 'Other authentication company'})
        self.website.company_id = other_company
        with self.assertRaises(AccessError):
            self.exchange._exchange('lease', {})

    def test_recovery_grant_is_transport_bound(self):
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        token = self.service._request_recovery('whatsapp', self.phone, self.browser, '192.0.2.1')
        self.service._process_queue()
        challenge = self.service._find(token, ['otp'], self.browser)
        event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        code = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())['code']
        grant = self.service._verify_recovery(token, self.browser, code)
        self.assertTrue(grant)
        self.assertFalse(self.service._reset_password(grant, '', 'Other9!Pass'))
        self.assertFalse(self.service.with_context(website_id=False)._reset_password(grant, self.browser, 'Other9!Pass'))
        self.transport.enabled = False
        self.assertFalse(self.service._reset_password(grant, self.browser, 'Other9!Pass'))

    def recovery_code(self, token):
        challenge = self.service._find(token, ['otp'], self.browser)
        pending = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'recovery_request')])
        self.service._process_event(pending)
        event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', challenge.channel)])
        payload = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())
        return challenge, payload

    def test_phone_identity_does_not_verify_whatsapp(self):
        self.service._set_identity(self.customer, 'phone', self.phone)
        self.assertFalse(self.service._channel('whatsapp')._available_for(self.customer))
        self.assertFalse(self.service._request_recovery('whatsapp', self.customer.login, self.browser, '192.0.2.1'))

    def test_link_replaces_only_whatsapp_and_preserves_profile(self):
        self.customer.phone = '+201112345678'
        login = self.customer.login
        self.service._set_identity(self.customer, 'telegram', '910001', '910001', '+201112345678')
        token = self.service._request_whatsapp_link(self.customer, self.phone, self.browser, '192.0.2.1')
        challenge = self.service._find(token, ['link'], self.browser)
        event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        code = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())['code']
        self.assertFalse(self.service._identities(self.customer).filtered(lambda item: item.kind == 'whatsapp'))
        self.assertFalse(self.service._finish_whatsapp_link(token, self.browser, self.worker, code))
        self.assertFalse(self.service._finish_whatsapp_link(token, 'forged', self.customer, code))
        self.assertTrue(self.service._finish_whatsapp_link(token, self.browser, self.customer, code))
        self.assertEqual(self.customer.phone, '+201112345678')
        self.assertEqual(self.customer.login, login)
        self.assertEqual(self.service._identities(self.customer).filtered(lambda item: item.kind == 'telegram').phone_value, '+201112345678')
        self.assertFalse(self.service._finish_whatsapp_link(token, self.browser, self.customer, code))

    def test_link_populates_empty_profile_phone(self):
        self.customer.phone = False
        token = self.service._request_whatsapp_link(self.customer, self.phone, self.browser, '192.0.2.1')
        challenge = self.service._find(token, ['link'], self.browser)
        event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        code = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())['code']
        self.assertTrue(self.service._finish_whatsapp_link(token, self.browser, self.customer, code))
        self.assertEqual(self.customer.phone, self.phone)

    def test_login_lookup_and_distinct_destinations(self):
        self.customer.phone = '+201222345678'
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        self.service._set_identity(self.customer, 'telegram', '910001', '910001', '+201112345678')
        with patch.object(type(self.env['ab_storefront_auth_telegram']), '_enabled', return_value=True):
            self.assertEqual(set(self.service._available_channels(self.customer)), {'whatsapp', 'telegram'})
            for identifier in (self.customer.login, self.phone, '+201112345678'):
                self.assertEqual(self.service._resolve_recovery_user(identifier), self.customer)
            token = self.service._request_recovery('whatsapp', self.customer.login, self.browser, '192.0.2.1')
            challenge, payload = self.recovery_code(token)
            self.assertEqual(payload['destination'], self.phone.lstrip('+'))
            self.service._invalidate_recovery(self.browser)
            self.assertFalse(self.service._verify_recovery(token, self.browser, payload['code']))
            self.env['ab_storefront_auth_rate'].search([]).unlink()
            token = self.service._request_recovery('telegram', self.phone, self.browser, '192.0.2.1')
            challenge, payload = self.recovery_code(token)
            self.assertEqual(payload['chat_id'], '910001')

    def test_ambiguous_lookup_and_company_scope(self):
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        self.worker.write({'login': self.phone})
        other = self.customer.copy({'name': 'Ambiguous customer', 'login': 'ambiguous@example.test', 'email': self.customer.login})
        self.assertFalse(self.service._resolve_recovery_user(self.customer.login))
        other.email = False
        company = self.env['res.company'].create({'name': 'Other recovery company'})
        self.customer.write({'company_id': company.id, 'company_ids': [(6, 0, [company.id])]})
        self.assertFalse(self.service._resolve_recovery_user(self.phone))
        self.assertFalse(self.service._available_channels(self.customer))
        with self.assertRaises(ValidationError):
            self.service._request_whatsapp_link(self.customer, self.phone, self.browser, '192.0.2.1')

    def test_existing_completed_signup_evidence(self):
        token, challenge, event, code = self.start()
        self.assertTrue(self.service._verify_whatsapp_signup(token, self.browser, code))
        user = self.service._finish_phone_signup(token, self.browser, {'name': 'Existing WhatsApp customer', 'password': 'Strong9!Pass'})
        self.service._identities(user).filtered(lambda item: item.kind == 'whatsapp').unlink()
        challenge.user_id = False
        self.assertTrue(self.service._verified_whatsapp(user))
        self.assertEqual(self.service._verified_whatsapp(user).verified_at, self.service._identities(user).filtered(lambda item: item.kind == 'phone').verified_at)

    def test_ambiguous_signup_evidence_requires_reverification(self):
        token, challenge, event, code = self.start()
        self.assertTrue(self.service._verify_whatsapp_signup(token, self.browser, code))
        user = self.service._finish_phone_signup(token, self.browser, {'name': 'Ambiguous WhatsApp customer', 'password': 'Strong9!Pass'})
        self.service._identities(user).filtered(lambda item: item.kind == 'whatsapp').unlink()
        challenge.copy({'token_hash': self.service._digest('duplicate-evidence')})
        self.assertFalse(self.service._verified_whatsapp(user))

    def test_lookup_limits_and_browser_binding(self):
        token = self.service._lookup_recovery(self.customer.login, self.browser, '192.0.2.1')
        self.assertTrue(self.service._find(token, ['lookup'], self.browser))
        self.assertFalse(self.service._find(token, ['lookup'], 'forged'))
        self.assertFalse(self.service._find(token, ['lookup'], ''))
        for index in range(9):
            self.assertTrue(self.service._lookup_recovery(self.customer.login, self.browser, '192.0.2.1'))
        self.assertFalse(self.service._lookup_recovery(self.customer.login, self.browser, '192.0.2.1'))

    def test_recovery_replacement_invalidates_old_code_and_grant(self):
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        token = self.service._request_recovery('whatsapp', self.customer.login, self.browser, '192.0.2.1')
        challenge, payload = self.recovery_code(token)
        grant = self.service._verify_recovery(token, self.browser, payload['code'])
        self.assertTrue(grant)
        self.service._set_identity(self.customer, 'whatsapp', '+201112345678')
        self.assertFalse(self.service._reset_password(grant, self.browser, 'Replacement9!Pass'))
        self.assertFalse(self.service._verify_recovery(token, self.browser, payload['code']))

    def test_recovery_shares_whatsapp_signup_phone_limit(self):
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        for index in range(5):
            self.service._rate_allow('link-phone', self.phone, 5)
        self.assertFalse(self.service._request_recovery('whatsapp', self.customer.login, self.browser, '192.0.2.1'))

    def test_recovery_reaches_gateway_with_auth_cron_disabled(self):
        self.env.ref('ab_ecommerce_storefront.cron_auth_delivery').active = False
        self.service._set_identity(self.customer, 'whatsapp', self.phone)
        token = self.service._request_recovery('whatsapp', self.customer.login, self.browser, '192.0.2.1')
        challenge = self.service._find(token, ['otp'], self.browser)
        request_event = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'recovery_request')])
        self.assertEqual(request_event.state, 'done')
        self.assertFalse(request_event.payload)
        delivery = self.env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        self.assertEqual(delivery.state, 'wa_pending')
        lease = self.exchange._exchange('lease', {})
        self.assertTrue(lease)
        payload = self.exchange._exchange('dispatch', lease)
        self.assertEqual(payload['destination'], self.phone.lstrip('+'))
        self.assertTrue(self.service._verify_recovery(token, self.browser, payload['code']))

    def test_settings_transport_views_load_from_xml_files(self):
        transport = self.env['ab_storefront_whatsapp_transport'].with_user(self.env.ref('base.user_admin')).with_context(read_arch_from_file=True, lang='en_US')
        views = [(self.env.ref('ab_storefront_whatsapp_auth.transport_list').id, 'list'),
                 (self.env.ref('ab_storefront_whatsapp_auth.transport_form').id, 'form')]
        result = transport.get_views(views)
        for view_type in ('list', 'form'):
            self.assertEqual(etree.fromstring(result['views'][view_type]['arch']).tag, view_type)
        self.assertIn('service_user_id', result['views']['form']['arch'])
