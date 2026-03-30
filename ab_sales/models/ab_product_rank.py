# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import fields, models


class AbProductRank(models.Model):
    _name = "ab_product_rank"
    _description = "Sales Product Ranking Cache"
    _order = "score desc, order_count desc, qty_total desc, id desc"

    product_id = fields.Many2one("ab_product", required=True, index=True, ondelete="cascade")
    store_id = fields.Many2one("ab_store", required=True, index=True, ondelete="cascade")
    customer_phone = fields.Char(default="", index=True)
    rank_scope = fields.Selection(
        selection=[("branch", "Branch"), ("customer", "Customer")],
        required=True,
        index=True,
    )
    period_days = fields.Integer(required=True, index=True)
    order_count = fields.Integer(default=0)
    qty_total = fields.Float(default=0.0)
    score = fields.Float(default=0.0, index=True)
    last_order_date = fields.Datetime(index=True)

    _uniq_rank_key = models.Constraint(
        "UNIQUE(product_id, store_id, customer_phone, rank_scope, period_days)",
        "Product rank entry already exists for this scope.",
    )

    def _score(self, order_count, qty_total):
        return (float(order_count or 0.0) * 0.6) + (float(qty_total or 0.0) * 0.4)

    @staticmethod
    def _normalize_phone(phone):
        digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
        if not digits:
            return ""
        if digits.startswith("0020") and len(digits) >= 14:
            digits = "0" + digits[4:]
        elif digits.startswith("20") and len(digits) >= 12:
            digits = "0" + digits[2:]
        elif len(digits) == 10 and digits.startswith("1"):
            digits = "0" + digits
        if len(digits) > 11 and digits.startswith("0"):
            digits = digits[-11:]
        if len(digits) == 11 and digits.startswith("01"):
            return digits
        return digits

    def _refresh_branch_rank(self, since_date):
        self.env.cr.execute(
            """
            SELECT
                h.store_id,
                l.product_id,
                COUNT(DISTINCT h.id) AS order_count,
                SUM(COALESCE(l.qty, 0.0)) AS qty_total,
                MAX(h.create_date) AS last_order_date
            FROM ab_sales_line l
            JOIN ab_sales_header h ON h.id = l.header_id
            WHERE h.status IN ('pending', 'saved')
              AND h.store_id IS NOT NULL
              AND h.create_date >= %s
              AND l.product_id IS NOT NULL
              AND COALESCE(l.qty, 0.0) > 0
            GROUP BY h.store_id, l.product_id
            """,
            (since_date,),
        )
        rows = self.env.cr.fetchall()
        vals_list = []
        for store_id, product_id, order_count, qty_total, last_order_date in rows:
            if not store_id or not product_id:
                continue
            vals_list.append(
                {
                    "store_id": int(store_id),
                    "product_id": int(product_id),
                    "customer_phone": "",
                    "rank_scope": "branch",
                    "period_days": 30,
                    "order_count": int(order_count or 0),
                    "qty_total": float(qty_total or 0.0),
                    "score": self._score(order_count, qty_total),
                    "last_order_date": last_order_date,
                }
            )
        return vals_list

    def _refresh_customer_rank(self, since_date):
        self.env.cr.execute(
            """
            SELECT
                h.store_id,
                l.product_id,
                regexp_replace(COALESCE(h.bill_customer_phone, ''), '[^0-9]', '', 'g') AS customer_phone,
                COUNT(DISTINCT h.id) AS order_count,
                SUM(COALESCE(l.qty, 0.0)) AS qty_total,
                MAX(h.create_date) AS last_order_date
            FROM ab_sales_line l
            JOIN ab_sales_header h ON h.id = l.header_id
            WHERE h.status IN ('pending', 'saved')
              AND h.store_id IS NOT NULL
              AND h.create_date >= %s
              AND l.product_id IS NOT NULL
              AND COALESCE(l.qty, 0.0) > 0
              AND regexp_replace(COALESCE(h.bill_customer_phone, ''), '[^0-9]', '', 'g') <> ''
            GROUP BY h.store_id, l.product_id, regexp_replace(COALESCE(h.bill_customer_phone, ''), '[^0-9]', '', 'g')
            """,
            (since_date,),
        )
        rows = self.env.cr.fetchall()
        vals_list = []
        for store_id, product_id, customer_phone, order_count, qty_total, last_order_date in rows:
            if not store_id or not product_id:
                continue
            customer_phone = self._normalize_phone(customer_phone)
            if not customer_phone:
                continue
            vals_list.append(
                {
                    "store_id": int(store_id),
                    "product_id": int(product_id),
                    "customer_phone": customer_phone,
                    "rank_scope": "customer",
                    "period_days": 90,
                    "order_count": int(order_count or 0),
                    "qty_total": float(qty_total or 0.0),
                    "score": self._score(order_count, qty_total),
                    "last_order_date": last_order_date,
                }
            )
        return vals_list

    def _replace_scope(self, rank_scope, period_days, vals_list):
        self.env.cr.execute(
            "DELETE FROM ab_product_rank WHERE rank_scope = %s AND period_days = %s",
            (rank_scope, period_days),
        )
        if not vals_list:
            return

        chunk_size = 1000
        for offset in range(0, len(vals_list), chunk_size):
            self.create(vals_list[offset: offset + chunk_size])

    def cron_refresh_rankings(self):
        now = fields.Datetime.now()
        since_30 = now - relativedelta(days=30)
        since_90 = now - relativedelta(days=90)

        branch_vals = self._refresh_branch_rank(since_30)
        customer_vals = self._refresh_customer_rank(since_90)

        self._replace_scope("branch", 30, branch_vals)
        self._replace_scope("customer", 90, customer_vals)
        return True
