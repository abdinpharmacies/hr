import re
import secrets
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import ChromeBrowser, HttpCase


@tagged("post_install", "-at_install")
class TestStorefrontAuthHTTP(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        params = cls.env["ir.config_parameter"].sudo()
        params.set_param("ab_storefront_auth.development", "True")
        params.set_param("ab_storefront_auth.base_url", cls.base_url())
        params.set_param("auth_signup.reset_password", "True")
        params.set_param("auth_signup.invitation_scope", "b2c")
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "HTTP customer", "login": "http.customer@example.test", "email": "http.customer@example.test",
            "password": "Original9!Pass", "group_ids": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })

    def _csrf(self, response):
        return re.search(r'name="csrf_token"[^>]*value="([^"]+)"', response.text).group(1)

    def test_recovery_generic_response_and_csrf(self):
        page = self.url_open("/ab_storefront/auth/recover")
        self.assertEqual(page.status_code, 200)
        csrf = self._csrf(page)
        known = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": csrf, "identifier": self.user.email, "channel": "email", "action": "request"})
        missing = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": csrf, "identifier": "missing.http@example.test", "channel": "email", "action": "request"})
        self.assertEqual(known.status_code, missing.status_code)
        self.assertEqual(known.text, missing.text)
        self.assertIn("no-store", known.headers["Cache-Control"])
        rejected = self.url_open("/ab_storefront/auth/recover", data={"identifier": self.user.email})
        self.assertEqual(rejected.status_code, 400)

    def test_existing_recovery_route_uses_generic_flow(self):
        page = self.url_open("/web/reset_password")
        self.assertEqual(page.status_code, 200)
        self.assertIn("recovery_identifier", page.text)

    def test_webhook_authentication_and_deduplication(self):
        secret = secrets.token_urlsafe(32)
        service_class = type(self.env["ab_storefront_auth_telegram"])
        with patch("odoo.addons.ab_ecommerce_storefront.controllers.auth_security.deployment_secret", return_value=secret), patch.object(service_class, "_enabled", return_value=True):
            invalid = self.url_open("/ab_storefront/auth/telegram/webhook", json={"update_id": 7770001})
            self.assertEqual(invalid.status_code, 403)
            headers = {"X-Telegram-Bot-Api-Secret-Token": secret}
            for index in range(2):
                result = self.url_open("/ab_storefront/auth/telegram/webhook", json={"update_id": 7770001, "message": {"from": {"id": 910003}, "chat": {"id": 910003, "type": "private"}, "text": "/help"}}, headers=headers)
                self.assertEqual(result.status_code, 200)
            self.assertEqual(self.env["ab_storefront_auth_event"].sudo().search_count([("update_key", "=", "7770001")]), 1)

    def test_authenticated_identity_page_and_existing_password_page(self):
        self.authenticate(self.user.login, "Original9!Pass")
        self.assertEqual(self.url_open("/my/authentication").status_code, 200)
        self.assertEqual(self.url_open("/my/security").status_code, 200)
        page = self.url_open("/my/authentication")
        denied = self.url_open("/my/authentication", data={"csrf_token": self._csrf(page), "email": self.user.email, "current_password": "incorrect"})
        self.assertIn("The current password is incorrect", denied.text)

    def test_email_reset_http_round_trip(self):
        page = self.url_open("/ab_storefront/auth/recover")
        service = self.env["ab_storefront_auth_service"].sudo()
        challenge, token = service._new_challenge("email_reset", self.user, value=self.user.email, channel="email")
        grant_page = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": self._csrf(page), "action": "email", "proof": token})
        self.assertEqual(grant_page.status_code, 200)
        self.assertIn('name="action" value="password"', grant_page.text)
        reset = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": self._csrf(grant_page), "action": "password", "password": "Replacement9!Pass", "confirm_password": "Replacement9!Pass"})
        self.assertEqual(reset.status_code, 200)
        self.assertIn("Your password has been reset successfully", reset.text)
        self.authenticate(self.user.login, "Replacement9!Pass")
        self.assertEqual(self.url_open("/my/authentication").status_code, 200)

    def test_arabic_view_translation(self):
        view = self.env.ref("ab_ecommerce_storefront.auth_recovery")
        english = view.with_context(lang="en_US").arch_db
        arabic = view.with_context(lang="ar_001").arch_db
        self.assertNotEqual(english, arabic)

    def test_phone_signup_and_telegram_recovery_http(self):
        telegram = self.env["ab_storefront_auth_telegram"]
        service = self.env["ab_storefront_auth_service"].sudo()
        messages = []
        with patch.object(type(telegram), "_enabled", return_value=True), patch.object(type(telegram), "_deliver", side_effect=lambda payload: messages.append(payload)):
            page = self.url_open("/ab_storefront/auth/phone")
            linked = self.url_open("/ab_storefront/auth/phone", data={"csrf_token": self._csrf(page), "phone": "01012345678", "action": "link"})
            token = re.search(r'https://t.me/Abdin_Pharmacy_Bot\?start=([A-Za-z0-9_-]{43})', linked.text).group(1)
            sender = {"id": 910005, "language_code": "en"}
            chat = {"id": 910005, "type": "private"}
            service._process_telegram_update({"message": {"from": sender, "chat": chat, "text": "/start " + token}})
            service._process_telegram_update({"message": {"from": sender, "chat": chat, "contact": {"user_id": 910005, "phone_number": "+201012345678"}}})
            verified = self.url_open("/ab_storefront/auth/phone")
            self.assertIn("Phone verified", verified.text)
            created = self.url_open("/ab_storefront/auth/phone", data={"csrf_token": self._csrf(verified), "action": "signup", "name": "HTTP phone customer", "password": "Original9!Pass", "confirm_password": "Original9!Pass"})
            self.assertEqual(created.status_code, 200)
            self.assertIn("security_email", created.text)
            self.url_open("/web/session/logout?redirect=/web/login")
            page = self.url_open("/ab_storefront/auth/recover")
            sent = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": self._csrf(page), "action": "request", "channel": "telegram", "identifier": "01012345678"})
            service._process_queue()
            code_messages = [message for message in messages if "security code is:" in message.get("text", "")]
            self.assertEqual(len(code_messages), 1)
            code = re.search(r'\b[0-9]{6}\b', code_messages[0]["text"]).group()
            grant = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": self._csrf(sent), "action": "otp", "code": code})
            self.assertIn('name="action" value="password"', grant.text)
            reset = self.url_open("/ab_storefront/auth/recover", data={"csrf_token": self._csrf(grant), "action": "password", "password": "Replacement9!Pass", "confirm_password": "Replacement9!Pass"})
            self.assertIn("Your password has been reset successfully", reset.text)
            self.authenticate("01012345678", "Replacement9!Pass")
            self.assertEqual(self.url_open("/my/authentication").status_code, 200)

    def test_email_signup_queues_verification(self):
        page = self.url_open("/web/signup")
        signed_up = self.url_open("/web/signup", data={"csrf_token": self._csrf(page), "name": "Email signup customer", "login": "new.http@example.test", "password": "Original9!Pass", "confirm_password": "Original9!Pass"})
        self.assertEqual(signed_up.status_code, 200)
        user = self.env["res.users"].sudo().search([("login", "=", "new.http@example.test")])
        self.assertEqual(len(user), 1)
        self.assertTrue(self.env["ab_storefront_auth_event"].sudo().search([("challenge_id.user_id", "=", user.id), ("channel", "=", "email")]))

    def test_shared_signup_phone_requires_verification(self):
        telegram = self.env["ab_storefront_auth_telegram"]
        service = self.env["ab_storefront_auth_service"].sudo()
        with patch.object(type(telegram), "_enabled", return_value=True):
            page = self.url_open("/web/signup")
            linked = self.url_open("/web/signup", data={"csrf_token": self._csrf(page), "login": "01012345679", "name": "Shared signup customer"})
            self.assertEqual(linked.status_code, 200)
            self.assertIn("/ab_storefront/auth/phone", linked.url)
            token = re.search(r'https://t.me/Abdin_Pharmacy_Bot\?start=([A-Za-z0-9_-]{43})', linked.text).group(1)
            self.assertFalse(self.env["res.users"].sudo().search([("login", "=", "+201012345679")]))
            premature = self.url_open("/ab_storefront/auth/phone", data={"csrf_token": self._csrf(linked), "action": "signup", "name": "Shared signup customer", "password": "Original9!Pass", "confirm_password": "Original9!Pass"})
            self.assertIn("Complete Telegram phone verification first", premature.text)
            sender = {"id": 910006, "language_code": "en"}
            chat = {"id": 910006, "type": "private"}
            service._process_telegram_update({"message": {"from": sender, "chat": chat, "text": "/start " + token}})
            service._process_telegram_update({"message": {"from": sender, "chat": chat, "contact": {"user_id": 910006, "phone_number": "+201012345679"}}})
            verified = self.url_open("/ab_storefront/auth/phone")
            self.assertIn('value="Shared signup customer"', verified.text)
            created = self.url_open("/ab_storefront/auth/phone", data={"csrf_token": self._csrf(verified), "action": "signup", "name": "Shared signup customer", "password": "Original9!Pass", "confirm_password": "Original9!Pass"})
            self.assertEqual(created.status_code, 200)
            user = self.env["res.users"].sudo().search([("login", "=", "+201012345679")])
            self.assertEqual(len(user), 1)
            self.assertFalse(user.email)
            self.assertEqual(set(service._identities(user).mapped("kind")), {"phone", "telegram"})

    def test_shared_signup_phone_unavailable(self):
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_enabled", return_value=False):
            page = self.url_open("/web/signup")
            denied = self.url_open("/web/signup", data={"csrf_token": self._csrf(page), "login": "01012345679", "name": "Unavailable signup"})
            self.assertEqual(denied.status_code, 200)
            self.assertIn("Telegram delivery is unavailable", denied.text)
            self.assertFalse(self.env["res.users"].sudo().search([("login", "=", "+201012345679")]))

    def test_shared_signup_invalid_identity(self):
        page = self.url_open("/web/signup")
        denied = self.url_open("/web/signup", data={"csrf_token": self._csrf(page), "login": "not-a-phone", "name": "Invalid signup"})
        self.assertEqual(denied.status_code, 200)
        self.assertIn("Please enter a valid phone number", denied.text)

    def test_signup_https_guard(self):
        page = self.url_open("/web/signup")
        self.env["ir.config_parameter"].sudo().set_param("ab_storefront_auth.development", "False")
        denied = self.url_open("/web/signup", data={"csrf_token": self._csrf(page), "login": "https.guard@example.test", "name": "HTTPS signup", "password": "Original9!Pass", "confirm_password": "Original9!Pass"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.headers.get("X-Ab-Auth-Error"), "https-required")

    def test_development_loopback_alias_signup_http(self):
        host = {"Host": "127.0.0.4:5069"}
        with patch.object(type(self.env["ab_storefront_auth_telegram"]), "_enabled", return_value=True):
            page = self.url_open("/web/signup", headers=host)
            linked = self.url_open("/web/signup", headers=host, data={"csrf_token": self._csrf(page), "login": "01012345679", "name": "Loopback signup"})
            self.assertEqual(linked.status_code, 200)
            self.assertIn("https://t.me/Abdin_Pharmacy_Bot?start=", linked.text)
            self.assertNotIn('X-Ab-Auth-Error', linked.headers)

    def test_development_rejects_lan_and_spoofed_local_host(self):
        denied = self.url_open("/ab_storefront/auth/recover", headers={"Host": "192.168.1.1:5069"})
        self.assertEqual(denied.status_code, 403)
        with patch("odoo.addons.ab_ecommerce_storefront.controllers.auth_security.StorefrontAuthSecurity._ip", return_value="192.168.1.1"):
            spoofed = self.url_open("/ab_storefront/auth/recover", headers={"Host": "localhost:5069"})
            self.assertEqual(spoofed.status_code, 403)

    def _check_shared_signup_browser(self, size):
        self.browser_size = size
        self.browser_js(
            "/web/signup",
            """
            (async () => {
                const form = document.querySelector('[data-ab-auth-form="signup"]');
                const identity = form.querySelector('[data-ab-signup-identity]');
                const button = form.querySelector('[data-ab-auth-submit]');
                const fill = (name, value) => {
                    const input = form.querySelector(`[name="${name}"]`);
                    input.value = value;
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                };
                fill('name', 'Browser signup customer');
                fill('login', '01012345678');
                if (!form.querySelector('[name=password]').disabled || !form.querySelector('[data-ab-signup-credentials]').classList.contains('d-none')) {
                    throw new Error('Phone signup asks for a password before verification');
                }
                if (!form.querySelector('[data-ab-phone-signup-notice]') || !button.textContent.includes('Telegram')) {
                    throw new Error('Phone signup does not explain Telegram verification');
                }
                fill('login', 'browser.customer@example.test');
                if (form.querySelector('[name=password]').disabled) {
                    throw new Error('Email signup password is disabled');
                }
                fill('password', 'Original9!Pass');
                fill('confirm_password', 'Original9!Pass');
                const originalFetch = window.fetch;
                try {
                    for (const [status, headers] of [[503, {}], [403, {'X-Ab-Auth-Error': 'https-required'}]]) {
                        window.fetch = async () => new Response('', {status, headers});
                        button.click();
                        for (let attempt = 0; attempt < 40 && button.disabled; attempt++) {
                            await new Promise(resolve => setTimeout(resolve, 100));
                        }
                        if (button.disabled || button.classList.contains('is-loading')) {
                            throw new Error('Signup submit button remains stuck after a failed request');
                        }
                        if (!form.querySelector('.ab-auth-alert-error')) {
                            throw new Error('Signup request failure has no visible message');
                        }
                        if (status === 403 && !form.querySelector('.ab-auth-alert-error').textContent.includes('HTTPS')) {
                            throw new Error('HTTPS rejection is not explained');
                        }
                    }
                } finally {
                    window.fetch = originalFetch;
                }
                if (document.documentElement.scrollWidth > window.innerWidth + 2) {
                    throw new Error('Shared signup overflows the viewport');
                }
                console.log('test successful');
            })().catch(error => {console.error(error);});
            """,
            ready="document.querySelector('[data-ab-signup-identity]')?.dataset.abIdentityBound === 'true'",
            timeout=45,
        )

    def test_shared_signup_browser_desktop(self):
        self._check_shared_signup_browser("1366x900")

    def test_shared_signup_browser_mobile(self):
        self._check_shared_signup_browser("390x844")

    def _check_proof_browser(self, size):
        self.browser_size = size
        original_ready = ChromeBrowser._wait_ready

        def capture(browser, ready):
            result = original_ready(browser, ready)
            if result:
                browser.take_screenshot().result(timeout=10)
            return result

        with patch.object(ChromeBrowser, "_wait_ready", capture):
            self.browser_js(
                "/ab_storefront/auth/recover#" + "a" * 43,
                """
                const form = document.querySelector('[data-ab-email-proof]');
                if (form.hidden || form.querySelector('[name=proof]').value.length !== 43) {
                    throw new Error('Email proof was not transferred to the form');
                }
                if (window.location.hash || window.location.search) {
                    throw new Error('Proof remains in the browser URL');
                }
                if (document.documentElement.scrollWidth > window.innerWidth + 2) {
                    throw new Error('Authentication page overflows the viewport');
                }
                console.log('test successful');
                """,
                ready="document.querySelector('[data-ab-email-proof] input[name=proof]')?.value.length === 43",
                timeout=45,
            )

    def test_email_proof_browser_desktop(self):
        self._check_proof_browser("1366x900")

    def test_email_proof_browser_mobile(self):
        self._check_proof_browser("390x844")
