from datetime import datetime, time
from decimal import Decimal

from odoo import api, fields, models


class SalesDashboardService(models.AbstractModel):
    _name = "ab.sales.dashboard.service"
    _inherit = ["ab_eplus_connect"]
    _description = "Sales Dashboard E-Plus Service"

    @api.model
    def fetch_dashboard_data(self, date_from, date_to, store_eplus_ids=None):
        start_dt, end_dt = self._date_window(date_from, date_to)
        store_eplus_ids = [int(store_id) for store_id in (store_eplus_ids or []) if store_id]
        where_sql, base_params = self._build_invoice_where(start_dt, end_dt, store_eplus_ids)

        with self.connect_eplus(param_str="?", charset="CP1256") as conn:
            with conn.cursor() as cursor:
                totals = self._fetch_one(cursor, self._totals_sql(where_sql), base_params)
                prev_start, prev_end = self._previous_period(start_dt, end_dt)
                prev_where_sql, prev_params = self._build_invoice_where(prev_start, prev_end, store_eplus_ids)
                previous = self._fetch_one(cursor, self._previous_totals_sql(prev_where_sql), prev_params)
                collections = self._fetch_all(cursor, self._collection_sql(where_sql), base_params)
                bearing = self._fetch_one(cursor, self._contract_bearing_sql(where_sql), base_params)
                medicine = self._fetch_all(cursor, self._medicine_sql(where_sql), base_params)
                users = self._fetch_all(cursor, self._sales_by_user_sql(where_sql), base_params)
                items = self._fetch_all(cursor, self._top_items_sql(where_sql, len(store_eplus_ids)), base_params + store_eplus_ids)
                invoices = self._fetch_all(cursor, self._recent_invoices_sql(where_sql), base_params)

        return self._normalize_dashboard_payload(
            totals=totals,
            previous=previous,
            collections=collections,
            bearing=bearing,
            medicine=medicine,
            users=users,
            items=items,
            invoices=invoices,
            days=max((end_dt.date() - start_dt.date()).days, 1),
        )

    @api.model
    def _date_window(self, date_from, date_to):
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
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
    def _invoice_base_cte(self, where_sql):
        return f"""
            WITH invoice_base AS (
                SELECT
                    h.sth_id,
                    h.sto_id,
                    h.cust_id,
                    h.emp_id,
                    h.sec_insert_date,
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
                          OR EXISTS (
                              SELECT 1
                              FROM r_sales_trans_d d WITH (NOLOCK)
                              WHERE d.sth_id = h.sth_id
                                AND d.std_stock_id = h.sto_id
                                AND (ISNULL(d.itm_dis_mon, 0) <> 0 OR ISNULL(d.itm_dis_per, 0) <> 0)
                          )
                        THEN 1 ELSE 0
                    END AS is_offer,
                    CASE
                        WHEN ISNULL(h.total_des_mon, 0) <> 0
                          OR ISNULL(h.total_dis_per, 0) <> 0
                          OR ISNULL(h.sth_pnt_dis, 0) <> 0
                        THEN 'offer'
                        WHEN ISNULL(h.fh_contract_id, 0) <> 0 OR ISNULL(h.fh_company_part, 0) <> 0
                        THEN 'contract'
                        WHEN h.bill_typ = 4
                        THEN 'delivery'
                        ELSE 'cash'
                    END AS collection_category
                FROM r_sales_trans_h h WITH (NOLOCK)
                WHERE {where_sql}
            )
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
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN net_amount - company_part ELSE 0 END), 0) AS customer_bearing_amount,
                ISNULL(SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END), 0) AS company_part_amount,
                100.0 * SUM(CASE WHEN is_contract = 1 THEN net_amount - company_part ELSE 0 END)
                    / NULLIF(SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END), 0) AS bearing_pct
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
            SELECT TOP (20)
                h.sth_id AS invoice_no,
                h.sec_insert_date,
                COALESCE(c.cust_name_ar, CONVERT(VARCHAR(20), h.cust_id)) AS customer_name,
                h.net_amount AS invoice_total,
                COUNT(d.std_id) AS item_count,
                STRING_AGG(CONVERT(NVARCHAR(MAX), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id))), N', ') AS items
            FROM invoice_base h
            LEFT JOIN Customer c WITH (NOLOCK) ON c.cust_id = h.cust_id
            JOIN r_sales_trans_d d WITH (NOLOCK) ON d.sth_id = h.sth_id AND d.std_stock_id = h.sto_id
            JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
            GROUP BY h.sth_id, h.sec_insert_date, h.cust_id, c.cust_name_ar, h.net_amount
            ORDER BY h.sec_insert_date DESC
        """

    @api.model
    def _fetch_one(self, cursor, sql, params):
        rows = self._fetch_all(cursor, sql, params)
        return rows[0] if rows else {}

    @api.model
    def _fetch_all(self, cursor, sql, params):
        cursor.execute(sql, params or [])
        columns = [column[0].lower() for column in (cursor.description or [])]
        return [self._normalize_row(row, columns) for row in cursor.fetchall()]

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
    def _normalize_dashboard_payload(self, totals, previous, collections, bearing, medicine, users, items, invoices, days):
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
            "collection_lines": collections,
            "user_lines": users,
            "item_lines": items,
            "invoice_lines": invoices,
        }
