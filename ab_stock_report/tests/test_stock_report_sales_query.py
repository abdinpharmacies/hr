# -*- coding: utf-8 -*-

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestStockReportSalesQuery(TransactionCase):
    def _create_stock_report_product(self, code, eplus_serial):
        try:
            card = self.env["ab_product_card"].sudo().create({"name": code})
            return self.env["ab_product"].sudo().create({
                "product_card_id": card.id,
                "code": code,
                "eplus_serial": eplus_serial,
                "default_price": 10.0,
            })
        except ValidationError as error:
            if "Replication Database" in str(error):
                self.skipTest("Replica database blocks creating ab_product test records.")
            raise

    def _create_stock_report_store(self, code, eplus_serial, has_working_balance):
        try:
            return self.env["ab_store"].sudo().create({
                "name": code,
                "code": code,
                "eplus_serial": eplus_serial,
                "active": True,
                "has_working_balance": has_working_balance,
            })
        except ValidationError as error:
            if "Replication Database" in str(error):
                self.skipTest("Replica database blocks creating ab_store test records.")
            raise

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

    def test_store_balance_filter_domain_requires_working_balance(self):
        field_domain = self.env["ab_stock_report_wizard"]._fields[
            "store_balance_filter_store_id"
        ].domain
        self.assertIn(("has_working_balance", "=", True), field_domain)

    def test_store_balance_view_filters_lines_from_selected_branch(self):
        view_arch = self.env.ref(
            "ab_stock_report.ab_stock_report_wizard_view_form"
        ).arch_db
        self.assertIn(
            "domain=\"store_balance_filter_store_id and "
            "[('store_id', '=', store_balance_filter_store_id)] or []\"",
            view_arch,
        )

    def test_store_balance_cache_uses_working_balance_stores_only(self):
        working_store = self._create_stock_report_store("SR-WB-STORE", 91001, True)
        hidden_store = self._create_stock_report_store("SR-NO-WB-STORE", 91002, False)
        stores = self.env["ab_stock_report_store_balance_cache"]._active_configured_stores()

        self.assertIn(working_store, stores)
        self.assertNotIn(hidden_store, stores)
        self.assertTrue(all(store.has_working_balance for store in stores))

    def test_store_balance_lines_load_working_stores_even_with_branch_filter(self):
        product = self._create_stock_report_product("SR-WB-PROD", 92001)
        working_store_1 = self._create_stock_report_store("SR-WB-ONE", 92011, True)
        working_store_2 = self._create_stock_report_store("SR-WB-TWO", 92012, True)
        hidden_store = self._create_stock_report_store("SR-WB-HIDDEN", 92013, False)
        self.env["ab_stock_report_store_balance_cache"].sudo().create({
            "product_id": product.id,
            "product_eplus_serial": int(product.eplus_serial),
            "store_id": hidden_store.id,
            "store_eplus_serial": int(hidden_store.eplus_serial),
            "main_updated_at": fields.Datetime.now(),
        })
        wizard = self.env["ab_stock_report_wizard"].sudo().create({
            "product_id": product.id,
            "limit": 10,
            "active_tab": "store_balance",
            "store_balance_filter_store_id": working_store_1.id,
        })

        wizard._load_store_balance_lines()
        line_stores = wizard.store_balance_line_ids.store_id

        self.assertIn(working_store_1, line_stores)
        self.assertIn(working_store_2, line_stores)
        self.assertNotIn(hidden_store, line_stores)

    def test_store_balance_main_cache_check_ignores_non_working_stores(self):
        product = self._create_stock_report_product("SR-WB-CACHE", 93001)
        working_store = self._create_stock_report_store("SR-WB-CACHE-ONE", 93011, True)
        hidden_store = self._create_stock_report_store("SR-WB-CACHE-HIDDEN", 93012, False)
        Cache = self.env["ab_stock_report_store_balance_cache"].sudo()
        Cache.create({
            "product_id": product.id,
            "product_eplus_serial": int(product.eplus_serial),
            "store_id": hidden_store.id,
            "store_eplus_serial": int(hidden_store.eplus_serial),
            "main_updated_at": fields.Datetime.now(),
        })

        self.assertFalse(Cache.has_main_cache_for_product(product))

        Cache.create({
            "product_id": product.id,
            "product_eplus_serial": int(product.eplus_serial),
            "store_id": working_store.id,
            "store_eplus_serial": int(working_store.eplus_serial),
            "main_updated_at": fields.Datetime.now(),
        })
        self.assertTrue(Cache.has_main_cache_for_product(product))
