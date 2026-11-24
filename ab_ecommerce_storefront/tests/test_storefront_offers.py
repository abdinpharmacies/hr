from types import SimpleNamespace
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase, new_test_user

from ..controllers import second_item_offer


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

    def test_offer_links_carousel_slide_for_same_website_or_shared(self):
        image = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z4p8AAAAASUVORK5CYII="
        slide = self.env["ab_website_carousel_slide"].create({
            "name": "Offer carousel slide",
            "website_id": self.website.id,
            "image_1920": image,
        })
        offer = self.offer(carousel_slide_id=slide.id)
        self.assertEqual(offer.carousel_slide_id, slide)
        self.assertEqual(offer.carousel_image_1920, slide.image_1920)

        shared_slide = self.env["ab_website_carousel_slide"].create({
            "name": "Shared offer carousel slide",
            "image_1920": image,
        })
        offer.carousel_slide_id = shared_slide
        self.assertEqual(offer.carousel_slide_id, shared_slide)

        other_website = self.env["website"].create({
            "name": "Other carousel website",
            "company_id": self.company.id,
        })
        other_slide = self.env["ab_website_carousel_slide"].create({
            "name": "Other website carousel slide",
            "website_id": other_website.id,
            "image_1920": image,
        })
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.carousel_slide_id = other_slide

    def test_linked_carousel_targets_main_product_and_rejects_overlap(self):
        image = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z4p8AAAAASUVORK5CYII="
        slide = self.env["ab_website_carousel_slide"].create({
            "name": "Linked offer carousel slide",
            "website_id": self.website.id,
            "image_1920": image,
            "cta_url": "/shop?category=offers",
        })
        offer = self.offer(carousel_slide_id=slide.id)
        self.assertFalse(self.website._ab_storefront_carousel_offer_urls(slide))
        self.product.product_tmpl_id.with_context(website_id=self.website.id).website_published = True
        self.assertEqual(
            self.website._ab_storefront_carousel_offer_urls(slide),
            {slide.id: self.product.product_tmpl_id._get_product_url()},
        )
        self.product.product_tmpl_id.active = False
        self.assertFalse(self.website._ab_storefront_carousel_offer_urls(slide))
        self.product.product_tmpl_id.active = True

        other_product = self.env["product.product"].create({
            "name": "Other carousel offer product",
            "type": "consu",
            "list_price": 90,
            "taxes_id": [Command.clear()],
            "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.offer(
                product_id=other_product.id,
                carousel_slide_id=slide.id,
                once_per_customer=False,
            )

        offer.active = False
        self.assertFalse(self.website._ab_storefront_carousel_offer_urls(slide))

    def test_offer_manager_carousel_access_is_company_scoped(self):
        image = b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z4p8AAAAASUVORK5CYII="
        slide = self.env["ab_website_carousel_slide"].create({
            "name": "Allowed carousel slide",
            "website_id": self.website.id,
            "image_1920": image,
        })
        other_company = self.env["res.company"].create({"name": "Other carousel company"})
        other_website = self.env["website"].create({
            "name": "Other company carousel website",
            "company_id": other_company.id,
        })
        other_slide = self.env["ab_website_carousel_slide"].create({
            "name": "Blocked carousel slide",
            "website_id": other_website.id,
            "image_1920": image,
        })

        self.assertEqual(slide.with_user(self.manager).read(["name"])[0]["name"], slide.name)
        with self.assertRaises(AccessError):
            other_slide.with_user(self.manager).read(["name"])
        self.assertEqual(other_slide.with_user(self.admin).read(["name"])[0]["name"], other_slide.name)
        with self.assertRaises(AccessError):
            slide.with_user(self.restricted).read(["name"])

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

    def test_total_sales_units_block_stale_and_future_price_orders(self):
        offer = self.offer(once_per_customer=False, max_offer_units=5)
        first, stale = self.cart(), self.cart(self.portal.partner_id)
        first.action_confirm()
        self.assertEqual(offer._sold_primary_quantity(), 2)
        second = self.cart(self.portal.partner_id)
        second.action_confirm()
        self.assertEqual(offer._sold_primary_quantity(), 4)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            stale.action_confirm()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            stale._check_cart_is_ready_to_be_paid()
        last = self.cart(self.portal.partner_id)
        last.order_line.product_uom_qty = 1
        self._refresh_offer_cart(last)
        self.assertEqual(last.order_line.ab_storefront_price_offer_id, offer)
        last.action_confirm()
        self.assertEqual(offer._sold_primary_quantity(), 5)
        self.assertEqual(self.cart(self.portal.partner_id).order_line.price_unit, 100)

    def test_total_sales_units_block_future_gift_orders(self):
        offer = self.offer(offer_type="gift", once_per_customer=False, max_offer_units=2)
        first, stale = self.cart(), self.cart(self.portal.partner_id)
        self.assertTrue(first.order_line.filtered("is_reward_line"))
        self.assertTrue(stale.order_line.filtered("is_reward_line"))
        first.action_confirm()
        self.assertEqual(offer._sold_primary_quantity(), 2)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            stale.action_confirm()
        self.assertFalse(self.cart(self.portal.partner_id).order_line.filtered("is_reward_line"))

    def test_global_offer_limits_reject_negative_values(self):
        offer = self.offer(once_per_customer=False)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.write({"max_offer_units": -1})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.write({"max_applications": -1})
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.write({"max_applications": 1})

    def test_gift_benefit_limit_resets_in_next_order(self):
        self.offer(offer_type="gift", once_per_customer=False, max_applications=2)
        for unused in range(2):
            order = self.cart()
            order.order_line.filtered(lambda line: not line.is_reward_line).product_uom_qty = 4
            self._refresh_offer_cart(order)
            self.assertEqual(sum(order.order_line.filtered("is_reward_line").mapped("product_uom_qty")), 2)
            order.action_confirm()

    def test_second_item_benefit_limit_resets_in_next_order(self):
        self.offer(offer_type="second_half", once_per_customer=False, max_applications=1)
        for unused in range(2):
            order = self.cart()
            order.order_line.filtered(lambda line: not line.is_reward_line).product_uom_qty = 4
            self._refresh_offer_cart(order)
            self.assertEqual(order.amount_total, 350)
            order.action_confirm()

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

    def test_second_half_same_product_discounts_one_unit(self):
        offer = self.offer(offer_type="second_half", once_per_customer=False)
        order = self.cart()
        rewards = order.order_line.filtered(lambda line: line.is_reward_line and line.reward_id.program_id in offer.generated_program_ids)
        self.assertEqual(len(rewards), 1)
        self.assertEqual(order.amount_total, 150)
        self.assertEqual(rewards.price_total, -50)

    def test_second_half_customer_choice_requires_an_eligible_item(self):
        second = self.env["product.product"].create({
            "name": "Second offer product", "type": "consu", "list_price": 80,
            "taxes_id": [Command.clear()], "company_id": self.company.id,
        })
        offer = self.offer(
            offer_type="second_half", second_item_mode="choice",
            second_product_ids=[Command.set(second.ids)], once_per_customer=False,
        )
        self.assertEqual(offer.generated_program_ids.reward_ids.discount_product_ids, second)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.write({"second_product_ids": [Command.clear()]})
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
            "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": 1})],
        })
        order._update_programs_and_rewards()
        order._auto_apply_rewards()
        self.assertFalse(order.order_line.filtered("is_reward_line"))
        order._cart_add(second.id)
        order._update_programs_and_rewards()
        order._auto_apply_rewards()
        self.assertEqual(order.amount_total, 140)

    def test_mix_discount_accepts_repeated_and_mixed_collection_products(self):
        collection_products = self.env["product.product"].create([
            {
                "name": "Collection product B", "type": "consu", "list_price": 80,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
            {
                "name": "Collection product C", "type": "consu", "list_price": 60,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
        ])
        offer = self.offer(
            offer_type="mix_discount", buy_qty=2, gift_qty=1,
            second_discount_rate="50", second_product_ids=[Command.set(collection_products.ids)],
            once_per_customer=False,
        )
        program = offer.generated_program_ids
        self.assertEqual(program.rule_ids.minimum_qty, 3)
        self.assertEqual(program.rule_ids.product_ids, self.product | collection_products)
        self.assertEqual(program.reward_ids.required_points, 3)
        self.assertEqual(program.reward_ids.discount_product_ids, self.product | collection_products)
        product_templates = (self.product | collection_products).product_tmpl_id
        details = self.website._ab_storefront_offer_details(product_templates)
        self.assertEqual(set(details), set(product_templates.ids))
        self.assertTrue(all(values["collection_offer"] for values in details.values()))
        for product_template in product_templates:
            displayed_ids = {
                item["id"] for item in details[product_template.id]["collection_products"]
            }
            self.assertEqual(
                displayed_ids,
                set((self.product | collection_products).filtered(
                    lambda item: item.product_tmpl_id != product_template
                ).ids),
            )

        repeated = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
            "order_line": [Command.create({"product_id": self.product.id, "product_uom_qty": 3})],
        })
        repeated._update_programs_and_rewards()
        repeated._auto_apply_rewards()
        self.assertEqual(repeated.amount_total, 250)

        mixed = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
            "order_line": [
                Command.create({"product_id": product.id, "product_uom_qty": 1})
                for product in self.product | collection_products
            ],
        })
        mixed._update_programs_and_rewards()
        mixed._auto_apply_rewards()
        self.assertEqual(mixed.amount_total, 210)

    def test_mix_discount_repeats_by_complete_collection_cycles(self):
        collection_products = self.env["product.product"].create([
            {
                "name": "Repeated collection product B", "type": "consu", "list_price": 80,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
            {
                "name": "Repeated collection product C", "type": "consu", "list_price": 60,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
        ])
        self.offer(
            offer_type="mix_discount", buy_qty=2, gift_qty=1,
            second_discount_rate="50", second_product_ids=[Command.set(collection_products.ids)],
            once_per_customer=False,
        )
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
            "order_line": [
                Command.create({"product_id": product.id, "product_uom_qty": 2})
                for product in self.product | collection_products
            ],
        })
        order._update_programs_and_rewards()
        order._auto_apply_rewards()
        self.assertEqual(order.amount_total, 420)

    def test_mix_discount_requires_additional_collection_products(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.offer(
                offer_type="mix_discount", buy_qty=2, gift_qty=1,
                second_discount_rate="50", once_per_customer=False,
            )

    def test_mix_collection_products_have_independent_lifetime_limits(self):
        second, third = self.env["product.product"].create([
            {
                "name": "Limited collection product", "type": "consu", "list_price": 80,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
            {
                "name": "Unlimited collection product", "type": "consu", "list_price": 60,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
        ])
        offer = self.offer(
            offer_type="mix_discount", buy_qty=1, gift_qty=1,
            second_discount_rate="50", once_per_customer=False,
            main_product_max_offer_units=4,
            collection_product_line_ids=[
                Command.create({"product_id": second.id, "max_offer_units": 2}),
                Command.create({"product_id": third.id, "max_offer_units": 0}),
            ],
        )
        self.assertEqual(offer._collection_products(), second | third)
        self.assertEqual(offer._product_offer_limit(self.product), 4)
        self.assertEqual(offer._product_offer_limit(second), 2)
        self.assertEqual(offer._product_offer_limit(third), 0)
        self.assertEqual(offer.generated_program_ids.rule_ids.product_ids, self.product | second | third)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.collection_product_line_ids.filtered(
                lambda line: line.product_id == second
            ).max_offer_units = -1

    def test_mix_controller_adds_cheapest_other_product(self):
        cheapest, next_cheapest = self.env["product.product"].create([
            {
                "name": "Cheapest primary", "type": "consu", "list_price": 60,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
            {
                "name": "Next cheapest benefit", "type": "consu", "list_price": 80,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
        ])
        offer = self.offer(
            offer_type="mix_discount", product_id=cheapest.id,
            buy_qty=1, gift_qty=1, second_discount_rate="50", once_per_customer=False,
            collection_product_line_ids=[
                Command.create({"product_id": next_cheapest.id}),
                Command.create({"product_id": self.product.id}),
            ],
        )
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
        })
        fake_request = SimpleNamespace(env=self.env, website=self.website, cart=order)
        product_class = type(self.product)
        template_class = type(self.product.product_tmpl_id)
        with patch.object(second_item_offer, "request", fake_request), patch.object(
            product_class, "_is_add_to_cart_allowed", return_value=True,
        ), patch.object(product_class, "_is_sold_out", return_value=False), patch.object(
            template_class, "_get_sales_prices", lambda templates, website: {
                template.id: {"price_reduce": template.list_price} for template in templates
            },
        ):
            result = second_item_offer.StorefrontSecondItemOffer().add_second_item(
                offer.id, primary_product_id=cheapest.id, purchase_quantity=1,
            )
        self.assertEqual(result["url"], "/shop/cart")
        benefit_line = order.order_line.filtered(
            lambda line: line.ab_storefront_mix_benefit_offer_id == offer
        )
        self.assertEqual(benefit_line.product_id, next_cheapest)
        self.assertEqual(benefit_line.product_uom_qty, 1)
        self.assertEqual(order.amount_total, 100)

    def test_mix_controller_skips_exhausted_cheapest_product(self):
        cheapest, next_cheapest = self.env["product.product"].create([
            {
                "name": "Limited cheapest benefit", "type": "consu", "list_price": 60,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
            {
                "name": "Available next benefit", "type": "consu", "list_price": 80,
                "taxes_id": [Command.clear()], "company_id": self.company.id,
            },
        ])
        offer = self.offer(
            offer_type="mix_discount", buy_qty=1, gift_qty=1,
            second_discount_rate="50", once_per_customer=False,
            collection_product_line_ids=[
                Command.create({"product_id": cheapest.id, "max_offer_units": 1}),
                Command.create({"product_id": next_cheapest.id}),
            ],
        )
        used = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
            "order_line": [
                Command.create({"product_id": self.product.id, "product_uom_qty": 1}),
                Command.create({"product_id": cheapest.id, "product_uom_qty": 1}),
            ],
        })
        self._refresh_offer_cart(used)
        used.action_confirm()
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
        })
        fake_request = SimpleNamespace(env=self.env, website=self.website, cart=order)
        product_class = type(self.product)
        template_class = type(self.product.product_tmpl_id)
        with patch.object(second_item_offer, "request", fake_request), patch.object(
            product_class, "_is_add_to_cart_allowed", return_value=True,
        ), patch.object(product_class, "_is_sold_out", return_value=False), patch.object(
            template_class, "_get_sales_prices", lambda templates, website: {
                template.id: {"price_reduce": template.list_price} for template in templates
            },
        ):
            second_item_offer.StorefrontSecondItemOffer().add_second_item(
                offer.id, primary_product_id=self.product.id, purchase_quantity=1,
            )
        benefit_line = order.order_line.filtered(
            lambda line: line.ab_storefront_mix_benefit_offer_id == offer
        )
        self.assertEqual(benefit_line.product_id, next_cheapest)
        self.assertEqual(order.amount_total, 140)

    def test_mix_product_limit_blocks_stale_order_confirmation(self):
        second = self.env["product.product"].create({
            "name": "Stale limited collection product", "type": "consu", "list_price": 80,
            "taxes_id": [Command.clear()], "company_id": self.company.id,
        })
        self.offer(
            offer_type="mix_discount", buy_qty=1, gift_qty=1,
            second_discount_rate="50", once_per_customer=False,
            main_product_max_offer_units=1,
            collection_product_line_ids=[Command.create({"product_id": second.id})],
        )
        orders = self.env["sale.order"]
        for unused in range(2):
            order = self.env["sale.order"].create({
                "partner_id": self.partner.id, "website_id": self.website.id,
                "company_id": self.company.id, "pricelist_id": self.pricelist.id,
                "order_line": [
                    Command.create({"product_id": self.product.id, "product_uom_qty": 1}),
                    Command.create({"product_id": second.id, "product_uom_qty": 1}),
                ],
            })
            self._refresh_offer_cart(order)
            orders |= order
        orders[0].action_confirm()
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            orders[1].action_confirm()

    def test_mix_discount_blocks_overlapping_offer_on_collection_product(self):
        collection_product = self.env["product.product"].create({
            "name": "Overlapping collection product", "type": "consu", "list_price": 100,
            "taxes_id": [Command.clear()], "company_id": self.company.id,
        })
        self.offer(
            offer_type="mix_discount", buy_qty=2, gift_qty=1,
            second_discount_rate="50", second_product_ids=[Command.set(collection_product.ids)],
            once_per_customer=False,
        )
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.offer(product_id=collection_product.id, once_per_customer=False)

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

    def _refresh_offer_cart(self, order):
        order._update_programs_and_rewards()
        order._auto_apply_rewards()

    def test_all_percentage_rates_follow_current_price(self):
        offer = self.offer(offer_type="percent", once_per_customer=False)
        for rate in (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70):
            with self.subTest(rate=rate):
                offer.percentage_rate = str(rate)
                self.assertAlmostEqual(self.cart().amount_total, 200 * (1 - rate / 100))
        self.product.list_price = 200
        self.assertAlmostEqual(self.cart().amount_total, 120)
        self.assertEqual(offer.current_price, 200)
        self.assertAlmostEqual(offer.discounted_price, 60)

    def test_cart_price_breakdown_shows_percentage_savings(self):
        regular_cart = self.cart()
        self.assertEqual(regular_cart._ab_storefront_cart_price_breakdown()["discount"], 0)
        self.offer(offer_type="percent", percentage_rate="10", once_per_customer=False)
        order = self.cart()
        breakdown = order._ab_storefront_cart_price_breakdown()
        self.assertAlmostEqual(breakdown["original_price"], 200)
        self.assertAlmostEqual(breakdown["discount"], 20)
        self.assertAlmostEqual(order.amount_total, 180)
        totals_html = self.env["ir.qweb"]._render("website_sale.total", {
            "website_sale_order": order, "hide_promotions": True,
        })
        self.assertIn("Original price", totals_html)
        self.assertIn("Discount", totals_html)
        arabic_totals_html = self.env["ir.qweb"].with_context(lang="ar_001")._render(
            "website_sale.total", {"website_sale_order": order, "hide_promotions": True},
        )
        self.assertIn("السعر الأصلي", arabic_totals_html)
        self.assertIn("الخصم", arabic_totals_html)
        self.product.list_price = 200
        updated_order = self.cart()
        updated_breakdown = updated_order._ab_storefront_cart_price_breakdown()
        self.assertAlmostEqual(updated_breakdown["original_price"], 400)
        self.assertAlmostEqual(updated_breakdown["discount"], 40)
        self.assertAlmostEqual(updated_order.amount_total, 360)

    def test_all_amount_discounts_and_current_price_changes(self):
        self.pricelist.currency_id = self.env.ref("base.EGP")
        self.company.currency_id = self.env.ref("base.EGP")
        self.product.list_price = 500
        offer = self.offer(offer_type="amount", once_per_customer=False)
        for amount in (80, 100, 120, 125, 130, 140, 150, 200, 250):
            with self.subTest(amount=amount):
                offer.amount_discount = str(amount)
                self.assertAlmostEqual(self.cart().amount_total, 2 * (500 - amount))
        self.product.list_price = 600
        self.assertAlmostEqual(self.cart().amount_total, 700)
        self.product.list_price = 200
        cart = self.cart()
        self.assertEqual(cart.amount_total, 400)
        self.assertFalse(cart.order_line.ab_storefront_price_offer_id)

    def test_amount_discount_rejects_wrong_currency_or_excess_amount(self):
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.offer(offer_type="amount", amount_discount="250")
        self.product.list_price = 500
        self.pricelist.currency_id = self.env.ref("base.USD")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.offer(offer_type="amount")

    def test_fixed_discount_equal_or_above_price_keeps_input_and_raises(self):
        self.pricelist.currency_id = self.env.ref("base.EGP")
        self.company.currency_id = self.env.ref("base.EGP")
        self.product.list_price = 75
        form = Form(self.env["ab_storefront_offer"], view=self.env.ref("ab_ecommerce_storefront.storefront_offer_form"))
        form.website_id = self.website
        form.product_id = self.product
        form.offer_type = "amount"
        form.pricelist_id = self.pricelist
        form.amount_discount = "custom"
        form.custom_amount_discount = 75
        self.assertEqual(form.custom_amount_discount, 75)
        for amount in (75, 76):
            with self.subTest(amount=amount), self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.offer(offer_type="amount", amount_discount="custom", custom_amount_discount=amount)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            self.offer(offer_type="amount", amount_discount="80")

    def test_custom_amount_discount_keeps_one_egp_product_price(self):
        self.pricelist.currency_id = self.env.ref("base.EGP")
        self.company.currency_id = self.env.ref("base.EGP")
        self.product.list_price = 36
        offer = self.offer(
            offer_type="amount", amount_discount="custom", custom_amount_discount=35,
        )
        self.assertEqual(offer.discounted_price, 1)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            offer.custom_amount_discount = 35.01
        with self.assertRaisesRegex(ValidationError, "جنيه مصري واحد"), self.env.cr.savepoint():
            offer.with_context(lang="ar_001").custom_amount_discount = 35.01
        self.product.list_price = 35
        self.assertEqual(self.cart().amount_total, 70)

    def test_custom_amount_discount_updates_price_and_rejects_excess(self):
        self.pricelist.currency_id = self.env.ref("base.EGP")
        self.company.currency_id = self.env.ref("base.EGP")
        self.product.list_price = 500
        offer = self.offer(
            offer_type="amount", amount_discount="custom", custom_amount_discount=275.5,
            once_per_customer=False,
        )
        self.assertAlmostEqual(self.cart().amount_total, 449)
        self.assertAlmostEqual(offer.discounted_price, 224.5)
        offer.custom_amount_discount = 300
        self.assertAlmostEqual(self.cart().amount_total, 400)
        for amount in (0, 500, 501):
            with self.subTest(amount=amount), self.assertRaises(ValidationError), self.env.cr.savepoint():
                offer.custom_amount_discount = amount

    def test_percentage_once_per_customer_and_legacy_price(self):
        offer = self.offer(offer_type="percent", percentage_rate="20")
        order = self.cart()
        self.assertEqual(order.amount_total, 160)
        order.action_confirm()
        self.assertEqual(self.cart().amount_total, 200)
        offer.active = False
        legacy = self.offer(once_per_customer=False)
        self.product.list_price = 120
        self.assertEqual(self.cart().amount_total, 160)
        self.assertEqual(legacy.price_after, 80)

    def test_second_item_all_rates_repeat_per_eligible_pair(self):
        offer = self.offer(offer_type="second_half", once_per_customer=False)
        order = self.cart()
        paid = order.order_line.filtered(lambda line: not line.is_reward_line)
        paid.product_uom_qty = 4
        for rate in (20, 25, 30, 35, 40, 45, 50, 60):
            with self.subTest(rate=rate):
                offer.second_discount_rate = str(rate)
                self._refresh_offer_cart(order)
                self.assertAlmostEqual(order.amount_total, 400 - 2 * rate)
        offer.write({"second_discount_rate": "50"})
        self._refresh_offer_cart(order)
        self.assertEqual(order.amount_total, 300)
        paid.product_uom_qty = 7
        self._refresh_offer_cart(order)
        self.assertEqual(order.amount_total, 550)
        paid.product_uom_qty = 1
        self._refresh_offer_cart(order)
        self.assertFalse(order.order_line.filtered("is_reward_line"))

    def test_second_item_chooses_cheapest_eligible_units(self):
        second, third, unrelated = self.env["product.product"].create([
            {"name": name, "type": "consu", "list_price": price, "taxes_id": [Command.clear()], "company_id": self.company.id}
            for name, price in (("Benefit 80", 80), ("Benefit 60", 60), ("Unrelated 1", 1))
        ])
        self.offer(offer_type="second_half", second_item_mode="choice", second_product_ids=[Command.set((second | third).ids)], once_per_customer=False)
        order = self.cart()
        order.write({"order_line": [Command.create({"product_id": product.id, "product_uom_qty": 1}) for product in (second, third, unrelated)]})
        self._refresh_offer_cart(order)
        self.assertEqual(order.amount_total, 271)
        order.order_line.filtered(lambda line: line.product_id == self.product and not line.is_reward_line).product_uom_qty = 1
        self._refresh_offer_cart(order)
        self.assertEqual(order.amount_total, 211)

    def test_gift_ratios_repeat_per_eligible_quantity(self):
        offer = self.offer(offer_type="gift", once_per_customer=False)
        for buy, free in ((1, 1), (2, 1), (3, 1), (2, 2)):
            with self.subTest(buy=buy, free=free):
                offer.write({"buy_qty": buy, "gift_qty": free})
                order = self.cart()
                paid = order.order_line.filtered(lambda line: not line.is_reward_line)
                paid.product_uom_qty = buy * 3
                self._refresh_offer_cart(order)
                self.assertEqual(sum(order.order_line.filtered("is_reward_line").mapped("product_uom_qty")), free * 3)
                self.assertEqual(order.amount_total, buy * 300)
                paid.product_uom_qty = buy - 1
                self._refresh_offer_cart(order)
                self.assertFalse(order.order_line.filtered("is_reward_line"))

    def test_fixed_different_gift_and_storefront_details(self):
        second = self.env["product.product"].create({"type": "consu", "taxes_id": [Command.clear()], "company_id": self.company.id, **{"name": "Different gift", "list_price": 80}})
        offer = self.offer(offer_type="gift", second_item_mode="choice", second_product_ids=[Command.set(second.ids)], buy_qty=2, gift_qty=2, once_per_customer=False)
        order = self.cart()
        gift = order.order_line.filtered("is_reward_line")
        self.assertEqual(gift.product_id, second)
        self.assertEqual(gift.product_uom_qty, 2)
        self.assertEqual(order.amount_total, 200)
        with patch.object(type(second), "_is_add_to_cart_allowed", return_value=True), patch.object(type(second), "_is_sold_out", return_value=False):
            details = self.website._ab_storefront_offer_details(self.product.product_tmpl_id)[self.product.product_tmpl_id.id]
        self.assertTrue(details["bundle_offer"])
        self.assertEqual(details["free_qty"], 2)
        self.assertEqual(details["offer_id"], offer.id)
        self.assertEqual(details["benefit_products"][0]["id"], second.id)
        self.assertEqual(details["benefit_products"][0]["name"], second.name)
        self.assertEqual(details["benefit_product_count"], 1)
        with patch.object(type(second), "_is_add_to_cart_allowed", return_value=False):
            unavailable = self.website._ab_storefront_offer_details(self.product.product_tmpl_id)[self.product.product_tmpl_id.id]
        self.assertFalse(unavailable["benefit_products"])

    def test_multi_product_gift_validates_choice_and_removal(self):
        second = self.env["product.product"].create({"type": "consu", "taxes_id": [Command.clear()], "company_id": self.company.id, **{"name": "Gift B", "list_price": 80}})
        third = self.env["product.product"].create({"type": "consu", "taxes_id": [Command.clear()], "company_id": self.company.id, **{"name": "Gift C", "list_price": 60}})
        offer = self.offer(offer_type="gift", second_item_mode="choice", second_product_ids=[Command.set((second | third).ids)], buy_qty=2, once_per_customer=False)
        order = self.cart()
        self.assertFalse(order.order_line.filtered("is_reward_line"))
        reward = offer.generated_program_ids.reward_ids
        coupon = order.coupon_point_ids.coupon_id.filtered(lambda card: card.program_id == offer.generated_program_ids)
        with self.assertRaises(UserError):
            order._get_reward_line_values(reward, coupon, product=self.product)
        result = order._apply_program_reward(reward, coupon, product=third)
        self.assertNotIn("error", result)
        self._refresh_offer_cart(order)
        self.assertEqual(order.order_line.filtered("is_reward_line").product_id, third)
        order.order_line.filtered(lambda line: not line.is_reward_line).product_uom_qty = 1
        self._refresh_offer_cart(order)
        self.assertFalse(order.order_line.filtered("is_reward_line"))

    def test_offer_selection_and_negative_limit_rejected(self):
        offer = self.offer(offer_type="gift")
        for values in ({"second_item_mode": "choice"}, {"second_item_mode": "choice", "second_product_ids": [Command.set(self.product.ids)]}):
            with self.subTest(values=values), self.assertRaises(ValidationError), self.env.cr.savepoint():
                offer.write(values)
        other_company = self.env["res.company"].create({"name": "Gift other company"})
        other_product = self.env["product.product"].create({"type": "consu", "taxes_id": [Command.clear()], "company_id": self.company.id, **{"name": "Foreign gift", "company_id": other_company.id}})
        with self.assertRaises(UserError), self.env.cr.savepoint():
            offer.write({"second_item_mode": "choice", "second_product_ids": [Command.set(other_product.ids)]})

    def test_portal_cannot_edit_discount_configuration(self):
        offer = self.offer(offer_type="percent")
        with self.assertRaises(AccessError):
            offer.with_user(self.portal).write({"percentage_rate": "70"})
        with self.assertRaises(AccessError):
            offer.with_user(self.portal).write({"max_offer_units": 1})
        with self.assertRaises(AccessError):
            offer.with_user(self.portal).write({"max_applications": 1})
        offer.with_user(self.designer).write({"percentage_rate": "25"})
        offer.with_user(self.designer).write({"max_offer_units": 2})
        self.assertEqual(offer.percentage_rate, "25")
        self.assertEqual(offer.max_offer_units, 2)

    def test_mix_collection_limit_access_follows_offer_permissions(self):
        second = self.env["product.product"].create({
            "name": "Secured collection product", "type": "consu", "list_price": 80,
            "taxes_id": [Command.clear()], "company_id": self.company.id,
        })
        offer = self.offer(
            offer_type="mix_discount", buy_qty=1, gift_qty=1,
            collection_product_line_ids=[Command.create({"product_id": second.id})],
            once_per_customer=False,
        )
        line = offer.collection_product_line_ids
        with self.assertRaises(AccessError):
            line.with_user(self.portal).write({"max_offer_units": 3})
        line.with_user(self.manager).write({"max_offer_units": 3})
        self.assertEqual(line.max_offer_units, 3)

    def test_gift_controller_adds_selected_gift_atomically(self):
        second = self.env["product.product"].create({"type": "consu", "taxes_id": [Command.clear()], "company_id": self.company.id, **{"name": "Selected gift", "list_price": 80}})
        third = self.env["product.product"].create({"type": "consu", "taxes_id": [Command.clear()], "company_id": self.company.id, **{"name": "Other gift", "list_price": 60}})
        offer = self.offer(offer_type="gift", second_item_mode="choice", second_product_ids=[Command.set((second | third).ids)], buy_qty=2, gift_qty=2, once_per_customer=False)
        order = self.env["sale.order"].create({"partner_id": self.partner.id, "website_id": self.website.id, "company_id": self.company.id, "pricelist_id": self.pricelist.id})
        fake_request = SimpleNamespace(env=self.env, website=self.website, cart=order)
        controller = second_item_offer.StorefrontSecondItemOffer()
        product_class = type(self.product)
        with patch.object(second_item_offer, "request", fake_request), patch.object(product_class, "_is_add_to_cart_allowed", return_value=True), patch.object(product_class, "_is_sold_out", return_value=False):
            with self.assertRaises(UserError):
                controller.add_second_item(offer.id, self.product.id)
            self.assertFalse(order.order_line)
            result = controller.add_second_item(offer.id, third.id)
            self.assertEqual(result["url"], "/shop/cart")
        gift = order.order_line.filtered("is_reward_line")
        self.assertEqual(gift.product_id, third)
        self.assertEqual(gift.product_uom_qty, 2)
        self.assertEqual(order.amount_total, 200)

    def test_gift_controller_splits_multiple_free_units_and_preserves_choices(self):
        second, third = self.env["product.product"].create([
            {"name": name, "type": "consu", "list_price": 80,
             "taxes_id": [Command.clear()], "company_id": self.company.id}
            for name in ("First gift", "Second gift")
        ])
        offer = self.offer(
            offer_type="gift", second_item_mode="choice", gift_qty=2,
            second_product_ids=[Command.set((second | third).ids)], once_per_customer=False,
        )
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
        })
        fake_request = SimpleNamespace(env=self.env, website=self.website, cart=order)
        controller = second_item_offer.StorefrontSecondItemOffer()
        product_class = type(self.product)
        allocations = [
            {"product_id": second.id, "quantity": 1},
            {"product_id": third.id, "quantity": 1},
        ]
        with patch.object(second_item_offer, "request", fake_request), patch.object(product_class, "_is_add_to_cart_allowed", return_value=True), patch.object(product_class, "_is_sold_out", return_value=False):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                controller.add_second_item(offer.id, gift_allocations=[
                    {"product_id": second.id, "quantity": 3},
                ])
            self.assertFalse(order.order_line)
            controller.add_second_item(offer.id, gift_allocations=allocations)
        gift_lines = order.order_line.filtered("is_reward_line")
        self.assertEqual({line.product_id.id: line.product_uom_qty for line in gift_lines}, {
            second.id: 1, third.id: 1,
        })
        self.assertEqual(sum(gift_lines.mapped("points_cost")), offer.buy_qty)
        self.assertEqual(order.amount_total, 100)
        order.order_line.filtered(lambda line: not line.is_reward_line).product_uom_qty = 2
        self._refresh_offer_cart(order)
        gift_lines = order.order_line.filtered("is_reward_line")
        self.assertEqual({line.product_id.id: line.product_uom_qty for line in gift_lines}, {
            second.id: 3, third.id: 1,
        })
        self.assertEqual(order.amount_total, 200)

    def test_gift_controller_reselects_two_gifts_after_second_purchase(self):
        second, third = self.env["product.product"].create([
            {"name": name, "type": "consu", "list_price": 80,
             "taxes_id": [Command.clear()], "company_id": self.company.id}
            for name in ("First choice", "Second choice")
        ])
        offer = self.offer(
            offer_type="gift", second_item_mode="choice", gift_qty=1,
            second_product_ids=[Command.set((second | third).ids)], once_per_customer=False,
        )
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id, "website_id": self.website.id,
            "company_id": self.company.id, "pricelist_id": self.pricelist.id,
        })
        fake_request = SimpleNamespace(env=self.env, website=self.website, cart=order)
        controller = second_item_offer.StorefrontSecondItemOffer()
        product_class = type(self.product)
        with patch.object(second_item_offer, "request", fake_request), patch.object(product_class, "_is_add_to_cart_allowed", return_value=True), patch.object(product_class, "_is_sold_out", return_value=False):
            controller.add_second_item(offer.id, purchase_quantity=2, gift_allocations=[
                {"product_id": second.id, "quantity": 1},
                {"product_id": third.id, "quantity": 1},
            ])
        gift_lines = order.order_line.filtered("is_reward_line")
        self.assertEqual({line.product_id.id: line.product_uom_qty for line in gift_lines}, {
            second.id: 1, third.id: 1,
        })
        self.assertEqual(order.amount_total, 200)

    def test_public_gift_picker_excludes_unpublished_products(self):
        published, unpublished = self.env["product.product"].create([
            {"name": name, "type": "consu", "list_price": 80,
             "taxes_id": [Command.clear()], "company_id": self.company.id}
            for name in ("Published gift", "Unpublished gift")
        ])
        published.product_tmpl_id.website_published = True
        offer = self.offer(
            offer_type="gift", second_item_mode="choice", gift_qty=2,
            second_product_ids=[Command.set((published | unpublished).ids)],
            once_per_customer=False,
        )
        public_env = self.env["product.product"].with_user(self.website.user_id).env
        fake_request = SimpleNamespace(
            env=public_env, website=self.website, cart=False, pricelist=self.pricelist,
        )
        product_class = type(self.product)
        template_class = type(self.product.product_tmpl_id)
        with patch.object(second_item_offer, "request", fake_request), patch.object(
            product_class, "_is_add_to_cart_allowed", lambda product: bool(product.website_published),
        ), patch.object(product_class, "_is_sold_out", return_value=False), patch.object(
            template_class, "_get_sales_prices", lambda templates, website: {
                template.id: {"price_reduce": 80} for template in templates
            },
        ):
            response = second_item_offer.StorefrontSecondItemOffer().second_items(offer.id)
        self.assertEqual([item["id"] for item in response["items"]], [published.id])
        self.assertEqual(response["gift_slots"], 2)

    def test_second_item_converts_purchase_units(self):
        self.offer(offer_type="second_half", once_per_customer=False)
        pair = self.env["uom.uom"].create({"name": "Offer pair", "relative_uom_id": self.product.uom_id.id, "relative_factor": 2})
        order = self.cart()
        line = order.order_line.filtered(lambda current: not current.is_reward_line)
        line.write({"product_uom_id": pair.id, "product_uom_qty": 2, "price_unit": 200})
        self._refresh_offer_cart(order)
        self.assertEqual(order.amount_total, 300)

    def test_gift_candidates_survive_archival_of_one_choice(self):
        second, third = self.env["product.product"].create([
            {"name": name, "type": "consu", "list_price": 80, "taxes_id": [Command.clear()], "company_id": self.company.id}
            for name in ("Gift first", "Gift remaining")
        ])
        offer = self.offer(offer_type="gift", second_item_mode="choice", second_product_ids=[Command.set((second | third).ids)], once_per_customer=False)
        second.active = False
        reward = offer.generated_program_ids.reward_ids
        self.assertEqual(reward.reward_product_ids, third)
        self.assertIn(reward, self.env["loyalty.reward"].search([("reward_product_ids", "in", third.ids)]))
        order = self.cart()
        self.assertEqual(order.order_line.filtered("is_reward_line").product_id, third)

    def test_bundle_controller_rejects_other_website_and_inactive_offer(self):
        offer = self.offer(offer_type="gift", once_per_customer=False)
        controller = second_item_offer.StorefrontSecondItemOffer()
        website = self.env["website"].create({"name": "Other offer website", "company_id": self.company.id})
        fake_request = SimpleNamespace(env=self.env(user=self.portal), website=website, cart=self.env["sale.order"])
        with patch.object(second_item_offer, "request", fake_request):
            with self.assertRaises(UserError):
                controller._get_offer(offer.id)
            fake_request.website = self.website
            self.assertEqual(controller._get_offer(offer.id), offer)
            offer.active = False
            with self.assertRaises(UserError):
                controller._get_offer(offer.id)

    def test_gift_controller_rolls_back_incomplete_purchase(self):
        offer = self.offer(offer_type="gift", buy_qty=2, once_per_customer=False)
        order = self.env["sale.order"].create({"partner_id": self.partner.id, "website_id": self.website.id, "company_id": self.company.id, "pricelist_id": self.pricelist.id})
        fake_request = SimpleNamespace(env=self.env, website=self.website, cart=order)
        original_add = type(order)._cart_add

        def incomplete_add(current_order, *args, **kwargs):
            result = original_add(current_order, *args, **kwargs)
            return {**result, "added_qty": 1}

        with patch.object(second_item_offer, "request", fake_request), patch.object(type(self.product), "_is_add_to_cart_allowed", return_value=True), patch.object(type(self.product), "_is_sold_out", return_value=False), patch.object(type(order), "_cart_add", incomplete_add):
            with self.assertRaises(UserError):
                second_item_offer.StorefrontSecondItemOffer().add_second_item(offer.id)
        self.assertFalse(order.order_line)
