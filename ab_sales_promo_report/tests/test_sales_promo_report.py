import base64
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from odoo.addons.ab_eplus_connect.models.ab_eplus_connect import FetchAllDictCursor
from odoo.exceptions import UserError

from odoo.tests.common import TransactionCase


class TestSalesPromoReport(TransactionCase):
    def setUp(self):
        super().setUp()
        # Fixtures use installation context on replica databases; report calls do not.
        self.store = self.env["ab_store"].sudo().with_context(install_mode=True).create({
            "name": "Promo Store",
            "code": "PROMO",
            "eplus_serial": 100,
        })
        card = self.env["ab_product_card"].sudo().with_context(install_mode=True).create({"name": "Promo Product Card"})
        self.product = self.env["ab_product"].sudo().with_context(install_mode=True).create({
            "product_card_id": card.id,
            "code": "PROMO-PROD",
            "eplus_serial": 200,
        })
        self.other_product = self.env["ab_product"].sudo().with_context(install_mode=True).create({
            "product_card_id": card.id,
            "code": "NO-PROMO-PROD",
            "eplus_serial": 201,
        })
        self.promo = self.env["ab_promo_program"].sudo().with_context(install_mode=True).create({
            "name": "May Promo",
            "rule_date_from": "2026-05-01 00:00:00",
            "rule_date_to": "2026-05-31 23:59:59",
            "disc_percent": 50.0,
            "product_ids": [(6, 0, [self.product.id])],
            "approval_email_attachment": base64.b64encode(b"approval email"),
            "approval_email_attachment_filename": "approval_email.eml",
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

    def test_build_report_vals_rejects_discount_outside_promo_date(self):
        wizard = self.env["ab_sales_promo_report_wizard"].new({
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "include_no_promo_found": True,
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
        self.assertFalse(vals_list[0]["promo_id"])
        self.assertEqual(vals_list[0]["promo_date_status"], "no_promo_found")

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

    def test_build_report_vals_uses_one_matching_promo_per_product(self):
        self.env["ab_promo_program"].sudo().with_context(install_mode=True).create({
            "name": "Duplicate May Promo",
            "rule_date_from": "2026-05-01 00:00:00",
            "rule_date_to": "2026-05-31 23:59:59",
            "disc_percent": 50.0,
            "product_ids": [(6, 0, [self.product.id])],
            "approval_email_attachment": base64.b64encode(b"approval email"),
            "approval_email_attachment_filename": "approval_email.eml",
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

    def _wizard(self, **values):
        defaults = {
            "date_from": "2026-05-01", "date_to": "2026-05-31",
            "promo_ids": [(6, 0, self.promo.ids)],
        }
        defaults.update(values)
        return self.env["ab_sales_promo_report_wizard"].new(defaults)

    def _row(self, **values):
        row = {
            "invoice_eplus_serial": 10001, "store_eplus_serial": 100,
            "product_eplus_serial": 200, "qty": 2.0, "price": 250.0,
            "total_price": 500.0, "total_bill": 1000.0,
            "total_bill_after_disc": 1000.0, "total_bill_net": 750.0,
            "invoice_date": "2026-05-09", "is_odoo": True,
        }
        row.update(values)
        return row

    def test_seven_day_batches_cover_boundaries(self):
        wizard = self._wizard()
        for start, end in [
            (date(2026, 5, 1), date(2026, 5, 1)),
            (date(2026, 5, 1), date(2026, 5, 7)),
            (date(2026, 5, 1), date(2026, 5, 8)),
            (date(2026, 5, 1), date(2026, 5, 14)),
            (date(2026, 5, 1), date(2026, 5, 15)),
            (date(2028, 2, 25), date(2028, 3, 10)),
        ]:
            with self.subTest(start=start, end=end):
                batches = list(wizard._date_batches(start, end))
                self.assertEqual(batches[0][0], start)
                self.assertEqual(batches[-1][1], end)
                covered = []
                for batch_start, batch_end in batches:
                    self.assertLessEqual((batch_end - batch_start).days, 6)
                    covered.extend(batch_start + timedelta(days=i) for i in range((batch_end - batch_start).days + 1))
                self.assertEqual(covered, [start + timedelta(days=i) for i in range((end - start).days + 1)])

    def test_fetchmany_consumes_cursor_and_changes_only_date_parameters(self):
        wizard = self._wizard(store_ids=[(6, 0, self.store.ids)], product_ids=[(6, 0, self.product.ids)])
        expected_query, expected_params = wizard._prepare_bconnect_query()
        connection = MagicMock()
        cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        rows = [self._row(invoice_eplus_serial=i) for i in range(4001)]
        cursor.fetchmany.side_effect = [rows[:2000], rows[2000:4000], rows[4000:], []]
        with patch.object(type(wizard), "connect_eplus", return_value=connection):
            actual = wizard._fetch_bconnect_rows(date(2026, 5, 8), date(2026, 5, 14))
        self.assertEqual(actual, rows)
        cursor.fetchall.assert_not_called()
        self.assertEqual(cursor.fetchmany.call_count, 4)
        self.assertTrue(all(call.args == (2000,) for call in cursor.fetchmany.call_args_list))
        query, params = cursor.execute.call_args.args
        self.assertEqual(query, expected_query)
        self.assertEqual(params, tuple(["2026-05-08", "2026-05-14"] + expected_params[2:]))
        connection.__exit__.assert_called_once()
        connection.__enter__.return_value.cursor.return_value.__exit__.assert_called_once()

    def test_fetchmany_normalizes_driver_rows_before_building_report(self):
        wizard = self._wizard()
        expected = self._row(invoice_date=date(2026, 5, 9))
        raw_cursor = MagicMock()
        raw_cursor.description = [(name, None, None, None, None, None, None) for name in expected]
        raw_cursor.fetchmany.side_effect = [[tuple(expected.values())], []]
        connection = MagicMock()
        connection.__enter__.return_value.cursor.return_value = FetchAllDictCursor(raw_cursor)
        with patch.object(type(wizard), "connect_eplus", return_value=connection):
            rows = wizard._fetch_bconnect_rows()
        self.assertEqual(rows, [expected])
        values = wizard._build_report_vals(rows)
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0]["promo_id"], self.promo.id)
        self.assertEqual(raw_cursor.fetchmany.call_count, 2)
        self.assertTrue(all(call.args == (2000,) for call in raw_cursor.fetchmany.call_args_list))
        raw_cursor.fetchall.assert_not_called()
        raw_cursor.__exit__.assert_called_once()
        connection.__exit__.assert_called_once()

    def test_action_batches_rows_creates_and_replaces_once(self):
        wizard = self._wizard(date_to="2026-05-15")
        Report = self.env["ab_sales_promo_report_line"]
        connections = []
        events = []
        batches = [[self._row(invoice_eplus_serial=i)] * size for i, size in enumerate([2001, 1, 1001])]
        for index, rows in enumerate(batches):
            connection = MagicMock()
            cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
            cursor.fetchmany.side_effect = [rows[offset:offset + 2000] for offset in range(0, len(rows), 2000)] + [[]]
            connection.__exit__.side_effect = lambda *args, index=index: events.append(("closed", index)) or False
            connections.append(connection)
        build_count = 0
        def build(rows):
            nonlocal build_count
            self.assertEqual(events[-1], ("closed", build_count))
            self.assertEqual(rows, batches[build_count])
            build_count += 1
            events.append(("built", build_count))
            return [{"invoice_eplus_serial": row["invoice_eplus_serial"]} for row in rows]
        next_id = 1
        def create(values):
            nonlocal next_id
            self.assertLessEqual(len(values), 1000)
            records = Report.browse(range(next_id, next_id + len(values)))
            next_id += len(values)
            events.append(("created", len(values)))
            return records
        existing = MagicMock()
        with patch.object(type(wizard), "connect_eplus", side_effect=connections), \
                patch.object(type(wizard), "_build_report_vals", side_effect=build), \
                patch.object(type(Report), "create", side_effect=create) as creates, \
                patch.object(type(Report), "search", return_value=existing) as search:
            action = wizard.action_load_report()
        self.assertEqual([len(call.args[0]) for call in creates.call_args_list], [1000, 1000, 1, 1, 1000, 1])
        self.assertEqual(action["domain"], [("id", "in", list(range(1, 3004)))])
        self.assertEqual(build_count, 3)
        existing.unlink.assert_called_once()
        search.assert_called_once_with([
            ("create_uid", "=", self.env.uid), ("invoice_date", ">=", date(2026, 5, 1)),
            ("invoice_date", "<=", date(2026, 5, 15)),
        ])
        periods = []
        for connection in connections:
            cursor = connection.__enter__.return_value.cursor.return_value.__enter__.return_value
            periods.append(cursor.execute.call_args.args[1][:2])
            cursor.fetchall.assert_not_called()
            self.assertTrue(all(call.args == (2000,) for call in cursor.fetchmany.call_args_list))
        self.assertEqual(periods, [("2026-05-01", "2026-05-07"), ("2026-05-08", "2026-05-14"), ("2026-05-15", "2026-05-15")])

    def test_action_preserves_existing_and_counts_unmatched_rows_across_batches(self):
        wizard = self._wizard(date_to="2026-05-08", replace_existing=False)
        Report = self.env["ab_sales_promo_report_line"]
        with patch.object(type(wizard), "_fetch_bconnect_rows", side_effect=[[self._row()], [self._row()] * 2]), \
                patch.object(type(wizard), "_build_report_vals", return_value=[]), \
                patch.object(type(Report), "search") as search:
            with self.assertRaisesRegex(UserError, "BConnect returned 3 line"):
                wizard.action_load_report()
        search.assert_not_called()

    def test_action_empty_batches_keep_existing_empty_result_error(self):
        wizard = self._wizard(date_to="2026-05-08", replace_existing=False)
        with patch.object(type(wizard), "_fetch_bconnect_rows", return_value=[]) as fetch:
            with self.assertRaisesRegex(UserError, "BConnect returned no rows"):
                wizard.action_load_report()
        self.assertEqual(fetch.call_count, 2)

    def test_sql_filters_and_branch_join_are_preserved(self):
        wizard = self._wizard(store_ids=[(6, 0, self.store.ids)], product_ids=[(6, 0, self.product.ids)])
        query, params = wizard._prepare_bconnect_query()
        for fragment in ["h.sto_id = d.std_stock_id", "h.sto_id IN (?)", "d.itm_id IN (?)", "h.sto_id != ?",
                         "h.sec_insert_date >= ?", "h.sec_insert_date < DATEADD(day, 1, ?)",
                         "ISNULL(h.sth_notice, '') LIKE N'%§§§%'", "ISNULL(c.cust_code, '') LIKE '%off%'"]:
            self.assertIn(fragment, query)
        self.assertEqual(params, ["2026-05-01", "2026-05-31", 140, 100, 200])

    def test_candidates_overlap_open_ended_and_inclusive_period(self):
        wizard = self._wizard()
        for start, end, included in [
            ("2026-04-01 00:00:00", "2026-04-30 23:59:59", False),
            ("2026-06-01 00:00:00", "2026-06-30 23:59:59", False),
            ("2026-04-01 00:00:00", "2026-05-01 00:00:00", True),
            ("2026-05-31 23:59:59", "2026-06-30 23:59:59", True),
            (False, "2026-05-01 00:00:00", True),
            ("2026-05-31 23:59:59", False, True),
            (False, False, True),
        ]:
            with self.subTest(start=start, end=end):
                self.promo.write({"rule_date_from": start, "rule_date_to": end})
                self.assertEqual(self.promo in wizard._promo_candidates(self.store), included)

    def test_candidates_keep_active_company_store_and_explicit_filters(self):
        # Company creation clears environment caches, so create it before the in-memory wizard.
        other_company = self.env["res.company"].create({"name": "Promo test other company"})
        wizard = self._wizard()
        self.assertIn(self.promo, wizard._promo_candidates(self.store))
        self.promo.active = False
        self.assertNotIn(self.promo, wizard._promo_candidates(self.store))
        self.promo.active = True
        other_store = self.store.copy({"code": "OTHER-PROMO", "eplus_serial": 101})
        self.promo.store_ids = other_store
        self.assertNotIn(self.promo, wizard._promo_candidates(self.store))
        self.promo.store_ids = self.store
        other_promo = self.promo.copy({"name": "Not explicitly selected"})
        self.assertNotIn(other_promo, wizard._promo_candidates(self.store))
        self.promo.company_id = other_company
        self.assertNotIn(self.promo, wizard._promo_candidates(self.store))
        self.promo.company_id = False
        self.assertIn(self.promo, wizard._promo_candidates(self.store))

    def test_invoice_date_boundaries_and_invalid_dates(self):
        wizard = self._wizard(include_no_promo_found=True)
        self.promo.write({"rule_date_from": "2026-05-10 12:00:00", "rule_date_to": "2026-05-20 12:00:00"})
        for invoice_date, expected in [("2026-05-09", False), ("2026-05-10", True), ("2026-05-15", True),
                                       ("2026-05-20", True), ("2026-05-21", False)]:
            with self.subTest(invoice_date=invoice_date):
                vals = wizard._build_report_vals([self._row(invoice_date=invoice_date)])[0]
                self.assertEqual(vals["promo_id"], self.promo.id if expected else False)
                self.assertEqual(vals["promo_date_status"], "in_date" if expected else "no_promo_found")
        wizard.include_no_promo_found = False
        self.assertFalse(wizard._build_report_vals([self._row(invoice_date="2026-05-21")]))

    def test_date_valid_candidate_wins_over_earlier_invalid_candidate(self):
        invalid = self.promo.copy({"name": "Expired earlier sequence", "sequence": 1, "rule_date_to": "2026-05-08 23:59:59"})
        self.promo.sequence = 2
        wizard = self._wizard(promo_ids=[(6, 0, (invalid | self.promo).ids)])
        self.assertEqual(wizard._promo_candidates(self.store).ids, [invalid.id, self.promo.id])
        vals = wizard._build_report_vals([self._row()])
        self.assertEqual(vals[0]["promo_id"], self.promo.id)

    def test_products_match_independently_and_use_selected_promo_dates(self):
        other_promo = self.promo.copy({
            "name": "Second product promo", "product_ids": [(6, 0, self.other_product.ids)],
            "rule_date_from": "2026-05-05 00:00:00", "rule_date_to": "2026-05-15 23:59:59",
        })
        wizard = self._wizard(promo_ids=[(6, 0, (self.promo | other_promo).ids)])
        rows = [self._row(), self._row(product_eplus_serial=201)]
        vals = wizard._build_report_vals(rows)
        self.assertEqual([val["promo_id"] for val in vals], [self.promo.id, other_promo.id])
        self.assertEqual([val["promo_discount"] for val in vals], [250.0, 250.0])
        self.assertEqual([val["total_compensation"] for val in vals], [250.0, 250.0])
        lines = self.env["ab_sales_promo_report_line"].create(vals)
        self.assertEqual(lines[0].promo_start, self.promo.rule_date_from)
        self.assertEqual(lines[0].promo_end, self.promo.rule_date_to)
        self.assertEqual(lines[1].promo_start, other_promo.rule_date_from)
        self.assertEqual(lines[1].promo_end, other_promo.rule_date_to)

    def test_unmatched_product_cannot_inherit_another_products_promotion(self):
        future = self.promo.copy({
            "name": "Future second product", "product_ids": [(6, 0, self.other_product.ids)],
            "rule_date_from": "2026-05-10 00:00:00",
        })
        wizard = self._wizard(promo_ids=[(6, 0, (self.promo | future).ids)], include_no_promo_found=True)
        vals = wizard._build_report_vals([self._row(), self._row(product_eplus_serial=201)])
        self.assertEqual(vals[0]["promo_id"], self.promo.id)
        self.assertFalse(vals[1]["promo_id"])
        self.assertEqual(vals[1]["promo_date_status"], "no_promo_found")

    def test_valid_but_uncompensated_product_is_no_promo_applied(self):
        other = self.promo.copy({"name": "Second product mismatch", "disc_percent": 10,
                                "product_ids": [(6, 0, self.other_product.ids)]})
        wizard = self._wizard(promo_ids=[(6, 0, (self.promo | other).ids)], include_no_promo_found=True)
        vals = wizard._build_report_vals([self._row(), self._row(product_eplus_serial=201)])
        self.assertEqual(vals[0]["promo_id"], self.promo.id)
        self.assertFalse(vals[1]["promo_id"])
        self.assertEqual(vals[1]["promo_date_status"], "no_promo_applied")

    def test_same_product_source_rows_reuse_one_invoice_match(self):
        wizard = self._wizard()
        rows = [self._row(qty=1, total_price=250), self._row(qty=1, total_price=250)]
        original = type(wizard)._matched_promo_for_invoice
        with patch.object(type(wizard), "_matched_promo_for_invoice", autospec=True, side_effect=original) as match:
            vals = wizard._build_report_vals(rows)
        self.assertEqual(match.call_count, 1)
        self.assertEqual([val["promo_id"] for val in vals], [self.promo.id, self.promo.id])
        self.assertEqual([val["promo_discount"] for val in vals], [250.0, 250.0])

    def test_product_matching_keeps_store_scope_and_rejects_missing_date(self):
        wizard = self._wizard()
        other_store = self.store.copy({"code": "SCOPE-PROMO", "eplus_serial": 102})
        self.promo.store_ids = other_store
        scope = {self.promo.id: self.product}
        self.assertFalse(wizard._product_matching_promos(self.promo, scope, self.store, self.product, date(2026, 5, 9)))
        self.promo.store_ids = self.store
        self.assertFalse(wizard._product_matching_promos(self.promo, scope, self.store, self.other_product, date(2026, 5, 9)))
        self.assertFalse(wizard._product_matching_promos(self.promo, scope, self.store, self.product, False))
        self.assertIn(self.promo, wizard._product_matching_promos(self.promo, scope, self.store, self.product, date(2026, 5, 9)))

    def test_discounts_are_not_combined_across_product_promotions(self):
        other = self.promo.copy({"name": "Independent discount", "product_ids": [(6, 0, self.other_product.ids)]})
        wizard = self._wizard(promo_ids=[(6, 0, (self.promo | other).ids)])
        vals = wizard._build_report_vals([
            self._row(total_bill_net=500.0),
            self._row(product_eplus_serial=201, total_bill_net=500.0),
        ])
        self.assertEqual(len(vals), 2)
        self.assertTrue(all(not val["promo_id"] for val in vals))
        self.assertTrue(all(val["promo_date_status"] == "no_promo_applied" for val in vals))
