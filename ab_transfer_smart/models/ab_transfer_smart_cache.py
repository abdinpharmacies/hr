# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SMART_DESTINATION_STOCK_SQL = """
    SELECT
        itm_id,
        sto_id,
        SUM(ISNULL(itm_qty, 0)) AS stock_qty
    FROM Item_Class_Store
    WHERE sto_id = ?
    GROUP BY itm_id, sto_id
    HAVING SUM(ISNULL(itm_qty, 0)) <> 0
"""

SMART_DESTINATION_SALES_QTY_EXPR = """
    CASE sd.itm_unit
        WHEN 1 THEN CAST(ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0) AS DECIMAL(18, 4))
        WHEN 2 THEN
            CAST(ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0) AS DECIMAL(18, 4))
            / NULLIF(CAST(ic.itm_unit1_unit2 AS DECIMAL(18, 4)), 0)
        WHEN 3 THEN
            CAST(ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0) AS DECIMAL(18, 4))
            / NULLIF(CAST(ic.itm_unit1_unit3 AS DECIMAL(18, 4)), 0)
        ELSE CAST(ISNULL(sd.qnty, 0) - ISNULL(sd.itm_back, 0) AS DECIMAL(18, 4))
    END
"""

SMART_DESTINATION_SALES_SQL = """
    SELECT
        sd.itm_id AS product_eplus_serial,
        SUM(CASE WHEN sd.sec_insert_date >= ? AND sd.sec_insert_date < ?
                 THEN {qty_expr} ELSE 0 END) AS month1_sales,
        SUM(CASE WHEN sd.sec_insert_date >= ? AND sd.sec_insert_date < ?
                 THEN {qty_expr} ELSE 0 END) AS month2_sales,
        SUM(CASE WHEN sd.sec_insert_date >= ? AND sd.sec_insert_date < ?
                 THEN {qty_expr} ELSE 0 END) AS month3_sales
    FROM sales_trans_d sd WITH (NOLOCK)
    INNER JOIN sales_trans_h sh WITH (NOLOCK)
        ON sd.sth_id = sh.sth_id
    INNER JOIN item_catalog ic WITH (NOLOCK)
        ON ic.itm_id = sd.itm_id
    WHERE sh.sto_id = ?
      AND sd.sec_insert_date >= ?
      AND sd.sec_insert_date < ?
    GROUP BY sd.itm_id
""".format(qty_expr=SMART_DESTINATION_SALES_QTY_EXPR)


class AbTransferSmartCacheTools:
    @api.model
    def _get_cache_date(self):
        return fields.Date.context_today(self)

    @api.model
    def _get_store_sql_id(self, store):
        if not store:
            raise UserError(_("Store is required."))
        store_sql_id = store.eplus_serial
        if store_sql_id in (False, None, "", 0):
            raise UserError(_("Store EPlus serial is missing: %s") % store.display_name)
        return int(store_sql_id)

    @api.model
    def _get_store_server(self, store):
        if not store:
            raise UserError(_("Store is required."))
        server = store.ip1
        if not server:
            raise UserError(_("Store MSSQL server IP1 is missing: %s") % store.display_name)
        return server

    @api.model
    def _ensure_store_record(self, store):
        store = self.env["ab_store"].browse(store.id if hasattr(store, "id") else store).exists()
        if not store:
            raise UserError(_("Store is required."))
        return store

    @api.depends("product_eplus_serial")
    def _compute_product_fields(self):
        product_serials = sorted({
            self._safe_int(record.product_eplus_serial)
            for record in self
            if record.product_eplus_serial
        })
        products_by_serial = self._get_products_by_eplus_serial(product_serials)
        for record in self:
            product = products_by_serial.get(self._safe_int(record.product_eplus_serial))
            record.product_id = product.id if product else False
            record.product_code = product.code if product else False

    @api.model
    def _get_products_by_eplus_serial(self, product_serials):
        serials = sorted({
            self._safe_int(product_serial)
            for product_serial in product_serials
            if product_serial
        })
        if not serials:
            return {}

        products = self.env["ab_product"].with_context(active_test=False).search(
            [("eplus_serial", "in", serials)],
            order="eplus_serial, active desc, id",
        )
        products_by_serial = {}
        for product in products:
            product_serial = self._safe_int(product.eplus_serial)
            if product_serial and product_serial not in products_by_serial:
                products_by_serial[product_serial] = product
        return products_by_serial


class AbTransferSmartStockCache(AbTransferSmartCacheTools, models.Model):
    _name = "ab_transfer_smart_stock_cache"
    _inherit = ["ab_eplus_connect"]
    _description = "Smart Transfer Destination Stock Cache"
    _order = "cache_date desc, store_id, product_eplus_serial"

    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_eplus_serial = fields.Integer(
        string="Product EPlus Serial",
        required=True,
        index=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        compute="_compute_product_fields",
        store=True,
        readonly=True,
        index=True,
    )
    product_code = fields.Char(
        string="Product Code",
        compute="_compute_product_fields",
        store=True,
        readonly=True,
        index=True,
    )
    stock_qty = fields.Float(
        string="Stock Quantity",
        digits=(16, 4),
        aggregator="sum",
    )
    cache_date = fields.Date(
        string="Cache Date",
        required=True,
        index=True,
        default=lambda self: self._get_cache_date(),
    )

    _uniq_smart_stock_store_product_cache_date = models.Constraint(
        "UNIQUE(store_id, product_eplus_serial, cache_date)",
        "Smart transfer stock cache already exists for this store, product, and date.",
    )

    def init(self):
        super().init()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_transfer_smart_stock_cache_store_date_idx
                ON ab_transfer_smart_stock_cache (store_id, cache_date)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_transfer_smart_stock_cache_store_product_date_idx
                ON ab_transfer_smart_stock_cache (store_id, product_eplus_serial, cache_date)
        """)

    @api.model
    def cron_refresh_smart_transfer_cache(self):
        stores = self.env["ab_store"].sudo().search([
            ("allow_sale", "=", True),
            ("eplus_serial", "!=", False),
        ])
        return self.refresh_stores_cache(stores, force=True)

    @api.model
    def refresh_stores_cache(self, stores, force=False):
        stores = self.env["ab_store"].browse(stores.ids if hasattr(stores, "ids") else stores).exists()
        result = {
            "stores": len(stores),
            "stock_rows": 0,
            "sales_rows": 0,
        }
        SalesCache = self.env["ab_transfer_smart_sales_cache"].sudo()
        for store in stores:
            result["stock_rows"] += self.sudo().refresh_store_cache(store, force=force)
            result["sales_rows"] += SalesCache.refresh_store_cache(store, force=force)
        return result

    @api.model
    def refresh_store_cache(self, store, force=False):
        store = self._ensure_store_record(store)
        cache_date = self._get_cache_date()
        self._delete_stale_cache(store, cache_date)
        if not force and self._has_today_cache(store, cache_date):
            return 0

        self.search([("store_id", "=", store.id)]).unlink()
        rows = self._fetch_store_stock_rows(store)
        vals_list = [
            {
                "store_id": store.id,
                "product_eplus_serial": product_serial,
                "stock_qty": stock_qty,
                "cache_date": cache_date,
            }
            for product_serial, stock_qty in rows.items()
            if product_serial and float(stock_qty or 0.0) != 0.0
        ]
        if vals_list:
            self.create(vals_list)
        return len(vals_list)

    @api.model
    def _delete_stale_cache(self, store, cache_date):
        self.search([
            ("store_id", "=", store.id),
            ("cache_date", "!=", cache_date),
        ]).unlink()

    @api.model
    def _has_today_cache(self, store, cache_date):
        return bool(self.search_count([
            ("store_id", "=", store.id),
            ("cache_date", "=", cache_date),
        ]))

    @api.model
    def _fetch_store_stock_rows(self, store):
        store_sql_id = self._get_store_sql_id(store)
        server = self._get_store_server(store)
        try:
            stock_by_product = {}
            with self.connect_eplus(
                    server=server,
                    param_str="?",
                    autocommit=True,
                    propagate_error=True,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(SMART_DESTINATION_STOCK_SQL, (store_sql_id,))
                    for product_serial, _store_sql_id, stock_qty in cursor.fetchall() or []:
                        product_serial = self._safe_int(product_serial)
                        stock_qty = float(stock_qty or 0.0)
                        if product_serial and stock_qty != 0.0:
                            stock_by_product[product_serial] = stock_qty
            return stock_by_product
        except Exception as error:
            _logger.exception("Smart transfer stock cache refresh failed: store=%s", store.display_name)
            raise UserError(
                _("Smart transfer stock cache refresh failed for %(store)s: %(error)s")
                % {"store": store.display_name, "error": error}
            )

    @staticmethod
    def _safe_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


class AbTransferSmartSalesCache(AbTransferSmartCacheTools, models.Model):
    _name = "ab_transfer_smart_sales_cache"
    _inherit = ["ab_eplus_connect"]
    _description = "Smart Transfer Destination Sales Cache"
    _order = "cache_date desc, store_id, product_eplus_serial"

    store_id = fields.Many2one(
        "ab_store",
        string="Store",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_eplus_serial = fields.Integer(
        string="Product EPlus Serial",
        required=True,
        index=True,
    )
    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        compute="_compute_product_fields",
        store=True,
        readonly=True,
        index=True,
    )
    product_code = fields.Char(
        string="Product Code",
        compute="_compute_product_fields",
        store=True,
        readonly=True,
        index=True,
    )
    month1_sales = fields.Float(
        string="Month 1 Sales",
        digits=(16, 4),
        aggregator="sum",
    )
    month2_sales = fields.Float(
        string="Month 2 Sales",
        digits=(16, 4),
        aggregator="sum",
    )
    month3_sales = fields.Float(
        string="Month 3 Sales",
        digits=(16, 4),
        aggregator="sum",
    )
    total_3_months_sales = fields.Float(
        string="Total 3 Months Sales",
        digits=(16, 4),
        aggregator="sum",
    )
    cache_date = fields.Date(
        string="Cache Date",
        required=True,
        index=True,
        default=lambda self: self._get_cache_date(),
    )

    _uniq_smart_sales_store_product_cache_date = models.Constraint(
        "UNIQUE(store_id, product_eplus_serial, cache_date)",
        "Smart transfer sales cache already exists for this store, product, and date.",
    )

    def init(self):
        super().init()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_transfer_smart_sales_cache_store_date_idx
                ON ab_transfer_smart_sales_cache (store_id, cache_date)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_transfer_smart_sales_cache_store_product_date_idx
                ON ab_transfer_smart_sales_cache (store_id, product_eplus_serial, cache_date)
        """)

    @api.model
    def refresh_store_cache(self, store, force=False):
        store = self._ensure_store_record(store)
        cache_date = self._get_cache_date()
        self._delete_stale_cache(store, cache_date)
        if not force and self._has_today_cache(store, cache_date):
            return 0

        self.search([("store_id", "=", store.id)]).unlink()
        rows = self._fetch_store_sales_rows(store)
        vals_list = [
            {
                "store_id": store.id,
                "product_eplus_serial": product_serial,
                "month1_sales": values["month1_sales"],
                "month2_sales": values["month2_sales"],
                "month3_sales": values["month3_sales"],
                "total_3_months_sales": values["total_3_months_sales"],
                "cache_date": cache_date,
            }
            for product_serial, values in rows.items()
            if product_serial
        ]
        if vals_list:
            self.create(vals_list)
        return len(vals_list)

    @api.model
    def _delete_stale_cache(self, store, cache_date):
        self.search([
            ("store_id", "=", store.id),
            ("cache_date", "!=", cache_date),
        ]).unlink()

    @api.model
    def _has_today_cache(self, store, cache_date):
        return bool(self.search_count([
            ("store_id", "=", store.id),
            ("cache_date", "=", cache_date),
        ]))

    @api.model
    def _fetch_store_sales_rows(self, store):
        store_sql_id = self._get_store_sql_id(store)
        server = self._get_store_server(store)
        today = self._get_cache_date()
        today_start = datetime.combine(today, time.min)
        month1_start = today_start - timedelta(days=30)
        month2_start = today_start - timedelta(days=60)
        month3_start = today_start - timedelta(days=90)
        try:
            sales_by_product = {}
            with self.connect_eplus(
                    server=server,
                    param_str="?",
                    autocommit=True,
                    propagate_error=True,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        SMART_DESTINATION_SALES_SQL,
                        (
                            month1_start,
                            today_start,
                            month2_start,
                            month1_start,
                            month3_start,
                            month2_start,
                            store_sql_id,
                            month3_start,
                            today_start,
                        ),
                    )
                    for product_serial, month1_sales, month2_sales, month3_sales in cursor.fetchall() or []:
                        product_serial = self._safe_int(product_serial)
                        if not product_serial:
                            continue
                        month1_sales = float(month1_sales or 0.0)
                        month2_sales = float(month2_sales or 0.0)
                        month3_sales = float(month3_sales or 0.0)
                        sales_by_product[product_serial] = {
                            "month1_sales": month1_sales,
                            "month2_sales": month2_sales,
                            "month3_sales": month3_sales,
                            "total_3_months_sales": month1_sales + month2_sales + month3_sales,
                        }
            return sales_by_product
        except Exception as error:
            _logger.exception("Smart transfer sales cache refresh failed: store=%s", store.display_name)
            raise UserError(
                _("Smart transfer sales cache refresh failed for %(store)s: %(error)s")
                % {"store": store.display_name, "error": error}
            )

    @staticmethod
    def _safe_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
