from odoo.tests.common import TransactionCase


class TestWebsiteCategoryMapping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Group = cls.env["ab_product_group"]

    def test_l3_group_maps_to_canonical_category(self):
        group = self.Group.create({"name": "Body Care L3"})

        category = group._get_or_create_website_category()

        self.assertEqual(category.name, "Body Care")
        self.assertEqual(category.parent_id.name, "Beauty & Skin Care")

    def test_brand_group_does_not_become_raw_category(self):
        existing_categories = self.env["product.public.category"].search_count([
            ("name", "=", "Limitless"),
        ])
        group = self.Group.create({"name": "Limitless"})

        category = group._get_or_create_website_category()

        self.assertFalse(category)
        self.assertFalse(group.website_public_category_id)
        self.assertEqual(
            self.env["product.public.category"].search_count([("name", "=", "Limitless")]),
            existing_categories,
        )

    def test_unknown_only_product_group_uses_everyday_essentials(self):
        group = self.Group.create({"name": "Unknown Brand Name"})

        categories = group._get_or_create_website_categories()

        self.assertEqual(categories.name, "Everyday Essentials")

    def test_missing_product_image_gets_placeholder(self):
        card = self.env["ab_product_card"].create({
            "name": "Placeholder Test Product",
        })
        product = self.env["ab_product"].create({
            "product_card_id": card.id,
            "code": "PLACEHOLDER-TEST",
            "allow_sale": True,
            "allow_purchase": True,
            "active": True,
            "website_sale_available": True,
        })

        template = product._sync_website_products()

        self.assertTrue(template.image_1920)
