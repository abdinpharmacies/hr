import json
import re
import secrets
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessDenied, AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase


@tagged("post_install", "-at_install")
class TestSignupOtp(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["ab_storefront_auth_service"].sudo()
        cls.users = cls.env["res.users"].with_context(no_reset_password=True).create([
            {"name": "OTP customer", "login": login, "email": login if "@" in login else False,
             "password": "Original9!Pass", "ab_signup_otp_pending": True,
             "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])]}
            for login in ("signup.otp@example.test", "+201012345678")
        ])
        cls.email_user, cls.phone_user = cls.users
        cls.service._set_identity(cls.phone_user, "telegram", "930001", "930001")
        cls.env["ir.config_parameter"].sudo().set_param("auth_signup.invitation_scope", "b2c")

    def setUp(self):
        super().setUp()
        self.patch(type(self.env["ab_storefront_auth_telegram"]), "_enabled", lambda _self: True)
        self.patch(type(self.service), "_wake_delivery", lambda _self: None)
        self.browser = secrets.token_urlsafe(32)

    def _request(self, user):
        token = self.service._request_signup_otp(user, self.browser, "192.0.2.5")
        challenge = self.service._find(token, ["signup_otp"], self.browser)
        event = self.env["ab_storefront_auth_event"].search([("challenge_id", "=", challenge.id)])
        payload = json.loads(self.service._cipher().decrypt(event.payload.encode()))
        code = payload.get("code") or re.search(r"\b[0-9]{6}\b", payload["text"]).group()
        return token, challenge, code

    def test_phone_otp_is_scoped_hashed_and_single_use(self):
        token, challenge, code = self._request(self.phone_user)
        self.assertNotEqual(challenge.code_hash, code)
        self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, "wrong-browser", code))
        self.assertFalse(self.service._verify_signup_otp(self.email_user, token, self.browser, code))
        self.assertTrue(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))
        self.assertFalse(self.phone_user._ab_needs_signup_otp())
        self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))

    def test_phone_otp_keeps_existing_device_protection(self):
        token, challenge, code = self._request(self.phone_user)
        self.assertEqual(challenge.channel, "telegram")
        self.assertTrue(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))
        self.assertFalse(self.phone_user._ab_needs_signup_otp())
        self.assertEqual(self.phone_user._mfa_url(), "/ab_storefront/auth/device")

    def test_wrong_codes_exhaust_attempts(self):
        token, challenge, code = self._request(self.phone_user)
        for _index in range(5):
            self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, self.browser, "bad"))
        self.assertTrue(challenge.used_at)
        self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))
        self.assertTrue(self.phone_user._ab_needs_signup_otp())

    def test_expiry_password_change_and_destination_change(self):
        token, challenge, code = self._request(self.phone_user)
        challenge.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))
        challenge.expires_at = fields.Datetime.now() + timedelta(minutes=5)
        self.service._set_identity(self.phone_user, "telegram", "930002", "930002")
        self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))
        self.service._set_identity(self.phone_user, "telegram", "930001", "930001")
        self.phone_user.password = "Replacement9!Pass"
        self.assertFalse(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))

    def test_resend_cooldown_keeps_original_code(self):
        token, challenge, code = self._request(self.phone_user)
        with self.assertRaises(UserError):
            self._request(self.phone_user)
        self.assertTrue(self.service._verify_signup_otp(self.phone_user, token, self.browser, code))

    def test_disabled_telegram_does_not_bypass_gate(self):
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_enabled", return_value=False):
            with self.assertRaises(UserError):
                self._request(self.phone_user)
        self.assertEqual(self.phone_user._mfa_url(), "/ab_storefront/auth/signup-otp")
        with self.assertRaises(AccessDenied):
            self.service._remember_browser(self.phone_user, "Browser")
        self.assertFalse(self.service._complete_device_login(self.phone_user, "", ""))

    def test_email_registration_does_not_require_otp(self):
        login, password = self.env["res.users"].sudo().signup({"name": "New email", "login": "new.otp@example.test", "email": "new.otp@example.test", "password": "Original9!Pass"})
        user = self.env["res.users"].search([("login", "=", login)])
        self.assertFalse(user.ab_signup_otp_pending)
        self.assertFalse(user._ab_needs_signup_otp())
        self.assertFalse(self.env.ref("base.user_admin")._ab_needs_signup_otp())
        self.assertTrue(self.email_user.ab_signup_otp_pending)
        self.assertFalse(self.email_user._mfa_url())
        self.assertFalse(self.service._identities(self.email_user))

    def test_pending_flag_and_challenges_are_not_customer_writable(self):
        for actor in (self.email_user, self.env.ref("base.public_user")):
            with self.assertRaises(AccessError):
                self.email_user.with_user(actor).write({"ab_signup_otp_pending": False})
            with self.assertRaises(AccessError):
                self.env["ab_storefront_auth_challenge"].with_user(actor).search([])
        with self.assertRaises(AccessDenied):
            self.phone_user.with_user(self.phone_user)._check_credentials({"type": "password", "password": "Original9!Pass"}, {"interactive": False})

    def test_verification_view_uses_arabic_translation(self):
        view = self.env.ref("ab_ecommerce_storefront.auth_signup_otp")
        self.assertIn("Verify and sign in", view.with_context(lang="en_US").arch_db)
        self.assertIn("تأكيد الرمز وتسجيل الدخول", view.with_context(lang="ar_001").arch_db)

    def test_email_cannot_request_or_receive_signup_otp(self):
        with self.assertRaises(AccessDenied):
            self._request(self.email_user)
        self.email_user.with_user(self.email_user)._check_credentials(
            {"type": "password", "password": "Original9!Pass"}, {"interactive": False},
        )



@tagged("post_install", "-at_install")
class TestSignupOtpHTTP(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.lang_en").active = True
        cls.env.ref("website.default_website").write({"language_ids": [(4, cls.env.ref("base.lang_en").id)], "default_lang_id": cls.env.ref("base.lang_en").id})
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("ab_storefront_auth.development", "True")
        params.set_param("ab_storefront_auth.base_url", cls.base_url())
        params.set_param("auth_signup.invitation_scope", "b2c")

    def _csrf(self, page):
        return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.text).group(1)

    def test_email_registration_and_later_login_work_without_otp(self):
        service = self.env["ab_storefront_auth_service"].sudo()
        with patch.object(type(service), "_request_signup_otp") as request_otp:
            page = self.url_open("/web/signup")
            created = self.url_open("/web/signup", data={"csrf_token": self._csrf(page), "name": "Email customer", "login": "http.signup.otp@example.test", "password": "Original9!Pass", "confirm_password": "Original9!Pass"})
            self.assertEqual(created.status_code, 200)
            self.assertNotIn("signup-otp", created.url)
            account = self.url_open("/my/home", allow_redirects=False)
            self.assertEqual(account.status_code, 200)
            user = self.env["res.users"].search([("login", "=", "http.signup.otp@example.test")])
            self.assertFalse(user.ab_signup_otp_pending)
            self.assertFalse(service._identities(user).filtered(lambda identity: identity.kind == "email"))
            self.assertFalse(self.env["ab_storefront_auth_challenge"].search_count([("user_id", "=", user.id), ("purpose", "=", "signup_otp")]))
            self.url_open("/web/session/logout?redirect=/web/login")
            user.ab_signup_otp_pending = True
            page = self.url_open("/web/login")
            logged = self.url_open("/web/login", data={"csrf_token": self._csrf(page), "login": user.login, "password": "Original9!Pass", "redirect": "/my/home"})
            self.assertEqual(logged.status_code, 200)
            self.assertNotIn("signup-otp", logged.url)
            self.assertEqual(self.url_open("/my/home", allow_redirects=False).status_code, 200)
            request_otp.assert_not_called()

    def test_pending_route_requires_password_and_csrf(self):
        self.assertIn("/web/login", self.url_open("/ab_storefront/auth/signup-otp").url)
        self.assertEqual(self.url_open("/ab_storefront/auth/signup-otp", data={"action": "verify", "code": "123456"}).status_code, 400)
