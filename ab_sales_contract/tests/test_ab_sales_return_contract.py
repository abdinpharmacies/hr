from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestAbSalesReturnContract(TransactionCase):
    def setUp(self):
        super().setUp()
        self.return_header = self.env["ab_sales_return_header"].new({})

    def test_contract_return_first_amount_preserves_zero(self):
        self.assertEqual(
            self.return_header._contract_return_first_amount(0.0, 100.0, 50.0),
            0.0,
        )

    def test_virtual_totals_preserve_zero_customer_liability(self):
        virtual_header = type(
            "ContractVirtualHeader",
            (),
            {
                "line_ids": [],
                "amount_total": 100.0,
                "contract_id": object(),
                "total_after_discount": 100.0,
                "total_net_amount": 0.0,
                "cust_pay": 0.0,
            },
        )()

        with patch.object(
            type(self.return_header),
            "_contract_return_build_virtual_header",
            return_value=virtual_header,
        ):
            totals = self.return_header._contract_return_virtual_totals(object(), mode="remaining")

        self.assertEqual(totals["after_disc"], 100.0)
        self.assertEqual(totals["net"], 0.0)
        self.assertEqual(totals["total_net_amount"], 0.0)

    def test_reprice_values_use_source_total_net_amount_minus_virtual_total_net_amount(self):
        source_header = type(
            "SourceHeader",
            (),
            {
                "contract_id": object(),
                "total_after_discount": 150.0,
                "total_net_amount": 40.0,
                "cust_pay": 40.0,
            },
        )()

        with patch.object(
            type(self.return_header),
            "_contract_return_get_source_header",
            return_value=source_header,
        ), patch.object(
            type(self.return_header),
            "_contract_return_virtual_totals",
            return_value={
                "after_disc": 100.0,
                "net": 15.0,
                "total_net_amount": 15.0,
            },
        ):
            values = self.return_header._contract_return_reprice_values()

        self.assertEqual(values["original_net"], 40.0)
        self.assertEqual(values["remaining_net"], 15.0)
        self.assertEqual(values["refund_net"], 25.0)
