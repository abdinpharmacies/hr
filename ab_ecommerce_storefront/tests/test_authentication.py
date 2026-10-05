import json
import secrets
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..models.auth_identity import normalize_identity
from ..models.auth_channels import deployment_secret


@tagged("post_install", "-at_install")
class TestStorefrontAuthentication(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.params = cls.env["ir.config_parameter"].sudo()
        cls.params.set_param("ab_storefront_auth.base_url", "https://pharmacy.example")
        cls.params.set_param("auth_signup.invitation_scope", "b2c")
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Auth customer", "login": "auth.customer@example.test", "email": "auth.customer@example.test",
            "password": "Original9!Pass", "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        cls.other = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Other customer", "login": "auth.other@example.test", "email": "auth.other@example.test",
            "password": "Original9!Pass", "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })

    def setUp(self):
        super().setUp()
        self.service = self.env["ab_storefront_auth_service"].sudo()
        self.Challenge = self.env["ab_storefront_auth_challenge"].sudo()
        self.Event = self.env["ab_storefront_auth_event"].sudo()
        self.browser = secrets.token_urlsafe(32)
        self.enabled = patch.object(type(self.env["ab_storefront_auth_telegram"]), "_enabled", return_value=True)
        self.enabled.start()
        self.addCleanup(self.enabled.stop)

    def _decode(self, event):
        return json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())

    def test_development_http_loopback_addresses_only(self):
        self.params.set_param("ab_storefront_auth.development", "True")
        for host in ["localhost", "127.0.0.1", "127.0.0.4", "127.10.20.30", "::1"]:
            self.assertTrue(self.service._development_http_allowed(host))
        for host in ["192.168.1.1", "0.0.0.0", "8.8.8.8", "localhost.example.com", "127.0.0.4.example.com", "", None]:
            self.assertFalse(self.service._development_http_allowed(host))
        self.params.set_param("ab_storefront_auth.development", "False")
        self.assertFalse(self.service._development_http_allowed("127.0.0.4"))

    def test_public_base_url_loopback_development_only(self):
        self.params.set_param("ab_storefront_auth.development", "True")
        for origin in ["http://127.0.0.4:4092", "http://[::1]:4092"]:
            self.params.set_param("ab_storefront_auth.base_url", origin)
            self.assertEqual(self.service._base_url(), origin)
        self.params.set_param("ab_storefront_auth.base_url", "http://192.168.1.1:4092")
        with self.assertRaises(UserError):
            self.service._base_url()
        self.params.set_param("ab_storefront_auth.base_url", "http://127.0.0.4:4092")
        self.params.set_param("ab_storefront_auth.development", "False")
        with self.assertRaises(UserError):
            self.service._base_url()

    def test_secret_file_from_odoo_configuration(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "credential"
            value = secrets.token_urlsafe(32)
            path.write_text(value)
            path.chmod(0o600)
            with patch.dict(os.environ, {}, clear=True), patch("odoo.addons.ab_ecommerce_storefront.models.auth_channels.config.get", return_value=str(path)):
                self.assertEqual(deployment_secret("AB_STOREFRONT_TELEGRAM_TOKEN"), value)
                path.chmod(0o644)
                self.assertEqual(deployment_secret("AB_STOREFRONT_TELEGRAM_TOKEN"), "")

    def test_secret_environment_file_precedes_odoo_configuration(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "credential"
            value = secrets.token_urlsafe(32)
            path.write_text(value)
            path.chmod(0o600)
            with patch.dict(os.environ, {"AB_STOREFRONT_TELEGRAM_TOKEN_FILE": str(path)}, clear=True), patch("odoo.addons.ab_ecommerce_storefront.models.auth_channels.config.get", return_value="/missing/credential"):
                self.assertEqual(deployment_secret("AB_STOREFRONT_TELEGRAM_TOKEN"), value)

    def test_secret_missing_configured_file_is_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True), patch("odoo.addons.ab_ecommerce_storefront.models.auth_channels.config.get", return_value="/missing/credential"):
            self.assertEqual(deployment_secret("AB_STOREFRONT_TELEGRAM_TOKEN"), "")

    def _telegram(self, text=None, contact=None, sender=910001, chat=None):
        message = {"from": {"id": sender, "language_code": "ar"}, "chat": {"id": sender if chat is None else chat, "type": "private"}}
        if text:
            message["text"] = text
        if contact:
            message["contact"] = contact
        self.service._process_telegram_update({"message": message})

    def _link(self, user=None, sender=910001, phone="01012345678"):
        token, url = self.service._request_link(user or self.user, phone, self.browser, "test-ip")
        self._telegram("/start " + token, sender=sender)
        self._telegram(contact={"user_id": sender, "phone_number": "+201012345678"}, sender=sender)
        return token, url

    def _otp(self):
        token = self.service._request_recovery("telegram", "01012345678", self.browser, "test-ip")
        challenge = self.service._find(token, ["otp"], self.browser)
        event = self.Event.search([("challenge_id", "=", challenge.id), ("channel", "=", "recovery_request")])
        self.service._prepare_recovery(challenge, self._decode(event))
        event.write({"state": "done", "payload": False})
        delivery = self.Event.search([("challenge_id", "=", challenge.id), ("channel", "=", "telegram")])
        import re
        code = re.search(r"\b[0-9]{6}\b", self._decode(delivery)["text"]).group()
        return challenge, token, code

    def test_phone_normalization(self):
        for value in ["01012345678", "+20 101 234 5678", "00201012345678", "٠١٠١٢٣٤٥٦٧٨"]:
            self.assertEqual(normalize_identity("phone", value), "+201012345678")
        with self.assertRaises(ValidationError):
            normalize_identity("phone", "garbage01012345678")

    def test_email_normalization(self):
        self.assertEqual(normalize_identity("email", " Auth.Customer@Example.Test "), self.user.login)
        with self.assertRaises(ValidationError):
            normalize_identity("email", "Name <customer@example.test>")

    def test_email_verification_single_use(self):
        self.service._request_email_verification(self.user, self.user.email, self.browser, "test-ip")
        event = self.Event.search([("channel", "=", "email")], order="id desc", limit=1)
        token = self._decode(event)["url"].split("#")[1]
        self.assertTrue(self.service._confirm_email(token))
        self.assertFalse(self.service._confirm_email(token))
        self.assertIn("email", self.service._available_channels(self.user))

    def test_email_reset_and_password_hash(self):
        token = self.service._request_recovery("email", self.user.email, self.browser, "test-ip")
        self.assertFalse(self.service._find(token, ["email_reset"]).user_id)
        self.service._process_queue()
        self.assertTrue(self.env["mail.mail"].sudo().search([("email_to", "=", self.user.email)], limit=1))
        grant = self.service._verify_recovery(token, self.browser)
        self.assertTrue(grant)
        self.assertFalse(self.service._verify_recovery(token, self.browser))
        old_session = self.user._compute_session_token("old-session")
        self.assertTrue(self.service._reset_password(grant, self.browser, "Replacement9!Pass"))
        self.assertNotEqual(old_session, self.user._compute_session_token("old-session"))
        self.assertFalse(self.service._reset_password(grant, self.browser, "Another9!Pass"))
        self.user.with_user(self.user)._check_credentials({"type": "password", "password": "Replacement9!Pass"}, {"interactive": True})

    def test_expired_and_invalid_tokens(self):
        for purpose in ["email_reset", "email_verify", "link", "otp", "grant"]:
            challenge, token = self.service._new_challenge(purpose, self.user, self.browser)
            challenge.write({"expires_at": fields.Datetime.now() - timedelta(seconds=1)})
            self.assertFalse(self.service._find(token, [purpose], self.browser))
        self.assertFalse(self.service._find("invalid", ["email_reset"]))

    def test_no_account_enumeration_in_request(self):
        with patch.object(type(self.service), "_recovery_user", side_effect=AssertionError("Account lookup in HTTP request")):
            known = self.service._request_recovery("email", self.user.email, self.browser, "test-ip")
            missing = self.service._request_recovery("email", "missing@example.test", self.browser, "test-ip")
        self.assertEqual(len(known), len(missing))
        self.assertEqual(len(self.Event.search([("channel", "=", "recovery_request")])), 2)

    def test_unknown_phone_still_enforces_attempt_limits(self):
        token = self.service._request_recovery("telegram", "01012345678", self.browser, "test-ip")
        challenge = self.service._find(token, ["otp"], self.browser)
        self.assertFalse(challenge.user_id)
        for attempt in range(5):
            self.assertFalse(self.service._verify_recovery(token, self.browser, "000000"))
        self.assertEqual(challenge.attempts, 5)
        self.assertTrue(challenge.used_at)

    def test_link_deep_link_and_one_time_start(self):
        token, url = self._link()
        self.assertEqual(url, "https://t.me/Abdin_Pharmacy_Bot?start=" + token)
        self._telegram("/start " + token, sender=910002)
        challenge = self.service._find(token, ["link"], self.browser)
        self.assertEqual(challenge.telegram_user_id, "910001")
        self.assertFalse(self.service._finish_link(token, "wrong-browser", self.user))
        self.assertTrue(self.service._finish_link(token, self.browser, self.user))
        self.assertFalse(self.service._finish_link(token, self.browser, self.user))

    def test_own_contact_and_private_chat_required(self):
        token, url = self.service._request_link(self.user, "01012345678", self.browser, "test-ip")
        self._telegram("/start " + token, chat=910002)
        challenge = self.service._find(token, ["link"], self.browser)
        self.assertFalse(challenge.telegram_user_id)
        self._telegram("/start " + token)
        self._telegram(contact={"user_id": 910002, "phone_number": "+201012345678"})
        self.assertFalse(challenge.phone_verified)
        self._telegram(contact={"user_id": 910001, "phone_number": "+201112345678"})
        self.assertFalse(challenge.phone_verified)

    def test_duplicate_phone_prevention(self):
        self.service._set_identity(self.user, "phone", "+201012345678")
        with self.assertRaises(ValidationError):
            self.service._set_identity(self.other, "phone", "+201012345678")

    def test_duplicate_telegram_prevention(self):
        self.service._set_identity(self.user, "telegram", "910001", "910001")
        with self.assertRaises(ValidationError):
            self.service._set_identity(self.other, "telegram", "910001", "910001")

    def test_existing_login_cannot_be_claimed(self):
        with self.assertRaises(ValidationError):
            self.service._set_identity(self.other, "email", self.user.login)

    def test_unverified_partner_phone_cannot_recover(self):
        self.user.partner_id.phone = "01012345678"
        self.assertFalse(self.service._recovery_user("phone", "+201012345678"))

    def test_otp_success_single_use_browser_binding(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        challenge, token, code = self._otp()
        self.assertNotIn(code, challenge.code_hash)
        self.assertFalse(self.service._verify_recovery(token, "other-browser", code))
        grant = self.service._verify_recovery(token, self.browser, code)
        self.assertTrue(grant)
        self.assertFalse(self.service._verify_recovery(token, self.browser, code))
        self.assertFalse(self.service._reset_password(grant, "other-browser", "Replacement9!Pass"))

    def test_otp_max_wrong_attempts(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        challenge, token, code = self._otp()
        wrong = "000001" if code == "000000" else "000000"
        for attempt in range(5):
            self.assertFalse(self.service._verify_recovery(token, self.browser, wrong))
        self.assertEqual(challenge.attempts, 5)
        self.assertFalse(self.service._verify_recovery(token, self.browser, code))

    def test_otp_expiration(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        challenge, token, code = self._otp()
        challenge.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self.assertFalse(self.service._verify_recovery(token, self.browser, code))

    def test_cooldown_rate_and_resend_invalidation(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        challenge, token, code = self._otp()
        self.assertFalse(self.service._request_recovery("telegram", "01012345678", self.browser, "test-ip"))
        self.env["ab_storefront_auth_rate"].sudo().search([]).write({"expires_at": fields.Datetime.now() - timedelta(seconds=1)})
        replacement, new_token, new_code = self._otp()
        self.assertFalse(self.service._verify_recovery(token, self.browser, code))
        self.assertTrue(self.service._verify_recovery(new_token, self.browser, new_code))
        for index in range(5):
            self.assertTrue(self.service._rate_allow("rate-test", "subject"))
        self.assertFalse(self.service._rate_allow("rate-test", "subject"))

    def test_duplicate_update(self):
        update = {"update_id": 1000001, "message": {"from": {"id": 910001}, "chat": {"id": 910001, "type": "private"}, "text": "/start"}}
        self.assertTrue(self.service._ingest_update(update))
        self.assertTrue(self.service._ingest_update(update))
        self.assertEqual(self.Event.search_count([("update_key", "=", "1000001")]), 1)
        self.service._process_queue()
        self.assertFalse(self.Event.search([("update_key", "=", "1000001")]).payload)

    def test_combined_account_and_channels(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        self.service._set_identity(self.user, "email", self.user.email)
        self.assertEqual(set(self.service._available_channels(self.user)), {"email", "telegram"})
        self.assertEqual(set(self.service._identities(self.user).mapped("user_id").ids), {self.user.id})
        domain = self.env["res.users"]._get_login_domain("01012345678")
        self.assertEqual(self.env["res.users"].search(domain), self.user)
        self.assertEqual(self.env["res.users"].search(self.env["res.users"]._get_login_domain(self.user.email.upper())), self.user)

    def test_phone_signup_creates_one_portal_account(self):
        token, url = self.service._request_link(None, "01012345678", self.browser, "test-ip")
        with self.assertRaises(ValidationError):
            self.service._finish_phone_signup(token, self.browser, {"name": "Phone shopper", "password": "Original9!Pass"})
        self._telegram("/start " + token)
        self._telegram(contact={"user_id": 910001, "phone_number": "+201012345678"})
        user = self.service._finish_phone_signup(token, self.browser, {"name": "Phone shopper", "password": "Original9!Pass"})
        self.assertTrue(user.share)
        self.assertFalse(user.email)
        self.assertEqual(len(self.service._identities(user)), 2)
        with self.assertRaises(ValidationError):
            self.service._finish_phone_signup(token, self.browser, {"name": "Phone shopper", "password": "Original9!Pass"})

    def test_password_change_invalidates_challenges(self):
        challenge, token = self.service._new_challenge("grant", self.user, self.browser)
        self.user.write({"password": "ChangedElsewhere9!"})
        self.assertFalse(self.service._reset_password(token, self.browser, "Replacement9!Pass"))

    def test_authentication_models_are_private(self):
        for model in ["ab_storefront_auth_identity", "ab_storefront_auth_challenge", "ab_storefront_auth_rate", "ab_storefront_auth_event"]:
            for user in [self.user, self.env.ref("base.public_user")]:
                with self.assertRaises(AccessError):
                    self.env[model].with_user(user).search([])

    def test_cleanup_expired_challenges(self):
        challenge, token = self.service._new_challenge("link", self.user, self.browser)
        challenge.expires_at = fields.Datetime.now() - timedelta(days=2)
        self.Challenge._gc_challenges()
        self.assertFalse(challenge.exists())

    def test_cancel_does_not_unlink_verified_identity(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        self._telegram("/cancel")
        self.assertEqual(len(self.service._identities(self.user)), 2)

    def test_partner_email_edit_does_not_replace_verified_recovery(self):
        self.service._set_identity(self.user, "email", self.user.email)
        self.user.partner_id.email = "unverified.edit@example.test"
        self.assertFalse(self.service._recovery_user("email", self.user.partner_id.email))
        self.assertEqual(self.service._recovery_user("email", self.user.login), self.user)

    def test_telegram_disabled_preserves_email_recovery(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        self.service._set_identity(self.user, "email", self.user.email)
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_enabled", return_value=False):
            self.assertEqual(self.service._available_channels(self.user), ["email"])

    def test_plaintext_codes_are_not_in_queue_storage(self):
        token, url = self._link()
        self.service._finish_link(token, self.browser, self.user)
        challenge, token, code = self._otp()
        event = self.Event.search([("challenge_id", "=", challenge.id), ("channel", "=", "telegram")])
        self.assertNotIn(code, event.payload)
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_deliver", return_value=None):
            self.service._process_queue()
        self.assertFalse(event.payload)

    def test_retry_clears_payload_on_terminal_failure(self):
        from odoo.exceptions import UserError
        event = self.service._queue("telegram", {"chat_id": "910001", "text": "Authentication message"})
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_deliver", side_effect=UserError("Delivery unavailable")):
            for index in range(3):
                event.next_attempt = fields.Datetime.now()
                self.service._process_queue()
        self.assertEqual(event.state, "failed")
        self.assertFalse(event.payload)

    def test_additional_channel_reuses_recovery_core(self):
        from types import SimpleNamespace
        self.service._set_identity(self.user, "phone", "+201012345678")
        delivered_codes = []

        def prepare(service, challenge, token):
            code = service._generate_otp(challenge, token)
            service._queue("sms_test", {"code": code}, challenge)

        adapter = SimpleNamespace(
            _identity_kind=lambda: "phone", _recovery_purpose=lambda: "otp",
            _can_recover=lambda user: True, _prepare_recovery=prepare,
            _deliver=lambda payload: delivered_codes.append(payload["code"]),
        )
        original_channel = self.service._channel
        with patch.object(type(self.service), "_channel", side_effect=lambda name: adapter if name == "sms_test" else original_channel(name)):
            token = self.service._request_recovery("sms_test", "01012345678", self.browser, "test-ip")
            self.service._process_queue()
            self.assertEqual(len(delivered_codes), 1)
            self.assertTrue(self.service._verify_recovery(token, self.browser, delivered_codes[0]))
