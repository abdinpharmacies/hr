from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user


@tagged("post_install", "-at_install")
class TestStorefrontOffers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.website = cls.env.ref("website.default_website")
        cls.company = cls.website.company_id
        cls.partner = cls.env["res.partner"].create({"name": "Offer customer"})
        cls.product = cls.env["product.product"].create({
            "name": "Offer test product", "type": "consu", "list_price": 100,
            "taxes_id": [Command.clear()], "company_id": cls.company.id,
        })
        cls.pricelist = cls.env["product.pricelist"].create({
            "name": "Offer test prices", "website_id": cls.website.id,
            "company_id": cls.company.id, "currency_id": cls.company.currency_id.id,
        })
        cls.designer = new_test_user(cls.env, login="offer_designer", groups="base.group_user,website.group_website_designer", company_id=cls.company.id)
        cls.manager = new_test_user(cls.env, login="offer_manager", groups="base.group_user,sales_team.group_sale_manager", company_id=cls.company.id)
        cls.restricted = new_test_user(cls.env, login="offer_restricted", groups="base.group_user,website.group_website_restricted_editor", company_id=cls.company.id)
        cls.admin = new_test_user(cls.env, login="offer_admin", groups="base.group_user,base.group_system", company_id=cls.company.id)
        cls.call_center = new_test_user(cls.env, login="offer_call_center", groups="base.group_user,ab_ecommerce_storefront.group_call_center", company_id=cls.company.id)
        cls.portal = new_test_user(cls.env, login="offer_portal", groups="base.group_portal", company_id=cls.company.id)

    def offer(self, **values):
        return self.env["ab_storefront_offer"].create({
            "name": "Offer test", "website_id": self.website.id,
            "product_id": self.product.id, "offer_type": "price",
            "pricelist_id": self.pricelist.id, "price_before": 100, "price_after": 80,
            "once_per_customer": True, **values,
        })

    def cart(self, partner=None):
        order = self.env["sale.order"].create({
            "partner_id": (partner or self.partner).id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
            "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": 2})],
        })
        order._update_programs_and_rewards()
        order._auto_apply_rewards()
        return order

    def test_delete_price_offer_as_designer(self):
        offer = self.offer()
        rules = offer.price_rule_ids
        offer.with_user(self.designer).unlink()
        self.assertFalse(offer.exists())
        self.assertFalse(rules.exists())
        self.assertTrue(self.pricelist.exists())

    def test_delete_gift_offer_as_admin_preserves_program(self):
        offer = self.offer(offer_type="gift")
        program = offer.generated_program_ids
        offer.with_user(self.admin).unlink()
        self.assertTrue(program.exists())
        self.assertFalse(program.active)
        self.assertFalse(program.ab_storefront_offer_id)

    def test_delete_denied_roles(self):
        offer = self.offer()
        for user in (self.manager, self.restricted, self.call_center, self.portal):
            with self.subTest(user=user.login), self.assertRaises(AccessError):
                offer.with_user(user).unlink()

    def test_company_isolation(self):
        company = self.env["res.company"].create({"name": "Other offer company"})
        website = self.env["website"].create({"name": "Other offer site", "company_id": company.id})
        product = self.env["product.product"].create({"name": "Other offer product", "company_id": company.id})
        offer = self.offer(website_id=website.id, product_id=product.id, offer_type="gift", pricelist_id=False)
        with self.assertRaises(AccessError):
            offer.with_user(self.designer).unlink()

    def test_price_once_and_stale_cart(self):
        offer = self.offer()
        first, stale = self.cart(), self.cart()
        self.assertEqual(first.order_line.price_unit, 80)
        self.assertEqual(stale.order_line.ab_storefront_price_offer_id, offer)
        first.action_confirm()
        with self.assertRaises(ValidationError):
            stale.action_confirm()
        with self.assertRaises(ValidationError):
            stale._check_cart_is_ready_to_be_paid()
        fresh = self.cart()
        self.assertEqual(fresh.order_line.price_unit, 100)
        fresh.action_confirm()

    def test_other_customer_and_delivery_contact(self):
        self.offer()
        first = self.cart()
        first.action_confirm()
        address = self.env["res.partner"].create({"name": "Delivery", "parent_id": self.partner.id, "type": "delivery"})
        self.assertEqual(self.cart(address).order_line.price_unit, 100)
        other = self.cart(self.portal.partner_id)
        self.assertEqual(other.order_line.price_unit, 80)
        other.action_confirm()

    def test_cancellation_does_not_reset_use(self):
        self.offer()
        first = self.cart()
        first.action_confirm()
        first._action_cancel()
        self.assertEqual(self.cart().order_line.price_unit, 100)

    def test_duplicate_order_does_not_copy_consumed_price(self):
        self.offer()
        first = self.cart()
        first.action_confirm()
        duplicate = first.copy()
        self.assertEqual(duplicate.order_line.price_unit, 100)
        self.assertFalse(duplicate.order_line.ab_storefront_price_offer_id)
        duplicate.action_confirm()

    def test_unlimited_offer_is_repeatable(self):
        self.offer(once_per_customer=False)
        for unused in range(2):
            order = self.cart()
            self.assertEqual(order.order_line.price_unit, 80)
            order.action_confirm()
        self.assertEqual(self.env["ab_storefront_offer_use"].search_count([("partner_id", "=", self.partner.id)]), 1)

    def test_enabling_limit_remembers_previous_use(self):
        offer = self.offer(once_per_customer=False)
        self.cart().action_confirm()
        offer.once_per_customer = True
        self.assertEqual(self.cart().order_line.price_unit, 100)

    def test_enabling_limit_recovers_confirmed_order_history(self):
        offer = self.offer(once_per_customer=False)
        order = self.cart()
        order.action_confirm()
        self.env["ab_storefront_offer_use"].search([("offer_id", "=", offer.id)]).unlink()
        offer.once_per_customer = True
        usage = self.env["ab_storefront_offer_use"].search([("offer_id", "=", offer.id)])
        self.assertEqual(usage.order_id, order)
        self.assertEqual(self.cart().order_line.price_unit, 100)

    def test_designer_can_manage_setting(self):
        offer = self.offer(once_per_customer=False)
        offer.with_user(self.designer).write({"once_per_customer": True})
        self.assertTrue(offer.once_per_customer)

    def test_batch_confirmation_cannot_redeem_twice(self):
        self.offer()
        orders = self.cart() | self.cart()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            orders.action_confirm()

    def test_linked_gift_program_is_limited_without_modifying_it(self):
        generated = self.offer(offer_type="gift", buy_qty=2, gift_qty=1)
        program = generated.generated_program_ids
        generated.unlink()
        program.active = True
        offer = self.offer(offer_type="gift", use_odoo_promotion=True, program_id=program.id)
        first = self.cart()
        self.assertTrue(first.order_line.filtered("is_reward_line"))
        first.action_confirm()
        self.assertFalse(self.cart().order_line.filtered("is_reward_line"))
        self.assertEqual(self.env["ab_storefront_offer_use"].search([("offer_id", "=", offer.id)]).order_id, first)
        self.assertTrue(program.active)

    def test_linked_discount_program_is_limited(self):
        program = self.env["loyalty.program"].create({
            "name": "Linked offer discount", "program_type": "promotion",
            "company_id": self.company.id, "website_id": self.website.id,
            "sale_ok": False, "ecommerce_ok": True, "trigger": "auto", "applies_on": "current",
            "rule_ids": [Command.create({
                "mode": "auto", "minimum_qty": 1, "minimum_amount": 0,
                "reward_point_mode": "order", "reward_point_amount": 1,
                "product_ids": [Command.set(self.product.ids)],
            })],
            "reward_ids": [Command.create({
                "reward_type": "discount", "discount": 20, "discount_mode": "percent",
                "discount_applicability": "specific", "required_points": 1,
                "discount_product_ids": [Command.set(self.product.ids)],
            })],
        })
        self.offer(use_odoo_promotion=True, program_id=program.id)
        first = self.cart()
        self.assertTrue(first.order_line.filtered("is_reward_line"))
        first.action_confirm()
        self.assertFalse(self.cart().order_line.filtered("is_reward_line"))

    def test_gift_once(self):
        offer = self.offer(offer_type="gift", buy_qty=2, gift_qty=1)
        first, stale = self.cart(), self.cart()
        self.assertEqual(first.order_line.filtered("is_reward_line").product_uom_qty, 1)
        first.action_confirm()
        self.assertEqual(self.env["ab_storefront_offer_use"].search([("offer_id", "=", offer.id)]).order_id, first)
        with self.assertRaises(ValidationError):
            stale.action_confirm()
        self.assertFalse(self.cart().order_line.filtered("is_reward_line"))

    def test_used_offer_cannot_be_deleted_or_usage_erased(self):
        offer = self.offer()
        self.cart().action_confirm()
        with self.assertRaises(ValidationError):
            offer.with_user(self.designer).unlink()
        usage = self.env["ab_storefront_offer_use"].search([("offer_id", "=", offer.id)])
        with self.assertRaises(AccessError):
            usage.with_user(self.admin).unlink()
        with self.assertRaises(AccessError):
            usage.with_user(self.portal).read(["partner_id"])

    def test_unique_usage_and_same_order_retry(self):
        offer = self.offer()
        first = self.cart()
        first.action_confirm()
        usage = self.env["ab_storefront_offer_use"].search([("offer_id", "=", offer.id)])
        first._ab_check_offer_eligibility()
        with self.assertRaises(IntegrityError), self.env.cr.savepoint():
            usage.copy({"order_id": self.cart().id})

    def test_price_snapshot_cannot_be_forged(self):
        self.offer()
        line = self.cart().order_line
        with self.assertRaises(AccessError):
            line.with_user(self.manager).write({"ab_storefront_price_offer_id": False})

    def test_public_customer_cannot_consume_offer(self):
        self.offer()
        order = self.cart(self.website.user_id.partner_id)
        self.assertEqual(order.order_line.price_unit, 100)
