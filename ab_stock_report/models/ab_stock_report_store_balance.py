# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .ab_stock_report_cache import AbStockReportRefreshJob

_logger = logging.getLogger(__name__)

DIRECT_STATUS_SELECTION = [
    ("not_checked", "Not Checked"),
    ("pending", "Pending"),
    ("running", "Running"),
    ("success", "Success"),
    ("missing_ip", "Missing IP"),
    ("failed", "Failed"),
    ("cancelled", "Cancelled"),
]

BULK_STATE_SELECTION = [
    ("pending", "Pending"),
    ("running", "Running"),
    ("cancel_requested", "Cancel Requested"),
    ("cancelled", "Cancelled"),
    ("done", "Done"),
    ("done_with_errors", "Done with Errors"),
    ("failed", "Failed"),
]

class AbStockReportStoreBalanceCache(models.Model):
    _name = "ab_stock_report_store_balance_cache"
    _inherit = "ab_eplus_connect"
    _description = "Stock Report Store Balance and Sales Cache"
    _order = "store_id, id"

    product_id = fields.Many2one("ab_product", string="Product", required=True, ondelete="cascade", index=True)
    product_eplus_serial = fields.Integer(string="EPlus Serial", required=True, index=True)
    store_id = fields.Many2one("ab_store", string="Store", required=True, ondelete="cascade", index=True)
    store_eplus_serial = fields.Integer(string="Store EPlus Serial", required=True, index=True)
    main_balance = fields.Float(string="Main Server Balance", digits=(16, 4))
    direct_balance = fields.Float(string="Direct Store Balance", digits=(16, 4))
    difference = fields.Float(string="Difference", compute="_compute_difference", store=True, digits=(16, 4))
    sales_days_61_90 = fields.Float(string="Days 61-90", digits=(16, 4))
    sales_days_31_60 = fields.Float(string="Days 31-60", digits=(16, 4))
    sales_last_30_days = fields.Float(string="Last 30 Days", digits=(16, 4))
    sales_total_90_days = fields.Float(
        string="Total 90 Days",
        compute="_compute_sales_total_90_days",
        store=True,
        digits=(16, 4),
    )
    main_updated_at = fields.Datetime(string="Main Updated At", readonly=True)
    direct_status = fields.Selection(
        DIRECT_STATUS_SELECTION,
        string="Direct Status",
        default="not_checked",
        required=True,
        index=True,
    )
    direct_updated_at = fields.Datetime(string="Direct Updated At", readonly=True)
    latest_error = fields.Text(string="Latest Error", readonly=True)

    _uniq_product_store = models.Constraint(
        "UNIQUE(product_id, store_id)",
        "Each product can only have one balance cache row per store.",
    )

    @api.depends("main_balance", "direct_balance", "direct_status")
    def _compute_difference(self):
        for rec in self:
            rec.difference = (
                (rec.direct_balance or 0.0) - (rec.main_balance or 0.0)
                if rec.direct_status == "success"
                else False
            )

    @api.depends("sales_days_61_90", "sales_days_31_60", "sales_last_30_days")
    def _compute_sales_total_90_days(self):
        for rec in self:
            rec.sales_total_90_days = (
                (rec.sales_days_61_90 or 0.0)
                + (rec.sales_days_31_60 or 0.0)
                + (rec.sales_last_30_days or 0.0)
            )

    @api.model
    def _active_configured_stores(self):
        return self.env["ab_store"].sudo().search(
            [("active", "=", True), ("eplus_serial", "!=", False)],
            order="eplus_serial, name, id",
        )

    @api.model
    def _get_or_create_rows(self, product):
        product_rec = self.env["ab_stock_report_cache_line"]._resolve_product(product)
        stores = self._active_configured_stores()
        existing = self.sudo().search([
            ("product_id", "=", product_rec.id),
            ("store_id", "in", stores.ids),
        ])
        by_store = {line.store_id.id: line for line in existing}
        created = self.browse()
        for store in stores:
            if store.id not in by_store:
                created |= self.sudo().create({
                    "product_id": product_rec.id,
                    "product_eplus_serial": int(product_rec.eplus_serial or 0),
                    "store_id": store.id,
                    "store_eplus_serial": int(store.eplus_serial or 0),
                })
        return (existing | created).sorted(lambda line: (line.store_eplus_serial or 0, line.store_id.display_name))

    @api.model
    def has_main_cache_for_product(self, product):
        product_rec = self.env["ab_stock_report_cache_line"]._resolve_product(product)
        return bool(self.sudo().search_count([
            ("product_id", "=", product_rec.id),
            ("main_updated_at", "!=", False),
        ]))

    @api.model
    def refresh_main_server(self, product):
        product_rec = self.env["ab_stock_report_cache_line"]._resolve_product(product)
        if not product_rec.eplus_serial:
            raise UserError(_("This product is not linked to an EPlus item serial."))

        rows = self._get_or_create_rows(product_rec)
        store_serials = [int(store.eplus_serial) for store in rows.store_id if store.eplus_serial]
        if not store_serials:
            return rows

        periods = self._completed_cairo_periods()
        placeholders = self._sql_placeholders(store_serials)
        with self.connect_eplus(param_str="?") as connection:
            balance_by_store = self._fetch_main_balance_by_store(
                connection,
                int(product_rec.eplus_serial),
                store_serials,
                placeholders,
            )
            sales_by_store = self._fetch_main_sales_by_store(
                connection,
                int(product_rec.eplus_serial),
                store_serials,
                placeholders,
                periods,
            )

        now = fields.Datetime.now()
        for line in rows:
            store_serial = int(line.store_eplus_serial or 0)
            sales = sales_by_store.get(store_serial, {})
            line.sudo().write({
                "product_eplus_serial": int(product_rec.eplus_serial or 0),
                "store_eplus_serial": store_serial,
                "main_balance": balance_by_store.get(store_serial, 0.0),
                "sales_days_61_90": sales.get("days_61_90", 0.0),
                "sales_days_31_60": sales.get("days_31_60", 0.0),
                "sales_last_30_days": sales.get("last_30_days", 0.0),
                "main_updated_at": now,
            })
        return rows

    @staticmethod
    def _completed_cairo_periods():
        today = datetime.now(ZoneInfo("Africa/Cairo")).date()
        midnight = datetime.combine(today, time.min)
        return {
            "start_90": midnight - timedelta(days=90),
            "start_60": midnight - timedelta(days=60),
            "start_30": midnight - timedelta(days=30),
            "today": midnight,
        }

    @staticmethod
    def _sql_placeholders(values):
        return ", ".join("?" for _value in values)

    @api.model
    def _fetch_main_balance_by_store(self, connection, product_serial, store_serials, placeholders):
        query = f"""
            SELECT
                ics.sto_id,
                SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS DECIMAL(18, 4))) AS balance
            FROM Item_Class_Store ics WITH (NOLOCK)
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
            WHERE ics.itm_id = ?
              AND ics.sto_id IN ({placeholders})
            GROUP BY ics.sto_id
        """
        with connection.cursor() as cursor:
            cursor.execute(query, tuple([product_serial] + store_serials))
            rows = cursor.fetchall() or []
        return {int(row[0]): float(row[1] or 0.0) for row in rows}

    @api.model
    def _fetch_main_sales_by_store(self, connection, product_serial, store_serials, placeholders, periods):
        quantity_expr = """
            CASE sd.itm_unit
                WHEN 1 THEN ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0)
                WHEN 2 THEN (ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0)) / NULLIF(ic.itm_unit1_unit2, 0)
                WHEN 3 THEN (ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0)) / NULLIF(ic.itm_unit1_unit3, 0)
                ELSE ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0)
            END
        """
        query = f"""
            SELECT
                sh.sto_id,
                SUM(CASE WHEN sh.sec_insert_date >= ? AND sh.sec_insert_date < ? THEN {quantity_expr} ELSE 0 END),
                SUM(CASE WHEN sh.sec_insert_date >= ? AND sh.sec_insert_date < ? THEN {quantity_expr} ELSE 0 END),
                SUM(CASE WHEN sh.sec_insert_date >= ? AND sh.sec_insert_date < ? THEN {quantity_expr} ELSE 0 END)
            FROM r_sales_trans_h sh WITH (NOLOCK)
            JOIN r_sales_trans_d sd WITH (NOLOCK)
              ON sd.sth_id = sh.sth_id
             AND sd.std_stock_id = sh.sto_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = sd.itm_id
            WHERE sh.sth_flag = 'C'
              AND sd.itm_id = ?
              AND sh.sto_id IN ({placeholders})
              AND sh.sec_insert_date >= ?
              AND sh.sec_insert_date < ?
            GROUP BY sh.sto_id
        """
        params = [
            periods["start_90"], periods["start_60"],
            periods["start_60"], periods["start_30"],
            periods["start_30"], periods["today"],
            product_serial,
            *store_serials,
            periods["start_90"], periods["today"],
        ]
        with connection.cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall() or []
        return {
            int(row[0]): {
                "days_61_90": float(row[1] or 0.0),
                "days_31_60": float(row[2] or 0.0),
                "last_30_days": float(row[3] or 0.0),
            }
            for row in rows
        }

    def refresh_direct_balance(self):
        self.ensure_one()
        active_job = self.env["ab_stock_report_store_balance_job"].sudo().search([
            ("product_id", "=", self.product_id.id),
            ("state", "in", ("pending", "running", "cancel_requested")),
        ], limit=1)
        if active_job and active_job.is_store_processing(self.store_id):
            raise UserError(_("This store is already being refreshed for the selected product."))
        return self._refresh_direct_balance_unchecked()

    def _refresh_direct_balance_unchecked(self):
        self.ensure_one()
        store = self.store_id.sudo()
        now = fields.Datetime.now()
        if not store.ip1:
            self.sudo().write({
                "direct_status": "missing_ip",
                "direct_updated_at": now,
                "latest_error": _("Store has no direct IP configured."),
            })
            return False
        self.sudo().write({"direct_status": "running", "latest_error": False})
        try:
            balance = self._fetch_direct_balance(store)
            self.sudo().write({
                "direct_balance": balance,
                "direct_status": "success",
                "direct_updated_at": fields.Datetime.now(),
                "latest_error": False,
            })
            return True
        except Exception as exc:
            _logger.exception(
                "Direct store balance refresh failed for product %s store %s.",
                self.product_eplus_serial,
                self.store_eplus_serial,
            )
            self.sudo().write({
                "direct_status": "failed",
                "direct_updated_at": fields.Datetime.now(),
                "latest_error": str(exc),
            })
            return False

    def _fetch_direct_balance(self, store):
        self.ensure_one()
        query = """
            SELECT
                SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS DECIMAL(18, 4))) AS balance
            FROM Item_Class_Store ics WITH (NOLOCK)
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
            WHERE ics.itm_id = ?
              AND ics.sto_id = ?
        """
        with self.connect_eplus(server=store.ip1, param_str="?") as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (int(self.product_eplus_serial), int(self.store_eplus_serial)))
                row = cursor.fetchone()
        return float((row[0] if row else 0.0) or 0.0)


class AbStockReportStoreBalanceJob(models.Model):
    _name = "ab_stock_report_store_balance_job"
    _description = "Stock Report Store Balance Bulk Refresh Job"
    _order = "requested_at desc, id desc"

    product_id = fields.Many2one("ab_product", string="Product", required=True, ondelete="cascade", index=True)
    product_eplus_serial = fields.Integer(string="EPlus Serial", required=True, index=True)
    state = fields.Selection(BULK_STATE_SELECTION, string="State", default="pending", required=True, index=True)
    target_store_ids = fields.Many2many(
        "ab_store",
        "ab_stock_report_store_balance_job_store_rel",
        "job_id",
        "store_id",
        string="Target Stores",
    )
    total_count = fields.Integer(string="Total")
    completed_count = fields.Integer(string="Completed")
    succeeded_count = fields.Integer(string="Succeeded")
    failed_count = fields.Integer(string="Failed")
    current_store_id = fields.Many2one("ab_store", string="Current Store")
    requested_at = fields.Datetime(string="Requested At", required=True, index=True)
    started_at = fields.Datetime(string="Started At", readonly=True)
    finished_at = fields.Datetime(string="Finished At", readonly=True)
    last_error = fields.Text(string="Last Error", readonly=True)

    @api.model
    def enqueue_for_product(self, product):
        product_rec = self.env["ab_stock_report_cache_line"]._resolve_product(product)
        if not product_rec.eplus_serial:
            raise UserError(_("This product is not linked to an EPlus item serial."))
        active = self.sudo().search([
            ("product_id", "=", product_rec.id),
            ("state", "in", ("pending", "running", "cancel_requested")),
        ], limit=1)
        if active:
            raise UserError(_("A direct balance update is already pending or running for this product."))

        cache_rows = self.env["ab_stock_report_store_balance_cache"].sudo()._get_or_create_rows(product_rec)
        stores = cache_rows.store_id
        cache_rows.write({"direct_status": "pending", "latest_error": False})
        job = self.sudo().create({
            "product_id": product_rec.id,
            "product_eplus_serial": int(product_rec.eplus_serial),
            "state": "pending",
            "target_store_ids": [(6, 0, stores.ids)],
            "total_count": len(stores),
            "completed_count": 0,
            "succeeded_count": 0,
            "failed_count": 0,
            "requested_at": fields.Datetime.now(),
            "last_error": False,
        })
        dbname = self.env.cr.dbname
        self.env.cr.postcommit.add(lambda dbname=dbname: AbStockReportRefreshJob._start_background_worker(dbname))
        return job

    def request_cancel(self):
        for job in self:
            if job.state == "pending":
                cache_rows = self.env["ab_stock_report_store_balance_cache"].sudo().search([
                    ("product_id", "=", job.product_id.id),
                    ("store_id", "in", job.target_store_ids.ids),
                    ("direct_status", "=", "pending"),
                ])
                cache_rows.write({
                    "direct_status": "cancelled",
                    "direct_updated_at": fields.Datetime.now(),
                    "latest_error": _("Direct balance update was cancelled."),
                })
                job.sudo().write({
                    "state": "cancelled",
                    "finished_at": fields.Datetime.now(),
                    "last_error": _("Cancelled before processing started."),
                })
            elif job.state == "running":
                job.sudo().write({"state": "cancel_requested"})
        return True

    def is_store_processing(self, store):
        self.ensure_one()
        return bool(
            self.current_store_id == store
            or (self.state == "pending" and store in self.target_store_ids)
        )

    @api.model
    def process_pending_jobs(self):
        jobs = self.sudo().search(
            [("state", "=", "pending")],
            order="requested_at asc, id asc",
            limit=1,
        )
        for job in jobs:
            job._process_one()

    def _process_one(self):
        self.ensure_one()
        cache_model = self.env["ab_stock_report_store_balance_cache"].sudo()
        try:
            self.sudo().write({
                "state": "running",
                "started_at": fields.Datetime.now(),
                "last_error": False,
            })
            self.env.cr.commit()
            for store in self.target_store_ids.sorted(lambda rec: (rec.eplus_serial or 0, rec.display_name)):
                self.invalidate_recordset(["state"])
                if self.state == "cancel_requested":
                    self._cancel_remaining()
                    return False
                line = cache_model.search([
                    ("product_id", "=", self.product_id.id),
                    ("store_id", "=", store.id),
                ], limit=1)
                if not line:
                    continue
                self.sudo().write({"current_store_id": store.id})
                line.sudo().write({"direct_status": "running", "latest_error": False})
                self.env.cr.commit()
                ok = line._refresh_direct_balance_unchecked()
                self.sudo().write({
                    "completed_count": self.completed_count + 1,
                    "succeeded_count": self.succeeded_count + (1 if ok else 0),
                    "failed_count": self.failed_count + (0 if ok else 1),
                })
                self.env.cr.commit()
            final_state = "done_with_errors" if self.failed_count else "done"
            self.sudo().write({
                "state": final_state,
                "current_store_id": False,
                "finished_at": fields.Datetime.now(),
            })
            return True
        except Exception as exc:
            _logger.exception("Store balance bulk refresh failed for product %s.", self.product_eplus_serial)
            self.sudo().write({
                "state": "failed",
                "current_store_id": False,
                "finished_at": fields.Datetime.now(),
                "last_error": str(exc),
            })
            return False

    def _cancel_remaining(self):
        self.ensure_one()
        remaining = self.env["ab_stock_report_store_balance_cache"].sudo().search([
            ("product_id", "=", self.product_id.id),
            ("store_id", "in", self.target_store_ids.ids),
            ("direct_status", "in", ("pending", "running")),
        ])
        remaining.write({
            "direct_status": "cancelled",
            "direct_updated_at": fields.Datetime.now(),
            "latest_error": _("Direct balance update was cancelled."),
        })
        self.sudo().write({
            "state": "cancelled",
            "current_store_id": False,
            "finished_at": fields.Datetime.now(),
        })
        self.env.cr.commit()
