from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestEplusCatalogImport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Snapshot = self.env["ab_eplus_stock_snapshot"].sudo()
        self.Product = self.env["ab_product"].sudo().with_context(active_test=False)

    def snapshot(self, itm_id, code):
        return self.Snapshot.create({
            "itm_id": itm_id, "itm_code": code, "itm_qty": 1.0,
        })

    def import_rows(self, rows, source):
        with patch.object(type(self.Snapshot), "_fetch_eplus_catalog_names", return_value=source):
            return rows._import_eplus_catalog_batch()

    def test_creates_unpublished_draft_with_real_eplus_name(self):
        row = self.snapshot(99177001, "99177001")
        source = {row.itm_id: [(row.itm_code, "Real Arabic Name", "Real English Name", True)]}

        self.assertEqual(self.import_rows(row, source), 1)
        product = self.Product.search([("eplus_serial", "=", row.itm_id)])
        self.assertEqual(len(product), 1)
        self.assertEqual(product.code, row.itm_code)
        self.assertEqual(product.product_card_name, "Real English Name")
        self.assertFalse(product.active)
        self.assertFalse(product.allow_sale)
        self.assertFalse(product.website_sale_available)
        self.assertFalse(product.website_product_tmpl_id)
        self.assertEqual(product.website_catalog_status, "eplus_draft")
        self.assertEqual(row.product_id, product)
        self.assertEqual(self.import_rows(row, source), 0)
        self.assertEqual(self.Product.search_count([("eplus_serial", "=", row.itm_id)]), 1)

    def test_links_existing_product_by_barcode(self):
        row = self.snapshot(99177002, "99177002")
        barcode = self.env["ab_product_barcode"].sudo().create({"name": row.itm_code})
        product = self.Product.create({
            "name": "Existing product", "product_card_name": "Existing product",
            "code": "EXISTING-99177002", "barcode_ids": [(6, 0, barcode.ids)],
        })
        source = {row.itm_id: [(row.itm_code, "Real Name", "Real Name", True)]}

        self.assertEqual(self.import_rows(row, source), 0)
        self.assertEqual(row.product_id, product)
        self.assertEqual(row.matched_by, "barcode")
        self.assertEqual(product.eplus_serial, row.itm_id)
        self.assertFalse(product.eplus_catalog_draft)

    def test_skips_missing_name_inactive_and_duplicate_codes(self):
        missing_name = self.snapshot(99177003, "99177003")
        inactive = self.snapshot(99177004, "99177004")
        duplicate_a = self.snapshot(99177005, "DUP-99177005")
        duplicate_b = self.snapshot(99177006, "DUP-99177005")
        rows = missing_name | inactive | duplicate_a | duplicate_b
        source = {
            missing_name.itm_id: [(missing_name.itm_code, "", "", True)],
            inactive.itm_id: [(inactive.itm_code, "Inactive", "Inactive", False)],
            duplicate_a.itm_id: [(duplicate_a.itm_code, "A", "A", True)],
            duplicate_b.itm_id: [(duplicate_b.itm_code, "B", "B", True)],
        }

        self.assertEqual(self.import_rows(rows, source), 0)
        self.assertFalse(rows.mapped("product_id"))

    def test_non_admin_cannot_import(self):
        row = self.snapshot(99177007, "99177007")
        user = self.env.ref("base.public_user")

        with self.assertRaises(AccessError):
            row.with_user(user)._import_eplus_catalog_batch()
