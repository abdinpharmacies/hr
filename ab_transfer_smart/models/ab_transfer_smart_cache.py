# -*- coding: utf-8 -*-
import logging
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

SMART_DESTINATION_STOCK_SQL = """
    SELECT
        main.itm_id,
        main.sto_id,
        CAST(SUM(
            CAST(ISNULL(main.itm_qty, 0) AS decimal(18,4))
            / CAST(ic.itm_unit1_unit3 AS decimal(18,4))
        ) AS decimal(18,2)) AS stock_qty
    FROM Item_Class_Store main
    INNER JOIN item_catalog ic ON ic.itm_id = main.itm_id
    WHERE main.sto_id = ?
      AND ISNULL(ic.itm_active, 1) = 1
    GROUP BY main.itm_id, main.sto_id
    HAVING CAST(SUM(
        CAST(ISNULL(main.itm_qty, 0) AS decimal(18,4))
        / CAST(ic.itm_unit1_unit3 AS decimal(18,4))
    ) AS decimal(18,2)) <> 0
"""

SMART_DESTINATION_PENDING_STOCK_SQL = """
    SELECT
        Item_Catalog.itm_id,
        Item_Catalog.itm_code,
        Store.sto_id,
        CAST(
            SUM(
                CAST(Store_Trans.st_itm_quantity AS DECIMAL(18, 4))
                / NULLIF(Item_Catalog.itm_unit1_unit3, 0)
            )
            AS DECIMAL(18, 2)
        ) AS stock
    FROM Store_Trans
    INNER JOIN Item_Catalog
        ON Item_Catalog.itm_id = Store_Trans.st_itm_id
    INNER JOIN Store
        ON Store.sto_id = Store_Trans.st_to_store
    INNER JOIN Store_Trans_h
        ON Store_Trans_h.stnh_id = Store_Trans.stnh_id
        AND Store_Trans_h.stnh_f_Sto_id = Store_Trans.st_from_store
        AND Store_Trans_h.stnh_t_Sto_id = Store_Trans.st_to_store
    WHERE Store_Trans_h.stnh_flag = 'S'
        AND Store.activated = 1
        AND Store.sto_id = ?
    GROUP BY
        Item_Catalog.itm_id,
        Item_Catalog.itm_code,
        Store.sto_id
"""

SMART_SOURCE_STOCK_SQL = """
    SELECT
        ics.itm_id,
        ics.sto_id,
        SUM(
            CASE
                WHEN ISNULL(ic.itm_unit1_unit3, 0) = 0 THEN 0
                ELSE ISNULL(ics.itm_qty, 0) / ic.itm_unit1_unit3
            END
        ) AS stock_qty
    FROM Item_Class_Store ics
    INNER JOIN item_catalog ic ON ic.itm_id = ics.itm_id
    WHERE ics.sto_id = ?
      AND ISNULL(ic.itm_active, 1) = 1
    GROUP BY ics.itm_id, ics.sto_id
    HAVING SUM(
        CASE
            WHEN ISNULL(ic.itm_unit1_unit3, 0) = 0 THEN 0
            ELSE ISNULL(ics.itm_qty, 0) / ic.itm_unit1_unit3
        END
    ) > 0
"""

SMART_SOURCE_RECEIVED_QTY_SQL = """
    SELECT
        Item_Catalog.itm_id,
        CAST(
            SUM(Store_Trans.st_itm_quantity / NULLIF(Item_Catalog.itm_unit1_unit3, 0))
            AS decimal(18,2)
        ) AS received_qty
    FROM Store_Trans Store_Trans
    INNER JOIN Item_Catalog Item_Catalog
        ON Item_Catalog.itm_id = Store_Trans.st_itm_id
    INNER JOIN Store Store_1
        ON Store_1.sto_id = Store_Trans.st_to_store
    LEFT JOIN Store_Trans_h h
        ON h.stnh_id = Store_Trans.stnh_id
        AND h.stnh_f_Sto_id = Store_Trans.st_from_store
        AND h.stnh_t_Sto_id = Store_Trans.st_to_store
    WHERE Store_Trans.sec_insert_date > ?
        AND Store_Trans.st_to_store = ?
        AND h.stnh_flag = 'R'
    GROUP BY Item_Catalog.itm_id
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


class AbTransferSmartSourceStockCache(AbTransferSmartCacheTools, models.Model):
    _name = "ab_transfer_smart_source_stock_cache"
    _inherit = ["ab_eplus_connect"]
    _description = "Smart Transfer Source Opening Stock Cache"
    _order = "cache_date desc, store_id, product_eplus_serial"
    _SOURCE_STOCK_CACHE_LOCK_NAMESPACE = 1907351901

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
    received_qty = fields.Float(
        string="Received Quantity",
        digits=(16, 4),
        aggregator="sum",
        default=0.0,
        readonly=True,
        copy=False,
    )
    received_updated_at = fields.Datetime(
        string="Received Updated At",
        readonly=True,
        copy=False,
    )
    cache_date = fields.Date(
        string="Cache Date",
        required=True,
        index=True,
        default=lambda self: self._get_cache_date(),
    )

    _uniq_smart_source_stock_store_product_cache_date = models.Constraint(
        "UNIQUE(store_id, product_eplus_serial, cache_date)",
        "Smart transfer source stock cache already exists for this store, product, and date.",
    )

    def init(self):
        super().init()
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_transfer_smart_source_stock_cache_store_date_idx
                ON ab_transfer_smart_source_stock_cache (store_id, cache_date)
        """)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS ab_transfer_smart_source_stock_cache_store_product_date_idx
                ON ab_transfer_smart_source_stock_cache (store_id, product_eplus_serial, cache_date)
        """)

    @api.model
    def refresh_stores_cache(self, stores, force=False):
        stores = self.env["ab_store"].browse(stores.ids if hasattr(stores, "ids") else stores).exists()
        result = {
            "stores": len(stores),
            "stock_rows": 0,
        }
        for store in stores:
            result["stock_rows"] += self.sudo().refresh_store_cache(store, force=force)
        return result

    @api.model
    def refresh_store_cache(self, store, force=False):
        store = self._ensure_store_record(store)
        cache_date = self._get_cache_date()
        if not force and self._has_today_cache(store, cache_date):
            return 0

        self._lock_source_stock_cache_refresh(store)
        if not force and self._has_today_cache(store, cache_date):
            return 0

        rows = self._fetch_store_stock_rows(store)
        vals_list = [
            {
                "store_id": store.id,
                "product_eplus_serial": product_serial,
                "stock_qty": stock_qty,
                "cache_date": cache_date,
            }
            for product_serial, stock_qty in rows.items()
            if product_serial and float(stock_qty or 0.0) > 0.0
        ]
        if force:
            self._delete_cache_day(store, cache_date)
        if vals_list:
            self.create(vals_list)
        return len(vals_list)

    @api.model
    def _lock_source_stock_cache_refresh(self, store):
        self.env.cr.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            [self._SOURCE_STOCK_CACHE_LOCK_NAMESPACE, int(store.id)],
        )

    @api.model
    def _delete_cache_day(self, store, cache_date):
        self.search([
            ("store_id", "=", store.id),
            ("cache_date", "=", cache_date),
        ]).unlink()

    @api.model
    def _has_today_cache(self, store, cache_date):
        return bool(self.search_count([
            ("store_id", "=", store.id),
            ("cache_date", "=", cache_date),
        ]))

    @api.model
    def read_store_cache_rows(self, store, product_serials=None, cache_date=None):
        return self.read_store_cache_context(
            store,
            product_serials=product_serials,
            cache_date=cache_date,
        )["stock_by_serial"]

    @api.model
    def read_store_cache_context(self, store, product_serials=None, cache_date=None):
        store = self._ensure_store_record(store)
        cache_date = cache_date or self._get_cache_date()
        base_domain = [
            ("store_id", "=", store.id),
            ("cache_date", "=", cache_date),
        ]
        snapshot_record = self.search(
            base_domain,
            order="create_date, id",
            limit=1,
        )
        domain = list(base_domain)
        serials = sorted({
            self._safe_int(product_serial)
            for product_serial in product_serials or []
            if product_serial
        })
        if serials:
            domain.append(("product_eplus_serial", "in", serials))

        return {
            "has_cache": bool(snapshot_record),
            "snapshot_at": snapshot_record.create_date if snapshot_record else False,
            "stock_by_serial": {
                int(line.product_eplus_serial): (
                    float(line.stock_qty or 0.0)
                    + float(line.received_qty or 0.0)
                )
                for line in self.search(domain)
            },
        }

    @api.model
    def refresh_store_received_qty(self, store):
        store = self._ensure_store_record(store)
        cache_date = self._get_cache_date()
        self.refresh_store_cache(store, force=False)
        self._lock_source_stock_cache_refresh(store)
        cache_context = self.read_store_cache_context(store, cache_date=cache_date)
        snapshot_at = cache_context["snapshot_at"]
        if not cache_context["has_cache"] or not snapshot_at:
            raise UserError(
                _("Cannot get received quantities because source stock snapshot is missing for %(store)s.")
                % {"store": store.display_name}
            )

        received_by_product = self._fetch_store_received_qty_rows(store, snapshot_at)
        today_lines = self.search([
            ("store_id", "=", store.id),
            ("cache_date", "=", cache_date),
        ])
        now = fields.Datetime.now()
        if today_lines:
            today_lines.write({
                "received_qty": 0.0,
                "received_updated_at": now,
            })

        lines_by_serial = {
            int(line.product_eplus_serial): line
            for line in today_lines
        }
        vals_list = []
        updated_products = 0
        total_received_qty = 0.0
        for product_serial, received_qty in received_by_product.items():
            product_serial = self._safe_int(product_serial)
            received_qty = float(received_qty or 0.0)
            if not product_serial or received_qty == 0.0:
                continue
            line = lines_by_serial.get(product_serial)
            if line:
                line.write({
                    "received_qty": received_qty,
                    "received_updated_at": now,
                })
            else:
                vals_list.append({
                    "store_id": store.id,
                    "product_eplus_serial": product_serial,
                    "stock_qty": 0.0,
                    "received_qty": received_qty,
                    "received_updated_at": now,
                    "cache_date": cache_date,
                })
            updated_products += 1
            total_received_qty += received_qty
        if vals_list:
            self.create(vals_list)
        return {
            "products": updated_products,
            "total_received_qty": total_received_qty,
        }

    @api.model
    def _fetch_store_received_qty_rows(self, store, snapshot_at):
        store_sql_id = self._get_store_sql_id(store)
        server = self._get_store_server(store)
        try:
            received_by_product = {}
            with self.connect_eplus(
                    server=server,
                    param_str="?",
                    autocommit=True,
                    propagate_error=True,
            ) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        SMART_SOURCE_RECEIVED_QTY_SQL,
                        (snapshot_at, store_sql_id),
                    )
                    for product_serial, received_qty in cursor.fetchall() or []:
                        product_serial = self._safe_int(product_serial)
                        received_qty = float(received_qty or 0.0)
                        if product_serial and received_qty != 0.0:
                            received_by_product[product_serial] = received_qty
            return received_by_product
        except Exception as error:
            _logger.exception(
                "Smart transfer source received quantity refresh failed: store=%s",
                store.display_name,
            )
            raise UserError(
                _("Smart transfer source received quantity refresh failed for %(store)s: %(error)s")
                % {"store": store.display_name, "error": error}
            )

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
                    cursor.execute(SMART_SOURCE_STOCK_SQL, (store_sql_id,))
                    for product_serial, _store_sql_id, stock_qty in cursor.fetchall() or []:
                        product_serial = self._safe_int(product_serial)
                        stock_qty = float(stock_qty or 0.0)
                        if product_serial and stock_qty > 0.0:
                            stock_by_product[product_serial] = stock_qty
            return stock_by_product
        except Exception as error:
            _logger.exception("Smart transfer source stock cache refresh failed: store=%s", store.display_name)
            raise UserError(
                _("Smart transfer source stock cache refresh failed for %(store)s: %(error)s")
                % {"store": store.display_name, "error": error}
            )

    @staticmethod
    def _safe_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


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
    stock_pending_qty = fields.Float(
        string="Pending Stock Quantity",
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
        onhand_by_product = self._fetch_store_stock_rows(store)
        pending_by_product = self._fetch_store_pending_stock_rows(store)
        product_serials = sorted(set(onhand_by_product) | set(pending_by_product))
        vals_list = [
            {
                "store_id": store.id,
                "product_eplus_serial": product_serial,
                "stock_qty": (
                    float(onhand_by_product.get(product_serial, 0.0) or 0.0)
                    + float(pending_by_product.get(product_serial, 0.0) or 0.0)
                ),
                "stock_pending_qty": float(
                    pending_by_product.get(product_serial, 0.0) or 0.0
                ),
                "cache_date": cache_date,
            }
            for product_serial in product_serials
            if product_serial and (
                float(onhand_by_product.get(product_serial, 0.0) or 0.0)
                + float(pending_by_product.get(product_serial, 0.0) or 0.0)
            ) != 0.0
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

    @api.model
    def _fetch_store_pending_stock_rows(self, store):
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
                    cursor.execute(SMART_DESTINATION_PENDING_STOCK_SQL, (store_sql_id,))
                    for product_serial, _product_code, _store_sql_id, stock_qty in cursor.fetchall() or []:
                        product_serial = self._safe_int(product_serial)
                        stock_qty = float(stock_qty or 0.0)
                        if product_serial and stock_qty != 0.0:
                            stock_by_product[product_serial] = stock_qty
            return stock_by_product
        except Exception as error:
            _logger.exception(
                "Smart transfer pending stock cache refresh failed: store=%s",
                store.display_name,
            )
            raise UserError(
                _("Smart transfer pending stock cache refresh failed for %(store)s: %(error)s")
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
