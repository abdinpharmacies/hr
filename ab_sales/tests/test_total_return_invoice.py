from odoo.tests.common import TransactionCase


class TestTotalReturnInvoice(TransactionCase):
    def setUp(self):
        super().setUp()
        self.store = self.env["ab_store"].sudo().create({
            "name": "Test Store",
            "code": "TST",
        })

    def test_full_return_uses_invoice_net_total(self):
        header = self.env["ab_sales_return_header"].sudo().create({
            "store_id": self.store.id,
            "total_sales_net": 123.45,
        })
        self.env["ab_sales_return_line"].sudo().create([
            {
                "header_id": header.id,
                "qty_str": "2",
                "max_returnable_qty": 2.0,
                "sell_price": 10.0,
            },
            {
                "header_id": header.id,
                "qty_str": "3",
                "max_returnable_qty": 3.0,
                "sell_price": 5.0,
            },
        ])

        header._compute_totals()

        self.assertTrue(header._is_total_return_invoice())
        self.assertAlmostEqual(header.total_return_qty, 5.0, places=4)
        self.assertAlmostEqual(header.total_return_value, 123.45, places=2)

    def test_partial_return_keeps_line_sum(self):
        header = self.env["ab_sales_return_header"].sudo().create({
            "store_id": self.store.id,
            "total_sales_net": 123.45,
        })
        self.env["ab_sales_return_line"].sudo().create([
            {
                "header_id": header.id,
                "qty_str": "1",
                "max_returnable_qty": 2.0,
                "sell_price": 10.0,
            },
            {
                "header_id": header.id,
                "qty_str": "3",
                "max_returnable_qty": 3.0,
                "sell_price": 5.0,
            },
        ])

        header._compute_totals()

        self.assertFalse(header._is_total_return_invoice())
        self.assertAlmostEqual(header.total_return_qty, 4.0, places=4)
        self.assertAlmostEqual(header.total_return_value, 25.0, places=2)
