from contextlib import contextmanager
from unittest.mock import patch
from datetime import datetime, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged

from ..models.sales_dashboard_config import SalesDashboardRefreshBusyError
from ..models.sales_dashboard_service import SalesDashboardSourceUnavailableError


@tagged("post_install", "-at_install")
class TestSalesDashboard(TransactionCase):
    class _FakeDashboardCursor:
        def __init__(self, fail_on_label=None, fail_cleanup_drop=False):
            self.fail_on_label = fail_on_label
            self.fail_cleanup_drop = fail_cleanup_drop
            self.executed = []
            self.labels = []
            self.description = []
            self.rows = []
            self.timeout = 0
            self.closed = False
            self.drop_count = 0

        def _label(self, sql):
            upper = sql.upper()
            if "DROP TABLE #INVOICE_BASE" in upper and "DROP TABLE #DAILY_ITEM_TYPE_FACT" in upper:
                return "drop_temp_tables"
            if "DROP TABLE #TOP_ITEMS" in upper:
                return "drop_top_items"
            if "DROP TABLE #RECENT_HEADERS" in upper:
                return "drop_recent_headers"
            if "DROP TABLE #INVOICE_BASE" in upper:
                return "drop_invoice_base"
            if "CREATE TABLE #INVOICE_BASE" in upper:
                return "create_invoice_base_table"
            if "INTO #INVOICE_BASE" in upper:
                return "create_invoice_base"
            if "INTO #DAILY_ITEM_TYPE_FACT" in upper:
                return "create_daily_item_type_fact"
            if "INTO #DAILY_ITEM_FACT" in upper:
                return "create_daily_item_fact"
            if "INTO #TOP_ITEMS" in upper:
                return "create_top_items"
            if "INTO #RECENT_HEADERS" in upper:
                return "create_recent_headers"
            if "CREATE CLUSTERED INDEX" in upper and "#INVOICE_BASE" in upper:
                return "create_invoice_base_index"
            if "FROM R_SALES_TRANS_H H" in upper and "TOTAL_BILL_NET" in upper and "#INVOICE_BASE" not in upper:
                return "previous_totals"
            if "GROUP BY REPORT_DATE, STO_ID, COLLECTION_CATEGORY" in upper:
                return "daily_collection"
            if "FROM #DAILY_ITEM_TYPE_FACT" in upper and "GROUP BY ITEM_TYPE" not in upper:
                return "daily_medicine"
            if "GROUP BY H.REPORT_DATE, H.STO_ID, H.EMP_ID" in upper:
                return "daily_user_facts"
            if "CONTRACT_NET_AMOUNT" in upper and "GROUP BY REPORT_DATE, STO_ID" in upper:
                return "daily_store_totals"
            if "FROM #INVOICE_BASE" in upper and "SUM(NET_AMOUNT)" in upper and "GROUP BY" not in upper:
                return "totals"
            if "GROUP BY COLLECTION_CATEGORY" in upper:
                return "collection"
            if "COMPANY_PART_AMOUNT" in upper:
                return "contract_bearing"
            if "FROM #DAILY_ITEM_TYPE_FACT" in upper and "GROUP BY ITEM_TYPE" in upper:
                return "medicine_split"
            if "TOTAL_UNITS_SOLD" in upper:
                return "product_kpis"
            if "LEFT JOIN EMPLOYEE" in upper:
                return "users"
            if "CURRENT_BALANCE" in upper:
                return "top_items"
            if "STRING_AGG" in upper and "FROM #RECENT_HEADERS" in upper:
                return "recent_invoices"
            if "FROM #DAILY_ITEM_FACT" in upper and "ITEM_EPLUS_ID" in upper:
                return "daily_item_facts"
            return "other"

        def _set_rows(self, columns, rows):
            self.description = [(column,) for column in columns]
            self.rows = rows

        def execute(self, sql, params=None):
            label = self._label(sql)
            self.executed.append((label, sql, params or []))
            self.labels.append(label)
            if label == "drop_temp_tables":
                self.drop_count += 1
                if self.fail_cleanup_drop and self.drop_count >= 2:
                    raise RuntimeError("cleanup drop failed")
            if self.fail_on_label == label:
                raise RuntimeError(f"{label} failed")

            self.description = []
            self.rows = []
            if label == "totals":
                self._set_rows(["total_sales", "invoice_count"], [(1000.0, 12)])
            elif label == "previous_totals":
                self._set_rows(["total_sales", "invoice_count"], [(800.0, 10)])
            elif label == "collection":
                self._set_rows(
                    ["collection_category", "invoice_count", "total_sales", "pct_of_total"],
                    [("cash", 8, 650.0, 65.0), ("delivery", 4, 350.0, 35.0)],
                )
            elif label == "contract_bearing":
                self._set_rows(
                    ["customer_bearing_amount", "company_part_amount", "bearing_pct"],
                    [(120.0, 80.0, 60.0)],
                )
            elif label == "medicine_split":
                self._set_rows(
                    ["item_type", "sales_amount"],
                    [("medicine", 700.0), ("non_medicine", 300.0)],
                )
            elif label == "product_kpis":
                self._set_rows(
                    [
                        "total_units_sold",
                        "unique_products_sold",
                        "total_product_sales",
                        "avg_products_per_invoice",
                        "stores_with_sales",
                        "avg_products_sold_per_store",
                    ],
                    [(42.0, 3, 990.0, 2.5, 2, 1.5)],
                )
            elif label == "users":
                self._set_rows(
                    ["emp_id", "employee_name", "invoice_count", "total_sales", "pct_of_total"],
                    [(15, "Ahmed", 7, 600.0, 60.0)],
                )
            elif label == "top_items":
                self._set_rows(
                    ["itm_id", "itm_code", "sale_times", "sold_qty", "total_sales", "current_balance"],
                    [(501, "ITM501", 5, 9.0, 450.0, 30.0)],
                )
            elif label == "recent_invoices":
                self._set_rows(
                    ["invoice_no", "sec_insert_date", "customer_name", "invoice_total", "item_count", "items"],
                    [("9001", datetime(2026, 7, 2, 10, 0, 0), "Customer", 250.0, 2, "ITM501, ITM502")],
                )
            elif label == "daily_store_totals":
                self._set_rows(
                    [
                        "report_date",
                        "sto_id",
                        "total_sales",
                        "invoice_count",
                        "customer_bearing_amount",
                        "company_part_amount",
                        "contract_net_amount",
                    ],
                    [(fields.Date.to_date("2026-07-01"), 99001, 1000.0, 12, 120.0, 80.0, 200.0)],
                )
            elif label == "daily_medicine":
                self._set_rows(
                    ["report_date", "sto_id", "item_type", "sales_amount"],
                    [
                        (fields.Date.to_date("2026-07-01"), 99001, "medicine", 700.0),
                        (fields.Date.to_date("2026-07-01"), 99001, "non_medicine", 300.0),
                    ],
                )
            elif label == "daily_collection":
                self._set_rows(
                    ["report_date", "sto_id", "collection_category", "invoice_count", "total_sales"],
                    [
                        (fields.Date.to_date("2026-07-01"), 99001, "cash", 8, 650.0),
                        (fields.Date.to_date("2026-07-01"), 99001, "delivery", 4, 350.0),
                    ],
                )
            elif label == "daily_user_facts":
                self._set_rows(
                    ["report_date", "sto_id", "emp_id", "employee_name", "invoice_count", "total_sales"],
                    [
                        (fields.Date.to_date("2026-07-01"), 99001, 15, "Ahmed", 7, 600.0),
                    ],
                )
            elif label == "daily_item_facts":
                self._set_rows(
                    [
                        "report_date",
                        "sto_id",
                        "item_eplus_id",
                        "item_code",
                        "item_type",
                        "sold_qty",
                        "sales_amount",
                        "invoice_count",
                        "sale_times",
                    ],
                    [
                        (fields.Date.to_date("2026-07-01"), 99001, 501, "ITM501", "medicine", 9.0, 450.0, 5, 5),
                    ],
                )

        def fetchall(self):
            return self.rows

        def close(self):
            self.closed = True

    class _FakeDashboardConnection:
        def __init__(self, cursor):
            self.cursor_obj = cursor
            self.cursor_calls = 0

        def cursor(self):
            self.cursor_calls += 1
            return self.cursor_obj

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Snapshot = cls.env["ab.sales.dashboard.snapshot"]
        cls.Service = cls.env["ab.sales.dashboard.service"]
        cls.Archive = cls.env["ab.sales.dashboard.report.archive"]
        cls.ReconciliationJob = cls.env["ab.sales.dashboard.reconciliation.job"]
        cls.Telemetry = cls.env["ab.sales.dashboard.report.telemetry"]
        cls.SyncState = cls.env["ab_sales_dashboard_sync_state"]

    def _patch_dashboard_connection(self, connection):
        @contextmanager
        def fake_connect(_service, *args, **kwargs):
            connection.connect_args = args
            connection.connect_kwargs = kwargs
            yield connection

        return patch.object(type(self.Service), "connect_eplus", fake_connect)

    def _payload(
        self,
        total_sales=1000.0,
        emp_id=15,
        employee_name="Ahmed",
        itm_id=501,
        itm_code="ITM501",
        invoice_no="9001",
    ):
        return {
            "total_sales": total_sales,
            "avg_daily_sales": 100.0,
            "prev_avg_daily_sales": 80.0,
            "avg_daily_growth_pct": 25.0,
            "invoice_count": 12,
            "medicine_sales": 700.0,
            "non_medicine_sales": 300.0,
            "customer_bearing_amount": 120.0,
            "company_part_amount": 80.0,
            "bearing_pct": 60.0,
            "total_units_sold": 42.0,
            "unique_products_sold": 3,
            "total_product_sales": 990.0,
            "avg_products_per_invoice": 2.5,
            "stores_with_sales": 2,
            "avg_products_sold_per_store": 1.5,
            "collection_lines": [
                {"collection_category": "cash", "invoice_count": 8, "total_sales": 650.0, "pct_of_total": 65.0},
                {"collection_category": "delivery", "invoice_count": 4, "total_sales": 350.0, "pct_of_total": 35.0},
            ],
            "user_lines": [
                {"emp_id": emp_id, "employee_name": employee_name, "invoice_count": 7, "total_sales": 600.0, "pct_of_total": 60.0},
            ],
            "item_lines": [
                {"itm_id": itm_id, "itm_code": itm_code, "sale_times": 5, "sold_qty": 9.0, "total_sales": 450.0, "current_balance": 30.0},
            ],
            "invoice_lines": [
                {
                    "invoice_no": invoice_no,
                    "sec_insert_date": "2026-07-02 10:00:00",
                    "customer_name": "Customer",
                    "invoice_total": 250.0,
                    "item_count": 2,
                    "items": "ITM501, ITM502",
                },
            ],
        }

    def _daily_payload(self, store_eplus_id=99001):
        return {
            "store_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store_eplus_id,
                "total_sales": 1000.0,
                "invoice_count": 12,
                "medicine_sales": 700.0,
                "non_medicine_sales": 300.0,
                "customer_bearing_amount": 120.0,
                "company_part_amount": 80.0,
                "contract_net_amount": 200.0,
            }],
            "collection_facts": [
                {
                    "report_date": fields.Date.to_date("2026-07-01"),
                    "store_eplus_id": store_eplus_id,
                    "category": "cash",
                    "invoice_count": 8,
                    "total_sales": 650.0,
                },
                {
                    "report_date": fields.Date.to_date("2026-07-01"),
                    "store_eplus_id": store_eplus_id,
                    "category": "delivery",
                    "invoice_count": 4,
                    "total_sales": 350.0,
                },
            ],
            "user_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store_eplus_id,
                "employee_eplus_id": 15,
                "employee_name": "Ahmed",
                "invoice_count": 7,
                "total_sales": 600.0,
            }],
            "item_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store_eplus_id,
                "item_eplus_id": 501,
                "item_code": "ITM501",
                "item_type": "medicine",
                "sold_qty": 9.0,
                "sales_amount": 450.0,
                "invoice_count": 5,
                "sale_times": 5,
            }],
        }

    def _create_coverage(self, store, *dates):
        return self.env["ab.sales.dashboard.sync.coverage"].sudo().create([
            {
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "sync_state": "synced",
                "synced_at": fields.Datetime.now(),
            }
            for report_date in dates
        ])

    def _create_fact_coverage(self, store, *dates, fact_type="item"):
        return self.env["ab.sales.dashboard.fact.coverage"].sudo().create([
            {
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "fact_type": fact_type,
                "sync_state": "synced",
                "synced_at": fields.Datetime.now(),
            }
            for report_date in dates
        ])

    def _seed_daily_summary_facts(self, store, date_from, days, total_sales=10.0, invoice_count=1):
        start = fields.Date.to_date(date_from)
        coverage_rows = []
        store_rows = []
        collection_rows = []
        for day_offset in range(days):
            report_date = fields.Date.add(start, days=day_offset)
            coverage_rows.append({
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "sync_state": "synced",
                "synced_at": fields.Datetime.now(),
            })
            store_rows.append({
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "total_sales": total_sales,
                "invoice_count": invoice_count,
                "medicine_sales": total_sales * 0.6,
                "non_medicine_sales": total_sales * 0.4,
                "customer_bearing_amount": total_sales * 0.2,
                "company_part_amount": total_sales * 0.1,
                "contract_net_amount": total_sales * 0.3,
            })
            collection_rows.append({
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "category": "cash",
                "invoice_count": invoice_count,
                "total_sales": total_sales,
            })
        self.env["ab.sales.dashboard.sync.coverage"].sudo().create(coverage_rows)
        self.env["ab.sales.dashboard.daily.store.fact"].sudo().create(store_rows)
        self.env["ab.sales.dashboard.daily.collection.fact"].sudo().create(collection_rows)

    def _seed_daily_item_facts(self, store, date_from, days, item_count=3, sales_amount=10.0):
        start = fields.Date.to_date(date_from)
        item_rows = []
        coverage_rows = []
        for day_offset in range(days):
            report_date = fields.Date.add(start, days=day_offset)
            coverage_rows.append({
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "fact_type": "item",
                "sync_state": "synced",
                "synced_at": fields.Datetime.now(),
            })
            for item_offset in range(item_count):
                item_id = 800000 + item_offset
                item_rows.append({
                    "report_date": report_date,
                    "store_id": store.id,
                    "store_eplus_id": int(store.eplus_serial),
                    "item_eplus_id": item_id,
                    "item_code": "ITEM%s" % item_id,
                    "item_name": "Product %s" % item_id,
                    "item_type": "medicine" if item_offset % 2 == 0 else "non_medicine",
                    "sold_qty": float(item_offset + 1),
                    "sales_amount": sales_amount * (item_offset + 1),
                    "invoice_count": item_offset + 1,
                    "sale_times": item_offset + 1,
                    "synced_at": fields.Datetime.now(),
                })
        self.env["ab.sales.dashboard.fact.coverage"].sudo().create(coverage_rows)
        self.env["ab.sales.dashboard.daily.item.fact"].sudo().create(item_rows)

    def _seed_daily_user_facts(self, store, date_from, days, total_sales=10.0, invoice_count=1):
        start = fields.Date.to_date(date_from)
        user_rows = []
        coverage_rows = []
        for day_offset in range(days):
            report_date = fields.Date.add(start, days=day_offset)
            coverage_rows.append({
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "fact_type": "user",
                "sync_state": "synced",
                "synced_at": fields.Datetime.now(),
            })
            user_rows.append({
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": int(store.eplus_serial),
                "employee_eplus_id": 15,
                "employee_name": "Ahmed",
                "invoice_count": invoice_count,
                "total_sales": total_sales,
                "synced_at": fields.Datetime.now(),
            })
        self.env["ab.sales.dashboard.fact.coverage"].sudo().create(coverage_rows)
        self.env["ab_sales_dashboard_daily_user_fact"].sudo().create(user_rows)

    def _store(self, code="TEST-DASH-STORE", eplus_serial=99001):
        return self.env["ab_store"].sudo().create({
            "name": code,
            "code": code,
            "allow_sale": True,
            "eplus_serial": eplus_serial,
        })

    def _snapshot_record(self, date_from="2026-07-01", date_to="2026-07-01", store=None):
        stores = store or self.env["ab_store"]
        return self.Snapshot.create({
            "name": "Test Dashboard Report",
            "date_from": date_from,
            "date_to": date_to,
            "store_ids": [(6, 0, stores.ids)],
            "store_filter_key": self.Snapshot._store_filter_key(stores),
            "store_filter_label": self.Snapshot._store_filter_label(stores),
        })

    def _reconciliation_job(self, date_from="2026-07-01", date_to="2026-07-31", stores=None):
        return self.ReconciliationJob.sudo().create({
            "name": "Test Reconciliation",
            "date_from": date_from,
            "date_to": date_to,
            "store_ids": [(6, 0, stores.ids)] if stores else False,
        })

    def _archive_for_snapshot(self, snapshot):
        action = snapshot.action_archive_report()
        archive = self.Archive.browse(action["res_id"])
        self.assertTrue(archive.exists())
        return archive

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

    def test_phase4_medicine_queries_read_shared_item_type_fact(self):
        create_sql = self.Service._daily_item_type_fact_create_sql()
        medicine_sql = self.Service._dashboard_medicine_sql()
        daily_sql = self.Service._dashboard_daily_medicine_sql()

        self.assertIn("INTO #daily_item_type_fact", create_sql)
        self.assertIn("FROM #daily_item_fact", create_sql)
        self.assertNotIn("FROM r_sales_trans_d d", create_sql)
        self.assertIn("FROM #daily_item_type_fact", medicine_sql)
        self.assertIn("FROM #daily_item_type_fact", daily_sql)
        self.assertNotIn("FROM r_sales_trans_d", medicine_sql)
        self.assertNotIn("FROM r_sales_trans_d", daily_sql)

    def test_phase4_recent_invoices_are_bounded_before_detail_aggregation(self):
        header_sql = self.Service._recent_headers_create_sql()
        invoice_sql = self.Service._dashboard_recent_invoices_sql()

        self.assertIn("SELECT TOP (20)", header_sql)
        self.assertIn("INTO #recent_headers", header_sql)
        self.assertIn("FROM #invoice_base", header_sql)
        self.assertIn("ORDER BY sec_insert_date DESC, sth_id DESC, sto_id DESC", header_sql)
        self.assertIn("FROM #recent_headers h", invoice_sql)
        self.assertIn("d.sth_id = h.sth_id AND d.std_stock_id = h.sto_id", invoice_sql)
        self.assertIn("GROUP BY h.sth_id, h.sto_id", invoice_sql)
        self.assertIn("AS item_pairs", invoice_sql)
        self.assertIn("NCHAR(31)", invoice_sql)
        self.assertIn("NCHAR(30)", invoice_sql)
        self.assertNotIn("FROM #invoice_base h", invoice_sql)

    def test_collection_category_uses_detail_line_discount_as_offer(self):
        create_sql = self.Service._invoice_base_create_sql("h.sec_insert_date >= ? AND h.sec_insert_date < ?")
        cte_sql = self.Service._invoice_base_cte("h.sec_insert_date >= ? AND h.sec_insert_date < ?")

        for sql in (create_sql, cte_sql):
            self.assertIn("OUTER APPLY", sql)
            self.assertIn("AS has_detail_discount", sql)
            self.assertIn("ISNULL(detail_offer.has_detail_discount, 0) = 1", sql)
            offer_case_start = sql.index("END AS is_offer")
            collection_case = sql[offer_case_start:]
            self.assertIn("THEN 'offer'", collection_case)
            self.assertIn("ISNULL(detail_offer.has_detail_discount, 0) = 1", collection_case)

    def test_collection_lines_are_normalized_to_four_categories(self):
        payload = self.Service._normalize_dashboard_payload(
            totals={},
            previous={},
            collections=[
                {"collection_category": "cash", "invoice_count": 3, "total_sales": 300.0, "pct_of_total": 75.0},
                {"collection_category": "delivery", "invoice_count": 1, "total_sales": 100.0, "pct_of_total": 25.0},
            ],
            bearing={},
            medicine=[],
            users=[],
            items=[],
            invoices=[],
            days=1,
        )

        categories = {row["collection_category"]: row for row in payload["collection_lines"]}
        self.assertEqual(set(categories), {"cash", "delivery", "contract", "offer"})
        self.assertEqual(categories["offer"]["invoice_count"], 0)
        self.assertEqual(categories["offer"]["total_sales"], 0.0)
        self.assertEqual(categories["contract"]["pct_of_total"], 0.0)

    def test_recent_invoice_items_are_normalized_to_odoo_product_names(self):
        item_pairs = "501\x1fITM501\x1e502\x1fITM502\x1e501\x1fITM501"
        with patch.object(type(self.Service), "_invoice_item_names_by_serial", return_value={
            501: "Product One",
            502: "Product Two",
        }) as mocked_names:
            payload = self.Service._normalize_dashboard_payload(
                totals={},
                previous={},
                collections=[],
                bearing={},
                medicine=[],
                users=[],
                items=[],
                invoices=[{
                    "invoice_no": "9001",
                    "customer_name": "Customer",
                    "items": "ITM501, ITM502, ITM501",
                    "item_pairs": item_pairs,
                }],
                days=1,
            )

        mocked_names.assert_called_once_with([501, 502, 501])
        invoice_line = payload["invoice_lines"][0]
        self.assertEqual(invoice_line["items"], "Product One, Product Two, Product One")
        self.assertNotIn("item_pairs", invoice_line)

    def test_recent_invoice_items_fall_back_to_code_when_product_name_missing(self):
        item_pairs = "501\x1fITM501\x1e999\x1fITM999"
        with patch.object(type(self.Service), "_invoice_item_names_by_serial", return_value={501: "Product One"}):
            summary = self.Service._invoice_item_names_summary(item_pairs, "ITM501, ITM999")

        self.assertEqual(summary, "Product One, ITM999")

    def test_recent_invoice_customer_display_prefers_confirmed_snapshot_sources(self):
        invoice_sql = self.Service._dashboard_recent_invoices_sql()

        self.assertIn("LEFT JOIN Customer_Delivery cd", invoice_sql)
        self.assertIn("FROM sales_deliv_info sdi", invoice_sql)
        self.assertIn("sdi.cust_id = h.cust_id", invoice_sql)
        self.assertIn("NULLIF(LTRIM(RTRIM(delivery.contact)), '')", invoice_sql)
        self.assertIn("NULLIF(LTRIM(RTRIM(cd.cd_contact_person)), '')", invoice_sql)
        self.assertIn("LIKE 'spare%'", invoice_sql)
        self.assertIn("__cash_customer__", invoice_sql)

    def test_cash_customer_sentinel_is_serialized_as_label(self):
        rows = [{
            "invoice_no": "9001",
            "sec_insert_date": datetime(2026, 7, 2, 10, 0, 0),
            "customer_name": "__cash_customer__",
            "invoice_total": 250.0,
            "item_count": 2,
            "items": "ITM501, ITM502",
        }]

        values = self.Snapshot._invoice_line_values(rows)

        self.assertEqual(values[0]["customer_name"], "Cash Customer")
        self.assertNotEqual(values[0]["customer_name"], "0")

    def test_cash_customer_sentinel_is_normalized_in_service_payload(self):
        payload = self.Service._normalize_dashboard_payload(
            totals={},
            previous={},
            collections=[],
            bearing={},
            medicine=[],
            users=[],
            items=[],
            invoices=[{"invoice_no": "9001", "customer_name": "__cash_customer__"}],
            days=1,
        )

        self.assertEqual(payload["invoice_lines"][0]["customer_name"], "Cash Customer")

    def test_contract_bearing_uses_customer_and_company_shares_without_negative_subtraction(self):
        bearing_sql = self.Service._dashboard_contract_bearing_sql()
        daily_sql = self.Service._dashboard_daily_store_totals_sql()

        self.assertIn("THEN net_amount ELSE 0 END", bearing_sql)
        self.assertIn("THEN net_amount + company_part ELSE 0 END", bearing_sql)
        self.assertIn("THEN net_amount + company_part ELSE 0 END", daily_sql)
        self.assertNotIn("net_amount - company_part", bearing_sql)
        self.assertNotIn("net_amount - company_part", daily_sql)

    def test_phase4_top_items_are_selected_before_stock_balance(self):
        create_sql = self.Service._top_items_create_sql()
        final_sql = self.Service._dashboard_top_items_sql(1)

        self.assertIn("SELECT TOP (20)", create_sql)
        self.assertIn("INTO #top_items", create_sql)
        self.assertIn("FROM #daily_item_fact", create_sql)
        self.assertNotIn("FROM r_sales_trans_d d", create_sql)
        self.assertIn("AS total_sales", create_sql)
        self.assertIn("ORDER BY sale_times DESC, sold_qty DESC", create_sql)
        self.assertIn("JOIN #top_items t ON t.itm_id = ics.itm_id", final_sql)
        self.assertIn("FROM #top_items t", final_sql)
        self.assertIn("t.total_sales", final_sql)
        self.assertIn("Item_Class_Store", final_sql)
        self.assertNotIn("OUTER APPLY", final_sql)

    def test_phase4_temp_table_cleanup_sql_covers_all_refresh_temp_tables(self):
        sql = self.Service._drop_dashboard_temp_tables_sql()
        self.assertIn("DROP TABLE #top_items", sql)
        self.assertIn("DROP TABLE #recent_headers", sql)
        self.assertIn("DROP TABLE #daily_item_type_fact", sql)
        self.assertIn("DROP TABLE #daily_item_fact", sql)
        self.assertIn("DROP TABLE #invoice_base", sql)

    def test_fetch_dashboard_data_reuses_one_mssql_session_and_temp_table(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            payload = self.Service.fetch_dashboard_data("2026-07-01", "2026-07-03", [123456, 234567])

        self.assertEqual(connection.cursor_calls, 1)
        self.assertEqual(cursor.labels.count("create_invoice_base_table"), 1)
        self.assertEqual(cursor.labels.count("create_invoice_base"), 1)
        self.assertEqual(cursor.labels.count("create_invoice_base_index"), 1)
        self.assertEqual(cursor.labels.count("create_daily_item_fact"), 1)
        self.assertEqual(cursor.labels.count("create_daily_item_type_fact"), 1)
        self.assertEqual(cursor.labels.count("create_top_items"), 1)
        self.assertEqual(cursor.labels.count("create_recent_headers"), 1)
        self.assertGreaterEqual(cursor.labels.count("drop_temp_tables"), 2)
        self.assertTrue(cursor.closed)
        self.assertEqual(cursor.timeout, self.Service._query_timeout_seconds())

        create_label, create_sql, create_params = next(item for item in cursor.executed if item[0] == "create_invoice_base")
        self.assertEqual(create_label, "create_invoice_base")
        self.assertIn("INSERT INTO #invoice_base", create_sql)
        self.assertIn("h.sto_id IN (?, ?)", create_sql)
        self.assertEqual(create_params[-2:], [123456, 234567])
        self.assertNotIn("123456", create_sql)
        self.assertNotIn("234567", create_sql)
        self.assertLess(cursor.labels.index("create_invoice_base_table"), cursor.labels.index("create_invoice_base"))
        self.assertLess(cursor.labels.index("create_invoice_base"), cursor.labels.index("create_invoice_base_index"))

        dashboard_labels = {"totals", "collection", "contract_bearing", "medicine_split", "product_kpis", "users", "top_items", "recent_invoices"}
        dashboard_sqls = [sql for label, sql, _params in cursor.executed if label in dashboard_labels]
        self.assertTrue(dashboard_sqls)
        self.assertTrue(all("#invoice_base" in sql or "#daily_item_type_fact" in sql or "#daily_item_fact" in sql or "#top_items" in sql or "#recent_headers" in sql for sql in dashboard_sqls))
        self.assertFalse(any("WITH invoice_base" in sql for sql in dashboard_sqls))

        previous_sql = next(sql for label, sql, _params in cursor.executed if label == "previous_totals")
        self.assertIn("FROM r_sales_trans_h h", previous_sql)
        self.assertNotIn("#invoice_base", previous_sql)

        top_params = next(params for label, _sql, params in cursor.executed if label == "top_items")
        self.assertEqual(top_params, [123456, 234567])
        self.assertEqual(payload["total_sales"], 1000.0)
        self.assertEqual(payload["avg_daily_sales"], 500.0)
        self.assertEqual(payload["prev_avg_daily_sales"], 400.0)
        self.assertEqual(payload["collection_lines"][0]["collection_category"], "cash")
        self.assertEqual(payload["total_units_sold"], 42.0)
        self.assertEqual(payload["unique_products_sold"], 3)
        self.assertEqual(payload["item_lines"][0]["itm_code"], "ITM501")
        self.assertEqual(payload["item_lines"][0]["total_sales"], 450.0)
        self.assertEqual(payload["invoice_lines"][0]["invoice_no"], "9001")

        medicine_sql = next(sql for label, sql, _params in cursor.executed if label == "medicine_split")
        self.assertIn("#daily_item_type_fact", medicine_sql)
        self.assertEqual(cursor.labels.count("create_daily_item_type_fact"), 1)

    def test_fetch_dashboard_data_parameterizes_single_store_scope(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            self.Service.fetch_dashboard_data("2026-07-01", "2026-07-02", [345678])

        _label, create_sql, create_params = next(item for item in cursor.executed if item[0] == "create_invoice_base")
        self.assertIn("h.sto_id IN (?)", create_sql)
        self.assertEqual(create_params[-1], 345678)
        self.assertNotIn("345678", create_sql)

    def test_dashboard_temp_table_cleanup_after_query_failure_preserves_original_exception(self):
        cursor = self._FakeDashboardCursor(fail_on_label="collection")
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            with self.assertRaisesRegex(RuntimeError, "collection failed"):
                self.Service.fetch_dashboard_data("2026-07-01", "2026-07-02", [123456])

        self.assertEqual(cursor.labels.count("create_invoice_base"), 1)
        self.assertEqual(cursor.labels.count("create_invoice_base_table"), 1)
        self.assertGreaterEqual(cursor.labels.count("drop_temp_tables"), 2)
        self.assertTrue(cursor.closed)

    def test_temp_table_cleanup_failure_does_not_replace_original_query_exception(self):
        cursor = self._FakeDashboardCursor(fail_on_label="collection", fail_cleanup_drop=True)
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            with self.assertRaisesRegex(RuntimeError, "collection failed"):
                self.Service.fetch_dashboard_data("2026-07-01", "2026-07-02", [123456])

        self.assertEqual(cursor.labels.count("drop_temp_tables"), 2)
        self.assertTrue(cursor.closed)

    def test_fetch_refresh_data_uses_one_session_for_dashboard_and_daily_facts(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            result = self.Service.fetch_refresh_data("2026-07-01", "2026-07-03", [123456, 234567])

        self.assertEqual(connection.cursor_calls, 1)
        self.assertEqual(cursor.labels.count("create_invoice_base_table"), 1)
        self.assertEqual(cursor.labels.count("create_invoice_base"), 1)
        self.assertEqual(cursor.labels.count("create_daily_item_type_fact"), 1)
        self.assertEqual(cursor.labels.count("create_top_items"), 1)
        self.assertEqual(cursor.labels.count("create_recent_headers"), 1)
        self.assertGreaterEqual(cursor.labels.count("drop_temp_tables"), 2)
        self.assertTrue(cursor.closed)
        self.assertIn("dashboard", result)
        self.assertIn("daily_store_facts", result)
        self.assertEqual(result["dashboard"]["total_sales"], 1000.0)
        self.assertEqual(result["daily_store_facts"]["store_facts"][0]["store_eplus_id"], 99001)
        self.assertIn("totals", cursor.labels)
        self.assertIn("daily_store_totals", cursor.labels)
        self.assertIn("daily_medicine", cursor.labels)
        self.assertIn("daily_collection", cursor.labels)
        daily_medicine_sql = next(sql for label, sql, _params in cursor.executed if label == "daily_medicine")
        self.assertIn("#daily_item_type_fact", daily_medicine_sql)
        medicine_sql = next(sql for label, sql, _params in cursor.executed if label == "medicine_split")
        self.assertNotIn("FROM r_sales_trans_d", medicine_sql)
        self.assertNotIn("FROM r_sales_trans_d", daily_medicine_sql)
        self.assertEqual(cursor.labels.count("create_daily_item_type_fact"), 1)

    def test_fetch_refresh_data_cleans_up_when_daily_facts_fail(self):
        cursor = self._FakeDashboardCursor(fail_on_label="daily_medicine")
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            with self.assertRaisesRegex(RuntimeError, "daily_medicine failed"):
                self.Service.fetch_refresh_data("2026-07-01", "2026-07-02", [123456])

        self.assertEqual(cursor.labels.count("create_invoice_base"), 1)
        self.assertEqual(cursor.labels.count("create_invoice_base_table"), 1)
        self.assertEqual(cursor.labels.count("create_daily_item_type_fact"), 1)
        self.assertIn("daily_store_totals", cursor.labels)
        self.assertIn("daily_medicine", cursor.labels)
        self.assertGreaterEqual(cursor.labels.count("drop_temp_tables"), 2)
        self.assertTrue(cursor.closed)

    def test_daily_fact_row_limit_rejects_oversized_shared_refresh_payload(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_fact_rows", "2")
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            with self.assertRaises(UserError):
                self.Service.fetch_refresh_data("2026-07-01", "2026-07-02", [123456])

        self.assertIn("daily_collection", cursor.labels)
        self.assertGreaterEqual(cursor.labels.count("drop_temp_tables"), 2)
        self.assertTrue(cursor.closed)

    def test_fetch_daily_store_facts_uses_temp_table_session_when_called_standalone(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            payload = self.Service.fetch_daily_store_facts("2026-07-01", "2026-07-02", [123456])

        self.assertEqual(connection.cursor_calls, 1)
        self.assertEqual(cursor.labels.count("create_invoice_base_table"), 1)
        self.assertEqual(cursor.labels.count("create_invoice_base"), 1)
        self.assertEqual(cursor.labels.count("create_daily_item_type_fact"), 1)
        self.assertIn("daily_store_totals", cursor.labels)
        self.assertIn("daily_medicine", cursor.labels)
        self.assertIn("daily_collection", cursor.labels)
        self.assertEqual(payload["store_facts"][0]["total_sales"], 1000.0)
        daily_sqls = [sql for label, sql, _params in cursor.executed if label.startswith("daily_")]
        self.assertTrue(all("#invoice_base" in sql or "#daily_item_type_fact" in sql or "#daily_item_fact" in sql for sql in daily_sqls))
        self.assertFalse(any("WITH invoice_base" in sql for sql in daily_sqls))

    def test_phase4_timing_events_are_emitted_without_sql_payloads(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        logger = self.Service._execute_statement.__func__.__globals__["_logger"]
        with self._patch_dashboard_connection(connection), \
             patch.object(logger, "info") as mocked_info:
            self.Service.fetch_dashboard_data("2026-07-01", "2026-07-02", [123456])

        messages = [" ".join(str(arg) for arg in call.args) for call in mocked_info.call_args_list if call.args]
        self.assertTrue(any("sales_dashboard_item_type_fact_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_top_items_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_recent_invoices_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_normalization_completed" in message for message in messages))
        self.assertFalse(any("SELECT " in message or "FROM " in message for message in messages))

    def test_daily_fact_persistence_guard_rejects_oversized_scope(self):
        store = self._store(code="TEST-DASH-FACT-LIMIT", eplus_serial=99006)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_fact_rows", "1")
        with self.assertRaises(UserError):
            self.Snapshot._upsert_daily_facts({
                "date_from": fields.Date.to_date("2026-07-01"),
                "date_to": fields.Date.to_date("2026-07-01"),
                "store_id": store.id,
            }, self._daily_payload(store.eplus_serial))

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
        store = self._store()
        with patch.object(type(service), "fetch_refresh_data", return_value={
            "dashboard": self._payload(),
            "daily_store_facts": self._daily_payload(),
        }) as mocked_fetch, \
             patch.object(type(service), "fetch_dashboard_data") as mocked_dashboard, \
             patch.object(type(service), "fetch_daily_store_facts") as mocked_daily:
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-07-01",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })

        mocked_fetch.assert_called_once()
        mocked_dashboard.assert_not_called()
        mocked_daily.assert_not_called()
        self.assertTrue(data["has_snapshot"])
        self.assertEqual(data["total_sales"], 1000.0)
        self.assertEqual(data["store_filter_label"], store.display_name)
        self.assertEqual(len(data["collection_lines"]), 2)
        self.assertEqual(data["item_lines"][0]["eplus_item_code"], "ITM501")
        self.assertEqual(data["invoice_lines"][0]["invoice_no"], "9001")
        fact = self.env["ab.sales.dashboard.daily.store.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(fact), 1)
        self.assertEqual(fact.total_sales, 1000.0)
        coverage = self.env["ab.sales.dashboard.sync.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage.sync_state, "synced")
        self.assertNotIn("category", coverage._fields)

        collection_facts = self.env["ab.sales.dashboard.daily.collection.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(set(collection_facts.mapped("category")), {"cash", "delivery"})
        user_facts = self.env["ab_sales_dashboard_daily_user_fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(user_facts), 1)
        self.assertEqual(user_facts.employee_eplus_id, 15)
        user_coverage = self.env["ab.sales.dashboard.fact.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("fact_type", "=", "user"),
        ])
        self.assertEqual(len(user_coverage), 1)

    def test_dashboard_range_allows_31_days(self):
        filters = self.Snapshot._normalize_filters({
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "store_id": 0,
        })
        self.assertEqual(filters["date_from"], fields.Date.to_date("2026-05-01"))
        self.assertEqual(filters["date_to"], fields.Date.to_date("2026-05-31"))

    def test_dashboard_filters_exclude_today_as_incomplete(self):
        today = fields.Date.context_today(self.Snapshot)
        yesterday = today - timedelta(days=1)
        filters = self.Snapshot._normalize_filters({
            "date_from": fields.Date.to_string(today),
            "date_to": fields.Date.to_string(today),
            "store_id": 0,
        })
        self.assertEqual(filters["date_from"], yesterday)
        self.assertEqual(filters["date_to"], yesterday)

    def test_dashboard_refresh_allows_ranges_above_configured_dashboard_max(self):
        payload = {"report_meta": {"mode": "summary"}}
        with patch.object(type(self.SyncState), "sync_dashboard_date_range", return_value={
            "synced_count": 62,
            "skipped_count": 0,
            "failed_count": 0,
            "failed": [],
        }) as mocked_sync, \
             patch.object(type(self.Snapshot), "get_dashboard_data", return_value=payload) as mocked_get:
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-05-01",
                "date_to": "2026-07-01",
                "store_id": 0,
            })

        args, kwargs = mocked_sync.call_args
        self.assertEqual(args[0], fields.Date.to_date("2026-05-01"))
        self.assertEqual(args[1], fields.Date.to_date("2026-07-01"))
        self.assertEqual(kwargs["store_id"], 0)
        self.assertTrue(kwargs["force_resync"])
        self.assertTrue(kwargs["descending"])
        self.assertTrue(kwargs["raise_on_error"])
        mocked_get.assert_called_once()
        self.assertEqual(data, payload)

    def test_dashboard_reversed_range_is_rejected_before_refresh(self):
        with patch.object(type(self.Snapshot), "_create_snapshot") as mocked_create:
            with self.assertRaises(UserError):
                self.Snapshot.refresh_dashboard_data({
                    "date_from": "2026-07-10",
                    "date_to": "2026-07-01",
                    "store_id": 0,
                })
        mocked_create.assert_not_called()

    def test_refresh_requires_explicit_date_from_and_date_to(self):
        with patch.object(type(self.Snapshot), "_create_snapshot") as mocked_create:
            with self.assertRaises(UserError):
                self.Snapshot.refresh_dashboard_data({"date_to": "2026-07-01", "store_id": 0})
            with self.assertRaises(UserError):
                self.Snapshot.refresh_dashboard_data({"date_from": "2026-07-01", "store_id": 0})
        mocked_create.assert_not_called()

    def test_invalid_max_dashboard_days_config_falls_back_to_31(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_dashboard_days", "invalid")
        self.assertEqual(self.Snapshot._dashboard_max_days(), 31)

    def test_empty_max_dashboard_days_config_falls_back_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_dashboard_days", "")
        self.assertEqual(self.Snapshot._dashboard_max_days(), 31)

    def test_negative_max_dashboard_days_config_cannot_disable_guard(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_dashboard_days", "-1")
        self.assertEqual(self.Snapshot._dashboard_max_days(), 31)
        with self.assertRaises(UserError):
            self.Snapshot._normalize_filters({
                "date_from": "2026-05-01",
                "date_to": "2026-06-01",
                "store_id": 0,
            })

    def test_query_batch_size_config_is_bounded_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_batch_size", "-1")
        self.assertEqual(self.Service._query_batch_size(), 1000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_batch_size", "999999")
        self.assertEqual(self.Service._query_batch_size(), 2000)

    def test_query_timeout_config_is_bounded_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_timeout_seconds", "-1")
        self.assertEqual(self.Service._query_timeout_seconds(), 120)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_timeout_seconds", "999999")
        self.assertEqual(self.Service._query_timeout_seconds(), 300)

    def test_max_daily_fact_rows_config_is_bounded_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_fact_rows", "invalid")
        self.assertEqual(self.Service._max_daily_fact_rows(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_fact_rows", "-1")
        self.assertEqual(self.Service._max_daily_fact_rows(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_fact_rows", "999999")
        self.assertEqual(self.Service._max_daily_fact_rows(), 50000)

    def test_max_daily_coverage_rows_config_is_bounded_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_coverage_rows", "invalid")
        self.assertEqual(self.Service._max_daily_coverage_rows(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_coverage_rows", "-1")
        self.assertEqual(self.Service._max_daily_coverage_rows(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_coverage_rows", "999999")
        self.assertEqual(self.Service._max_daily_coverage_rows(), 50000)

    def test_service_range_guard_rejects_before_bconnect_connection(self):
        with patch.object(type(self.Service), "connect_eplus") as mocked_connect:
            with self.assertRaises(UserError):
                self.Service.fetch_dashboard_data("2026-07-01", "2026-08-02", store_eplus_ids=[])
        mocked_connect.assert_not_called()

    def test_query_timeout_is_applied_when_cursor_supports_it(self):
        class FakeCursor:
            timeout = 0
            description = [("value",)]

            def execute(self, sql, params=None):
                self.sql = sql
                self.params = params or []

            def fetchall(self):
                return [(1,)]

        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_timeout_seconds", "77")
        cursor = FakeCursor()
        rows = self.Service._fetch_all(
            cursor,
            "SELECT 1 AS value",
            [],
            "test_query",
            fields.Datetime.to_datetime("2026-07-01 00:00:00"),
            fields.Datetime.to_datetime("2026-07-02 00:00:00"),
            0,
        )
        self.assertEqual(cursor.timeout, 77)
        self.assertEqual(rows, [{"value": 1}])

    def test_advisory_lock_success_permits_refresh(self):
        snapshot = self._snapshot_record()
        with patch.object(type(self.Snapshot), "_try_sales_dashboard_refresh_lock", return_value=True) as mocked_lock, \
             patch.object(type(self.Snapshot), "_create_snapshot", return_value=snapshot) as mocked_create:
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-07-01",
                "date_to": "2026-07-01",
                "store_id": 0,
            })
        mocked_lock.assert_called_once()
        mocked_create.assert_called_once()
        self.assertEqual(data["snapshot_id"], snapshot.id)

    def test_advisory_lock_failure_prevents_heavy_refresh(self):
        with patch.object(type(self.Snapshot), "_try_sales_dashboard_refresh_lock", return_value=False), \
             patch.object(type(self.Snapshot), "_create_snapshot") as mocked_create:
            with self.assertRaises(UserError):
                self.Snapshot.refresh_dashboard_data({
                    "date_from": "2026-07-01",
                    "date_to": "2026-07-01",
                    "store_id": 0,
                })
        mocked_create.assert_not_called()

    def test_get_dashboard_data_is_not_blocked_by_refresh_lock(self):
        with patch.object(type(self.Snapshot), "_try_sales_dashboard_refresh_lock", side_effect=AssertionError("lock should not be used")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-06-01",
                "date_to": "2026-06-02",
                "store_id": 0,
            })
        self.assertIn("has_snapshot", data)

    def test_dashboard_payload_contract_keys_are_preserved(self):
        service = self.env["ab.sales.dashboard.service"]
        store = self._store(code="TEST-DASH-PAYLOAD", eplus_serial=99005)
        expected_keys = {
            "date_from",
            "date_to",
            "store_id",
            "stores",
            "has_snapshot",
            "summary_only",
            "total_sales",
            "avg_daily_sales",
            "prev_avg_daily_sales",
            "avg_daily_growth_pct",
            "invoice_count",
            "bearing_pct",
            "company_part_amount",
            "medicine_sales",
            "non_medicine_sales",
            "collection_lines",
            "user_lines",
            "item_lines",
            "invoice_lines",
        }
        with patch.object(type(service), "fetch_refresh_data", return_value={
            "dashboard": self._payload(),
            "daily_store_facts": self._daily_payload(store.eplus_serial),
        }):
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-07-01",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })
        self.assertTrue(expected_keys.issubset(data.keys()))
        self.assertTrue(data["collection_lines"][0]["row_key"])
        self.assertTrue(data["user_lines"][0]["row_key"])
        self.assertTrue(data["item_lines"][0]["row_key"])
        self.assertTrue(data["invoice_lines"][0]["row_key"])

    def test_refresh_dashboard_updates_existing_snapshot_for_same_period_and_store(self):
        service = self.env["ab.sales.dashboard.service"]
        store = self._store(code="TEST-DASH-UPSERT", eplus_serial=99004)
        payload_1 = self._payload(total_sales=1000.0, emp_id=15, employee_name="Ahmed", itm_id=501, itm_code="ITM501", invoice_no="9001")
        payload_2 = self._payload(total_sales=2200.0, emp_id=16, employee_name="Mona", itm_id=502, itm_code="ITM502", invoice_no="9002")
        filters = {
            "date_from": "2026-07-01",
            "date_to": "2026-07-01",
            "store_id": store.id,
        }
        with patch.object(type(service), "fetch_refresh_data", side_effect=[
            {"dashboard": payload_1, "daily_store_facts": self._daily_payload(store.eplus_serial)},
            {"dashboard": payload_2, "daily_store_facts": self._daily_payload(store.eplus_serial)},
        ]) as mocked_fetch:
            first = self.Snapshot.refresh_dashboard_data(filters)
            second = self.Snapshot.refresh_dashboard_data(filters)

        self.assertEqual(mocked_fetch.call_count, 2)
        self.assertEqual(first["snapshot_id"], second["snapshot_id"])
        self.assertEqual(second["total_sales"], 2200.0)

        snapshots = self.Snapshot.search([
            ("date_from", "=", "2026-07-01"),
            ("date_to", "=", "2026-07-01"),
            ("store_filter_key", "=", str(store.eplus_serial)),
        ])
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(second["user_lines"][0]["employee_eplus_id"], 16)
        self.assertEqual(second["item_lines"][0]["eplus_item_code"], "ITM502")
        self.assertEqual(second["invoice_lines"][0]["invoice_no"], "9002")

    def test_phase6_snapshot_parent_lookup_is_not_duplicated(self):
        store = self._store(code="TEST-DASH-PARENT-LOOKUP", eplus_serial=99014)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        original_search = type(self.Snapshot).search
        search_calls = []

        def counted_search(recordset, *args, **kwargs):
            search_calls.append((args, kwargs))
            return original_search(recordset, *args, **kwargs)

        with patch.object(type(self.Snapshot), "search", counted_search):
            self.Snapshot._create_snapshot_from_payload(filters, self._payload())

        self.assertEqual(len(search_calls), 1)

    def test_phase6_snapshot_parent_reuses_existing_record_with_one_write(self):
        store = self._store(code="TEST-DASH-PARENT-WRITE", eplus_serial=99015)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        first = self.Snapshot._create_snapshot_from_payload(filters, self._payload(total_sales=1000.0))
        original_write = type(self.Snapshot).write
        write_calls = []

        def counted_write(recordset, *args, **kwargs):
            write_calls.append(recordset.ids)
            return original_write(recordset, *args, **kwargs)

        with patch.object(type(self.Snapshot), "write", counted_write):
            second = self.Snapshot._create_snapshot_from_payload(filters, self._payload(total_sales=2200.0))

        self.assertEqual(first.id, second.id)
        self.assertEqual(write_calls, [[first.id]])
        self.assertEqual(second.total_sales, 2200.0)

    def test_phase6_child_persistence_avoids_orm_create_and_unlink_loops(self):
        store = self._store(code="TEST-DASH-CHILD-SQL", eplus_serial=99016)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        child_models = [
            self.env["ab.sales.dashboard.collection.line"],
            self.env["ab.sales.dashboard.user.line"],
            self.env["ab.sales.dashboard.item.line"],
            self.env["ab.sales.dashboard.invoice.line"],
        ]
        patches = []
        for model in child_models:
            patches.append(patch.object(type(model), "create", side_effect=AssertionError("child ORM create should not run")))
            patches.append(patch.object(type(model), "unlink", side_effect=AssertionError("child ORM unlink should not run")))
        started = [patcher.start() for patcher in patches]
        try:
            snapshot = self.Snapshot._create_snapshot_from_payload(filters, self._payload())
        finally:
            for patcher in reversed(patches):
                patcher.stop()
            del started

        self.assertEqual(len(snapshot.collection_line_ids), 2)
        self.assertEqual(len(snapshot.user_line_ids), 1)
        self.assertEqual(len(snapshot.item_line_ids), 1)
        self.assertEqual(len(snapshot.invoice_line_ids), 1)

    def test_phase6_child_replacement_is_scoped_by_snapshot_and_serializes_immediately(self):
        store_1 = self._store(code="TEST-DASH-SCOPE-A", eplus_serial=99017)
        store_2 = self._store(code="TEST-DASH-SCOPE-B", eplus_serial=99018)
        filters_1 = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store_1.id,
        }
        filters_2 = dict(filters_1, store_id=store_2.id)
        snapshot_1 = self.Snapshot._create_snapshot_from_payload(filters_1, self._payload(emp_id=10, invoice_no="OLD"))
        snapshot_2 = self.Snapshot._create_snapshot_from_payload(filters_2, self._payload(emp_id=20, invoice_no="OTHER"))

        # Prime the one2many cache, then replace children through direct SQL.
        self.assertEqual(snapshot_1.user_line_ids.employee_eplus_id, 10)
        updated = self.Snapshot._create_snapshot_from_payload(filters_1, self._payload(emp_id=30, invoice_no="NEW"))
        data = self.Snapshot._serialize_dashboard(updated, filters_1)

        self.assertEqual(updated.id, snapshot_1.id)
        self.assertEqual(data["user_lines"][0]["employee_eplus_id"], 30)
        self.assertEqual(data["invoice_lines"][0]["invoice_no"], "NEW")
        self.assertNotEqual(data["invoice_lines"][0]["invoice_no"], "OLD")
        self.assertEqual(snapshot_2.user_line_ids.employee_eplus_id, 20)
        self.assertEqual(snapshot_2.invoice_line_ids.invoice_no, "OTHER")

    def test_phase6_child_ordering_and_row_keys_are_preserved(self):
        store = self._store(code="TEST-DASH-ORDER", eplus_serial=99019)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        payload = self._payload()
        payload["collection_lines"] = [
            {"collection_category": "delivery", "invoice_count": 1, "total_sales": 100.0, "pct_of_total": 10.0},
            {"collection_category": "cash", "invoice_count": 2, "total_sales": 900.0, "pct_of_total": 90.0},
        ]
        payload["user_lines"] = [
            {"emp_id": 1, "employee_name": "Low", "invoice_count": 1, "total_sales": 100.0, "pct_of_total": 10.0},
            {"emp_id": 2, "employee_name": "High", "invoice_count": 2, "total_sales": 900.0, "pct_of_total": 90.0},
        ]
        payload["item_lines"] = [
            {"itm_id": 701, "itm_code": "LOW", "sale_times": 1, "sold_qty": 1.0, "current_balance": 10.0},
            {"itm_id": 702, "itm_code": "HIGH", "sale_times": 3, "sold_qty": 8.0, "current_balance": 20.0},
        ]
        payload["invoice_lines"] = [
            {
                "invoice_no": "OLD",
                "sec_insert_date": "2026-07-01 10:00:00",
                "customer_name": "Old Customer",
                "invoice_total": 100.0,
                "item_count": 1,
                "items": "LOW",
            },
            {
                "invoice_no": "NEW",
                "sec_insert_date": "2026-07-02 10:00:00",
                "customer_name": "New Customer",
                "invoice_total": 900.0,
                "item_count": 2,
                "items": "HIGH",
            },
        ]

        snapshot = self.Snapshot._create_snapshot_from_payload(filters, payload)
        data = self.Snapshot._serialize_dashboard(snapshot, filters)

        self.assertEqual([row["category"] for row in data["collection_lines"]], ["cash", "delivery"])
        self.assertEqual([row["employee_eplus_id"] for row in data["user_lines"]], [2, 1])
        self.assertEqual([row["eplus_item_code"] for row in data["item_lines"]], ["HIGH", "LOW"])
        self.assertEqual([row["invoice_no"] for row in data["invoice_lines"]], ["NEW", "OLD"])
        self.assertTrue(all(row["row_key"] for row in data["collection_lines"]))
        self.assertTrue(all(row["row_key"] for row in data["user_lines"]))
        self.assertTrue(all(row["row_key"] for row in data["item_lines"]))
        self.assertTrue(all(row["row_key"] for row in data["invoice_lines"]))

    def test_phase6_child_insert_sql_is_parameterized_and_scoped(self):
        mapping = self.Snapshot._snapshot_child_mappings()["collection"]
        sql = self.Snapshot._snapshot_child_insert_sql(mapping, 2)

        self.assertIn("INSERT INTO ab_sales_dashboard_collection_line", sql)
        self.assertIn("snapshot_id", sql)
        self.assertEqual(sql.count("%s"), 18)
        self.assertNotIn("cash", sql)
        self.assertNotIn("delivery", sql)

    def test_phase6_child_batching_guard_and_timing_events(self):
        store = self._store(code="TEST-DASH-CHILD-BATCH", eplus_serial=99020)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_batch_size", "1")
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_snapshot_child_rows", "2")
        logger = self.Snapshot._persist_snapshot_children.__func__.__globals__["_logger"]
        with patch.object(logger, "info") as mocked_info:
            self.Snapshot._create_snapshot_from_payload(filters, self._payload())

        messages = [" ".join(str(arg) for arg in call.args) for call in mocked_info.call_args_list if call.args]
        self.assertTrue(any("event=sales_dashboard_snapshot_child_batch_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_snapshot_child_delete_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_snapshot_cache_invalidation_completed" in message for message in messages))
        self.assertTrue(any("batch_size=%s" in message for message in messages))

        payload = self._payload()
        payload["user_lines"] = [
            {"emp_id": idx, "employee_name": "User %s" % idx, "invoice_count": 1, "total_sales": 1.0, "pct_of_total": 1.0}
            for idx in range(3)
        ]
        with self.assertRaises(UserError):
            self.Snapshot._create_snapshot_from_payload(filters, payload)

    def test_phase6_max_snapshot_child_rows_config_is_bounded_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_snapshot_child_rows", "invalid")
        self.assertEqual(self.Snapshot._max_snapshot_child_rows(), 100)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_snapshot_child_rows", "-1")
        self.assertEqual(self.Snapshot._max_snapshot_child_rows(), 100)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_snapshot_child_rows", "999999")
        self.assertEqual(self.Snapshot._max_snapshot_child_rows(), 1000)

    def test_phase6_snapshot_persistence_introduces_no_manual_commit(self):
        source = self.Snapshot._persist_snapshot_children.__func__.__code__.co_names
        self.assertNotIn("commit", source)
        parent_source = self.Snapshot._persist_snapshot_parent.__func__.__code__.co_names
        self.assertNotIn("commit", parent_source)

    def test_phase7_archive_creates_explicit_immutable_records_without_changing_snapshot_reuse(self):
        store = self._store(code="TEST-DASH-ARCHIVE-REUSE", eplus_serial=99021)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        snapshot = self.Snapshot._create_snapshot_from_payload(filters, self._payload())
        first_archive = self._archive_for_snapshot(snapshot)
        second_archive = self._archive_for_snapshot(snapshot)

        self.assertNotEqual(first_archive.id, second_archive.id)
        self.assertNotEqual(first_archive.archive_number, second_archive.archive_number)
        self.assertEqual(first_archive.payload_hash, second_archive.payload_hash)

        refreshed = self.Snapshot._create_snapshot_from_payload(filters, self._payload(total_sales=2200.0))
        self.assertEqual(snapshot.id, refreshed.id)
        self.assertEqual(self.Archive.search_count([("snapshot_id", "=", snapshot.id)]), 2)

    def test_archived_reports_are_discoverable_from_reports(self):
        snapshot = self._snapshot_record()
        other_snapshot = self._snapshot_record(date_from="2026-07-02", date_to="2026-07-02")

        self.assertEqual(snapshot.archive_count, 0)
        archives = self._archive_for_snapshot(snapshot) | self._archive_for_snapshot(snapshot)
        snapshot.invalidate_recordset(["archive_ids", "archive_count"])

        self.assertEqual(snapshot.archive_count, 2)
        self.assertEqual(set(snapshot.archive_ids.ids), set(archives.ids))
        self.assertIn(snapshot, self.Snapshot.search([("archive_ids", "!=", False)]))
        self.assertNotIn(other_snapshot, self.Snapshot.search([("archive_ids", "!=", False)]))

        action = snapshot.action_view_archives()
        self.assertEqual(action["res_model"], "ab.sales.dashboard.report.archive")
        self.assertEqual(action["domain"], [("snapshot_id", "=", snapshot.id)])
        self.assertEqual(action["context"], {"create": False})

    def test_technical_reporting_menus_are_background_or_maintenance_only(self):
        maintenance = self.env.ref("ab_sales_dashboard.menu_ab_sales_dashboard_maintenance")
        reconciliation = self.env.ref("ab_sales_dashboard.menu_ab_sales_dashboard_reconciliation_jobs")
        analytics = self.env.ref("ab_sales_dashboard.menu_ab_sales_dashboard_reporting_analytics")

        self.assertFalse(self.env.ref("ab_sales_dashboard.menu_ab_sales_dashboard_report_archives").active)
        self.assertFalse(self.env.ref("ab_sales_dashboard.menu_ab_sales_dashboard_fact_decision").active)
        self.assertFalse(self.env.ref("ab_sales_dashboard.menu_ab_sales_dashboard_report_data").active)
        self.assertEqual(reconciliation.parent_id, maintenance)
        self.assertEqual(analytics.parent_id, maintenance)

    def test_phase7_archive_payload_matches_serialized_dashboard_and_preserves_ordering(self):
        store = self._store(code="TEST-DASH-ARCHIVE-PAYLOAD", eplus_serial=99022)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        payload = self._payload()
        payload["collection_lines"] = [
            {"collection_category": "delivery", "invoice_count": 1, "total_sales": 100.0, "pct_of_total": 10.0},
            {"collection_category": "cash", "invoice_count": 2, "total_sales": 900.0, "pct_of_total": 90.0},
        ]
        payload["user_lines"] = [
            {"emp_id": 1, "employee_name": "Low", "invoice_count": 1, "total_sales": 100.0, "pct_of_total": 10.0},
            {"emp_id": 2, "employee_name": "High", "invoice_count": 2, "total_sales": 900.0, "pct_of_total": 90.0},
        ]
        payload["item_lines"] = [
            {"itm_id": 701, "itm_code": "LOW", "sale_times": 1, "sold_qty": 1.0, "current_balance": 10.0},
            {"itm_id": 702, "itm_code": "HIGH", "sale_times": 3, "sold_qty": 8.0, "current_balance": 20.0},
        ]
        payload["invoice_lines"] = [
            {
                "invoice_no": "OLD",
                "sec_insert_date": "2026-07-01 10:00:00",
                "customer_name": "Old Customer",
                "invoice_total": 100.0,
                "item_count": 1,
                "items": "LOW",
            },
            {
                "invoice_no": "NEW",
                "sec_insert_date": "2026-07-02 10:00:00",
                "customer_name": "New Customer",
                "invoice_total": 900.0,
                "item_count": 2,
                "items": "HIGH",
            },
        ]
        snapshot = self.Snapshot._create_snapshot_from_payload(filters, payload)
        expected = self.Snapshot._serialize_dashboard(snapshot, filters)
        archive = self._archive_for_snapshot(snapshot)

        self.assertEqual(archive.payload_json, expected)
        self.assertEqual(set(archive.payload_json), set(expected))
        self.assertEqual([row["category"] for row in archive.payload_json["collection_lines"]], ["cash", "delivery"])
        self.assertEqual([row["employee_eplus_id"] for row in archive.payload_json["user_lines"]], [2, 1])
        self.assertEqual([row["eplus_item_code"] for row in archive.payload_json["item_lines"]], ["HIGH", "LOW"])
        self.assertEqual([row["invoice_no"] for row in archive.payload_json["invoice_lines"]], ["NEW", "OLD"])
        self.assertTrue(all(row["row_key"] for row in archive.payload_json["collection_lines"]))
        self.assertTrue(all(row["row_key"] for row in archive.payload_json["user_lines"]))
        self.assertTrue(all(row["row_key"] for row in archive.payload_json["item_lines"]))
        self.assertTrue(all(row["row_key"] for row in archive.payload_json["invoice_lines"]))

    def test_phase7_archive_payload_hash_is_deterministic(self):
        payload_a = {"b": 1, "a": {"text": "تقرير المبيعات", "rows": [1, 2]}}
        payload_b = {"a": {"rows": [1, 2], "text": "تقرير المبيعات"}, "b": 1}
        payload_c = {"a": {"rows": [1, 3], "text": "تقرير المبيعات"}, "b": 1}

        hash_a = self.Archive._compute_archive_payload_hash(payload_a)
        hash_b = self.Archive._compute_archive_payload_hash(payload_b)
        hash_c = self.Archive._compute_archive_payload_hash(payload_c)

        self.assertEqual(hash_a, hash_b)
        self.assertNotEqual(hash_a, hash_c)
        self.assertEqual(len(hash_a), 64)

    def test_phase7_archive_payload_size_guard_and_config_bounds(self):
        store = self._store(code="TEST-DASH-ARCHIVE-SIZE", eplus_serial=99023)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        snapshot = self.Snapshot._create_snapshot_from_payload(filters, self._payload())
        self._archive_for_snapshot(snapshot)

        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_archive_payload_bytes", "10")
        with self.assertRaises(UserError):
            snapshot.action_archive_report()

        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_archive_payload_bytes", "invalid")
        self.assertEqual(self.Archive._max_archive_payload_bytes(), 1048576)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_archive_payload_bytes", "-1")
        self.assertEqual(self.Archive._max_archive_payload_bytes(), 1048576)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_archive_payload_bytes", "999999999")
        self.assertEqual(self.Archive._max_archive_payload_bytes(), 10485760)

    def test_phase7_archive_is_immutable_except_cancellation(self):
        snapshot = self.Snapshot._create_snapshot_from_payload({
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": self._store(code="TEST-DASH-ARCHIVE-IMMUTABLE", eplus_serial=99024).id,
        }, self._payload())
        archive = self._archive_for_snapshot(snapshot)

        with self.assertRaises(UserError):
            archive.write({"payload_json": {"changed": True}})
        with self.assertRaises(UserError):
            archive.write({"date_from": fields.Date.to_date("2026-07-02")})
        with self.assertRaises(UserError):
            archive.write({"store_ids": [(5, 0, 0)]})
        with self.assertRaises(UserError):
            archive.unlink()

        archive.action_cancel()
        self.assertEqual(archive.state, "cancelled")

    def test_phase7_archive_creation_is_controlled_by_action_and_manager_group(self):
        store = self._store(code="TEST-DASH-ARCHIVE-ACCESS", eplus_serial=99025)
        snapshot = self.Snapshot._create_snapshot_from_payload({
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }, self._payload())
        with self.assertRaises(AccessError):
            self.Archive.create({
                "name": "Direct",
                "archive_number": "DIRECT",
                "date_from": snapshot.date_from,
                "date_to": snapshot.date_to,
                "archived_at": fields.Datetime.now(),
                "archived_by": self.env.user.id,
                "payload_json": {},
                "payload_hash": "0" * 64,
            })

        user = self.env.ref("base.public_user")
        with self.assertRaises(AccessError):
            snapshot.with_user(user).action_archive_report()

        action = snapshot.action_archive_report()
        archive = self.Archive.browse(action["res_id"])
        self.assertEqual(archive.archived_by.id, self.env.user.id)

    def test_phase7_archive_read_uses_stored_json_only(self):
        store = self._store(code="TEST-DASH-ARCHIVE-READ", eplus_serial=99026)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        snapshot = self.Snapshot._create_snapshot_from_payload(filters, self._payload())
        archive = self._archive_for_snapshot(snapshot)

        with patch.object(type(self.Service), "connect_eplus", side_effect=AssertionError("B-Connect should not be opened")), \
             patch.object(type(self.Service), "fetch_refresh_data", side_effect=AssertionError("refresh source should not run")), \
             patch.object(type(self.Snapshot), "_serialize_dashboard", side_effect=AssertionError("archive read should not reserialize snapshot")):
            payload = self.Archive.get_archived_dashboard_data(archive.id)

        self.assertEqual(payload, archive.payload_json)
        payload["total_sales"] = 999999.0
        self.assertNotEqual(payload["total_sales"], self.Archive.browse(archive.id).payload_json["total_sales"])

    def test_phase7_archive_payload_remains_unchanged_after_current_data_changes(self):
        store = self._store(code="TEST-DASH-ARCHIVE-STABLE", eplus_serial=99027)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        snapshot = self.Snapshot._create_snapshot_from_payload(filters, self._payload(total_sales=1000.0, invoice_no="ARCHIVED"))
        archive = self._archive_for_snapshot(snapshot)
        archived_payload = self.Archive.get_archived_dashboard_data(archive.id)

        updated = self.Snapshot._create_snapshot_from_payload(filters, self._payload(total_sales=2200.0, invoice_no="UPDATED"))
        self.env["ab.sales.dashboard.daily.store.fact"].sudo().create({
            "report_date": "2026-07-01",
            "store_id": store.id,
            "store_eplus_id": store.eplus_serial,
            "total_sales": 999.0,
            "invoice_count": 9,
        })

        self.assertEqual(updated.id, snapshot.id)
        self.assertEqual(self.Archive.get_archived_dashboard_data(archive.id), archived_payload)
        self.assertEqual(archived_payload["total_sales"], 1000.0)
        self.assertEqual(archived_payload["invoice_lines"][0]["invoice_no"], "ARCHIVED")

    def test_phase7_archives_are_not_dashboard_cache_or_refresh_inputs(self):
        store = self._store(code="TEST-DASH-ARCHIVE-ISOLATED", eplus_serial=99028)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        snapshot = self.Snapshot._create_snapshot_from_payload(filters, self._payload())
        archive = self._archive_for_snapshot(snapshot)

        with patch.object(type(self.Archive), "search", side_effect=AssertionError("archives must not be dashboard fallback")):
            data = self.Snapshot.get_dashboard_data(filters)
        self.assertEqual(data["snapshot_id"], snapshot.id)

        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(self.Archive), "write", side_effect=AssertionError("refresh must not update archives")), \
             patch.object(type(service), "fetch_refresh_data", return_value={
                 "dashboard": self._payload(total_sales=3300.0),
                 "daily_store_facts": self._daily_payload(store.eplus_serial),
             }):
            self.Snapshot.refresh_dashboard_data(filters)

        self.assertEqual(self.Archive.get_archived_dashboard_data(archive.id)["total_sales"], 1000.0)

    def test_phase7_archive_timing_events_and_no_manual_commit(self):
        snapshot = self.Snapshot._create_snapshot_from_payload({
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": self._store(code="TEST-DASH-ARCHIVE-LOGS", eplus_serial=99029).id,
        }, self._payload())
        logger = self.Snapshot.create_management_report_archive.__func__.__globals__["_logger"]
        with patch.object(logger, "info") as mocked_info:
            archive = self._archive_for_snapshot(snapshot)
            self.Archive.get_archived_dashboard_data(archive.id)

        messages = [" ".join(str(arg) for arg in call.args) for call in mocked_info.call_args_list if call.args]
        self.assertTrue(any("event=sales_dashboard_archive_started" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_archive_serialized" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_archive_hash_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_archive_created" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_archive_read_completed" in message for message in messages))
        self.assertFalse(any("ITM501, ITM502" in message for message in messages))
        self.assertNotIn("commit", self.Snapshot.create_management_report_archive.__code__.co_names)
        self.assertNotIn("commit", self.Archive.get_archived_dashboard_data.__code__.co_names)

    def test_get_dashboard_can_calculate_from_daily_facts_without_eplus(self):
        store = self._store(code="TEST-DASH-FACTS", eplus_serial=99002)
        self._create_coverage(store, "2026-07-01", "2026-07-02")
        self.env["ab.sales.dashboard.daily.store.fact"].sudo().create([
            {
                "report_date": "2026-07-01",
                "store_id": store.id,
                "store_eplus_id": store.eplus_serial,
                "total_sales": 100.0,
                "invoice_count": 2,
                "medicine_sales": 70.0,
                "non_medicine_sales": 30.0,
                "customer_bearing_amount": 20.0,
                "company_part_amount": 10.0,
                "contract_net_amount": 30.0,
            },
            {
                "report_date": "2026-07-02",
                "store_id": store.id,
                "store_eplus_id": store.eplus_serial,
                "total_sales": 200.0,
                "invoice_count": 4,
                "medicine_sales": 120.0,
                "non_medicine_sales": 80.0,
                "customer_bearing_amount": 10.0,
                "company_part_amount": 10.0,
                "contract_net_amount": 20.0,
            },
        ])
        self.env["ab.sales.dashboard.daily.collection.fact"].sudo().create([
            {
                "report_date": "2026-07-01",
                "store_id": store.id,
                "store_eplus_id": store.eplus_serial,
                "category": "cash",
                "invoice_count": 2,
                "total_sales": 100.0,
            },
            {
                "report_date": "2026-07-02",
                "store_id": store.id,
                "store_eplus_id": store.eplus_serial,
                "category": "cash",
                "invoice_count": 4,
                "total_sales": 200.0,
            },
        ])

        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-07-01",
            "date_to": "2026-07-02",
            "store_id": store.id,
        })

        self.assertTrue(data["has_snapshot"])
        self.assertEqual(data["data_source"], "odoo_daily_facts")
        self.assertTrue(data["summary_only"])
        self.assertEqual(data["total_sales"], 300.0)
        self.assertEqual(data["invoice_count"], 6)
        self.assertEqual(data["avg_daily_sales"], 150.0)
        self.assertEqual(data["medicine_sales"], 190.0)
        self.assertEqual(data["non_medicine_sales"], 110.0)
        self.assertEqual(data["collection_lines"][0]["category"], "cash")
        self.assertEqual(data["collection_lines"][0]["collection_category"], "cash")
        self.assertEqual(data["collection_lines"][0]["total_sales"], 300.0)
        zero_categories = {
            row["category"]: row
            for row in data["collection_lines"]
            if row["category"] != "cash"
        }
        self.assertEqual(set(zero_categories), {"delivery", "contract", "offer"})
        self.assertTrue(all(row["total_sales"] == 0.0 for row in zero_categories.values()))

    def test_daily_fallback_requires_sync_coverage(self):
        store = self._store(code="TEST-DASH-NO-COVERAGE", eplus_serial=99008)
        self.env["ab.sales.dashboard.daily.store.fact"].sudo().create({
            "report_date": "2026-07-01",
            "store_id": store.id,
            "store_eplus_id": store.eplus_serial,
            "total_sales": 100.0,
            "invoice_count": 1,
        })

        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-07-01",
            "date_to": "2026-07-01",
            "store_id": store.id,
        })

        self.assertFalse(data["has_snapshot"])
        self.assertEqual(data["total_sales"], 0.0)

    def test_phase8_summary_max_days_config_is_bounded_safely(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_summary_days", "invalid")
        self.assertEqual(self.Snapshot._summary_max_days(), 90)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_summary_days", "-1")
        self.assertEqual(self.Snapshot._summary_max_days(), 90)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_summary_days", "999999")
        self.assertEqual(self.Snapshot._summary_max_days(), 365)

    def test_phase8_refresh_over_90_days_uses_dashboard_sync(self):
        service = self.env["ab.sales.dashboard.service"]
        payload = {"report_meta": {"mode": "summary"}}
        with patch.object(type(service), "fetch_refresh_data", side_effect=AssertionError("refresh must use dashboard sync")) as mocked_fetch, \
             patch.object(type(self.SyncState), "sync_dashboard_date_range", return_value={
                 "synced_count": 92,
                 "skipped_count": 0,
                 "failed_count": 0,
                 "failed": [],
             }) as mocked_sync, \
             patch.object(type(self.Snapshot), "get_dashboard_data", return_value=payload):
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-04-01",
                "date_to": "2026-07-01",
                "store_id": 0,
            })

        args, kwargs = mocked_sync.call_args
        self.assertEqual(args[0], fields.Date.to_date("2026-04-01"))
        self.assertEqual(args[1], fields.Date.to_date("2026-07-01"))
        self.assertEqual(kwargs["store_id"], 0)
        self.assertEqual(data, payload)
        mocked_fetch.assert_not_called()

    def test_phase8_ninety_day_get_uses_daily_facts_without_bconnect(self):
        store = self._store(code="TEST-DASH-90D", eplus_serial=99030)
        self._seed_daily_summary_facts(store, "2026-04-03", 90, total_sales=10.0, invoice_count=1)
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "connect_eplus", side_effect=AssertionError("summary must not connect to B-Connect")), \
             patch.object(type(service), "fetch_refresh_data", side_effect=AssertionError("summary must not refresh from B-Connect")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-04-03",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })

        self.assertEqual(data["data_source"], "daily_facts")
        self.assertTrue(data["summary_only"])
        self.assertEqual(data["report_meta"]["mode"], "summary")
        self.assertEqual(data["report_meta"]["coverage_state"], "complete")
        self.assertEqual(data["report_meta"]["expected_store_days"], 90)
        self.assertEqual(data["report_meta"]["covered_store_days"], 90)
        self.assertEqual(data["total_sales"], 900.0)
        self.assertEqual(data["avg_daily_sales"], 10.0)
        self.assertEqual(data["medicine_sales"], 540.0)
        self.assertEqual(data["non_medicine_sales"], 360.0)
        self.assertEqual(data["bearing_pct"], 100.0 * 180.0 / 270.0)
        self.assertEqual(data["collection_lines"][0]["category"], "cash")
        self.assertEqual(data["collection_lines"][0]["total_sales"], 900.0)
        self.assertFalse(data["user_lines"])
        self.assertFalse(data["item_lines"])
        self.assertFalse(data["invoice_lines"])
        self.assertEqual(set(data["report_meta"]["unsupported_sections"]), {"sales_by_user", "top_items", "customer_sales"})

    def test_phase8_summary_partial_coverage_is_reported_not_silently_completed(self):
        store = self._store(code="TEST-DASH-PARTIAL", eplus_serial=99031)
        self._seed_daily_summary_facts(store, "2026-06-01", 10, total_sales=20.0, invoice_count=2)
        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-06-01",
            "date_to": "2026-07-02",
            "store_id": store.id,
        })

        self.assertEqual(data["report_meta"]["mode"], "summary")
        self.assertEqual(data["report_meta"]["coverage_state"], "partial")
        self.assertEqual(data["report_meta"]["expected_store_days"], 32)
        self.assertEqual(data["report_meta"]["covered_store_days"], 10)
        self.assertEqual(data["report_meta"]["missing_store_days"], 22)
        self.assertEqual(data["total_sales"], 200.0)
        self.assertEqual(data["avg_daily_sales"], 20.0)

    def test_phase8_summary_unavailable_coverage_returns_safe_empty_payload(self):
        store = self._store(code="TEST-DASH-UNAVAILABLE", eplus_serial=99032)
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "fetch_refresh_data", side_effect=AssertionError("unavailable summary must not refresh")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-06-01",
                "date_to": "2026-07-02",
                "store_id": store.id,
            })

        self.assertEqual(data["report_meta"]["mode"], "summary")
        self.assertEqual(data["report_meta"]["coverage_state"], "unavailable")
        self.assertEqual(data["total_sales"], 0.0)
        self.assertFalse(data["user_lines"])
        self.assertFalse(data["item_lines"])
        self.assertFalse(data["invoice_lines"])

    def test_phase8_summary_range_above_legacy_limit_uses_postgresql(self):
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "connect_eplus", side_effect=AssertionError("summary read must remain PostgreSQL-only")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-04-01",
                "date_to": "2026-06-30",
                "store_id": 0,
            })
        self.assertEqual(data["report_meta"]["mode"], "summary")

    def test_phase8_summary_previous_period_uses_daily_facts_only(self):
        store = self._store(code="TEST-DASH-PREV", eplus_serial=99033)
        self._seed_daily_summary_facts(store, "2026-05-01", 32, total_sales=50.0, invoice_count=1)
        self._seed_daily_summary_facts(store, "2026-06-02", 32, total_sales=100.0, invoice_count=2)
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "connect_eplus", side_effect=AssertionError("previous summary must not use B-Connect")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-06-02",
                "date_to": "2026-07-03",
                "store_id": store.id,
            })

        self.assertEqual(data["report_meta"]["coverage_state"], "complete")
        self.assertEqual(data["report_meta"]["previous_coverage_state"], "complete")
        self.assertEqual(data["avg_daily_sales"], 100.0)
        self.assertEqual(data["prev_avg_daily_sales"], 50.0)
        self.assertEqual(data["avg_daily_growth_pct"], 100.0)

    def test_phase8_summary_store_filter_reuses_daily_facts_without_exact_snapshot(self):
        store_1 = self._store(code="TEST-DASH-SUMMARY-A", eplus_serial=99034)
        store_2 = self._store(code="TEST-DASH-SUMMARY-B", eplus_serial=99035)
        self._seed_daily_summary_facts(store_1, "2026-06-01", 32, total_sales=10.0, invoice_count=1)
        self._seed_daily_summary_facts(store_2, "2026-06-01", 32, total_sales=100.0, invoice_count=1)

        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-06-01",
            "date_to": "2026-07-02",
            "store_id": store_1.id,
        })

        self.assertFalse(self.Snapshot.search([
            ("date_from", "=", "2026-06-01"),
            ("date_to", "=", "2026-07-02"),
            ("store_filter_key", "=", str(store_1.eplus_serial)),
        ]))
        self.assertEqual(data["report_meta"]["coverage_state"], "complete")
        self.assertEqual(data["total_sales"], 320.0)
        self.assertEqual(data["invoice_count"], 32)

    def test_phase9_reconciliation_config_bounds(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_branch_days", "invalid")
        self.assertEqual(self.Snapshot._max_reconciliation_branch_days(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_branch_days", "-1")
        self.assertEqual(self.Snapshot._max_reconciliation_branch_days(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_branch_days", "999999")
        self.assertEqual(self.Snapshot._max_reconciliation_branch_days(), 50000)

        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_chunks", "invalid")
        self.assertEqual(self.Snapshot._max_reconciliation_chunks(), 500)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_chunks", "-1")
        self.assertEqual(self.Snapshot._max_reconciliation_chunks(), 500)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_chunks", "999999")
        self.assertEqual(self.Snapshot._max_reconciliation_chunks(), 5000)

    def test_phase9_coverage_analysis_uses_postgresql_only_and_groups_chunks(self):
        store_1 = self._store(code="TEST-DASH-RECON-A", eplus_serial=99036)
        store_2 = self._store(code="TEST-DASH-RECON-B", eplus_serial=99037)
        self._create_coverage(store_1, "2026-07-01", "2026-07-02")
        self._create_fact_coverage(store_1, "2026-07-01", "2026-07-02")
        job = self._reconciliation_job("2026-07-01", "2026-07-04", store_1 | store_2)

        with patch.object(type(self.Service), "connect_eplus", side_effect=AssertionError("analysis must not use B-Connect")), \
             patch.object(type(self.Service), "fetch_refresh_data", side_effect=AssertionError("analysis must not refresh")):
            job.action_analyze_coverage()

        self.assertEqual(job.state, "ready")
        self.assertEqual(job.total_branch_days, 8)
        self.assertEqual(job.covered_branch_days, 2)
        self.assertEqual(job.missing_branch_days, 6)
        self.assertEqual(job.chunk_count, 2)
        chunks = job.chunk_ids.sorted("sequence")
        self.assertEqual((chunks[0].date_from, chunks[0].date_to), (fields.Date.to_date("2026-07-01"), fields.Date.to_date("2026-07-02")))
        self.assertEqual(chunks[0].store_ids, store_2)
        self.assertEqual((chunks[1].date_from, chunks[1].date_to), (fields.Date.to_date("2026-07-03"), fields.Date.to_date("2026-07-04")))
        self.assertEqual(set(chunks[1].store_ids.ids), set((store_1 | store_2).ids))
        self.assertTrue(all((chunk.date_to - chunk.date_from).days + 1 <= 31 for chunk in chunks))

    def test_phase9_complete_coverage_creates_no_missing_chunks(self):
        store = self._store(code="TEST-DASH-RECON-COMPLETE", eplus_serial=99038)
        self._create_coverage(store, "2026-07-01", "2026-07-02")
        self._create_fact_coverage(store, "2026-07-01", "2026-07-02")
        job = self._reconciliation_job("2026-07-01", "2026-07-02", store)

        job.action_analyze_coverage()

        self.assertEqual(job.state, "done")
        self.assertEqual(job.missing_branch_days, 0)
        self.assertFalse(job.chunk_ids)

    def test_phase9_reconciliation_guards_reject_oversized_scope_and_plan(self):
        store = self._store(code="TEST-DASH-RECON-GUARD", eplus_serial=99039)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_branch_days", "2")
        job = self._reconciliation_job("2026-07-01", "2026-07-03", store)
        with self.assertRaises(UserError):
            job.action_analyze_coverage()

        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_branch_days", "100")
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_reconciliation_chunks", "1")
        store_2 = self._store(code="TEST-DASH-RECON-GUARD-B", eplus_serial=99040)
        self._create_coverage(store, "2026-07-02")
        self._create_fact_coverage(store, "2026-07-02")
        job = self._reconciliation_job("2026-07-01", "2026-07-03", store | store_2)
        with self.assertRaises(UserError):
            job.action_analyze_coverage()

    def test_phase9_fact_only_source_uses_daily_queries_without_dashboard_sections(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        with self._patch_dashboard_connection(connection):
            payload = self.Service.fetch_daily_fact_data("2026-07-01", "2026-07-03", [123456])

        self.assertEqual(connection.cursor_calls, 1)
        self.assertIn("daily_store_totals", cursor.labels)
        self.assertIn("daily_medicine", cursor.labels)
        self.assertIn("daily_collection", cursor.labels)
        self.assertIn("daily_item_facts", cursor.labels)
        self.assertNotIn("users", cursor.labels)
        self.assertNotIn("top_items", cursor.labels)
        self.assertNotIn("recent_invoices", cursor.labels)
        self.assertIn("store_facts", payload)
        self.assertIn("collection_facts", payload)
        self.assertIn("item_facts", payload)

    def test_phase9_successful_reconciliation_persists_sparse_facts_and_coverage(self):
        store = self._store(code="TEST-DASH-RECON-SUCCESS", eplus_serial=99041)
        job = self._reconciliation_job("2026-07-01", "2026-07-01", store)
        job.action_analyze_coverage()
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(self.ReconciliationJob), "_try_sales_dashboard_refresh_lock", return_value=True), \
             patch.object(type(service), "fetch_daily_fact_data", return_value=self._daily_payload(store.eplus_serial)) as mocked_fetch:
            job.action_start_reconciliation()

        mocked_fetch.assert_called_once()
        self.assertEqual(job.state, "done")
        self.assertEqual(job.completed_chunk_count, 1)
        fact = self.env["ab.sales.dashboard.daily.store.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(fact), 1)
        self.assertEqual(fact.total_sales, 1000.0)
        coverage = self.env["ab.sales.dashboard.sync.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(coverage), 1)
        self.assertEqual(coverage.sync_state, "synced")
        item_fact = self.env["ab.sales.dashboard.daily.item.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("item_eplus_id", "=", 501),
        ])
        self.assertEqual(len(item_fact), 1)
        self.assertEqual(item_fact.sales_amount, 450.0)
        item_coverage = self.env["ab.sales.dashboard.fact.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("fact_type", "=", "item"),
        ])
        self.assertEqual(len(item_coverage), 1)
        self.assertEqual(item_coverage.sync_state, "synced")

    def test_phase9_failed_persistence_does_not_leave_successful_coverage(self):
        store = self._store(code="TEST-DASH-RECON-FAIL", eplus_serial=99042)
        job = self._reconciliation_job("2026-07-01", "2026-07-01", store)
        job.action_analyze_coverage()
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(self.ReconciliationJob), "_try_sales_dashboard_refresh_lock", return_value=True), \
             patch.object(type(service), "fetch_daily_fact_data", return_value=self._daily_payload(store.eplus_serial)), \
             patch.object(type(self.Snapshot), "_upsert_daily_facts", side_effect=RuntimeError("persistence failed")):
            job.action_start_reconciliation()

        self.assertEqual(job.state, "failed")
        self.assertEqual(job.failed_chunk_count, 1)
        coverage = self.env["ab.sales.dashboard.sync.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertFalse(coverage)
        item_coverage = self.env["ab.sales.dashboard.fact.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("fact_type", "=", "item"),
        ])
        self.assertFalse(item_coverage)

    def test_phase9_retry_skips_already_covered_failed_chunk_without_bconnect(self):
        store = self._store(code="TEST-DASH-RECON-SKIP", eplus_serial=99043)
        job = self._reconciliation_job("2026-07-01", "2026-07-01", store)
        job.action_analyze_coverage()
        chunk = job.chunk_ids
        chunk.write({"state": "failed", "error_message": "old failure"})
        job.write({"state": "failed"})
        self._create_coverage(store, "2026-07-01")
        self._create_fact_coverage(store, "2026-07-01")
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(self.ReconciliationJob), "_try_sales_dashboard_refresh_lock", return_value=True), \
             patch.object(type(service), "fetch_daily_fact_data", side_effect=AssertionError("covered retry should skip source")):
            job.action_retry_failed_chunks()

        self.assertEqual(chunk.state, "done")
        self.assertEqual(job.state, "done")

    def test_phase9_partial_success_marks_job_partial_and_uses_savepoints(self):
        store_1 = self._store(code="TEST-DASH-RECON-PART-A", eplus_serial=99044)
        store_2 = self._store(code="TEST-DASH-RECON-PART-B", eplus_serial=99045)
        self._create_coverage(store_1, "2026-07-02")
        self._create_fact_coverage(store_1, "2026-07-02")
        job = self._reconciliation_job("2026-07-01", "2026-07-02", store_1 | store_2)
        job.action_analyze_coverage()
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(self.ReconciliationJob), "_try_sales_dashboard_refresh_lock", return_value=True), \
             patch.object(type(service), "fetch_daily_fact_data", side_effect=[
                 self._daily_payload(store_2.eplus_serial),
                 RuntimeError("source failed"),
             ]):
            job.action_start_reconciliation()

        self.assertEqual(job.state, "partial")
        self.assertEqual(job.completed_chunk_count, 1)
        self.assertEqual(job.failed_chunk_count, 1)

    def test_phase9_reconciliation_is_manager_only_and_not_dashboard_read_path(self):
        store = self._store(code="TEST-DASH-RECON-ACCESS", eplus_serial=99046)
        job = self._reconciliation_job("2026-07-01", "2026-07-01", store)
        with self.assertRaises(AccessError):
            job.with_user(self.env.ref("base.public_user")).action_analyze_coverage()

        with patch.object(type(self.ReconciliationJob), "search", side_effect=AssertionError("dashboard read must not inspect reconciliation jobs")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-07-01",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })
        self.assertIn("has_snapshot", data)

    def test_phase9_reconciliation_path_introduces_no_manual_commit(self):
        self.assertNotIn("commit", self.ReconciliationJob._run_reconciliation_chunks.__code__.co_names)
        self.assertNotIn("commit", self.env["ab.sales.dashboard.reconciliation.chunk"]._execute_reconciliation_chunk.__code__.co_names)

    def test_phase10_item_fact_config_bounds_and_coverage_is_separate(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_item_fact_rows", "invalid")
        self.assertEqual(self.Snapshot._max_daily_item_fact_rows(), 750000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_item_fact_rows", "-1")
        self.assertEqual(self.Snapshot._max_daily_item_fact_rows(), 750000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_item_fact_rows", "9999999")
        self.assertEqual(self.Snapshot._max_daily_item_fact_rows(), 1000000)

        store = self._store(code="TEST-DASH-ITEM-COVERAGE", eplus_serial=99100)
        self._create_coverage(store, "2026-07-01")
        self.assertFalse(self.Snapshot._has_complete_fact_coverage("2026-07-01", "2026-07-01", [store.eplus_serial], 1, "item"))
        self._create_fact_coverage(store, "2026-07-01")
        self.assertTrue(self.Snapshot._has_complete_fact_coverage("2026-07-01", "2026-07-01", [store.eplus_serial], 1, "item"))

    def test_phase10_daily_item_facts_are_sparse_and_batched(self):
        store = self._store(code="TEST-DASH-ITEM-SPARSE", eplus_serial=99101)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        payload = self._daily_payload(store.eplus_serial)
        self.Snapshot._upsert_daily_facts(filters, payload)

        facts = self.env["ab.sales.dashboard.daily.item.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts.item_eplus_id, 501)
        self.assertEqual(facts.sales_amount, 450.0)
        self.assertFalse(self.env["ab.sales.dashboard.daily.item.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("item_eplus_id", "=", 999999),
        ]))
        item_coverage = self.env["ab.sales.dashboard.fact.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("fact_type", "=", "item"),
        ])
        self.assertEqual(len(item_coverage), 1)

    def test_phase10_item_fact_row_guard_rejects_oversized_payload(self):
        store = self._store(code="TEST-DASH-ITEM-GUARD", eplus_serial=99102)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_item_fact_rows", "1")
        payload = self._daily_payload(store.eplus_serial)
        payload["item_facts"].append(dict(payload["item_facts"][0], item_eplus_id=502, item_code="ITM502"))
        with self.assertRaises(UserError):
            self.Snapshot._upsert_daily_facts({
                "date_from": fields.Date.to_date("2026-07-01"),
                "date_to": fields.Date.to_date("2026-07-01"),
                "store_id": store.id,
            }, payload)
        self.assertFalse(self.env["ab.sales.dashboard.fact.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("fact_type", "=", "item"),
        ]))

    def test_phase10_summary_product_kpis_and_top_items_use_postgresql_only(self):
        store = self._store(code="TEST-DASH-ITEM-SUMMARY", eplus_serial=99103)
        self._seed_daily_summary_facts(store, "2026-04-03", 90, total_sales=100.0, invoice_count=2)
        self._seed_daily_item_facts(store, "2026-04-03", 90, item_count=3, sales_amount=10.0)
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "connect_eplus", side_effect=AssertionError("summary must not use B-Connect")), \
             patch.object(type(service), "fetch_refresh_data", side_effect=AssertionError("summary must not refresh")), \
             patch.object(type(service), "fetch_daily_fact_data", side_effect=AssertionError("summary must not reconcile")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-04-03",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })
        self.assertEqual(data["report_meta"]["mode"], "summary")
        self.assertEqual(data["report_meta"]["item_coverage_state"], "complete")
        self.assertNotIn("top_items", data["report_meta"]["unsupported_sections"])
        self.assertEqual(data["unique_products_sold"], 3)
        self.assertEqual(data["total_units_sold"], 540.0)
        self.assertEqual(data["total_product_sales"], 5400.0)
        self.assertTrue(data["item_lines"])

    def test_phase10_summary_user_lines_use_daily_user_facts(self):
        store = self._store(code="TEST-DASH-USER-SUMMARY", eplus_serial=99109)
        self._seed_daily_summary_facts(store, "2026-04-03", 90, total_sales=100.0, invoice_count=2)
        self._seed_daily_user_facts(store, "2026-04-03", 90, total_sales=80.0, invoice_count=1)
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "connect_eplus", side_effect=AssertionError("summary must not use B-Connect")):
            data = self.Snapshot.get_dashboard_data({
                "date_from": "2026-04-03",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })

        self.assertEqual(data["report_meta"]["mode"], "summary")
        self.assertEqual(data["report_meta"]["user_coverage_state"], "complete")
        self.assertNotIn("sales_by_user", data["report_meta"]["unsupported_sections"])
        self.assertEqual(data["user_lines"][0]["employee_eplus_id"], 15)
        self.assertEqual(data["user_lines"][0]["total_sales"], 7200.0)

    def test_phase10_partial_item_coverage_does_not_fake_top_items(self):
        store = self._store(code="TEST-DASH-ITEM-PARTIAL", eplus_serial=99104)
        self._seed_daily_summary_facts(store, "2026-06-01", 32, total_sales=10.0, invoice_count=1)
        self._seed_daily_item_facts(store, "2026-06-01", 1, item_count=2, sales_amount=10.0)
        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-06-01",
            "date_to": "2026-07-02",
            "store_id": store.id,
        })
        self.assertEqual(data["report_meta"]["mode"], "summary")
        self.assertEqual(data["report_meta"]["item_coverage_state"], "partial")
        self.assertIn("top_items", data["report_meta"]["unsupported_sections"])
        self.assertEqual(data["item_lines"], [])
        self.assertEqual(data["unique_products_sold"], 0)

    def test_phase10_daily_user_facts_are_sparse_but_coverage_is_recorded(self):
        store = self._store(code="TEST-DASH-USER-SPARSE", eplus_serial=99110)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        payload = self._daily_payload(store.eplus_serial)
        payload["user_facts"] = []
        self.Snapshot._upsert_daily_facts(filters, payload)

        self.assertFalse(self.env["ab_sales_dashboard_daily_user_fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ]))
        user_coverage = self.env["ab.sales.dashboard.fact.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("fact_type", "=", "user"),
        ])
        self.assertEqual(len(user_coverage), 1)

    def test_dashboard_sync_wizard_accepts_ranges_over_dashboard_limit_day_by_day(self):
        store = self._store(code="TEST-DASH-SYNC-WIZ", eplus_serial=99111)
        snapshot = self._snapshot_record("2026-05-01", "2026-05-01", store)
        with patch.object(type(self.Snapshot), "_create_snapshot", return_value=snapshot) as mocked_create:
            result = self.SyncState.sync_dashboard_date_range(
                "2026-05-01",
                "2026-06-05",
                store_id=store.id,
                force_resync=True,
            )

        self.assertEqual(result["synced_count"], 36)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(mocked_create.call_count, 36)
        called_dates = [call_args.args[0]["date_from"] for call_args in mocked_create.call_args_list]
        self.assertEqual(called_dates[0], fields.Date.to_date("2026-06-05"))
        self.assertEqual(called_dates[-1], fields.Date.to_date("2026-05-01"))

    def test_dashboard_sync_rejects_today_and_future_dates(self):
        today = fields.Date.context_today(self.SyncState)
        with self.assertRaises(UserError):
            self.SyncState.sync_dashboard_date_range(today, today, force_resync=True)

    def test_dashboard_sync_last_90_cron_uses_force_resync_range(self):
        wizard_model = self.env["ab_sales_dashboard_sync_wizard"]
        with patch.object(type(self.SyncState), "sync_dashboard_date_range", return_value={
            "synced_count": 90,
            "skipped_count": 0,
            "failed_count": 0,
            "failed": [],
        }) as mocked_sync:
            wizard_model.cron_sync_last_90_dashboard_days()

        args, kwargs = mocked_sync.call_args
        date_from = fields.Date.to_date(args[0])
        date_to = fields.Date.to_date(args[1])
        self.assertEqual((date_to - date_from).days, 89)
        self.assertTrue(kwargs["force_resync"])
        self.assertTrue(kwargs["descending"])

    def test_dashboard_sync_claims_done_days_descending_by_cursor(self):
        store_values = self.SyncState._store_scope_values(0)
        states = self.SyncState.create([
            dict(store_values, sync_date=fields.Date.to_date("2026-07-01"), state="done"),
            dict(store_values, sync_date=fields.Date.to_date("2026-07-02"), state="done"),
            dict(store_values, sync_date=fields.Date.to_date("2026-07-03"), state="done"),
        ])
        self.SyncState._set_sync_cursor("all", fields.Date.to_date("2026-07-03"))
        claimed = self.SyncState._claim_next_sync_state(
            fields.Date.to_date("2026-07-01"),
            fields.Date.to_date("2026-07-03"),
        )
        self.assertEqual(claimed.sync_date, fields.Date.to_date("2026-07-02"))

        self.SyncState._set_sync_cursor("all", fields.Date.to_date("2026-07-01"))
        claimed = self.SyncState._claim_next_sync_state(
            fields.Date.to_date("2026-07-01"),
            fields.Date.to_date("2026-07-03"),
        )
        self.assertEqual(claimed.sync_date, fields.Date.to_date("2026-07-03"))
        self.assertEqual(len(states), 3)

    def test_dashboard_sync_competing_poll_is_deferred_without_failed_day(self):
        sync_date = fields.Date.to_date("2026-01-15")
        self.SyncState.create(dict(
            self.SyncState._store_scope_values(0),
            sync_date=sync_date,
            state="pending",
        ))
        with patch.object(type(self.SyncState), "_try_sync_claim_lock", return_value=False):
            progress = self.SyncState.process_next_dashboard_sync_day(
                sync_date,
                sync_date,
                force_resync=True,
            )

        state = self.SyncState.search([
            ("sync_date", "=", sync_date),
            ("store_filter_key", "=", "all"),
        ], limit=1)
        self.assertEqual(progress["last_status"], "busy")
        self.assertTrue(progress["is_active"])
        self.assertEqual(progress["failed_days"], 0)
        self.assertEqual(state.state, "pending")
        self.assertFalse(state.error_message)

    def test_dashboard_sync_refresh_lock_busy_keeps_pending_state(self):
        store_values = self.SyncState._store_scope_values(0)
        state = self.SyncState.create(dict(
            store_values,
            sync_date=fields.Date.to_date("2026-01-16"),
            state="pending",
        ))

        @contextmanager
        def busy_refresh_lock(_snapshot):
            raise SalesDashboardRefreshBusyError("busy")
            yield

        with patch.object(type(self.Snapshot), "_sales_dashboard_refresh_lock", busy_refresh_lock):
            with self.assertRaises(SalesDashboardRefreshBusyError):
                state._sync_one_state_with_progress(force_resync=True)

        state.invalidate_recordset()
        self.assertEqual(state.state, "pending")
        self.assertFalse(state.started_at)
        self.assertFalse(state.finished_at)
        self.assertFalse(state.error_message)

    def test_dashboard_sync_range_can_propagate_original_source_error(self):
        sync_date = fields.Date.to_date("2026-01-17")
        with patch.object(
            type(self.SyncState),
            "_sync_one_state_with_progress",
            side_effect=RuntimeError("source failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "source failed"):
                self.SyncState.sync_dashboard_date_range(
                    sync_date,
                    sync_date,
                    raise_on_error=True,
                )

    def test_dashboard_sync_orchestration_introduces_no_manual_commit(self):
        methods = (
            self.SyncState.cron_sync_next_dashboard_day,
            self.SyncState.sync_dashboard_date_range,
            self.SyncState.process_next_dashboard_sync_day,
            self.SyncState._sync_one_state_with_progress,
        )
        for method in methods:
            self.assertNotIn("commit", method.__func__.__code__.co_names)
            self.assertNotIn("rollback", method.__func__.__code__.co_names)

    def test_dashboard_source_connection_fails_over_and_caches_healthy_candidate(self):
        calls = []

        @contextmanager
        def candidate_connection(_service, server=None, **kwargs):
            calls.append(server)
            if server == "primary":
                raise UserError("primary unavailable")
            yield "secondary connection"

        service_type = type(self.Service)
        with patch.object(service_type, "_dashboard_preferred_server", False), \
             patch.object(service_type, "_dashboard_source_candidates", return_value=["primary", "secondary"]), \
             patch.object(service_type, "connect_eplus", candidate_connection):
            with self.Service._dashboard_source_connection() as connection:
                self.assertEqual(connection, "secondary connection")
            self.assertEqual(service_type._dashboard_preferred_server, "secondary")

        self.assertEqual(calls, ["primary", "secondary"])

    def test_dashboard_source_connection_reports_all_candidates_unavailable(self):
        @contextmanager
        def unavailable_connection(_service, **kwargs):
            raise UserError("unavailable")
            yield

        service_type = type(self.Service)
        with patch.object(service_type, "_dashboard_preferred_server", False), \
             patch.object(service_type, "_dashboard_source_candidates", return_value=["primary", "secondary"]), \
             patch.object(service_type, "connect_eplus", unavailable_connection):
            with self.assertRaises(SalesDashboardSourceUnavailableError):
                with self.Service._dashboard_source_connection():
                    pass

    def test_dashboard_sync_source_outage_pauses_without_failing_days(self):
        sync_date = fields.Date.to_date("2026-01-20")
        state = self.SyncState.create(dict(
            self.SyncState._store_scope_values(0),
            sync_date=sync_date,
            state="pending",
        ))
        with patch.object(
            type(self.SyncState),
            "_sync_one_state_with_progress",
            side_effect=SalesDashboardSourceUnavailableError("source unavailable"),
        ):
            progress = self.SyncState.process_next_dashboard_sync_day(
                sync_date,
                sync_date,
                force_resync=True,
            )

        state.invalidate_recordset()
        self.assertEqual(progress["last_status"], "source_unavailable")
        self.assertTrue(progress["source_unavailable"])
        self.assertFalse(progress["is_active"])
        self.assertEqual(progress["failed_days"], 0)
        self.assertEqual(state.state, "pending")
        self.assertFalse(state.error_message)

    def test_dashboard_sync_rpcs_preserve_selected_store_scope(self):
        store = self._store(code="TEST-DASH-SYNC-SCOPE", eplus_serial=99130)
        filters = {"date_from": "2026-07-01", "date_to": "2026-07-07", "store_id": store.id}
        sync_type = type(self.SyncState)
        with patch.object(sync_type, "start_dashboard_sync_range", return_value={}) as start, \
             patch.object(sync_type, "dashboard_sync_progress", return_value={}) as progress, \
             patch.object(sync_type, "process_next_dashboard_sync_day", return_value={}) as process:
            self.Snapshot.start_dashboard_sync(filters)
            self.Snapshot.get_dashboard_sync_progress(filters)
            self.Snapshot.process_dashboard_sync_day(filters)

        self.assertEqual(start.call_args.kwargs["store_id"], store.id)
        self.assertEqual(progress.call_args.kwargs["store_id"], store.id)
        self.assertEqual(process.call_args.kwargs["store_id"], store.id)

    def test_section_pages_are_bounded_and_search_all_item_facts(self):
        store = self._store(code="TEST-DASH-ITEM-PAGE", eplus_serial=99131)
        self._seed_daily_summary_facts(store, "2026-07-01", 1, total_sales=1000.0, invoice_count=25)
        self._seed_daily_item_facts(store, "2026-07-01", 1, item_count=25, sales_amount=10.0)
        filters = {"date_from": "2026-07-01", "date_to": "2026-07-01", "store_id": store.id}

        first = self.Snapshot.get_dashboard_section_page(filters, "top_items", 1, "")
        second = self.Snapshot.get_dashboard_section_page(filters, "top_items", 2, "")
        searched = self.Snapshot.get_dashboard_section_page(filters, "top_items", 1, "ITEM800024")

        self.assertEqual(first["page_size"], 20)
        self.assertEqual(first["total_count"], 25)
        self.assertEqual(len(first["rows"]), 20)
        self.assertEqual(len(second["rows"]), 5)
        self.assertIs(first["rows"][0]["current_balance"], False)
        self.assertEqual(searched["total_count"], 1)
        self.assertEqual(searched["rows"][0]["eplus_item_code"], "ITEM800024")

    def test_section_pages_are_bounded_and_search_all_user_facts(self):
        store = self._store(code="TEST-DASH-USER-PAGE", eplus_serial=99132)
        self._seed_daily_summary_facts(store, "2026-07-01", 1, total_sales=3250.0, invoice_count=25)
        self._create_fact_coverage(store, "2026-07-01", fact_type="user")
        self.env["ab_sales_dashboard_daily_user_fact"].sudo().create([
            {
                "report_date": "2026-07-01",
                "store_id": store.id,
                "store_eplus_id": store.eplus_serial,
                "employee_eplus_id": 7000 + index,
                "employee_name": "Employee %02d" % index,
                "invoice_count": index + 1,
                "total_sales": float((index + 1) * 10),
                "synced_at": fields.Datetime.now(),
            }
            for index in range(25)
        ])
        filters = {"date_from": "2026-07-01", "date_to": "2026-07-01", "store_id": store.id}

        first = self.Snapshot.get_dashboard_section_page(filters, "sales_by_user", 1, "")
        second = self.Snapshot.get_dashboard_section_page(filters, "sales_by_user", 2, "")
        searched = self.Snapshot.get_dashboard_section_page(filters, "sales_by_user", 1, "Employee 03")

        self.assertEqual(first["total_count"], 25)
        self.assertEqual(len(first["rows"]), 20)
        self.assertEqual(len(second["rows"]), 5)
        self.assertEqual(searched["total_count"], 1)
        self.assertEqual(searched["rows"][0]["employee_name"], "Employee 03")

    def test_customer_section_page_is_store_scoped_and_bounded(self):
        store = self._store(code="TEST-DASH-CUSTOMER-PAGE", eplus_serial=99133)
        source_rows = [{
            "invoice_no": 9001,
            "sto_id": store.eplus_serial,
            "sec_insert_date": "2026-07-01 10:00:00",
            "customer_name": "Customer One",
            "invoice_total": 150.0,
            "item_count": 2,
            "items": "ITEM1, ITEM2",
        }]
        with patch.object(type(self.Service), "fetch_customer_sales_page", return_value={
            "rows": source_rows,
            "total_count": 41,
        }) as fetch:
            result = self.Snapshot.get_dashboard_section_page(
                {"date_from": "2026-07-01", "date_to": "2026-07-07", "store_id": store.id},
                "customer_sales",
                2,
                "Customer",
            )

        self.assertEqual(fetch.call_args.kwargs["store_eplus_ids"], [store.eplus_serial])
        self.assertEqual(fetch.call_args.kwargs["page_size"], 20)
        self.assertEqual(result["page"], 2)
        self.assertEqual(result["total_count"], 41)
        self.assertEqual(result["rows"][0]["row_key"], "customer_%s_9001" % store.eplus_serial)

    def test_customer_section_page_is_never_sourced_from_eplus_above_31_days(self):
        with patch.object(
            type(self.Service),
            "fetch_customer_sales_page",
            side_effect=AssertionError("long-range customer page must remain PostgreSQL-only"),
        ):
            result = self.Snapshot.get_dashboard_section_page(
                {"date_from": "2026-04-16", "date_to": "2026-07-14", "store_id": 0},
                "customer_sales",
                1,
                "",
            )
        self.assertFalse(result["available"])
        self.assertEqual(result["source"], "unsupported")

    def test_customer_page_sql_is_parameterized_and_fixed_to_20_rows(self):
        sql = self.Service._customer_sales_page_sql(
            "h.sec_insert_date >= ? AND h.sec_insert_date < ? AND h.sto_id IN (?)",
            has_search=True,
        )
        self.assertIn("OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", sql)
        self.assertIn("h.sto_id IN (?)", sql)
        self.assertIn("AS item_pairs", sql)
        self.assertNotIn("SELECT TOP (20)", sql)
        self.assertNotIn("Customer One", sql)
        self.assertNotIn("commit", self.Service.fetch_customer_sales_page.__func__.__code__.co_names)

    def test_customer_page_service_clamps_page_size_and_binds_search(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        rows = [{"invoice_no": 9001, "total_count": 41}]
        with self._patch_dashboard_connection(connection), patch.object(
            type(self.Service), "_fetch_all", return_value=rows
        ) as fetch:
            result = self.Service.fetch_customer_sales_page(
                "2026-07-01",
                "2026-07-08",
                store_eplus_ids=[99133],
                page=2,
                page_size=500,
                search_term="Customer One",
            )

        params = fetch.call_args.args[2]
        self.assertEqual(result["total_count"], 41)
        self.assertEqual(params[-5:], ["%Customer One%", "%Customer One%", "%Customer One%", 20, 20])
        self.assertIn(99133, params)
        self.assertTrue(cursor.closed)

    def test_customer_page_items_are_normalized_to_odoo_product_names(self):
        cursor = self._FakeDashboardCursor()
        connection = self._FakeDashboardConnection(cursor)
        rows = [{
            "invoice_no": 9001,
            "customer_name": "Customer One",
            "items": "ITM501, ITM502",
            "item_pairs": "501\x1fITM501\x1e502\x1fITM502",
            "total_count": 1,
        }]
        with self._patch_dashboard_connection(connection), patch.object(
            type(self.Service), "_fetch_all", return_value=rows
        ), patch.object(
            type(self.Service),
            "_invoice_item_names_by_serial",
            return_value={501: "Product One", 502: "Product Two"},
        ):
            result = self.Service.fetch_customer_sales_page(
                "2026-07-01",
                "2026-07-08",
                store_eplus_ids=[99133],
            )

        self.assertEqual(result["rows"][0]["items"], "Product One, Product Two")
        self.assertNotIn("item_pairs", result["rows"][0])

    def test_phase10_product_sales_report_is_not_top20_limited(self):
        store = self._store(code="TEST-DASH-PRODUCT-REPORT", eplus_serial=99105)
        self._seed_daily_item_facts(store, "2026-07-01", 1, item_count=25, sales_amount=5.0)
        rows = self.env["ab.sales.dashboard.product.sales.report"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ], limit=80)
        self.assertEqual(len(rows), 25)
        first = rows[0]
        self.assertGreater(first.total_sales, 0)
        self.assertEqual(first.average_selling_price, first.total_sales / first.units_sold)

    def test_sparse_daily_fact_persistence_replaces_stale_scope_rows(self):
        store = self._store(code="TEST-DASH-SPARSE", eplus_serial=99009)
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        first_payload = {
            "store_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store.eplus_serial,
                "total_sales": 500.0,
                "invoice_count": 5,
            }],
            "collection_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store.eplus_serial,
                "category": "offer",
                "invoice_count": 2,
                "total_sales": 500.0,
            }],
        }
        second_payload = {
            "store_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store.eplus_serial,
                "total_sales": 300.0,
                "invoice_count": 3,
            }],
            "collection_facts": [{
                "report_date": fields.Date.to_date("2026-07-01"),
                "store_eplus_id": store.eplus_serial,
                "category": "cash",
                "invoice_count": 3,
                "total_sales": 300.0,
            }],
        }

        self.Snapshot._upsert_daily_facts(filters, first_payload)
        self.Snapshot._upsert_daily_facts(filters, second_payload)

        collections = self.env["ab.sales.dashboard.daily.collection.fact"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(collections.mapped("category"), ["cash"])
        self.assertEqual(collections.total_sales, 300.0)
        coverage = self.env["ab.sales.dashboard.sync.coverage"].search([
            ("report_date", "=", "2026-07-01"),
            ("store_eplus_id", "=", store.eplus_serial),
        ])
        self.assertEqual(len(coverage), 1)

    def test_sparse_daily_fact_persistence_preserves_rows_outside_scope(self):
        store = self._store(code="TEST-DASH-SCOPE", eplus_serial=99010)
        self.env["ab.sales.dashboard.daily.collection.fact"].sudo().create({
            "report_date": "2026-07-02",
            "store_id": store.id,
            "store_eplus_id": store.eplus_serial,
            "category": "offer",
            "invoice_count": 1,
            "total_sales": 50.0,
        })
        self.Snapshot._upsert_daily_facts({
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }, self._daily_payload(store.eplus_serial))

        outside = self.env["ab.sales.dashboard.daily.collection.fact"].search([
            ("report_date", "=", "2026-07-02"),
            ("store_eplus_id", "=", store.eplus_serial),
            ("category", "=", "offer"),
        ])
        self.assertEqual(len(outside), 1)
        self.assertEqual(outside.total_sales, 50.0)

    def test_daily_fact_persistence_avoids_orm_search_and_write_loops(self):
        store = self._store(code="TEST-DASH-SQL-PERSIST", eplus_serial=99011)
        StoreFact = self.env["ab.sales.dashboard.daily.store.fact"]
        CollectionFact = self.env["ab.sales.dashboard.daily.collection.fact"]
        filters = {
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }
        with patch.object(type(StoreFact), "search", side_effect=AssertionError("store fact search should not run")), \
             patch.object(type(CollectionFact), "search", side_effect=AssertionError("collection fact search should not run")), \
             patch.object(type(StoreFact), "write", side_effect=AssertionError("store fact write should not run")), \
             patch.object(type(CollectionFact), "write", side_effect=AssertionError("collection fact write should not run")):
            self.Snapshot._upsert_daily_facts(filters, self._daily_payload(store.eplus_serial))

    def test_daily_fact_persistence_uses_bounded_batches_and_logs_events(self):
        store = self._store(code="TEST-DASH-BATCH", eplus_serial=99012)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.query_batch_size", "1")
        logger = self.Snapshot._upsert_daily_facts.__func__.__globals__["_logger"]
        with patch.object(logger, "info") as mocked_info:
            self.Snapshot._upsert_daily_facts({
                "date_from": fields.Date.to_date("2026-07-01"),
                "date_to": fields.Date.to_date("2026-07-01"),
                "store_id": store.id,
            }, self._daily_payload(store.eplus_serial))

        messages = [" ".join(str(arg) for arg in call.args) for call in mocked_info.call_args_list if call.args]
        self.assertTrue(any("event=sales_dashboard_fact_batch_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_scope_delete_completed" in message for message in messages))
        self.assertTrue(any("event=sales_dashboard_coverage_persistence_completed" in message for message in messages))
        self.assertFalse(any("event=sales_dashboard_zero_rows_completed" in message for message in messages))

    def test_daily_coverage_limit_rejects_oversized_scope(self):
        store = self._store(code="TEST-DASH-COVERAGE-LIMIT", eplus_serial=99013)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_coverage_rows", "0")
        self.assertEqual(self.Snapshot._max_daily_coverage_rows(), 10000)
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.max_daily_coverage_rows", "1")
        with self.assertRaises(UserError):
            self.Snapshot._upsert_daily_facts({
                "date_from": fields.Date.to_date("2026-07-01"),
                "date_to": fields.Date.to_date("2026-07-02"),
                "store_id": store.id,
            }, self._daily_payload(store.eplus_serial))

    def test_refresh_dashboard_fetches_full_report_when_only_daily_facts_exist(self):
        store = self._store(code="TEST-DASH-FULL-REFRESH", eplus_serial=99003)
        self.env["ab.sales.dashboard.daily.store.fact"].sudo().create({
            "report_date": "2026-07-01",
            "store_id": store.id,
            "store_eplus_id": store.eplus_serial,
            "total_sales": 500.0,
            "invoice_count": 5,
            "medicine_sales": 350.0,
            "non_medicine_sales": 150.0,
            "customer_bearing_amount": 0.0,
            "company_part_amount": 0.0,
            "contract_net_amount": 0.0,
        })
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "fetch_refresh_data", return_value={
            "dashboard": self._payload(),
            "daily_store_facts": self._daily_payload(store.eplus_serial),
        }) as mocked_fetch:
            data = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-07-01",
                "date_to": "2026-07-01",
                "store_id": store.id,
            })

        mocked_fetch.assert_called_once()
        self.assertTrue(data["has_snapshot"])
        self.assertTrue(data["snapshot_id"])
        self.assertFalse(data["summary_only"])
        self.assertEqual(data["total_sales"], 1000.0)
        self.assertTrue(data["user_lines"])
        self.assertTrue(data["item_lines"])
        self.assertTrue(data["invoice_lines"])

    def test_get_dashboard_returns_empty_payload_without_snapshot(self):
        data = self.Snapshot.get_dashboard_data({
            "date_from": "2026-06-01",
            "date_to": "2026-06-02",
            "store_id": 0,
        })
        self.assertFalse(data["has_snapshot"])
        self.assertEqual(data["total_sales"], 0.0)
        self.assertIn("stores", data)

    def _telemetry_vals(self, **overrides):
        vals = {
            "event_date": "2026-07-14",
            "event_type": "summary_read",
            "report_mode": "summary",
            "range_bucket": "32_60_days",
            "store_scope_bucket": "all_stores",
            "coverage_state": "complete",
            "requested_days": 45,
            "selected_store_count": 10,
            "duration_ms": 100,
            "maximum_duration_ms": 100,
            "result_size_bytes": 1000,
            "operation_count": 1,
            "unsupported_user_section": False,
            "unsupported_item_section": False,
            "unsupported_customer_section": False,
            "user_section_available": True,
            "item_section_available": True,
            "customer_section_available": True,
        }
        vals.update(overrides)
        return vals

    def test_phase12_dashboard_and_summary_reads_record_one_top_level_event(self):
        before = self.Telemetry.search_count([])
        self.Snapshot.get_dashboard_data({"date_from": "2026-07-01", "date_to": "2026-07-07", "store_id": 0})
        event = self.Telemetry.search([], order="id desc", limit=1)
        self.assertEqual(self.Telemetry.search_count([]), before + 1)
        self.assertEqual(event.event_type, "dashboard_read")
        self.assertEqual(event.report_mode, "full")

        self.Snapshot.get_dashboard_data({"date_from": "2026-06-01", "date_to": "2026-07-14", "store_id": 0})
        event = self.Telemetry.search([], order="id desc", limit=1)
        self.assertEqual(self.Telemetry.search_count([]), before + 2)
        self.assertEqual(event.event_type, "summary_read")
        self.assertEqual(event.report_mode, "summary")
        self.assertTrue(event.unsupported_user_section)
        self.assertTrue(event.unsupported_customer_section)

    def test_phase12_archive_read_records_archive_mode(self):
        store = self._store(code="TEST-DASH-P12-ARCHIVE", eplus_serial=99120)
        snapshot = self.Snapshot._create_snapshot_from_payload({
            "date_from": fields.Date.to_date("2026-07-01"),
            "date_to": fields.Date.to_date("2026-07-01"),
            "store_id": store.id,
        }, self._payload())
        archive = self._archive_for_snapshot(snapshot)
        before = self.Telemetry.search_count([])
        self.Archive.get_archived_dashboard_data(archive.id)
        event = self.Telemetry.search([], order="id desc", limit=1)
        self.assertEqual(self.Telemetry.search_count([]), before + 1)
        self.assertEqual((event.event_type, event.report_mode), ("archive_read", "archive"))
        self.assertTrue(event.archive_used)

    def test_phase12_telemetry_schema_contains_no_business_identifiers_or_payload(self):
        field_names = set(self.Telemetry._fields)
        forbidden = {
            "payload_json", "filter_json", "request_payload", "sql_text",
            "customer_id", "customer_name", "product_id", "product_name",
            "employee_id", "employee_name", "invoice_id", "invoice_no", "store_ids",
        }
        self.assertFalse(field_names & forbidden)

    def test_phase12_range_and_store_scope_buckets(self):
        self.assertEqual(self.Telemetry._range_bucket(1), "1_7_days")
        self.assertEqual(self.Telemetry._range_bucket(7), "1_7_days")
        self.assertEqual(self.Telemetry._range_bucket(8), "8_31_days")
        self.assertEqual(self.Telemetry._range_bucket(31), "8_31_days")
        self.assertEqual(self.Telemetry._range_bucket(32), "32_60_days")
        self.assertEqual(self.Telemetry._range_bucket(60), "32_60_days")
        self.assertEqual(self.Telemetry._range_bucket(61), "61_90_days")
        self.assertEqual(self.Telemetry._range_bucket(90), "61_90_days")
        self.assertEqual(self.Telemetry._store_scope_bucket(1), "single_store")
        self.assertEqual(self.Telemetry._store_scope_bucket(2), "2_10_stores")
        self.assertEqual(self.Telemetry._store_scope_bucket(11), "11_50_stores")
        self.assertEqual(self.Telemetry._store_scope_bucket(51), "51_100_stores")
        self.assertEqual(self.Telemetry._store_scope_bucket(101), "over_100_stores")
        self.assertEqual(self.Telemetry._store_scope_bucket(20, all_stores=True), "all_stores")

    def test_phase12_item_availability_follows_actual_report_meta(self):
        complete = self.Telemetry.record_operation(
            "summary_read", "summary",
            filters={"date_from": "2026-06-01", "date_to": "2026-07-14", "store_id": 0},
            report_meta={"mode": "summary", "coverage_state": "complete", "requested_days": 44, "unsupported_sections": ["sales_by_user", "customer_sales"]},
            result={"report_meta": {"unsupported_sections": ["sales_by_user", "customer_sales"]}},
        )
        partial = self.Telemetry.record_operation(
            "summary_read", "summary",
            filters={"date_from": "2026-06-01", "date_to": "2026-07-14", "store_id": 0},
            report_meta={"mode": "summary", "coverage_state": "partial", "requested_days": 44, "unsupported_sections": ["sales_by_user", "top_items", "customer_sales"]},
            result={},
        )
        self.assertTrue(complete.item_section_available)
        self.assertFalse(complete.unsupported_item_section)
        self.assertFalse(partial.item_section_available)
        self.assertTrue(partial.unsupported_item_section)

    def test_phase12_result_size_and_duration_are_measured_and_clamped(self):
        event = self.Telemetry.record_operation(
            "dashboard_read", "full",
            filters={"date_from": "2026-07-01", "date_to": "2026-07-01", "store_id": 1},
            duration_ms=-5,
            result={"total_sales": 10.0, "lines": [1, 2, 3]},
            report_meta={"coverage_state": "complete", "requested_days": 1, "unsupported_sections": []},
            selected_store_count=1,
        )
        self.assertEqual(event.duration_ms, 0)
        self.assertGreater(event.result_size_bytes, 0)
        self.assertNotIn("payload", event._fields)

    def test_phase12_telemetry_failure_never_breaks_read_or_hides_refresh_error(self):
        with patch.object(type(self.Telemetry), "create", side_effect=RuntimeError("telemetry failed")):
            data = self.Snapshot.get_dashboard_data({"date_from": "2026-07-01", "date_to": "2026-07-01", "store_id": 0})
        self.assertIn("total_sales", data)

        service = self.env["ab.sales.dashboard.service"]
        store = self._store(code="TEST-DASH-P12-FAIL", eplus_serial=99121)
        with patch.object(type(service), "fetch_refresh_data", side_effect=RuntimeError("source failed")), \
             patch.object(type(self.Telemetry), "create", side_effect=RuntimeError("telemetry failed")):
            with self.assertRaisesRegex(RuntimeError, "source failed"):
                self.Snapshot.refresh_dashboard_data({"date_from": "2026-07-01", "date_to": "2026-07-01", "store_id": store.id})

    def test_phase12_retention_cleanup_is_bounded_sql_without_orm_loading(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.telemetry_cleanup_batch_size", "1")
        self.Telemetry.sudo().create([
            self._telemetry_vals(event_date="2025-01-01"),
            self._telemetry_vals(event_date="2025-01-02"),
        ])
        before = self.Telemetry.search_count([])
        with patch.object(type(self.Telemetry), "search", side_effect=AssertionError("cleanup must not ORM-load telemetry")):
            deleted = self.Telemetry._cron_cleanup_telemetry()
        self.assertEqual(deleted, 1)
        self.assertEqual(self.Telemetry.search_count([]), before - 1)

    def test_phase12_fact_volume_analysis_uses_aggregate_sql_without_fact_loading(self):
        ItemFact = self.env["ab.sales.dashboard.daily.item.fact"]
        with patch.object(type(ItemFact), "search", side_effect=AssertionError("analysis must not ORM-load item facts")):
            result = self.Telemetry.get_fact_volume_analysis()
        self.assertIn("daily_store_facts", result)
        self.assertIn("daily_collection_facts", result)
        self.assertIn("daily_item_facts", result)
        self.assertIn("coverage", result)
        self.assertIn("snapshots", result)
        self.assertIn("archives", result)
        self.assertIn("telemetry", result)

    def test_phase12_fact_grain_recommendation_rules(self):
        scenarios = [
            (8, 2, "employee"),
            (2, 8, "customer"),
            (8, 6, "both_employee_first"),
            (6, 8, "both_customer_first"),
            (2, 2, "neither"),
        ]
        for user_gap, customer_gap, expected in scenarios:
            self.Telemetry.sudo().search([]).unlink()
            vals_list = []
            for index in range(10):
                vals_list.append(self._telemetry_vals(
                    unsupported_user_section=index < user_gap,
                    user_section_available=index >= user_gap,
                    unsupported_customer_section=index < customer_gap,
                    customer_section_available=index >= customer_gap,
                    unsupported_item_section=index < 5,
                    item_section_available=index >= 5,
                ))
            self.Telemetry.sudo().create(vals_list)
            recommendation = self.Telemetry.get_fact_grain_recommendation()
            self.assertEqual(recommendation["recommendation_code"], expected)
            self.assertEqual(recommendation["long_range_item_unsupported_count"], 5)
            self.assertNotIn("item", recommendation["recommendation_code"])

    def test_phase12_warning_thresholds_log_without_rejecting_operations(self):
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("ab_reports.warn_dashboard_duration_ms", "1")
        params.set_param("ab_reports.warn_payload_size_bytes", "1")
        logger = self.Telemetry._log_health_warnings.__func__.__globals__["_logger"]
        with patch.object(logger, "warning") as warning:
            event = self.Telemetry.record_operation(
                "dashboard_read", "full",
                filters={"date_from": "2026-07-01", "date_to": "2026-07-01", "store_id": 1},
                duration_ms=2,
                result={"large": "payload"},
                report_meta={"coverage_state": "complete", "requested_days": 1, "unsupported_sections": []},
                selected_store_count=1,
            )
        self.assertTrue(event)
        messages = [call.args[0] for call in warning.call_args_list]
        self.assertTrue(any("sales_dashboard_slow_operation" in message for message in messages))
        self.assertTrue(any("sales_dashboard_large_payload" in message for message in messages))

    def test_phase12_item_fact_warning_and_false_product_sql_null_regression(self):
        self.env["ir.config_parameter"].sudo().set_param("ab_reports.warn_daily_item_fact_rows", "1")
        store = self._store(code="TEST-DASH-P12-NULL", eplus_serial=99122)
        payload = self._daily_payload(store.eplus_serial)
        payload["item_facts"] = [{
            "report_date": fields.Date.to_date("2026-07-01"),
            "store_eplus_id": store.eplus_serial,
            "item_eplus_id": 99999991,
            "item_code": "UNMAPPED-P12",
            "item_type": "medicine",
            "sold_qty": 1.0,
            "sales_amount": 10.0,
            "invoice_count": 1,
            "sale_times": 1,
        }, {
            "report_date": fields.Date.to_date("2026-07-01"),
            "store_eplus_id": store.eplus_serial,
            "item_eplus_id": 99999992,
            "item_code": "UNMAPPED-P12-B",
            "item_type": "medicine",
            "sold_qty": 1.0,
            "sales_amount": 10.0,
            "invoice_count": 1,
            "sale_times": 1,
        }]
        self.Snapshot._upsert_daily_facts({"date_from": fields.Date.to_date("2026-07-01"), "date_to": fields.Date.to_date("2026-07-01"), "store_id": store.id}, payload)
        facts = self.env["ab.sales.dashboard.daily.item.fact"].search([("store_eplus_id", "=", store.eplus_serial)])
        self.assertEqual(len(facts), 2)
        self.assertFalse(facts.mapped("product_id"))
        logger = self.Telemetry.get_fact_volume_analysis.__func__.__globals__["_logger"]
        with patch.object(logger, "warning") as warning:
            self.Telemetry.get_fact_volume_analysis()
        self.assertTrue(any("sales_dashboard_fact_volume_warning" in call.args[0] for call in warning.call_args_list))

    def test_phase12_preserves_long_range_postgresql_and_read_reconciliation_isolation(self):
        service = self.env["ab.sales.dashboard.service"]
        with patch.object(type(service), "connect_eplus", side_effect=AssertionError("90-day read must remain PostgreSQL-only")), \
             patch.object(type(self.ReconciliationJob), "search", side_effect=AssertionError("dashboard read must not inspect reconciliation")):
            data = self.Snapshot.get_dashboard_data({"date_from": "2026-04-16", "date_to": "2026-07-14", "store_id": 0})
        self.assertEqual(data["report_meta"]["mode"], "summary")
        with patch.object(type(self.SyncState), "sync_dashboard_date_range", return_value={
            "synced_count": 90,
            "skipped_count": 0,
            "failed_count": 0,
            "failed": [],
            "deferred": False,
        }) as mocked_sync, patch.object(type(self.Snapshot), "get_dashboard_data", return_value=data):
            refreshed = self.Snapshot.refresh_dashboard_data({
                "date_from": "2026-04-16",
                "date_to": "2026-07-14",
                "store_id": 0,
            })
        mocked_sync.assert_called_once()
        self.assertEqual(refreshed, data)
