import base64
import hashlib
from io import BytesIO
import os
import tempfile
from unittest.mock import patch

from PIL import Image

from odoo.exceptions import AccessError
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


class TestImagePublication(TransactionCase):
    def setUp(self):
        super().setUp()
        self.service = self.env["ab.website.product.image.sync.service"]
        self.product = self.env["ab_product"].create({
            "product_card_name": "Publication image", "code": "IMG-PUBLISH-NEW",
            "eplus_serial": 99888776, "default_price": 10,
            "active": True, "allow_sale": True, "website_sale_available": True,
        })
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        with open(os.path.join(self.root.name, self.product.code + ".png"), "wb") as image:
            image.write(PNG_1X1)

    def plan(self, price=25):
        plan = self.service.prepare_sync_plan(self.root.name, products=self.product)
        plan["publication_prices"] = {self.product.code: [{
            "item_id": self.product.eplus_serial, "price": price, "active": True,
        }]}
        return plan

    def test_image_creates_links_prices_and_publishes(self):
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        template = self.product.website_product_tmpl_id
        self.assertEqual(result["summary"]["updated"], 1)
        self.assertEqual(template.ab_product_id, self.product)
        self.assertEqual(template.list_price, 25)
        self.assertEqual(self.product.default_price, 25)
        self.assertTrue(template.is_published)
        self.assertTrue(template.message_ids.filtered(lambda msg: "Eplus image publication" in str(msg.body)))

    def test_unchanged_image_republishes_without_duplicate_template(self):
        self.service.apply_sync_plan(self.plan(), publish_requested=True)
        template = self.product.website_product_tmpl_id
        template.is_published = False
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertTrue(template.is_published)
        self.assertEqual(self.product.website_product_tmpl_id, template)
        self.assertEqual(result["summary"]["updated"], 0)

    def test_invalid_price_rolls_back_image_and_publication(self):
        for price in (0, -1, float("nan"), float("inf")):
            with self.subTest(price=price):
                result = self.service.apply_sync_plan(self.plan(price), publish_requested=True)
                self.assertEqual(result["summary"]["error"], 1)
                self.assertFalse(self.product.website_product_tmpl_id)
                self.assertEqual(self.product.default_price, 10)

    def test_imported_draft_becomes_saleable_after_valid_price(self):
        self.product.write({"eplus_catalog_draft": True, "allow_sale": False, "website_sale_available": False})
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["updated"], 1)
        self.assertTrue(self.product.allow_sale)
        self.assertTrue(self.product.website_sale_available)
        self.assertFalse(self.product.eplus_catalog_draft)
        self.assertTrue(self.product.website_product_tmpl_id.is_published)

    def test_archived_product_remains_unpublished(self):
        self.product.active = False
        result = self.service.apply_sync_plan(self.plan(), publish_requested=True)
        self.assertEqual(result["summary"]["error"], 1)
        self.assertFalse(self.product.website_product_tmpl_id)
        self.assertFalse(self.product.active)

    def test_duplicate_or_conflicting_eplus_identity_is_rejected(self):
        for duplicate in (True, False):
            plan = self.plan()
            sources = plan["publication_prices"][self.product.code]
            if duplicate:
                sources.append(dict(sources[0]))
            else:
                sources[0]["item_id"] += 1
            result = self.service.apply_sync_plan(plan, publish_requested=True)
            self.assertEqual(result["summary"]["error"], 1)
            self.assertFalse(self.product.website_product_tmpl_id)

    def test_public_user_cannot_refresh_or_publish(self):
        service = self.service.with_user(self.env.ref("base.public_user"))
        with self.assertRaises(AccessError):
            service.prepare_publication_sync_plan(self.root.name)
        with self.assertRaises(AccessError):
            service.apply_sync_plan(self.plan(), publish_requested=True)

    def test_refresh_and_import_finish_before_image_matching(self):
        Snapshot = type(self.env["ab_eplus_stock_snapshot"])
        events = []
        row = self.env["ab_eplus_stock_snapshot"].create({
            "itm_id": self.product.eplus_serial, "itm_code": self.product.code, "itm_qty": 1,
        })
        with patch.object(Snapshot, "action_refresh_from_eplus", side_effect=lambda: events.append("refresh")), \
             patch.object(Snapshot, "_import_eplus_catalog_batch", side_effect=lambda: events.append("import")), \
             patch.object(type(self.service), "prepare_sync_plan", side_effect=lambda path: events.append("plan") or {"report": [], "summary": {"missing": 0}}):
            self.service.prepare_publication_sync_plan(self.root.name)
        self.assertEqual(events, ["refresh", "import", "plan"])

    def test_refresh_failure_prevents_image_application(self):
        from odoo.exceptions import UserError
        with patch.object(type(self.env["ab_eplus_stock_snapshot"]), "action_refresh_from_eplus", side_effect=UserError("Offline")):
            with self.assertRaises(UserError):
                self.service.prepare_publication_sync_plan(self.root.name)
        self.assertFalse(self.product.website_product_tmpl_id)

    def test_new_eplus_code_is_imported_priced_linked_and_published(self):
        from odoo.addons.integration_queue_job.tests.common import trap_jobs
        code = "IMG-EPLUS-NEW"
        item_id = 99888777
        with open(os.path.join(self.root.name, code + ".png"), "wb") as image:
            image.write(PNG_1X1)
        Snapshot = type(self.env["ab_eplus_stock_snapshot"])
        with trap_jobs(), \
             patch.object(Snapshot, "_fetch_eplus_stock_rows", return_value=[{
                 "itm_id": item_id, "itm_code": code, "itm_qty": 2, "extra_data": {},
             }]), \
             patch.object(Snapshot, "_fetch_eplus_catalog_names", return_value={
                 item_id: [(code, "Arabic product", "New Eplus product", True)],
             }), \
             patch.object(Snapshot, "_fetch_image_publication_prices", return_value={
                 code: [{"item_id": item_id, "price": 67.5, "active": True}],
                 self.product.code: [{"item_id": self.product.eplus_serial, "price": 10, "active": True}],
             }):
            plan = self.service.prepare_publication_sync_plan(self.root.name)
            result = self.service.apply_sync_plan(plan, publish_requested=True)
        product = self.env["ab_product"].search([("code", "=", code)])
        self.assertEqual(len(product), 1)
        self.assertEqual(product.eplus_serial, item_id)
        self.assertEqual(product.default_price, 67.5)
        self.assertEqual(product.website_product_tmpl_id.list_price, 67.5)
        self.assertTrue(product.website_product_tmpl_id.is_published)
        self.assertEqual(result["summary"]["published"], 2)

    def test_master_write_rejection_preserves_image_price_and_publication(self):
        template = self.product._sync_website_products(create_missing=True)
        old_image = template.image_1920
        plan = self.plan()
        with patch.object(type(self.product), "write", side_effect=AccessError("Product replica is read only")):
            result = self.service.apply_sync_plan(plan, publish_requested=True)
        self.assertEqual(result["summary"]["error"], 1)
        self.assertEqual(template.image_1920, old_image)
        self.assertEqual(template.list_price, 10)
        self.assertFalse(template.is_published)
