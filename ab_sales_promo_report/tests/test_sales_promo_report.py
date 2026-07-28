from odoo.tests.common import TransactionCase


class TestSalesPromoReport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.store = self.env["ab_store"].sudo().create({
            "name": "Promo Store",
            "code": "PROMO",
            "eplus_serial": 100,
        })
        card = self.env["ab_product_card"].sudo().create({"name": "Promo Product Card"})
        self.product = self.env["ab_product"].sudo().create({
            "product_card_id": card.id,
            "code": "PROMO-PROD",
            "eplus_serial": 200,
        })
        self.other_product = self.env["ab_product"].sudo().create({
            "product_card_id": card.id,
            "code": "NO-PROMO-PROD",
            "eplus_serial": 201,
        })
        self.promo = self.env["ab_promo_program"].sudo().create({
            "name": "May Promo",
            "rule_date_from": "2026-05-01 00:00:00",
            "rule_date_to": "2026-05-31 23:59:59",
            "disc_percent": 50.0,
            "product_ids": [(6, 0, [self.product.id])],
        })

    def test_build_report_vals_matches_discount_to_compensation(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        })
        rows = [{
            "invoice_eplus_serial": 10001,
            "store_eplus_serial": 100,
            "product_eplus_serial": 200,
            "qty": 2.0,
            "price": 250.0,
            "total_price": 500.0,
            "total_bill": 860.0,
            "total_bill_after_disc": 860.0,
            "total_bill_net": 610.0,
            "invoice_date": "2026-05-09",
            "is_odoo": True,
        }]

        vals_list = wizard._build_report_vals(rows)

        self.assertEqual(len(vals_list), 1)
        self.assertEqual(vals_list[0]["store_id"], self.store.id)
        self.assertEqual(vals_list[0]["product_id"], self.product.id)
        self.assertEqual(vals_list[0]["promo_id"], self.promo.id)
        self.assertEqual(vals_list[0]["total_compensation"], 250.0)
        self.assertEqual(vals_list[0]["promo_discount"], 250.0)
        self.assertTrue(vals_list[0]["is_odoo"])
        self.assertEqual(vals_list[0]["promo_date_status"], "in_date")

    def test_build_report_vals_matches_discount_even_outside_promo_date(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
        })
        rows = [{
            "invoice_eplus_serial": 10002,
            "store_eplus_serial": 100,
            "product_eplus_serial": 200,
            "qty": 1.0,
            "price": 250.0,
            "total_price": 250.0,
            "total_bill": 250.0,
            "total_bill_after_disc": 250.0,
            "total_bill_net": 125.0,
            "invoice_date": "2026-06-02",
        }]

        vals_list = wizard._build_report_vals(rows)

        self.assertEqual(len(vals_list), 1)
        self.assertEqual(vals_list[0]["promo_id"], self.promo.id)
        self.assertEqual(vals_list[0]["promo_date_status"], "out_of_date")

    def test_build_report_vals_uses_bconnect_tolerance(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        })
        rows = [{
            "invoice_eplus_serial": 10004,
            "store_eplus_serial": 100,
            "product_eplus_serial": 200,
            "qty": 2.0,
            "price": 250.0,
            "total_price": 500.0,
            "total_bill": 500.0,
            "total_bill_after_disc": 500.0,
            "total_bill_net": 254.0,
            "invoice_date": "2026-05-09",
            "is_odoo": False,
        }]

        vals_list = wizard._build_report_vals(rows)

        self.assertEqual(len(vals_list), 1)
        self.assertEqual(vals_list[0]["promo_id"], self.promo.id)
        self.assertEqual(vals_list[0]["promo_discount"], 250.0)
        self.assertEqual(vals_list[0]["total_compensation"], 246.0)

    def test_build_report_vals_uses_stricter_odoo_tolerance(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        })
        rows = [{
            "invoice_eplus_serial": 10005,
            "store_eplus_serial": 100,
            "product_eplus_serial": 200,
            "qty": 2.0,
            "price": 250.0,
            "total_price": 500.0,
            "total_bill": 500.0,
            "total_bill_after_disc": 500.0,
            "total_bill_net": 254.0,
            "invoice_date": "2026-05-09",
            "is_odoo": True,
        }]

        vals_list = wizard._build_report_vals(rows)

        self.assertEqual(len(vals_list), 1)
        self.assertFalse(vals_list[0]["promo_id"])
        self.assertEqual(vals_list[0]["promo_discount"], 0.0)
        self.assertEqual(vals_list[0]["total_compensation"], 246.0)
        self.assertEqual(vals_list[0]["promo_date_status"], "no_promo_applied")

    def test_build_report_vals_uses_one_matching_promo_per_invoice(self):
        self.env["ab_promo_program"].sudo().create({
            "name": "Duplicate May Promo",
            "rule_date_from": "2026-05-01 00:00:00",
            "rule_date_to": "2026-05-31 23:59:59",
            "disc_percent": 50.0,
            "product_ids": [(6, 0, [self.product.id])],
        })
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "show_all_matching_promos": True,
        })
        rows = [{
            "invoice_eplus_serial": 10006,
            "store_eplus_serial": 100,
            "product_eplus_serial": 200,
            "qty": 2.0,
            "price": 250.0,
            "total_price": 500.0,
            "total_bill": 500.0,
            "total_bill_after_disc": 500.0,
            "total_bill_net": 250.0,
            "invoice_date": "2026-05-09",
        }]

        vals_list = wizard._build_report_vals(rows)

        self.assertEqual(len(vals_list), 1)
        self.assertEqual(vals_list[0]["promo_id"], self.promo.id)

    def test_build_report_vals_skips_rows_without_any_promo_by_default(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        })
        rows = [{
            "invoice_eplus_serial": 10003,
            "store_eplus_serial": 100,
            "product_eplus_serial": 201,
            "qty": 1.0,
            "price": 300.0,
            "total_price": 300.0,
            "total_bill": 300.0,
            "total_bill_after_disc": 300.0,
            "total_bill_net": 300.0,
            "invoice_date": "2026-05-09",
        }]

        self.assertFalse(wizard._build_report_vals(rows))

    def test_build_report_vals_keeps_rows_without_any_promo_when_enabled(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "include_no_promo_found": True,
        })
        rows = [{
            "invoice_eplus_serial": 10003,
            "store_eplus_serial": 100,
            "product_eplus_serial": 201,
            "qty": 1.0,
            "price": 300.0,
            "total_price": 300.0,
            "total_bill": 300.0,
            "total_bill_after_disc": 300.0,
            "total_bill_net": 300.0,
            "invoice_date": "2026-05-09",
        }]

        vals_list = wizard._build_report_vals(rows)

        self.assertEqual(len(vals_list), 1)
        self.assertEqual(vals_list[0]["product_id"], self.other_product.id)
        self.assertFalse(vals_list[0]["promo_id"])
        self.assertEqual(vals_list[0]["promo_discount"], 0.0)
        self.assertEqual(vals_list[0]["promo_date_status"], "no_promo_found")

    def test_build_report_vals_skips_unmapped_products(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "include_no_promo_found": True,
        })
        rows = [{
            "invoice_eplus_serial": 10007,
            "store_eplus_serial": 100,
            "product_eplus_serial": 999999,
            "qty": 1.0,
            "price": 300.0,
            "total_price": 300.0,
            "total_bill": 300.0,
            "total_bill_after_disc": 300.0,
            "total_bill_net": 250.0,
            "invoice_date": "2026-05-09",
        }]

        self.assertFalse(wizard._build_report_vals(rows))
