import hashlib
import json
import logging
import time
from datetime import date, timedelta

from odoo import api, fields, models, tools
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


REPORT_MODE_FULL = "full"
REPORT_MODE_SUMMARY = "summary"
COVERAGE_COMPLETE = "complete"
COVERAGE_PARTIAL = "partial"
COVERAGE_UNAVAILABLE = "unavailable"
SUMMARY_UNSUPPORTED_SECTIONS = ("sales_by_user", "top_items", "customer_sales")
PRODUCT_SUMMARY_UNSUPPORTED_SECTIONS = ("sales_by_user", "customer_sales")


class SalesDashboardSnapshot(models.Model):
    _name = "ab.sales.dashboard.snapshot"
    _inherit = ["ab.sales.dashboard.config.mixin"]
    _description = "Sales Dashboard Report"
    _order = "refresh_date desc, id desc"

    name = fields.Char(required=True, readonly=True, default="Sales Dashboard")
    date_from = fields.Date(required=True, readonly=True, index=True)
    date_to = fields.Date(required=True, readonly=True, index=True)
    refresh_date = fields.Datetime(default=fields.Datetime.now, readonly=True, index=True)
    store_ids = fields.Many2many("ab_store", string="Stores", readonly=True)
    store_filter_key = fields.Char(readonly=True, index=True)
    store_filter_label = fields.Char(readonly=True)
    total_sales = fields.Float(readonly=True)
    avg_daily_sales = fields.Float(readonly=True)
    prev_avg_daily_sales = fields.Float(readonly=True)
    avg_daily_growth_pct = fields.Float(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    medicine_sales = fields.Float(readonly=True)
    non_medicine_sales = fields.Float(readonly=True)
    customer_bearing_amount = fields.Float(readonly=True)
    company_part_amount = fields.Float(readonly=True)
    bearing_pct = fields.Float(readonly=True)
    total_units_sold = fields.Float(readonly=True)
    unique_products_sold = fields.Integer(readonly=True)
    total_product_sales = fields.Float(readonly=True)
    avg_products_per_invoice = fields.Float(readonly=True)
    stores_with_sales = fields.Integer(readonly=True)
    avg_products_sold_per_store = fields.Float(readonly=True)
    collection_line_ids = fields.One2many("ab.sales.dashboard.collection.line", "snapshot_id", readonly=True)
    user_line_ids = fields.One2many("ab.sales.dashboard.user.line", "snapshot_id", readonly=True)
    item_line_ids = fields.One2many("ab.sales.dashboard.item.line", "snapshot_id", readonly=True)
    invoice_line_ids = fields.One2many("ab.sales.dashboard.invoice.line", "snapshot_id", readonly=True)

    def action_refresh(self):
        self.ensure_one()
        refreshed = self.sudo()._create_snapshot(self._filters_from_record())
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": refreshed.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_archive_report(self):
        self.ensure_one()
        archive = self.create_management_report_archive()
        return {
            "type": "ir.actions.act_window",
            "res_model": "ab.sales.dashboard.report.archive",
            "res_id": archive.id,
            "view_mode": "form",
            "target": "current",
        }

    def create_management_report_archive(self):
        self.ensure_one()
        if not self.env.user.has_group("ab_sales_dashboard.group_ab_sales_dashboard_manager"):
            raise AccessError(_("Only sales dashboard managers can archive sales dashboard reports."))

        Archive = self.env["ab.sales.dashboard.report.archive"]
        filters = self._filters_from_record()
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_archive_started snapshot_id=%s date_from=%s date_to=%s store_key=%s",
            self.id,
            self.date_from,
            self.date_to,
            self.store_filter_key,
        )
        try:
            payload = self._serialize_dashboard(self, filters)
            payload_bytes = Archive._archive_payload_bytes(payload)
            Archive._validate_archive_payload_size(payload_bytes)
            serialized_ms = int((time.monotonic() - started) * 1000)
            _logger.info(
                "event=sales_dashboard_archive_serialized snapshot_id=%s payload_size_bytes=%s elapsed_ms=%s",
                self.id,
                len(payload_bytes),
                serialized_ms,
            )

            hash_started = time.monotonic()
            payload_hash = Archive._compute_archive_payload_hash(payload)
            _logger.info(
                "event=sales_dashboard_archive_hash_completed snapshot_id=%s payload_hash_prefix=%s elapsed_ms=%s",
                self.id,
                payload_hash[:12],
                int((time.monotonic() - hash_started) * 1000),
            )
            duplicate_count = Archive.sudo().search_count([("payload_hash", "=", payload_hash)])
            if duplicate_count:
                _logger.info(
                    "event=sales_dashboard_archive_duplicate_payload_detected source_snapshot_id=%s existing_archive_count=%s payload_hash_prefix=%s",
                    self.id,
                    duplicate_count,
                    payload_hash[:12],
                )

            archive_number = self.env["ir.sequence"].sudo().next_by_code("ab.sales.dashboard.report.archive") or "/"
            archive = Archive.with_context(ab_sales_dashboard_allow_archive_create=True).create({
                "name": archive_number,
                "archive_number": archive_number,
                "snapshot_id": self.id,
                "date_from": self.date_from,
                "date_to": self.date_to,
                "store_filter_key": self.store_filter_key,
                "store_filter_label": self.store_filter_label,
                "store_ids": [(6, 0, self.store_ids.ids)],
                "archived_at": fields.Datetime.now(),
                "archived_by": self.env.user.id,
                "state": "archived",
                "payload_json": payload,
                "payload_hash": payload_hash,
                "payload_size_bytes": len(payload_bytes),
                "source_snapshot_write_date": self.write_date,
            })
            _logger.info(
                "event=sales_dashboard_archive_created snapshot_id=%s archive_id=%s archive_number=%s payload_size_bytes=%s payload_hash_prefix=%s elapsed_ms=%s",
                self.id,
                archive.id,
                archive.archive_number,
                len(payload_bytes),
                payload_hash[:12],
                int((time.monotonic() - started) * 1000),
            )
            return archive
        except Exception:
            _logger.exception(
                "event=sales_dashboard_archive_failed snapshot_id=%s elapsed_ms=%s",
                self.id,
                int((time.monotonic() - started) * 1000),
            )
            raise

    @api.model
    def get_dashboard_data(self, filters=None):
        started = time.monotonic()
        filters = self._normalize_filters(
            filters,
            max_days=self._summary_max_days(),
            limit_message=_("The selected reporting period exceeds the maximum allowed summary range of %s days."),
        )
        requested_days = self._requested_days(filters)
        report_mode = REPORT_MODE_SUMMARY if requested_days > self._dashboard_max_days() else REPORT_MODE_FULL
        _logger.info(
            "event=sales_dashboard_report_mode_selected mode=%s date_from=%s date_to=%s requested_days=%s store_id=%s",
            report_mode,
            filters["date_from"],
            filters["date_to"],
            requested_days,
            filters["store_id"],
        )
        if report_mode == REPORT_MODE_SUMMARY:
            payload = self._build_dashboard_from_daily_facts(filters, allow_partial=True)
            result = self._serialize_dashboard_payload(payload, filters, source="daily_facts")
        else:
            snapshot = self._find_latest_full_snapshot(filters)
            if snapshot:
                result = self._serialize_dashboard(snapshot, filters)
            else:
                derived_payload = self._dashboard_payload_from_daily_facts(filters)
                if derived_payload:
                    result = self._serialize_dashboard_payload(derived_payload, filters, source="odoo_daily_facts")
                else:
                    snapshot = self._find_latest_snapshot(filters)
                    result = self._serialize_dashboard(snapshot, filters, summary_only=bool(snapshot))
        self._record_top_level_telemetry(result, filters, started, report_mode=report_mode)
        return result

    @api.model
    def refresh_dashboard_data(self, filters=None):
        try:
            filters = self._normalize_filters(filters, require_dates=True)
            self._validate_dashboard_range(filters)
        except UserError:
            normalized = dict(filters or {})
            _logger.info(
                "event=sales_dashboard_long_refresh_rejected date_from=%s date_to=%s store_id=%s max_days=%s",
                normalized.get("date_from"),
                normalized.get("date_to"),
                normalized.get("store_id") or 0,
                self._dashboard_max_days(),
            )
            raise
        store_count = self._refresh_store_count(filters)
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_refresh_started date_from=%s date_to=%s store_id=%s store_count=%s",
            filters["date_from"],
            filters["date_to"],
            filters["store_id"],
            store_count,
        )
        try:
            with self._sales_dashboard_refresh_lock():
                # The dashboard button is a fetch/update action: it always reads the
                # selected period and branch scope from E-Plus, then upserts the report.
                snapshot = self.sudo()._create_snapshot(filters)
            duration_ms = int((time.monotonic() - started) * 1000)
            _logger.info(
                "event=sales_dashboard_refresh_completed date_from=%s date_to=%s store_id=%s store_count=%s duration_ms=%s status=success",
                filters["date_from"],
                filters["date_to"],
                filters["store_id"],
                store_count,
                duration_ms,
            )
            result = self._serialize_dashboard(snapshot, filters)
            self._record_top_level_telemetry(result, filters, started, event_type="dashboard_refresh")
            return result
        except UserError:
            duration_ms = int((time.monotonic() - started) * 1000)
            _logger.info(
                "event=sales_dashboard_refresh_failed date_from=%s date_to=%s store_id=%s store_count=%s duration_ms=%s status=user_error",
                filters["date_from"],
                filters["date_to"],
                filters["store_id"],
                store_count,
                duration_ms,
            )
            self._record_top_level_telemetry(None, filters, started, event_type="dashboard_refresh")
            raise
        except Exception:
            duration_ms = int((time.monotonic() - started) * 1000)
            _logger.exception(
                "event=sales_dashboard_refresh_failed date_from=%s date_to=%s store_id=%s store_count=%s duration_ms=%s status=failed",
                filters["date_from"],
                filters["date_to"],
                filters["store_id"],
                store_count,
                duration_ms,
            )
            self._record_top_level_telemetry(None, filters, started, event_type="dashboard_refresh")
            raise

    @api.model
    def _record_top_level_telemetry(self, result, filters, started, event_type=None, report_mode=None):
        report_meta = (result or {}).get("report_meta") or {}
        report_mode = report_mode or report_meta.get("mode") or REPORT_MODE_FULL
        event_type = event_type or ("summary_read" if report_mode == REPORT_MODE_SUMMARY else "dashboard_read")
        source = (result or {}).get("data_source")
        self.env["ab.sales.dashboard.report.telemetry"].record_operation(
            event_type,
            report_mode,
            filters=filters,
            duration_ms=int((time.monotonic() - started) * 1000),
            result=result,
            report_meta=report_meta,
            selected_store_count=report_meta.get("store_count") or self._refresh_store_count(filters),
            snapshot_used=source == "snapshot",
            daily_fact_used=source in ("daily_facts", "odoo_daily_facts"),
            item_fact_used=report_mode == REPORT_MODE_SUMMARY and "top_items" not in set(report_meta.get("unsupported_sections") or []),
        )

    @api.model
    def _create_snapshot(self, filters):
        stores = self._stores_from_filters(filters)
        if filters["store_id"] and not stores:
            raise UserError(_("The selected store was not found."))
        if any(not store.eplus_serial for store in stores):
            missing = ", ".join(stores.filtered(lambda store: not store.eplus_serial).mapped("display_name"))
            raise UserError(_("These stores have no E-Plus serial: %s") % missing)

        store_eplus_ids = [int(store.eplus_serial) for store in stores]
        refresh_data = self.env["ab.sales.dashboard.service"].fetch_refresh_data(
            filters["date_from"],
            fields.Date.add(filters["date_to"], days=1),
            store_eplus_ids=store_eplus_ids,
        )
        payload = refresh_data["dashboard"]
        daily_payload = refresh_data["daily_store_facts"]
        self._upsert_daily_facts(filters, daily_payload)
        return self._create_snapshot_from_payload(filters, payload)

    @api.model
    def _create_snapshot_from_payload(self, filters, payload):
        stores = self._stores_from_filters(filters)
        products_by_serial = self._products_by_serial([row.get("itm_id") for row in payload["item_lines"]])
        store_key = self._store_filter_key(stores)
        parent_vals = {
            "name": self._snapshot_name(filters, stores),
            "date_from": filters["date_from"],
            "date_to": filters["date_to"],
            "refresh_date": fields.Datetime.now(),
            "store_ids": [(6, 0, stores.ids)],
            "store_filter_key": store_key,
            "store_filter_label": self._store_filter_label(stores),
            "total_sales": payload["total_sales"],
            "avg_daily_sales": payload["avg_daily_sales"],
            "prev_avg_daily_sales": payload["prev_avg_daily_sales"],
            "avg_daily_growth_pct": payload["avg_daily_growth_pct"],
            "invoice_count": payload["invoice_count"],
            "medicine_sales": payload["medicine_sales"],
            "non_medicine_sales": payload["non_medicine_sales"],
            "customer_bearing_amount": payload["customer_bearing_amount"],
            "company_part_amount": payload["company_part_amount"],
            "bearing_pct": payload["bearing_pct"],
            "total_units_sold": payload.get("total_units_sold", 0.0),
            "unique_products_sold": payload.get("unique_products_sold", 0),
            "total_product_sales": payload.get("total_product_sales", 0.0),
            "avg_products_per_invoice": payload.get("avg_products_per_invoice", 0.0),
            "stores_with_sales": payload.get("stores_with_sales", 0),
            "avg_products_sold_per_store": payload.get("avg_products_sold_per_store", 0.0),
        }
        child_rows = {
            "collection": self._collection_line_values(payload["collection_lines"]),
            "user": self._user_line_values(payload["user_lines"]),
            "item": self._item_line_values(payload["item_lines"], products_by_serial),
            "invoice": self._invoice_line_values(payload["invoice_lines"]),
        }
        self._validate_snapshot_child_rows(child_rows, filters)
        snapshot = self._persist_snapshot_parent(filters, store_key, parent_vals)
        self._persist_snapshot_children(snapshot, child_rows, filters)
        return snapshot

    @api.model
    def _persist_snapshot_parent(self, filters, store_key, vals):
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_snapshot_parent_persistence_started date_from=%s date_to=%s store_id=%s",
            filters["date_from"],
            filters["date_to"],
            filters["store_id"],
        )
        existing = self.sudo().search([
            ("date_from", "=", filters["date_from"]),
            ("date_to", "=", filters["date_to"]),
            ("store_filter_key", "=", store_key),
        ], limit=1)
        if existing:
            existing.write(vals)
            operation = "write"
            snapshot = existing
        else:
            snapshot = self.create(vals)
            operation = "create"
        _logger.info(
            "event=sales_dashboard_snapshot_parent_persistence_completed operation=%s duration_ms=%s snapshot_id=%s date_from=%s date_to=%s store_id=%s",
            operation,
            int((time.monotonic() - started) * 1000),
            snapshot.id,
            filters["date_from"],
            filters["date_to"],
            filters["store_id"],
        )
        return snapshot

    @api.model
    def _validate_snapshot_child_rows(self, child_rows, filters):
        max_rows = self._max_snapshot_child_rows()
        for child_type, rows in child_rows.items():
            if len(rows) > max_rows:
                _logger.warning(
                    "event=sales_dashboard_snapshot_child_limit_exceeded child_type=%s row_count=%s max_rows=%s date_from=%s date_to=%s store_id=%s",
                    child_type,
                    len(rows),
                    max_rows,
                    filters["date_from"],
                    filters["date_to"],
                    filters["store_id"],
                )
                raise UserError(_("The snapshot %(child_type)s line count exceeds the configured safety limit of %(limit)s rows.") % {
                    "child_type": child_type,
                    "limit": max_rows,
                })
        return True

    @api.model
    def _snapshot_child_mappings(self):
        return {
            "collection": {
                "model": "ab.sales.dashboard.collection.line",
                "table": "ab_sales_dashboard_collection_line",
                "relation_field": "collection_line_ids",
                "columns": ["snapshot_id", "category", "invoice_count", "total_sales", "pct_of_total"],
            },
            "user": {
                "model": "ab.sales.dashboard.user.line",
                "table": "ab_sales_dashboard_user_line",
                "relation_field": "user_line_ids",
                "columns": ["snapshot_id", "employee_eplus_id", "employee_name", "invoice_count", "total_sales", "pct_of_total"],
            },
            "item": {
                "model": "ab.sales.dashboard.item.line",
                "table": "ab_sales_dashboard_item_line",
                "relation_field": "item_line_ids",
                "columns": ["snapshot_id", "eplus_item_id", "eplus_item_code", "product_id", "item_name", "sale_times", "sold_qty", "total_sales", "current_balance"],
            },
            "invoice": {
                "model": "ab.sales.dashboard.invoice.line",
                "table": "ab_sales_dashboard_invoice_line",
                "relation_field": "invoice_line_ids",
                "columns": ["snapshot_id", "invoice_no", "invoice_date", "customer_name", "invoice_total", "item_count", "items_summary"],
            },
        }

    @api.model
    def _persist_snapshot_children(self, snapshot, child_rows, filters):
        started = time.monotonic()
        mappings = self._snapshot_child_mappings()
        for child_type, rows in child_rows.items():
            mapping = mappings[child_type]
            self._delete_snapshot_child_rows(snapshot, child_type, mapping)
            self._insert_snapshot_child_rows(snapshot, child_type, mapping, rows)
        self._invalidate_snapshot_child_cache(snapshot, mappings)
        _logger.info(
            "event=sales_dashboard_snapshot_child_persistence_completed duration_ms=%s snapshot_id=%s row_count=%s",
            int((time.monotonic() - started) * 1000),
            snapshot.id,
            sum(len(rows) for rows in child_rows.values()),
        )

    @api.model
    def _delete_snapshot_child_rows(self, snapshot, child_type, mapping):
        started = time.monotonic()
        self.env.cr.execute(
            f"DELETE FROM {mapping['table']} WHERE snapshot_id = %s",
            [snapshot.id],
        )
        deleted_count = self.env.cr.rowcount
        _logger.info(
            "event=sales_dashboard_snapshot_child_delete_completed duration_ms=%s snapshot_id=%s child_type=%s deleted_count=%s",
            int((time.monotonic() - started) * 1000),
            snapshot.id,
            child_type,
            deleted_count,
        )
        return deleted_count

    @api.model
    def _snapshot_child_insert_sql(self, mapping, row_count):
        columns = list(mapping["columns"]) + ["create_uid", "create_date", "write_uid", "write_date"]
        placeholders = ", ".join(
            ["(" + ", ".join(["%s"] * len(columns)) + ")"] * row_count
        )
        return "INSERT INTO %s (%s) VALUES %s" % (
            mapping["table"],
            ", ".join(columns),
            placeholders,
        )

    @api.model
    def _insert_snapshot_child_rows(self, snapshot, child_type, mapping, rows):
        batch_size = self._query_batch_size()
        now = fields.Datetime.now()
        total_count = 0
        columns = list(mapping["columns"])
        for batch_number, offset in enumerate(range(0, len(rows), batch_size), start=1):
            batch = rows[offset:offset + batch_size]
            if not batch:
                continue
            sql = self._snapshot_child_insert_sql(mapping, len(batch))
            params = []
            for row in batch:
                values = dict(row, snapshot_id=snapshot.id)
                params.extend(self._sql_value(values.get(column)) for column in columns)
                params.extend([self.env.uid, now, self.env.uid, now])
            started = time.monotonic()
            self.env.cr.execute(sql, params)
            total_count += len(batch)
            _logger.info(
                "event=sales_dashboard_snapshot_child_batch_completed duration_ms=%s snapshot_id=%s child_type=%s batch_number=%s batch_size=%s row_count=%s",
                int((time.monotonic() - started) * 1000),
                snapshot.id,
                child_type,
                batch_number,
                batch_size,
                len(batch),
            )
        return total_count

    @api.model
    def _sql_value(self, value):
        return None if value is False else value

    @api.model
    def _invalidate_snapshot_child_cache(self, snapshot, mappings):
        started = time.monotonic()
        for mapping in mappings.values():
            self.env[mapping["model"]].invalidate_model()
        snapshot.invalidate_recordset([mapping["relation_field"] for mapping in mappings.values()])
        _logger.info(
            "event=sales_dashboard_snapshot_cache_invalidation_completed duration_ms=%s snapshot_id=%s",
            int((time.monotonic() - started) * 1000),
            snapshot.id,
        )

    @api.model
    def _normalize_filters(self, filters, require_dates=False, max_days=None, limit_message=None):
        filters = dict(filters or {})
        today = fields.Date.context_today(self)
        first_day = date(today.year, today.month, 1)
        if require_dates and (not filters.get("date_from") or not filters.get("date_to")):
            missing_label = _("Date From") if not filters.get("date_from") else _("Date To")
            raise UserError(_("%s is required.") % missing_label)
        date_from = self._coerce_dashboard_date(filters.get("date_from") or first_day, _("Date From"))
        date_to = self._coerce_dashboard_date(filters.get("date_to") or today, _("Date To"))
        self._validate_dashboard_date_range(date_from, date_to, max_days=max_days, limit_message=limit_message)
        store_id = int(filters.get("store_id") or 0)
        return {"date_from": date_from, "date_to": date_to, "store_id": store_id}

    @api.model
    def _validate_dashboard_range(self, filters):
        return self._validate_dashboard_date_range(filters.get("date_from"), filters.get("date_to"))

    @api.model
    def _requested_days(self, filters):
        return max((fields.Date.to_date(filters["date_to"]) - fields.Date.to_date(filters["date_from"])).days + 1, 1)

    @api.model
    def _refresh_store_count(self, filters):
        if filters.get("store_id"):
            return 1
        return self.env["ab_store"].sudo().search_count([
            ("active", "=", True),
            ("allow_sale", "=", True),
            ("eplus_serial", "!=", False),
        ])

    @api.model
    def _stores_from_filters(self, filters):
        if not filters["store_id"]:
            return self.env["ab_store"]
        return self.env["ab_store"].sudo().browse(filters["store_id"]).exists()

    @api.model
    def _fact_scope_stores(self, filters):
        if filters["store_id"]:
            return self._stores_from_filters(filters)
        return self.env["ab_store"].sudo().search([
            ("active", "=", True),
            ("allow_sale", "=", True),
            ("eplus_serial", "!=", False),
        ])

    @api.model
    def _store_filter_key(self, stores):
        if not stores:
            return "all"
        return ",".join(str(store.eplus_serial) for store in stores.sorted("eplus_serial"))

    @api.model
    def _store_filter_label(self, stores):
        if not stores:
            return _("All Stores")
        return ", ".join(stores.mapped("display_name"))

    @api.model
    def _snapshot_name(self, filters, stores):
        return _("%(from)s to %(to)s - %(stores)s") % {
            "from": filters["date_from"],
            "to": filters["date_to"],
            "stores": self._store_filter_label(stores),
        }

    def _filters_from_record(self):
        self.ensure_one()
        return {
            "date_from": self.date_from,
            "date_to": self.date_to,
            "store_id": self.store_ids[:1].id if len(self.store_ids) == 1 else 0,
        }

    @api.model
    def _find_latest_snapshot(self, filters):
        stores = self._stores_from_filters(filters)
        return self.sudo().search([
            ("date_from", "=", filters["date_from"]),
            ("date_to", "=", filters["date_to"]),
            ("store_filter_key", "=", self._store_filter_key(stores)),
        ], limit=1)

    @api.model
    def _find_latest_full_snapshot(self, filters):
        stores = self._stores_from_filters(filters)
        snapshots = self.sudo().search([
            ("date_from", "=", filters["date_from"]),
            ("date_to", "=", filters["date_to"]),
            ("store_filter_key", "=", self._store_filter_key(stores)),
        ], limit=5)
        return snapshots.filtered(lambda snapshot: snapshot._has_full_report())[:1]

    def _has_full_report(self):
        self.ensure_one()
        if not self.invoice_count and not self.total_sales:
            return True
        return bool(self.user_line_ids and self.item_line_ids and self.invoice_line_ids)

    @api.model
    def _available_stores_payload(self):
        stores = self.env["ab_store"].sudo().search([
            ("active", "=", True),
            ("allow_sale", "=", True),
            ("eplus_serial", "!=", False),
        ], order="name")
        return [{"id": store.id, "name": store.display_name} for store in stores]

    @api.model
    def _serialize_dashboard(self, snapshot, filters, summary_only=False):
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_serialization_started date_from=%s date_to=%s store_id=%s has_snapshot=%s",
            filters.get("date_from"),
            filters.get("date_to"),
            filters.get("store_id"),
            bool(snapshot),
        )
        data = {
            "date_from": fields.Date.to_string(filters["date_from"]),
            "date_to": fields.Date.to_string(filters["date_to"]),
            "store_id": filters["store_id"],
            "stores": self._available_stores_payload(),
            "has_snapshot": bool(snapshot),
            "data_source": "snapshot" if snapshot else "none",
            "summary_only": bool(summary_only),
            "report_meta": self._full_report_meta(filters, source="snapshot" if snapshot else "none"),
        }
        if not snapshot:
            data.update({
                "total_sales": 0.0,
                "avg_daily_sales": 0.0,
                "prev_avg_daily_sales": 0.0,
                "avg_daily_growth_pct": 0.0,
                "invoice_count": 0,
                "medicine_sales": 0.0,
                "non_medicine_sales": 0.0,
                "customer_bearing_amount": 0.0,
                "company_part_amount": 0.0,
                "bearing_pct": 0.0,
                "total_units_sold": 0.0,
                "unique_products_sold": 0,
                "total_product_sales": 0.0,
                "avg_products_per_invoice": 0.0,
                "stores_with_sales": 0,
                "avg_products_sold_per_store": 0.0,
                "store_filter_label": _("All Stores"),
                "refresh_date": False,
                "collection_lines": [],
                "user_lines": [],
                "item_lines": [],
                "invoice_lines": [],
            })
            self._log_dashboard_serialization(started, filters, data)
            return data

        data.update({
            "snapshot_id": snapshot.id,
            "total_sales": snapshot.total_sales,
            "avg_daily_sales": snapshot.avg_daily_sales,
            "prev_avg_daily_sales": snapshot.prev_avg_daily_sales,
            "avg_daily_growth_pct": snapshot.avg_daily_growth_pct,
            "invoice_count": snapshot.invoice_count,
            "medicine_sales": snapshot.medicine_sales,
            "non_medicine_sales": snapshot.non_medicine_sales,
            "customer_bearing_amount": snapshot.customer_bearing_amount,
            "company_part_amount": snapshot.company_part_amount,
            "bearing_pct": snapshot.bearing_pct,
            "total_units_sold": snapshot.total_units_sold,
            "unique_products_sold": snapshot.unique_products_sold,
            "total_product_sales": snapshot.total_product_sales,
            "avg_products_per_invoice": snapshot.avg_products_per_invoice,
            "stores_with_sales": snapshot.stores_with_sales,
            "avg_products_sold_per_store": snapshot.avg_products_sold_per_store,
            "store_filter_label": snapshot.store_filter_label,
            "refresh_date": fields.Datetime.to_string(snapshot.refresh_date) if snapshot.refresh_date else False,
            "collection_lines": [line._as_dashboard_dict() for line in snapshot.collection_line_ids],
            "user_lines": [line._as_dashboard_dict() for line in snapshot.user_line_ids],
            "item_lines": [line._as_dashboard_dict() for line in snapshot.item_line_ids],
            "invoice_lines": [line._as_dashboard_dict() for line in snapshot.invoice_line_ids],
        })
        self._log_dashboard_serialization(started, filters, data)
        return data

    @api.model
    def _serialize_dashboard_payload(self, payload, filters, source=False):
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_serialization_started date_from=%s date_to=%s store_id=%s has_snapshot=%s source=%s",
            filters.get("date_from"),
            filters.get("date_to"),
            filters.get("store_id"),
            True,
            source or "odoo",
        )
        data = {
            "date_from": fields.Date.to_string(filters["date_from"]),
            "date_to": fields.Date.to_string(filters["date_to"]),
            "store_id": filters["store_id"],
            "stores": self._available_stores_payload(),
            "has_snapshot": payload.get("has_snapshot", True),
            "snapshot_id": False,
            "data_source": source or "odoo",
            "summary_only": True,
            "total_sales": payload["total_sales"],
            "avg_daily_sales": payload["avg_daily_sales"],
            "prev_avg_daily_sales": payload["prev_avg_daily_sales"],
            "avg_daily_growth_pct": payload["avg_daily_growth_pct"],
            "invoice_count": payload["invoice_count"],
            "medicine_sales": payload["medicine_sales"],
            "non_medicine_sales": payload["non_medicine_sales"],
            "customer_bearing_amount": payload["customer_bearing_amount"],
            "company_part_amount": payload["company_part_amount"],
            "bearing_pct": payload["bearing_pct"],
            "total_units_sold": payload.get("total_units_sold", 0.0),
            "unique_products_sold": payload.get("unique_products_sold", 0),
            "total_product_sales": payload.get("total_product_sales", 0.0),
            "avg_products_per_invoice": payload.get("avg_products_per_invoice", 0.0),
            "stores_with_sales": payload.get("stores_with_sales", 0),
            "avg_products_sold_per_store": payload.get("avg_products_sold_per_store", 0.0),
            "store_filter_label": self._store_filter_label(self._stores_from_filters(filters)),
            "refresh_date": False,
            "collection_lines": payload["collection_lines"],
            "user_lines": payload.get("user_lines", []),
            "item_lines": payload.get("item_lines", []),
            "invoice_lines": payload.get("invoice_lines", []),
            "report_meta": payload.get("report_meta") or self._summary_report_meta(filters),
        }
        self._log_dashboard_serialization(started, filters, data)
        return data

    @api.model
    def _full_report_meta(self, filters, source="bconnect_refresh"):
        requested_days = self._requested_days(filters)
        store_count = self._refresh_store_count(filters)
        expected_store_days = requested_days * store_count
        return {
            "mode": REPORT_MODE_FULL,
            "coverage_state": COVERAGE_COMPLETE,
            "date_from": fields.Date.to_string(filters["date_from"]),
            "date_to": fields.Date.to_string(filters["date_to"]),
            "requested_days": requested_days,
            "covered_days": requested_days,
            "missing_days": 0,
            "store_count": store_count,
            "covered_store_days": expected_store_days,
            "expected_store_days": expected_store_days,
            "missing_store_days": 0,
            "coverage_pct": 100.0 if expected_store_days else 0.0,
            "unsupported_sections": [],
            "source": source,
        }

    @api.model
    def _summary_report_meta(self, filters, coverage=None, previous_coverage=None, item_coverage=None, unsupported_sections=None, unavailable_comparisons=None):
        coverage = coverage or {}
        previous_coverage = previous_coverage or {}
        item_coverage = item_coverage or {}
        return {
            "mode": REPORT_MODE_SUMMARY,
            "coverage_state": coverage.get("coverage_state", COVERAGE_UNAVAILABLE),
            "date_from": fields.Date.to_string(filters["date_from"]),
            "date_to": fields.Date.to_string(filters["date_to"]),
            "requested_days": coverage.get("requested_days", self._requested_days(filters)),
            "covered_days": coverage.get("covered_days", 0),
            "missing_days": coverage.get("missing_days", self._requested_days(filters)),
            "store_count": coverage.get("store_count", 0),
            "covered_store_days": coverage.get("covered_store_days", 0),
            "expected_store_days": coverage.get("expected_store_days", 0),
            "missing_store_days": coverage.get("missing_store_days", 0),
            "coverage_pct": coverage.get("coverage_pct", 0.0),
            "previous_coverage_state": previous_coverage.get("coverage_state", COVERAGE_UNAVAILABLE),
            "previous_covered_store_days": previous_coverage.get("covered_store_days", 0),
            "previous_expected_store_days": previous_coverage.get("expected_store_days", 0),
            "item_coverage_state": item_coverage.get("coverage_state", COVERAGE_UNAVAILABLE),
            "item_covered_store_days": item_coverage.get("covered_store_days", 0),
            "item_expected_store_days": item_coverage.get("expected_store_days", 0),
            "item_missing_store_days": item_coverage.get("missing_store_days", item_coverage.get("expected_store_days", 0)),
            "item_coverage_pct": item_coverage.get("coverage_pct", 0.0),
            "unsupported_sections": list(unsupported_sections or SUMMARY_UNSUPPORTED_SECTIONS),
            "unavailable_comparisons": list(unavailable_comparisons or []),
            "source": "daily_facts",
        }

    @api.model
    def _log_dashboard_serialization(self, started, filters, data):
        _logger.info(
            "event=sales_dashboard_serialization_completed duration_ms=%s date_from=%s date_to=%s store_id=%s collection_count=%s user_count=%s item_count=%s invoice_count=%s summary_only=%s",
            int((time.monotonic() - started) * 1000),
            filters.get("date_from"),
            filters.get("date_to"),
            filters.get("store_id"),
            len(data.get("collection_lines") or []),
            len(data.get("user_lines") or []),
            len(data.get("item_lines") or []),
            len(data.get("invoice_lines") or []),
            data.get("summary_only"),
        )

    @api.model
    def _date_range(self, date_from, date_to):
        current = fields.Date.to_date(date_from)
        end = fields.Date.to_date(date_to)
        while current <= end:
            yield current
            current += timedelta(days=1)

    @api.model
    def _daily_fact_key(self, report_date, store_eplus_id):
        return (fields.Date.to_date(report_date), int(store_eplus_id or 0))

    @api.model
    def _store_by_eplus_id(self, stores):
        return {int(store.eplus_serial): store for store in stores if store.eplus_serial}

    @api.model
    def _upsert_daily_facts(self, filters, daily_payload, stores=None):
        stores = stores if stores is not None else self._fact_scope_stores(filters)
        if not stores:
            return
        store_by_eplus = self._store_by_eplus_id(stores)
        categories = [key for key, _label in self.env["ab.sales.dashboard.daily.collection.fact"]._fields["category"].selection]
        report_dates = list(self._date_range(filters["date_from"], filters["date_to"]))
        coverage_rows = self._build_sync_coverage_rows(report_dates, stores)
        self._validate_daily_coverage_row_count(coverage_rows, filters, len(stores))

        store_fact_vals = self._normalize_store_fact_rows(daily_payload, store_by_eplus, report_dates)
        collection_fact_vals = self._normalize_collection_fact_rows(daily_payload, store_by_eplus, report_dates, categories)
        item_fact_vals = self._normalize_item_fact_rows(daily_payload, store_by_eplus, report_dates)
        actual_fact_count = len(store_fact_vals) + len(collection_fact_vals)
        max_fact_rows = self._max_daily_fact_rows()
        if actual_fact_count > max_fact_rows:
            _logger.warning(
                "event=sales_dashboard_daily_fact_persistence_limit_exceeded actual_rows=%s max_rows=%s date_from=%s date_to=%s store_count=%s",
                actual_fact_count,
                max_fact_rows,
                filters["date_from"],
                filters["date_to"],
                len(stores),
            )
            raise UserError(_("The daily fact persistence scope exceeds the configured safety limit of %s rows.") % max_fact_rows)
        max_item_rows = self._max_daily_item_fact_rows()
        if len(item_fact_vals) > max_item_rows:
            _logger.warning(
                "event=sales_dashboard_daily_item_fact_limit_exceeded actual_rows=%s max_rows=%s date_from=%s date_to=%s store_count=%s",
                len(item_fact_vals),
                max_item_rows,
                filters["date_from"],
                filters["date_to"],
                len(stores),
            )
            raise UserError(_("The daily item fact persistence scope exceeds the configured safety limit of %s rows.") % max_item_rows)

        store_eplus_ids = sorted(store_by_eplus)
        self._replace_fact_scope(
            "ab.sales.dashboard.daily.store.fact",
            list(store_fact_vals.values()),
            filters,
            store_eplus_ids,
        )
        self._replace_fact_scope(
            "ab.sales.dashboard.daily.collection.fact",
            list(collection_fact_vals.values()),
            filters,
            store_eplus_ids,
        )
        if "item_facts" in daily_payload:
            self._replace_fact_scope(
                "ab.sales.dashboard.daily.item.fact",
                list(item_fact_vals.values()),
                filters,
                store_eplus_ids,
            )
        self._persist_sync_coverage(coverage_rows, filters, len(stores))
        if "item_facts" in daily_payload:
            self._persist_fact_coverage(
                self._build_fact_coverage_rows(report_dates, stores, "item"),
                filters,
                len(stores),
                "item",
            )
        self._invalidate_daily_reporting_models()

    @api.model
    def _normalize_store_fact_rows(self, daily_payload, store_by_eplus, report_dates):
        allowed_dates = set(report_dates)
        rows_by_key = {}
        for row in daily_payload.get("store_facts", []):
            report_date = fields.Date.to_date(row.get("report_date"))
            store_eplus_id = int(row.get("store_eplus_id") or 0)
            store = store_by_eplus.get(store_eplus_id)
            if not store or report_date not in allowed_dates:
                continue
            key = self._daily_fact_key(report_date, store_eplus_id)
            data = rows_by_key.setdefault(key, {
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": store_eplus_id,
                "total_sales": 0.0,
                "invoice_count": 0,
                "medicine_sales": 0.0,
                "non_medicine_sales": 0.0,
                "customer_bearing_amount": 0.0,
                "company_part_amount": 0.0,
                "contract_net_amount": 0.0,
            })
            data["total_sales"] += float(row.get("total_sales") or 0.0)
            data["invoice_count"] += int(row.get("invoice_count") or 0)
            data["medicine_sales"] += float(row.get("medicine_sales") or 0.0)
            data["non_medicine_sales"] += float(row.get("non_medicine_sales") or 0.0)
            data["customer_bearing_amount"] += float(row.get("customer_bearing_amount") or 0.0)
            data["company_part_amount"] += float(row.get("company_part_amount") or 0.0)
            data["contract_net_amount"] += float(row.get("contract_net_amount") or 0.0)
        return rows_by_key

    @api.model
    def _normalize_collection_fact_rows(self, daily_payload, store_by_eplus, report_dates, categories):
        allowed_dates = set(report_dates)
        allowed_categories = set(categories)
        rows_by_key = {}
        for row in daily_payload.get("collection_facts", []):
            report_date = fields.Date.to_date(row.get("report_date"))
            store_eplus_id = int(row.get("store_eplus_id") or 0)
            category = row.get("category") or "cash"
            store = store_by_eplus.get(store_eplus_id)
            if not store or report_date not in allowed_dates or category not in allowed_categories:
                continue
            key = (report_date, store_eplus_id, category)
            data = rows_by_key.setdefault(key, {
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": store_eplus_id,
                "category": category,
                "invoice_count": 0,
                "total_sales": 0.0,
            })
            data["invoice_count"] += int(row.get("invoice_count") or 0)
            data["total_sales"] += float(row.get("total_sales") or 0.0)
        return rows_by_key

    @api.model
    def _normalize_item_fact_rows(self, daily_payload, store_by_eplus, report_dates):
        allowed_dates = set(report_dates)
        rows_by_key = {}
        raw_rows = daily_payload.get("item_facts", [])
        products_by_serial = self._products_by_serial([row.get("item_eplus_id") for row in raw_rows])
        synced_at = fields.Datetime.now()
        for row in raw_rows:
            report_date = fields.Date.to_date(row.get("report_date"))
            store_eplus_id = int(row.get("store_eplus_id") or 0)
            item_eplus_id = int(row.get("item_eplus_id") or 0)
            item_type = row.get("item_type") or "medicine"
            store = store_by_eplus.get(store_eplus_id)
            if not store or not item_eplus_id or report_date not in allowed_dates:
                continue
            if item_type not in ("medicine", "non_medicine"):
                item_type = "medicine"
            product = products_by_serial.get(item_eplus_id)
            key = (report_date, store_eplus_id, item_eplus_id)
            data = rows_by_key.setdefault(key, {
                "report_date": report_date,
                "store_id": store.id,
                "store_eplus_id": store_eplus_id,
                "item_eplus_id": item_eplus_id,
                "item_code": row.get("item_code") or "",
                "product_id": product.id if product else False,
                "item_name": product.display_name if product else (row.get("item_code") or str(item_eplus_id)),
                "item_type": item_type,
                "sold_qty": 0.0,
                "sales_amount": 0.0,
                "invoice_count": 0,
                "sale_times": 0,
                "synced_at": synced_at,
            })
            data["sold_qty"] += float(row.get("sold_qty") or 0.0)
            data["sales_amount"] += float(row.get("sales_amount") or 0.0)
            data["invoice_count"] += int(row.get("invoice_count") or 0)
            data["sale_times"] += int(row.get("sale_times") or 0)
        return rows_by_key

    @api.model
    def _build_sync_coverage_rows(self, report_dates, stores):
        started = time.monotonic()
        rows = []
        synced_at = fields.Datetime.now()
        for report_date in report_dates:
            for store in stores:
                if not store.eplus_serial:
                    continue
                rows.append({
                    "report_date": report_date,
                    "store_id": store.id,
                    "store_eplus_id": int(store.eplus_serial),
                    "sync_state": "synced",
                    "synced_at": synced_at,
                })
        _logger.info(
            "event=sales_dashboard_coverage_build_completed duration_ms=%s coverage_count=%s store_count=%s",
            int((time.monotonic() - started) * 1000),
            len(rows),
            len(stores),
        )
        return rows

    @api.model
    def _build_fact_coverage_rows(self, report_dates, stores, fact_type):
        started = time.monotonic()
        rows = []
        synced_at = fields.Datetime.now()
        for report_date in report_dates:
            for store in stores:
                if not store.eplus_serial:
                    continue
                rows.append({
                    "report_date": report_date,
                    "store_id": store.id,
                    "store_eplus_id": int(store.eplus_serial),
                    "fact_type": fact_type,
                    "sync_state": "synced",
                    "synced_at": synced_at,
                })
        _logger.info(
            "event=sales_dashboard_item_coverage_build_completed duration_ms=%s coverage_count=%s store_count=%s fact_type=%s",
            int((time.monotonic() - started) * 1000),
            len(rows),
            len(stores),
            fact_type,
        )
        return rows

    @api.model
    def _validate_daily_coverage_row_count(self, coverage_rows, filters, store_count):
        max_rows = self._max_daily_coverage_rows()
        if len(coverage_rows) > max_rows:
            _logger.warning(
                "event=sales_dashboard_coverage_limit_exceeded coverage_count=%s max_rows=%s date_from=%s date_to=%s store_count=%s",
                len(coverage_rows),
                max_rows,
                filters["date_from"],
                filters["date_to"],
                store_count,
            )
            raise UserError(_("The daily sync coverage scope exceeds the configured safety limit of %s rows.") % max_rows)
        return True

    @api.model
    def _daily_fact_persistence_mappings(self):
        return {
            "ab.sales.dashboard.daily.store.fact": {
                "table": "ab_sales_dashboard_daily_store_fact",
                "columns": [
                    "report_date",
                    "store_id",
                    "store_eplus_id",
                    "total_sales",
                    "invoice_count",
                    "medicine_sales",
                    "non_medicine_sales",
                    "customer_bearing_amount",
                    "company_part_amount",
                    "contract_net_amount",
                ],
                "conflict": ["report_date", "store_eplus_id"],
                "update": [
                    "store_id",
                    "total_sales",
                    "invoice_count",
                    "medicine_sales",
                    "non_medicine_sales",
                    "customer_bearing_amount",
                    "company_part_amount",
                    "contract_net_amount",
                ],
            },
            "ab.sales.dashboard.daily.collection.fact": {
                "table": "ab_sales_dashboard_daily_collection_fact",
                "columns": [
                    "report_date",
                    "store_id",
                    "store_eplus_id",
                    "category",
                    "invoice_count",
                    "total_sales",
                ],
                "conflict": ["report_date", "store_eplus_id", "category"],
                "update": ["store_id", "invoice_count", "total_sales"],
            },
            "ab.sales.dashboard.daily.item.fact": {
                "table": "ab_sales_dashboard_daily_item_fact",
                "columns": [
                    "report_date",
                    "store_id",
                    "store_eplus_id",
                    "item_eplus_id",
                    "item_code",
                    "product_id",
                    "item_name",
                    "item_type",
                    "sold_qty",
                    "sales_amount",
                    "invoice_count",
                    "sale_times",
                    "synced_at",
                ],
                "conflict": ["report_date", "store_eplus_id", "item_eplus_id"],
                "update": [
                    "store_id",
                    "item_code",
                    "product_id",
                    "item_name",
                    "item_type",
                    "sold_qty",
                    "sales_amount",
                    "invoice_count",
                    "sale_times",
                    "synced_at",
                ],
            },
        }

    @api.model
    def _coverage_persistence_mapping(self):
        return {
            "table": "ab_sales_dashboard_sync_coverage",
            "columns": ["report_date", "store_id", "store_eplus_id", "sync_state", "synced_at"],
            "conflict": ["report_date", "store_eplus_id"],
            "update": ["store_id", "sync_state", "synced_at"],
        }

    @api.model
    def _fact_coverage_persistence_mapping(self):
        return {
            "table": "ab_sales_dashboard_fact_coverage",
            "columns": ["report_date", "store_id", "store_eplus_id", "fact_type", "sync_state", "synced_at"],
            "conflict": ["report_date", "store_eplus_id", "fact_type"],
            "update": ["store_id", "sync_state", "synced_at"],
        }

    @api.model
    def _replace_fact_scope(self, model_name, rows, filters, store_eplus_ids):
        mapping = self._daily_fact_persistence_mappings()[model_name]
        self._delete_fact_scope(mapping["table"], model_name, filters, store_eplus_ids)
        self._insert_rows_in_batches(mapping, rows, model_name, filters)

    @api.model
    def _delete_fact_scope(self, table, model_name, filters, store_eplus_ids):
        started = time.monotonic()
        if not store_eplus_ids:
            deleted_count = 0
        else:
            self.env.cr.execute(
                f"""
                    DELETE FROM {table}
                    WHERE report_date >= %s
                      AND report_date <= %s
                      AND store_eplus_id = ANY(%s)
                """,
                [filters["date_from"], filters["date_to"], store_eplus_ids],
            )
            deleted_count = self.env.cr.rowcount
        _logger.info(
            "event=sales_dashboard_scope_delete_completed duration_ms=%s model=%s deleted_count=%s date_from=%s date_to=%s store_count=%s",
            int((time.monotonic() - started) * 1000),
            model_name,
            deleted_count,
            filters["date_from"],
            filters["date_to"],
            len(store_eplus_ids),
        )
        return deleted_count

    @api.model
    def _insert_rows_in_batches(self, mapping, rows, model_name, filters):
        started = time.monotonic()
        columns = list(mapping["columns"])
        insert_columns = columns + ["create_uid", "create_date", "write_uid", "write_date"]
        update_columns = list(mapping["update"]) + ["write_uid", "write_date"]
        conflict_columns = mapping["conflict"]
        batch_size = self._query_batch_size()
        total_count = 0
        now = fields.Datetime.now()
        for batch_number, offset in enumerate(range(0, len(rows), batch_size), start=1):
            batch = rows[offset:offset + batch_size]
            if not batch:
                continue
            placeholders = ", ".join(
                ["(" + ", ".join(["%s"] * len(insert_columns)) + ")"] * len(batch)
            )
            sql = f"""
                INSERT INTO {mapping['table']} ({', '.join(insert_columns)})
                VALUES {placeholders}
                ON CONFLICT ({', '.join(conflict_columns)})
                DO UPDATE SET {', '.join(f'{column} = EXCLUDED.{column}' for column in update_columns)}
            """
            params = []
            for row in batch:
                params.extend(self._sql_value(row[column]) for column in columns)
                params.extend([self.env.uid, now, self.env.uid, now])
            batch_started = time.monotonic()
            self.env.cr.execute(sql, params)
            total_count += len(batch)
            _logger.info(
                "event=sales_dashboard_fact_batch_completed duration_ms=%s model=%s batch_number=%s batch_size=%s row_count=%s date_from=%s date_to=%s",
                int((time.monotonic() - batch_started) * 1000),
                model_name,
                batch_number,
                batch_size,
                len(batch),
                filters["date_from"],
                filters["date_to"],
            )
        _logger.info(
            "event=sales_dashboard_fact_persistence_completed duration_ms=%s model=%s row_count=%s batch_size=%s date_from=%s date_to=%s store_id=%s",
            int((time.monotonic() - started) * 1000),
            model_name,
            total_count,
            batch_size,
            filters["date_from"],
            filters["date_to"],
            filters["store_id"],
        )

    @api.model
    def _persist_sync_coverage(self, rows, filters, store_count):
        started = time.monotonic()
        self._insert_rows_in_batches(
            self._coverage_persistence_mapping(),
            rows,
            "ab.sales.dashboard.sync.coverage",
            filters,
        )

    @api.model
    def _persist_fact_coverage(self, rows, filters, store_count, fact_type):
        started = time.monotonic()
        self._validate_daily_coverage_row_count(rows, filters, store_count)
        self._insert_rows_in_batches(
            self._fact_coverage_persistence_mapping(),
            rows,
            "ab.sales.dashboard.fact.coverage",
            filters,
        )
        _logger.info(
            "event=sales_dashboard_item_coverage_persistence_completed duration_ms=%s coverage_count=%s date_from=%s date_to=%s store_count=%s fact_type=%s",
            int((time.monotonic() - started) * 1000),
            len(rows),
            filters["date_from"],
            filters["date_to"],
            store_count,
            fact_type,
        )
        _logger.info(
            "event=sales_dashboard_coverage_persistence_completed duration_ms=%s coverage_count=%s date_from=%s date_to=%s store_count=%s",
            int((time.monotonic() - started) * 1000),
            len(rows),
            filters["date_from"],
            filters["date_to"],
            store_count,
        )

    @api.model
    def _invalidate_daily_reporting_models(self):
        for model_name in (
            "ab.sales.dashboard.daily.store.fact",
            "ab.sales.dashboard.daily.collection.fact",
            "ab.sales.dashboard.daily.item.fact",
            "ab.sales.dashboard.sync.coverage",
            "ab.sales.dashboard.fact.coverage",
        ):
            self.env[model_name].invalidate_model()

    @api.model
    def _dashboard_payload_from_daily_facts(self, filters):
        return self._build_dashboard_from_daily_facts(filters, allow_partial=False)

    @api.model
    def _build_dashboard_from_daily_facts(self, filters, allow_partial=False):
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_summary_started date_from=%s date_to=%s store_id=%s allow_partial=%s",
            filters.get("date_from"),
            filters.get("date_to"),
            filters.get("store_id"),
            allow_partial,
        )
        stores = self._fact_scope_stores(filters)
        if not stores or any(not store.eplus_serial for store in stores):
            self._log_daily_fallback_read(started, filters, 0, 0, "missing_store_scope")
            payload = self._empty_daily_summary_payload(filters, self._summary_report_meta(filters))
            return payload if allow_partial else False

        store_eplus_ids = [int(store.eplus_serial) for store in stores]
        coverage_started = time.monotonic()
        coverage = self._sync_coverage_metrics(filters["date_from"], filters["date_to"], store_eplus_ids)
        _logger.info(
            "event=sales_dashboard_summary_coverage_completed duration_ms=%s date_from=%s date_to=%s store_count=%s expected_store_days=%s covered_store_days=%s coverage_state=%s",
            int((time.monotonic() - coverage_started) * 1000),
            filters["date_from"],
            filters["date_to"],
            len(store_eplus_ids),
            coverage["expected_store_days"],
            coverage["covered_store_days"],
            coverage["coverage_state"],
        )
        if coverage["coverage_state"] != COVERAGE_COMPLETE and not allow_partial:
            self._log_daily_fallback_read(started, filters, 0, 0, "incomplete_current_coverage")
            return False
        if coverage["coverage_state"] == COVERAGE_UNAVAILABLE:
            _logger.info(
                "event=sales_dashboard_summary_unavailable date_from=%s date_to=%s store_count=%s expected_store_days=%s",
                filters["date_from"],
                filters["date_to"],
                len(store_eplus_ids),
                coverage["expected_store_days"],
            )
            payload = self._empty_daily_summary_payload(filters, self._summary_report_meta(filters, coverage=coverage))
            self._log_daily_fallback_read(started, filters, 0, 0, "unavailable_coverage")
            _logger.info(
                "event=sales_dashboard_summary_completed duration_ms=%s date_from=%s date_to=%s store_count=%s coverage_state=%s",
                int((time.monotonic() - started) * 1000),
                filters["date_from"],
                filters["date_to"],
                len(store_eplus_ids),
                coverage["coverage_state"],
            )
            return payload

        prev_from, prev_to = self._previous_filter_window(filters["date_from"], filters["date_to"])
        previous_coverage = self._sync_coverage_metrics(prev_from, prev_to, store_eplus_ids)
        item_coverage = self._fact_coverage_metrics(filters["date_from"], filters["date_to"], store_eplus_ids, "item")
        query_started = time.monotonic()
        current_totals = self._daily_store_fact_totals(filters["date_from"], filters["date_to"], store_eplus_ids)
        if previous_coverage["coverage_state"] == COVERAGE_COMPLETE:
            prev_total_sales = self._daily_store_fact_totals(prev_from, prev_to, store_eplus_ids)["total_sales"]
            unavailable_comparisons = []
        else:
            prev_total_sales = 0.0
            unavailable_comparisons = ["previous_avg_daily_sales"]
        _logger.info(
            "event=sales_dashboard_summary_query_completed duration_ms=%s date_from=%s date_to=%s store_count=%s fact_count=%s previous_coverage_state=%s",
            int((time.monotonic() - query_started) * 1000),
            filters["date_from"],
            filters["date_to"],
            len(store_eplus_ids),
            current_totals["fact_count"],
            previous_coverage["coverage_state"],
        )
        total_sales = current_totals["total_sales"]
        invoice_count = current_totals["invoice_count"]
        contract_net_amount = current_totals["contract_net_amount"]
        customer_bearing_amount = current_totals["customer_bearing_amount"]
        company_part_amount = current_totals["company_part_amount"]
        days = coverage["requested_days"] if coverage["coverage_state"] == COVERAGE_COMPLETE else max(coverage["covered_days"], 1)
        avg_daily_sales = total_sales / days
        prev_avg_daily_sales = prev_total_sales / coverage["requested_days"] if prev_total_sales else 0.0
        avg_daily_growth_pct = 100.0 * (avg_daily_sales - prev_avg_daily_sales) / prev_avg_daily_sales if prev_avg_daily_sales else 0.0
        bearing_pct = 100.0 * customer_bearing_amount / contract_net_amount if contract_net_amount else 0.0

        collection_lines = self._collection_lines_from_daily_facts(filters, store_eplus_ids, total_sales)
        if item_coverage["coverage_state"] == COVERAGE_COMPLETE:
            product_kpis = self._daily_item_product_kpis(filters["date_from"], filters["date_to"], store_eplus_ids, invoice_count)
            item_lines = self._summary_top_items_from_daily_item_facts(filters["date_from"], filters["date_to"], store_eplus_ids)
            unsupported_sections = PRODUCT_SUMMARY_UNSUPPORTED_SECTIONS
        else:
            product_kpis = self._empty_product_kpis()
            item_lines = []
            unsupported_sections = SUMMARY_UNSUPPORTED_SECTIONS
        report_meta = self._summary_report_meta(
            filters,
            coverage=coverage,
            previous_coverage=previous_coverage,
            item_coverage=item_coverage,
            unsupported_sections=unsupported_sections,
            unavailable_comparisons=unavailable_comparisons,
        )
        payload = {
            "has_snapshot": True,
            "total_sales": total_sales,
            "avg_daily_sales": avg_daily_sales,
            "prev_avg_daily_sales": prev_avg_daily_sales,
            "avg_daily_growth_pct": avg_daily_growth_pct,
            "invoice_count": invoice_count,
            "medicine_sales": current_totals["medicine_sales"],
            "non_medicine_sales": current_totals["non_medicine_sales"],
            "customer_bearing_amount": customer_bearing_amount,
            "company_part_amount": company_part_amount,
            "bearing_pct": bearing_pct,
            "total_units_sold": product_kpis["total_units_sold"],
            "unique_products_sold": product_kpis["unique_products_sold"],
            "total_product_sales": product_kpis["total_product_sales"],
            "avg_products_per_invoice": product_kpis["avg_products_per_invoice"],
            "stores_with_sales": product_kpis["stores_with_sales"],
            "avg_products_sold_per_store": product_kpis["avg_products_sold_per_store"],
            "collection_lines": collection_lines,
            "user_lines": [],
            "item_lines": item_lines,
            "invoice_lines": [],
            "report_meta": report_meta,
        }
        if coverage["coverage_state"] == COVERAGE_PARTIAL:
            _logger.info(
                "event=sales_dashboard_summary_partial date_from=%s date_to=%s store_count=%s covered_store_days=%s expected_store_days=%s",
                filters["date_from"],
                filters["date_to"],
                len(store_eplus_ids),
                coverage["covered_store_days"],
                coverage["expected_store_days"],
            )
        _logger.info(
            "event=sales_dashboard_summary_normalization_completed duration_ms=%s date_from=%s date_to=%s store_count=%s coverage_state=%s",
            int((time.monotonic() - query_started) * 1000),
            filters["date_from"],
            filters["date_to"],
            len(store_eplus_ids),
            coverage["coverage_state"],
        )
        self._log_daily_fallback_read(started, filters, current_totals["fact_count"], len(collection_lines), "success")
        _logger.info(
            "event=sales_dashboard_summary_completed duration_ms=%s date_from=%s date_to=%s store_count=%s coverage_state=%s",
            int((time.monotonic() - started) * 1000),
            filters["date_from"],
            filters["date_to"],
            len(store_eplus_ids),
            coverage["coverage_state"],
        )
        return payload

    @api.model
    def _has_complete_sync_coverage(self, date_from, date_to, store_eplus_ids, day_count):
        metrics = self._sync_coverage_metrics(date_from, date_to, store_eplus_ids, day_count=day_count)
        return metrics["coverage_state"] == COVERAGE_COMPLETE

    @api.model
    def _sync_coverage_metrics(self, date_from, date_to, store_eplus_ids, day_count=None):
        store_eplus_ids = [int(store_id) for store_id in store_eplus_ids if store_id]
        requested_days = day_count or max((fields.Date.to_date(date_to) - fields.Date.to_date(date_from)).days + 1, 1)
        store_count = len(store_eplus_ids)
        expected_count = requested_days * store_count
        if not store_eplus_ids:
            return {
                "coverage_state": COVERAGE_UNAVAILABLE,
                "requested_days": requested_days,
                "covered_days": 0,
                "missing_days": requested_days,
                "store_count": 0,
                "covered_store_days": 0,
                "expected_store_days": 0,
                "missing_store_days": 0,
                "coverage_pct": 0.0,
            }
        self.env.cr.execute(
            """
                SELECT COUNT(*) AS covered_store_days,
                       COUNT(DISTINCT report_date) AS covered_days
                FROM ab_sales_dashboard_sync_coverage
                WHERE report_date >= %s
                  AND report_date <= %s
                  AND store_eplus_id = ANY(%s)
                  AND sync_state = 'synced'
            """,
            [date_from, date_to, store_eplus_ids],
        )
        row = self.env.cr.fetchone()
        covered_store_days = int(row[0] or 0) if row else 0
        covered_days = int(row[1] or 0) if row else 0
        if expected_count and covered_store_days == expected_count:
            coverage_state = COVERAGE_COMPLETE
        elif covered_store_days:
            coverage_state = COVERAGE_PARTIAL
        else:
            coverage_state = COVERAGE_UNAVAILABLE
        missing_store_days = max(expected_count - covered_store_days, 0)
        return {
            "coverage_state": coverage_state,
            "requested_days": requested_days,
            "covered_days": min(covered_days, requested_days),
            "missing_days": max(requested_days - min(covered_days, requested_days), 0),
            "store_count": store_count,
            "covered_store_days": covered_store_days,
            "expected_store_days": expected_count,
            "missing_store_days": missing_store_days,
            "coverage_pct": 100.0 * covered_store_days / expected_count if expected_count else 0.0,
        }

    @api.model
    def _fact_coverage_metrics(self, date_from, date_to, store_eplus_ids, fact_type, day_count=None):
        store_eplus_ids = [int(store_id) for store_id in store_eplus_ids if store_id]
        requested_days = day_count or max((fields.Date.to_date(date_to) - fields.Date.to_date(date_from)).days + 1, 1)
        store_count = len(store_eplus_ids)
        expected_count = requested_days * store_count
        if not store_eplus_ids:
            return {
                "coverage_state": COVERAGE_UNAVAILABLE,
                "requested_days": requested_days,
                "covered_days": 0,
                "missing_days": requested_days,
                "store_count": 0,
                "covered_store_days": 0,
                "expected_store_days": 0,
                "missing_store_days": 0,
                "coverage_pct": 0.0,
            }
        started = time.monotonic()
        self.env.cr.execute(
            """
                SELECT COUNT(*) AS covered_store_days,
                       COUNT(DISTINCT report_date) AS covered_days
                FROM ab_sales_dashboard_fact_coverage
                WHERE report_date >= %s
                  AND report_date <= %s
                  AND store_eplus_id = ANY(%s)
                  AND fact_type = %s
                  AND sync_state = 'synced'
            """,
            [date_from, date_to, store_eplus_ids, fact_type],
        )
        row = self.env.cr.fetchone()
        covered_store_days = int(row[0] or 0) if row else 0
        covered_days = int(row[1] or 0) if row else 0
        if expected_count and covered_store_days == expected_count:
            coverage_state = COVERAGE_COMPLETE
        elif covered_store_days:
            coverage_state = COVERAGE_PARTIAL
        else:
            coverage_state = COVERAGE_UNAVAILABLE
        missing_store_days = max(expected_count - covered_store_days, 0)
        result = {
            "coverage_state": coverage_state,
            "requested_days": requested_days,
            "covered_days": min(covered_days, requested_days),
            "missing_days": max(requested_days - min(covered_days, requested_days), 0),
            "store_count": store_count,
            "covered_store_days": covered_store_days,
            "expected_store_days": expected_count,
            "missing_store_days": missing_store_days,
            "coverage_pct": 100.0 * covered_store_days / expected_count if expected_count else 0.0,
        }
        _logger.info(
            "event=sales_dashboard_item_coverage_analysis_completed duration_ms=%s fact_type=%s date_from=%s date_to=%s store_count=%s coverage_state=%s covered_store_days=%s expected_store_days=%s",
            int((time.monotonic() - started) * 1000),
            fact_type,
            date_from,
            date_to,
            store_count,
            coverage_state,
            covered_store_days,
            expected_count,
        )
        return result

    @api.model
    def _has_complete_fact_coverage(self, date_from, date_to, store_eplus_ids, day_count, fact_type):
        metrics = self._fact_coverage_metrics(date_from, date_to, store_eplus_ids, fact_type, day_count=day_count)
        return metrics["coverage_state"] == COVERAGE_COMPLETE

    @api.model
    def _empty_product_kpis(self):
        return {
            "total_units_sold": 0.0,
            "unique_products_sold": 0,
            "total_product_sales": 0.0,
            "avg_products_per_invoice": 0.0,
            "stores_with_sales": 0,
            "avg_products_sold_per_store": 0.0,
        }

    @api.model
    def _daily_item_product_kpis(self, date_from, date_to, store_eplus_ids, invoice_count):
        started = time.monotonic()
        self.env.cr.execute(
            """
                WITH store_product_counts AS (
                    SELECT store_eplus_id, COUNT(DISTINCT item_eplus_id) AS unique_products
                    FROM ab_sales_dashboard_daily_item_fact
                    WHERE report_date >= %s
                      AND report_date <= %s
                      AND store_eplus_id = ANY(%s)
                    GROUP BY store_eplus_id
                )
                SELECT
                    COALESCE(SUM(sold_qty), 0) AS total_units_sold,
                    COUNT(DISTINCT item_eplus_id) AS unique_products_sold,
                    COALESCE(SUM(sales_amount), 0) AS total_product_sales,
                    COALESCE(SUM(sale_times), 0) AS item_invoice_occurrences,
                    COUNT(DISTINCT store_eplus_id) AS stores_with_sales,
                    COALESCE((SELECT AVG(unique_products::numeric) FROM store_product_counts), 0) AS avg_products_sold_per_store
                FROM ab_sales_dashboard_daily_item_fact
                WHERE report_date >= %s
                  AND report_date <= %s
                  AND store_eplus_id = ANY(%s)
            """,
            [date_from, date_to, store_eplus_ids, date_from, date_to, store_eplus_ids],
        )
        row = self.env.cr.fetchone() or [0, 0, 0, 0, 0, 0]
        item_invoice_occurrences = float(row[3] or 0.0)
        result = {
            "total_units_sold": float(row[0] or 0.0),
            "unique_products_sold": int(row[1] or 0),
            "total_product_sales": float(row[2] or 0.0),
            "avg_products_per_invoice": item_invoice_occurrences / invoice_count if invoice_count else 0.0,
            "stores_with_sales": int(row[4] or 0),
            "avg_products_sold_per_store": float(row[5] or 0.0),
        }
        _logger.info(
            "event=sales_dashboard_summary_product_aggregation_completed duration_ms=%s date_from=%s date_to=%s store_count=%s unique_products_sold=%s",
            int((time.monotonic() - started) * 1000),
            date_from,
            date_to,
            len(store_eplus_ids),
            result["unique_products_sold"],
        )
        return result

    @api.model
    def _summary_top_items_from_daily_item_facts(self, date_from, date_to, store_eplus_ids):
        started = time.monotonic()
        self.env.cr.execute(
            """
                SELECT
                    item_eplus_id,
                    MAX(item_code) AS item_code,
                    MAX(product_id) AS product_id,
                    MAX(item_name) AS item_name,
                    COALESCE(SUM(sale_times), 0) AS sale_times,
                    COALESCE(SUM(sold_qty), 0) AS sold_qty,
                    COALESCE(SUM(sales_amount), 0) AS total_sales
                FROM ab_sales_dashboard_daily_item_fact
                WHERE report_date >= %s
                  AND report_date <= %s
                  AND store_eplus_id = ANY(%s)
                GROUP BY item_eplus_id
                ORDER BY COALESCE(SUM(sale_times), 0) DESC, COALESCE(SUM(sold_qty), 0) DESC
                LIMIT 20
            """,
            [date_from, date_to, store_eplus_ids],
        )
        rows = self.env.cr.fetchall()
        result = []
        for item_eplus_id, item_code, product_id, item_name, sale_times, sold_qty, total_sales in rows:
            result.append({
                "row_key": "summary_item_%s" % item_eplus_id,
                "eplus_item_id": int(item_eplus_id or 0),
                "eplus_item_code": item_code or "",
                "product_name": item_name or item_code or str(item_eplus_id),
                "product_id": product_id or False,
                "sale_times": int(sale_times or 0),
                "sold_qty": float(sold_qty or 0.0),
                "total_sales": float(total_sales or 0.0),
                "current_balance": 0.0,
            })
        _logger.info(
            "event=sales_dashboard_summary_top_items_completed duration_ms=%s date_from=%s date_to=%s store_count=%s row_count=%s",
            int((time.monotonic() - started) * 1000),
            date_from,
            date_to,
            len(store_eplus_ids),
            len(result),
        )
        return result

    @api.model
    def _empty_daily_summary_payload(self, filters, report_meta):
        categories = [key for key, _label in self.env["ab.sales.dashboard.daily.collection.fact"]._fields["category"].selection]
        collection_lines = []
        for category in categories:
            collection_lines.append({
                "category": category,
                "collection_category": category,
                "invoice_count": 0,
                "total_sales": 0.0,
                "pct_of_total": 0.0,
                "row_key": "collection_%s" % category,
            })
        return {
            "has_snapshot": True,
            "total_sales": 0.0,
            "avg_daily_sales": 0.0,
            "prev_avg_daily_sales": 0.0,
            "avg_daily_growth_pct": 0.0,
            "invoice_count": 0,
            "medicine_sales": 0.0,
            "non_medicine_sales": 0.0,
            "customer_bearing_amount": 0.0,
            "company_part_amount": 0.0,
            "bearing_pct": 0.0,
            "total_units_sold": 0.0,
            "unique_products_sold": 0,
            "total_product_sales": 0.0,
            "avg_products_per_invoice": 0.0,
            "stores_with_sales": 0,
            "avg_products_sold_per_store": 0.0,
            "collection_lines": collection_lines,
            "user_lines": [],
            "item_lines": [],
            "invoice_lines": [],
            "report_meta": report_meta,
        }

    @api.model
    def _daily_store_fact_totals(self, date_from, date_to, store_eplus_ids):
        self.env.cr.execute(
            """
                SELECT
                    COUNT(*) AS fact_count,
                    COALESCE(SUM(total_sales), 0) AS total_sales,
                    COALESCE(SUM(invoice_count), 0) AS invoice_count,
                    COALESCE(SUM(medicine_sales), 0) AS medicine_sales,
                    COALESCE(SUM(non_medicine_sales), 0) AS non_medicine_sales,
                    COALESCE(SUM(customer_bearing_amount), 0) AS customer_bearing_amount,
                    COALESCE(SUM(company_part_amount), 0) AS company_part_amount,
                    COALESCE(SUM(contract_net_amount), 0) AS contract_net_amount
                FROM ab_sales_dashboard_daily_store_fact
                WHERE report_date >= %s
                  AND report_date <= %s
                  AND store_eplus_id = ANY(%s)
            """,
            [date_from, date_to, store_eplus_ids],
        )
        row = self.env.cr.fetchone() or [0, 0, 0, 0, 0, 0, 0, 0]
        return {
            "fact_count": int(row[0] or 0),
            "total_sales": float(row[1] or 0.0),
            "invoice_count": int(row[2] or 0),
            "medicine_sales": float(row[3] or 0.0),
            "non_medicine_sales": float(row[4] or 0.0),
            "customer_bearing_amount": float(row[5] or 0.0),
            "company_part_amount": float(row[6] or 0.0),
            "contract_net_amount": float(row[7] or 0.0),
        }

    @api.model
    def _log_daily_fallback_read(self, started, filters, fact_count, collection_count, status):
        _logger.info(
            "event=sales_dashboard_daily_fallback_read_completed duration_ms=%s date_from=%s date_to=%s store_id=%s fact_count=%s collection_count=%s status=%s",
            int((time.monotonic() - started) * 1000),
            filters.get("date_from"),
            filters.get("date_to"),
            filters.get("store_id"),
            fact_count,
            collection_count,
            status,
        )

    @api.model
    def _previous_filter_window(self, date_from, date_to):
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        days = max((date_to - date_from).days + 1, 1)
        prev_to = date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        return prev_from, prev_to

    @api.model
    def _collection_lines_from_daily_facts(self, filters, store_eplus_ids, total_sales):
        categories = [key for key, _label in self.env["ab.sales.dashboard.daily.collection.fact"]._fields["category"].selection]
        totals = {
            category: {
                "category": category,
                "collection_category": category,
                "invoice_count": 0,
                "total_sales": 0.0,
            }
            for category in categories
        }
        self.env.cr.execute(
            """
                SELECT
                    category,
                    COALESCE(SUM(invoice_count), 0) AS invoice_count,
                    COALESCE(SUM(total_sales), 0) AS total_sales
                FROM ab_sales_dashboard_daily_collection_fact
                WHERE report_date >= %s
                  AND report_date <= %s
                  AND store_eplus_id = ANY(%s)
                GROUP BY category
            """,
            [filters["date_from"], filters["date_to"], store_eplus_ids],
        )
        for category, invoice_count, sales_amount in self.env.cr.fetchall():
            if category not in totals:
                continue
            totals[category]["invoice_count"] = int(invoice_count or 0)
            totals[category]["total_sales"] = float(sales_amount or 0.0)
        result = []
        for data in totals.values():
            data["pct_of_total"] = 100.0 * data["total_sales"] / total_sales if total_sales else 0.0
            data["row_key"] = "collection_%s" % data["category"]
            result.append(data)
        return sorted(result, key=lambda item: item["total_sales"], reverse=True)

    @api.model
    def _products_by_serial(self, itm_ids):
        clean_ids = [int(itm_id) for itm_id in itm_ids if itm_id]
        products = self.env["ab_product"].sudo().with_context(active_test=False).search([
            ("eplus_serial", "in", clean_ids),
        ])
        result = {}
        for product in products:
            result.setdefault(int(product.eplus_serial or 0), product)
        return result

    @api.model
    def _collection_line_values(self, rows):
        return [{
            "category": row.get("collection_category") or "cash",
            "invoice_count": int(row.get("invoice_count") or 0),
            "total_sales": float(row.get("total_sales") or 0.0),
            "pct_of_total": float(row.get("pct_of_total") or 0.0),
        } for row in rows]

    @api.model
    def _user_line_values(self, rows):
        return [{
            "employee_eplus_id": int(row.get("emp_id") or 0),
            "employee_name": row.get("employee_name") or "",
            "invoice_count": int(row.get("invoice_count") or 0),
            "total_sales": float(row.get("total_sales") or 0.0),
            "pct_of_total": float(row.get("pct_of_total") or 0.0),
        } for row in rows]

    @api.model
    def _item_line_values(self, rows, products_by_serial):
        values = []
        for row in rows:
            item_id = int(row.get("itm_id") or 0)
            product = products_by_serial.get(item_id)
            values.append({
                "eplus_item_id": item_id,
                "eplus_item_code": row.get("itm_code") or "",
                "product_id": product.id if product else False,
                "item_name": product.display_name if product else (row.get("itm_code") or str(item_id)),
                "sale_times": int(row.get("sale_times") or 0),
                "sold_qty": float(row.get("sold_qty") or 0.0),
                "total_sales": float(row.get("total_sales") or 0.0),
                "current_balance": float(row.get("current_balance") or 0.0),
            })
        return values

    @api.model
    def _invoice_line_values(self, rows):
        return [{
            "invoice_no": str(row.get("invoice_no") or ""),
            "invoice_date": row.get("sec_insert_date") or False,
            "customer_name": self._dashboard_customer_name(row.get("customer_name")),
            "invoice_total": float(row.get("invoice_total") or 0.0),
            "item_count": int(row.get("item_count") or 0),
            "items_summary": row.get("items") or "",
        } for row in rows]

    @api.model
    def _dashboard_customer_name(self, value):
        value = (value or "").strip()
        if value == "__cash_customer__":
            return _("Cash Customer")
        return value


class SalesDashboardCollectionLine(models.Model):
    _name = "ab.sales.dashboard.collection.line"
    _description = "Sales Dashboard Collection Line"
    _order = "total_sales desc, id"

    snapshot_id = fields.Many2one("ab.sales.dashboard.snapshot", required=True, ondelete="cascade", index=True)
    category = fields.Selection([
        ("cash", "Cash"),
        ("delivery", "Delivery"),
        ("contract", "Contracts"),
        ("offer", "Offers"),
    ], required=True, readonly=True)
    invoice_count = fields.Integer(readonly=True)
    total_sales = fields.Float(readonly=True)
    pct_of_total = fields.Float(readonly=True)

    def _as_dashboard_dict(self):
        self.ensure_one()
        return {
            "row_key": "collection_%s_%s" % (self.id, self.category),
            "category": self.category,
            "label": dict(self._fields["category"].selection).get(self.category, self.category),
            "invoice_count": self.invoice_count,
            "total_sales": self.total_sales,
            "pct_of_total": self.pct_of_total,
        }


class SalesDashboardUserLine(models.Model):
    _name = "ab.sales.dashboard.user.line"
    _description = "Sales Dashboard User Line"
    _order = "total_sales desc, id"

    snapshot_id = fields.Many2one("ab.sales.dashboard.snapshot", required=True, ondelete="cascade", index=True)
    employee_eplus_id = fields.Integer(readonly=True, index=True)
    employee_name = fields.Char(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    total_sales = fields.Float(readonly=True)
    pct_of_total = fields.Float(readonly=True)

    def _as_dashboard_dict(self):
        self.ensure_one()
        return {
            "row_key": "user_%s" % self.id,
            "employee_eplus_id": self.employee_eplus_id,
            "employee_name": self.employee_name,
            "invoice_count": self.invoice_count,
            "total_sales": self.total_sales,
            "pct_of_total": self.pct_of_total,
        }


class SalesDashboardItemLine(models.Model):
    _name = "ab.sales.dashboard.item.line"
    _description = "Sales Dashboard Item Line"
    _order = "sale_times desc, sold_qty desc, id"

    snapshot_id = fields.Many2one("ab.sales.dashboard.snapshot", required=True, ondelete="cascade", index=True)
    eplus_item_id = fields.Integer(readonly=True, index=True)
    eplus_item_code = fields.Char(readonly=True, index=True)
    product_id = fields.Many2one("ab_product", readonly=True, index=True)
    item_name = fields.Char(readonly=True)
    sale_times = fields.Integer(readonly=True)
    sold_qty = fields.Float(readonly=True)
    total_sales = fields.Float(readonly=True)
    current_balance = fields.Float(readonly=True)

    def _as_dashboard_dict(self):
        self.ensure_one()
        return {
            "row_key": "item_%s" % self.id,
            "eplus_item_id": self.eplus_item_id,
            "eplus_item_code": self.eplus_item_code,
            "product_name": self.product_id.display_name if self.product_id else self.item_name,
            "sale_times": self.sale_times,
            "sold_qty": self.sold_qty,
            "total_sales": self.total_sales,
            "current_balance": self.current_balance,
        }


class SalesDashboardInvoiceLine(models.Model):
    _name = "ab.sales.dashboard.invoice.line"
    _description = "Sales Dashboard Invoice Line"
    _order = "invoice_date desc, id desc"

    snapshot_id = fields.Many2one("ab.sales.dashboard.snapshot", required=True, ondelete="cascade", index=True)
    invoice_no = fields.Char(readonly=True, index=True)
    invoice_date = fields.Datetime(readonly=True, index=True)
    customer_name = fields.Char(readonly=True)
    invoice_total = fields.Float(readonly=True)
    item_count = fields.Integer(readonly=True)
    items_summary = fields.Text(readonly=True)

    def _as_dashboard_dict(self):
        self.ensure_one()
        return {
            "row_key": "invoice_%s" % self.id,
            "invoice_no": self.invoice_no,
            "invoice_date": fields.Datetime.to_string(self.invoice_date) if self.invoice_date else "",
            "customer_name": self.customer_name,
            "invoice_total": self.invoice_total,
            "item_count": self.item_count,
            "items_summary": self.items_summary,
        }


class SalesDashboardReportArchive(models.Model):
    _name = "ab.sales.dashboard.report.archive"
    _inherit = ["ab.sales.dashboard.config.mixin"]
    _description = "Archived Sales Dashboard Report"
    _order = "archived_at desc, id desc"

    name = fields.Char(required=True, readonly=True)
    archive_number = fields.Char(required=True, readonly=True, copy=False, index=True)
    snapshot_id = fields.Many2one("ab.sales.dashboard.snapshot", readonly=True, ondelete="restrict", index=True)
    date_from = fields.Date(required=True, readonly=True, index=True)
    date_to = fields.Date(required=True, readonly=True, index=True)
    store_filter_key = fields.Char(readonly=True, index=True)
    store_filter_label = fields.Char(readonly=True)
    store_ids = fields.Many2many("ab_store", string="Stores", readonly=True)
    archived_at = fields.Datetime(required=True, readonly=True, index=True)
    archived_by = fields.Many2one("res.users", required=True, readonly=True, index=True)
    state = fields.Selection([
        ("archived", "Archived"),
        ("cancelled", "Cancelled"),
    ], required=True, readonly=True, default="archived", index=True)
    payload_json = fields.Json(required=True, readonly=True)
    payload_hash = fields.Char(required=True, readonly=True, index=True)
    payload_size_bytes = fields.Integer(readonly=True)
    source_snapshot_write_date = fields.Datetime(readonly=True)

    _uniq_archive_number = models.Constraint(
        "UNIQUE(archive_number)",
        "Archive number must be unique.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.context.get("ab_sales_dashboard_allow_archive_create"):
            raise AccessError(_("Sales dashboard report archives must be created through the archive action."))
        sequence = self.env["ir.sequence"].sudo()
        now = fields.Datetime.now()
        user_id = self.env.user.id
        for vals in vals_list:
            archive_number = vals.get("archive_number") or sequence.next_by_code("ab.sales.dashboard.report.archive") or "/"
            vals.setdefault("archive_number", archive_number)
            vals.setdefault("name", archive_number)
            vals.setdefault("archived_at", now)
            vals.setdefault("archived_by", user_id)
            vals.setdefault("state", "archived")
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) != {"state"} or vals.get("state") != "cancelled":
            raise UserError(_("Archived sales dashboard reports are immutable."))
        return super().write(vals)

    def unlink(self):
        raise UserError(_("Archived sales dashboard reports cannot be deleted."))

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    @api.model
    def _archive_payload_bytes(self, payload):
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @api.model
    def _compute_archive_payload_hash(self, payload):
        return hashlib.sha256(self._archive_payload_bytes(payload)).hexdigest()

    @api.model
    def _validate_archive_payload_size(self, payload_bytes):
        max_bytes = self._max_archive_payload_bytes()
        if len(payload_bytes) > max_bytes:
            raise UserError(_("The archived dashboard payload exceeds the configured safety limit of %s bytes.") % max_bytes)
        return True

    @api.model
    def get_archived_dashboard_data(self, archive_id):
        started = time.monotonic()
        _logger.info(
            "event=sales_dashboard_archive_read_started archive_id=%s",
            archive_id,
        )
        archive = self.browse(archive_id).exists()
        if not archive:
            raise UserError(_("Archived sales dashboard report was not found."))
        archive.check_access("read")
        payload = json.loads(json.dumps(archive.payload_json or {}, ensure_ascii=False))
        _logger.info(
            "event=sales_dashboard_archive_read_completed archive_id=%s archive_number=%s payload_size_bytes=%s elapsed_ms=%s",
            archive.id,
            archive.archive_number,
            archive.payload_size_bytes,
            int((time.monotonic() - started) * 1000),
        )
        report_meta = payload.get("report_meta") or {}
        filters = {"date_from": archive.date_from, "date_to": archive.date_to, "store_id": archive.store_ids[:1].id if len(archive.store_ids) == 1 else 0}
        self.env["ab.sales.dashboard.report.telemetry"].record_operation(
            "archive_read",
            "archive",
            filters=filters,
            duration_ms=int((time.monotonic() - started) * 1000),
            result=payload,
            report_meta=report_meta,
            selected_store_count=len(archive.store_ids),
            archive_used=True,
            snapshot_used=True,
        )
        return payload


class SalesDashboardDailyStoreFact(models.Model):
    _name = "ab.sales.dashboard.daily.store.fact"
    _description = "Sales Dashboard Daily Store Fact"
    _order = "report_date desc, store_eplus_id"

    report_date = fields.Date(required=True, readonly=True, index=True)
    store_id = fields.Many2one("ab_store", readonly=True, index=True)
    store_eplus_id = fields.Integer(required=True, readonly=True, index=True)
    total_sales = fields.Float(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    medicine_sales = fields.Float(readonly=True)
    non_medicine_sales = fields.Float(readonly=True)
    customer_bearing_amount = fields.Float(readonly=True)
    company_part_amount = fields.Float(readonly=True)
    contract_net_amount = fields.Float(readonly=True)

    _uniq_daily_store = models.Constraint(
        "UNIQUE(report_date, store_eplus_id)",
        "Daily store facts must be unique per date and E-Plus store.",
    )


class SalesDashboardDailyCollectionFact(models.Model):
    _name = "ab.sales.dashboard.daily.collection.fact"
    _description = "Sales Dashboard Daily Collection Fact"
    _order = "report_date desc, store_eplus_id, category"

    report_date = fields.Date(required=True, readonly=True, index=True)
    store_id = fields.Many2one("ab_store", readonly=True, index=True)
    store_eplus_id = fields.Integer(required=True, readonly=True, index=True)
    category = fields.Selection([
        ("cash", "Cash"),
        ("delivery", "Delivery"),
        ("contract", "Contracts"),
        ("offer", "Offers"),
    ], required=True, readonly=True, index=True)
    invoice_count = fields.Integer(readonly=True)
    total_sales = fields.Float(readonly=True)

    _uniq_daily_collection = models.Constraint(
        "UNIQUE(report_date, store_eplus_id, category)",
        "Daily collection facts must be unique per date, E-Plus store, and category.",
    )


class SalesDashboardDailyItemFact(models.Model):
    _name = "ab.sales.dashboard.daily.item.fact"
    _description = "Sales Dashboard Daily Item Fact"
    _order = "report_date desc, store_eplus_id, sales_amount desc, item_eplus_id"

    report_date = fields.Date(required=True, readonly=True, index=True)
    store_id = fields.Many2one("ab_store", readonly=True, index=True)
    store_eplus_id = fields.Integer(required=True, readonly=True, index=True)
    item_eplus_id = fields.Integer(required=True, readonly=True, index=True)
    item_code = fields.Char(readonly=True, index=True)
    product_id = fields.Many2one("ab_product", readonly=True, index=True)
    item_name = fields.Char(readonly=True)
    item_type = fields.Selection([
        ("medicine", "Medicine"),
        ("non_medicine", "Non-Medicine"),
    ], required=True, readonly=True, default="medicine", index=True)
    sold_qty = fields.Float(readonly=True)
    sales_amount = fields.Float(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    sale_times = fields.Integer(readonly=True)
    synced_at = fields.Datetime(readonly=True, index=True)

    _uniq_daily_item = models.Constraint(
        "UNIQUE(report_date, store_eplus_id, item_eplus_id)",
        "Daily item facts must be unique per date, E-Plus store, and E-Plus item.",
    )


class SalesDashboardFactCoverage(models.Model):
    _name = "ab.sales.dashboard.fact.coverage"
    _description = "Sales Dashboard Fact Coverage"
    _order = "report_date desc, store_eplus_id, fact_type"

    report_date = fields.Date(required=True, readonly=True, index=True)
    store_id = fields.Many2one("ab_store", readonly=True, index=True)
    store_eplus_id = fields.Integer(required=True, readonly=True, index=True)
    fact_type = fields.Selection([
        ("store", "Store"),
        ("collection", "Collection"),
        ("item", "Item"),
    ], required=True, readonly=True, index=True)
    sync_state = fields.Selection([
        ("synced", "Synced"),
        ("failed", "Failed"),
    ], required=True, readonly=True, default="synced", index=True)
    synced_at = fields.Datetime(readonly=True, index=True)

    _uniq_fact_coverage = models.Constraint(
        "UNIQUE(report_date, store_eplus_id, fact_type)",
        "Fact coverage must be unique per date, E-Plus store, and fact type.",
    )


class SalesDashboardProductSalesReport(models.Model):
    _name = "ab.sales.dashboard.product.sales.report"
    _description = "Product Sales Report"
    _auto = False
    _order = "total_sales desc, units_sold desc, item_eplus_id"

    report_date = fields.Date(readonly=True, index=True)
    store_id = fields.Many2one("ab_store", readonly=True, index=True)
    store_eplus_id = fields.Integer(readonly=True, index=True)
    item_eplus_id = fields.Integer(readonly=True, index=True)
    item_code = fields.Char(readonly=True, index=True)
    product_id = fields.Many2one("ab_product", readonly=True, index=True)
    product_name = fields.Char(readonly=True)
    item_type = fields.Selection([
        ("medicine", "Medicine"),
        ("non_medicine", "Non-Medicine"),
    ], readonly=True, index=True)
    branches_sold_in = fields.Integer(readonly=True)
    sale_times = fields.Integer(readonly=True)
    invoice_count = fields.Integer(readonly=True)
    units_sold = fields.Float(readonly=True)
    total_sales = fields.Float(readonly=True)
    average_selling_price = fields.Float(readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(fact.id) AS id,
                    fact.report_date,
                    fact.store_id,
                    fact.store_eplus_id,
                    fact.item_eplus_id,
                    MAX(fact.item_code) AS item_code,
                    MAX(fact.product_id) AS product_id,
                    MAX(fact.item_name) AS product_name,
                    MAX(fact.item_type) AS item_type,
                    COUNT(DISTINCT fact.store_eplus_id) AS branches_sold_in,
                    SUM(fact.sale_times) AS sale_times,
                    SUM(fact.invoice_count) AS invoice_count,
                    SUM(fact.sold_qty) AS units_sold,
                    SUM(fact.sales_amount) AS total_sales,
                    SUM(fact.sales_amount) / NULLIF(SUM(fact.sold_qty), 0) AS average_selling_price
                FROM ab_sales_dashboard_daily_item_fact fact
                GROUP BY
                    fact.report_date,
                    fact.store_id,
                    fact.store_eplus_id,
                    fact.item_eplus_id
            )
        """)


class SalesDashboardSyncCoverage(models.Model):
    _name = "ab.sales.dashboard.sync.coverage"
    _description = "Sales Dashboard Sync Coverage"
    _order = "report_date desc, store_eplus_id"

    report_date = fields.Date(required=True, readonly=True, index=True)
    store_id = fields.Many2one("ab_store", readonly=True, index=True)
    store_eplus_id = fields.Integer(required=True, readonly=True, index=True)
    sync_state = fields.Selection([
        ("synced", "Synced"),
        ("failed", "Failed"),
    ], required=True, readonly=True, default="synced", index=True)
    synced_at = fields.Datetime(readonly=True, index=True)

    _uniq_sync_coverage = models.Constraint(
        "UNIQUE(report_date, store_eplus_id)",
        "Sync coverage must be unique per date and E-Plus store.",
    )
