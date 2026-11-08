import json
import base64
import hashlib
import io
import secrets
from datetime import timedelta
from unittest.mock import patch

from PIL import Image

from odoo import fields
from odoo.exceptions import AccessDenied, AccessError
from odoo.tests import HttpCase, tagged, new_test_user

from ..controllers.common import ApiError, body, schema, validate
from ..controllers.docs import openapi_document


@tagged("post_install", "-at_install")
class TestEcommerceApi(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env["website"].search([], limit=1)
        cls.password = "ApiTest-2026!Strong"
        cls.customer = new_test_user(cls.env, login="api_customer_a", password=cls.password,
                                     groups="base.group_portal", company_id=cls.website.company_id.id)
        cls.other = new_test_user(cls.env, login="api_customer_b", password=cls.password,
                                  groups="base.group_portal", company_id=cls.website.company_id.id)
        cls.product = cls.env["product.template"].create({
            "name": "API Published Test Service", "type": "service", "list_price": 15,
            "sale_ok": True, "is_published": True, "website_id": cls.website.id,
            "taxes_id": [(5, 0, 0)],
        })
        cls.hidden_product = cls.env["product.template"].create({
            "name": "API Private Product", "type": "service", "list_price": 777,
            "is_published": False,
        })
        cls.sessions = cls.env["ab_ecommerce_api_session"]
        cls.session_a, cls.tokens_a = cls.sessions._issue(cls.customer, cls.website)
        cls.session_b, cls.tokens_b = cls.sessions._issue(cls.other, cls.website)
        cls.customer.partner_id.write({"street": "API Test Street", "city": "Cairo",
                                       "phone": "01000000000", "country_id": cls.env.ref("base.eg").id})

    def _request(self, path, method="GET", payload=None, token=None, expected=200, idempotency_key=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        if method == "POST" and path.split("?", 1)[0] == "/cart/items":
            headers["Idempotency-Key"] = idempotency_key or secrets.token_urlsafe(18)
        response = self.url_open("/api/v1" + path, data=json.dumps(payload) if payload is not None else None,
                                 headers=headers, method=method)
        self.assertEqual(response.status_code, expected, response.text[:1000])
        return response.json()

    def test_login_customer_and_reject_internal(self):
        response = self._request("/auth/login", "POST", {"login": self.customer.login, "password": self.password})
        self.assertIn("access_token", response["data"])
        self._request("/auth/login", "POST", {"login": self.customer.login, "password": "wrong"}, expected=401)
        with self.assertRaises(AccessDenied):
            self.sessions._issue(self.env.ref("base.user_admin"), self.website)

    def test_bearer_required_and_scope(self):
        self._request("/me", expected=401)
        self._request("/me", token="invalid", expected=401)
        result = self._request("/me", token=self.tokens_a["access_token"])
        self.assertEqual(result["data"]["id"], self.customer.id)
        self.assertNotIn("password", result["data"])

    def test_tokens_expiry_rotation_and_revocation(self):
        session, tokens = self.sessions._issue(self.customer, self.website)
        session.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        with self.assertRaises(AccessDenied):
            self.sessions._resolve(tokens["access_token"], self.website)
        rotated = self.sessions._rotate(tokens["refresh_token"], self.website)
        self.assertFalse(self.sessions._rotate(tokens["refresh_token"], self.website))
        self.assertTrue(session.revoked)
        self.assertEqual(session.revocation_reason, "refresh_reuse")
        with self.assertRaises(AccessDenied):
            self.sessions._resolve(rotated["access_token"], self.website)

    def test_refresh_token_http_reuse_revokes_rotated_access(self):
        session, tokens = self.sessions._issue(self.customer, self.website, "Replay test")
        payload = {"refresh_token": tokens["refresh_token"]}
        rotated = self._request("/auth/refresh", "POST", payload)["data"]
        self._request("/auth/refresh", "POST", payload, expected=401)
        session.invalidate_recordset()
        self.assertTrue(session.revoked)
        self.assertEqual(session.revocation_reason, "refresh_reuse")
        self._request("/me", token=rotated["access_token"], expected=401)

    def test_password_change_invalidates_tokens(self):
        self.customer.password = "DifferentPassword-2026!"
        with self.assertRaises(AccessDenied):
            self.sessions._resolve(self.tokens_a["access_token"], self.website)

    def test_tokens_not_usable_across_websites(self):
        other_site = self.website.copy({"name": "Other API Website", "domain": "https://other-api.invalid"})
        with self.assertRaises(AccessDenied):
            self.sessions._resolve(self.tokens_a["access_token"], other_site)

    def test_session_model_is_not_public_rpc(self):
        for user in (self.customer, self.website.user_id):
            with self.assertRaises(AccessError):
                self.session_a.with_user(user).read(["refresh_hash"])
            with self.assertRaises(AccessError):
                self.session_a.with_user(user).write({"user_id": user.id})
            for model_name in (
                    "ab_ecommerce_api_refresh_token",
                    "ab_ecommerce_api_idempotency",
                    "ab_ecommerce_api_browser_grant"):
                with self.assertRaises(AccessError):
                    self.env[model_name].with_user(user).search([])

    def test_published_catalog_and_pagination(self):
        self._request(f"/products/{self.hidden_product.id}", expected=404)
        result = self._request(f"/products/{self.product.id}")
        self.assertEqual(result["data"]["id"], self.product.id)
        self.assertNotIn("standard_price", result["data"])
        self._request("/products?limit=10000", expected=400)
        self._request("/products?domain=[]", expected=400)

    def test_cart_server_prices_and_line_ownership(self):
        token = self.tokens_a["access_token"]
        result = self._request("/cart/items", "POST", {"product_id": self.product.product_variant_id.id, "quantity": 2}, token)
        cart = result["data"]
        self.assertEqual(cart["lines"][0]["quantity"], 2)
        self.assertEqual(cart["lines"][0]["unit_price"], 15)
        self._request("/cart/items", "POST", {"product_id": self.product.product_variant_id.id, "quantity": 1, "price_unit": 0}, token, expected=400)
        self._request(f"/orders/{cart['id']}", token=self.tokens_b["access_token"], expected=404)
        self._request(f"/cart/items/{cart['lines'][0]['id']}", "PUT", {"quantity": 999}, self.tokens_b["access_token"], expected=404)
        updated = self._request(f"/cart/items/{cart['lines'][0]['id']}", "PUT", {"quantity": 3}, token)
        self.assertEqual(updated["data"]["lines"][0]["quantity"], 3)

    def test_cart_add_idempotency_prevents_duplicate_quantity(self):
        token = self.tokens_a["access_token"]
        key = "cart-replay-key-2026"
        payload = {"product_id": self.product.product_variant_id.id, "quantity": 2}
        first = self._request("/cart/items", "POST", payload, token, idempotency_key=key)
        second = self._request("/cart/items", "POST", payload, token, idempotency_key=key)
        self.assertEqual(first["data"], second["data"])
        self.assertEqual(second["data"]["lines"][0]["quantity"], 2)
        self._request("/cart/items", "POST", dict(payload, quantity=3), token,
                      expected=409, idempotency_key=key)

    def test_address_ownership(self):
        address = self.env["res.partner"].create({"name": "Other address", "parent_id": self.other.partner_id.id, "type": "delivery"})
        self._request("/cart/address", "PUT", {"address_id": address.id}, self.tokens_a["access_token"], expected=404)

    def test_wishlist_history(self):
        token = self.tokens_a["access_token"]
        self._request(f"/wishlist/{self.product.product_variant_id.id}", "PUT", {}, token)
        result = self._request("/wishlist", token=token)
        self.assertIn(self.product.id, [item["id"] for item in result["data"]["items"]])
        self._request(f"/history/{self.product.id}", "PUT", {}, token)
        self.assertEqual(self._request("/history", token=token)["data"][0]["id"], self.product.id)
        self.assertEqual(self._request("/history", token=self.tokens_b["access_token"])["data"], [])

    def test_prescription_and_invoice_idor(self):
        token = self.tokens_a["access_token"]
        self._request("/prescriptions/999999/image", token=token, expected=404)
        self._request("/orders/999999/invoices/999999/pdf", token=token, expected=404)
        self._request("/prescriptions", "GET", token=token)

    def test_strict_input_validation(self):
        definition = body({"quantity": schema("number", minimum=0, maximum=100)}, ("quantity",))
        for value in ({}, {"quantity": True}, {"quantity": float("nan")}, {"quantity": -1}, {"quantity": 1, "sudo": True}):
            with self.assertRaises(ApiError):
                validate(value, definition)

    def test_openapi_operations_match_routes(self):
        document = openapi_document()
        self.assertEqual(document["openapi"], "3.0.3")
        self.assertGreaterEqual(len(document["paths"]), 35)
        self.assertEqual(sum(len(operations) for operations in document["paths"].values()), 62)
        self.assertEqual(document["paths"]["/me"]["get"]["security"], [{"customerToken": []}])
        self.assertEqual(document["paths"]["/auth/login"]["post"]["security"], [])
        session_parameter = document["paths"]["/auth/sessions/{session_id}"]["delete"]["parameters"][0]
        self.assertEqual(session_parameter["schema"]["type"], "string")
        cart_parameters = document["paths"]["/cart/items"]["post"]["parameters"]
        self.assertTrue(any(parameter["name"] == "Idempotency-Key" for parameter in cart_parameters))

    def test_arabic_error(self):
        english = self._request("/me?lang=en", expected=401)
        arabic = self._request("/me?lang=ar", expected=401)
        if "ar_001" in dict(self.env["res.lang"].get_installed()):
            self.assertNotEqual(english["error"]["message"], arabic["error"]["message"])

    def test_cart_checkout_payment_idempotency(self):
        provider = self.env.ref("payment.payment_provider_transfer")
        provider.write({"state": "test", "is_published": True, "website_id": self.website.id})
        method = provider.payment_method_ids[:1]
        method.active = True
        token = self.tokens_a["access_token"]
        self._request("/cart/items", "POST", {"product_id": self.product.product_variant_id.id, "quantity": 1}, token)
        options = self._request("/cart/payment-methods", token=token)["data"]
        self.assertIn(provider.id, [option["provider_id"] for option in options])
        checkout = self._request("/cart/checkout", "POST", {}, token)["data"]
        values = {"idempotency_key": checkout["idempotency_key"], "provider_id": provider.id,
                  "payment_method_id": method.id}
        order_id = checkout["order"]["id"]
        first = self._request(f"/orders/{order_id}/payment", "POST", values, token)["data"]
        second = self._request(f"/orders/{order_id}/payment", "POST", values, token)["data"]
        self.assertEqual(first["processing"]["reference"], second["processing"]["reference"])
        self.assertEqual(self.env["payment.transaction"].search_count([("sale_order_ids", "in", [order_id])]), 1)
        self._request(f"/orders/{order_id}/payment", "POST", values, self.tokens_b["access_token"], expected=404)

    def test_cart_rejects_unpublished_and_negative_quantity(self):
        token = self.tokens_a["access_token"]
        self._request("/cart/items", "POST", {"product_id": self.hidden_product.product_variant_id.id, "quantity": 1}, token, expected=404)
        self._request("/cart/items", "POST", {"product_id": self.product.product_variant_id.id, "quantity": -1}, token, expected=400)

    def test_cross_company_order_denied(self):
        company = self.env["res.company"].create({"name": "API Other Company"})
        order = self.env["sale.order"].with_company(company).create({
            "partner_id": self.customer.partner_id.id, "company_id": company.id})
        self._request(f"/orders/{order.id}", token=self.tokens_a["access_token"], expected=404)

    def test_home_and_content(self):
        for path in ("/config", "/home", "/brands", "/categories", "/branches", "/pages", "/countries", "/offers"):
            with self.subTest(path=path):
                self._request(path)

    def test_mfa_cannot_be_bypassed(self):
        with patch.object(type(self.env["res.users"]), "_mfa_url", return_value="/web/login/totp"):
            self._request("/auth/login", "POST", {"login": self.customer.login, "password": self.password}, expected=403)

    def test_rate_limit(self):
        with patch.object(type(self.env["ab_storefront_auth_service"]), "_rate_allow", return_value=False):
            self._request("/config", expected=429)

    def test_rate_limit_runs_before_bearer_lookup(self):
        events = []

        def allow(service, *args, **kwargs):
            events.append("rate")
            return True

        def resolve(sessions, *args, **kwargs):
            events.append("resolve")
            raise AccessDenied()

        with patch.object(type(self.env["ab_storefront_auth_service"]), "_rate_allow", allow), \
                patch.object(type(self.sessions), "_resolve", resolve):
            self._request("/me", token="x" * 43, expected=401)
        self.assertEqual(events, ["rate", "resolve"])

    def test_rate_limit_database_query_cost_is_bounded(self):
        service = self.env["ab_storefront_auth_service"]
        action = "mobile-api:query-cost:" + secrets.token_hex(8)
        start = self.env.cr.sql_log_count
        self.assertTrue(service._rate_allow(action, "127.0.0.1", 10, 60))
        cold_queries = self.env.cr.sql_log_count - start
        start = self.env.cr.sql_log_count
        self.assertTrue(service._rate_allow(action, "127.0.0.1", 10, 60))
        warm_queries = self.env.cr.sql_log_count - start
        self.assertLessEqual(cold_queries, 8, f"cold rate-limit queries: {cold_queries}")
        self.assertLessEqual(warm_queries, 3, f"warm rate-limit queries: {warm_queries}")

    def test_logout_revokes_http_token(self):
        token = self.tokens_a["access_token"]
        self._request("/auth/logout", "POST", {}, token)
        self._request("/me", token=token, expected=401)

    def test_device_session_management_is_owner_scoped(self):
        other_session, other_tokens = self.sessions._issue(self.customer, self.website, "Tablet")
        sessions = self._request("/auth/sessions", token=self.tokens_a["access_token"])["data"]
        self.assertIn(other_session._public_id(), [session["id"] for session in sessions])
        self.assertEqual(sum(session["current"] for session in sessions), 1)
        self._request(f"/auth/sessions/{other_session._public_id()}", "DELETE",
                      token=self.tokens_a["access_token"])
        other_session.invalidate_recordset()
        self.assertTrue(other_session.revoked)
        self._request("/me", token=other_tokens["access_token"], expected=401)
        self._request(f"/auth/sessions/{self.session_b._public_id()}", "DELETE",
                      token=self.tokens_a["access_token"], expected=404)
        result = self._request("/auth/logout-all", "POST", {}, self.tokens_a["access_token"])
        self.assertGreaterEqual(result["data"]["revoked"], 1)
        self._request("/me", token=self.tokens_a["access_token"], expected=401)

    def test_active_device_sessions_are_bounded(self):
        for sequence in range(21):
            self.sessions._issue(self.customer, self.website, f"Device {sequence}")
        active_sessions = self.sessions.sudo().search_count([
            ("user_id", "=", self.customer.id),
            ("website_id", "=", self.website.id),
            ("revoked", "=", False),
            ("refresh_expires_at", ">", fields.Datetime.now()),
        ])
        self.assertEqual(active_sessions, 20)

    def test_expired_api_security_records_are_cleaned(self):
        old = fields.Datetime.now() - timedelta(days=8)
        session, _tokens = self.sessions._issue(self.customer, self.website, "Expired")
        session.write({"revoked": True, "revoked_at": old, "refresh_expires_at": old})
        history_session, history_tokens = self.sessions._issue(self.customer, self.website, "History")
        self.sessions._rotate(history_tokens["refresh_token"], self.website)
        history = self.env["ab_ecommerce_api_refresh_token"].sudo().search([
            ("session_id", "=", history_session.id),
        ], limit=1)
        history.expires_at = old
        idempotency = self.env["ab_ecommerce_api_idempotency"].sudo().create({
            "session_id": self.session_a.id,
            "operation": "cleanup-test",
            "key_hash": self.sessions._hash("cleanup-key"),
            "request_hash": self.sessions._hash("cleanup-request"),
            "expires_at": old,
        })
        grant = self.env["ab_ecommerce_api_browser_grant"].sudo().create({
            "token_hash": self.sessions._hash(secrets.token_urlsafe(32)),
            "code_challenge": "z" * 43,
            "website_id": self.website.id,
            "expires_at": old,
        })
        self.env["ab_ecommerce_api_refresh_token"]._gc_refresh_tokens()
        self.env["ab_ecommerce_api_idempotency"]._gc_idempotency()
        self.sessions._gc_sessions()
        self.env["ab_ecommerce_api_browser_grant"]._gc_browser_grants()
        self.assertFalse(session.exists())
        self.assertFalse(history.exists())
        self.assertFalse(idempotency.exists())
        self.assertFalse(grant.exists())

    def test_cookie_cannot_authorize_api(self):
        self.authenticate(self.customer.login, self.password)
        self._request("/me", expected=401)

    def test_docs_restricted_to_admin(self):
        self.authenticate(self.customer.login, self.password)
        self.assertEqual(self.url_open("/api/v1/openapi.json").status_code, 403)

    def test_browser_pkce_single_use_and_scope(self):
        verifier = "a" * 43
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        grants = self.env["ab_ecommerce_api_browser_grant"]
        flow = grants._start(challenge, self.website)
        self.assertTrue(grants._exchange(flow, verifier, self.website)["authorization_pending"])
        with self.assertRaises(AccessDenied):
            grants._exchange(flow, "b" * 43, self.website)
        grants._approve(flow, self.website, self.customer)
        with self.assertRaises(AccessDenied):
            grants._approve(flow, self.website, self.other)
        tokens = grants._exchange(flow, verifier, self.website)
        self.assertEqual(self.sessions._resolve(tokens["access_token"], self.website).user_id, self.customer)
        with self.assertRaises(AccessDenied):
            grants._exchange(flow, verifier, self.website)
        with self.assertRaises(AccessError):
            grants.with_user(self.customer).search([])

    def test_browser_api_and_csrf(self):
        verifier = "c" * 43
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        start = self._request("/auth/browser/start", "POST", {"code_challenge": challenge})["data"]
        exchange = {"flow_token": start["flow_token"], "code_verifier": verifier}
        self.assertTrue(self._request("/auth/browser/token", "POST", exchange)["data"]["authorization_pending"])
        self.authenticate(self.customer.login, self.password)
        response = self.url_open(start["authorization_url"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.url_open(start["authorization_url"], data={}, method="POST").status_code, 400)

    def test_stock_quantity_not_bypassed(self):
        product = self.env["product.template"].create({"name": "API Unavailable Stock", "type": "consu",
            "is_storable": True, "allow_out_of_stock_order": False, "is_published": True,
            "website_id": self.website.id, "list_price": 10})
        response = self.url_open("/api/v1/cart/items", json={"product_id": product.product_variant_id.id, "quantity": 1},
                                 headers={"Authorization": "Bearer " + self.tokens_a["access_token"],
                                          "Idempotency-Key": secrets.token_urlsafe(18)}, method="POST")
        self.assertIn(response.status_code, (200, 422))
        if response.status_code == 200:
            self.assertFalse(any(line["quantity"] > 0 for line in response.json()["data"]["lines"]))

    def test_payment_foreign_method_and_rollback(self):
        token = self.tokens_a["access_token"]
        cart = self._request("/cart/items", "POST", {"product_id": self.product.product_variant_id.id, "quantity": 1}, token)["data"]
        self._request(f"/orders/{cart['id']}/payment", "POST", {"idempotency_key": "unknown", "provider_id": 999999,
                                                               "payment_method_id": 999999}, token, expected=400)
        self.assertEqual(self.env["payment.transaction"].search_count([("sale_order_ids", "in", [cart["id"]])]), 0)

    def test_prescription_upload_replay_and_private_image(self):
        provider = self.env.ref("payment.payment_provider_transfer")
        provider.write({"state": "test", "custom_mode": "cash_on_delivery"})
        method = self.env["payment.method"].search([("code", "=", "cash_on_delivery")], limit=1)
        method.active = True
        provider.payment_method_ids = method
        self.customer.partner_id.state_id = self.env["res.country.state"].search([
            ("country_id", "=", self.env.ref("base.eg").id)], limit=1)
        token = self.tokens_a["access_token"]
        key = self._request("/prescriptions/submission", "POST", {}, token)["data"]["idempotency_key"]
        image = io.BytesIO()
        Image.new("RGB", (4, 4)).save(image, "PNG")
        image_data = image.getvalue()
        form = {"idempotency_key": key, "address_id": self.customer.partner_id.id, "customer_note": "Test upload"}
        headers = {"Authorization": "Bearer " + token}
        first = self.url_open("/api/v1/prescriptions", data=form,
                              files={"prescription_image": ("prescription.png", image_data, "image/png")}, headers=headers, method="POST")
        self.assertEqual(first.status_code, 201, first.text[:1000])
        second = self.url_open("/api/v1/prescriptions", data=form,
                               files={"prescription_image": ("prescription.png", image_data, "image/png")}, headers=headers, method="POST")
        self.assertEqual(second.status_code, 201, second.text[:1000])
        self.assertEqual(first.json()["data"]["id"], second.json()["data"]["id"])
        image_url = first.json()["data"]["image_url"]
        self.assertEqual(self.url_open(image_url, headers=headers).content, image_data)
        self._request(image_url.removeprefix("/api/v1"), token=self.tokens_b["access_token"], expected=404)
        form["customer_note"] = "Changed replay"
        changed = self.url_open("/api/v1/prescriptions", data=form,
                                files={"prescription_image": ("prescription.png", image_data, "image/png")}, headers=headers, method="POST")
        self.assertEqual(changed.status_code, 422)

    def test_coupon_updates_server_total(self):
        program = self.env["loyalty.program"].create({
            "name": "API Test Discount", "program_type": "promo_code", "trigger": "with_code",
            "applies_on": "current", "company_id": self.website.company_id.id,
            "website_id": self.website.id, "currency_id": self.website.currency_id.id,
            "rule_ids": [(0, 0, {"mode": "with_code", "code": "API-TEST-10", "minimum_qty": 1,
                                  "reward_point_amount": 1, "reward_point_mode": "order"})],
            "reward_ids": [(0, 0, {"reward_type": "discount", "discount_mode": "percent",
                                    "discount": 10, "discount_applicability": "order", "required_points": 1})],
        })
        token = self.tokens_a["access_token"]
        cart = self._request("/cart/items", "POST", {"product_id": self.product.product_variant_id.id, "quantity": 2}, token)["data"]
        discounted = self._request("/cart/coupon", "POST", {"code": "API-TEST-10"}, token)["data"]
        self.assertLess(discounted["total"], cart["total"])
        self.assertTrue(any(line["is_reward"] for line in discounted["lines"]))
