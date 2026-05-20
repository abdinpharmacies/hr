import logging
from datetime import date, datetime
from decimal import Decimal

from odoo import api, fields, models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


EPLUS_STOCK_SQL = """
    SELECT
        ics.itm_id,
        ic.itm_code,
        SUM(ics.itm_qty) AS itm_qty
    FROM Item_Class_Store ics WITH (NOLOCK)
    JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
    GROUP BY ics.itm_id, ic.itm_code
"""


class EplusStockSnapshot(models.Model):
    _name = "ab_eplus_stock_snapshot"
    _inherit = ["ab_eplus_connect"]
    _description = "Eplus Stock Snapshot"
    _order = "itm_code, itm_id"

    itm_id = fields.Integer(string="Eplus Item ID", required=True, index=True, readonly=True)
    itm_code = fields.Char(string="Item Code", index=True, readonly=True)
    itm_qty = fields.Float(string="Eplus Quantity", readonly=True)
    extra_data = fields.Json(string="Additional Attributes", readonly=True)
    product_id = fields.Many2one("ab_product", string="Abdin Product", index=True, readonly=True)
    product_code = fields.Char(related="product_id.code", string="Product Code", readonly=True)
    product_name = fields.Char(related="product_id.name", string="Product Name", readonly=True)
    matched_by = fields.Selection(
        selection=[
            ("eplus_serial", "Eplus ID"),
            ("code", "Item Code"),
            ("none", "Not Matched"),
        ],
        default="none",
        required=True,
        readonly=True,
    )
    last_sync_date = fields.Datetime(string="Last Refresh", readonly=True)
    active = fields.Boolean(default=True, index=True)

    _itm_id_unique = models.UniqueIndex(
        "(itm_id)",
        "Each Eplus item can only appear once in the eCommerce stock snapshot.",
    )

    def action_refresh_from_eplus(self):
        result = self.sudo()._refresh_from_eplus()
        message = _("Eplus stock refreshed: %(total)s rows, %(matched)s matched, %(unmatched)s unmatched.") % {
            "total": result["total"],
            "matched": result["matched"],
            "unmatched": result["unmatched"],
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Eplus Stock"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    @api.model
    def _refresh_from_eplus(self):
        rows = self._fetch_eplus_stock_rows()
        now = fields.Datetime.now()
        itm_ids = [row["itm_id"] for row in rows]
        itm_codes = [row["itm_code"] for row in rows if row["itm_code"]]

        products_by_serial = self._get_products_by_eplus_serial(itm_ids)
        products_by_code = self._get_products_by_code(itm_codes)
        existing_by_itm_id = {
            rec.itm_id: rec
            for rec in self.with_context(active_test=False).search([("itm_id", "in", itm_ids)])
        }

        vals_to_create = []
        seen_itm_ids = set()
        matched_count = 0
        unmatched_count = 0

        for row in rows:
            itm_id = row["itm_id"]
            itm_code = row["itm_code"]
            product = products_by_serial.get(itm_id)
            matched_by = "eplus_serial" if product else "none"
            if not product and itm_code:
                product = products_by_code.get(itm_code)
                matched_by = "code" if product else "none"

            if product:
                matched_count += 1
            else:
                unmatched_count += 1

            vals = {
                "itm_id": itm_id,
                "itm_code": itm_code,
                "itm_qty": row["itm_qty"],
                "extra_data": row["extra_data"],
                "product_id": product.id if product else False,
                "matched_by": matched_by,
                "last_sync_date": now,
                "active": True,
            }
            existing = existing_by_itm_id.get(itm_id)
            if existing:
                existing.write(vals)
            else:
                vals_to_create.append(vals)
            seen_itm_ids.add(itm_id)

        if vals_to_create:
            self.create(vals_to_create)

        stale_domain = [("active", "=", True)]
        if seen_itm_ids:
            stale_domain.append(("itm_id", "not in", list(seen_itm_ids)))
        stale_records = self.search(stale_domain)
        if stale_records:
            stale_records.write({"active": False, "last_sync_date": now})

        _logger.info(
            "Eplus stock snapshot refreshed: total=%s matched=%s unmatched=%s stale=%s",
            len(rows),
            matched_count,
            unmatched_count,
            len(stale_records),
        )
        return {
            "total": len(rows),
            "matched": matched_count,
            "unmatched": unmatched_count,
            "stale": len(stale_records),
        }

    @api.model
    def _fetch_eplus_stock_rows(self):
        with self.connect_eplus(param_str="?", charset="CP1256") as conn:
            with conn.cursor() as cursor:
                cursor.execute(EPLUS_STOCK_SQL)
                columns = [column[0] for column in (cursor.description or [])]
                return [self._normalize_eplus_row(row, columns=columns) for row in cursor.fetchall()]

    @api.model
    def _normalize_eplus_row(self, row, columns=None):
        if not isinstance(row, dict):
            columns = columns or ["itm_id", "itm_code", "itm_qty"]
            row = dict(zip(columns, row))

        normalized_row = {
            str(key).lower(): value
            for key, value in row.items()
        }
        itm_id = normalized_row.get("itm_id")
        itm_code = normalized_row.get("itm_code")
        itm_qty = normalized_row.get("itm_qty")
        extra_data = {
            key: self._json_safe_value(value)
            for key, value in normalized_row.items()
            if key not in {"itm_id", "itm_code", "itm_qty"}
        }
        return {
            "itm_id": int(itm_id or 0),
            "itm_code": str(itm_code or "").strip(),
            "itm_qty": float(itm_qty or 0.0),
            "extra_data": extra_data,
        }

    @api.model
    def _json_safe_value(self, value):
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return value

    @api.model
    def _get_products_by_eplus_serial(self, itm_ids):
        products = self.env["ab_product"].sudo().with_context(active_test=False).search([
            ("eplus_serial", "in", itm_ids),
        ])
        products_by_serial = {}
        for product in products:
            products_by_serial.setdefault(int(product.eplus_serial or 0), product)
        return products_by_serial

    @api.model
    def _get_products_by_code(self, itm_codes):
        products = self.env["ab_product"].sudo().with_context(active_test=False).search([
            ("code", "in", itm_codes),
        ])
        products_by_code = {}
        for product in products:
            code = (product.code or "").strip()
            if code:
                products_by_code.setdefault(code, product)
        return products_by_code
