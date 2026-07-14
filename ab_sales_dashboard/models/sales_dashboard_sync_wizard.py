import logging
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)


class SalesDashboardSyncWizard(models.TransientModel):
    _name = "ab_sales_dashboard_sync_wizard"
    _description = "Sales Dashboard Sync Wizard"

    date_from = fields.Date(
        string="Date From",
        required=True,
    )
    date_to = fields.Date(
        string="Date To",
        required=True,
    )
    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        help="Leave empty to sync all stores.",
    )
    force_resync = fields.Boolean(
        string="Refresh Synced Days",
        default=True,
        help="Refresh days that already have complete dashboard report data.",
    )

    @api.model
    def cron_sync_last_90_dashboard_days(self):
        today = fields.Date.context_today(self)
        date_to = today - timedelta(days=1)
        date_from = date_to - timedelta(days=89)
        wizard = self.sudo().create({
            "date_from": date_from,
            "date_to": date_to,
            "force_resync": True,
        })
        return wizard.action_sync_dashboard_data()

    def action_sync_dashboard_data(self):
        self.ensure_one()
        result = self.env["ab_sales_dashboard_sync_state"].sudo().sync_dashboard_date_range(
            self.date_from,
            self.date_to,
            store_id=self.store_id.id if self.store_id else 0,
            force_resync=self.force_resync,
            descending=True,
        )
        failed_count = result["failed_count"]
        if failed_count:
            notification_type = "warning"
            message = _(
                "Dashboard sync finished with warnings. Synced days: %(synced)s. "
                "Skipped days: %(skipped)s. Failed days: %(failed)s."
            ) % {
                "synced": result["synced_count"],
                "skipped": result["skipped_count"],
                "failed": failed_count,
            }
            failed_dates = ", ".join(item["date"] for item in result["failed"][:5])
            if failed_dates:
                message = _("%(message)s Failed dates: %(dates)s.") % {
                    "message": message,
                    "dates": failed_dates,
                }
        else:
            notification_type = "success"
            message = _(
                "Dashboard sync finished. Synced days: %(synced)s. Skipped days: %(skipped)s."
            ) % {
                "synced": result["synced_count"],
                "skipped": result["skipped_count"],
            }

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Sales Dashboard Sync"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }


class SalesDashboardSyncState(models.Model):
    _name = "ab_sales_dashboard_sync_state"
    _description = "Sales Dashboard Sync State"
    _order = "sync_date desc, store_filter_key"

    sync_date = fields.Date(
        string="Sync Date",
        required=True,
        index=True,
    )
    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        readonly=True,
        index=True,
    )
    store_filter_key = fields.Char(
        string="Store Key",
        required=True,
        readonly=True,
        index=True,
        default="all",
    )
    store_filter_label = fields.Char(
        string="Store Scope",
        readonly=True,
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

    _uniq_dashboard_sync_state = models.Constraint(
        "UNIQUE(sync_date, store_filter_key)",
        "Dashboard sync state already exists for this date and store scope.",
    )

    @api.model
    def cron_sync_next_dashboard_day(self):
        today = fields.Date.context_today(self)
        date_to = today - timedelta(days=1)
        date_from = date_to - timedelta(days=89)
        self = self.sudo()
        self._ensure_sync_states(date_from, date_to)
        self.env.cr.commit()
        state = self._claim_next_sync_state(date_from, date_to)
        if not state:
            return False
        state_id = state.id
        try:
            state._sync_one_state_with_progress(force_resync=True)
        except Exception as error:
            self.env.cr.rollback()
            failed_state = self.browse(state_id).exists()
            if failed_state:
                failed_state._mark_failed(error)
                self.env.cr.commit()
            return False
        self._set_sync_cursor(state.store_filter_key, state.sync_date)
        self.env.cr.commit()
        return True

    @api.model
    def sync_dashboard_date_range(self, date_from, date_to, store_id=0, force_resync=True, descending=True):
        date_from, date_to = self._validate_sync_range(date_from, date_to)
        store_id = int(store_id or 0)
        dates = list(self._iter_dates(date_from, date_to, descending=descending))
        self._ensure_sync_states(date_from, date_to, store_id=store_id)
        self.env.cr.commit()
        result = {
            "synced_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "failed": [],
        }
        for sync_date in dates:
            state = self._get_or_create_state(sync_date, store_id=store_id)
            self.env.cr.commit()
            state_id = state.id
            try:
                status = state._sync_one_state_with_progress(force_resync=force_resync)
            except Exception as error:
                self.env.cr.rollback()
                failed_state = self.browse(state_id).exists()
                if failed_state:
                    failed_state._mark_failed(error)
                    self.env.cr.commit()
                result["failed_count"] += 1
                result["failed"].append({
                    "date": fields.Date.to_string(sync_date),
                    "error": self._sanitize_error(error),
                })
                continue
            if status == "skipped":
                result["skipped_count"] += 1
            else:
                result["synced_count"] += 1
        return result

    @api.model
    def start_dashboard_sync_range(self, date_from, date_to, store_id=0, force_resync=True):
        date_from, date_to = self._validate_sync_range(date_from, date_to)
        store_id = int(store_id or 0)
        self._ensure_sync_states(date_from, date_to, store_id=store_id)
        if force_resync:
            store_values = self._store_scope_values(store_id)
            states = self.sudo().search([
                ("sync_date", ">=", date_from),
                ("sync_date", "<=", date_to),
                ("store_filter_key", "=", store_values["store_filter_key"]),
                ("state", "!=", "running"),
            ])
            if states:
                states.write({
                    "state": "pending",
                    "rows_synced": 0,
                    "started_at": False,
                    "finished_at": False,
                    "error_message": False,
                })
        self.env.cr.commit()
        return self.dashboard_sync_progress(date_from, date_to, store_id=store_id)

    @api.model
    def dashboard_sync_progress(self, date_from, date_to, store_id=0):
        date_from, date_to = self._validate_sync_range(date_from, date_to)
        store_values = self._store_scope_values(int(store_id or 0))
        requested_days = max((date_to - date_from).days + 1, 1)
        self.env.cr.execute(
            """
                SELECT state, COUNT(*)
                  FROM ab_sales_dashboard_sync_state
                 WHERE sync_date >= %s
                   AND sync_date <= %s
                   AND store_filter_key = %s
                 GROUP BY state
            """,
            [date_from, date_to, store_values["store_filter_key"]],
        )
        counts = {state: int(count) for state, count in self.env.cr.fetchall()}
        pending_days = counts.get("pending", 0)
        running_days = counts.get("running", 0)
        done_days = counts.get("done", 0)
        failed_days = counts.get("failed", 0)
        known_days = pending_days + running_days + done_days + failed_days
        missing_days = max(requested_days - known_days, 0)
        progress_pct = 100.0 * done_days / requested_days if requested_days else 0.0
        return {
            "date_from": fields.Date.to_string(date_from),
            "date_to": fields.Date.to_string(date_to),
            "requested_days": requested_days,
            "known_days": known_days,
            "pending_days": pending_days,
            "running_days": running_days,
            "done_days": done_days,
            "failed_days": failed_days,
            "missing_days": missing_days,
            "progress_pct": min(max(progress_pct, 0.0), 100.0),
            "has_sync_state": bool(known_days),
            "is_active": bool(pending_days or running_days),
            "is_complete": bool(requested_days and done_days == requested_days),
            "store_filter_key": store_values["store_filter_key"],
            "store_filter_label": store_values["store_filter_label"],
        }

    @api.model
    def process_next_dashboard_sync_day(self, date_from, date_to, store_id=0, force_resync=True):
        date_from, date_to = self._validate_sync_range(date_from, date_to)
        store_id = int(store_id or 0)
        self._ensure_sync_states(date_from, date_to, store_id=store_id)
        self.env.cr.commit()
        state = self._claim_next_pending_sync_state(date_from, date_to, store_id=store_id)
        if not state:
            return self.dashboard_sync_progress(date_from, date_to, store_id=store_id)

        state_id = state.id
        try:
            state._sync_one_state_with_progress(force_resync=force_resync)
        except Exception as error:
            self.env.cr.rollback()
            failed_state = self.browse(state_id).exists()
            if failed_state:
                failed_state._mark_failed(error)
                self.env.cr.commit()
            progress = self.dashboard_sync_progress(date_from, date_to, store_id=store_id)
            progress.update({
                "last_status": "failed",
                "last_date": fields.Date.to_string(state.sync_date),
                "last_error": self._sanitize_error(error),
            })
            return progress

        self._set_sync_cursor(state.store_filter_key, state.sync_date)
        self.env.cr.commit()
        progress = self.dashboard_sync_progress(date_from, date_to, store_id=store_id)
        progress.update({
            "last_status": "done",
            "last_date": fields.Date.to_string(state.sync_date),
        })
        return progress

    @api.model
    def _validate_sync_range(self, date_from, date_to):
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        today = fields.Date.context_today(self)
        if not date_from or not date_to:
            raise UserError(_("Date From and Date To are required."))
        if date_from > date_to:
            raise UserError(_("Date From must be before or equal to Date To."))
        if date_to >= today:
            raise UserError(_("Only completed days can be synced. Select a date before today."))
        return date_from, date_to

    @api.model
    def _iter_dates(self, date_from, date_to, descending=True):
        current = fields.Date.to_date(date_to if descending else date_from)
        end = fields.Date.to_date(date_from if descending else date_to)
        step = -1 if descending else 1
        while True:
            if descending and current < end:
                break
            if not descending and current > end:
                break
            yield current
            current += timedelta(days=step)

    @api.model
    def _ensure_sync_states(self, date_from, date_to, store_id=0):
        store_values = self._store_scope_values(store_id)
        existing_dates = {
            fields.Date.to_date(value)
            for value in self.sudo().search([
                ("sync_date", ">=", date_from),
                ("sync_date", "<=", date_to),
                ("store_filter_key", "=", store_values["store_filter_key"]),
            ]).mapped("sync_date")
        }
        vals_list = []
        for sync_date in self._iter_dates(date_from, date_to, descending=False):
            if sync_date not in existing_dates:
                vals = dict(store_values, sync_date=sync_date)
                vals_list.append(vals)
        if vals_list:
            self.sudo().create(vals_list)

    @api.model
    def _store_scope_values(self, store_id=0):
        Snapshot = self.env["ab.sales.dashboard.snapshot"].sudo()
        filters = {"date_from": fields.Date.context_today(self), "date_to": fields.Date.context_today(self), "store_id": int(store_id or 0)}
        stores = Snapshot._stores_from_filters(filters)
        if store_id and not stores:
            raise UserError(_("The selected store was not found."))
        if any(not store.eplus_serial for store in stores):
            missing = ", ".join(stores.filtered(lambda store: not store.eplus_serial).mapped("display_name"))
            raise UserError(_("These stores have no E-Plus serial: %s") % missing)
        return {
            "store_id": stores[:1].id if len(stores) == 1 else False,
            "store_filter_key": Snapshot._store_filter_key(stores),
            "store_filter_label": Snapshot._store_filter_label(stores),
        }

    @api.model
    def _get_or_create_state(self, sync_date, store_id=0):
        store_values = self._store_scope_values(store_id)
        state = self.sudo().search([
            ("sync_date", "=", sync_date),
            ("store_filter_key", "=", store_values["store_filter_key"]),
        ], limit=1)
        if state:
            return state
        vals = dict(store_values, sync_date=sync_date)
        return self.sudo().create(vals)

    @api.model
    def _claim_next_sync_state(self, date_from, date_to, store_id=0):
        store_values = self._store_scope_values(store_id)
        stale_before = fields.Datetime.now() - timedelta(hours=6)
        self.sudo().search([
            ("store_filter_key", "=", store_values["store_filter_key"]),
            ("state", "=", "running"),
            ("started_at", "<", fields.Datetime.to_string(stale_before)),
        ]).write({
            "state": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": _("Sync was marked failed because the previous run became stale."),
        })

        self.env.cr.execute(
            """
                SELECT id
                  FROM ab_sales_dashboard_sync_state
                 WHERE sync_date >= %s
                   AND sync_date <= %s
                   AND store_filter_key = %s
                   AND state = ANY(%s)
                 ORDER BY sync_date DESC
                 FOR UPDATE SKIP LOCKED
                 LIMIT 1
            """,
            [date_from, date_to, store_values["store_filter_key"], ["pending", "failed"]],
        )
        row = self.env.cr.fetchone()
        if not row:
            target_date = self._next_cursor_date(date_from, date_to, store_values["store_filter_key"])
            row = self._claim_done_state_for_target(date_from, date_to, store_values["store_filter_key"], target_date)
        return self.browse(row[0]) if row else self.browse()

    @api.model
    def _claim_next_pending_sync_state(self, date_from, date_to, store_id=0):
        store_values = self._store_scope_values(store_id)
        stale_before = fields.Datetime.now() - timedelta(hours=6)
        self.sudo().search([
            ("store_filter_key", "=", store_values["store_filter_key"]),
            ("state", "=", "running"),
            ("started_at", "<", fields.Datetime.to_string(stale_before)),
        ]).write({
            "state": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": _("Sync was marked failed because the previous run became stale."),
        })

        self.env.cr.execute(
            """
                SELECT id
                  FROM ab_sales_dashboard_sync_state
                 WHERE sync_date >= %s
                   AND sync_date <= %s
                   AND store_filter_key = %s
                   AND state = 'pending'
                 ORDER BY sync_date DESC
                 FOR UPDATE SKIP LOCKED
                 LIMIT 1
            """,
            [date_from, date_to, store_values["store_filter_key"]],
        )
        row = self.env.cr.fetchone()
        return self.browse(row[0]) if row else self.browse()

    @api.model
    def _claim_done_state_for_target(self, date_from, date_to, store_filter_key, target_date):
        for operator, order in (("=", "sync_date DESC"), ("<=", "sync_date DESC"), (">=", "sync_date DESC")):
            self.env.cr.execute(
                f"""
                    SELECT id
                      FROM ab_sales_dashboard_sync_state
                     WHERE sync_date >= %s
                       AND sync_date <= %s
                       AND store_filter_key = %s
                       AND state = 'done'
                       AND sync_date {operator} %s
                     ORDER BY {order}
                     FOR UPDATE SKIP LOCKED
                     LIMIT 1
                """,
                [date_from, date_to, store_filter_key, target_date],
            )
            row = self.env.cr.fetchone()
            if row:
                return row
        return False

    @api.model
    def _next_cursor_date(self, date_from, date_to, store_filter_key):
        param_key = self._cursor_param_key(store_filter_key)
        last_date = fields.Date.to_date(self.env["ir.config_parameter"].sudo().get_param(param_key))
        if not last_date:
            return date_to
        next_date = last_date - timedelta(days=1)
        return date_to if next_date < date_from else next_date

    @api.model
    def _set_sync_cursor(self, store_filter_key, sync_date):
        self.env["ir.config_parameter"].sudo().set_param(
            self._cursor_param_key(store_filter_key),
            fields.Date.to_string(sync_date),
        )

    @api.model
    def _cursor_param_key(self, store_filter_key):
        clean_key = "".join(character if character.isalnum() else "_" for character in (store_filter_key or "all"))
        return "ab_sales_dashboard.next_sync_date.%s" % clean_key

    def _sync_one_state(self, force_resync=True):
        self.ensure_one()
        if not force_resync and self._is_dashboard_day_complete():
            self._mark_done(self.rows_synced)
            return "skipped"
        self._mark_running()
        rows_synced = self._sync_dashboard_day()
        self._mark_done(rows_synced)
        self._log_sync_completed(rows_synced)
        return "synced"

    def _sync_one_state_with_progress(self, force_resync=True):
        self.ensure_one()
        if not force_resync and self._is_dashboard_day_complete():
            self._mark_done(self.rows_synced)
            self.env.cr.commit()
            return "skipped"

        self._mark_running()
        self.env.cr.commit()
        Snapshot = self.env["ab.sales.dashboard.snapshot"].sudo()
        with Snapshot._sales_dashboard_refresh_lock():
            rows_synced = self._sync_dashboard_day()
        self._mark_done(rows_synced)
        self.env.cr.commit()
        self._log_sync_completed(rows_synced)
        return "synced"

    def _mark_running(self):
        self.ensure_one()
        self.write({
            "state": "running",
            "started_at": fields.Datetime.now(),
            "finished_at": False,
            "error_message": False,
        })

    def _mark_done(self, rows_synced):
        self.ensure_one()
        self.write({
            "state": "done",
            "rows_synced": rows_synced,
            "finished_at": fields.Datetime.now(),
            "error_message": False,
        })

    def _log_sync_completed(self, rows_synced):
        self.ensure_one()
        _logger.info(
            "event=sales_dashboard_day_sync_completed sync_date=%s store_key=%s rows_synced=%s",
            self.sync_date,
            self.store_filter_key,
            rows_synced,
        )

    def _sync_dashboard_day(self):
        self.ensure_one()
        filters = {
            "date_from": self.sync_date,
            "date_to": self.sync_date,
            "store_id": self.store_id.id if self.store_id else 0,
        }
        snapshot = self.env["ab.sales.dashboard.snapshot"].sudo()._create_snapshot(filters)
        return self._dashboard_sync_row_count(snapshot)

    def _is_dashboard_day_complete(self):
        self.ensure_one()
        Snapshot = self.env["ab.sales.dashboard.snapshot"].sudo()
        filters = {
            "date_from": self.sync_date,
            "date_to": self.sync_date,
            "store_id": self.store_id.id if self.store_id else 0,
        }
        stores = Snapshot._fact_scope_stores(filters)
        store_eplus_ids = [int(store.eplus_serial) for store in stores if store.eplus_serial]
        if not store_eplus_ids:
            return False
        return bool(
            Snapshot._find_latest_full_snapshot(filters)
            and Snapshot._has_complete_sync_coverage(self.sync_date, self.sync_date, store_eplus_ids, 1)
            and Snapshot._has_complete_fact_coverage(self.sync_date, self.sync_date, store_eplus_ids, 1, "item")
            and Snapshot._has_complete_fact_coverage(self.sync_date, self.sync_date, store_eplus_ids, 1, "user")
        )

    def _dashboard_sync_row_count(self, snapshot):
        self.ensure_one()
        Snapshot = self.env["ab.sales.dashboard.snapshot"].sudo()
        filters = {
            "date_from": self.sync_date,
            "date_to": self.sync_date,
            "store_id": self.store_id.id if self.store_id else 0,
        }
        stores = Snapshot._fact_scope_stores(filters)
        store_eplus_ids = [int(store.eplus_serial) for store in stores if store.eplus_serial]
        if not store_eplus_ids:
            return 0
        daily_domain = [
            ("report_date", "=", self.sync_date),
            ("store_eplus_id", "in", store_eplus_ids),
        ]
        return (
            self.env["ab.sales.dashboard.daily.store.fact"].sudo().search_count(daily_domain)
            + self.env["ab.sales.dashboard.daily.collection.fact"].sudo().search_count(daily_domain)
            + self.env["ab.sales.dashboard.daily.item.fact"].sudo().search_count(daily_domain)
            + self.env["ab_sales_dashboard_daily_user_fact"].sudo().search_count(daily_domain)
            + len(snapshot.collection_line_ids)
            + len(snapshot.user_line_ids)
            + len(snapshot.item_line_ids)
            + len(snapshot.invoice_line_ids)
        )

    def _mark_failed(self, error):
        self.ensure_one()
        message = self._sanitize_error(error)
        self.write({
            "state": "failed",
            "finished_at": fields.Datetime.now(),
            "error_message": message,
        })
        _logger.exception(
            "event=sales_dashboard_day_sync_failed sync_date=%s store_key=%s error=%s",
            self.sync_date,
            self.store_filter_key,
            message,
        )

    @api.model
    def _sanitize_error(self, error):
        message = str(error or "").replace("\n", " ").replace("\r", " ").strip()
        return message[:1000]
