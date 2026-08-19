# -*- coding: utf-8 -*-
import logging
import threading
from datetime import timedelta
from datetime import datetime as dt

from odoo import SUPERUSER_ID, api, fields, models, _
from odoo.exceptions import UserError
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 10
CACHE_STALE_MINUTES = 15
REFRESH_BATCH_SIZE = 20

MOVEMENT_GROUP_SELECTION = [
    ("sale", "Sales / Return"),
    ("purchase", "Purchase / Return"),
    ("transfer", "Transfer / From / To"),
]

MOVEMENT_SELECTION = [
    ("purchase", "Purchase"),
    ("purchase_return", "Purchase Return"),
    ("sale", "Sale"),
    ("sale_return", "Sale Return"),
    ("transfer_out", "Transfer Out"),
    ("transfer_in", "Transfer In"),
]

MOVEMENT_SORT = {
    "sale": 10,
    "sale_return": 20,
    "purchase": 30,
    "purchase_return": 40,
    "transfer_out": 50,
    "transfer_in": 60,
}

_REFRESH_WORKER_LOCK = threading.Lock()
_REFRESH_WORKER_RUNNING = False


class AbStockReportCacheLine(models.Model):
    _name = "ab_stock_report_cache_line"
    _inherit = "ab_eplus_connect"
    _description = "Stock Movement JSON Cache"

    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_eplus_serial = fields.Integer(
        string="EPlus Serial",
        required=True,
        index=True,
    )
    cache_limit = fields.Integer(
        string="Cache Limit",
        required=True,
        index=True,
    )
    movement_group = fields.Selection(
        MOVEMENT_GROUP_SELECTION,
        string="Movement Group",
        required=True,
        index=True,
    )
    movement_type = fields.Selection(
        MOVEMENT_SELECTION,
        string="Movement Type",
        index=True,
    )
    movement_datetime = fields.Datetime(
        string="Movement Date",
        index=True,
    )
    movement_sort = fields.Integer(
        string="Movement Sort",
        required=True,
        default=0,
        index=True,
    )
    sale_price = fields.Float(
        string="Sale Price",
        digits=(16, 4),
    )
    qty_large = fields.Float(
        string="Quantity in Large Unit",
        digits=(16, 4),
    )
    store_name = fields.Char(
        string="Store",
    )
    supplier_name = fields.Char(
        string="Supplier",
    )
    customer_name = fields.Char(
        string="Customer",
    )
    employee_name = fields.Char(
        string="Employee",
    )
    source_table = fields.Char(
        string="Source Table",
        index=True,
    )
    source_line_id = fields.Char(
        string="Source Line ID",
        index=True,
    )
    source_updated_at = fields.Datetime(
        string="Source Updated At",
        index=True,
    )
    cache_generated_at = fields.Datetime(
        string="Cache Generated At",
        index=True,
    )
    cache_payload = fields.Json(
        string="Cached JSON Payload",
        readonly=True,
        default=list,
    )

    @api.model
    def _normalize_limit(self, limit):
        try:
            limit_value = int(limit or DEFAULT_LIMIT)
        except Exception:
            limit_value = DEFAULT_LIMIT
        return max(limit_value, 1)

    @api.model
    def _resolve_product(self, product):
        if hasattr(product, "_name"):
            product_rec = product[:1]
        elif product:
            product_rec = self.env["ab_product"].browse(int(product)).exists()
        else:
            product_rec = self.env["ab_product"]
        if not product_rec:
            raise UserError(_("This product is not linked to an EPlus item serial."))
        return product_rec

    @api.model
    def is_refresh_needed(self, product_serial, limit, movement_group=None):
        limit_value = self._normalize_limit(limit)
        cutoff = fields.Datetime.now() - timedelta(minutes=CACHE_STALE_MINUTES)
        domain = [
            ("product_eplus_serial", "=", int(product_serial or 0)),
            ("cache_limit", "=", limit_value),
        ]
        if movement_group:
            domain.append(("movement_group", "=", movement_group))
        exact_count = self.search_count(domain)
        if not exact_count:
            return True
        last_row = self.search(domain, order="cache_generated_at desc, movement_datetime desc, id desc", limit=1)
        if not last_row:
            return True
        return bool(last_row.cache_generated_at and last_row.cache_generated_at < cutoff)

    @api.model
    def get_display_rows(self, product_serial, limit, movement_group=None):
        limit_value = self._normalize_limit(limit)
        product_serial = int(product_serial or 0)
        rows = []
        last_refresh = False
        state_bits = []

        groups = MOVEMENT_GROUP_SELECTION
        if movement_group:
            groups = [item for item in groups if item[0] == movement_group]

        for movement_group, label in groups:
            exact_domain = [
                ("product_eplus_serial", "=", product_serial),
                ("cache_limit", "=", limit_value),
                ("movement_group", "=", movement_group),
            ]
            cache_record = self.search(
                exact_domain,
                order="cache_generated_at desc, id desc",
                limit=1,
            )
            if cache_record:
                group_rows = self._rows_from_json(cache_record.cache_payload)
                state_bits.append(_("Cached %s") % label)
                rows.extend(group_rows)
                generated_at = cache_record.cache_generated_at
                if generated_at and (not last_refresh or generated_at > last_refresh):
                    last_refresh = generated_at
            else:
                state_bits.append(_("No %s cache") % label)

        rows = sorted(
            rows,
            key=lambda row: (
                row["movement_datetime"] or dt.min,
                self._sort_line_id(row["source_line_id"]),
                row["movement_sort"],
            ),
            reverse=True,
        )
        state = ", ".join(state_bits) if state_bits else _("No cached movements yet")
        return rows, state, last_refresh

    @api.model
    def refresh_product_cache(self, product, limit, force=False, movement_group=None):
        product_rec = self._resolve_product(product)
        limit_value = self._normalize_limit(limit)
        if not product_rec.eplus_serial:
            raise UserError(_("This product is not linked to an EPlus item serial."))

        cache_generated_at = fields.Datetime.now()
        movement_groups = [movement_group] if movement_group else ["sale", "purchase", "transfer"]
        total_rows = 0
        for group in movement_groups:
            rows = self._fetch_group_rows(
                product_rec.eplus_serial,
                limit_value,
                movement_group=group,
            )
            self._replace_group_cache(product_rec, limit_value, group, rows, cache_generated_at)
            total_rows += len(rows)
        return {
            "product_id": product_rec.id,
            "product_eplus_serial": product_rec.eplus_serial,
            "limit": limit_value,
            "rows": total_rows,
            "cache_generated_at": cache_generated_at,
        }

    @api.model
    def _fetch_group_rows(self, product_serial, limit_value, movement_group, from_date=None, offset=0):
        offset = max(int(offset or 0), 0)
        fetch_limit = limit_value + offset
        if movement_group == "sale":
            with self.connect_eplus(param_str="?") as connection:
                rows = self._fetch_sales_batch_rows_with_connection(
                    product_serial,
                    fetch_limit,
                    return_only=None,
                    from_date=from_date,
                    connection=connection,
                )
            return self._sort_group_rows(rows)[offset:offset + limit_value]
        fetchers = {
            "sale": (
                self._fetch_sales_rows,
                self._fetch_sale_return_rows,
            ),
            "purchase": (
                self._fetch_purchase_rows,
                self._fetch_purchase_return_rows,
            ),
            "transfer": (
                self._fetch_transfer_out_rows,
                self._fetch_transfer_in_rows,
            ),
        }.get(movement_group)
        if not fetchers:
            return []
        return self._fetch_family_rows(
            product_serial,
            fetch_limit,
            movement_group=movement_group,
            fetchers=fetchers,
            from_date=from_date,
            offset=offset,
            page_limit=limit_value,
        )

    def _sort_group_rows(self, rows):
        return sorted(
            rows,
            key=lambda row: (
                row["movement_datetime"] or dt.min,
                self._sort_line_id(row["source_line_id"]),
                row["movement_sort"],
            ),
            reverse=True,
        )

    @api.model
    def _replace_group_cache(self, product, limit_value, movement_group, rows, cache_generated_at):
        domain = [
            ("product_eplus_serial", "=", product.eplus_serial),
            ("cache_limit", "=", limit_value),
            ("movement_group", "=", movement_group),
        ]
        self.search(domain).unlink()
        self.create({
            "product_id": product.id,
            "product_eplus_serial": product.eplus_serial,
            "cache_limit": limit_value,
            "movement_group": movement_group,
            "cache_generated_at": cache_generated_at,
            "cache_payload": [self._row_to_json(row) for row in rows],
        })

    @staticmethod
    def _row_to_json(row):
        result = dict(row)
        for key in ("movement_datetime", "source_updated_at"):
            if result.get(key):
                result[key] = fields.Datetime.to_string(result[key])
        return result

    @staticmethod
    def _rows_from_json(payload):
        rows = []
        for row in payload or []:
            row = dict(row)
            for key in ("movement_datetime", "source_updated_at"):
                if row.get(key):
                    row[key] = fields.Datetime.to_datetime(row[key])
            rows.append(row)
        return rows

    @api.model
    def _fetch_family_rows(
            self, product_serial, limit_value, movement_group, fetchers, from_date=None, offset=0, page_limit=None
    ):
        rows = []
        for fetcher in fetchers:
            rows.extend(fetcher(product_serial, limit_value, from_date=from_date))
        rows = sorted(
            rows,
            key=lambda row: (
                row["movement_datetime"] or dt.min,
                self._sort_line_id(row["source_line_id"]),
                row["movement_sort"],
            ),
            reverse=True,
        )
        page_limit = page_limit or limit_value
        return rows[offset:offset + page_limit]

    @staticmethod
    def _sort_line_id(value):
        try:
            return int(value or 0)
        except Exception:
            return 0

    @staticmethod
    def _sql_placeholders(values):
        return ", ".join("?" for _value in values)

    @api.model
    def _run_raw_query(self, query, params, connection=None):
        if connection is not None:
            with connection.cursor() as cursor:
                cursor.execute(query, tuple(params))
                return cursor.fetchall() or []
        with self.connect_eplus(param_str="?") as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, tuple(params))
                return cursor.fetchall() or []

    @api.model
    def _fetch_sales_batch_rows(self, product_serial, limit_value, return_only=False, from_date=None):
        with self.connect_eplus(param_str="?") as connection:
            return self._fetch_sales_batch_rows_with_connection(
                product_serial,
                limit_value,
                return_only=return_only,
                from_date=from_date,
                connection=connection,
            )

    @api.model
    def _fetch_sales_batch_rows_with_connection(
            self, product_serial, limit_value, return_only=False, from_date=None, connection=None
    ):
        # Fetch detail rows first. Header and lookup tables are loaded in batches
        # below, avoiding repeated dimension-table joins for every detail row.
        candidate_limit = max(limit_value * 5, 50)
        return_filter = "AND sd.sec_update_date IS NOT NULL AND ISNULL(sd.itm_back, 0) > 0" if return_only is True else ""
        date_filter = "AND sd.sec_update_date >= ?" if from_date else ""
        detail_query = f"""
            SELECT TOP (?)
                sd.std_id, sd.sth_id, sd.std_stock_id, sd.itm_unit,
                sd.qnty, sd.itm_sell, sd.itm_back_price, sd.itm_back,
                sd.sec_update_date
            FROM r_sales_trans_d sd WITH (NOLOCK)
            WHERE sd.itm_id = ?
              AND sd.sec_update_date IS NOT NULL
              {return_filter}
              {date_filter}
            ORDER BY sd.sec_update_date DESC
        """
        detail_params = [candidate_limit, product_serial]
        if from_date:
            detail_params.append(from_date)
        detail_rows = self._run_raw_query(
            detail_query,
            detail_params,
            connection=connection,
        )
        if not detail_rows:
            return []

        header_keys = list(dict.fromkeys((row[1], row[2]) for row in detail_rows))
        pair_sql = " OR ".join("(sh.sth_id = ? AND sh.sto_id = ?)" for _key in header_keys)
        header_query = f"""
            SELECT sh.sth_id, sh.sto_id, sh.cust_id, sh.emp_id, sh.sth_flag
            FROM r_sales_trans_h sh WITH (NOLOCK)
            WHERE {pair_sql}
        """
        header_rows = self._run_raw_query(
            header_query,
            [value for key in header_keys for value in key],
            connection=connection,
        )
        headers = {
            (row[0], row[1]): {
                "cust_id": row[2],
                "emp_id": row[3],
                "valid": row[4] == "C",
            }
            for row in header_rows
        }
        detail_rows = [
            row for row in detail_rows
            if headers.get((row[1], row[2]), {}).get("valid")
        ]
        if not detail_rows:
            return []

        store_ids = list(dict.fromkeys(row[2] for row in detail_rows))
        customer_ids = list(dict.fromkeys(
            headers[(row[1], row[2])]["cust_id"]
            for row in detail_rows
            if headers[(row[1], row[2])]["cust_id"] is not None
        ))
        employee_ids = list(dict.fromkeys(
            headers[(row[1], row[2])]["emp_id"]
            for row in detail_rows
            if headers[(row[1], row[2])]["emp_id"] is not None
        ))

        stores = self._fetch_sales_lookup(
            "Store", "sto_id", "sto_name_ar, sto_name_en", store_ids, connection,
        )
        customers = self._fetch_sales_lookup(
            "Customer", "cust_id", "cust_name_ar, cust_name_en", customer_ids, connection,
        )
        employees = self._fetch_sales_lookup(
            "Employee", "e_id", "e_Name", employee_ids, connection,
        )
        item_rows = self._run_raw_query(
            """
            SELECT itm_id, itm_unit1_unit2, itm_unit1_unit3
            FROM Item_Catalog WITH (NOLOCK)
            WHERE itm_id = ?
            """,
            (product_serial,),
            connection=connection,
        )
        item_units = {
            row[0]: (row[1], row[2])
            for row in item_rows
        }.get(product_serial, (None, None))

        result = []
        modes = [return_only] if return_only is not None else [False, True]
        for return_mode in modes:
            movement_type = "sale_return" if return_mode else "sale"
            movement_sort = 20 if return_mode else 10
            for row in detail_rows:
                header = headers[(row[1], row[2])]
                quantity = row[7] if return_mode else row[4]
                if return_mode and not quantity:
                    continue
                movement_datetime = row[8]
                if not self._date_matches(movement_datetime, from_date):
                    continue
                result.append({
                    "movement_group": "sale",
                    "movement_type": movement_type,
                    "movement_datetime": movement_datetime,
                    "sale_price": float((row[6] if return_mode else row[5]) or 0.0),
                    "qty_large": self._sales_quantity_in_large_unit(
                        quantity, row[3], item_units[0], item_units[1], negate=not return_mode,
                    ),
                    "store_name": self._lookup_name(stores.get(row[2]), row[2]),
                    "supplier_name": "",
                    "customer_name": self._lookup_name(customers.get(header["cust_id"]), header["cust_id"]),
                    "employee_name": self._lookup_name(employees.get(header["emp_id"]), header["emp_id"]),
                    "source_table": "r_sales_trans_d",
                    "source_line_id": str(row[0] or ""),
                    "source_updated_at": row[8],
                    "movement_sort": movement_sort,
                })
        result.sort(
            key=lambda row: (
                row["movement_datetime"] or dt.min,
                self._sort_line_id(row["source_line_id"]),
            ),
            reverse=True,
        )
        return result[:limit_value]

    @api.model
    def _fetch_sales_lookup(self, table, key_field, value_fields, values, connection=None):
        if not values:
            return {}
        placeholders = self._sql_placeholders(values)
        rows = self._run_raw_query(
            f"SELECT {key_field}, {value_fields} FROM {table} WITH (NOLOCK) WHERE {key_field} IN ({placeholders})",
            values,
            connection=connection,
        )
        return {row[0]: row[1:] for row in rows}

    @staticmethod
    def _lookup_name(value, fallback):
        if value:
            for part in value:
                if part not in (None, ""):
                    return str(part)
        return str(fallback or "")

    @staticmethod
    def _sales_quantity_in_large_unit(quantity, unit, unit2, unit3, negate=False):
        quantity = float(quantity or 0.0)
        divisor = {2: unit2, 3: unit3}.get(unit)
        if unit in (2, 3) and divisor:
            quantity /= float(divisor)
        return -quantity if negate else quantity

    @staticmethod
    def _date_matches(value, from_date):
        if not from_date:
            return True
        if not value:
            return False
        value_date = value.date() if hasattr(value, "date") else value
        return value_date >= from_date

    @api.model
    def _fetch_sales_rows(self, product_serial, limit_value, from_date=None, connection=None):
        if connection is not None:
            return self._fetch_sales_batch_rows_with_connection(
                product_serial, limit_value, from_date=from_date, connection=connection,
            )
        return self._fetch_sales_batch_rows(product_serial, limit_value, from_date=from_date)

    @api.model
    def _fetch_sale_return_rows(self, product_serial, limit_value, from_date=None, connection=None):
        if connection is not None:
            return self._fetch_sales_batch_rows_with_connection(
                product_serial, limit_value, return_only=True, from_date=from_date, connection=connection,
            )
        return self._fetch_sales_batch_rows(
            product_serial, limit_value, return_only=True, from_date=from_date,
        )

    @api.model
    def _fetch_purchase_rows(self, product_serial, limit_value, from_date=None):
        query = """
                SELECT TOP(?) CAST('purchase' AS NVARCHAR(20)) AS movement_type,
                pd.sec_update_date AS movement_datetime,
                CAST(COALESCE(pd.itm_pur_price, pd.itm_cost, pd.itm_sell, 0) AS DECIMAL(18, 4)) AS sale_price,
                CAST(
                    CASE pd.ptd_itm_purchase_unit
                        WHEN 1 THEN CAST(ISNULL(pd.qnty, 0) AS DECIMAL(18, 4))
                        WHEN 2 THEN CAST(ISNULL(pd.qnty, 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(pd.ptd_itm_unit1_unit2 AS DECIMAL(18, 4)), 0)
                        WHEN 3 THEN CAST(ISNULL(pd.qnty, 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(pd.ptd_itm_unit1_unit3 AS DECIMAL(18, 4)), 0)
                        ELSE CAST(ISNULL(pd.qnty, 0) AS DECIMAL(18, 4))
                    END
                    AS DECIMAL(18, 4)
                ) AS qty_large,
                COALESCE(st.sto_name_ar, st.sto_name_en, CONVERT(NVARCHAR(50), ph.sto_id)) AS store_name,
                COALESCE(v.ven_name_ar, v.ven_name_en, CONVERT(NVARCHAR(50), ph.ven_id)) AS supplier_name,
                CAST(NULL AS NVARCHAR(255)) AS customer_name,
                COALESCE(e.e_Name, CONVERT(NVARCHAR(50), ph.emp_id)) AS employee_name,
                CAST('pur_trans_d' AS NVARCHAR(50)) AS source_table,
                CONVERT(NVARCHAR(50), pd.ptd_id) AS source_line_id,
                pd.sec_update_date AS source_updated_at,
                30 AS movement_sort
                FROM pur_trans_h ph
                WITH (NOLOCK)
                    INNER JOIN pur_trans_d pd
                WITH (NOLOCK)
                ON pd.pth_id = ph.pth_id
                    INNER JOIN Item_Catalog ic
                WITH (NOLOCK)
                ON ic.itm_id = pd.itm_id
                    LEFT JOIN Store st
                WITH (NOLOCK)
                ON st.sto_id = ph.sto_id
                    LEFT JOIN Vendor v
                WITH (NOLOCK)
                ON v.ven_id = ph.ven_id
                    LEFT JOIN Employee e
                WITH (NOLOCK)
                ON e.e_id = ph.emp_id
                WHERE pd.itm_id = ?
                  AND pd.sec_update_date IS NOT NULL
                  AND (? IS NULL
                   OR pd.sec_update_date >= ?)
                ORDER BY pd.sec_update_date DESC \
                """
        return self._run_query(
            query,
            (limit_value, product_serial, from_date, from_date),
            "purchase",
        )

    @api.model
    def _fetch_purchase_return_rows(self, product_serial, limit_value, from_date=None):
        query = """
                SELECT TOP(?) CAST('purchase_return' AS NVARCHAR(20)) AS movement_type,
                pd.sec_update_date AS movement_datetime,
                CAST(COALESCE(pd.itm_back_pharm, pd.itm_cost, pd.itm_pur_price, 0) AS DECIMAL(18, 4)) AS sale_price,
                CAST(
                    -1 * CASE pd.ptd_r_itm_purchase_unit
                        WHEN 1 THEN CAST(ISNULL(COALESCE(pd.itm_back_qty, pd.itm_back), 0) AS DECIMAL(18, 4))
                        WHEN 2 THEN CAST(ISNULL(COALESCE(pd.itm_back_qty, pd.itm_back), 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(pd.ptd_r_itm_unit1_unit2 AS DECIMAL(18, 4)), 0)
                        WHEN 3 THEN CAST(ISNULL(COALESCE(pd.itm_back_qty, pd.itm_back), 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(pd.ptd_r_itm_unit1_unit3 AS DECIMAL(18, 4)), 0)
                        ELSE CAST(ISNULL(COALESCE(pd.itm_back_qty, pd.itm_back), 0) AS DECIMAL(18, 4))
                    END
                    AS DECIMAL(18, 4)
                ) AS qty_large,
                COALESCE(st.sto_name_ar, st.sto_name_en, CONVERT(NVARCHAR(50), ph.sto_id)) AS store_name,
                COALESCE(v.ven_name_ar, v.ven_name_en, CONVERT(NVARCHAR(50), ph.ven_id)) AS supplier_name,
                CAST(NULL AS NVARCHAR(255)) AS customer_name,
                COALESCE(e.e_Name, CONVERT(NVARCHAR(50), ph.emp_id)) AS employee_name,
                CAST('pur_trans_d' AS NVARCHAR(50)) AS source_table,
                CONVERT(NVARCHAR(50), pd.ptd_id) AS source_line_id,
                pd.sec_update_date AS source_updated_at,
                40 AS movement_sort
                FROM pur_trans_h ph
                WITH (NOLOCK)
                    INNER JOIN pur_trans_d pd
                WITH (NOLOCK)
                ON pd.pth_id = ph.pth_id
                    INNER JOIN Item_Catalog ic
                WITH (NOLOCK)
                ON ic.itm_id = pd.itm_id
                    LEFT JOIN Store st
                WITH (NOLOCK)
                ON st.sto_id = ph.sto_id
                    LEFT JOIN Vendor v
                WITH (NOLOCK)
                ON v.ven_id = ph.ven_id
                    LEFT JOIN Employee e
                WITH (NOLOCK)
                ON e.e_id = ph.emp_id
                WHERE pd.itm_id = ?
                  AND pd.sec_update_date IS NOT NULL
                  AND ISNULL(COALESCE (pd.itm_back_qty
                    , pd.itm_back)
                    , 0)
                    > 0
                  AND (? IS NULL
                   OR pd.sec_update_date >= ?)
                ORDER BY pd.sec_update_date DESC \
                """
        return self._run_query(
            query,
            (limit_value, product_serial, from_date, from_date),
            "purchase_return",
        )

    @api.model
    def _fetch_transfer_out_rows(self, product_serial, limit_value, from_date=None):
        query = """
                SELECT TOP(?) CAST('transfer_out' AS NVARCHAR(20)) AS movement_type,
                sth.sec_update_date AS movement_datetime,
                CAST(COALESCE(st.st_itm_sell, 0) AS DECIMAL(18, 4)) AS sale_price,
                CAST(
                    -1 * CASE st.st_itm_unit
                        WHEN 1 THEN CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                        WHEN 2 THEN CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(st.st_f_itm_unit1_unit2 AS DECIMAL(18, 4)), 0)
                        WHEN 3 THEN CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(st.st_f_itm_unit1_unit3 AS DECIMAL(18, 4)), 0)
                        ELSE CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                    END
                    AS DECIMAL(18, 4)
                ) AS qty_large,
                COALESCE(src_store.sto_name_ar, src_store.sto_name_en, CONVERT(NVARCHAR(50), sth.stnh_f_Sto_id)) AS store_name,
                CAST(NULL AS NVARCHAR(255)) AS supplier_name,
                CAST(NULL AS NVARCHAR(255)) AS customer_name,
                COALESCE(e.e_Name, CONVERT(NVARCHAR(50), sth.delivery_emp), CONVERT(NVARCHAR(50), sth.sec_insert_uid)) AS employee_name,
                CAST('Store_Trans' AS NVARCHAR(50)) AS source_table,
                CONVERT(NVARCHAR(50), st.st_id) AS source_line_id,
                sth.sec_update_date AS source_updated_at,
                50 AS movement_sort
                FROM Store_Trans_h sth
                WITH (NOLOCK)
                    INNER JOIN Store_Trans st
                WITH (NOLOCK)
                ON st.stnh_id = sth.stnh_id
                    AND st.st_from_store = sth.stnh_f_Sto_id
                    AND st.st_to_store = sth.stnh_t_Sto_id
                    LEFT JOIN Store src_store
                WITH (NOLOCK)
                ON src_store.sto_id = sth.stnh_f_Sto_id
                    LEFT JOIN Employee e
                WITH (NOLOCK)
                ON e.e_id = sth.delivery_emp
                WHERE st.st_itm_id = ?
                  AND sth.sec_update_date IS NOT NULL
                  AND (? IS NULL
                   OR sth.sec_update_date >= ?)
                ORDER BY sth.sec_update_date DESC \
                """
        return self._run_query(
            query,
            (limit_value, product_serial, from_date, from_date),
            "transfer_out",
        )

    @api.model
    def _fetch_transfer_in_rows(self, product_serial, limit_value, from_date=None):
        query = """
                SELECT TOP(?) CAST('transfer_in' AS NVARCHAR(20)) AS movement_type,
                sth.sec_update_date AS movement_datetime,
                CAST(COALESCE(st.st_itm_sell, 0) AS DECIMAL(18, 4)) AS sale_price,
                CAST(
                    CASE st.st_itm_unit
                        WHEN 1 THEN CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                        WHEN 2 THEN CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(st.st_t_itm_unit1_unit2 AS DECIMAL(18, 4)), 0)
                        WHEN 3 THEN CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                            / NULLIF(CAST(st.st_t_itm_unit1_unit3 AS DECIMAL(18, 4)), 0)
                        ELSE CAST(ISNULL(st.st_itm_quantity, 0) AS DECIMAL(18, 4))
                    END
                    AS DECIMAL(18, 4)
                ) AS qty_large,
                COALESCE(dst_store.sto_name_ar, dst_store.sto_name_en, CONVERT(NVARCHAR(50), sth.stnh_t_Sto_id)) AS store_name,
                CAST(NULL AS NVARCHAR(255)) AS supplier_name,
                CAST(NULL AS NVARCHAR(255)) AS customer_name,
                COALESCE(e.e_Name, CONVERT(NVARCHAR(50), sth.delivery_emp), CONVERT(NVARCHAR(50), sth.sec_insert_uid)) AS employee_name,
                CAST('Store_Trans' AS NVARCHAR(50)) AS source_table,
                CONVERT(NVARCHAR(50), st.st_id) AS source_line_id,
                sth.sec_update_date AS source_updated_at,
                60 AS movement_sort
                FROM Store_Trans_h sth
                WITH (NOLOCK)
                    INNER JOIN Store_Trans st
                WITH (NOLOCK)
                ON st.stnh_id = sth.stnh_id
                    AND st.st_from_store = sth.stnh_f_Sto_id
                    AND st.st_to_store = sth.stnh_t_Sto_id
                    LEFT JOIN Store dst_store
                WITH (NOLOCK)
                ON dst_store.sto_id = sth.stnh_t_Sto_id
                    LEFT JOIN Employee e
                WITH (NOLOCK)
                ON e.e_id = sth.delivery_emp
                WHERE st.st_itm_id = ?
                  AND sth.sec_update_date IS NOT NULL
                  AND (? IS NULL
                   OR sth.sec_update_date >= ?)
                ORDER BY sth.sec_update_date DESC \
                """
        return self._run_query(
            query,
            (limit_value, product_serial, from_date, from_date),
            "transfer_in",
        )

    @api.model
    def _run_query(self, query, params, movement_type):
        with self.connect_eplus(param_str="?") as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall() or []
        result = []
        for row in rows:
            if not row:
                continue
            result.append({
                "movement_group": self._movement_group_from_type(movement_type),
                "movement_type": row[0] or movement_type,
                "movement_datetime": row[1],
                "sale_price": float(row[2] or 0.0),
                "qty_large": float(row[3] or 0.0),
                "store_name": row[4] or "",
                "supplier_name": row[5] or "",
                "customer_name": row[6] or "",
                "employee_name": row[7] or "",
                "source_table": row[8] or "",
                "source_line_id": row[9] or "",
                "source_updated_at": row[10],
                "movement_sort": row[11] or MOVEMENT_SORT.get(movement_type, 0),
            })
        return result

    @api.model
    def _movement_group_from_type(self, movement_type):
        if movement_type.startswith("sale"):
            return "sale"
        if movement_type.startswith("purchase"):
            return "purchase"
        return "transfer"

    @api.model
    def _to_wizard_rows(self):
        rows = []
        for record in self:
            rows.append({
                "movement_group": record.movement_group,
                "movement_type": record.movement_type,
                "movement_datetime": record.movement_datetime,
                "sale_price": record.sale_price,
                "qty_large": record.qty_large,
                "store_name": record.store_name or "",
                "supplier_name": record.supplier_name or "",
                "customer_name": record.customer_name or "",
                "employee_name": record.employee_name or "",
                "movement_sort": MOVEMENT_SORT.get(record.movement_type, 0),
                "source_line_id": record.source_line_id or "",
            })
        return rows


class AbStockReportRefreshJob(models.Model):
    _name = "ab_stock_report_refresh_job"
    _description = "Stock Movement Refresh Job"

    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        required=True,
        ondelete="cascade",
        index=True,
    )
    product_eplus_serial = fields.Integer(
        string="EPlus Serial",
        required=True,
        index=True,
    )
    limit = fields.Integer(
        string="Cache Limit",
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
        default="pending",
        required=True,
        index=True,
    )
    requested_at = fields.Datetime(
        string="Requested At",
        required=True,
        index=True,
    )
    started_at = fields.Datetime(
        string="Started At",
        readonly=True,
    )
    finished_at = fields.Datetime(
        string="Finished At",
        readonly=True,
    )
    last_error = fields.Text(
        string="Last Error",
        readonly=True,
    )

    @api.model
    def request_refresh(self, product, limit, immediate=False):
        product_rec = self.env["ab_stock_report_cache_line"]._resolve_product(product)
        limit_value = self.env["ab_stock_report_cache_line"]._normalize_limit(limit)
        now = fields.Datetime.now()
        domain = [
            ("product_eplus_serial", "=", product_rec.eplus_serial),
            ("limit", "=", limit_value),
            ("state", "in", ("pending", "running")),
        ]
        job = self.search(domain, order="requested_at desc, id desc", limit=1)
        vals = {
            "product_id": product_rec.id,
            "product_eplus_serial": product_rec.eplus_serial,
            "limit": limit_value,
            "state": "pending",
            "requested_at": now,
            "last_error": False,
        }
        if job:
            job.write(vals)
        else:
            job = self.create(vals)
        if immediate:
            dbname = self.env.cr.dbname
            self.env.cr.postcommit.add(
                lambda dbname=dbname: AbStockReportRefreshJob._start_background_worker(dbname)
            )
        return job

    @staticmethod
    def _start_background_worker(dbname):
        global _REFRESH_WORKER_RUNNING
        with _REFRESH_WORKER_LOCK:
            if _REFRESH_WORKER_RUNNING:
                return
            _REFRESH_WORKER_RUNNING = True
        worker = threading.Thread(
            target=self._run_background_worker,
            args=(dbname,),
            daemon=True,
        )
        worker.start()

    @staticmethod
    def _run_background_worker(dbname):
        global _REFRESH_WORKER_RUNNING
        try:
            with api.Environment.manage():
                registry = Registry(dbname)
                with registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env["ab_stock_report_refresh_job"].process_pending_jobs()
                    cr.commit()
        except Exception:
            _logger.exception("Background stock report refresh worker failed.")
        finally:
            with _REFRESH_WORKER_LOCK:
                _REFRESH_WORKER_RUNNING = False

    @api.model
    def cron_process_pending_jobs(self):
        self.process_pending_jobs()

    @api.model
    def action_process_pending_jobs(self):
        self.process_pending_jobs()

    @api.model
    def process_pending_jobs(self):
        while True:
            jobs = self.search(
                [("state", "=", "pending")],
                order="requested_at asc, id asc",
                limit=REFRESH_BATCH_SIZE,
            )
            if not jobs:
                break
            for job in jobs:
                job._process_one()
            self.env.cr.commit()

    def _process_one(self):
        self.ensure_one()
        cache_model = self.env["ab_stock_report_cache_line"]
        try:
            self.write({
                "state": "running",
                "started_at": fields.Datetime.now(),
                "last_error": False,
            })
            self.env.cr.commit()
            cache_model.refresh_product_cache(self.product_id, self.limit, force=True)
            self.write({
                "state": "done",
                "finished_at": fields.Datetime.now(),
            })
            return True
        except Exception as exc:
            _logger.exception("Failed to refresh stock report cache for product %s.", self.product_eplus_serial)
            self.write({
                "state": "failed",
                "finished_at": fields.Datetime.now(),
                "last_error": str(exc),
            })
            return False
