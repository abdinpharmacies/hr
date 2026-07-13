from datetime import date

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class SalesDashboardSnapshot(models.Model):
    _name = "ab.sales.dashboard.snapshot"
    _description = "Sales Dashboard Snapshot"
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

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = self._normalize_filters(filters)
        snapshot = self._find_latest_snapshot(filters)
        return self._serialize_dashboard(snapshot, filters)

    @api.model
    def refresh_dashboard_data(self, filters=None):
        filters = self._normalize_filters(filters)
        snapshot = self.sudo()._create_snapshot(filters)
        return self._serialize_dashboard(snapshot, filters)

    @api.model
    def _create_snapshot(self, filters):
        stores = self._stores_from_filters(filters)
        if filters["store_id"] and not stores:
            raise UserError(_("The selected store was not found."))
        if any(not store.eplus_serial for store in stores):
            missing = ", ".join(stores.filtered(lambda store: not store.eplus_serial).mapped("display_name"))
            raise UserError(_("These stores have no E-Plus serial: %s") % missing)

        store_eplus_ids = [int(store.eplus_serial) for store in stores]
        payload = self.env["ab.sales.dashboard.service"].fetch_dashboard_data(
            filters["date_from"],
            fields.Date.add(filters["date_to"], days=1),
            store_eplus_ids=store_eplus_ids,
        )
        products_by_serial = self._products_by_serial([row.get("itm_id") for row in payload["item_lines"]])
        store_key = self._store_filter_key(stores)
        vals = {
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
            "collection_line_ids": self._collection_commands(payload["collection_lines"]),
            "user_line_ids": self._user_commands(payload["user_lines"]),
            "item_line_ids": self._item_commands(payload["item_lines"], products_by_serial),
            "invoice_line_ids": self._invoice_commands(payload["invoice_lines"]),
        }
        return self.create(vals)

    @api.model
    def _normalize_filters(self, filters):
        filters = dict(filters or {})
        today = fields.Date.context_today(self)
        first_day = date(today.year, today.month, 1)
        date_from = fields.Date.to_date(filters.get("date_from") or first_day)
        date_to = fields.Date.to_date(filters.get("date_to") or today)
        if date_to < date_from:
            raise UserError(_("Date To must be greater than or equal to Date From."))
        store_id = int(filters.get("store_id") or 0)
        return {"date_from": date_from, "date_to": date_to, "store_id": store_id}

    @api.model
    def _stores_from_filters(self, filters):
        if not filters["store_id"]:
            return self.env["ab_store"]
        return self.env["ab_store"].sudo().browse(filters["store_id"]).exists()

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
    def _available_stores_payload(self):
        stores = self.env["ab_store"].sudo().search([
            ("active", "=", True),
            ("allow_sale", "=", True),
            ("eplus_serial", "!=", False),
        ], order="name")
        return [{"id": store.id, "name": store.display_name} for store in stores]

    @api.model
    def _serialize_dashboard(self, snapshot, filters):
        data = {
            "date_from": fields.Date.to_string(filters["date_from"]),
            "date_to": fields.Date.to_string(filters["date_to"]),
            "store_id": filters["store_id"],
            "stores": self._available_stores_payload(),
            "has_snapshot": bool(snapshot),
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
                "store_filter_label": _("All Stores"),
                "refresh_date": False,
                "collection_lines": [],
                "user_lines": [],
                "item_lines": [],
                "invoice_lines": [],
            })
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
            "store_filter_label": snapshot.store_filter_label,
            "refresh_date": fields.Datetime.to_string(snapshot.refresh_date) if snapshot.refresh_date else False,
            "collection_lines": [line._as_dashboard_dict() for line in snapshot.collection_line_ids],
            "user_lines": [line._as_dashboard_dict() for line in snapshot.user_line_ids],
            "item_lines": [line._as_dashboard_dict() for line in snapshot.item_line_ids],
            "invoice_lines": [line._as_dashboard_dict() for line in snapshot.invoice_line_ids],
        })
        return data

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
    def _collection_commands(self, rows):
        return [(0, 0, {
            "category": row.get("collection_category") or "cash",
            "invoice_count": int(row.get("invoice_count") or 0),
            "total_sales": float(row.get("total_sales") or 0.0),
            "pct_of_total": float(row.get("pct_of_total") or 0.0),
        }) for row in rows]

    @api.model
    def _user_commands(self, rows):
        return [(0, 0, {
            "employee_eplus_id": int(row.get("emp_id") or 0),
            "employee_name": row.get("employee_name") or "",
            "invoice_count": int(row.get("invoice_count") or 0),
            "total_sales": float(row.get("total_sales") or 0.0),
            "pct_of_total": float(row.get("pct_of_total") or 0.0),
        }) for row in rows]

    @api.model
    def _item_commands(self, rows, products_by_serial):
        commands = []
        for row in rows:
            item_id = int(row.get("itm_id") or 0)
            product = products_by_serial.get(item_id)
            commands.append((0, 0, {
                "eplus_item_id": item_id,
                "eplus_item_code": row.get("itm_code") or "",
                "product_id": product.id if product else False,
                "item_name": product.display_name if product else (row.get("itm_code") or str(item_id)),
                "sale_times": int(row.get("sale_times") or 0),
                "sold_qty": float(row.get("sold_qty") or 0.0),
                "current_balance": float(row.get("current_balance") or 0.0),
            }))
        return commands

    @api.model
    def _invoice_commands(self, rows):
        return [(0, 0, {
            "invoice_no": str(row.get("invoice_no") or ""),
            "invoice_date": row.get("sec_insert_date") or False,
            "customer_name": row.get("customer_name") or "",
            "invoice_total": float(row.get("invoice_total") or 0.0),
            "item_count": int(row.get("item_count") or 0),
            "items_summary": row.get("items") or "",
        }) for row in rows]


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
    current_balance = fields.Float(readonly=True)

    def _as_dashboard_dict(self):
        self.ensure_one()
        return {
            "eplus_item_id": self.eplus_item_id,
            "eplus_item_code": self.eplus_item_code,
            "product_name": self.product_id.display_name if self.product_id else self.item_name,
            "sale_times": self.sale_times,
            "sold_qty": self.sold_qty,
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
            "invoice_no": self.invoice_no,
            "invoice_date": fields.Datetime.to_string(self.invoice_date) if self.invoice_date else "",
            "customer_name": self.customer_name,
            "invoice_total": self.invoice_total,
            "item_count": self.item_count,
            "items_summary": self.items_summary,
        }
