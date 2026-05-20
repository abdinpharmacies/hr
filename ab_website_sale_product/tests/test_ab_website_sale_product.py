from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestAbWebsiteSaleProduct(TransactionCase):
    def test_sync_ab_product_creates_published_ecommerce_product(self):
        group = self.env["ab_product_group"].create({"name": "Website Test Group"})
        tag = self.env["ab_product_tag"].create({"name": "Website Test Tag", "priority": 4})
        barcode = self.env["ab_product_barcode"].create({"name": "ABWEBTEST001"})
        card = self.env["ab_product_card"].create({
            "name": "Website Test Product",
            "description": "Visible in the shop.",
            "groups_ids": [fields.Command.set(group.ids)],
        })
        product = self.env["ab_product"].create({
            "product_card_id": card.id,
            "code": "AB-WEB-TEST-001",
            "default_price": 25.5,
            "default_cost": 10.0,
            "tag_ids": [fields.Command.set(tag.ids)],
            "barcode_ids": [fields.Command.set(barcode.ids)],
            "website_sale_available": True,
        })

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
