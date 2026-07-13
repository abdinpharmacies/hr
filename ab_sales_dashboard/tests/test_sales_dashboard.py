from unittest.mock import patch
from datetime import datetime

from odoo import fields
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalesDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Snapshot = cls.env["ab.sales.dashboard.snapshot"]
        cls.Service = cls.env["ab.sales.dashboard.service"]

    def _payload(self):
        return {
            "total_sales": 1000.0,
            "avg_daily_sales": 100.0,
            "prev_avg_daily_sales": 80.0,
            "avg_daily_growth_pct": 25.0,
            "invoice_count": 12,
            "medicine_sales": 700.0,
            "non_medicine_sales": 300.0,
            "customer_bearing_amount": 120.0,
            "company_part_amount": 80.0,
            "bearing_pct": 60.0,
            "collection_lines": [
                {"collection_category": "cash", "invoice_count": 8, "total_sales": 650.0, "pct_of_total": 65.0},
                {"collection_category": "delivery", "invoice_count": 4, "total_sales": 350.0, "pct_of_total": 35.0},
            ],
            "user_lines": [
                {"emp_id": 15, "employee_name": "Ahmed", "invoice_count": 7, "total_sales": 600.0, "pct_of_total": 60.0},
            ],
            "item_lines": [
                {"itm_id": 501, "itm_code": "ITM501", "sale_times": 5, "sold_qty": 9.0, "current_balance": 30.0},
            ],
            "invoice_lines": [
                {
                    "invoice_no": "9001",
                    "sec_insert_date": "2026-07-02 10:00:00",
                    "customer_name": "Customer",
                    "invoice_total": 250.0,
                    "item_count": 2,
                    "items": "ITM501, ITM502",
                },
            ],
        }

    def test_invoice_where_uses_parameterized_store_filter(self):
        where_sql, params = self.Service._build_invoice_where(
            fields.Datetime.to_datetime("2026-07-01 00:00:00"),
            fields.Datetime.to_datetime("2026-07-10 00:00:00"),
            [10, 20],
        )
        self.assertIn("h.sto_id IN (?, ?)", where_sql)
        self.assertEqual(params[-2:], [10, 20])
        self.assertIn("h.sth_flag = 'C'", where_sql)

    def test_sales_by_user_sql_uses_existing_employee_name_column(self):
        where_sql, _params = self.Service._build_invoice_where(
            fields.Datetime.to_datetime("2026-07-01 00:00:00"),
            fields.Datetime.to_datetime("2026-07-10 00:00:00"),
            [],
        )
        sql = self.Service._sales_by_user_sql(where_sql)
        self.assertIn("e.e_name", sql)
        self.assertNotIn("e_name_ar", sql)

    def test_top_items_balance_query_does_not_aggregate_outer_unit_column(self):
        where_sql, _params = self.Service._build_invoice_where(
            fields.Datetime.to_datetime("2026-07-01 00:00:00"),
            fields.Datetime.to_datetime("2026-07-10 00:00:00"),
            [10],
        )
        sql = self.Service._top_items_sql(where_sql, 1)
        self.assertIn("JOIN item_catalog ic_balance", sql)
        self.assertIn("NULLIF(ic_balance.itm_unit1_unit3, 0)", sql)
        self.assertNotIn("NULLIF(ic.itm_unit1_unit3, 0) AS DECIMAL(18,2))) AS balance", sql)

    def test_eplus_datetime_normalizes_to_odoo_datetime_string(self):
        value = self.Service._json_safe_value(datetime(2026, 7, 13, 10, 1, 10, 210000))
        self.assertEqual(value, "2026-07-13 10:01:10")
        self.assertNotIn("T", value)

    def test_dashboard_payload_normalizes_totals_and_growth(self):
        payload = self.Service._normalize_dashboard_payload(
            totals={"total_sales": 900.0, "invoice_count": 9},
            previous={"total_sales": 600.0},
            collections=[],
            bearing={"bearing_pct": 10.0},
            medicine=[
                {"item_type": "medicine", "sales_amount": 700.0},
                {"item_type": "non_medicine", "sales_amount": 200.0},
            ],
            users=[],
            items=[],
            invoices=[],
            days=3,
        )
        self.assertEqual(payload["avg_daily_sales"], 300.0)
        self.assertEqual(payload["prev_avg_daily_sales"], 200.0)
        self.assertEqual(payload["avg_daily_growth_pct"], 50.0)
        self.assertEqual(payload["medicine_sales"], 700.0)
        self.assertEqual(payload["non_medicine_sales"], 200.0)

    def test_refresh_dashboard_creates_snapshot_from_mocked_eplus_payload(self):
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "fetch_dashboard_data", return_value=self._payload()) as mocked_fetch:
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-07-01",
                "date_to": "2026-07-09",
                "store_id": 0,
            })

        mocked_fetch.assert_called_once()
        self.assertTrue(data["has_snapshot"])
        self.assertEqual(data["total_sales"], 1000.0)
        self.assertEqual(data["store_filter_label"], "All Stores")
        self.assertEqual(len(data["collection_lines"]), 2)
        self.assertEqual(data["item_lines"][0]["eplus_item_code"], "ITM501")
        self.assertEqual(data["invoice_lines"][0]["invoice_no"], "9001")

    def test_get_dashboard_returns_empty_payload_without_snapshot(self):
        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-06-01",
            "date_to": "2026-06-02",
            "store_id": 0,
        })
        self.assertFalse(data["has_snapshot"])
        self.assertEqual(data["total_sales"], 0.0)
        self.assertIn("stores", data)
