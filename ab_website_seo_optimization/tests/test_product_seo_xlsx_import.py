import base64
from io import BytesIO
from unittest.mock import patch

from openpyxl import Workbook

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.product_seo_xlsx_import_wizard import HEADERS


@tagged("post_install", "-at_install")
class TestProductSeoXlsxImport(TransactionCase):
    def setUp(self):
        super().setUp()
        card = self.env["ab_product_card"].create({"name": "Excel SEO Product"})
        self.product = self.env["ab_product"].create({
            "product_card_id": card.id,
            "code": "SEO-EXCEL-001",
            "default_price": 10,
            "allow_sale": True,
        })
        self.template = self.env["product.template"].create({
            "name": "Excel SEO Product",
            "ab_product_id": self.product.id,
            "sale_ok": True,
            "is_published": True,
        })

    def _wizard(self, rows):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(list(HEADERS))
        for row in rows:
            sheet.append([row.get(field_name) for field_name in HEADERS.values()])
        output = BytesIO()
        workbook.save(output)
        return self.env["ab_product_seo_xlsx_import_wizard"].create({
            "file": base64.b64encode(output.getvalue()),
            "filename": "products.xlsx",
        })

    def test_import_creates_english_draft_without_publishing(self):
        wizard = self._wizard([{
            "product_code": self.product.code,
            "meta_title": "Excel SEO Title",
            "meta_description": "Excel SEO Description",
            "keyword_text": "medicine, pharmacy",
            "seo_name": "excel-seo-product",
            "short_description": "Short copy",
            "public_description": "First line\nSecond line",
            "active_ingredient": "Ingredient A",
            "warnings": "Warning A",
            "contraindications": "Contraindication A",
            "storage": "Store below 25 C",
        }])
        action = wizard.action_import()
        seo = self.env["ab.product.seo"].search([("ab_product_id", "=", self.product.id)])
        english = seo.translation_ids.filtered(lambda item: item.lang_code == "en_US")
        self.assertEqual(action["res_model"], "ab.product.seo")
        self.assertEqual(seo.state, "draft")
        self.assertEqual(english.meta_title, "Excel SEO Title")
        self.assertEqual(str(english.public_description), "<p>First line<br>Second line</p>")
        self.assertEqual(english.active_ingredient, "Ingredient A")
        self.assertEqual(english.warnings, "Warning A")
        self.assertEqual(english.contraindications, "Contraindication A")
        self.assertEqual(english.storage, "Store below 25 C")
        self.assertFalse(self.template.website_meta_title)
        self.assertFalse(seo.published_version_id)

    def test_import_rejects_missing_code_before_writing_any_row(self):
        wizard = self._wizard([
            {"product_code": self.product.code, "meta_title": "Valid", "meta_description": "Valid description"},
            {"product_code": "UNKNOWN", "meta_title": "Unknown", "meta_description": "Unknown description"},
        ])
        with self.assertRaises(UserError):
            wizard.action_import()
        self.assertFalse(self.env["ab.product.seo"].search([("ab_product_id", "=", self.product.id)]))

    def test_import_accepts_numeric_product_code_cells(self):
        self.product.code = "555"
        self._wizard([{
            "product_code": 555,
            "meta_title": "Numeric product code",
            "meta_description": "Description from Excel",
        }]).action_import()
        seo = self.env["ab.product.seo"].search([("ab_product_id", "=", self.product.id)])
        self.assertEqual(seo.en_meta_title, "Numeric product code")

    def test_import_does_not_replace_approved_review(self):
        seo = self.env["ab.product.seo"].create({"product_template_id": self.template.id})
        seo.state = "approved"
        wizard = self._wizard([{
            "product_code": self.product.code,
            "meta_title": "Excel SEO Title",
            "meta_description": "Excel SEO Description",
        }])
        with self.assertRaises(UserError):
            wizard.action_import()
        self.assertFalse(seo.translation_ids.filtered(lambda item: item.lang_code == "en_US").meta_title)

    def test_manager_import_reopens_published_record_and_keeps_blank_optional_values(self):
        seo = self.env["ab.product.seo"].create({"product_template_id": self.template.id})
        english = seo.translation_ids.filtered(lambda item: item.lang_code == "en_US")
        english.write({"meta_title": "Old title", "meta_description": "Old description", "warnings": "Existing warning"})
        seo.state = "published"
        self.template.website_meta_title = "Published title"
        manager = self.env["res.users"].create({
            "name": "SEO import manager",
            "login": "seo_import_manager_test",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("ab_website_seo_optimization.group_ab_website_seo_optimization_manager").id,
            ])],
        })
        wizard = self._wizard([{
            "product_code": self.product.code,
            "meta_title": "New title",
            "meta_description": "New description",
        }])
        wizard.with_user(manager).action_import()
        self.assertEqual(seo.state, "draft")
        self.assertEqual(english.meta_title, "New title")
        self.assertEqual(english.warnings, "Existing warning")
        self.assertEqual(self.template.website_meta_title, "Published title")

    def test_imported_template_draft_can_be_approved_as_manual_content(self):
        seo = self.env["ab.product.seo"].create({"product_template_id": self.template.id})
        english = seo.translation_ids.filtered(lambda item: item.lang_code == "en_US")
        template = self.env["ab_seo_template"].search([], limit=1)
        self.assertTrue(template)
        english.sudo().write({"seo_template_id": template.id, "template_version": template.version})
        self._wizard([{
            "product_code": self.product.code,
            "meta_title": "Imported manual title",
            "meta_description": "Imported manual description",
            "public_description": "Imported content for human review.",
        }]).action_import()
        self.assertFalse(english.seo_template_id)
        self.assertEqual(english.content_source, "manual")
        seo.action_submit_review()
        seo.action_approve()
        self.assertEqual(seo.state, "approved")
        self.assertEqual(english.current_version_id.meta_title, "Imported manual title")
        self.assertFalse(self.template.website_meta_title)

    def test_ordinary_seo_user_cannot_call_import_method(self):
        user = self.env["res.users"].create({
            "name": "SEO import user",
            "login": "seo_import_user_test",
            "group_ids": [(6, 0, [
                self.env.ref("base.group_user").id,
                self.env.ref("ab_website_seo_optimization.group_ab_website_seo_optimization_user").id,
            ])],
        })
        wizard = self._wizard([{
            "product_code": self.product.code,
            "meta_title": "Excel SEO Title",
            "meta_description": "Excel SEO Description",
        }])
        with self.assertRaises(AccessError):
            wizard.with_user(user).action_import()
        with self.assertRaises(AccessError):
            wizard.with_user(user).action_import_report()

    def test_success_report_lists_saved_products(self):
        wizard = self._wizard([{
            "product_code": self.product.code,
            "meta_title": "Report title",
            "meta_description": "Report description",
        }])
        action = wizard.action_import_report()
        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(action["target"], "new")
        self.assertEqual(wizard.import_outcome, "success")
        self.assertEqual(wizard.import_summary, "Imported: 1. Not imported: 0.")
        self.assertFalse(wizard.import_error)
        self.assertEqual(wizard.report_line_ids.product_code, self.product.code)
        self.assertEqual(wizard.report_line_ids.status, "imported")
        self.assertEqual(wizard.report_line_ids.row_number, "2")
        self.assertEqual(wizard.report_line_ids.seo_id.en_meta_title, "Report title")
        self.assertEqual(wizard.action_open_imported_drafts()["domain"], [
            ("id", "in", wizard.report_line_ids.seo_id.ids),
        ])

    def test_failure_report_does_not_claim_partial_success(self):
        wizard = self._wizard([
            {"product_code": self.product.code, "meta_title": "Valid", "meta_description": "Valid description"},
            {"product_code": "UNKNOWN", "meta_title": "Unknown", "meta_description": "Unknown description"},
        ])
        wizard.action_import_report()
        self.assertEqual(wizard.import_outcome, "failed")
        self.assertEqual(wizard.import_summary, "Imported: 0. Not imported: 2.")
        self.assertIn("UNKNOWN", wizard.import_error)
        self.assertEqual(len(wizard.report_line_ids), 2)
        self.assertEqual(set(wizard.report_line_ids.mapped("status")), {"not_imported"})
        self.assertFalse(wizard.report_line_ids.mapped("seo_id"))
        self.assertFalse(self.env["ab.product.seo"].search([("ab_product_id", "=", self.product.id)]))

    def test_report_rolls_back_business_writes_on_late_failure(self):
        wizard = self._wizard([{
            "product_code": self.product.code,
            "meta_title": "Report title",
            "meta_description": "Report description",
        }])
        original_title = self.template.website_meta_title

        def fail_after_write(record):
            self.template.website_meta_title = "Uncommitted title"
            raise UserError("Import failed after a write")

        with patch.object(type(wizard), "action_import", fail_after_write):
            wizard.action_import_report()
        self.assertEqual(self.template.website_meta_title, original_title)
        self.assertEqual(wizard.import_outcome, "failed")
        self.assertEqual(wizard.report_line_ids.status, "not_imported")

    def test_invalid_file_has_file_error_report(self):
        wizard = self._wizard([])
        wizard.filename = "products.txt"
        wizard.action_import_report()
        self.assertEqual(wizard.import_outcome, "failed")
        self.assertIn(".xlsx", wizard.import_error)
        self.assertEqual(wizard.report_line_ids.status, "error")
        self.assertFalse(wizard.report_line_ids.row_number)
