from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAbWebsiteSaleProduct(TransactionCase):
    def _create_ab_product(self, code="AB-WEB-TEST-001"):
        group = self.env["ab_product_group"].create({"name": "Website Test Group"})
        tag = self.env["ab_product_tag"].create({"name": "Website Test Tag", "priority": 4})
        barcode = self.env["ab_product_barcode"].create({"name": code.replace("-", "")})
        card = self.env["ab_product_card"].create({
            "name": "Website Test Product",
            "description": "Visible in the shop.",
            "groups_ids": [fields.Command.set(group.ids)],
        })
        return self.env["ab_product"].create({
            "product_card_id": card.id,
            "code": code,
            "default_price": 25.5,
            "default_cost": 10.0,
            "tag_ids": [fields.Command.set(tag.ids)],
            "barcode_ids": [fields.Command.set(barcode.ids)],
            "website_sale_available": True,
        })

    def test_sync_ab_product_creates_published_ecommerce_product(self):
        product = self._create_ab_product()

        template = product._sync_website_products()

        self.assertEqual(template.ab_product_id, product)
        self.assertEqual(template.name, "Website Test Product")
        self.assertEqual(template.default_code, "AB-WEB-TEST-001")
        self.assertEqual(template.list_price, 25.5)
        self.assertTrue(template.sale_ok)
        self.assertTrue(template.is_published)
        self.assertEqual(template.product_variant_id.barcode, "ABWEBTEST001")
        self.assertEqual(template.public_categ_ids.name, "Website Test Group")
        self.assertEqual(template.product_tag_ids.name, "Website Test Tag")
<<<<<<< Updated upstream

    def test_ecommerce_cart_quantity_is_limited_by_eplus_snapshot_total(self):
        card = self.env["ab_product_card"].create({
            "name": "Website Limited Product",
        })
        ab_product = self.env["ab_product"].create({
            "product_card_id": card.id,
            "code": "AB-WEB-LIMIT-001",
            "default_price": 15.0,
            "default_cost": 5.0,
            "website_sale_available": True,
        })
        self.env["ab_eplus_stock_snapshot"].create({
            "itm_id": 900001,
            "itm_code": "AB-WEB-LIMIT-001",
            "itm_qty": 3.0,
            "product_id": ab_product.id,
            "matched_by": "code",
            "last_sync_date": fields.Datetime.now(),
        })
        template = ab_product._sync_website_products()
        variant = template.product_variant_id
        order = self.env["sale.order"].create({
            "partner_id": self.env.ref("base.public_partner").id,
            "pricelist_id": self.env.ref("product.list0").id,
            "website_id": self.env["website"].get_current_website().id,
        })

        qty, warning = order._verify_updated_quantity(
            self.env["sale.order.line"],
            variant.id,
            5.0,
            variant.uom_id.id,
        )

        self.assertEqual(qty, 3.0)
        self.assertIn("You cannot buy more than", warning)
=======
        self.assertTrue(template.is_storable)
        self.assertFalse(template.allow_out_of_stock_order)
        self.assertTrue(template.show_availability)

    def test_cart_add_is_limited_by_eplus_stock_snapshot(self):
        product = self._create_ab_product("AB-WEB-STOCK-001")
        template = product._sync_website_products()
        variant = template.product_variant_id
        self.env["ab_eplus_stock_snapshot"].create({
            "itm_id": 991001,
            "itm_code": product.code,
            "itm_qty": 3.0,
            "product_id": product.id,
            "matched_by": "code",
        })
        order = self.env["sale.order"].create({
            "partner_id": self.env.ref("base.public_partner").id,
            "website_id": self.env["website"].get_current_website().id,
        })

        result = order._cart_add(variant.id, quantity=5)

        self.assertEqual(result["quantity"], 3.0)
        self.assertIn("only 3 is available", result["warning"])
        self.assertEqual(order.order_line.product_uom_qty, 3.0)

    def test_cart_validation_uses_snapshot_for_existing_untracked_products(self):
        product = self._create_ab_product("AB-WEB-STOCK-002")
        template = product._sync_website_products()
        template.is_storable = False
        variant = template.product_variant_id
        self.env["ab_eplus_stock_snapshot"].create({
            "itm_id": 991002,
            "itm_code": product.code,
            "itm_qty": 2.0,
            "product_id": product.id,
            "matched_by": "code",
        })
        order = self.env["sale.order"].create({
            "partner_id": self.env.ref("base.public_partner").id,
            "website_id": self.env["website"].get_current_website().id,
        })

        result = order._cart_add(variant.id, quantity=4)

        self.assertEqual(result["quantity"], 2.0)
        self.assertIn("only 2 is available", result["warning"])
        self.assertEqual(order.order_line._get_max_line_qty(), 2.0)

    def test_website_available_qty_comes_from_eplus_stock_snapshot(self):
        product = self._create_ab_product("AB-WEB-STOCK-003")
        template = product._sync_website_products()
        self.env["ab_eplus_stock_snapshot"].create([
            {
                "itm_id": 991003,
                "itm_code": product.code,
                "itm_qty": 4.0,
                "product_id": product.id,
                "matched_by": "code",
            },
            {
                "itm_id": 991004,
                "itm_code": product.code,
                "itm_qty": 5.0,
                "product_id": product.id,
                "matched_by": "code",
            },
        ])

        qty = self.env["website"].get_current_website()._get_product_available_qty(
            template.product_variant_id
        )

        self.assertEqual(qty, 9.0)
>>>>>>> Stashed changes
