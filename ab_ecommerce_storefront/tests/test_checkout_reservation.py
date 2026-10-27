import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import HttpCase, TransactionCase
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.website_sale.tests.common import MockRequest

from ..controllers.checkout_submission import StorefrontPaymentPortal
from ..controllers.payment_status import StorefrontPaymentPostProcessing
from ..controllers.prescription_order import AbPrescriptionOrderPortal
from ..controllers.shop import AbEcommerceStorefrontShop
from ..controllers.submission_security import submission_owner


@tagged("post_install", "-at_install")
class TestStorefrontReservations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.company = cls.website.company_id
        cls.warehouse = cls.env["stock.warehouse"].create({
            "name": "Reservation tests", "code": "RSH", "company_id": cls.company.id,
        })
        cls.website.warehouse_id = cls.warehouse
        cls.warehouse.out_type_id.reservation_method = "at_confirm"
        cls.partner = cls.env["res.partner"].create({"name": "Reservation customer"})
        cls.product = cls.env["product.product"].create({
            "name": "Reservation product", "type": "consu", "is_storable": True,
            "is_published": True, "list_price": 10, "allow_out_of_stock_order": False,
            "company_id": cls.company.id, "taxes_id": [Command.clear()],
        })
        cls.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": cls.product.id, "location_id": cls.warehouse.lot_stock_id.id,
            "inventory_quantity": 2,
        }).action_apply_inventory()
        cls.submissions = cls.env["ab_storefront_submission"]

    def cart(self):
        return self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "warehouse_id": self.warehouse.id,
        })

    def available(self):
        return self.website._get_product_available_qty(self.product)

    def link_eplus_stock(self):
        source = self.env["ab_product"].create({"name": "External stock", "code": "HOLD-EXTERNAL-TEST"})
        self.product.product_tmpl_id.write({"ab_product_id": source.id, "eplus_stock_shown_qty_value": 10})
        self.env["ab_eplus_stock_snapshot"].create({
            "itm_id": -15152026, "product_id": source.id, "itm_qty": 10,
        })

    def completed_eplus_sync(self, warehouse=None, state="done"):
        warehouse = warehouse or self.warehouse
        job = self.env["ab_eplus_inventory_sync_job"].create({
            "state": state, "warehouse_id": warehouse.id,
            "location_id": warehouse.lot_stock_id.id, "total_count": 1,
            "processed_count": 1, "date_done": fields.Datetime.now(),
        })
        self.env["ab_eplus_inventory_sync_job_line"].create({
            "job_id": job.id, "product_product_id": self.product.id,
            "target_qty": 2, "state": "unchanged",
        })
        return job

    def test_other_cart_cannot_take_held_stock(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 2)
        self.assertEqual(self.available(), 0)
        self.assertEqual(cart._get_free_qty(self.product), 2)
        other = self.cart()
        result = other._cart_add(self.product.id, 1)
        self.assertEqual(result["quantity"], 0)
        self.assertFalse(other.order_line)

    def test_expiry_releases_without_cron_or_inventory_write(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 2)
        holds = self.env["ab_storefront_cart_hold"].search([("order_id", "=", cart.id)])
        holds.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        self.assertEqual(self.available(), 2)
        self.assertEqual(cart.order_line.product_uom_qty, 2)
        product = self.product.with_context(warehouse_id=self.warehouse.id)
        self.assertEqual(product.qty_available, 2)
        self.assertEqual(product.free_qty, 2)

    def test_delete_releases_and_edits_do_not_extend_deadline(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        deadline = cart.ab_cart_hold_expires_at
        cart._cart_add(self.product.id, 1)
        self.assertEqual(cart.ab_cart_hold_expires_at, deadline)
        cart._cart_update_line_quantity(cart.order_line.id, 0)
        self.assertEqual(self.available(), 2)
        self.assertFalse(cart.ab_cart_hold_expires_at)

    def test_native_confirmation_does_not_double_deduct(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 2)
        cart.action_confirm()
        self.assertEqual(cart.state, "sale")
        self.assertEqual(self.available(), 0)
        self.assertEqual(self.product.with_context(warehouse_id=self.warehouse.id).qty_available, 2)
        cart.with_context(disable_cancel_warning=True).action_cancel()
        self.assertEqual(self.available(), 2)

    def test_external_stock_cannot_confirm_without_reservation(self):
        self.link_eplus_stock()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            cart._check_cart_is_ready_to_be_paid()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            cart.action_confirm()
        self.assertEqual(cart.state, "draft")

    def test_completed_eplus_sync_uses_odoo_stock_for_reservation(self):
        self.link_eplus_stock()
        self.completed_eplus_sync()
        cart = self.cart()
        cart._cart_add(self.product.id, 2)
        self.assertEqual(cart._get_free_qty(self.product), 2)
        self.assertEqual(self.available(), 0)
        other = self.cart()
        self.assertEqual(other._cart_add(self.product.id, 1)["quantity"], 0)
        cart.action_confirm()
        self.assertEqual(cart.state, "sale")
        self.assertTrue(cart.picking_ids.move_ids)
        self.assertTrue(all(move.state == "assigned" for move in cart.picking_ids.move_ids))
        self.assertEqual(self.product.with_context(warehouse_id=self.warehouse.id).free_qty, 0)

    def test_failed_eplus_sync_does_not_authorize_checkout(self):
        self.link_eplus_stock()
        self.completed_eplus_sync()
        self.completed_eplus_sync(state="failed")
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            cart._check_cart_is_ready_to_be_paid()
        self.assertEqual(cart.state, "draft")

    def test_other_warehouse_eplus_sync_does_not_authorize_checkout(self):
        self.link_eplus_stock()
        other = self.env["stock.warehouse"].create({
            "name": "Other sync warehouse", "code": "RSO", "company_id": self.company.id,
        })
        self.completed_eplus_sync(warehouse=other)
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            cart._check_cart_is_ready_to_be_paid()
        self.assertEqual(cart.state, "draft")

    def test_read_only_availability_does_not_renew(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        expiry = cart.ab_cart_hold_expires_at
        self.available()
        self.available()
        self.assertEqual(cart.ab_cart_hold_expires_at, expiry)

    def test_company_and_warehouse_holds_are_isolated(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        other = self.env["stock.warehouse"].create({
            "name": "Other reservation tests", "code": "RSO", "company_id": self.company.id,
        })
        held = self.env["ab_storefront_cart_hold"]._quantities(self.product, self.company, other)
        self.assertFalse(held)

    def test_native_cart_uses_its_warehouse_when_website_has_no_warehouse(self):
        self.website.warehouse_id = False
        other = self.env["stock.warehouse"].create({
            "name": "Other native cart stock", "code": "RNN", "company_id": self.company.id,
        })
        self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": self.product.id, "location_id": other.lot_stock_id.id,
            "inventory_quantity": 10,
        }).action_apply_inventory()
        self.assertEqual(self.cart()._get_free_qty(self.product), 2)

    def test_public_cannot_read_or_change_holds_or_submissions(self):
        public = self.website.user_id
        for name in ("ab_storefront_cart_hold", "ab_storefront_submission"):
            with self.assertRaises(AccessError):
                self.env[name].with_user(public).search([])
            with self.assertRaises(AccessError):
                self.env[name].with_user(public).create({})

    def test_catalog_uses_fallback_warehouse_and_expires_holds(self):
        self.website.warehouse_id = False
        self.env["ir.default"].set(
            "sale.order", "warehouse_id", self.warehouse.id, company_id=self.company.id,
        )
        cart = self.cart()
        cart._cart_add(self.product.id, 2)
        with MockRequest(self.env, website=self.website):
            visible = AbEcommerceStorefrontShop()._ab_storefront_available_products(
                self.product.product_tmpl_id, self.website,
            )
            self.assertFalse(visible)
            self.env["ab_storefront_cart_hold"].search([("order_id", "=", cart.id)]).expires_at = (
                fields.Datetime.now() - timedelta(seconds=1)
            )
            visible = AbEcommerceStorefrontShop()._ab_storefront_available_products(
                self.product.product_tmpl_id, self.website,
            )
            self.assertEqual(visible, self.product.product_tmpl_id)

    def test_same_key_same_payload_reuses_submission(self):
        submission = self.submissions._issue("prescription", self.website, "owner")
        first = self.submissions._claim(submission.key, "prescription", self.website, "owner", {"image": "hash"})
        second = self.submissions._claim(submission.key, "prescription", self.website, "owner", {"image": "hash"})
        self.assertEqual(first, second)

    def test_key_rejects_changed_payload_owner_and_kind(self):
        submission = self.submissions._issue("prescription", self.website, "owner")
        self.submissions._claim(submission.key, "prescription", self.website, "owner", {"image": "a"})
        with self.assertRaises(ValidationError):
            self.submissions._claim(submission.key, "prescription", self.website, "owner", {"image": "b"})
        with self.assertRaises(AccessError):
            self.submissions._claim(submission.key, "prescription", self.website, "other", {"image": "a"})
        with self.assertRaises(AccessError):
            self.submissions._claim(submission.key, "checkout", self.website, "owner", {"image": "a"})

    def test_unused_expired_key_is_rejected(self):
        submission = self.submissions._issue("prescription", self.website, "owner")
        submission.expires_at = fields.Datetime.now() - timedelta(seconds=1)
        with self.assertRaises(ValidationError):
            self.submissions._claim(submission.key, "prescription", self.website, "owner", {})

    def test_direct_confirmation_write_cannot_bypass_reservation(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            cart.with_context(ab_confirmation_token=True).write({"state": "sale"})
        self.assertEqual(cart.state, "draft")

    def test_cart_hold_quantities_use_product_units(self):
        quant = self.env["stock.quant"].search([
            ("product_id", "=", self.product.id), ("location_id", "=", self.warehouse.lot_stock_id.id),
        ], limit=1)
        quant.with_context(inventory_mode=True).inventory_quantity = 12
        quant.action_apply_inventory()
        cart = self.cart()
        cart._cart_add(self.product.id, 1, uom_id=self.env.ref("uom.product_uom_pack_6").id)
        self.assertEqual(self.available(), 6)
        self.assertEqual(cart.order_line.product_uom_qty, 1)

    def test_prescription_cannot_confirm_without_identified_items(self):
        prescription = self.env["ab.prescription.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "prescription_image": base64.b64encode(b"review-test"),
        })
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            prescription.action_confirmed()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            prescription.write({"state": "confirmed"})

    def test_cart_hold_view_has_arabic_translation(self):
        view = self.env.ref("ab_ecommerce_storefront.cart_hold_notice")
        english = view.with_context(lang="en_US").arch_db
        arabic = view.with_context(lang="ar_001").arch_db
        self.assertIn("Items in your cart are temporarily reserved", english)
        self.assertIn("تم حجز الكمية في سلتك مؤقتًا", arabic)
        self.assertNotEqual(english, arabic)

    def test_prescription_retry_creates_one_request_and_order(self):
        controller = AbPrescriptionOrderPortal()
        method = self.env["payment.method"].search([("code", "=", "cash_on_delivery")], limit=1)
        self.assertTrue(method)
        with MockRequest(self.env, website=self.website):
            submission = self.submissions._issue("prescription", self.website, submission_owner())
            with patch.object(controller, "_read_prescription_upload", return_value={
                "prescription_image": base64.b64encode(b"reservation-test"),
                "prescription_filename": "test.png", "prescription_mimetype": "image/png",
            }), patch.object(controller, "_prescription_partner_values", return_value={
                "partner_id": self.partner.id, "user_id": self.env.uid,
            }), patch.object(type(self.env["ab.prescription.order"]), "_ab_storefront_cash_on_delivery_method", return_value=method):
                first = controller.prescription_order_submit(idempotency_key=submission.key)
                second = controller.prescription_order_submit(idempotency_key=submission.key)
            self.assertEqual(first.location, second.location)
            self.assertTrue(submission.prescription_id)
            self.assertEqual(submission.order_id, submission.prescription_id.sale_order_id)
            self.assertEqual(self.env["sale.order"].search_count([("origin", "=", submission.prescription_id.name)]), 1)

    def test_checkout_replay_checks_ownership(self):
        cart = self.cart()
        cart._portal_ensure_token()
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            with self.assertRaises(AccessError):
                StorefrontPaymentPortal().shop_payment_transaction(cart.id, cart.access_token)

    def test_checkout_retry_creates_one_transaction(self):
        cart = self.cart()
        cart.partner_id = self.env.user.partner_id
        cart.carrier_id = self.env.ref("delivery.free_delivery_carrier")
        cart.carrier_id.website_published = True
        cart._cart_add(self.product.id, 1)
        cart._portal_ensure_token()
        provider = self.env["payment.provider"].search([
            ("code", "=", "custom"), ("custom_mode", "=", "cash_on_delivery"),
            ("company_id", "=", self.company.id),
        ], limit=1)
        self.assertTrue(provider)
        method = self.env["payment.method"].search([("code", "=", "cash_on_delivery")], limit=1)
        provider.payment_method_ids = method
        self.assertTrue(method)
        payload = {
            "provider_id": provider.id, "payment_method_id": method.id,
            "token_id": None, "amount": cart.amount_total, "flow": "redirect",
            "tokenization_requested": False, "landing_route": "/shop/payment/validate",
        }
        controller = StorefrontPaymentPortal()
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            first = controller.shop_payment_transaction(cart.id, cart.access_token, **payload)
            second = controller.shop_payment_transaction(cart.id, cart.access_token, **payload)
        self.assertEqual(first, second)
        self.assertEqual(len(cart.transaction_ids), 1)
        self.assertEqual(cart.ab_checkout_submission_id.transaction_id, cart.transaction_ids)

    def test_cash_on_delivery_post_processing_confirms_and_reserves_once(self):
        cart = self.cart()
        cart.partner_id = self.env.user.partner_id
        cart.carrier_id = self.env.ref("delivery.free_delivery_carrier")
        cart.carrier_id.website_published = True
        cart._cart_add(self.product.id, 1)
        cart._portal_ensure_token()
        provider = self.env["payment.provider"].search([
            ("code", "=", "custom"), ("custom_mode", "=", "cash_on_delivery"),
            ("company_id", "=", self.company.id),
        ], limit=1)
        method = self.env["payment.method"].search([("code", "=", "cash_on_delivery")], limit=1)
        provider.payment_method_ids = method
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            StorefrontPaymentPortal().shop_payment_transaction(
                cart.id, cart.access_token,
                provider_id=provider.id, payment_method_id=method.id,
                token_id=None, amount=cart.amount_total, flow="redirect",
                tokenization_requested=False, landing_route="/shop/payment/validate",
            )
        transaction = cart.transaction_ids
        transaction._set_pending()
        self.assertEqual(cart.state, "draft")
        with MockRequest(self.env, website=self.website) as request, patch.object(
            PaymentPostProcessing, "display_status", return_value="status page",
        ):
            request.session["__payment_monitored_tx_id__"] = transaction.id
            status = StorefrontPaymentPostProcessing.display_status.original_endpoint(
                StorefrontPaymentPostProcessing(),
            )
            self.assertEqual(status, "status page")
        self.assertEqual(cart.state, "sale")
        self.assertTrue(transaction.is_post_processed)
        self.assertEqual(transaction.state, "pending")
        self.assertTrue(cart.picking_ids.move_ids)
        self.assertTrue(all(move.state == "assigned" for move in cart.picking_ids.move_ids))
        self.assertEqual(self.product.with_context(warehouse_id=self.warehouse.id).qty_available, 2)
        self.assertEqual(self.product.with_context(warehouse_id=self.warehouse.id).free_qty, 1)
        transaction._post_process()
        self.assertEqual(len(cart.picking_ids), 1)
        self.assertEqual(self.product.with_context(warehouse_id=self.warehouse.id).free_qty, 1)

    def test_cash_on_delivery_rejects_changed_amount_before_confirmation(self):
        cart = self.cart()
        cart.partner_id = self.env.user.partner_id
        cart.carrier_id = self.env.ref("delivery.free_delivery_carrier")
        cart.carrier_id.website_published = True
        cart._cart_add(self.product.id, 1)
        cart._portal_ensure_token()
        provider = self.env["payment.provider"].search([
            ("code", "=", "custom"), ("custom_mode", "=", "cash_on_delivery"),
            ("company_id", "=", self.company.id),
        ], limit=1)
        method = self.env["payment.method"].search([("code", "=", "cash_on_delivery")], limit=1)
        provider.payment_method_ids = method
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            StorefrontPaymentPortal().shop_payment_transaction(
                cart.id, cart.access_token,
                provider_id=provider.id, payment_method_id=method.id,
                token_id=None, amount=cart.amount_total, flow="redirect",
                tokenization_requested=False, landing_route="/shop/payment/validate",
            )
        transaction = cart.transaction_ids
        transaction._set_pending()
        cart.order_line.price_unit += 1
        with MockRequest(self.env, website=self.website) as request, patch.object(
            request, "render", return_value="failed status",
        ) as render:
            request.session["__payment_monitored_tx_id__"] = transaction.id
            poll = StorefrontPaymentPostProcessing.poll_status.original_endpoint(
                StorefrontPaymentPostProcessing(),
            )
            self.assertEqual(poll, {
                "provider_code": "custom", "state": "error", "landing_route": "/payment/status",
            })
            status = StorefrontPaymentPostProcessing.display_status.original_endpoint(
                StorefrontPaymentPostProcessing(),
            )
            self.assertEqual(status.get_data(as_text=True), "failed status")
            self.assertEqual(render.call_args.args[0], "payment.payment_status")
            self.assertEqual(render.call_args.args[1]["tx"], transaction)
        self.assertEqual(cart.state, "draft")
        self.assertFalse(cart.picking_ids)
        self.assertEqual(transaction.state, "error")


@tagged("post_install", "-at_install")
class TestStorefrontCartHoldHTTP(HttpCase):
    def _browser_in_current_session(self, *args, **kwargs):
        with patch.object(self, "authenticate", return_value=self.session):
            self.browser_js(*args, **kwargs)

    def test_guest_cart_countdown_and_expiration(self):
        website = self.env.ref("website.default_website")
        warehouse = self.env["stock.warehouse"].create({
            "name": "HTTP reservation tests", "code": "HRT", "company_id": website.company_id.id,
        })
        website.warehouse_id = warehouse
        product = self.env["product.product"].create({
            "name": "HTTP reservation product", "type": "consu", "is_storable": True,
            "is_published": True, "website_id": website.id, "list_price": 10,
            "allow_out_of_stock_order": False, "company_id": website.company_id.id,
        })
        self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": product.id, "location_id": warehouse.lot_stock_id.id,
            "inventory_quantity": 2,
        }).action_apply_inventory()
        self.env.flush_all()
        response = self.url_open("/shop/cart/add", json={
            "jsonrpc": "2.0", "id": 1, "method": "call", "params": {
                "product_template_id": product.product_tmpl_id.id,
                "product_id": product.id, "quantity": 1,
            },
        })
        self.assertNotIn("error", response.json())
        status = self.url_open("/shop/ab/cart-hold")
        self.assertIn("no-store", status.headers["Cache-Control"])
        expiry = status.json()["expires_at"]
        self.assertTrue(expiry)
        session_cookies = {"session_id": self.opener.cookies.get("session_id")}
        self._browser_in_current_session("/shop/cart", """
            (async () => {
                const errors = [];
                window.addEventListener('error', event => errors.push(event.error?.stack || event.message));
                const end = Date.now() + 15000;
                while (!document.querySelector('[data-ab-cart-hold-countdown]')?.textContent) {
                    if (Date.now() > end) throw new Error('Cart countdown did not start: ' + errors.join(' | '));
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                const text = document.querySelector('[data-ab-cart-hold-countdown]').textContent;
                if (!/^\\d{2}:\\d{2}$/.test(text)) throw new Error('Invalid cart countdown');
                console.log('test successful');
            })();
        """, cookies=session_cookies, timeout=45)
        self.assertEqual(self.url_open("/shop/ab/cart-hold", cookies=session_cookies).json()["expires_at"], expiry)
        holds = self.env["ab_storefront_cart_hold"].search([("product_id", "=", product.id)])
        expired = fields.Datetime.now() - timedelta(seconds=2)
        holds.expires_at = expired
        holds.order_id.ab_cart_hold_expires_at = expired
        self.env.flush_all()
        self._browser_in_current_session("/shop/cart", """
            (async () => {
                const end = Date.now() + 15000;
                while (document.querySelector('[data-ab-cart-hold-expired]')?.classList.contains('d-none')) {
                    if (Date.now() > end) throw new Error('Expired cart hold remains active');
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                if (document.querySelector('[data-ab-cart-hold-countdown]').textContent) {
                    throw new Error('Expired cart hold still displays a countdown');
                }
                console.log('test successful');
            })();
        """, cookies=session_cookies, timeout=45)
        self.assertEqual(website._get_product_available_qty(product), 2)
