import json
import secrets
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


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
        self.assertEqual(self.service._identities(user).mapped('kind'), ['phone'])
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
        self.service._set_identity(self.customer, 'phone', self.phone)
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
        self.service._set_identity(self.customer, 'phone', self.phone)
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
