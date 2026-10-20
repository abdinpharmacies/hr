import base64
import hashlib
from io import BytesIO
import os
import tempfile
from unittest.mock import patch

from PIL import Image

from odoo.tests.common import TransactionCase


def _make_png_1x1():
    output = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(output, format="PNG")
    return output.getvalue()


PNG_1X1 = _make_png_1x1()


class TestWebsiteCategoryMapping(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Group = cls.env["ab_product_group"]
        cls.env["ab_product_classification_taxonomy"].action_prepare()

    def test_l3_group_maps_to_canonical_category(self):
        group = self.Group.create({"name": "Body Care L3"})

        category = group._get_or_create_website_category()

        self.assertEqual(category.name, "Body Care")
        self.assertEqual(category.parent_id.name, "Skin Care & Beauty")

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

    def test_unknown_only_product_group_has_no_fallback(self):
        group = self.Group.create({"name": "Unknown Brand Name"})

        categories = group._get_or_create_website_categories()

        self.assertFalse(categories)

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

    def _create_website_product(self, code):
        card = self.env["ab_product_card"].create({
            "name": "Image Sync %s" % code,
        })
        product = self.env["ab_product"].create({
            "product_card_id": card.id,
            "code": code,
            "allow_sale": True,
            "allow_purchase": True,
            "active": True,
            "website_sale_available": True,
        })
        product._sync_website_products()
        return product

    def _write_image(self, root, relative_path, payload=PNG_1X1):
        image_path = os.path.join(root, relative_path)
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        with open(image_path, "wb") as image_file:
            image_file.write(payload)
        return image_path

    def _plan_for(self, root, product):
        return self.env["ab.website.product.image.sync.service"].prepare_sync_plan(
            root,
            products=product,
        )

    def _single_product_line(self, plan, product):
        lines = [line for line in plan["report"] if line.get("product_id") == product.id]
        self.assertEqual(len(lines), 1)
        return lines[0]

    def _guard_product_image_reads(self):
        image_field_type = type(self.env["product.template"]._fields["image_1920"])
        original_read = image_field_type.read

        def read(field, records):
            self.assertFalse(
                records._name == "product.template" and field.name == "image_1920",
                "Product image payload loaded during planning",
            )
            return original_read(field, records)

        return patch.object(image_field_type, "read", read)

    def test_flat_image_matches_product_code(self):
        product = self._create_website_product("IMG-FLAT")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-FLAT.jpg")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "matched")
        self.assertEqual(line["match_method"], "code")
        self.assertEqual(line["relative_path"], "IMG-FLAT.jpg")

    def test_external_serial_cannot_match_another_products_image(self):
        owner = self._create_website_product("98520001")
        recipient = self._create_website_product("98520002")
        recipient.eplus_serial = int(owner.code)
        template = recipient.website_product_tmpl_id
        output = BytesIO()
        Image.new("RGB", (1, 1), (20, 40, 60)).save(output, format="PNG")
        template.image_1920 = base64.b64encode(output.getvalue())
        original_image = template.image_1920
        service = self.env["ab.website.product.image.sync.service"]

        for relative_path in ("98520001.png", "98520001/main.png"):
            with self.subTest(relative_path=relative_path), tempfile.TemporaryDirectory() as root:
                self._write_image(root, relative_path)
                plan = self._plan_for(root, owner | recipient)
                owner_line = self._single_product_line(plan, owner)
                recipient_line = self._single_product_line(plan, recipient)
                self.assertEqual(owner_line["match_method"], "code")
                self.assertEqual(recipient_line["status"], "missing")
                self.assertFalse(recipient_line["image_path"])
                service.apply_sync_plan(self._plan_for(root, recipient))
                self.assertEqual(template.image_1920, original_image)

    def test_product_code_image_wins_over_external_serial(self):
        product = self._create_website_product("98520002")
        product.eplus_serial = 98520001
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "98520001/main.png")
            self._write_image(root, "98520002.png")
            line = self._single_product_line(self._plan_for(root, product), product)
        self.assertEqual(line["match_method"], "code")
        self.assertEqual(line["relative_path"], "98520002.png")

    def test_barcode_image_matching_is_preserved(self):
        product = self._create_website_product("IMG-BARCODE")
        barcode = self.env["ab_product_barcode"].create({"name": "9988776655443"})
        product.barcode_ids = barcode
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "9988776655443.png")
            line = self._single_product_line(self._plan_for(root, product), product)
        self.assertEqual(line["match_method"], "barcode")
        self.assertEqual(line["matched_identifier"], barcode.name)

    def test_nested_product_folder_matches_product_code(self):
        product = self._create_website_product("IMG-NESTED")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-NESTED/main.jpg")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "matched")
        self.assertEqual(line["relative_path"], os.path.join("IMG-NESTED", "main.jpg"))

    def test_deep_nested_product_folder_matches_product_code(self):
        product = self._create_website_product("IMG-DEEP")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "products/pharmacy/IMG-DEEP/main.webp")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "matched")
        self.assertEqual(line["relative_path"], os.path.join("products", "pharmacy", "IMG-DEEP", "main.webp"))

    def test_uppercase_image_extension_is_supported(self):
        product = self._create_website_product("IMG-UPPER")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-UPPER.PNG")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "matched")
        self.assertEqual(line["relative_path"], "IMG-UPPER.PNG")

    def test_missing_image_does_not_remove_existing_odoo_image(self):
        product = self._create_website_product("IMG-MISSING")
        template = product.website_product_tmpl_id
        template.image_1920 = base64.b64encode(PNG_1X1)
        existing_image = template.image_1920
        with tempfile.TemporaryDirectory() as root:
            plan = self._plan_for(root, product)
            result = self.env["ab.website.product.image.sync.service"].apply_sync_plan(plan)

        line = self._single_product_line(result, product)
        self.assertEqual(line["status"], "missing")
        self.assertEqual(template.image_1920, existing_image)

    def test_ambiguous_images_are_not_selected_randomly(self):
        product = self._create_website_product("IMG-AMBIG")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-AMBIG/a.jpg")
            self._write_image(root, "IMG-AMBIG/b.jpg")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "ambiguous")

    def test_main_image_has_priority_over_numbered_images(self):
        product = self._create_website_product("IMG-MAIN")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-MAIN/01.jpg")
            self._write_image(root, "IMG-MAIN/main.jpg")
            self._write_image(root, "IMG-MAIN/02.jpg")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "matched")
        self.assertEqual(line["relative_path"], os.path.join("IMG-MAIN", "main.jpg"))

    def test_corrupt_image_reports_invalid_without_crashing(self):
        product = self._create_website_product("IMG-CORRUPT")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-CORRUPT.jpg", payload=b"not-an-image")

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "invalid")

    def test_unchanged_image_is_not_marked_for_update(self):
        product = self._create_website_product("IMG-SAME")
        Service = self.env["ab.website.product.image.sync.service"]
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-SAME.jpg")
            Service.apply_sync_plan(self._plan_for(root, product))

            line = self._single_product_line(self._plan_for(root, product), product)

        self.assertEqual(line["status"], "unchanged")

    def test_image_checksum_does_not_read_base64_image_field(self):
        product = self._create_website_product("IMG-ATTACHMENT")
        template = product.website_product_tmpl_id
        expected_checksum = hashlib.sha256(PNG_1X1).hexdigest()

        template.image_1920 = base64.b64encode(PNG_1X1)
        template.invalidate_recordset(["image_1920"])
        with self._guard_product_image_reads():
            checksum = self.env["ab.website.product.image.sync.service"]._template_image_sha256(template)

        self.assertEqual(checksum, expected_checksum)

    def test_sync_button_requests_replacement_without_loading_images(self):
        product = self._create_website_product("IMG-BUTTON")
        template = product.website_product_tmpl_id
        template.image_1920 = base64.b64encode(PNG_1X1)
        original_checksum = hashlib.sha256(PNG_1X1).hexdigest()
        output = BytesIO()
        Image.new("RGB", (1, 1), (20, 40, 60)).save(output, format="PNG")
        service = self.env["ab.website.product.image.sync.service"]

        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-BUTTON.png", payload=output.getvalue())
            wizard = self.env["ab.website.sale.add.many.by.codes.wizard"].create({
                "directory_path": root,
            })
            self.env.flush_all()
            template.invalidate_recordset(["image_1920"])
            with (
                patch.object(type(service), "_get_website_products", return_value=product),
                self._guard_product_image_reads(),
            ):
                wizard.action_preview_images()
                action = wizard.action_sync_images()

        self.assertEqual(action["res_id"], wizard.id)
        self.assertTrue(wizard.image_sync_confirmation_required)
        self.assertEqual(wizard.image_sync_replacement_count, 1)
        self.assertEqual(wizard.image_sync_line_ids.status, "matched")
        self.assertTrue(wizard.image_sync_line_ids.replaces_existing)
        self.assertEqual(service._template_image_sha256(template), original_checksum)

    def test_image_plan_distinguishes_empty_placeholder_and_unchanged_without_loading_images(self):
        empty = self._create_website_product("IMG-EMPTY")
        placeholder = self._create_website_product("IMG-PLACEHOLDER")
        unchanged = self._create_website_product("IMG-UNCHANGED")
        products = empty | placeholder | unchanged
        templates = products.mapped("website_product_tmpl_id")
        empty.website_product_tmpl_id.image_1920 = False
        placeholder.website_product_tmpl_id.image_1920 = base64.b64encode(PNG_1X1)
        output = BytesIO()
        Image.new("RGB", (1, 1), (20, 40, 60)).save(output, format="PNG")
        unchanged.website_product_tmpl_id.image_1920 = base64.b64encode(output.getvalue())
        service = self.env["ab.website.product.image.sync.service"]

        with tempfile.TemporaryDirectory() as root:
            for product in products:
                self._write_image(root, product.code + ".png", payload=output.getvalue())
            self.env.flush_all()
            templates.invalidate_recordset(["image_1920"])
            with (
                patch.object(type(service), "_placeholder_image_sha256",
                             return_value=hashlib.sha256(PNG_1X1).hexdigest()),
                self._guard_product_image_reads(),
            ):
                plan = self._plan_for(root, products)

        self.assertEqual(plan["summary"]["new_images"], 2)
        self.assertEqual(plan["summary"]["replacements"], 0)
        self.assertEqual(plan["summary"]["unchanged"], 1)
        for product in empty | placeholder:
            line = self._single_product_line(plan, product)
            self.assertEqual(line["status"], "matched")
            self.assertFalse(line["replaces_existing"])
        self.assertEqual(self._single_product_line(plan, unchanged)["status"], "unchanged")

    def test_changed_image_replaces_previous_and_repeated_plan_is_noop(self):
        product = self._create_website_product("IMG-CHANGED")
        Service = self.env["ab.website.product.image.sync.service"]
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-CHANGED.png")
            Service.apply_sync_plan(self._plan_for(root, product))
            output = BytesIO()
            Image.new("RGB", (1, 1), (20, 40, 60)).save(output, format="PNG")
            self._write_image(root, "IMG-CHANGED.png", payload=output.getvalue())
            plan = self._plan_for(root, product)
            result = Service.apply_sync_plan(plan)
            self.assertEqual(result["summary"]["updated"], 1)
            self.assertEqual(product.website_product_tmpl_id.image_1920, base64.b64encode(output.getvalue()))
            result = Service.apply_sync_plan(plan)
            self.assertEqual(result["summary"]["updated"], 0)
            self.assertEqual(self._single_product_line(result, product)["status"], "unchanged")

    def test_resized_source_image_is_unchanged_and_manual_edit_detected(self):
        product = self._create_website_product("IMG-RESIZED")
        Service = self.env["ab.website.product.image.sync.service"]
        output = BytesIO()
        Image.new("RGB", (2000, 40), (20, 40, 60)).save(output, format="PNG")
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-RESIZED.png", payload=output.getvalue())
            Service.apply_sync_plan(self._plan_for(root, product))
            template = product.website_product_tmpl_id
            self.assertNotEqual(template.website_image_source_checksum, template.website_image_applied_checksum)
            plan = self._plan_for(root, product)
            self.assertEqual(self._single_product_line(plan, product)["status"], "unchanged")
            template.image_1920 = base64.b64encode(PNG_1X1)
            plan = self._plan_for(root, product)
            self.assertEqual(self._single_product_line(plan, product)["status"], "matched")
