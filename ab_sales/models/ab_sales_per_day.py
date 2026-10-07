# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class AbSalesPerDay(models.Model):
    _name = "ab_sales_per_day"
    _description = "Sales Per Store/Product/Day"
    _order = "sale_date desc, store_id, product_eplus_serial"

    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_eplus_serial = fields.Integer(
        string="Product EPlus Serial",
        required=True,
        index=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        index=True,
        ondelete="set null",
    )
    sale_date = fields.Date(
        string="Sale Date",
        required=True,
        index=True,
    )
    sales_qty = fields.Float(
        string="Sales Quantity",
        digits=(16, 4),
        aggregator="sum",
    )
    sync_at = fields.Datetime(
        string="Synced At",
        readonly=True,
    )

    _uniq_store_product_day = models.Constraint(
        "UNIQUE(store_id, product_eplus_serial, sale_date)",
        "Sales per day already exists for this store, product, and date.",
    )

    def init(self):
        super().init()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_sales_per_day_store_date_idx
                ON ab_sales_per_day (store_id, sale_date)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_sales_per_day_product_date_idx
                ON ab_sales_per_day (product_eplus_serial, sale_date)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_sales_per_day_store_product_date_idx
                ON ab_sales_per_day (store_id, product_eplus_serial, sale_date)
        """)

    @api.model
    def cron_sync_next_sales_day(
            self,
            start_date=False,
            end_date=False,
            force_resync=False,
            rolling_days=10,
    ):
        self = self.sudo()
        today = fields.Date.context_today(self)
        if start_date or end_date:
            window_start = fields.Date.to_date(start_date or end_date)
            window_end = fields.Date.to_date(end_date or start_date)
            allow_rolling = False
        else:
            window_end = today - timedelta(days=1)
            window_start = window_end - timedelta(days=89)
            allow_rolling = True
        if window_start > window_end:
            return False

        self._ensure_sync_states(window_start, window_end)
        state = self._claim_next_sync_state(
            window_start,
            window_end,
            force_resync=force_resync,
            rolling_days=rolling_days,
            allow_rolling=allow_rolling,
        )
        if not state:
            return False

        state_id = state.id
        try:
            rows = self._fetch_remote_sales_day(state.sale_date)
            rows_synced = self._replace_sales_day(state.sale_date, rows)
            state.write({
                "state": "done",
                "rows_synced": rows_synced,
                "finished_at": fields.Datetime.now(),
                "error_message": False,
            })
            self.env.cr.commit()
            _logger.info("Sales per day sync finished: date=%s rows=%s", state.sale_date, rows_synced)
            return True
        except Exception as error:
            _logger.exception("Sales per day sync failed: state_id=%s", state_id)
            self.env.cr.rollback()
            failed_state = self.env["ab_sales_per_day_sync_state"].sudo().browse(state_id)
            if failed_state.exists():
                failed_state.write({
                    "state": "failed",
                    "finished_at": fields.Datetime.now(),
                    "error_message": repr(error),
                })
                self.env.cr.commit()
            return False

    @api.model
    def _ensure_sync_states(self, start_date, end_date):
        State = self.env["ab_sales_per_day_sync_state"].sudo()
        existing_dates = {
            fields.Date.to_date(value)
            for value in State.search([
                ("sale_date", ">=", start_date),
                ("sale_date", "<=", end_date),
            ]).mapped("sale_date")
        }

        vals_list = []
        current = start_date
        while current <= end_date:
            if current not in existing_dates:
                vals_list.append({"sale_date": current})
            current += timedelta(days=1)
        if vals_list:
            State.create(vals_list)

    @api.model
    def _claim_next_sync_state(
            self,
            window_start,
            window_end,
            force_resync=False,
            rolling_days=10,
            allow_rolling=True,
    ):
        State = self.env["ab_sales_per_day_sync_state"].sudo()
        stale_before = fields.Datetime.now() - timedelta(hours=6)
        State.search([
            ("state", "=", "running"),
            ("started_at", "<", fields.Datetime.to_string(stale_before)),
        ]).write({
            "state": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": _("Sync was marked failed because the previous run became stale."),
        })

        states = ("pending", "failed", "done") if force_resync else ("pending", "failed")
        self.env.cr.execute(
            """
            SELECT id
            FROM ab_sales_per_day_sync_state
            WHERE sale_date >= %s
              AND sale_date <= %s
              AND state = ANY(%s)
            ORDER BY
              CASE WHEN state IN ('pending', 'failed') THEN 0 ELSE 1 END,
              sale_date DESC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            [window_start, window_end, list(states)],
        )
        row = self.env.cr.fetchone()

        if not row and allow_rolling:
            rolling_days = max(1, int(rolling_days or 10))
            rolling_start = window_end - timedelta(days=rolling_days - 1)
            self.env.cr.execute(
                """
                SELECT id
                FROM ab_sales_per_day_sync_state
                WHERE sale_date >= %s
                  AND sale_date <= %s
                  AND state = 'done'
                ORDER BY finished_at NULLS FIRST, sale_date
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                [rolling_start, window_end],
            )
            row = self.env.cr.fetchone()

        if not row:
            return State.browse()

        state = State.browse(row[0])
        state.write({
            "state": "running",
            "started_at": fields.Datetime.now(),
            "finished_at": False,
            "error_message": False,
        })
        self.env.cr.commit()
        return state


    @api.model
    def _products_by_eplus_serial(self, product_serials):
        if not product_serials:
            return {}
        products = self.env["ab_product"].sudo().search([
            ("eplus_serial", "in", product_serials),
        ])
        result = {}
        for product in products:
            product_serial = self._safe_int(product.eplus_serial)
            if product_serial and product_serial not in result:
                result[product_serial] = product.id
        return result

    @staticmethod
    def _safe_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _chunks(values, size):
        for index in range(0, len(values), size):
            yield values[index:index + size]


class AbSalesPerDaySyncState(models.Model):
    _name = "ab_sales_per_day_sync_state"
    _description = "Sales Per Day Sync State"
    _order = "sale_date desc"

    sale_date = fields.Date(
        string="Sale Date",
        required=True,
        index=True,
    )
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("running", "Running"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        string="Status",
        default="pending",
        required=True,
        index=True,
    )
    rows_synced = fields.Integer(
        string="Rows Synced",
        readonly=True,
    )
    started_at = fields.Datetime(
        string="Started At",
        readonly=True,
    )
    finished_at = fields.Datetime(
        string="Finished At",
        readonly=True,
    )
    error_message = fields.Text(
        string="Error",
        readonly=True,
    )

    _uniq_sale_date = models.Constraint(
        "UNIQUE(sale_date)",
        "Sales sync state already exists for this date.",
    )
