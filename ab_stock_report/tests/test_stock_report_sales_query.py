# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo import fields
from odoo.tests.common import TransactionCase


class TestStockReportSalesQuery(TransactionCase):
    def test_sales_query_joins_headers_without_large_or_lookup(self):
        cache = self.env["ab_stock_report_cache_line"]
        movement_date = fields.Datetime.now()
        calls = []

        def fake_run_raw_query(model, query, params, connection=None):
            calls.append((query, tuple(params), connection))
            if "FROM r_sales_trans_d" in query:
                return [
                    (
                        9001,
                        7001,
                        17,
                        1,
                        3.0,
                        42.0,
                        0.0,
                        0.0,
                        movement_date,
                        501,
                        601,
                    )
                ]
            if "FROM Item_Catalog" in query:
                return [(12345, 1, 1)]
            return []

        with patch.object(type(cache), "_run_raw_query", autospec=True, side_effect=fake_run_raw_query):
            rows = cache._fetch_sales_batch_rows_with_connection(
                12345,
                200,
                connection=object(),
            )

        detail_query, detail_params, _connection = calls[0]
        self.assertEqual(detail_params, (200, 12345))
        self.assertIn("INNER JOIN r_sales_trans_h sh WITH (NOLOCK)", detail_query)
        self.assertIn("sh.sth_id = sd.sth_id", detail_query)
        self.assertIn("sh.sto_id = sd.std_stock_id", detail_query)
        self.assertIn("sh.sth_flag = 'C'", detail_query)
        self.assertIn("ORDER BY sd.sec_update_date DESC", detail_query)
        self.assertNotIn(" OR ", detail_query)
        self.assertNotIn("limit_value * 5", detail_query)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["movement_type"], "sale")
        self.assertEqual(rows[0]["source_line_id"], "9001")

    def test_sales_date_and_return_filters_stay_parameterized(self):
        cache = self.env["ab_stock_report_cache_line"]
        from_date = fields.Date.today()
        calls = []

        def fake_run_raw_query(model, query, params, connection=None):
            calls.append((query, tuple(params), connection))
            return []

        with patch.object(type(cache), "_run_raw_query", autospec=True, side_effect=fake_run_raw_query):
            rows = cache._fetch_sales_batch_rows_with_connection(
                12345,
                50,
                return_only=True,
                from_date=from_date,
                connection=object(),
            )

        detail_query, detail_params, _connection = calls[0]
        self.assertEqual(rows, [])
        self.assertEqual(detail_params, (50, 12345, from_date))
        self.assertIn("sd.sec_update_date >= ?", detail_query)
        self.assertIn("ISNULL(sd.itm_back, 0) > 0", detail_query)
        self.assertIn("sh.sth_flag = 'C'", detail_query)
