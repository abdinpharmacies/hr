import base64
import hashlib
from io import BytesIO
import os
import tempfile
from unittest.mock import MagicMock, patch

from PIL import Image

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
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
        cls.env["ir.config_parameter"].sudo().set_param("ir_attachment.location", "db")
        cls.Group = cls.env["ab_product_group"].with_context(lang="en_US")
        cls.env["ab_product_classification_taxonomy"].with_context(lang="en_US").action_prepare()

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

        template = product._sync_website_products(create_missing=True)

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
        product._sync_website_products(create_missing=True)
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

    def test_image_sync_creates_unpublished_template_for_unlinked_product(self):
        product = self.env["ab_product"].create({
            "name": "Unlinked image product",
            "product_card_name": "Unlinked image product",
            "code": "IMG-UNLINKED",
            "active": True,
            "allow_sale": True,
            "website_sale_available": False,
        })
        Service = self.env["ab.website.product.image.sync.service"]
        self.assertIn(product, Service._get_website_products([("id", "=", product.id)]))
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-UNLINKED.png")
            plan = self._plan_for(root, product)
            self.assertEqual(self._single_product_line(plan, product)["status"], "matched")
            result = Service.apply_sync_plan(plan)

        template = product.website_product_tmpl_id
        self.assertEqual(result["summary"]["updated"], 1)
        self.assertTrue(template)
        self.assertFalse(template.is_published)
        self.assertEqual(template.image_1920, base64.b64encode(PNG_1X1))

    def test_image_sync_includes_archived_unlinked_product(self):
        product = self.env["ab_product"].create({
            "name": "Archived image product",
            "product_card_name": "Archived image product",
            "code": "IMG-ARCHIVED",
            "active": False,
            "allow_sale": True,
            "website_sale_available": False,
        })
        service = self.env["ab.website.product.image.sync.service"]
        self.assertIn(product, service._get_website_products([("id", "=", product.id)]))
        with tempfile.TemporaryDirectory() as root:
            self._write_image(root, "IMG-ARCHIVED.png")
            plan = service.prepare_sync_plan(root, product_domain=[("id", "=", product.id)])
            self.assertEqual(self._single_product_line(plan, product)["status"], "matched")
            result = service.apply_sync_plan(plan)

        template = product.website_product_tmpl_id
        self.assertEqual(result["summary"]["updated"], 1)
        self.assertFalse(product.active)
        self.assertTrue(template)
        self.assertFalse(template.active)
        self.assertFalse(template.is_published)
        self.assertEqual(template.image_1920, base64.b64encode(PNG_1X1))

    def test_non_admin_cannot_call_image_sync_service(self):
        Service = self.env["ab.website.product.image.sync.service"].with_user(
            self.env.ref("base.public_user")
        )
        with self.assertRaises(AccessError):
            Service.prepare_sync_plan("/tmp")
        with self.assertRaises(AccessError):
            Service.apply_sync_plan({"summary": {}, "report": []})

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


@tagged("post_install", "-at_install")
class TestImagePublication(TransactionCase):
    def setUp(self):
        super().setUp()
        self.service = self.env["ab.website.product.image.sync.service"].with_context(lang="en_US")
        self.product = self.env["ab_product"].create({
            "product_card_name": "Publication image", "code": "IMG-PUBLISH-NEW",
            "eplus_serial": 99888776, "default_price": 10,
            "active": True, "allow_sale": True, "website_sale_available": True,
        })
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        with open(os.path.join(self.root.name, self.product.code + ".png"), "wb") as image:
            image.write(PNG_1X1)

    def plan(self):
        return self.service.prepare_sync_plan(self.root.name, products=self.product)

    def fallback_catalog(self, **values):
        source = dict(item_id=99888777, price=67.5, active=True, name="Fallback product")
        source.update(values)
        code = "IMG-EPLUS-NEW"
        with open(os.path.join(self.root.name, code + ".png"), "wb") as image:
            image.write(PNG_1X1)
        return {code: [source]}

    def publication_plan(self, catalog):
        with patch.object(type(self.env["ab_eplus_stock_snapshot"]), "_fetch_image_fallback_catalog", return_value=catalog):
            return self.service.prepare_publication_sync_plan(self.root.name)

    def test_image_creates_links_prices_and_publishes(self):
        self.product._sync_website_products(create_missing=True).list_price = 5
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        template = self.product.website_product_tmpl_id
        self.assertEqual(result["summary"]["updated"], 1)
        self.assertEqual(template.ab_product_id, self.product)
        self.assertEqual(template.list_price, 10)
        self.assertEqual(self.product.default_price, 10)
        self.assertTrue(template.is_published)
        self.assertTrue(template.message_ids.filtered(lambda msg: "Image publication:" in str(msg.body)))

    def test_unchanged_image_republishes_without_duplicate_template(self):
        self.service.apply_sync_plan(self.plan(), publish_requested=True)
        template = self.product.website_product_tmpl_id
        template.is_published = False
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertTrue(template.is_published)
        self.assertEqual(self.product.website_product_tmpl_id, template)
        self.assertEqual(result["summary"]["updated"], 0)

    def test_invalid_master_price_does_not_fall_back(self):
        for price in (0, -1):
            with self.subTest(price=price):
                self.product.default_price = price
                with patch.object(type(self.env["ab_eplus_stock_snapshot"]), "_fetch_image_fallback_catalog") as fetch:
                    plan = self.service.prepare_publication_sync_plan(self.root.name)
                    result = self.service.apply_sync_plan(plan, publish_requested=True)
                fetch.assert_not_called()
                self.assertEqual(result["summary"]["error"], 1)
                self.assertFalse(self.product.website_product_tmpl_id)
                self.assertEqual(self.product.default_price, price)

    def test_imported_draft_becomes_saleable_after_valid_price(self):
        self.product.write({"eplus_catalog_draft": True, "allow_sale": False, "website_sale_available": False})
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["updated"], 1)
        self.assertFalse(self.product.allow_sale)
        self.assertFalse(self.product.website_sale_available)
        self.assertTrue(self.product.eplus_catalog_draft)
        self.assertTrue(self.product.website_product_tmpl_id.is_published)

    def test_archived_source_stays_archived_while_website_is_published(self):
        self.product.write({"active": False, "allow_sale": False, "website_sale_available": False})
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["published"], 1)
        template = self.product.website_product_tmpl_id
        self.assertTrue(template.active)
        self.assertTrue(template.sale_ok)
        self.assertTrue(template.is_published)
        self.assertFalse(self.product.active)
        self.product._sync_website_products()
        self.assertTrue(template.active)
        self.assertTrue(template.sale_ok)
        self.assertTrue(template.is_published)

    def test_conflicting_fallback_identity_is_not_adopted(self):
        template = self.env["product.template"].create({
            "name": "Different external item", "default_code": self.product.code,
            "website_eplus_item_id": self.product.eplus_serial + 1,
        })
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["ambiguous"], 1)
        self.assertFalse(template.ab_product_id)
        self.assertFalse(template.is_published)

    def test_existing_fallback_identity_with_changed_code_is_not_duplicated(self):
        template = self.env["product.template"].create({
            "name": "Existing external item", "default_code": "OLD-ITEM-CODE",
            "website_eplus_item_id": self.product.eplus_serial,
        })
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["ambiguous"], 1)
        self.assertFalse(template.ab_product_id)
        self.assertFalse(self.product.website_product_tmpl_id)

    def test_fallback_template_outside_selected_company_is_not_modified(self):
        self.service = self.service.with_context(allowed_company_ids=self.env.company.ids)
        company = self.env["res.company"].create({"name": "Foreign fallback company"})
        template = self.env["product.template"].create({
            "name": "Foreign item", "default_code": "IMG-EPLUS-NEW", "company_id": company.id,
        })
        result = self.service.apply_sync_plan(self.publication_plan(self.fallback_catalog()), publish_requested=True)
        self.assertEqual(result["summary"]["error"], 1)
        self.assertFalse(template.is_published)
        self.assertFalse(template.website_eplus_item_id)

    def test_fallback_query_is_parameterized_and_batched(self):
        snapshot = self.env["ab_eplus_stock_snapshot"]
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [(99888777, "SAFE-CODE", 67.5, True, "Fallback", None)]
        codes = ["CODE-%s" % number for number in range(200)] + ["X'); DROP TABLE Item_Catalog; --"]
        with patch.object(type(snapshot), "_connect_eplus_read", return_value=connection):
            catalog = snapshot._fetch_image_fallback_catalog(codes)
        self.assertEqual(cursor.execute.call_count, 2)
        for call, expected in zip(cursor.execute.call_args_list, (codes[:200], codes[200:])):
            sql, params = call.args
            self.assertTrue(sql.startswith("SELECT "))
            self.assertEqual(sql.count("%s"), len(expected))
            self.assertEqual(params, tuple(expected))
            self.assertNotIn(codes[-1], sql)
            self.assertNotIn("NOLOCK", sql)
        self.assertEqual(catalog["SAFE-CODE"][0]["price"], 67.5)

    def test_public_user_cannot_refresh_or_publish(self):
        service = self.service.with_user(self.env.ref("base.public_user"))
        with self.assertRaises(AccessError):
            service.prepare_publication_sync_plan(self.root.name)
        with self.assertRaises(AccessError):
            service.apply_sync_plan(self.plan(), publish_requested=True)

    def test_replicated_code_publishes_without_eplus(self):
        with patch.object(type(self.env["ab_eplus_stock_snapshot"]), "_fetch_image_fallback_catalog", side_effect=UserError("Offline")) as fetch:
            result = self.service.apply_sync_plan(
                self.service.prepare_publication_sync_plan(self.root.name), publish_requested=True,
            )
        fetch.assert_not_called()
        self.assertEqual(result["summary"]["published"], 1)
        self.assertEqual(self.product.website_product_tmpl_id.list_price, self.product.default_price)

    def test_fallback_failure_does_not_block_replicated_products(self):
        self.fallback_catalog()
        for error in (UserError("Offline"), RuntimeError("External connection failed")):
            with self.subTest(error=type(error).__name__):
                with patch.object(type(self.env["ab_eplus_stock_snapshot"]), "_fetch_image_fallback_catalog", side_effect=error):
                    result = self.service.apply_sync_plan(
                        self.service.prepare_publication_sync_plan(self.root.name), publish_requested=True,
                    )
                self.assertEqual(result["summary"]["error"], 1)
                self.assertEqual(result["summary"]["published"], 1)
                self.assertTrue(self.product.website_product_tmpl_id.is_published)

    def test_missing_code_fallback_is_reused_and_later_linked_to_master(self):
        catalog = self.fallback_catalog()
        result = self.service.apply_sync_plan(self.publication_plan(catalog), publish_requested=True)
        self.assertEqual(result["summary"]["published"], 2)
        code = next(iter(catalog))
        Product = self.env["ab_product"].with_context(active_test=False)
        self.assertFalse(Product.search([("code", "=", code)]))
        template = self.env["product.template"].search([("default_code", "=", code)])
        self.assertTrue(template.is_published)
        self.assertEqual(template.list_price, 67.5)
        self.assertEqual(template.website_eplus_item_id, 99888777)
        self.service.apply_sync_plan(self.publication_plan(catalog), publish_requested=True)
        self.assertEqual(self.env["product.template"].search([("default_code", "=", code)]), template)
        master = self.product.copy({"code": code, "eplus_serial": 99888777, "default_price": 73})
        with patch.object(type(self.env["ab_eplus_stock_snapshot"]), "_fetch_image_fallback_catalog") as fetch:
            self.service.apply_sync_plan(self.service.prepare_publication_sync_plan(self.root.name), publish_requested=True)
        fetch.assert_not_called()
        self.assertEqual(master.website_product_tmpl_id, template)
        self.assertEqual(template.list_price, 73)
        self.assertTrue(template.is_published)

    def test_fallback_invalid_price_name_and_duplicate_rows_are_rejected(self):
        for values in ({"price": 0}, {"price": -1}, {"price": float("nan")}, {"price": float("inf")}, {"name": ""}):
            with self.subTest(values=values):
                result = self.service.apply_sync_plan(self.publication_plan(self.fallback_catalog(**values)), publish_requested=True)
                self.assertEqual(result["summary"]["error"], 1)
                self.assertFalse(self.env["product.template"].search([("website_eplus_item_id", "=", 99888777)]))
        catalog = self.fallback_catalog()
        catalog["IMG-EPLUS-NEW"] *= 2
        result = self.service.apply_sync_plan(self.publication_plan(catalog), publish_requested=True)
        self.assertEqual(result["summary"]["error"], 1)

    def test_unknown_code_is_reported_without_creation(self):
        self.fallback_catalog()
        result = self.service.apply_sync_plan(self.publication_plan({}), publish_requested=True)
        missing = [line for line in result["report"] if line.get("relative_path") == "IMG-EPLUS-NEW.png"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["status"], "missing")
        self.assertFalse(self.env["product.template"].search([("default_code", "=", "IMG-EPLUS-NEW")]))

    def test_fallback_different_code_for_existing_source_identity_is_rejected(self):
        catalog = self.fallback_catalog(item_id=self.product.eplus_serial)
        result = self.service.apply_sync_plan(self.publication_plan(catalog), publish_requested=True)
        self.assertEqual(result["summary"]["error"], 1)
        self.assertFalse(self.env["product.template"].search([("default_code", "=", "IMG-EPLUS-NEW")]))

    def test_archived_fallback_template_is_reactivated(self):
        catalog = self.fallback_catalog(active=False)
        template = self.env["product.template"].create({
            "name": "Archived fallback", "default_code": "IMG-EPLUS-NEW", "active": False,
        })
        self.service.apply_sync_plan(self.publication_plan(catalog), publish_requested=True)
        self.assertTrue(template.active)
        self.assertTrue(template.is_published)
        self.assertEqual(template.list_price, 67.5)
        self.assertFalse(template.ab_product_id)

    def _different_image(self):
        output = BytesIO()
        Image.new("RGB", (1, 1), (0, 0, 255)).save(output, format="PNG")
        return output.getvalue()

    def test_fallback_replacement_requires_confirmation(self):
        catalog = self.fallback_catalog()
        template = self.env["product.template"].create({
            "name": "Existing fallback", "default_code": "IMG-EPLUS-NEW",
            "image_1920": base64.b64encode(self._different_image()),
        })
        plan = self.publication_plan(catalog)
        lines = [line for line in plan["report"] if line.get("eplus_item_id")]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0]["replaces_existing"])
        wizard = self.env["ab.website.sale.add.many.by.codes.wizard"].create({})
        wizard._write_image_sync_report(plan, confirmation_required=True)
        self.assertTrue(wizard.image_sync_confirmation_required)
        self.assertEqual(wizard.image_sync_line_ids.filtered("eplus_item_id").eplus_item_id, 99888777)
        self.assertFalse(template.is_published)

    def test_publication_does_not_write_master_product(self):
        template = self.product._sync_website_products(create_missing=True)
        plan = self.plan()
        with patch.object(type(self.product), "write", side_effect=AccessError("Product replica is read only")):
            result = self.service.apply_sync_plan(plan, publish_requested=True)
        self.assertEqual(result["summary"]["published"], 1)
        self.assertEqual(template.list_price, 10)
        self.assertTrue(template.is_published)

    def test_reuses_archived_unlinked_template_and_preserves_master(self):
        template = self.env["product.template"].create({
            "name": "Existing store product", "default_code": self.product.code,
            "active": False, "list_price": 10,
        })
        self.product.active = False
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["published"], 1)
        self.assertEqual(self.product.website_product_tmpl_id, template)
        self.assertTrue(template.active)
        self.assertTrue(template.is_published)
        self.assertFalse(self.product.active)
        self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(self.env["product.template"].with_context(active_test=False).search_count([
            ("default_code", "=", self.product.code),
        ]), 1)

    def test_duplicate_template_codes_require_review(self):
        self.env["product.template"].create([
            {"name": "First", "default_code": self.product.code},
            {"name": "Second", "default_code": self.product.code, "active": False},
        ])
        plan = self.plan()
        self.assertEqual(plan["summary"]["ambiguous"], 1)
        result = self.service.apply_sync_plan(plan, publish_requested=True)
        self.assertFalse(result["summary"]["published"])
        self.assertFalse(self.product.website_product_tmpl_id)

    def test_foreign_company_template_is_not_adopted(self):
        self.service = self.service.with_context(allowed_company_ids=self.env.company.ids)
        company = self.env["res.company"].create({"name": "Other image company"})
        template = self.env["product.template"].create({
            "name": "Other company product", "default_code": self.product.code,
            "company_id": company.id,
        })
        plan = self.plan()
        self.assertEqual(plan["summary"]["ambiguous"], 1)
        self.service.apply_sync_plan(plan, publish_requested=True)
        self.assertFalse(template.ab_product_id)
        self.assertFalse(self.product.website_product_tmpl_id)

    def test_existing_code_link_to_another_source_is_not_reassigned(self):
        other = self.product.copy({"code": "OTHER-SOURCE", "eplus_serial": 99888778})
        template = other._sync_website_products(create_missing=True)
        template.default_code = self.product.code
        plan = self.plan()
        self.assertEqual(plan["summary"]["ambiguous"], 1)
        self.service.apply_sync_plan(plan, publish_requested=True)
        self.assertEqual(template.ab_product_id, other)
        self.assertFalse(self.product.website_product_tmpl_id)


class TestImageSyncCompletion(TransactionCase):
    def setUp(self):
        super().setUp()
        self.wizard = self.env["ab.website.sale.add.many.by.codes.wizard"].with_context(lang="en_US").create({})
        self.report_action = {"type": "ir.actions.act_window", "res_id": self.wizard.id, "target": "new"}

    def completion(self, summary, report=None):
        with patch.object(type(self.wizard), "_write_image_sync_report", return_value=self.report_action):
            return self.wizard._image_sync_completion_action({"summary": summary, "report": report or []})

    def test_success_keeps_report_and_confirms_real_counts(self):
        action = self.completion({"published": 12, "updated": 8, "unchanged": 4, "missing": 35000})
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        self.assertEqual(action["params"]["next"], self.report_action)
        self.assertTrue(action["params"]["sticky"])
        self.assertIn("Published products: 12", action["params"]["message"])
        self.assertIn("Updated images: 8", action["params"]["message"])

    def test_completion_provides_views_for_direct_client_action(self):
        view = self.env.ref("ab_website_sale_product.view_sync_images_wizard_form")
        for summary in ({"published": 197, "unchanged": 197}, {"error": 1}, {}):
            with self.subTest(summary=summary):
                action = self.wizard._image_sync_completion_action({
                    "summary": summary, "report": [], "image_root": "/tmp",
                })
                next_action = action["params"]["next"]
                self.assertEqual(next_action["type"], "ir.actions.act_window")
                self.assertEqual(next_action["res_model"], self.wizard._name)
                self.assertEqual(next_action["res_id"], self.wizard.id)
                self.assertEqual(next_action["target"], "new")
                self.assertEqual(next_action["views"], [(view.id, "form")])

    def test_failures_are_not_reported_as_complete_success(self):
        action = self.completion({"published": 2, "error": 1, "invalid": 1, "ambiguous": 1}, [{
            "status": "missing", "image_path": "/tmp/unmatched.png", "product_id": False,
        }])
        self.assertEqual(action["params"]["type"], "warning")
        self.assertIn("Items requiring review: 4", action["params"]["message"])

    def test_no_matches_has_informational_result(self):
        action = self.completion({"missing": 35000})
        self.assertEqual(action["params"]["type"], "info")
        self.assertEqual(action["params"]["title"], "No images were synchronized")

    def test_confirmation_and_sync_paths_notify_only_after_execution(self):
        service = self.env["ab.website.product.image.sync.service"]
        plan = {"summary": {}, "report": []}
        result = {"summary": {"published": 3}, "report": []}
        for method in ("action_sync_images", "action_confirm_replace_images", "action_sync_new_images_only"):
            with self.subTest(method=method), \
                 patch.object(type(self.wizard), "_prepare_image_sync_plan", return_value=(service, plan)), \
                 patch.object(type(service), "apply_sync_plan", return_value=result) as apply, \
                 patch.object(type(self.wizard), "_write_image_sync_report", return_value=self.report_action):
                action = getattr(self.wizard, method)()
                apply.assert_called_once()
                self.assertEqual(action["params"]["type"], "success")
                self.assertIn("Published products: 3", action["params"]["message"])

    def test_replacement_question_does_not_claim_completion(self):
        service = self.env["ab.website.product.image.sync.service"]
        plan = {"summary": {"replacements": 1}, "report": []}
        with patch.object(type(self.wizard), "_prepare_image_sync_plan", return_value=(service, plan)), \
             patch.object(type(service), "apply_sync_plan") as apply, \
             patch.object(type(self.wizard), "_write_image_sync_report", return_value=self.report_action):
            action = self.wizard.action_sync_images()
        apply.assert_not_called()
        self.assertEqual(action, self.report_action)
