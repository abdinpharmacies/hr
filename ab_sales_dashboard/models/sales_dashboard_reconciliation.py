import logging
import time
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


class SalesDashboardReconciliationJob(models.Model):
    _name = "ab.sales.dashboard.reconciliation.job"
    _inherit = ["ab.sales.dashboard.config.mixin"]
    _description = "Sales Dashboard Coverage Reconciliation Job"
    _order = "create_date desc, id desc"

    name = fields.Char(required=True, default="Sales Dashboard Reconciliation")
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    store_ids = fields.Many2many(
        "ab_store",
        "ab_sales_dash_recon_job_store_rel",
        "job_id",
        "store_id",
        string="Stores",
    )
    store_filter_key = fields.Char(readonly=True, index=True)
    state = fields.Selection([
        ("draft", "Draft"),
        ("analyzing", "Analyzing"),
        ("ready", "Ready"),
        ("running", "Running"),
        ("partial", "Partial"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ], required=True, default="draft", readonly=True, index=True)

    total_branch_days = fields.Integer(readonly=True)
    covered_branch_days = fields.Integer(readonly=True)
    missing_branch_days = fields.Integer(readonly=True)
    processed_branch_days = fields.Integer(readonly=True)
    failed_branch_days = fields.Integer(readonly=True)

    chunk_count = fields.Integer(readonly=True)
    completed_chunk_count = fields.Integer(readonly=True)
    failed_chunk_count = fields.Integer(readonly=True)

    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    last_error = fields.Text(readonly=True)
    last_processed_date = fields.Date(readonly=True)
    created_by = fields.Many2one("res.users", required=True, readonly=True, default=lambda self: self.env.user)
    chunk_ids = fields.One2many("ab.sales.dashboard.reconciliation.chunk", "job_id", readonly=True)

    def action_analyze_coverage(self):
        for job in self:
            job._check_reconciliation_manager()
            job._analyze_coverage()
        return True

    def action_start_reconciliation(self):
        for job in self:
            job._check_reconciliation_manager()
            if job.state == "draft":
                job._analyze_coverage()
            job._run_reconciliation_chunks(("pending",))
        return True

    def action_retry_failed_chunks(self):
        for job in self:
            job._check_reconciliation_manager()
            job._run_reconciliation_chunks(("failed", "pending"))
        return True

    def action_cancel(self):
        for job in self:
            job._check_reconciliation_manager()
            if job.state in ("done", "cancelled"):
                continue
            job.chunk_ids.filtered(lambda chunk: chunk.state in ("pending", "failed")).write({"state": "cancelled"})
            job.write({"state": "cancelled", "completed_at": fields.Datetime.now()})
        return True

    def _check_reconciliation_manager(self):
        if not self.env.user.has_group("ab_sales_dashboard.group_ab_sales_dashboard_manager"):
            raise AccessError(_("Only sales dashboard managers can run coverage reconciliation."))

    def _analyze_coverage(self):
        self.ensure_one()
        if self.state == "running":
            raise UserError(_("A reconciliation job cannot be analyzed while it is running."))
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_reconciliation_analysis_started job_id=%s date_from=%s date_to=%s",
            self.id,
            self.date_from,
            self.date_to,
        )
        self.write({"state": "analyzing", "last_error": False})
        stores = self._reconciliation_stores()
        store_eplus_ids = self._store_eplus_ids(stores)
        self._validate_reconciliation_scope(stores)
        missing_rows = self._missing_coverage_rows(store_eplus_ids, fact_type="item")
        metrics = self.env["ab.sales.dashboard.snapshot"]._fact_coverage_metrics(
            self.date_from,
            self.date_to,
            store_eplus_ids,
            "item",
        )
        chunks = self._plan_reconciliation_chunks(missing_rows, stores)
        self.chunk_ids.sudo().unlink()
        self._create_chunks(chunks)
        state = "ready" if chunks else "done"
        self.write({
            "name": self._default_job_name(stores),
            "store_filter_key": self.env["ab.sales.dashboard.snapshot"]._store_filter_key(stores),
            "state": state,
            "total_branch_days": metrics["expected_store_days"],
            "covered_branch_days": metrics["covered_store_days"],
            "missing_branch_days": len(missing_rows),
            "processed_branch_days": 0,
            "failed_branch_days": 0,
            "chunk_count": len(chunks),
            "completed_chunk_count": 0,
            "failed_chunk_count": 0,
            "completed_at": fields.Datetime.now() if not chunks else False,
            "last_processed_date": False,
        })
        _logger.info(
            "event=sales_dashboard_reconciliation_analysis_completed job_id=%s duration_ms=%s total_branch_days=%s missing_branch_days=%s chunk_count=%s",
            self.id,
            int((time.monotonic() - started) * 1000),
            metrics["expected_store_days"],
            len(missing_rows),
            len(chunks),
        )

    def _reconciliation_stores(self):
        self.ensure_one()
        if self.store_ids:
            stores = self.store_ids
        else:
            stores = self.env["ab_store"].sudo().search([
                ("active", "=", True),
                ("allow_sale", "=", True),
                ("eplus_serial", "!=", False),
            ], order="eplus_serial")
        if not stores:
            raise UserError(_("No E-Plus stores are available for reconciliation."))
        missing = stores.filtered(lambda store: not store.eplus_serial)
        if missing:
            raise UserError(_("These stores have no E-Plus serial: %s") % ", ".join(missing.mapped("display_name")))
        return stores

    def _store_eplus_ids(self, stores):
        return sorted(int(store.eplus_serial) for store in stores if store.eplus_serial)

    def _validate_reconciliation_scope(self, stores):
        self.ensure_one()
        date_from, date_to, day_count = self._validate_dashboard_date_range(
            self.date_from,
            self.date_to,
            max_days=self._max_reconciliation_branch_days(),
            limit_message=_("The reconciliation date span exceeds the configured branch-day safety limit of %s days."),
        )
        branch_days = day_count * len(stores)
        max_branch_days = self._max_reconciliation_branch_days()
        if branch_days > max_branch_days:
            raise UserError(_("The reconciliation scope exceeds the configured safety limit of %s branch-days.") % max_branch_days)
        return date_from, date_to, day_count

    def _missing_coverage_rows(self, store_eplus_ids, fact_type="item"):
        self.ensure_one()
        started = time.monotonic()
        if not store_eplus_ids:
            return []
        self.env.cr.execute(
            """
                WITH requested_dates AS (
                    SELECT generate_series(%s::date, %s::date, interval '1 day')::date AS report_date
                ),
                requested_stores AS (
                    SELECT unnest(%s::integer[]) AS store_eplus_id
                ),
                expected AS (
                    SELECT requested_dates.report_date, requested_stores.store_eplus_id
                    FROM requested_dates
                    CROSS JOIN requested_stores
                )
                SELECT expected.report_date, expected.store_eplus_id
                FROM expected
                LEFT JOIN ab_sales_dashboard_fact_coverage coverage
                  ON coverage.report_date = expected.report_date
                 AND coverage.store_eplus_id = expected.store_eplus_id
                 AND coverage.fact_type = %s
                 AND coverage.sync_state = 'synced'
                WHERE coverage.id IS NULL
                ORDER BY expected.report_date, expected.store_eplus_id
            """,
            [self.date_from, self.date_to, store_eplus_ids, fact_type],
        )
        rows = [(fields.Date.to_date(report_date), int(store_eplus_id)) for report_date, store_eplus_id in self.env.cr.fetchall()]
        _logger.info(
            "event=sales_dashboard_reconciliation_plan_started job_id=%s duration_ms=%s missing_branch_days=%s fact_type=%s",
            self.id,
            int((time.monotonic() - started) * 1000),
            len(rows),
            fact_type,
        )
        return rows

    def _plan_reconciliation_chunks(self, missing_rows, stores):
        self.ensure_one()
        started = time.monotonic()
        max_days = self._dashboard_max_days()
        store_by_eplus = {int(store.eplus_serial): store for store in stores}
        missing_by_date = defaultdict(set)
        for report_date, store_eplus_id in missing_rows:
            if store_eplus_id in store_by_eplus:
                missing_by_date[fields.Date.to_date(report_date)].add(store_eplus_id)

        chunks = []
        active_start = False
        active_end = False
        active_store_ids = False
        previous_date = False
        for report_date in sorted(missing_by_date):
            store_ids = tuple(sorted(missing_by_date[report_date]))
            contiguous = previous_date and report_date == previous_date + timedelta(days=1)
            active_length = ((active_end - active_start).days + 1) if active_start else 0
            can_extend = (
                active_start
                and contiguous
                and active_store_ids == store_ids
                and active_length < max_days
            )
            if not can_extend:
                if active_start:
                    chunks.append(self._chunk_plan(active_start, active_end, active_store_ids, store_by_eplus))
                active_start = report_date
                active_store_ids = store_ids
            active_end = report_date
            previous_date = report_date
        if active_start:
            chunks.append(self._chunk_plan(active_start, active_end, active_store_ids, store_by_eplus))

        max_chunks = self._max_reconciliation_chunks()
        if len(chunks) > max_chunks:
            raise UserError(_("The reconciliation plan exceeds the configured safety limit of %s chunks.") % max_chunks)
        _logger.info(
            "event=sales_dashboard_reconciliation_plan_completed job_id=%s duration_ms=%s chunk_count=%s missing_branch_days=%s",
            self.id,
            int((time.monotonic() - started) * 1000),
            len(chunks),
            len(missing_rows),
        )
        return chunks

    def _chunk_plan(self, date_from, date_to, store_eplus_ids, store_by_eplus):
        stores = self.env["ab_store"].browse([store_by_eplus[store_id].id for store_id in store_eplus_ids])
        day_count = (date_to - date_from).days + 1
        return {
            "date_from": date_from,
            "date_to": date_to,
            "store_ids": stores.ids,
            "store_filter_key": self.env["ab.sales.dashboard.snapshot"]._store_filter_key(stores),
            "branch_day_count": day_count * len(stores),
        }

    def _create_chunks(self, chunks):
        vals_list = []
        for sequence, chunk in enumerate(chunks, start=1):
            vals_list.append({
                "job_id": self.id,
                "sequence": sequence,
                "date_from": chunk["date_from"],
                "date_to": chunk["date_to"],
                "store_ids": [(6, 0, chunk["store_ids"])],
                "store_filter_key": chunk["store_filter_key"],
                "branch_day_count": chunk["branch_day_count"],
                "state": "pending",
            })
        if vals_list:
            self.env["ab.sales.dashboard.reconciliation.chunk"].sudo().create(vals_list)

    def _run_reconciliation_chunks(self, states):
        self.ensure_one()
        started = time.monotonic()
        if self.state == "cancelled":
            raise UserError(_("Cancelled reconciliation jobs cannot be started."))
        chunks = self.chunk_ids.filtered(lambda chunk: chunk.state in states).sorted("sequence")
        if not chunks:
            self._refresh_progress_counts()
            self._record_reconciliation_telemetry(started)
            return True
        self.write({"state": "running", "started_at": self.started_at or fields.Datetime.now(), "last_error": False})
        _logger.info(
            "event=sales_dashboard_reconciliation_started job_id=%s chunk_count=%s",
            self.id,
            len(chunks),
        )
        try:
            with self._sales_dashboard_refresh_lock():
                for chunk in chunks:
                    try:
                        with self.env.cr.savepoint():
                            chunk._execute_reconciliation_chunk()
                    except Exception as error:
                        chunk._mark_failed(error)
                        continue
        except Exception as error:
            self.write({
                "state": "failed",
                "last_error": self._sanitize_error(error),
                "completed_at": fields.Datetime.now(),
            })
            _logger.exception(
                "event=sales_dashboard_reconciliation_failed job_id=%s duration_ms=%s",
                self.id,
                int((time.monotonic() - started) * 1000),
            )
            self._record_reconciliation_telemetry(started)
            raise
        self._refresh_progress_counts()
        if self.state == "partial":
            _logger.info(
                "event=sales_dashboard_reconciliation_partial job_id=%s duration_ms=%s completed_chunks=%s failed_chunks=%s",
                self.id,
                int((time.monotonic() - started) * 1000),
                self.completed_chunk_count,
                self.failed_chunk_count,
            )
        else:
            _logger.info(
                "event=sales_dashboard_reconciliation_completed job_id=%s duration_ms=%s completed_chunks=%s failed_chunks=%s",
                self.id,
                int((time.monotonic() - started) * 1000),
                self.completed_chunk_count,
                self.failed_chunk_count,
            )
        self._record_reconciliation_telemetry(started)
        return True

    def _record_reconciliation_telemetry(self, started):
        self.ensure_one()
        stores = self._reconciliation_stores()
        self.env["ab.sales.dashboard.report.telemetry"].record_operation(
            "reconciliation_run",
            "reconciliation",
            filters={"date_from": self.date_from, "date_to": self.date_to, "store_id": self.store_ids[:1].id if len(self.store_ids) == 1 else 0},
            duration_ms=int((time.monotonic() - started) * 1000),
            selected_store_count=len(stores),
            all_stores=not bool(self.store_ids),
        )

    def _refresh_progress_counts(self):
        self.ensure_one()
        chunks = self.chunk_ids
        completed = chunks.filtered(lambda chunk: chunk.state == "done")
        failed = chunks.filtered(lambda chunk: chunk.state == "failed")
        pending = chunks.filtered(lambda chunk: chunk.state in ("pending", "running"))
        if failed and completed:
            state = "partial"
        elif failed and not completed:
            state = "failed"
        elif not pending:
            state = "done"
        else:
            state = "ready"
        values = {
            "chunk_count": len(chunks),
            "completed_chunk_count": len(completed),
            "failed_chunk_count": len(failed),
            "processed_branch_days": sum(completed.mapped("branch_day_count")),
            "failed_branch_days": sum(failed.mapped("branch_day_count")),
            "state": state,
            "completed_at": fields.Datetime.now() if state in ("done", "partial", "failed") else False,
            "last_processed_date": max(completed.mapped("date_to")) if completed else False,
        }
        if failed:
            values["last_error"] = failed[-1].error_message
        self.write(values)

    def _default_job_name(self, stores):
        return _("Sales Dashboard Reconciliation %(from)s to %(to)s - %(stores)s") % {
            "from": self.date_from,
            "to": self.date_to,
            "stores": self.env["ab.sales.dashboard.snapshot"]._store_filter_label(stores),
        }

    @api.model
    def _sanitize_error(self, error):
        message = str(error or "").replace("\n", " ").replace("\r", " ").strip()
        return message[:1000]


class SalesDashboardReconciliationChunk(models.Model):
    _name = "ab.sales.dashboard.reconciliation.chunk"
    _inherit = ["ab.sales.dashboard.config.mixin"]
    _description = "Sales Dashboard Coverage Reconciliation Chunk"
    _order = "job_id, sequence, id"

    job_id = fields.Many2one("ab.sales.dashboard.reconciliation.job", required=True, readonly=True, ondelete="cascade", index=True)
    sequence = fields.Integer(required=True, readonly=True, index=True)
    date_from = fields.Date(required=True, readonly=True, index=True)
    date_to = fields.Date(required=True, readonly=True, index=True)
    store_ids = fields.Many2many(
        "ab_store",
        "ab_sales_dash_recon_chunk_store_rel",
        "chunk_id",
        "store_id",
        string="Stores",
        readonly=True,
    )
    store_filter_key = fields.Char(readonly=True, index=True)
    branch_day_count = fields.Integer(readonly=True)
    state = fields.Selection([
        ("pending", "Pending"),
        ("running", "Running"),
        ("done", "Done"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ], required=True, default="pending", readonly=True, index=True)
    attempt_count = fields.Integer(readonly=True)
    started_at = fields.Datetime(readonly=True)
    completed_at = fields.Datetime(readonly=True)
    error_message = fields.Text(readonly=True)
    source_duration_ms = fields.Integer(readonly=True)
    persistence_duration_ms = fields.Integer(readonly=True)

    _uniq_job_sequence = models.Constraint(
        "UNIQUE(job_id, sequence)",
        "Reconciliation chunk sequence must be unique per job.",
    )

    def _execute_reconciliation_chunk(self):
        self.ensure_one()
        self.job_id._check_reconciliation_manager()
        if self.state == "done":
            return True
        if self._is_chunk_covered():
            self.write({
                "state": "done",
                "completed_at": fields.Datetime.now(),
                "error_message": False,
            })
            _logger.info(
                "event=sales_dashboard_reconciliation_chunk_skipped_covered job_id=%s chunk_id=%s date_from=%s date_to=%s store_count=%s",
                self.job_id.id,
                self.id,
                self.date_from,
                self.date_to,
                len(self.store_ids),
            )
            return True

        self.write({
            "state": "running",
            "started_at": fields.Datetime.now(),
            "attempt_count": self.attempt_count + 1,
            "error_message": False,
        })
        _logger.info(
            "event=sales_dashboard_reconciliation_chunk_started job_id=%s chunk_id=%s date_from=%s date_to=%s store_count=%s branch_day_count=%s attempt_count=%s",
            self.job_id.id,
            self.id,
            self.date_from,
            self.date_to,
            len(self.store_ids),
            self.branch_day_count,
            self.attempt_count,
        )
        store_eplus_ids = [int(store.eplus_serial) for store in self.store_ids if store.eplus_serial]
        service = self.env["ab.sales.dashboard.service"]
        source_started = time.monotonic()
        daily_payload = service.fetch_daily_fact_data(
            self.date_from,
            fields.Date.add(self.date_to, days=1),
            store_eplus_ids=store_eplus_ids,
        )
        source_duration_ms = int((time.monotonic() - source_started) * 1000)
        _logger.info(
            "event=sales_dashboard_reconciliation_chunk_source_completed job_id=%s chunk_id=%s duration_ms=%s fact_row_count=%s",
            self.job_id.id,
            self.id,
            source_duration_ms,
            service._daily_fact_row_count(daily_payload),
        )

        persistence_started = time.monotonic()
        self.env["ab.sales.dashboard.snapshot"]._upsert_daily_facts(
            {
                "date_from": self.date_from,
                "date_to": self.date_to,
                "store_id": 0,
            },
            daily_payload,
            stores=self.store_ids,
        )
        persistence_duration_ms = int((time.monotonic() - persistence_started) * 1000)
        _logger.info(
            "event=sales_dashboard_reconciliation_chunk_persistence_completed job_id=%s chunk_id=%s duration_ms=%s",
            self.job_id.id,
            self.id,
            persistence_duration_ms,
        )
        self.write({
            "state": "done",
            "completed_at": fields.Datetime.now(),
            "source_duration_ms": source_duration_ms,
            "persistence_duration_ms": persistence_duration_ms,
            "error_message": False,
        })
        _logger.info(
            "event=sales_dashboard_reconciliation_chunk_completed job_id=%s chunk_id=%s date_from=%s date_to=%s store_count=%s branch_day_count=%s",
            self.job_id.id,
            self.id,
            self.date_from,
            self.date_to,
            len(self.store_ids),
            self.branch_day_count,
        )
        return True

    def _is_chunk_covered(self):
        self.ensure_one()
        store_eplus_ids = [int(store.eplus_serial) for store in self.store_ids if store.eplus_serial]
        day_count = max((self.date_to - self.date_from).days + 1, 1)
        return self.env["ab.sales.dashboard.snapshot"]._has_complete_fact_coverage(
            self.date_from,
            self.date_to,
            store_eplus_ids,
            day_count,
            "item",
        )

    def _mark_failed(self, error):
        self.ensure_one()
        message = self.job_id._sanitize_error(error)
        self.write({
            "state": "failed",
            "completed_at": fields.Datetime.now(),
            "error_message": message,
        })
        _logger.exception(
            "event=sales_dashboard_reconciliation_chunk_failed job_id=%s chunk_id=%s date_from=%s date_to=%s store_count=%s error=%s",
            self.job_id.id,
            self.id,
            self.date_from,
            self.date_to,
            len(self.store_ids),
            message,
        )
