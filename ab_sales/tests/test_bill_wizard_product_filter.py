from odoo.tests.common import TransactionCase, tagged


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


@tagged("post_install", "-at_install")
class TestBillWizardInvoiceInfo(TransactionCase):
    """Display metadata must not require optional addons or change invoice behavior."""

    def _header(self, **values):
        from types import SimpleNamespace

        defaults = dict(
            id=1, eplus_serial=0, status="pending", store_id=False,
            number_of_products=0, total_price=0, total_net_amount=0,
            description="", create_date=False, create_uid=False,
            employee_id=False, is_delivery=False,
        )
        defaults.update(values)
        return SimpleNamespace(**defaults)

    def test_invoice_type_priority_in_payload(self):
        api = self.env["ab_sales_ui_api"].with_context(lang="en_US")
        cases = [
            ({}, ""),
            ({"is_delivery": True}, "Delivery"),
            ({"contract_name": "Insurance"}, "Contract"),
            ({"contract_name": "Insurance", "is_delivery": True}, "Contract"),
            ({"applied_program_name": "Offer"}, "Promo"),
            ({"applied_program_name": "Offer", "is_delivery": True}, "Promo"),
            ({"contract_name": "Insurance", "applied_program_name": "Offer",
              "is_delivery": True}, "Contract"),
            ({"promo_discount_amount": 10}, ""),
        ]
        for values, expected in cases:
            with self.subTest(values=values):
                payload = api._bill_wizard_header_payload(self._header(**values))
                self.assertEqual(payload["invoice_type"], expected)

    def test_contract_relation_takes_priority(self):
        from types import SimpleNamespace

        api = self.env["ab_sales_ui_api"].with_context(lang="en_US")
        for delivery in (False, True):
            with self.subTest(is_delivery=delivery):
                header = self._header(
                    contract_id=SimpleNamespace(name="Insurance"),
                    applied_program_name="Offer",
                    is_delivery=delivery,
                )
                self.assertEqual(api._bill_wizard_header_payload(header)["invoice_type"], "Contract")

    def test_salesperson_uses_employee_only(self):
        from types import SimpleNamespace

        api = self.env["ab_sales_ui_api"]
        creator = SimpleNamespace(id=2, display_name="Invoice Creator")
        header = self._header(create_uid=creator)
        self.assertEqual(api._bill_wizard_header_payload(header)["employee_name"], "")
        header.employee_id = SimpleNamespace(display_name="Actual Salesperson")
        self.assertEqual(
            api._bill_wizard_header_payload(header)["employee_name"], "Actual Salesperson",
        )

    def test_delivery_label_in_arabic(self):
        if not self.env["res.lang"].search_count([("code", "=", "ar_001")]):
            self.skipTest("Arabic is not installed")
        api = self.env["ab_sales_ui_api"].with_context(lang="ar_001")
        self.assertEqual(
            api._bill_wizard_header_payload(self._header(is_delivery=True))["invoice_type"],
            "توصيل",
        )

    def test_effective_applied_programs(self):
        from types import SimpleNamespace

        class Programs(list):
            def filtered(self, predicate):
                return Programs(program for program in self if predicate(program))

            def __getitem__(self, key):
                result = super().__getitem__(key)
                return result[0] if isinstance(key, slice) and result else result

        header = self._header(
            applied_program_ids=Programs([SimpleNamespace(display_name="Offer")]),
            _program_is_effective=lambda program: True,
            is_delivery=True,
        )
        api = self.env["ab_sales_ui_api"].with_context(lang="en_US")
        self.assertEqual(api._bill_wizard_header_payload(header)["invoice_type"], "Promo")
        header._program_is_effective = lambda program: False
        self.assertEqual(api._bill_wizard_header_payload(header)["invoice_type"], "Delivery")

    def test_bills_list_shows_contract_column_when_installed(self):
        from lxml import etree

        if "contract_id" not in self.env["ab_sales_header"]._fields:
            self.skipTest("Contracts is not installed")
        view = self.env["ab_sales_header"].get_view(
            view_id=self.env.ref("ab_sales.ab_sales_header_view_tree").id,
            view_type="list",
        )
        arch = etree.fromstring(view["arch"])
        self.assertTrue(arch.xpath("//field[@name='contract_id'][@optional='show']"))
