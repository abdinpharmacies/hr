import json
import re
import secrets
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessDenied, AccessError
from odoo.tests import tagged
from odoo.tests.common import ChromeBrowser, HttpCase, TransactionCase

from ..models.auth_device import DEVICE_COOKIE


@tagged("post_install", "-at_install")
class TestStorefrontAuthDevice(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env["ab_storefront_auth_service"].sudo()
        cls.users = cls.env["res.users"].with_context(no_reset_password=True).create([
            {"name": name, "login": login, "password": "Original9!Pass", "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])]}
            for name, login in [("Device customer", "device@example.test"), ("Other device customer", "other.device@example.test")]
        ])
        cls.user, cls.other = cls.users
        cls.service._set_identity(cls.user, "telegram", "920001", "920001")
        cls.service._set_identity(cls.other, "telegram", "920002", "920002")

    def setUp(self):
        super().setUp()
        self.patch(type(self.env["ab_storefront_auth_telegram"]), "_enabled", lambda _self: True)
        self.browser = secrets.token_urlsafe(32)

    def _challenge(self, user=None, browser=None, ip="192.0.2.1"):
        user = user or self.user
        browser = browser or self.browser
        token = self.service._new_device_login(user, browser, ip, "Test browser")
        return token, self.service._device_challenge(user, token, browser)

    def _decide(self, token, decision="a", sender=920001):
        self.service._process_device_callback({"id": "query", "from": {"id": sender}, "message": {"chat": {"id": sender, "type": "private"}}, "data": "ab:" + decision + ":" + token})

    def test_device_token_hash_scope_expiry_and_revocation(self):
        token = self.service._remember_browser(self.user, "Browser")
        device = self.service._trusted_device(self.user, token)
        self.assertTrue(device)
        self.assertNotEqual(device.token_hash, token)
        self.assertFalse(self.service._trusted_device(self.other, token))
        self.service._revoke_browser(self.other, device.id)
        self.assertTrue(self.service._trusted_device(self.user, token))
        device.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self.assertFalse(self.service._trusted_device(self.user, token))
        device.expires_at = fields.Datetime.now() + timedelta(days=30)
        self.service._revoke_browser(self.user, device.id)
        self.assertFalse(self.service._trusted_device(self.user, token))

    def test_approval_requires_owner_and_requesting_browser_and_is_single_use(self):
        token, challenge = self._challenge()
        self.assertTrue(challenge.approval_sent)
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser))
        self._decide(token, sender=920002)
        self.assertEqual(challenge.decision, "pending")
        self._decide(token)
        self.assertEqual(challenge.decision, "approved")
        self.assertFalse(self.service._complete_device_login(self.other, token, self.browser))
        self.assertFalse(self.service._complete_device_login(self.user, token, "wrong-browser"))
        self.assertTrue(self.service._complete_device_login(self.user, token, self.browser))
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser))

    def test_rejection_is_final_and_source_scoped(self):
        remembered = self.service._remember_browser(self.user, "Owner browser")
        token, challenge = self._challenge()
        self._decide(token, "r")
        self._decide(token, "a")
        self.assertEqual(challenge.decision, "rejected")
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser))
        self.assertTrue(self.service._device_cooldown(self.user, "192.0.2.1"))
        self.assertFalse(self.service._device_cooldown(self.user, "192.0.2.2"))
        self.assertFalse(self.service._device_cooldown(self.other, "192.0.2.1"))
        self.assertTrue(self.service._trusted_device(self.user, remembered))
        self.assertTrue(self.user.active)

    def test_expired_approval_and_password_change_invalidate_trust(self):
        remembered = self.service._remember_browser(self.user, "Owner browser")
        codes = self.service._generate_recovery_codes(self.user)
        token, challenge = self._challenge()
        challenge.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self._decide(token)
        self.assertEqual(challenge.decision, "pending")
        self.user.write({"password": "Replacement9!Pass"})
        self.assertFalse(self.service._trusted_device(self.user, remembered))
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser, codes[0]))
        self.assertEqual(self.env["ab_storefront_auth_recovery_code"].search_count([("user_id", "=", self.user.id), ("used_at", "=", False)]), 8)
        new_token, new_challenge = self._challenge()
        self.assertTrue(self.service._complete_device_login(self.user, new_token, self.browser, codes[0]))

    def test_recovery_code_is_hashed_scoped_single_use_and_revokes_trust(self):
        code = self.service._generate_recovery_codes(self.user)[0]
        self.assertNotIn(code.replace("-", ""), self.env["ab_storefront_auth_recovery_code"].search([]).mapped("code_hash"))
        remembered = self.service._remember_browser(self.user, "Owner browser")
        token, challenge = self._challenge()
        other_token, other_challenge = self._challenge(self.other, "other-browser")
        self.assertFalse(self.service._complete_device_login(self.other, other_token, "other-browser", code))
        self.assertTrue(self.service._complete_device_login(self.user, token, self.browser, code))
        self.assertFalse(self.service._trusted_device(self.user, remembered))
        second_token, second = self._challenge()
        self.assertFalse(self.service._complete_device_login(self.user, second_token, self.browser, code))

    def test_recovery_works_when_telegram_disabled_without_password_only_bypass(self):
        codes = self.service._generate_recovery_codes(self.user)
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_enabled", return_value=False):
            token, challenge = self._challenge()
            self.assertFalse(challenge.approval_sent)
            self.assertEqual(self.user._mfa_url(), "/ab_storefront/auth/device")
            self.assertFalse(self.service._complete_device_login(self.user, token, self.browser))
            self.assertTrue(self.service._complete_device_login(self.user, token, self.browser, codes[0]))

    def test_recovery_attempt_budget_and_regeneration(self):
        old = self.service._generate_recovery_codes(self.user)[0]
        current = self.service._generate_recovery_codes(self.user)[0]
        token, challenge = self._challenge()
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser, old))
        for _index in range(4):
            self.assertFalse(self.service._complete_device_login(self.user, token, self.browser, "wrong"))
        self.assertTrue(challenge.used_at)
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser, current))

    def test_notification_limit_preserves_existing_request(self):
        token, first = self._challenge()
        second_token, second = self._challenge(browser="second-browser")
        self.assertTrue(first.approval_sent)
        self.assertFalse(second.approval_sent)
        self._decide(token)
        self.assertTrue(self.service._complete_device_login(self.user, token, self.browser))

    def test_password_rpc_denied_and_backend_unaffected(self):
        with self.assertRaises(AccessDenied):
            self.user.with_user(self.user)._check_credentials({"type": "password", "password": "Original9!Pass"}, {"interactive": False})
        self.user.with_user(self.user)._check_credentials({"type": "password", "password": "Original9!Pass"}, {"interactive": True})
        self.assertFalse(self.env.ref("base.user_admin")._ab_device_protected())

    def test_private_models_reject_portal_and_public_orm(self):
        for actor in [self.user, self.env.ref("base.public_user")]:
            for model in ["ab_storefront_auth_device", "ab_storefront_auth_recovery_code", "ab_storefront_auth_challenge"]:
                with self.assertRaises(AccessError):
                    self.env[model].with_user(actor).search([])
                with self.assertRaises(AccessError):
                    self.env[model].with_user(actor).create({})

    def test_telegram_callback_ingestion_is_idempotent(self):
        token, challenge = self._challenge()
        payload = {"update_id": 880001, "callback_query": {"id": "query", "from": {"id": 920001}, "message": {"chat": {"id": 920001, "type": "private"}}, "data": "ab:a:" + token}}
        self.assertTrue(self.service._ingest_update(payload))
        self.assertTrue(self.service._ingest_update(payload))
        event = self.env["ab_storefront_auth_event"].search([("update_key", "=", "880001")])
        self.assertEqual(len(event), 1)
        self.service._process_event(event)
        self.assertEqual(challenge.decision, "approved")

    def test_group_callback_cannot_approve(self):
        token, challenge = self._challenge()
        self.service._process_device_callback({"from": {"id": 920001}, "message": {"chat": {"id": -1234, "type": "group"}}, "data": "ab:a:" + token})
        self.assertEqual(challenge.decision, "pending")

    def test_replacing_telegram_revokes_old_approval_and_backup_codes(self):
        remembered = self.service._remember_browser(self.user, "Owner browser")
        code = self.service._generate_recovery_codes(self.user)[0]
        token, challenge = self._challenge()
        self.service._set_identity(self.user, "telegram", "920009", "920009")
        self._decide(token)
        self.assertFalse(self.service._trusted_device(self.user, remembered))
        self.assertFalse(self.service._complete_device_login(self.user, token, self.browser, code))
        self.assertFalse(self.env["ab_storefront_auth_recovery_code"].search_count([("user_id", "=", self.user.id), ("used_at", "=", False)]))


@tagged("post_install", "-at_install")
class TestStorefrontAuthDeviceHTTP(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref("base.lang_en").active = True
        cls.env.ref("website.default_website").write({"language_ids": [(4, cls.env.ref("base.lang_en").id)], "default_lang_id": cls.env.ref("base.lang_en").id})
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("ab_storefront_auth.development", "True")
        params.set_param("ab_storefront_auth.base_url", cls.base_url())
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "HTTP device customer", "login": "http.device@example.test", "password": "Original9!Pass", "lang": "en_US",
            "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })
        cls.service = cls.env["ab_storefront_auth_service"].sudo()
        cls.service._set_identity(cls.user, "telegram", "930001", "930001")

    def setUp(self):
        super().setUp()
        self.patch(type(self.env["ab_storefront_auth_telegram"]), "_enabled", lambda _self: True)

    def _csrf(self, page):
        return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page.text).group(1)

    def _login(self):
        page = self.url_open("/web/login")
        return self.url_open("/web/login", data={"csrf_token": self._csrf(page), "login": self.user.login, "password": "Original9!Pass"})

    def _approve(self):
        challenge = self.env["ab_storefront_auth_challenge"].search([("user_id", "=", self.user.id), ("purpose", "=", "device_login")], order="id desc", limit=1)
        event = self.env["ab_storefront_auth_event"].search([("challenge_id", "=", challenge.id), ("channel", "=", "telegram")], limit=1)
        payload = json.loads(self.service._cipher().decrypt(event.payload.encode()).decode())
        data = payload["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
        self.service._process_device_callback({"from": {"id": 930001}, "message": {"chat": {"id": 930001, "type": "private"}}, "data": data})

    def test_password_only_is_pending_and_approval_sets_secure_cookie(self):
        page = self._login()
        self.assertIn("Approve browser sign-in", page.text)
        denied = self.url_open("/my/orders", allow_redirects=False)
        self.assertIn("/web/login", denied.headers.get("Location", ""))
        premature = self.url_open("/ab_storefront/auth/device", data={"csrf_token": self._csrf(page), "action": "continue"})
        self.assertIn("Sign-in has not been approved", premature.text)
        self._approve()
        allowed = self.url_open("/ab_storefront/auth/device", data={"csrf_token": self._csrf(premature), "action": "continue", "remember": "1"}, allow_redirects=False)
        self.assertEqual(allowed.status_code, 303)
        cookies = allowed.raw.headers.getlist("Set-Cookie")
        trusted = next(value for value in cookies if value.startswith(DEVICE_COOKIE + "="))
        for flag in ["Secure", "HttpOnly", "SameSite=Lax", "Max-Age=2592000"]:
            self.assertIn(flag, trusted)
        self.assertIn("Browsers and recovery codes", self.url_open("/my/authentication/browsers").text)

    def test_json_authentication_and_backend_redirect_cannot_bypass(self):
        response = self.url_open("/web/session/authenticate", json={"jsonrpc": "2.0", "method": "call", "params": {"db": self.env.cr.dbname, "login": self.user.login, "password": "Original9!Pass"}, "id": 1})
        self.assertIsNone(response.json()["result"]["uid"])
        self.assertIn("/web/login", self.url_open("/my/orders", allow_redirects=False).headers.get("Location", ""))
        page = self.url_open("/web/login?redirect=/odoo")
        login = self.url_open("/web/login?redirect=/odoo", data={"csrf_token": self._csrf(page), "login": self.user.login, "password": "Original9!Pass"})
        self.assertIn("Approve browser sign-in", login.text)

    def test_wrong_password_sends_no_approval(self):
        page = self.url_open("/web/login")
        self.url_open("/web/login", data={"csrf_token": self._csrf(page), "login": self.user.login, "password": "wrong"})
        self.assertFalse(self.env["ab_storefront_auth_challenge"].search_count([("user_id", "=", self.user.id), ("purpose", "=", "device_login")]))

    def test_remembered_browser_signs_in_without_new_approval(self):
        token = self.service._remember_browser(self.user, "Owner browser")
        self.url_open("/web/login")
        self.opener.cookies.set(DEVICE_COOKIE, token)
        page = self._login()
        self.assertIn("Browsers and recovery codes", page.text)
        self.assertFalse(self.env["ab_storefront_auth_challenge"].search_count([("user_id", "=", self.user.id), ("purpose", "=", "device_login")]))

    def test_pending_login_cannot_survive_password_change(self):
        page = self._login()
        self._approve()
        self.user.write({"password": "Replacement9!Pass"})
        response = self.url_open("/ab_storefront/auth/device", data={"csrf_token": self._csrf(page), "action": "continue"}, allow_redirects=False)
        self.assertIn("/web/login", response.headers.get("Location", ""))

    def test_device_post_requires_csrf(self):
        self._login()
        self.assertEqual(self.url_open("/ab_storefront/auth/device", data={"action": "continue"}).status_code, 400)

    def test_unverified_existing_session_cannot_generate_backup_codes(self):
        self.authenticate(self.user.login, "Original9!Pass")
        page = self.url_open("/my/authentication/browsers")
        response = self.url_open("/my/authentication/browsers", data={"csrf_token": self._csrf(page), "action": "codes", "current_password": "Original9!Pass"})
        self.assertEqual(response.status_code, 403)

    def test_recovery_login_and_management_password_confirmation(self):
        code = self.service._generate_recovery_codes(self.user)[0]
        page = self._login()
        recovered = self.url_open("/ab_storefront/auth/device", data={"csrf_token": self._csrf(page), "action": "recovery", "recovery_code": code})
        self.assertIn("Browsers and recovery codes", recovered.text)
        denied = self.url_open("/my/authentication/browsers", data={"csrf_token": self._csrf(recovered), "action": "codes", "current_password": "wrong"})
        self.assertIn("The current password is incorrect", denied.text)
        generated = self.url_open("/my/authentication/browsers", data={"csrf_token": self._csrf(denied), "action": "codes", "current_password": "Original9!Pass"})
        self.assertIn("Save your recovery codes now", generated.text)
        self.assertIn("no-store", generated.headers["Cache-Control"])
        refreshed = self.url_open("/my/authentication/browsers")
        self.assertNotIn("Save your recovery codes now", refreshed.text)

    def test_arabic_device_views(self):
        for xmlid in ["auth_device_wait", "auth_device_management"]:
            view = self.env.ref("ab_ecommerce_storefront." + xmlid)
            self.assertNotEqual(view.with_context(lang="en_US").arch_db, view.with_context(lang="ar_001").arch_db)

    def _check_device_browser(self, path, size, ready):
        self.browser_size = size
        sid = self.opener.cookies.get("session_id")
        original_ready = ChromeBrowser._wait_ready

        def use_session(login, password, browser=None):
            browser.set_cookie("session_id", sid, "/", "127.0.0.1")

        def capture(browser, condition):
            result = original_ready(browser, condition)
            if result:
                browser.take_screenshot().result(timeout=10)
            return result

        with patch.object(self, "authenticate", use_session), patch.object(ChromeBrowser, "_wait_ready", capture):
            self.browser_js(path, """
                if (document.documentElement.scrollWidth > window.innerWidth + 2) {
                    throw new Error('Browser security page overflows the viewport');
                }
                for (const input of document.querySelectorAll('input[id^="device_"]')) {
                    if (input.type !== 'hidden' && !document.querySelector('label[for="' + input.id + '"]')) {
                        throw new Error('Security input has no visible label');
                    }
                }
                console.log('test successful');
            """, ready=ready, timeout=45)

    def test_approval_browser_mobile_arabic(self):
        self._login()
        self._check_device_browser("/ar/ab_storefront/auth/device", "390x844", "Boolean(document.querySelector('#device_recovery_code'))")

    def test_browser_management_desktop(self):
        code = self.service._generate_recovery_codes(self.user)[0]
        page = self._login()
        self.url_open("/ab_storefront/auth/device", data={"csrf_token": self._csrf(page), "action": "recovery", "recovery_code": code})
        self._check_device_browser("/my/authentication/browsers", "1366x900", "Boolean(document.querySelector('#device_current_password'))")
