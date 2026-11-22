import base64
from io import BytesIO
from unittest.mock import patch

from lxml import etree
from PIL import Image

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestStorefrontImageFilter(TransactionCase):
    def test_abdin_product_search_view_translates_image_filter(self):
        labels = {}
        for lang in ("en_US", "ar_001"):
            view = self.env["ab_product"].with_context(lang=lang).get_view(view_type="search")
            root = etree.fromstring(view["arch"].encode())
            filters = root.xpath("//filter[@name='filter_storefront_image']")
            self.assertEqual(len(filters), 1)
            labels[lang] = filters[0].get("string")
        self.assertEqual(labels["en_US"], "Has Storefront Image")
        self.assertNotEqual(labels["ar_001"], labels["en_US"])
        self.assertTrue(any("\u0600" <= character <= "\u06ff" for character in labels["ar_001"]))

    def test_abdin_product_filter_excludes_placeholder_and_tracks_image_changes(self):
        source = self.env["ab_product"].create({
            "name": "Image filter product",
            "product_card_name": "Image filter product",
            "code": "STOREFRONT-IMAGE-FILTER",
        })
        template = self.env["product.template"].create({
            "name": source.name,
            "ab_product_id": source.id,
            "list_price": source.default_price,
        })
        domain = [
            ("id", "=", source.id),
            ("website_sync_template_ids", "any", [("ab_storefront_has_real_image", "=", True)]),
        ]
        self.assertFalse(self.env["ab_product"].search(domain))

        template.image_1920 = source._get_website_placeholder_image()
        self.assertFalse(self.env["ab_product"].search(domain))
        self.assertTrue(template.image_256)
        self.env.flush_all()
        self.assertTrue(self.env["ir.attachment"].search_count([
            ("res_model", "=", "product.template"),
            ("res_id", "=", template.id),
            ("res_field", "=", "image_256"),
        ]))
        attachment_model = type(self.env["ir.attachment"])
        search_fetch = attachment_model.search_fetch

        def reverse_attachment_order(attachments, attachment_domain, field_names, **kwargs):
            return search_fetch(attachments, attachment_domain, field_names, **kwargs).sorted(
                key=lambda attachment: attachment.res_field,
                reverse=True,
            )

        with patch.object(attachment_model, "search_fetch", reverse_attachment_order):
            template._compute_ab_storefront_has_real_image()
            self.assertFalse(template.ab_storefront_has_real_image)

        image = BytesIO()
        Image.new("RGB", (2, 2), (20, 70, 120)).save(image, format="PNG")
        template.image_1920 = base64.b64encode(image.getvalue())
        self.assertEqual(self.env["ab_product"].search(domain), source)

        template.image_1920 = False
        self.assertFalse(self.env["ab_product"].search(domain))
