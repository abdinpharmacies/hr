import logging
from contextlib import contextmanager

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


class SalesDashboardConfigMixin(models.AbstractModel):
    _name = "ab.sales.dashboard.config.mixin"
    _description = "Sales Dashboard Configuration Helpers"

    # Stable transaction-scoped PostgreSQL advisory lock for heavy sales
    # dashboard refreshes. Keep this fixed across workers/processes.
    _SALES_DASHBOARD_REFRESH_LOCK_ID = 1907350131

    @api.model
    def _get_int_param(self, key, default, minimum=None, maximum=None):
        raw_value = self.env["ir.config_parameter"].sudo().get_param(key)
        if raw_value in (None, False, ""):
            return default
        try:
            value = int(str(raw_value).strip())
        except (TypeError, ValueError):
            _logger.warning(
                "event=sales_dashboard_invalid_config key=%s value=%r default=%s reason=parse_error",
                key,
                raw_value,
                default,
            )
            return default
        if minimum is not None and value < minimum:
            _logger.warning(
                "event=sales_dashboard_invalid_config key=%s value=%r default=%s reason=below_minimum minimum=%s",
                key,
                raw_value,
                default,
                minimum,
            )
            return default
        if maximum is not None and value > maximum:
            _logger.warning(
                "event=sales_dashboard_config_clamped key=%s value=%r maximum=%s",
                key,
                raw_value,
                maximum,
            )
            return maximum
        return value

    @api.model
    def _dashboard_max_days(self):
        return self._get_int_param("ab_reports.max_dashboard_days", 31, minimum=1, maximum=31)

    @api.model
    def _summary_max_days(self):
        return self._get_int_param("ab_reports.max_summary_days", 90, minimum=31, maximum=365)

    @api.model
    def _query_batch_size(self):
        return self._get_int_param("ab_reports.query_batch_size", 1000, minimum=1, maximum=2000)

    @api.model
    def _query_timeout_seconds(self):
        return self._get_int_param("ab_reports.query_timeout_seconds", 120, minimum=1, maximum=300)

    @api.model
    def _max_daily_fact_rows(self):
        return self._get_int_param("ab_reports.max_daily_fact_rows", 10000, minimum=1, maximum=50000)

    @api.model
    def _max_daily_item_fact_rows(self):
        return self._get_int_param("ab_reports.max_daily_item_fact_rows", 750000, minimum=1, maximum=1000000)

    @api.model
    def _max_daily_coverage_rows(self):
        return self._get_int_param("ab_reports.max_daily_coverage_rows", 10000, minimum=1, maximum=50000)

    @api.model
    def _max_snapshot_child_rows(self):
        return self._get_int_param("ab_reports.max_snapshot_child_rows", 100, minimum=1, maximum=1000)

    @api.model
    def _max_archive_payload_bytes(self):
        return self._get_int_param("ab_reports.max_archive_payload_bytes", 1048576, minimum=1, maximum=10485760)

    @api.model
    def _max_reconciliation_branch_days(self):
        return self._get_int_param("ab_reports.max_reconciliation_branch_days", 10000, minimum=1, maximum=50000)

    @api.model
    def _max_reconciliation_chunks(self):
        return self._get_int_param("ab_reports.max_reconciliation_chunks", 500, minimum=1, maximum=5000)

    @api.model
    def _telemetry_retention_days(self):
        return self._get_int_param("ab_reports.telemetry_retention_days", 90, minimum=1, maximum=365)

    @api.model
    def _telemetry_cleanup_batch_size(self):
        return self._get_int_param("ab_reports.telemetry_cleanup_batch_size", 5000, minimum=1, maximum=20000)

    @api.model
    def _warn_dashboard_duration_ms(self):
        return self._get_int_param("ab_reports.warn_dashboard_duration_ms", 5000, minimum=1, maximum=3600000)

    @api.model
    def _warn_summary_duration_ms(self):
        return self._get_int_param("ab_reports.warn_summary_duration_ms", 5000, minimum=1, maximum=3600000)

    @api.model
    def _warn_refresh_duration_ms(self):
        return self._get_int_param("ab_reports.warn_refresh_duration_ms", 120000, minimum=1, maximum=3600000)

    @api.model
    def _warn_payload_size_bytes(self):
        return self._get_int_param("ab_reports.warn_payload_size_bytes", 524288, minimum=1, maximum=104857600)

    @api.model
    def _warn_daily_item_fact_rows(self):
        return self._get_int_param("ab_reports.warn_daily_item_fact_rows", 250000, minimum=1, maximum=100000000)

    @api.model
    def _fact_demand_threshold_percentage(self):
        return self._get_int_param("ab_reports.fact_demand_threshold_percentage", 30, minimum=1, maximum=100)

    @api.model
    def _coerce_dashboard_date(self, value, label):
        if not value:
            raise UserError(_("%s is required.") % label)
        try:
            parsed = fields.Date.to_date(value)
        except (TypeError, ValueError):
            parsed = False
        if not parsed:
            raise UserError(_("Invalid %s.") % label)
        return parsed

    @api.model
    def _validate_dashboard_date_range(self, date_from, date_to, date_to_exclusive=False, max_days=None, limit_message=None):
        date_from = self._coerce_dashboard_date(date_from, _("Date From"))
        date_to = self._coerce_dashboard_date(date_to, _("Date To"))
        if date_to_exclusive:
            if date_to <= date_from:
                raise UserError(_("Date To must be greater than Date From."))
            day_count = (date_to - date_from).days
        else:
            if date_to < date_from:
                raise UserError(_("Date To must be greater than or equal to Date From."))
            day_count = (date_to - date_from).days + 1
        if max_days is None:
            max_days = self._dashboard_max_days()
        if max_days and day_count > max_days:
            raise UserError(
                (limit_message or _("The selected reporting period exceeds the maximum allowed dashboard range of %s days.")) % max_days
            )
        return date_from, date_to, day_count

    @api.model
    def _try_sales_dashboard_refresh_lock(self):
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(%s)", [self._SALES_DASHBOARD_REFRESH_LOCK_ID])
        row = self.env.cr.fetchone()
        return bool(row and row[0])

    @api.model
    @contextmanager
    def _sales_dashboard_refresh_lock(self):
        if not self._try_sales_dashboard_refresh_lock():
            _logger.info(
                "event=sales_dashboard_refresh_lock_busy lock_id=%s",
                self._SALES_DASHBOARD_REFRESH_LOCK_ID,
            )
            raise UserError(_("A sales dashboard refresh is already running. Please wait for it to finish and try again."))
        yield
