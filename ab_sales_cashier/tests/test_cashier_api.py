from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestCashierApi(TransactionCase):
    def setUp(self):
        super().setUp()
        self.store = self.env["ab_store"].create({
            "name": "Cashier Test Store",
            "code": "CASH-TEST",
            "allow_sale": True,
            "ip1": "127.0.0.1",
            "eplus_serial": 101,
        })
        self.local_pending_header = self.env["ab_sales_header"].create({
            "store_id": self.store.id,
            "status": "pending",
            "eplus_serial": 900001,
        })
        self.local_pending_return = self.env["ab_sales_return_header"].create({
            "store_id": self.store.id,
            "status": "pending",
            "origin_header_id": 900001,
            "notes": "pending return from cashier test",
        })
        self.local_pending_return_line = self.env["ab_sales_return_line"].create({
            "header_id": self.local_pending_return.id,
            "qty_str": "2",
            "sell_price": 25.0,
            "itm_eplus_id": 555,
        })

        group_user = self.env.ref("base.group_user")
        group_cashier = self.env.ref("ab_sales.group_ab_sales_cashier")
        Users = self.env["res.users"].with_context(no_reset_password=True)

        self.cashier_user = Users.create({
            "name": "Cashier User",
            "login": "cashier_user",
            "email": "cashier_user@example.com",
            "groups_id": [(6, 0, [group_user.id, group_cashier.id])],
        })
        self.normal_user = Users.create({
            "name": "Normal User",
            "login": "normal_user",
            "email": "normal_user@example.com",
            "groups_id": [(6, 0, [group_user.id])],
        })

    def test_pending_list_and_save_idempotent(self):
        api = self.env["ab_sales_cashier_api"].with_user(self.cashier_user)
        model_cls = type(api)
        pending_rows = [{
            "sth_id": 900001,
            "sth_flag": "P",
            "no_of_items": 2,
            "total_bill_net": 150.5,
            "total_bill": 150.5,
            "sth_notice": "cashier note",
            "customer_name": "Cash Customer",
            "customer_phone": "01000000000",
            "sec_insert_date": "2026-02-17 09:00:00",
            "sec_update_date": "2026-02-17 09:00:00",
        }]

        with (
            patch.object(model_cls, "_fetch_pending_headers_from_bconnect", return_value=pending_rows),
            patch.object(
                model_cls,
                "_save_pending_invoice_in_bconnect",
                side_effect=[("saved", "P", 150.5), ("already_saved", "C", 0.0)],
            ),
        ):
            payload = api.get_pending_invoices(limit=200, store_id=self.store.id)
            invoice_ids = {row["id"] for row in payload["invoices"]}
            self.assertIn(900001, invoice_ids)

            result = api.save_pending_invoice(900001, request_id="req_1", store_id=self.store.id, wallet_id=7)
            self.assertEqual(result["status"], "saved")
            self.assertEqual(result["wallet_id"], 7)
            self.assertEqual(result["collected_amount"], 150.5)

            refreshed_header = self.env["ab_sales_header"].browse(self.local_pending_header.id)
            self.assertEqual(refreshed_header.status, "saved")

            second_result = api.save_pending_invoice(900001, request_id="req_2", store_id=self.store.id, wallet_id=7)
            self.assertEqual(second_result["status"], "already_saved")

    def test_invoice_snapshot_from_bconnect(self):
        api = self.env["ab_sales_cashier_api"].with_user(self.cashier_user)
        model_cls = type(api)
        header_row = {
            "sth_id": 900001,
            "sth_flag": "P",
            "no_of_items": 1,
            "total_bill_net": 80.0,
            "total_bill": 80.0,
            "sth_notice": "snapshot note",
            "customer_name": "Snapshot Customer",
            "customer_phone": "01111111111",
            "sec_insert_date": "2026-02-17 10:00:00",
            "sec_update_date": "2026-02-17 10:00:00",
        }
        line_rows = [{
            "std_id": 1,
            "itm_id": 555,
            "itm_code": "ITM-555",
            "product_name": "Product 555",
            "qnty": 2,
            "itm_sell": 40.0,
            "itm_dis_mon": 0.0,
            "itm_unit": 1,
            "line_total_net": 80.0,
        }]

        with (
            patch.object(model_cls, "_fetch_invoice_snapshot_header_from_bconnect", return_value=header_row),
            patch.object(model_cls, "_fetch_pending_lines_from_bconnect", return_value=line_rows),
        ):
            snapshot = api.get_invoice_snapshot(900001, store_id=self.store.id)
            self.assertEqual(snapshot["id"], 900001)
            self.assertEqual(snapshot["line_count"], 1)
            self.assertEqual(snapshot["lines"][0]["product_code"], "ITM-555")

    def test_wallets_for_store(self):
        api = self.env["ab_sales_cashier_api"].with_user(self.cashier_user)
        model_cls = type(api)
        with patch.object(
            model_cls,
            "_fetch_store_wallets_from_bconnect",
            return_value=[
                {"id": 11, "name": "Main Wallet", "balance": 1000.0},
                {"id": 12, "name": "Second Wallet", "balance": 50.0},
            ],
        ):
            payload = api.get_store_wallets(store_id=self.store.id)
            self.assertEqual(payload["default_wallet_id"], 11)
            self.assertEqual(len(payload["wallets"]), 2)

    def test_pending_list_includes_pending_returns(self):
        api = self.env["ab_sales_cashier_api"].with_user(self.cashier_user)
        model_cls = type(api)
        with patch.object(model_cls, "_fetch_pending_headers_from_bconnect", return_value=[]):
            payload = api.get_pending_invoices(limit=200, store_id=self.store.id)
        rows = [row for row in payload["invoices"] if row.get("document_type") == "return"]
        self.assertTrue(rows)
        self.assertIn(self.local_pending_return.id, {row["id"] for row in rows})

    def test_return_snapshot_and_save(self):
        api = self.env["ab_sales_cashier_api"].with_user(self.cashier_user)
        snapshot = api.get_invoice_snapshot(
            self.local_pending_return.id,
            store_id=self.store.id,
            document_type="return",
        )
        self.assertEqual(snapshot["document_type"], "return")
        self.assertEqual(snapshot["id"], self.local_pending_return.id)
        self.assertEqual(snapshot["line_count"], 1)

        model_cls = type(self.env["ab_sales_return_header"])

        def _mock_push_to_eplus(recordset):
            recordset.write({"status": "saved"})
            return True

        with patch.object(model_cls, "action_push_to_eplus_return", autospec=True, side_effect=_mock_push_to_eplus):
            result = api.save_pending_invoice(
                self.local_pending_return.id,
                request_id="req_ret_1",
                store_id=self.store.id,
                document_type="return",
            )
        self.assertEqual(result["status"], "saved")
        self.assertEqual(result["document_type"], "return")
        self.assertFalse(result["wallet_id"])

        refreshed_return = self.env["ab_sales_return_header"].browse(self.local_pending_return.id)
        self.assertEqual(refreshed_return.status, "saved")

        second_result = api.save_pending_invoice(
            self.local_pending_return.id,
            request_id="req_ret_2",
            store_id=self.store.id,
            document_type="return",
        )
        self.assertEqual(second_result["status"], "already_saved")
        self.assertEqual(second_result["document_type"], "return")

    def test_cashier_access_required(self):
        api = self.env["ab_sales_cashier_api"].with_user(self.normal_user)
        with self.assertRaises(AccessError):
            api.get_pending_invoices(store_id=self.store.id)
        with self.assertRaises(AccessError):
            api.get_store_wallets(store_id=self.store.id)
