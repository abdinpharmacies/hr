import logging
import time as pytime
from contextlib import ExitStack, contextmanager
from datetime import datetime, time
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import config
from odoo.tools.translate import _


_logger = logging.getLogger(__name__)


class SalesDashboardSourceUnavailableError(UserError):
    """Raised when no configured E-Plus source can accept a connection."""


class SalesDashboardService(models.AbstractModel):
    _name = "ab.sales.dashboard.service"
    _inherit = ["ab_eplus_connect", "ab.sales.dashboard.config.mixin"]
    _description = "Sales Dashboard E-Plus Service"
    _dashboard_preferred_server = False

    @api.model
    def fetch_dashboard_data(self, date_from, date_to, store_eplus_ids=None):
        start_dt, end_dt, store_eplus_ids, where_sql, base_params = self._prepare_source_context(
            date_from,
            date_to,
            store_eplus_ids,
        )
        started = pytime.monotonic()
        _logger.info(
            "event=sales_dashboard_service_started operation=fetch_dashboard_data date_from=%s date_to=%s store_count=%s",
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )

        try:
            with self._dashboard_query_session(where_sql, base_params, start_dt, end_dt, len(store_eplus_ids)) as cursor:
                payload = self._fetch_dashboard_from_cursor(cursor, start_dt, end_dt, store_eplus_ids)
        except SalesDashboardSourceUnavailableError:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.warning(
                "event=sales_dashboard_service_source_unavailable operation=fetch_dashboard_data duration_ms=%s date_from=%s date_to=%s store_count=%s",
                duration_ms,
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise
        except Exception:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.exception(
                "event=sales_dashboard_service_failed operation=fetch_dashboard_data duration_ms=%s date_from=%s date_to=%s store_count=%s",
                duration_ms,
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise

        duration_ms = int((pytime.monotonic() - started) * 1000)
        _logger.info(
            "event=sales_dashboard_service_completed operation=fetch_dashboard_data duration_ms=%s date_from=%s date_to=%s store_count=%s",
            duration_ms,
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )

        return payload

    @api.model
    def fetch_refresh_data(self, date_from, date_to, store_eplus_ids=None):
        """Fetch dashboard payload and daily facts from one B-Connect session.

        date_to is exclusive. This method is internal to refresh persistence and
        intentionally does not change the frontend RPC payload contract.
        """
        start_dt, end_dt, store_eplus_ids, where_sql, base_params = self._prepare_source_context(
            date_from,
            date_to,
            store_eplus_ids,
        )
        started = pytime.monotonic()
        _logger.info(
            "event=sales_dashboard_source_started date_from=%s date_to=%s store_count=%s",
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )

        try:
            with self._dashboard_query_session(where_sql, base_params, start_dt, end_dt, len(store_eplus_ids)) as cursor:
                dashboard_started = pytime.monotonic()
                dashboard = self._fetch_dashboard_from_cursor(cursor, start_dt, end_dt, store_eplus_ids)
                dashboard_duration_ms = int((pytime.monotonic() - dashboard_started) * 1000)
                _logger.info(
                    "event=sales_dashboard_sections_completed duration_ms=%s date_from=%s date_to=%s store_count=%s",
                    dashboard_duration_ms,
                    start_dt.date(),
                    end_dt.date(),
                    len(store_eplus_ids),
                )

                daily_started = pytime.monotonic()
                daily_store_facts = self._fetch_daily_store_facts_from_cursor(cursor, start_dt, end_dt, len(store_eplus_ids))
                self._validate_daily_fact_row_count(daily_store_facts, start_dt, end_dt, len(store_eplus_ids))
                daily_duration_ms = int((pytime.monotonic() - daily_started) * 1000)
                _logger.info(
                    "event=sales_dashboard_daily_facts_completed duration_ms=%s row_count=%s date_from=%s date_to=%s store_count=%s",
                    daily_duration_ms,
                    self._daily_fact_row_count(daily_store_facts),
                    start_dt.date(),
                    end_dt.date(),
                    len(store_eplus_ids),
                )
        except SalesDashboardSourceUnavailableError:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.warning(
                "event=sales_dashboard_source_unavailable duration_ms=%s date_from=%s date_to=%s store_count=%s",
                duration_ms,
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise
        except Exception:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.exception(
                "event=sales_dashboard_source_failed duration_ms=%s date_from=%s date_to=%s store_count=%s",
                duration_ms,
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise

        duration_ms = int((pytime.monotonic() - started) * 1000)
        _logger.info(
            "event=sales_dashboard_source_completed duration_ms=%s dashboard_duration_ms=%s daily_facts_duration_ms=%s daily_fact_row_count=%s date_from=%s date_to=%s store_count=%s",
            duration_ms,
            dashboard_duration_ms,
            daily_duration_ms,
            self._daily_fact_row_count(daily_store_facts),
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )
        return {
            "dashboard": dashboard,
            "daily_store_facts": daily_store_facts,
        }

    @api.model
    def fetch_customer_sales_page(
        self,
        date_from,
        date_to,
        store_eplus_ids=None,
        page=1,
        page_size=20,
        search_term=None,
    ):
        start_dt, end_dt, store_eplus_ids, where_sql, base_params = self._prepare_source_context(
            date_from,
            date_to,
            store_eplus_ids,
        )
        page = max(int(page or 1), 1)
        page_size = max(1, min(int(page_size or 20), 20))
        search_term = str(search_term or "").strip()[:100]
        search_pattern = "%%%s%%" % search_term if search_term else False
        params = list(base_params)
        if search_pattern:
            params.extend([search_pattern, search_pattern, search_pattern])
        params.extend([(page - 1) * page_size, page_size])
        started = pytime.monotonic()
        _logger.info(
            "event=sales_dashboard_customer_page_started page=%s page_size=%s date_from=%s date_to=%s store_count=%s has_search=%s",
            page,
            page_size,
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
            bool(search_term),
        )
        cursor = None
        try:
            with self._dashboard_source_connection() as connection:
                cursor = connection.cursor()
                rows = self._fetch_all(
                    cursor,
                    self._customer_sales_page_sql(where_sql, has_search=bool(search_pattern)),
                    params,
                    "customer_sales_page",
                    start_dt,
                    end_dt,
                    len(store_eplus_ids),
                )
        except SalesDashboardSourceUnavailableError:
            _logger.warning(
                "event=sales_dashboard_customer_page_source_unavailable page=%s duration_ms=%s date_from=%s date_to=%s store_count=%s",
                page,
                int((pytime.monotonic() - started) * 1000),
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise
        except Exception:
            _logger.exception(
                "event=sales_dashboard_customer_page_failed page=%s duration_ms=%s date_from=%s date_to=%s store_count=%s",
                page,
                int((pytime.monotonic() - started) * 1000),
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    _logger.warning(
                        "event=sales_dashboard_customer_page_cursor_close_failed page=%s date_from=%s date_to=%s store_count=%s",
                        page,
                        start_dt.date(),
                        end_dt.date(),
                        len(store_eplus_ids),
                        exc_info=True,
                    )
        total_count = int(rows[0].get("total_count") or 0) if rows else 0
        rows = self._normalize_invoice_lines(rows)
        _logger.info(
            "event=sales_dashboard_customer_page_completed page=%s page_size=%s row_count=%s total_count=%s duration_ms=%s date_from=%s date_to=%s store_count=%s",
            page,
            page_size,
            len(rows),
            total_count,
            int((pytime.monotonic() - started) * 1000),
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )
        return {"rows": rows, "total_count": total_count}

    @api.model
    def fetch_daily_store_facts(self, date_from, date_to, store_eplus_ids=None):
        """Return bounded daily/store aggregates for Odoo-side report reuse.

        date_to is exclusive, matching the dashboard SQL boundary convention.
        The result is intentionally limited to branch/day aggregate facts, not
        raw invoices or sale lines.
        """
        start_dt, end_dt, store_eplus_ids, where_sql, base_params = self._prepare_source_context(
            date_from,
            date_to,
            store_eplus_ids,
        )
        started = pytime.monotonic()
        _logger.info(
            "event=sales_dashboard_service_started operation=fetch_daily_store_facts date_from=%s date_to=%s store_count=%s",
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )

        try:
            with self._dashboard_query_session(where_sql, base_params, start_dt, end_dt, len(store_eplus_ids)) as cursor:
                daily_payload = self._fetch_daily_store_facts_from_cursor(cursor, start_dt, end_dt, len(store_eplus_ids))
                self._validate_daily_fact_row_count(daily_payload, start_dt, end_dt, len(store_eplus_ids))
        except Exception:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.exception(
                "event=sales_dashboard_service_failed operation=fetch_daily_store_facts duration_ms=%s date_from=%s date_to=%s store_count=%s",
                duration_ms,
                start_dt.date(),
                end_dt.date(),
                len(store_eplus_ids),
            )
            raise

        duration_ms = int((pytime.monotonic() - started) * 1000)
        _logger.info(
            "event=sales_dashboard_service_completed operation=fetch_daily_store_facts duration_ms=%s date_from=%s date_to=%s store_count=%s",
            duration_ms,
            start_dt.date(),
            end_dt.date(),
            len(store_eplus_ids),
        )

        return daily_payload

    @api.model
    def fetch_daily_fact_data(self, date_from, date_to, store_eplus_ids=None):
        """Fact-only source path for explicit reconciliation jobs.

        The method intentionally reuses the optimized daily-fact session path
        and does not fetch dashboard-only sections such as users, top items, or
        recent invoices.
        """
        return self.fetch_daily_store_facts(date_from, date_to, store_eplus_ids=store_eplus_ids)

    @api.model
    def _prepare_source_context(self, date_from, date_to, store_eplus_ids=None):
        start_dt, end_dt = self._date_window(date_from, date_to)
        self._validate_dashboard_date_range(start_dt.date(), end_dt.date(), date_to_exclusive=True)
        store_eplus_ids = [int(store_id) for store_id in (store_eplus_ids or []) if store_id]
        where_sql, base_params = self._build_invoice_where(start_dt, end_dt, store_eplus_ids)
        return start_dt, end_dt, store_eplus_ids, where_sql, base_params

    @api.model
    def _fetch_dashboard_from_cursor(self, cursor, start_dt, end_dt, store_eplus_ids):
        store_count = len(store_eplus_ids)
        totals = self._fetch_one(cursor, self._dashboard_totals_sql(), [], "totals", start_dt, end_dt, store_count)
        prev_start, prev_end = self._previous_period(start_dt, end_dt)
        prev_where_sql, prev_params = self._build_invoice_where(prev_start, prev_end, store_eplus_ids)
        previous = self._fetch_one(cursor, self._previous_totals_sql(prev_where_sql), prev_params, "previous_totals", prev_start, prev_end, store_count)
        collections = self._fetch_all(cursor, self._dashboard_collection_sql(), [], "collection", start_dt, end_dt, store_count)
        bearing = self._fetch_one(cursor, self._dashboard_contract_bearing_sql(), [], "contract_bearing", start_dt, end_dt, store_count)
        medicine = self._fetch_all(cursor, self._dashboard_medicine_sql(), [], "medicine_split", start_dt, end_dt, store_count)
        product_kpis = self._fetch_one(cursor, self._dashboard_product_kpis_sql(), [], "product_kpis", start_dt, end_dt, store_count)
        users = self._fetch_all(cursor, self._dashboard_sales_by_user_sql(), [], "users", start_dt, end_dt, store_count)
        items = self._fetch_top_items_from_cursor(cursor, start_dt, end_dt, store_eplus_ids)
        invoices = self._fetch_recent_invoices_from_cursor(cursor, start_dt, end_dt, store_count)
        normalization_started = pytime.monotonic()
        payload = self._normalize_dashboard_payload(
            totals=totals,
            previous=previous,
            collections=collections,
            bearing=bearing,
            medicine=medicine,
            product_kpis=product_kpis,
            users=users,
            items=items,
            invoices=invoices,
            days=max((end_dt.date() - start_dt.date()).days, 1),
        )
        _logger.info(
            "event=sales_dashboard_normalization_completed duration_ms=%s date_from=%s date_to=%s store_count=%s collection_count=%s user_count=%s item_count=%s invoice_count=%s",
            int((pytime.monotonic() - normalization_started) * 1000),
            start_dt.date(),
            end_dt.date(),
            store_count,
            len(collections),
            len(users),
            len(items),
            len(invoices),
        )
        return payload

    @api.model
    def _fetch_daily_store_facts_from_cursor(self, cursor, start_dt, end_dt, store_count):
        store_rows = self._fetch_all(cursor, self._dashboard_daily_store_totals_sql(), [], "daily_store_totals", start_dt, end_dt, store_count)
        medicine_rows = self._fetch_all(cursor, self._dashboard_daily_medicine_sql(), [], "daily_medicine", start_dt, end_dt, store_count)
        collection_rows = self._fetch_all(cursor, self._dashboard_daily_collection_sql(), [], "daily_collection", start_dt, end_dt, store_count)
        user_rows = self._fetch_all(cursor, self._dashboard_daily_user_sql(), [], "daily_user_facts", start_dt, end_dt, store_count)
        item_rows = self._fetch_all(cursor, self._dashboard_daily_item_fact_sql(), [], "daily_item_facts", start_dt, end_dt, store_count)
        merge_started = pytime.monotonic()
        payload = self._merge_daily_store_facts(store_rows, medicine_rows, collection_rows)
        payload["user_facts"] = self._normalize_daily_user_fact_rows(user_rows)
        payload["item_facts"] = self._normalize_daily_item_fact_rows(item_rows)
        _logger.info(
            "event=sales_dashboard_daily_merge_completed duration_ms=%s store_row_count=%s medicine_row_count=%s collection_row_count=%s user_row_count=%s item_row_count=%s output_row_count=%s date_from=%s date_to=%s store_count=%s",
            int((pytime.monotonic() - merge_started) * 1000),
            len(store_rows),
            len(medicine_rows),
            len(collection_rows),
            len(user_rows),
            len(item_rows),
            self._daily_fact_row_count(payload),
            start_dt.date(),
            end_dt.date(),
            store_count,
        )
        return payload

    @api.model
    def _fetch_top_items_from_cursor(self, cursor, start_dt, end_dt, store_eplus_ids):
        store_count = len(store_eplus_ids)
        started = pytime.monotonic()
        self._drop_top_items(cursor, start_dt, end_dt, store_count)
        self._create_top_items(cursor, start_dt, end_dt, store_count)
        rows = self._fetch_all(cursor, self._dashboard_top_items_sql(store_count), store_eplus_ids, "top_items", start_dt, end_dt, store_count)
        _logger.info(
            "event=sales_dashboard_top_items_completed duration_ms=%s row_count=%s date_from=%s date_to=%s store_count=%s",
            int((pytime.monotonic() - started) * 1000),
            len(rows),
            start_dt.date(),
            end_dt.date(),
            store_count,
        )
        return rows

    @api.model
    def _fetch_recent_invoices_from_cursor(self, cursor, start_dt, end_dt, store_count):
        started = pytime.monotonic()
        self._drop_recent_headers(cursor, start_dt, end_dt, store_count)
        self._create_recent_headers(cursor, start_dt, end_dt, store_count)
        rows = self._fetch_all(cursor, self._dashboard_recent_invoices_sql(), [], "recent_invoices", start_dt, end_dt, store_count)
        _logger.info(
            "event=sales_dashboard_recent_invoices_completed duration_ms=%s row_count=%s date_from=%s date_to=%s store_count=%s",
            int((pytime.monotonic() - started) * 1000),
            len(rows),
            start_dt.date(),
            end_dt.date(),
            store_count,
        )
        return rows

    @api.model
    def _daily_fact_row_count(self, daily_payload):
        return (
            len(daily_payload.get("store_facts", []))
            + len(daily_payload.get("collection_facts", []))
            + len(daily_payload.get("user_facts", []))
            + len(daily_payload.get("item_facts", []))
        )

    @api.model
    def _validate_daily_fact_row_count(self, daily_payload, date_from, date_to, store_count):
        row_count = (
            len(daily_payload.get("store_facts", []))
            + len(daily_payload.get("collection_facts", []))
            + len(daily_payload.get("user_facts", []))
        )
        max_rows = self._max_daily_fact_rows()
        if row_count > max_rows:
            _logger.warning(
                "event=sales_dashboard_daily_fact_limit_exceeded row_count=%s max_rows=%s date_from=%s date_to=%s store_count=%s",
                row_count,
                max_rows,
                date_from.date() if hasattr(date_from, "date") else date_from,
                date_to.date() if hasattr(date_to, "date") else date_to,
                store_count,
            )
            raise UserError(_("The generated daily fact rows exceed the configured safety limit of %s rows.") % max_rows)
        item_row_count = len(daily_payload.get("item_facts", []))
        max_item_rows = self._max_daily_item_fact_rows()
        if item_row_count > max_item_rows:
            _logger.warning(
                "event=sales_dashboard_daily_item_fact_limit_exceeded row_count=%s max_rows=%s date_from=%s date_to=%s store_count=%s",
                item_row_count,
                max_item_rows,
                date_from.date() if hasattr(date_from, "date") else date_from,
                date_to.date() if hasattr(date_to, "date") else date_to,
                store_count,
            )
            raise UserError(_("The generated daily item fact rows exceed the configured safety limit of %s rows.") % max_item_rows)
        return True

    @api.model
    @contextmanager
    def _dashboard_query_session(self, where_sql, params, date_from, date_to, store_count):
        cursor = None
        pending_exception = None
        pending_traceback = None
        session_started = pytime.monotonic()
        # The shared connector returns a pooled ConnectionProxy and intentionally
        # keeps it open. The dashboard session owns only this cursor and temp
        # table; it must not close the pooled connection directly.
        with self._dashboard_source_connection() as conn:
            cursor = conn.cursor()
            try:
                self._apply_query_timeout(cursor, "dashboard_session")
                _logger.info(
                    "event=sales_dashboard_session_opened date_from=%s date_to=%s store_count=%s",
                    date_from.date(),
                    date_to.date(),
                    store_count,
                )
                temp_started = pytime.monotonic()
                self._drop_dashboard_temp_tables(cursor, date_from, date_to, store_count, operation="temp_tables_drop_stale")
                self._create_invoice_base(cursor, where_sql, params, date_from, date_to, store_count)
                self._create_invoice_base_indexes(cursor, date_from, date_to, store_count)
                self._create_daily_item_fact(cursor, date_from, date_to, store_count)
                self._create_daily_item_type_fact(cursor, date_from, date_to, store_count)
                _logger.info(
                    "event=sales_dashboard_temp_source_created duration_ms=%s date_from=%s date_to=%s store_count=%s",
                    int((pytime.monotonic() - temp_started) * 1000),
                    date_from.date(),
                    date_to.date(),
                    store_count,
                )
                yield cursor
            except Exception as exc:
                pending_exception = exc
                pending_traceback = exc.__traceback__
            finally:
                cleanup_started = pytime.monotonic()
                try:
                    self._drop_dashboard_temp_tables(cursor, date_from, date_to, store_count, operation="temp_tables_drop_cleanup")
                except Exception:
                    _logger.warning(
                        "event=sales_dashboard_temp_tables_drop_failed date_from=%s date_to=%s store_count=%s",
                        date_from.date(),
                        date_to.date(),
                        store_count,
                        exc_info=True,
                    )
                cleanup_duration_ms = int((pytime.monotonic() - cleanup_started) * 1000)
                _logger.info(
                    "event=sales_dashboard_mssql_cleanup_completed duration_ms=%s date_from=%s date_to=%s store_count=%s",
                    cleanup_duration_ms,
                    date_from.date(),
                    date_to.date(),
                    store_count,
                )
                try:
                    cursor.close()
                except Exception:
                    _logger.warning(
                        "event=sales_dashboard_session_cursor_close_failed date_from=%s date_to=%s store_count=%s",
                        date_from.date(),
                        date_to.date(),
                        store_count,
                        exc_info=True,
                    )
                duration_ms = int((pytime.monotonic() - session_started) * 1000)
                _logger.info(
                    "event=sales_dashboard_session_closed date_from=%s date_to=%s store_count=%s duration_ms=%s connection_owner=ab_eplus_connect_pool",
                    date_from.date(),
                    date_to.date(),
                    store_count,
                    duration_ms,
                )
        if pending_exception:
            raise pending_exception.with_traceback(pending_traceback)

    @api.model
    def _dashboard_source_candidates(self):
        configured = []
        for key in ("bconnect_ip1", "bconnect_ip2"):
            server = config.get(key)
            if server and server not in configured:
                configured.append(server)
        preferred = type(self)._dashboard_preferred_server
        if preferred in configured:
            configured.remove(preferred)
            configured.insert(0, preferred)
        return configured or [None]

    @api.model
    @contextmanager
    def _dashboard_source_connection(self):
        last_error = None
        candidates = self._dashboard_source_candidates()
        with ExitStack() as stack:
            for candidate_number, server in enumerate(candidates, start=1):
                try:
                    connection = stack.enter_context(
                        self.connect_eplus(
                            server=server,
                            param_str="?",
                            charset="CP1256",
                        )
                    )
                except UserError as error:
                    last_error = error
                    _logger.warning(
                        "event=sales_dashboard_source_candidate_unavailable candidate_number=%s candidate_count=%s error_type=%s",
                        candidate_number,
                        len(candidates),
                        type(error).__name__,
                    )
                    continue

                type(self)._dashboard_preferred_server = server
                if candidate_number > 1:
                    _logger.info(
                        "event=sales_dashboard_source_failover_completed candidate_number=%s candidate_count=%s",
                        candidate_number,
                        len(candidates),
                    )
                yield connection
                return

        raise SalesDashboardSourceUnavailableError(
            _("E-Plus is unavailable. Dashboard sync is paused; try again after the connection is restored.")
        ) from last_error

    @api.model
    def _date_window(self, date_from, date_to):
        date_from = self._coerce_dashboard_date(date_from, _("Date From"))
        date_to = self._coerce_dashboard_date(date_to, _("Date To"))
        start_dt = datetime.combine(date_from, time.min)
        end_dt = datetime.combine(date_to, time.min)
        return start_dt, end_dt

    @api.model
    def _previous_period(self, start_dt, end_dt):
        days = max((end_dt.date() - start_dt.date()).days, 1)
        prev_end = start_dt
        prev_start = datetime.combine(fields.Date.subtract(start_dt.date(), days=days), time.min)
        return prev_start, prev_end

    @api.model
    def _build_invoice_where(self, date_from, date_to, store_eplus_ids):
        params = [date_from, date_to]
        where_sql = """
            h.sec_insert_date >= ?
            AND h.sec_insert_date < ?
            AND h.sth_flag = 'C'
        """
        if store_eplus_ids:
            placeholders = ", ".join(["?"] * len(store_eplus_ids))
            where_sql += f"\n            AND h.sto_id IN ({placeholders})"
            params.extend(store_eplus_ids)
        return where_sql, params

    @api.model
    def _invoice_base_table_create_sql(self):
        # Create the temp table in a standalone non-parameterized batch. SQL
        # Server can scope temp tables created by parameterized prepared
        # statements too narrowly for the following index/query statements.
        return """
            CREATE TABLE #invoice_base (
                sth_id BIGINT NOT NULL,
                sto_id INT NOT NULL,
                cust_id BIGINT NULL,
                emp_id INT NULL,
                sec_insert_date DATETIME NULL,
                report_date DATE NOT NULL,
                net_amount DECIMAL(18,2) NOT NULL,
                company_part DECIMAL(18,2) NOT NULL,
                is_delivery BIT NOT NULL,
                is_contract BIT NOT NULL,
                is_offer BIT NOT NULL,
                collection_category VARCHAR(20) NOT NULL
            )
        """

    @api.model
    def _invoice_base_create_sql(self, where_sql):
        return f"""
            INSERT INTO #invoice_base (
                sth_id,
                sto_id,
                cust_id,
                emp_id,
                sec_insert_date,
                report_date,
                net_amount,
                company_part,
                is_delivery,
                is_contract,
                is_offer,
                collection_category
            )
            SELECT
                h.sth_id,
                h.sto_id,
                h.cust_id,
                h.emp_id,
                h.sec_insert_date,
                CAST(h.sec_insert_date AS DATE) AS report_date,
                CAST(ISNULL(h.total_bill_net, 0) AS DECIMAL(18,2)) AS net_amount,
                CAST(ISNULL(h.fh_company_part, 0) AS DECIMAL(18,2)) AS company_part,
                CASE WHEN h.bill_typ = 4 THEN 1 ELSE 0 END AS is_delivery,
                CASE
                    WHEN ISNULL(h.fh_contract_id, 0) <> 0
                      OR ISNULL(h.fh_company_part, 0) <> 0
                      OR NULLIF(LTRIM(RTRIM(ISNULL(h.fh_medins_rec_name, ''))), '') IS NOT NULL
                    THEN 1 ELSE 0
                END AS is_contract,
                CASE
                    WHEN ISNULL(h.total_des_mon, 0) <> 0
                      OR ISNULL(h.total_dis_per, 0) <> 0
                      OR ISNULL(h.sth_pnt_dis, 0) <> 0
                      OR ISNULL(detail_offer.has_detail_discount, 0) = 1
                    THEN 1 ELSE 0
                END AS is_offer,
                CASE
                    WHEN ISNULL(h.total_des_mon, 0) <> 0
                      OR ISNULL(h.total_dis_per, 0) <> 0
                      OR ISNULL(h.sth_pnt_dis, 0) <> 0
                      OR ISNULL(detail_offer.has_detail_discount, 0) = 1
                    THEN 'offer'
                    WHEN ISNULL(h.fh_contract_id, 0) <> 0 OR ISNULL(h.fh_company_part, 0) <> 0
                    THEN 'contract'
                    WHEN h.bill_typ = 4
                    THEN 'delivery'
                    ELSE 'cash'
                END AS collection_category
            FROM r_sales_trans_h h WITH (NOLOCK)
            OUTER APPLY (
                SELECT TOP (1) 1 AS has_detail_discount
                FROM r_sales_trans_d d WITH (NOLOCK)
                WHERE d.sth_id = h.sth_id
                  AND d.std_stock_id = h.sto_id
                  AND (ISNULL(d.itm_dis_mon, 0) <> 0 OR ISNULL(d.itm_dis_per, 0) <> 0)
            ) detail_offer
            WHERE {where_sql}
        """

    @api.model
    def _drop_invoice_base_sql(self):
        return "IF OBJECT_ID('tempdb..#invoice_base') IS NOT NULL DROP TABLE #invoice_base"

    @api.model
    def _drop_dashboard_temp_tables_sql(self):
        return """
            IF OBJECT_ID('tempdb..#top_items') IS NOT NULL DROP TABLE #top_items;
            IF OBJECT_ID('tempdb..#recent_headers') IS NOT NULL DROP TABLE #recent_headers;
            IF OBJECT_ID('tempdb..#daily_item_type_fact') IS NOT NULL DROP TABLE #daily_item_type_fact;
            IF OBJECT_ID('tempdb..#daily_item_fact') IS NOT NULL DROP TABLE #daily_item_fact;
            IF OBJECT_ID('tempdb..#invoice_base') IS NOT NULL DROP TABLE #invoice_base;
        """

    @api.model
    def _create_invoice_base(self, cursor, where_sql, params, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._invoice_base_table_create_sql(),
            [],
            "invoice_base_table_created",
            date_from,
            date_to,
            store_count,
        )
        self._execute_statement(
            cursor,
            self._invoice_base_create_sql(where_sql),
            params,
            "invoice_base_created",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _drop_dashboard_temp_tables(self, cursor, date_from, date_to, store_count, operation):
        self._execute_statement(
            cursor,
            self._drop_dashboard_temp_tables_sql(),
            [],
            operation,
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _drop_invoice_base(self, cursor, date_from, date_to, store_count, operation):
        self._execute_statement(
            cursor,
            self._drop_invoice_base_sql(),
            [],
            operation,
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _daily_item_type_fact_create_sql(self):
        return """
            SELECT
                report_date,
                sto_id,
                item_type,
                ISNULL(SUM(sales_amount), 0) AS sales_amount
            INTO #daily_item_type_fact
            FROM #daily_item_fact
            GROUP BY
                report_date,
                sto_id,
                item_type
        """

    @api.model
    def _daily_item_fact_create_sql(self):
        line_qty = self._normalized_item_quantity_sql("d", "ic")
        line_sales = self._line_sales_amount_sql("d")
        return f"""
            SELECT
                h.report_date,
                h.sto_id,
                d.itm_id AS item_eplus_id,
                MAX(COALESCE(ic.itm_code, CONVERT(VARCHAR(50), d.itm_id))) AS item_code,
                CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END AS item_type,
                ISNULL(SUM({line_qty}), 0) AS sold_qty,
                ISNULL(SUM({line_sales}), 0) AS sales_amount,
                COUNT(DISTINCT d.sth_id) AS invoice_count,
                COUNT(DISTINCT d.sth_id) AS sale_times
            INTO #daily_item_fact
            FROM r_sales_trans_d d WITH (NOLOCK)
            JOIN #invoice_base h ON h.sth_id = d.sth_id AND h.sto_id = d.std_stock_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY
                h.report_date,
                h.sto_id,
                d.itm_id,
                CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END
        """

    @api.model
    def _normalized_item_quantity_sql(self, detail_alias="d", item_alias="ic"):
        return f"""
            CASE {detail_alias}.itm_unit
                WHEN 1 THEN ISNULL({detail_alias}.qnty, 0) - ISNULL({detail_alias}.itm_back, 0)
                WHEN 2 THEN (ISNULL({detail_alias}.qnty, 0) - ISNULL({detail_alias}.itm_back, 0)) / NULLIF({item_alias}.itm_unit1_unit2, 0)
                WHEN 3 THEN (ISNULL({detail_alias}.qnty, 0) - ISNULL({detail_alias}.itm_back, 0)) / NULLIF({item_alias}.itm_unit1_unit3, 0)
                ELSE ISNULL({detail_alias}.qnty, 0) - ISNULL({detail_alias}.itm_back, 0)
            END
        """

    @api.model
    def _line_sales_amount_sql(self, detail_alias="d"):
        return f"""
            ((ISNULL({detail_alias}.qnty, 0) - ISNULL({detail_alias}.itm_back, 0)) * ISNULL({detail_alias}.itm_sell, 0))
            * (1 - (ISNULL({detail_alias}.itm_dis_per, 0) / 100.0))
            - ISNULL({detail_alias}.itm_dis_mon, 0)
        """

    @api.model
    def _create_daily_item_fact(self, cursor, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._daily_item_fact_create_sql(),
            [],
            "daily_item_fact_created",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _create_daily_item_type_fact(self, cursor, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._daily_item_type_fact_create_sql(),
            [],
            "daily_item_type_fact_created",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _drop_top_items_sql(self):
        return "IF OBJECT_ID('tempdb..#top_items') IS NOT NULL DROP TABLE #top_items"

    @api.model
    def _top_items_create_sql(self):
        return """
            SELECT TOP (20)
                item_eplus_id AS itm_id,
                MAX(item_code) AS itm_code,
                ISNULL(SUM(sale_times), 0) AS sale_times,
                ISNULL(SUM(sold_qty), 0) AS sold_qty,
                ISNULL(SUM(sales_amount), 0) AS total_sales
            INTO #top_items
            FROM #daily_item_fact
            GROUP BY item_eplus_id
            ORDER BY sale_times DESC, sold_qty DESC
        """

    @api.model
    def _drop_top_items(self, cursor, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._drop_top_items_sql(),
            [],
            "top_items_drop_stale",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _create_top_items(self, cursor, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._top_items_create_sql(),
            [],
            "top_items_created",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _drop_recent_headers_sql(self):
        return "IF OBJECT_ID('tempdb..#recent_headers') IS NOT NULL DROP TABLE #recent_headers"

    @api.model
    def _recent_headers_create_sql(self):
        return """
            SELECT TOP (20)
                sth_id,
                sto_id,
                cust_id,
                sec_insert_date,
                net_amount
            INTO #recent_headers
            FROM #invoice_base
            ORDER BY sec_insert_date DESC, sth_id DESC, sto_id DESC
        """

    @api.model
    def _drop_recent_headers(self, cursor, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._drop_recent_headers_sql(),
            [],
            "recent_headers_drop_stale",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _create_recent_headers(self, cursor, date_from, date_to, store_count):
        self._execute_statement(
            cursor,
            self._recent_headers_create_sql(),
            [],
            "recent_headers_created",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _create_invoice_base_indexes(self, cursor, date_from, date_to, store_count):
        # High-value join path for medicine, top items, and recent invoices:
        # r_sales_trans_d joins #invoice_base on sth_id + stock/store id.
        self._execute_statement(
            cursor,
            "CREATE CLUSTERED INDEX IX_invoice_base_sth_store ON #invoice_base(sth_id, sto_id)",
            [],
            "invoice_base_index_sth_store",
            date_from,
            date_to,
            store_count,
        )

    @api.model
    def _execute_statement(self, cursor, sql, params, operation, date_from, date_to, store_count):
        started = pytime.monotonic()
        self._apply_query_timeout(cursor, operation)
        try:
            self._cursor_execute(cursor, sql, params)
        except Exception:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.exception(
                "event=sales_dashboard_statement_failed operation=%s duration_ms=%s date_from=%s date_to=%s store_count=%s",
                operation,
                duration_ms,
                date_from.date() if hasattr(date_from, "date") else date_from,
                date_to.date() if hasattr(date_to, "date") else date_to,
                store_count,
            )
            raise

        duration_ms = int((pytime.monotonic() - started) * 1000)
        if operation in ("invoice_base_table_created", "invoice_base_created"):
            event = "sales_dashboard_invoice_base_completed"
        elif operation == "daily_item_fact_created":
            event = "sales_dashboard_daily_item_fact_completed"
        elif operation == "daily_item_type_fact_created":
            event = "sales_dashboard_item_type_fact_completed"
        elif operation.startswith("invoice_base_drop") or operation.startswith("temp_tables_drop"):
            event = "sales_dashboard_temp_tables_dropped"
        elif operation == "recent_headers_created":
            event = "sales_dashboard_recent_headers_completed"
        elif operation == "top_items_created":
            event = "sales_dashboard_top_items_source_completed"
        else:
            event = "sales_dashboard_statement_completed"
        _logger.info(
            "event=%s operation=%s duration_ms=%s date_from=%s date_to=%s store_count=%s",
            event,
            operation,
            duration_ms,
            date_from.date() if hasattr(date_from, "date") else date_from,
            date_to.date() if hasattr(date_to, "date") else date_to,
            store_count,
        )

    @api.model
    def _cursor_execute(self, cursor, sql, params=None):
        if params:
            return cursor.execute(sql, params)
        return cursor.execute(sql)

    @api.model
    def _invoice_base_cte(self, where_sql):
        return f"""
            WITH invoice_base AS (
                SELECT
                    h.sth_id,
                    h.sto_id,
                    h.cust_id,
                    h.emp_id,
                    h.sec_insert_date,
                    CAST(h.sec_insert_date AS DATE) AS report_date,
                    CAST(ISNULL(h.total_bill_net, 0) AS DECIMAL(18,2)) AS net_amount,
                    CAST(ISNULL(h.fh_company_part, 0) AS DECIMAL(18,2)) AS company_part,
                    CASE WHEN h.bill_typ = 4 THEN 1 ELSE 0 END AS is_delivery,
                    CASE
                        WHEN ISNULL(h.fh_contract_id, 0) <> 0
                          OR ISNULL(h.fh_company_part, 0) <> 0
                          OR NULLIF(LTRIM(RTRIM(ISNULL(h.fh_medins_rec_name, ''))), '') IS NOT NULL
                        THEN 1 ELSE 0
                    END AS is_contract,
                    CASE
                        WHEN ISNULL(h.total_des_mon, 0) <> 0
                          OR ISNULL(h.total_dis_per, 0) <> 0
                          OR ISNULL(h.sth_pnt_dis, 0) <> 0
                          OR ISNULL(detail_offer.has_detail_discount, 0) = 1
                        THEN 1 ELSE 0
                    END AS is_offer,
                    CASE
                        WHEN ISNULL(h.total_des_mon, 0) <> 0
                          OR ISNULL(h.total_dis_per, 0) <> 0
                          OR ISNULL(h.sth_pnt_dis, 0) <> 0
                          OR ISNULL(detail_offer.has_detail_discount, 0) = 1
                        THEN 'offer'
                        WHEN ISNULL(h.fh_contract_id, 0) <> 0 OR ISNULL(h.fh_company_part, 0) <> 0
                        THEN 'contract'
                        WHEN h.bill_typ = 4
                        THEN 'delivery'
                        ELSE 'cash'
                    END AS collection_category
                FROM r_sales_trans_h h WITH (NOLOCK)
                OUTER APPLY (
                    SELECT TOP (1) 1 AS has_detail_discount
                    FROM r_sales_trans_d d WITH (NOLOCK)
                    WHERE d.sth_id = h.sth_id
                      AND d.std_stock_id = h.sto_id
                      AND (ISNULL(d.itm_dis_mon, 0) <> 0 OR ISNULL(d.itm_dis_per, 0) <> 0)
                ) detail_offer
                WHERE {where_sql}
            )
        """

    @api.model
    def _dashboard_totals_sql(self):
        return """
            SELECT
                ISNULL(SUM(net_amount), 0) AS total_sales,
                COUNT(*) AS invoice_count
            FROM #invoice_base
        """

    @api.model
    def _dashboard_collection_sql(self):
        return """
            SELECT
                collection_category,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(net_amount), 0) AS total_sales,
                100.0 * SUM(net_amount) / NULLIF((SELECT SUM(net_amount) FROM #invoice_base), 0) AS pct_of_total
            FROM #invoice_base
            GROUP BY collection_category
            ORDER BY total_sales DESC
        """

    @api.model
    def _dashboard_contract_bearing_sql(self):
        return """
            SELECT
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END), 0) AS customer_bearing_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END), 0) AS company_part_amount,
                100.0 * SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END)
                    / NULLIF(SUM(CASE WHEN is_contract = 1 THEN net_amount + company_part ELSE 0 END), 0) AS bearing_pct
            FROM #invoice_base
        """

    @api.model
    def _dashboard_medicine_sql(self):
        return """
            SELECT
                item_type,
                ISNULL(SUM(sales_amount), 0) AS sales_amount
            FROM #daily_item_type_fact
            GROUP BY item_type
        """

    @api.model
    def _dashboard_sales_by_user_sql(self):
        return """
            SELECT TOP (20)
                h.emp_id,
                COALESCE(e.e_name, CONVERT(VARCHAR(20), h.emp_id)) AS employee_name,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(h.net_amount), 0) AS total_sales,
                100.0 * SUM(h.net_amount) / NULLIF((SELECT SUM(net_amount) FROM #invoice_base), 0) AS pct_of_total
            FROM #invoice_base h
            LEFT JOIN employee e WITH (NOLOCK) ON e.e_id = h.emp_id
            GROUP BY h.emp_id, e.e_name
            ORDER BY total_sales DESC
        """

    @api.model
    def _dashboard_top_items_sql(self, store_filter_count):
        stock_filter = ""
        if store_filter_count:
            stock_filter = "AND ics.sto_id IN (" + ", ".join(["?"] * store_filter_count) + ")"
        return f"""
            WITH stock_balance AS (
                SELECT
                    ics.itm_id,
                    SUM(CAST(ics.itm_qty / NULLIF(ic_balance.itm_unit1_unit3, 0) AS DECIMAL(18,2))) AS current_balance
                FROM Item_Class_Store ics WITH (NOLOCK)
                JOIN #top_items t ON t.itm_id = ics.itm_id
                JOIN item_catalog ic_balance WITH (NOLOCK) ON ic_balance.itm_id = ics.itm_id
                WHERE 1 = 1
                {stock_filter}
                GROUP BY ics.itm_id
            )
            SELECT
                t.itm_id,
                t.itm_code,
                t.sale_times,
                t.sold_qty,
                t.total_sales,
                ISNULL(stock.current_balance, 0) AS current_balance
            FROM #top_items t
            LEFT JOIN stock_balance stock ON stock.itm_id = t.itm_id
            ORDER BY t.sale_times DESC, t.sold_qty DESC
        """

    @api.model
    def _dashboard_recent_invoices_sql(self):
        return """
            WITH recent_customer AS (
                SELECT
                    h.sth_id,
                    h.sto_id,
                    h.cust_id,
                    h.sec_insert_date,
                    h.net_amount,
                    COALESCE(
                        NULLIF(LTRIM(RTRIM(delivery.contact)), ''),
                        NULLIF(LTRIM(RTRIM(cd.cd_contact_person)), ''),
                        CASE
                            WHEN NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '') LIKE 'spare%' THEN NULL
                            ELSE NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '')
                        END,
                        NULLIF(LTRIM(RTRIM(cd.cd_tel)), ''),
                        CASE
                            WHEN ISNULL(h.cust_id, 0) = 0 THEN '__cash_customer__'
                            ELSE CONVERT(VARCHAR(20), h.cust_id)
                        END
                    ) AS customer_name
                FROM #recent_headers h
                LEFT JOIN Customer c WITH (NOLOCK) ON c.cust_id = h.cust_id
                LEFT JOIN Customer_Delivery cd WITH (NOLOCK)
                    ON cd.cd_cust_id = h.cust_id
                   AND cd.cd_id = 1
                OUTER APPLY (
                    SELECT TOP (1)
                        sdi.contact
                    FROM sales_deliv_info sdi WITH (NOLOCK)
                    WHERE sdi.sth_id = h.sth_id
                      AND sdi.cust_id = h.cust_id
                    ORDER BY CASE WHEN sdi.cust_id = h.cust_id THEN 0 ELSE 1 END
                ) delivery
            )
            SELECT
                h.sth_id AS invoice_no,
                h.sec_insert_date,
                h.customer_name,
                h.net_amount AS invoice_total,
                COUNT(d.std_id) AS item_count,
                STRING_AGG(CONVERT(NVARCHAR(MAX), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id))), N', ') AS items,
                STRING_AGG(
                    CONVERT(NVARCHAR(MAX), CONCAT(CONVERT(VARCHAR(20), d.itm_id), NCHAR(31), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id)))),
                    NCHAR(30)
                ) AS item_pairs
            FROM recent_customer h
            JOIN r_sales_trans_d d WITH (NOLOCK) ON d.sth_id = h.sth_id AND d.std_stock_id = h.sto_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY h.sth_id, h.sto_id, h.sec_insert_date, h.customer_name, h.net_amount
            ORDER BY h.sec_insert_date DESC, h.sth_id DESC, h.sto_id DESC
        """

    @api.model
    def _dashboard_daily_store_totals_sql(self):
        return """
            SELECT
                report_date,
                sto_id,
                ISNULL(SUM(net_amount), 0) AS total_sales,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END), 0) AS customer_bearing_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END), 0) AS company_part_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount + company_part ELSE 0 END), 0) AS contract_net_amount
            FROM #invoice_base
            GROUP BY report_date, sto_id
        """

    @api.model
    def _dashboard_daily_collection_sql(self):
        return """
            SELECT
                report_date,
                sto_id,
                collection_category,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(net_amount), 0) AS total_sales
            FROM #invoice_base
            GROUP BY report_date, sto_id, collection_category
        """

    @api.model
    def _dashboard_daily_medicine_sql(self):
        return """
            SELECT
                report_date,
                sto_id,
                item_type,
                sales_amount
            FROM #daily_item_type_fact
        """

    @api.model
    def _dashboard_daily_user_sql(self):
        return """
            SELECT
                h.report_date,
                h.sto_id,
                ISNULL(h.emp_id, 0) AS emp_id,
                COALESCE(e.e_name, CONVERT(VARCHAR(20), ISNULL(h.emp_id, 0))) AS employee_name,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(h.net_amount), 0) AS total_sales
            FROM #invoice_base h
            LEFT JOIN employee e WITH (NOLOCK) ON e.e_id = h.emp_id
            GROUP BY h.report_date, h.sto_id, h.emp_id, e.e_name
        """

    @api.model
    def _dashboard_daily_item_fact_sql(self):
        return """
            SELECT
                report_date,
                sto_id,
                item_eplus_id,
                item_code,
                item_type,
                sold_qty,
                sales_amount,
                invoice_count,
                sale_times
            FROM #daily_item_fact
        """

    @api.model
    def _dashboard_product_kpis_sql(self):
        return """
            WITH store_product_counts AS (
                SELECT
                    sto_id,
                    COUNT(DISTINCT item_eplus_id) AS unique_products
                FROM #daily_item_fact
                GROUP BY sto_id
            )
            SELECT
                ISNULL(SUM(sold_qty), 0) AS total_units_sold,
                COUNT(DISTINCT item_eplus_id) AS unique_products_sold,
                ISNULL(SUM(sales_amount), 0) AS total_product_sales,
                1.0 * ISNULL(SUM(sale_times), 0) / NULLIF((SELECT COUNT(*) FROM #invoice_base), 0) AS avg_products_per_invoice,
                COUNT(DISTINCT sto_id) AS stores_with_sales,
                ISNULL((SELECT AVG(1.0 * unique_products) FROM store_product_counts), 0) AS avg_products_sold_per_store
            FROM #daily_item_fact
        """

    @api.model
    def _daily_store_totals_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                report_date,
                sto_id,
                ISNULL(SUM(net_amount), 0) AS total_sales,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END), 0) AS customer_bearing_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END), 0) AS company_part_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount + company_part ELSE 0 END), 0) AS contract_net_amount
            FROM invoice_base
            GROUP BY report_date, sto_id
        """

    @api.model
    def _daily_collection_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                report_date,
                sto_id,
                collection_category,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(net_amount), 0) AS total_sales
            FROM invoice_base
            GROUP BY report_date, sto_id, collection_category
        """

    @api.model
    def _daily_medicine_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                h.report_date,
                h.sto_id,
                CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END AS item_type,
                ISNULL(SUM(
                    ((ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)) * ISNULL(d.itm_sell, 0))
                    * (1 - (ISNULL(d.itm_dis_per, 0) / 100.0))
                    - ISNULL(d.itm_dis_mon, 0)
                ), 0) AS sales_amount
            FROM r_sales_trans_d d WITH (NOLOCK)
            JOIN invoice_base h ON h.sth_id = d.sth_id AND h.sto_id = d.std_stock_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY
                h.report_date,
                h.sto_id,
                CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END
        """

    @api.model
    def _totals_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                ISNULL(SUM(net_amount), 0) AS total_sales,
                COUNT(*) AS invoice_count
            FROM invoice_base
        """

    @api.model
    def _previous_totals_sql(self, where_sql):
        return f"""
            SELECT
                ISNULL(SUM(ISNULL(h.total_bill_net, 0)), 0) AS total_sales,
                COUNT(*) AS invoice_count
            FROM r_sales_trans_h h WITH (NOLOCK)
            WHERE {where_sql}
        """

    @api.model
    def _collection_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                collection_category,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(net_amount), 0) AS total_sales,
                100.0 * SUM(net_amount) / NULLIF((SELECT SUM(net_amount) FROM invoice_base), 0) AS pct_of_total
            FROM invoice_base
            GROUP BY collection_category
            ORDER BY total_sales DESC
        """

    @api.model
    def _contract_bearing_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END), 0) AS customer_bearing_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END), 0) AS company_part_amount,
                100.0 * SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END)
                    / NULLIF(SUM(CASE WHEN is_contract = 1 THEN net_amount + company_part ELSE 0 END), 0) AS bearing_pct
            FROM invoice_base
        """

    @api.model
    def _medicine_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT
                CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END AS item_type,
                ISNULL(SUM(
                    ((ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)) * ISNULL(d.itm_sell, 0))
                    * (1 - (ISNULL(d.itm_dis_per, 0) / 100.0))
                    - ISNULL(d.itm_dis_mon, 0)
                ), 0) AS sales_amount
            FROM r_sales_trans_d d WITH (NOLOCK)
            JOIN invoice_base h ON h.sth_id = d.sth_id AND h.sto_id = d.std_stock_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END
        """

    @api.model
    def _sales_by_user_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            SELECT TOP (20)
                h.emp_id,
                COALESCE(e.e_name, CONVERT(VARCHAR(20), h.emp_id)) AS employee_name,
                COUNT(*) AS invoice_count,
                ISNULL(SUM(h.net_amount), 0) AS total_sales,
                100.0 * SUM(h.net_amount) / NULLIF((SELECT SUM(net_amount) FROM invoice_base), 0) AS pct_of_total
            FROM invoice_base h
            LEFT JOIN employee e WITH (NOLOCK) ON e.e_id = h.emp_id
            GROUP BY h.emp_id, e.e_name
            ORDER BY total_sales DESC
        """

    @api.model
    def _top_items_sql(self, where_sql, store_filter_count):
        stock_filter = ""
        if store_filter_count:
            stock_filter = "AND ics.sto_id IN (" + ", ".join(["?"] * store_filter_count) + ")"
        return self._invoice_base_cte(where_sql) + f"""
            SELECT TOP (20)
                d.itm_id,
                ic.itm_code,
                COUNT(DISTINCT d.sth_id) AS sale_times,
                ISNULL(SUM(CASE d.itm_unit
                    WHEN 1 THEN ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)
                    WHEN 2 THEN (ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)) / NULLIF(ic.itm_unit1_unit2, 0)
                    WHEN 3 THEN (ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)) / NULLIF(ic.itm_unit1_unit3, 0)
                    ELSE ISNULL(d.qnty, 0) - ISNULL(d.itm_back, 0)
                END), 0) AS sold_qty,
                ISNULL(b.balance, 0) AS current_balance
            FROM r_sales_trans_d d WITH (NOLOCK)
            JOIN invoice_base h ON h.sth_id = d.sth_id AND h.sto_id = d.std_stock_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            OUTER APPLY (
                SELECT SUM(CAST(ics.itm_qty / NULLIF(ic_balance.itm_unit1_unit3, 0) AS DECIMAL(18,2))) AS balance
                FROM Item_Class_Store ics WITH (NOLOCK)
                JOIN item_catalog ic_balance WITH (NOLOCK) ON ic_balance.itm_id = ics.itm_id
                WHERE ics.itm_id = d.itm_id
                {stock_filter}
            ) b
            GROUP BY d.itm_id, ic.itm_code, b.balance
            ORDER BY sale_times DESC, sold_qty DESC
        """

    @api.model
    def _recent_invoices_sql(self, where_sql):
        return self._invoice_base_cte(where_sql) + """
            , recent_headers AS (
                SELECT TOP (20)
                    sth_id,
                    sto_id,
                    cust_id,
                    sec_insert_date,
                    net_amount
                FROM invoice_base
                ORDER BY sec_insert_date DESC, sth_id DESC, sto_id DESC
            ),
            recent_customer AS (
                SELECT
                    h.sth_id,
                    h.sto_id,
                    h.cust_id,
                    h.sec_insert_date,
                    h.net_amount,
                    COALESCE(
                        NULLIF(LTRIM(RTRIM(delivery.contact)), ''),
                        NULLIF(LTRIM(RTRIM(cd.cd_contact_person)), ''),
                        CASE
                            WHEN NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '') LIKE 'spare%' THEN NULL
                            ELSE NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '')
                        END,
                        NULLIF(LTRIM(RTRIM(cd.cd_tel)), ''),
                        CASE
                            WHEN ISNULL(h.cust_id, 0) = 0 THEN '__cash_customer__'
                            ELSE CONVERT(VARCHAR(20), h.cust_id)
                        END
                    ) AS customer_name
                FROM recent_headers h
                LEFT JOIN Customer c WITH (NOLOCK) ON c.cust_id = h.cust_id
                LEFT JOIN Customer_Delivery cd WITH (NOLOCK)
                    ON cd.cd_cust_id = h.cust_id
                   AND cd.cd_id = 1
                OUTER APPLY (
                    SELECT TOP (1)
                        sdi.contact
                    FROM sales_deliv_info sdi WITH (NOLOCK)
                    WHERE sdi.sth_id = h.sth_id
                      AND sdi.cust_id = h.cust_id
                    ORDER BY CASE WHEN sdi.cust_id = h.cust_id THEN 0 ELSE 1 END
                ) delivery
            )
            SELECT
                h.sth_id AS invoice_no,
                h.sec_insert_date,
                h.customer_name,
                h.net_amount AS invoice_total,
                COUNT(d.std_id) AS item_count,
                STRING_AGG(CONVERT(NVARCHAR(MAX), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id))), N', ') AS items,
                STRING_AGG(
                    CONVERT(NVARCHAR(MAX), CONCAT(CONVERT(VARCHAR(20), d.itm_id), NCHAR(31), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id)))),
                    NCHAR(30)
                ) AS item_pairs
            FROM recent_customer h
            JOIN r_sales_trans_d d WITH (NOLOCK) ON d.sth_id = h.sth_id AND d.std_stock_id = h.sto_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY h.sth_id, h.sto_id, h.sec_insert_date, h.customer_name, h.net_amount
            ORDER BY h.sec_insert_date DESC, h.sth_id DESC, h.sto_id DESC
        """

    @api.model
    def _customer_sales_page_sql(self, where_sql, has_search=False):
        search_sql = ""
        if has_search:
            search_sql = """
                WHERE CONVERT(NVARCHAR(100), h.sth_id) LIKE ?
                   OR h.customer_name LIKE ?
                   OR EXISTS (
                        SELECT 1
                        FROM r_sales_trans_d search_d WITH (NOLOCK)
                        JOIN item_catalog search_ic WITH (NOLOCK) ON search_ic.itm_id = search_d.itm_id
                        WHERE search_d.sth_id = h.sth_id
                          AND search_d.std_stock_id = h.sto_id
                          AND CONVERT(NVARCHAR(100), search_ic.itm_code) LIKE ?
                   )
            """
        return f"""
            WITH invoice_headers AS (
                SELECT
                    h.sth_id,
                    h.sto_id,
                    h.cust_id,
                    h.sec_insert_date,
                    CAST(ISNULL(h.total_bill_net, 0) AS DECIMAL(18,2)) AS net_amount
                FROM r_sales_trans_h h WITH (NOLOCK)
                WHERE {where_sql}
            ),
            resolved_customer AS (
                SELECT
                    h.sth_id,
                    h.sto_id,
                    h.cust_id,
                    h.sec_insert_date,
                    h.net_amount,
                    COALESCE(
                        NULLIF(LTRIM(RTRIM(delivery.contact)), ''),
                        NULLIF(LTRIM(RTRIM(cd.cd_contact_person)), ''),
                        CASE
                            WHEN NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '') LIKE 'spare%' THEN NULL
                            ELSE NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '')
                        END,
                        NULLIF(LTRIM(RTRIM(cd.cd_tel)), ''),
                        CASE
                            WHEN ISNULL(h.cust_id, 0) = 0 THEN '__cash_customer__'
                            ELSE CONVERT(VARCHAR(20), h.cust_id)
                        END
                    ) AS customer_name
                FROM invoice_headers h
                LEFT JOIN Customer c WITH (NOLOCK) ON c.cust_id = h.cust_id
                LEFT JOIN Customer_Delivery cd WITH (NOLOCK)
                    ON cd.cd_cust_id = h.cust_id
                   AND cd.cd_id = 1
                OUTER APPLY (
                    SELECT TOP (1) sdi.contact
                    FROM sales_deliv_info sdi WITH (NOLOCK)
                    WHERE sdi.sth_id = h.sth_id
                      AND sdi.cust_id = h.cust_id
                    ORDER BY CASE WHEN sdi.cust_id = h.cust_id THEN 0 ELSE 1 END
                ) delivery
            ),
            filtered_customer AS (
                SELECT h.*
                FROM resolved_customer h
                {search_sql}
            ),
            paged_customer AS (
                SELECT h.*, COUNT(*) OVER() AS total_count
                FROM filtered_customer h
                ORDER BY h.sec_insert_date DESC, h.sth_id DESC, h.sto_id DESC
                OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            )
            SELECT
                h.sth_id AS invoice_no,
                h.sto_id,
                h.sec_insert_date,
                h.customer_name,
                h.net_amount AS invoice_total,
                h.total_count,
                COUNT(d.std_id) AS item_count,
                STRING_AGG(
                    CONVERT(NVARCHAR(MAX), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id))),
                    N', '
                ) AS items,
                STRING_AGG(
                    CONVERT(NVARCHAR(MAX), CONCAT(
                        CONVERT(VARCHAR(20), d.itm_id),
                        NCHAR(31),
                        COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id))
                    )),
                    NCHAR(30)
                ) AS item_pairs
            FROM paged_customer h
            JOIN r_sales_trans_d d WITH (NOLOCK)
              ON d.sth_id = h.sth_id
             AND d.std_stock_id = h.sto_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY
                h.sth_id,
                h.sto_id,
                h.sec_insert_date,
                h.customer_name,
                h.net_amount,
                h.total_count
            ORDER BY h.sec_insert_date DESC, h.sth_id DESC, h.sto_id DESC
        """

    @api.model
    def _fetch_one(self, cursor, sql, params, operation, date_from, date_to, store_count):
        rows = self._fetch_all(cursor, sql, params, operation, date_from, date_to, store_count)
        return rows[0] if rows else {}

    @api.model
    def _fetch_all(self, cursor, sql, params, operation, date_from, date_to, store_count):
        started = pytime.monotonic()
        self._apply_query_timeout(cursor, operation)
        try:
            self._cursor_execute(cursor, sql, params)
            columns = [column[0].lower() for column in (cursor.description or [])]
            rows = [self._normalize_row(row, columns) for row in cursor.fetchall()]
        except Exception:
            duration_ms = int((pytime.monotonic() - started) * 1000)
            _logger.exception(
                "event=sales_dashboard_query_failed operation=%s duration_ms=%s date_from=%s date_to=%s store_count=%s",
                operation,
                duration_ms,
                date_from.date() if hasattr(date_from, "date") else date_from,
                date_to.date() if hasattr(date_to, "date") else date_to,
                store_count,
            )
            raise
        duration_ms = int((pytime.monotonic() - started) * 1000)
        _logger.info(
            "event=sales_dashboard_query_completed operation=%s duration_ms=%s row_count=%s date_from=%s date_to=%s store_count=%s",
            operation,
            duration_ms,
            len(rows),
            date_from.date() if hasattr(date_from, "date") else date_from,
            date_to.date() if hasattr(date_to, "date") else date_to,
            store_count,
        )
        return rows

    @api.model
    def _apply_query_timeout(self, cursor, operation):
        timeout = self._query_timeout_seconds()
        if not hasattr(cursor, "timeout"):
            _logger.info(
                "event=sales_dashboard_query_timeout_unsupported operation=%s timeout_seconds=%s",
                operation,
                timeout,
            )
            return False
        try:
            cursor.timeout = timeout
        except Exception:
            _logger.exception(
                "event=sales_dashboard_query_timeout_failed operation=%s timeout_seconds=%s",
                operation,
                timeout,
            )
            return False
        return True

    @api.model
    def _normalize_row(self, row, columns):
        if isinstance(row, dict):
            row = {str(key).lower(): value for key, value in row.items()}
        else:
            row = dict(zip(columns, row))
        return {key: self._json_safe_value(value) for key, value in row.items()}

    @api.model
    def _json_safe_value(self, value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime,)):
            return fields.Datetime.to_string(value)
        return value

    @api.model
    def _daily_key(self, row):
        return (fields.Date.to_date(row.get("report_date")), int(row.get("sto_id") or 0))

    @api.model
    def _merge_daily_store_facts(self, store_rows, medicine_rows, collection_rows):
        facts = {}
        for row in store_rows:
            key = self._daily_key(row)
            facts[key] = {
                "report_date": key[0],
                "store_eplus_id": key[1],
                "total_sales": float(row.get("total_sales") or 0.0),
                "invoice_count": int(row.get("invoice_count") or 0),
                "medicine_sales": 0.0,
                "non_medicine_sales": 0.0,
                "customer_bearing_amount": float(row.get("customer_bearing_amount") or 0.0),
                "company_part_amount": float(row.get("company_part_amount") or 0.0),
                "contract_net_amount": float(row.get("contract_net_amount") or 0.0),
            }

        for row in medicine_rows:
            key = self._daily_key(row)
            fact = facts.setdefault(key, {
                "report_date": key[0],
                "store_eplus_id": key[1],
                "total_sales": 0.0,
                "invoice_count": 0,
                "medicine_sales": 0.0,
                "non_medicine_sales": 0.0,
                "customer_bearing_amount": 0.0,
                "company_part_amount": 0.0,
                "contract_net_amount": 0.0,
            })
            if row.get("item_type") == "non_medicine":
                fact["non_medicine_sales"] += float(row.get("sales_amount") or 0.0)
            else:
                fact["medicine_sales"] += float(row.get("sales_amount") or 0.0)

        return {
            "store_facts": list(facts.values()),
            "collection_facts": [{
                "report_date": fields.Date.to_date(row.get("report_date")),
                "store_eplus_id": int(row.get("sto_id") or 0),
                "category": row.get("collection_category") or "cash",
                "invoice_count": int(row.get("invoice_count") or 0),
                "total_sales": float(row.get("total_sales") or 0.0),
            } for row in collection_rows],
        }

    @api.model
    def _normalize_daily_user_fact_rows(self, user_rows):
        rows = []
        for row in user_rows:
            invoice_count = int(row.get("invoice_count") or 0)
            if not invoice_count:
                continue
            rows.append({
                "report_date": fields.Date.to_date(row.get("report_date")),
                "store_eplus_id": int(row.get("sto_id") or 0),
                "employee_eplus_id": int(row.get("emp_id") or 0),
                "employee_name": row.get("employee_name") or "",
                "invoice_count": invoice_count,
                "total_sales": float(row.get("total_sales") or 0.0),
            })
        return rows

    @api.model
    def _normalize_daily_item_fact_rows(self, item_rows):
        rows = []
        for row in item_rows:
            rows.append({
                "report_date": fields.Date.to_date(row.get("report_date")),
                "store_eplus_id": int(row.get("sto_id") or 0),
                "item_eplus_id": int(row.get("item_eplus_id") or 0),
                "item_code": row.get("item_code") or "",
                "item_type": row.get("item_type") or "medicine",
                "sold_qty": float(row.get("sold_qty") or 0.0),
                "sales_amount": float(row.get("sales_amount") or 0.0),
                "invoice_count": int(row.get("invoice_count") or 0),
                "sale_times": int(row.get("sale_times") or 0),
            })
        return rows

    @api.model
    def _normalize_dashboard_payload(self, totals, previous, collections, bearing, medicine, users, items, invoices, days, product_kpis=None):
        product_kpis = product_kpis or {}
        total_sales = float(totals.get("total_sales") or 0.0)
        prev_total_sales = float(previous.get("total_sales") or 0.0)
        avg_daily_sales = total_sales / days if days else 0.0
        prev_avg_daily_sales = prev_total_sales / days if days else 0.0
        avg_daily_growth_pct = 0.0
        if prev_avg_daily_sales:
            avg_daily_growth_pct = 100.0 * (avg_daily_sales - prev_avg_daily_sales) / prev_avg_daily_sales

        medicine_sales = 0.0
        non_medicine_sales = 0.0
        for row in medicine:
            if row.get("item_type") == "non_medicine":
                non_medicine_sales += float(row.get("sales_amount") or 0.0)
            else:
                medicine_sales += float(row.get("sales_amount") or 0.0)

        return {
            "total_sales": total_sales,
            "avg_daily_sales": avg_daily_sales,
            "prev_avg_daily_sales": prev_avg_daily_sales,
            "avg_daily_growth_pct": avg_daily_growth_pct,
            "invoice_count": int(totals.get("invoice_count") or 0),
            "medicine_sales": medicine_sales,
            "non_medicine_sales": non_medicine_sales,
            "customer_bearing_amount": float(bearing.get("customer_bearing_amount") or 0.0),
            "company_part_amount": float(bearing.get("company_part_amount") or 0.0),
            "bearing_pct": float(bearing.get("bearing_pct") or 0.0),
            "total_units_sold": float(product_kpis.get("total_units_sold") or 0.0),
            "unique_products_sold": int(product_kpis.get("unique_products_sold") or 0),
            "total_product_sales": float(product_kpis.get("total_product_sales") or 0.0),
            "avg_products_per_invoice": float(product_kpis.get("avg_products_per_invoice") or 0.0),
            "stores_with_sales": int(product_kpis.get("stores_with_sales") or 0),
            "avg_products_sold_per_store": float(product_kpis.get("avg_products_sold_per_store") or 0.0),
            "collection_lines": self._normalize_collection_lines(collections),
            "user_lines": users,
            "item_lines": items,
            "invoice_lines": self._normalize_invoice_lines(invoices),
        }

    @api.model
    def _normalize_collection_lines(self, collections):
        category_order = ["cash", "delivery", "contract", "offer"]
        by_category = {}
        for row in collections:
            category = row.get("collection_category") or row.get("category") or "cash"
            data = by_category.setdefault(category, {
                "collection_category": category,
                "invoice_count": 0,
                "total_sales": 0.0,
                "pct_of_total": 0.0,
            })
            data["invoice_count"] += int(row.get("invoice_count") or 0)
            data["total_sales"] += float(row.get("total_sales") or 0.0)
            data["pct_of_total"] += float(row.get("pct_of_total") or 0.0)

        for category in category_order:
            by_category.setdefault(category, {
                "collection_category": category,
                "invoice_count": 0,
                "total_sales": 0.0,
                "pct_of_total": 0.0,
            })

        return sorted(
            by_category.values(),
            key=lambda item: (-float(item.get("total_sales") or 0.0), category_order.index(item["collection_category"]) if item["collection_category"] in category_order else len(category_order)),
        )

    @api.model
    def _normalize_invoice_lines(self, invoices):
        parsed_by_row = []
        all_item_ids = []
        for row in invoices:
            parsed = self._parse_invoice_item_pairs(row.get("item_pairs"))
            parsed_by_row.append(parsed)
            all_item_ids.extend(item_id for item_id, _code in parsed)
        names_by_serial = self._invoice_item_names_by_serial(all_item_ids)

        normalized = []
        for row, parsed_pairs in zip(invoices, parsed_by_row):
            line = dict(row)
            line.pop("item_pairs", None)
            line["items"] = self._invoice_item_names_summary_from_pairs(parsed_pairs, line.get("items"), names_by_serial)
            if (line.get("customer_name") or "").strip() == "__cash_customer__":
                line["customer_name"] = _("Cash Customer")
            normalized.append(line)
        return normalized

    @api.model
    def _invoice_item_names_summary(self, item_pairs, fallback_items):
        parsed_pairs = self._parse_invoice_item_pairs(item_pairs)
        if not parsed_pairs:
            return fallback_items or ""
        names_by_serial = self._invoice_item_names_by_serial([item_id for item_id, _code in parsed_pairs])
        return self._invoice_item_names_summary_from_pairs(parsed_pairs, fallback_items, names_by_serial)

    @api.model
    def _invoice_item_names_summary_from_pairs(self, parsed_pairs, fallback_items, names_by_serial):
        if not parsed_pairs:
            return fallback_items or ""
        return ", ".join(
            names_by_serial.get(item_id) or item_code or str(item_id)
            for item_id, item_code in parsed_pairs
        )

    @api.model
    def _parse_invoice_item_pairs(self, item_pairs):
        if not item_pairs:
            return []
        parsed = []
        for token in str(item_pairs).split("\x1e"):
            token = token.strip()
            if not token:
                continue
            raw_item_id, separator, item_code = token.partition("\x1f")
            try:
                item_id = int(raw_item_id or 0)
            except (TypeError, ValueError):
                item_id = 0
            if item_id:
                parsed.append((item_id, item_code if separator else ""))
        return parsed

    @api.model
    def _invoice_item_names_by_serial(self, item_ids):
        clean_ids = sorted({int(item_id) for item_id in item_ids if item_id})
        if not clean_ids:
            return {}
        products = self.env["ab_product"].sudo().with_context(active_test=False).search([
            ("eplus_serial", "in", clean_ids),
        ])
        names_by_serial = {}
        for product in products:
            item_id = int(product.eplus_serial or 0)
            if item_id and item_id not in names_by_serial:
                names_by_serial[item_id] = product.name or product.display_name
        return names_by_serial
