from odoo.tests.common import TransactionCase


class TestBillWizardProductFilter(TransactionCase):
    def setUp(self):
        super().setUp()

        self.store = self.env["ab_store"].sudo().create({
            "name": "Bill Wizard Store",
            "code": "BWST",
        })

        self.product_exact = self._create_product("BW-EXACT", "Bill Wizard Exact Product")
        self.product_name_match = self._create_product("BW-OTHER", "Bill Wizard Needle Product")
        self.product_unmatched = self._create_product("BW-NONE", "Bill Wizard Other Product")

    def _create_product(self, code, name):
        card = self.env["ab_product_card"].sudo().create({"name": name})
        return self.env["ab_product"].sudo().create({
            "product_card_id": card.id,
            "code": code,
        })

    def _create_bill(self, product):
        header = self.env["ab_sales_header"].sudo().create({
            "store_id": self.store.id,
            "status": "pending",
        })
        self.env["ab_sales_line"].sudo().create({
            "header_id": header.id,
            "product_id": product.id,
            "qty_str": "1",
        })
        return header

    def test_product_widget_name_search_uses_exact_code_first(self):
        Product = self.env["ab_product"].sudo().with_context(ab_bill_wizard_product_search=True)

        exact_ids = [row[0] for row in Product.name_search("BW-EXACT", [], "ilike", 10)]
        self.assertEqual(exact_ids, self.product_exact.ids)

        name_match_ids = [row[0] for row in Product.name_search("Needle", [], "ilike", 10)]
        self.assertIn(self.product_name_match.id, name_match_ids)
        self.assertNotIn(self.product_unmatched.id, name_match_ids)

    def test_bill_wizard_search_accepts_multiple_products(self):
        exact_bill = self._create_bill(self.product_exact)
        name_bill = self._create_bill(self.product_name_match)
        unmatched_bill = self._create_bill(self.product_unmatched)

        result = self.env["ab_sales_ui_api"].sudo().bill_wizard_search(
            product_ids=[self.product_exact.id, self.product_name_match.id],
            page=1,
        )

        result_ids = {item["id"] for item in result["items"]}
        self.assertIn(exact_bill.id, result_ids)
        self.assertIn(name_bill.id, result_ids)
        self.assertNotIn(unmatched_bill.id, result_ids)

    def test_bill_wizard_text_search_prefers_exact_code_over_name(self):
        exact_bill = self._create_bill(self.product_exact)
        self._create_bill(self.product_name_match)

        result = self.env["ab_sales_ui_api"].sudo().bill_wizard_search(
            product_query="BW-EXACT",
            page=1,
        )

        self.assertEqual([item["id"] for item in result["items"]], [exact_bill.id])
