# -*- coding: utf-8 -*-
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestSalesPerDay(TransactionCase):
    def _create_store_or_skip(self, vals):
        try:
            return self.env["ab_store"].create(vals)
        except ValidationError as error:
            if "Replication Database" in str(error):
                self.skipTest("Replica database blocks creating ab_store test records.")
            raise

    def test_replace_sales_day_deletes_existing_day_and_bulk_inserts_rows(self):
        SalesPerDay = self.env["ab_sales_per_day"]
        sale_date = fields.Date.context_today(self.env["ab_sales_per_day"]) - timedelta(days=1)
        store = self._create_store_or_skip({
            "name": "Sales Cache Store",
            "code": "SPD",
            "eplus_serial": 7001,
        })
        SalesPerDay.create({
            "store_id": store.id,
            "product_eplus_serial": 1001,
            "sale_date": sale_date,
            "sales_qty": 12,
        })

        rows_synced = SalesPerDay._replace_sales_day(sale_date, [
            {
                "store_id": store.id,
                "product_eplus_serial": 1002,
                "sale_date": sale_date,
                "sales_qty": 5.5,
            },
        ])

        self.assertEqual(rows_synced, 1)
        self.assertFalse(SalesPerDay.search([
            ("store_id", "=", store.id),
            ("product_eplus_serial", "=", 1001),
            ("sale_date", "=", sale_date),
        ]))
        inserted = SalesPerDay.search([
            ("store_id", "=", store.id),
            ("product_eplus_serial", "=", 1002),
            ("sale_date", "=", sale_date),
        ])
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted.sales_qty, 5.5)

    def test_ensure_sync_states_creates_missing_days_only_once(self):
        SalesPerDay = self.env["ab_sales_per_day"]
        State = self.env["ab_sales_per_day_sync_state"]
        end_date = fields.Date.context_today(SalesPerDay) - timedelta(days=1)
        start_date = end_date - timedelta(days=2)

        SalesPerDay._ensure_sync_states(start_date, end_date)
        SalesPerDay._ensure_sync_states(start_date, end_date)

        states = State.search([
            ("sale_date", ">=", start_date),
            ("sale_date", "<=", end_date),
        ])
        self.assertEqual(len(states), 3)
        self.assertEqual(set(states.mapped("state")), {"pending"})

    def test_claim_next_sync_state_uses_custom_rolling_days(self):
        SalesPerDay = self.env["ab_sales_per_day"]
        State = self.env["ab_sales_per_day_sync_state"]
        window_start = date(2020, 1, 1)
        window_end = date(2020, 1, 20)
        State.create([
            {
                "sale_date": date(2020, 1, 5),
                "state": "done",
                "finished_at": "2020-01-05 00:00:00",
            },
            {
                "sale_date": date(2020, 1, 15),
                "state": "done",
                "finished_at": "2020-01-15 00:00:00",
            },
        ])

        with patch.object(self.env.cr, "commit", lambda: None):
            state = SalesPerDay._claim_next_sync_state(
                window_start,
                window_end,
                rolling_days=10,
                allow_rolling=True,
            )

        self.assertEqual(fields.Date.to_date(state.sale_date), date(2020, 1, 15))
        self.assertEqual(state.state, "running")

    def test_claim_next_sync_state_claims_pending_days_newest_first(self):
        SalesPerDay = self.env["ab_sales_per_day"]
        State = self.env["ab_sales_per_day_sync_state"]
        window_start = date(2020, 1, 1)
        window_end = date(2020, 1, 3)
        State.create([
            {"sale_date": date(2020, 1, 1), "state": "pending"},
            {"sale_date": date(2020, 1, 2), "state": "pending"},
            {"sale_date": date(2020, 1, 3), "state": "pending"},
        ])

        with patch.object(self.env.cr, "commit", lambda: None):
            state = SalesPerDay._claim_next_sync_state(
                window_start,
                window_end,
                allow_rolling=False,
            )

        self.assertEqual(fields.Date.to_date(state.sale_date), date(2020, 1, 3))
        self.assertEqual(state.state, "running")

    def test_claim_next_sync_state_force_resync_can_pick_done_day(self):
        SalesPerDay = self.env["ab_sales_per_day"]
        State = self.env["ab_sales_per_day_sync_state"]
        sale_date = date(2020, 2, 1)
        State.create({
            "sale_date": sale_date,
            "state": "done",
            "finished_at": "2020-02-01 00:00:00",
        })

        with patch.object(self.env.cr, "commit", lambda: None):
            state = SalesPerDay._claim_next_sync_state(
                sale_date,
                sale_date,
                force_resync=True,
                allow_rolling=False,
            )

        self.assertEqual(fields.Date.to_date(state.sale_date), sale_date)
        self.assertEqual(state.state, "running")

    def test_sync_wizard_rejects_today_and_future_dates(self):
        today = fields.Date.context_today(self.env["ab_sales_per_day_sync_wizard"])
        wizard = self.env["ab_sales_per_day_sync_wizard"].create({
            "date_from": today,
            "date_to": today,
        })

        with self.assertRaises(UserError):
            wizard.action_sync_sales_per_day()

    def test_sync_wizard_calls_sync_day_by_day(self):
        Wizard = self.env["ab_sales_per_day_sync_wizard"]
        SalesPerDay = self.env["ab_sales_per_day"]
        date_from = date(2020, 3, 1)
        date_to = date(2020, 3, 3)
        calls = []

        def fake_sync(self, start_date=False, end_date=False, force_resync=False, rolling_days=10):
            calls.append((start_date, end_date, force_resync, rolling_days))
            return True

        wizard = Wizard.create({
            "date_from": date_from,
            "date_to": date_to,
            "force_resync": True,
        })
        with patch.object(type(SalesPerDay), "cron_sync_next_sales_day", fake_sync):
            wizard.action_sync_sales_per_day()

        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0], (date_from, date_from, True, 10))
        self.assertEqual(calls[2], (date_to, date_to, True, 10))

    def test_cron_sync_last_90_sales_per_day_uses_refresh_window(self):
        Wizard = self.env["ab_sales_per_day_sync_wizard"]
        today = fields.Date.context_today(Wizard)
        expected_date_to = today - timedelta(days=1)
        expected_date_from = expected_date_to - timedelta(days=89)
        calls = []

        def fake_action(self):
            calls.append((
                fields.Date.to_date(self.date_from),
                fields.Date.to_date(self.date_to),
                self.force_resync,
            ))
            return True

        with patch.object(type(Wizard), "action_sync_sales_per_day", fake_action):
            Wizard.cron_sync_last_90_sales_per_day()

        self.assertEqual(calls, [(expected_date_from, expected_date_to, True)])
