from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestAbSalesReturnPromo(TransactionCase):
    def setUp(self):
        super().setUp()
        self.return_header = self.env["ab_sales_return_header"].new({})

    def test_compute_totals_uses_repriced_refund_value(self):
        with patch.object(
            type(self.return_header),
            "_promo_return_reprice_values",
            return_value={"source_header": object(), "refund_total": 80.0},
        ):
            self.return_header._compute_totals()

        self.assertEqual(self.return_header.total_return_value, 80.0)

    def test_return_adjustments_use_repriced_refund_value(self):
        with patch.object(
            type(self.return_header),
            "_promo_return_reprice_values",
            return_value={"source_header": object(), "refund_total": 80.0},
        ):
            adjustments = self.return_header._get_return_adjustments(
                cur=None,
                sth_id=1001,
                total_value=120.0,
                net_return=120.0,
            )

        self.assertEqual(adjustments["total_bill_after_disc_delta"], 80.0)
        self.assertEqual(adjustments["total_bill_net_delta"], 80.0)
        self.assertEqual(adjustments["fcs_current_balance_delta"], 80.0)
        self.assertEqual(adjustments["fh_value_delta"], 80.0)
        self.assertEqual(adjustments["sales_return_payment_value"], -80.0)

    def test_line_qty_source_uses_current_returnable_qty_for_repeated_returns(self):
        line = type(
            "PromoLine",
            (),
            {
                "qty_sold_source": 2.0,
                "max_returnable_source": 1.0,
                "_qty_to_source_unit": lambda self: 1.0,
            },
        )()

        self.assertEqual(self.return_header._promo_return_line_qty_source(line, mode="current"), 1.0)
        self.assertEqual(self.return_header._promo_return_line_qty_source(line, mode="remaining"), 0.0)
