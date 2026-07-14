import json
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


EVENT_TYPES = (
    "dashboard_read",
    "dashboard_refresh",
    "summary_read",
    "archive_read",
    "product_report_read",
    "reconciliation_run",
)
REPORT_MODES = ("full", "summary", "archive", "product_report", "reconciliation")
COVERAGE_STATES = ("complete", "partial", "unavailable", "not_applicable")
RANGE_BUCKETS = ("1_7_days", "8_31_days", "32_60_days", "61_90_days")
STORE_SCOPE_BUCKETS = (
    "single_store",
    "2_10_stores",
    "11_50_stores",
    "51_100_stores",
    "over_100_stores",
    "all_stores",
)
MAX_INTEGER_METADATA = 2147483647


class SalesDashboardReportTelemetry(models.Model):
    _name = "ab.sales.dashboard.report.telemetry"
    _inherit = ["ab.sales.dashboard.config.mixin"]
    _description = "Sales Dashboard Reporting Telemetry"
    _order = "event_date desc, id desc"

    event_date = fields.Date(required=True, readonly=True, default=fields.Date.context_today, index=True)
    event_type = fields.Selection([(value, value.replace("_", " ").title()) for value in EVENT_TYPES], required=True, readonly=True, index=True)
    report_mode = fields.Selection([(value, value.replace("_", " ").title()) for value in REPORT_MODES], required=True, readonly=True, index=True)
    range_bucket = fields.Selection([(value, value.replace("_", " ").title()) for value in RANGE_BUCKETS], required=True, readonly=True, index=True)
    store_scope_bucket = fields.Selection([(value, value.replace("_", " ").title()) for value in STORE_SCOPE_BUCKETS], required=True, readonly=True, index=True)
    coverage_state = fields.Selection([(value, value.replace("_", " ").title()) for value in COVERAGE_STATES], required=True, readonly=True, index=True)
    requested_days = fields.Integer(readonly=True, aggregator="avg")
    selected_store_count = fields.Integer(readonly=True, aggregator="avg")
    duration_ms = fields.Integer(readonly=True, aggregator="avg")
    maximum_duration_ms = fields.Integer(readonly=True, aggregator="max")
    result_size_bytes = fields.Integer(readonly=True, aggregator="avg")
    operation_count = fields.Integer(readonly=True, default=1, aggregator="sum")
    snapshot_used = fields.Boolean(readonly=True)
    daily_fact_used = fields.Boolean(readonly=True)
    item_fact_used = fields.Boolean(readonly=True)
    archive_used = fields.Boolean(readonly=True)
    product_report_used = fields.Boolean(readonly=True)
    unsupported_user_section = fields.Boolean(readonly=True, index=True)
    unsupported_item_section = fields.Boolean(readonly=True, index=True)
    unsupported_customer_section = fields.Boolean(readonly=True, index=True)
    user_section_available = fields.Boolean(readonly=True)
    item_section_available = fields.Boolean(readonly=True)
    customer_section_available = fields.Boolean(readonly=True)
    created_at = fields.Datetime(required=True, readonly=True, default=fields.Datetime.now, index=True)

    @api.model
    def _clamp_integer(self, value):
        try:
            return min(max(int(value or 0), 0), MAX_INTEGER_METADATA)
        except (TypeError, ValueError, OverflowError):
            return 0

    @api.model
    def _range_bucket(self, requested_days):
        requested_days = self._clamp_integer(requested_days) or 1
        if requested_days <= 7:
            return "1_7_days"
        if requested_days <= 31:
            return "8_31_days"
        if requested_days <= 60:
            return "32_60_days"
        return "61_90_days"

    @api.model
    def _store_scope_bucket(self, selected_store_count, all_stores=False):
        if all_stores:
            return "all_stores"
        count = self._clamp_integer(selected_store_count)
        if count <= 1:
            return "single_store"
        if count <= 10:
            return "2_10_stores"
        if count <= 50:
            return "11_50_stores"
        if count <= 100:
            return "51_100_stores"
        return "over_100_stores"

    @api.model
    def _serialized_result_size(self, result):
        if result is None:
            return 0
        try:
            payload = json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
            return self._clamp_integer(len(payload.encode("utf-8")))
        except (TypeError, ValueError, OverflowError):
            _logger.warning("event=sales_dashboard_telemetry_size_failed result_type=%s", type(result).__name__)
            return 0

    @api.model
    def record_operation(self, event_type, report_mode, filters=None, duration_ms=0, result=None, report_meta=None, selected_store_count=0, **usage):
        try:
            filters = dict(filters or {})
            report_meta = dict(report_meta or {})
            if event_type not in EVENT_TYPES or report_mode not in REPORT_MODES:
                raise ValueError("unsupported telemetry selection")
            requested_days = self._clamp_integer(report_meta.get("requested_days") or usage.get("requested_days"))
            if not requested_days and filters.get("date_from") and filters.get("date_to"):
                requested_days = self._clamp_integer((fields.Date.to_date(filters["date_to"]) - fields.Date.to_date(filters["date_from"])).days + 1)
            requested_days = requested_days or 1
            selected_store_count = self._clamp_integer(report_meta.get("store_count") or selected_store_count)
            unsupported = set(report_meta.get("unsupported_sections") or [])
            coverage_state = report_meta.get("coverage_state") or "not_applicable"
            if coverage_state not in COVERAGE_STATES:
                coverage_state = "not_applicable"
            result_size_bytes = self._serialized_result_size(result)
            duration_ms = self._clamp_integer(duration_ms)
            vals = {
                "event_date": fields.Date.context_today(self),
                "event_type": event_type,
                "report_mode": report_mode,
                "range_bucket": self._range_bucket(requested_days),
                "store_scope_bucket": self._store_scope_bucket(
                    selected_store_count,
                    all_stores=bool(usage.get("all_stores", not bool(filters.get("store_id")))),
                ),
                "coverage_state": coverage_state,
                "requested_days": requested_days,
                "selected_store_count": selected_store_count,
                "duration_ms": duration_ms,
                "maximum_duration_ms": duration_ms,
                "result_size_bytes": result_size_bytes,
                "operation_count": 1,
                "snapshot_used": bool(usage.get("snapshot_used")),
                "daily_fact_used": bool(usage.get("daily_fact_used")),
                "item_fact_used": bool(usage.get("item_fact_used")),
                "archive_used": bool(usage.get("archive_used")),
                "product_report_used": bool(usage.get("product_report_used")),
                "unsupported_user_section": "sales_by_user" in unsupported,
                "unsupported_item_section": "top_items" in unsupported,
                "unsupported_customer_section": "customer_sales" in unsupported,
                "user_section_available": "sales_by_user" not in unsupported,
                "item_section_available": "top_items" not in unsupported,
                "customer_section_available": "customer_sales" not in unsupported,
                "created_at": fields.Datetime.now(),
            }
            telemetry = self.sudo().create(vals)
            self._log_health_warnings(vals)
            return telemetry
        except Exception as error:
            _logger.warning(
                "event=sales_dashboard_telemetry_write_failed event_type=%s error_type=%s",
                event_type if event_type in EVENT_TYPES else "invalid",
                type(error).__name__,
            )
            return self.browse()

    @api.model
    def _log_health_warnings(self, vals):
        mode = vals["report_mode"]
        duration_limit = self._warn_summary_duration_ms() if mode == "summary" else self._warn_refresh_duration_ms() if vals["event_type"] == "dashboard_refresh" else self._warn_dashboard_duration_ms()
        if vals["duration_ms"] > duration_limit:
            _logger.warning(
                "event=sales_dashboard_slow_operation event_type=%s report_mode=%s duration_ms=%s threshold_ms=%s range_bucket=%s store_scope_bucket=%s",
                vals["event_type"], mode, vals["duration_ms"], duration_limit, vals["range_bucket"], vals["store_scope_bucket"],
            )
        payload_limit = self._warn_payload_size_bytes()
        if vals["result_size_bytes"] > payload_limit:
            _logger.warning(
                "event=sales_dashboard_large_payload event_type=%s report_mode=%s result_size_bytes=%s threshold_bytes=%s range_bucket=%s store_scope_bucket=%s",
                vals["event_type"], mode, vals["result_size_bytes"], payload_limit, vals["range_bucket"], vals["store_scope_bucket"],
            )

    @api.model
    def _cron_cleanup_telemetry(self):
        cutoff = fields.Date.context_today(self) - timedelta(days=self._telemetry_retention_days())
        batch_size = self._telemetry_cleanup_batch_size()
        self.env.cr.execute(
            """
            DELETE FROM ab_sales_dashboard_report_telemetry
             WHERE id IN (
                SELECT id
                  FROM ab_sales_dashboard_report_telemetry
                 WHERE event_date < %s
                 ORDER BY event_date, id
                 LIMIT %s
             )
            """,
            [cutoff, batch_size],
        )
        deleted_count = self.env.cr.rowcount
        _logger.info("event=sales_dashboard_telemetry_cleanup_completed deleted_count=%s retention_days=%s batch_size=%s", deleted_count, self._telemetry_retention_days(), batch_size)
        self._log_estimated_item_fact_volume_warning()
        return deleted_count

    @api.model
    def _log_estimated_item_fact_volume_warning(self):
        self.env.cr.execute(
            "SELECT GREATEST(reltuples, 0)::bigint FROM pg_class WHERE oid = 'ab_sales_dashboard_daily_item_fact'::regclass"
        )
        row = self.env.cr.fetchone()
        estimated_rows = self._clamp_integer(row[0] if row else 0)
        threshold = self._warn_daily_item_fact_rows()
        if estimated_rows > threshold:
            _logger.warning(
                "event=sales_dashboard_fact_volume_warning fact_type=daily_item estimated=true row_count=%s threshold_rows=%s",
                estimated_rows,
                threshold,
            )
        return estimated_rows

    @api.model
    def get_fact_volume_analysis(self):
        self._check_manager()
        queries = {
            "daily_store_facts": (("total_rows", "oldest_date", "newest_date"), "SELECT COUNT(*), MIN(report_date), MAX(report_date) FROM ab_sales_dashboard_daily_store_fact"),
            "daily_collection_facts": (("total_rows", "oldest_date", "newest_date"), "SELECT COUNT(*), MIN(report_date), MAX(report_date) FROM ab_sales_dashboard_daily_collection_fact"),
            "daily_item_facts": (("total_rows", "oldest_date", "newest_date", "distinct_item_eplus_id_count", "distinct_store_eplus_id_count"), "SELECT COUNT(*), MIN(report_date), MAX(report_date), COUNT(DISTINCT item_eplus_id), COUNT(DISTINCT store_eplus_id) FROM ab_sales_dashboard_daily_item_fact"),
            "coverage": (("legacy_sync_coverage_row_count", "fact_coverage_row_count", "store_coverage_count", "collection_coverage_count", "item_coverage_count"), "SELECT (SELECT COUNT(*) FROM ab_sales_dashboard_sync_coverage), COUNT(*), COUNT(*) FILTER (WHERE fact_type = 'store'), COUNT(*) FILTER (WHERE fact_type = 'collection'), COUNT(*) FILTER (WHERE fact_type = 'item') FROM ab_sales_dashboard_fact_coverage"),
            "snapshots": (("snapshot_count", "collection_child_row_count", "user_child_row_count", "item_child_row_count", "invoice_child_row_count"), "SELECT COUNT(*), (SELECT COUNT(*) FROM ab_sales_dashboard_collection_line), (SELECT COUNT(*) FROM ab_sales_dashboard_user_line), (SELECT COUNT(*) FROM ab_sales_dashboard_item_line), (SELECT COUNT(*) FROM ab_sales_dashboard_invoice_line) FROM ab_sales_dashboard_snapshot"),
            "archives": (("archive_count", "total_payload_size_bytes", "average_payload_size_bytes", "maximum_payload_size_bytes"), "SELECT COUNT(*), COALESCE(SUM(payload_size_bytes), 0), COALESCE(AVG(payload_size_bytes), 0), COALESCE(MAX(payload_size_bytes), 0) FROM ab_sales_dashboard_report_archive"),
            "telemetry": (("telemetry_row_count", "oldest_event_date", "newest_event_date"), "SELECT COUNT(*), MIN(event_date), MAX(event_date) FROM ab_sales_dashboard_report_telemetry"),
        }
        result = {}
        for key, (columns, query) in queries.items():
            self.env.cr.execute(query)
            result[key] = dict(zip(columns, self.env.cr.fetchone()))
        item_rows = self._clamp_integer(result["daily_item_facts"]["total_rows"])
        threshold = self._warn_daily_item_fact_rows()
        if item_rows > threshold:
            _logger.warning("event=sales_dashboard_fact_volume_warning fact_type=daily_item row_count=%s threshold_rows=%s", item_rows, threshold)
        return result

    @api.model
    def get_fact_grain_recommendation(self):
        self._check_manager()
        self.env.cr.execute(
            """
            SELECT MIN(event_date), MAX(event_date), COUNT(*),
                   COUNT(*) FILTER (WHERE unsupported_user_section),
                   COUNT(*) FILTER (WHERE unsupported_customer_section),
                   COUNT(*) FILTER (WHERE unsupported_item_section),
                   COALESCE(AVG(duration_ms), 0), COALESCE(AVG(result_size_bytes), 0),
                   COALESCE(100.0 * AVG(CASE WHEN item_section_available THEN 1.0 ELSE 0.0 END), 0)
              FROM ab_sales_dashboard_report_telemetry
             WHERE report_mode = 'summary'
               AND requested_days > 31
            """
        )
        period_from, period_to, count, user_gap, customer_gap, item_gap, avg_duration, avg_size, item_complete = self.env.cr.fetchone()
        count = int(count or 0)
        user_gap = int(user_gap or 0)
        customer_gap = int(customer_gap or 0)
        item_gap = int(item_gap or 0)
        user_pct = 100.0 * user_gap / count if count else 0.0
        customer_pct = 100.0 * customer_gap / count if count else 0.0
        item_pct = 100.0 * item_gap / count if count else 0.0
        threshold = self._fact_demand_threshold_percentage()
        if user_pct >= threshold and customer_pct >= threshold:
            recommendation = "both_employee_first" if user_pct >= customer_pct else "both_customer_first"
        elif user_pct >= threshold:
            recommendation = "employee"
        elif customer_pct >= threshold:
            recommendation = "customer"
        else:
            recommendation = "neither"
        reasons = {
            "employee": _("Employee reporting demand exceeds the configured threshold; customer demand does not."),
            "customer": _("Customer reporting demand exceeds the configured threshold; employee demand does not."),
            "both_employee_first": _("Both fact grains meet the demand threshold; employee demand is equal or higher, so implement it first."),
            "both_customer_first": _("Both fact grains meet the demand threshold; customer demand is higher, so implement it first."),
            "neither": _("Neither employee nor customer reporting demand currently meets the configured threshold."),
        }
        return {
            "measurement_period": {"date_from": fields.Date.to_string(period_from) if period_from else False, "date_to": fields.Date.to_string(period_to) if period_to else False},
            "long_range_report_count": count,
            "long_range_user_unsupported_count": user_gap,
            "long_range_customer_unsupported_count": customer_gap,
            "long_range_item_unsupported_count": item_gap,
            "user_demand_gap_percentage": user_pct,
            "customer_demand_gap_percentage": customer_pct,
            "item_demand_gap_percentage": item_pct,
            "average_long_range_duration_ms": float(avg_duration or 0.0),
            "average_long_range_result_size_bytes": float(avg_size or 0.0),
            "item_coverage_complete_percentage": float(item_complete or 0.0),
            "demand_threshold_percentage": threshold,
            "recommendation_code": recommendation,
            "recommendation_reason": reasons[recommendation],
        }

    @api.model
    def _check_manager(self):
        if not self.env.user.has_group("ab_sales_dashboard.group_ab_sales_dashboard_manager"):
            raise AccessError(_("Only sales dashboard managers can access reporting analytics."))


class SalesDashboardFactDecision(models.TransientModel):
    _name = "ab.sales.dashboard.fact.decision"
    _description = "Sales Dashboard Fact Grain Decision"

    measurement_period = fields.Char(readonly=True)
    long_range_report_count = fields.Integer(readonly=True)
    employee_unsupported_count = fields.Integer(readonly=True)
    employee_gap_percentage = fields.Float(readonly=True)
    customer_unsupported_count = fields.Integer(readonly=True)
    customer_gap_percentage = fields.Float(readonly=True)
    product_unsupported_count = fields.Integer(readonly=True)
    product_gap_percentage = fields.Float(readonly=True)
    item_coverage_complete_percentage = fields.Float(readonly=True)
    average_duration_ms = fields.Float(readonly=True)
    average_result_size_bytes = fields.Float(readonly=True)
    recommendation_code = fields.Selection([
        ("employee", "Employee Facts"),
        ("customer", "Customer Facts"),
        ("both_employee_first", "Both - Employee First"),
        ("both_customer_first", "Both - Customer First"),
        ("neither", "Neither Yet"),
    ], readonly=True)
    recommendation_reason = fields.Text(readonly=True)

    @api.model
    def default_get(self, field_names):
        values = super().default_get(field_names)
        recommendation = self.env["ab.sales.dashboard.report.telemetry"].get_fact_grain_recommendation()
        period = recommendation["measurement_period"]
        values.update({
            "measurement_period": "%s - %s" % (period["date_from"] or _("No data"), period["date_to"] or _("No data")),
            "long_range_report_count": recommendation["long_range_report_count"],
            "employee_unsupported_count": recommendation["long_range_user_unsupported_count"],
            "employee_gap_percentage": recommendation["user_demand_gap_percentage"],
            "customer_unsupported_count": recommendation["long_range_customer_unsupported_count"],
            "customer_gap_percentage": recommendation["customer_demand_gap_percentage"],
            "product_unsupported_count": recommendation["long_range_item_unsupported_count"],
            "product_gap_percentage": recommendation["item_demand_gap_percentage"],
            "item_coverage_complete_percentage": recommendation["item_coverage_complete_percentage"],
            "average_duration_ms": recommendation["average_long_range_duration_ms"],
            "average_result_size_bytes": recommendation["average_long_range_result_size_bytes"],
            "recommendation_code": recommendation["recommendation_code"],
            "recommendation_reason": recommendation["recommendation_reason"],
        })
        return values
