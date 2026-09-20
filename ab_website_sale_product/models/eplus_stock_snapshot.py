import logging
from datetime import date, datetime
from decimal import Decimal

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare
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

EPLUS_STOCK_STORE_SQL = """
    SELECT
        ics.itm_id,
        ic.itm_code,
        ics.sto_id,
        s.sto_code,
        s.sto_name_ar,
        s.sto_name_en,
        SUM(ics.itm_qty) AS itm_qty
    FROM Item_Class_Store ics WITH (NOLOCK)
    JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
    LEFT JOIN Store s WITH (NOLOCK) ON s.sto_id = ics.sto_id
    GROUP BY ics.itm_id, ic.itm_code, ics.sto_id, s.sto_code, s.sto_name_ar, s.sto_name_en
"""

EPLUS_STOCK_STORE_BASIC_SQL = """
    SELECT
        ics.itm_id,
        ic.itm_code,
        ics.sto_id,
        SUM(ics.itm_qty) AS itm_qty
    FROM Item_Class_Store ics WITH (NOLOCK)
    JOIN Item_Catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
    GROUP BY ics.itm_id, ic.itm_code, ics.sto_id
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

    def action_refresh_branch_stock_from_eplus(self):
        result = self.sudo()._refresh_branch_stock_from_eplus()
        message = _("Eplus branch stock refreshed: %(total)s rows, %(matched)s matched, %(unmatched)s unmatched.") % {
            "total": result["total"],
            "matched": result["matched"],
            "unmatched": result["unmatched"],
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Eplus Branch Stock"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_sync_to_odoo_inventory(self):
        if not self:
            raise UserError(_("Select one or more Eplus stock rows to sync to Odoo Inventory."))

        result = self.sudo()._sync_to_odoo_inventory()
        message = _(
            "Odoo inventory synced from Eplus: %(updated)s updated, %(unchanged)s unchanged, "
            "%(skipped)s skipped."
        ) % {
            "updated": result["updated"],
            "unchanged": result["unchanged"],
            "skipped": result["skipped"],
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

    def action_start_full_inventory_sync(self):
        return self.env["ab_eplus_inventory_sync_job"].sudo().action_open_full_sync_console()

    def action_open_eplus_branch_stock(self):
        records = self.sudo().filtered(lambda record: record.active)
        if not records:
            raise UserError(_("Select active Eplus stock rows to inspect branch quantities."))
        domain = [("active", "=", True), ("itm_id", "in", records.mapped("itm_id"))]
        return {
            "type": "ir.actions.act_window",
            "name": _("Eplus Branch Stock"),
            "res_model": "ab_eplus_stock_snapshot_store",
            "view_mode": "list,pivot,form",
            "domain": domain,
            "context": {"search_default_group_by_store": 1},
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
    def _refresh_branch_stock_from_eplus(self):
        store_rows = self._fetch_eplus_stock_store_rows() or []
        itm_ids = [row["itm_id"] for row in store_rows]
        itm_codes = [row["itm_code"] for row in store_rows if row["itm_code"]]
        products_by_serial = self._get_products_by_eplus_serial(itm_ids)
        products_by_code = self._get_products_by_code(itm_codes)
        return self.env["ab_eplus_stock_snapshot_store"].sudo()._refresh_from_eplus_rows(
            store_rows,
            products_by_serial=products_by_serial,
            products_by_code=products_by_code,
            sync_date=fields.Datetime.now(),
        )

    def _sync_to_odoo_inventory(self):
        warehouse = self._get_inventory_sync_warehouse()
        location = warehouse.lot_stock_id
        if not location:
            raise UserError(_("The selected warehouse has no stock location."))

        selected_records = self.sudo().filtered(lambda record: record.active and record.product_id)
        if not selected_records:
            raise UserError(_("Select matched active Eplus stock rows to sync."))

        groups = self.sudo()._read_group(
            [("id", "in", selected_records.ids), ("active", "=", True), ("product_id", "!=", False)],
            groupby=["product_id"],
            aggregates=["itm_qty:sum"],
        )
        if not groups:
            raise UserError(_("No matched Eplus stock rows are available to sync."))

        products_by_ab_product = self._get_inventory_sync_products(groups)
        Quant = self.env["stock.quant"].sudo().with_context(inventory_mode=True)
        products = self.env["product.product"].sudo().browse([
            product.id for product in products_by_ab_product.values()
        ])
        current_qty_by_product = self._get_inventory_sync_current_quantities(products, location)
        base_quant_by_product = self._get_inventory_sync_base_quants(products, location)
        quants_to_apply = Quant.browse()
        create_vals = []
        updated_count = 0
        unchanged_count = 0
        skipped_count = 0

        for ab_product, eplus_qty in groups:
            product = products_by_ab_product.get(ab_product.id)
            if not product or product.type == "service":
                skipped_count += 1
                continue

            target_qty = max(eplus_qty or 0.0, 0.0)
            current_qty = current_qty_by_product.get(product.id, 0.0)
            rounding = product.uom_id.rounding
            if float_compare(current_qty, target_qty, precision_rounding=rounding) == 0:
                unchanged_count += 1
                continue

            base_quant = base_quant_by_product.get(product.id)
            delta_qty = target_qty - current_qty
            if base_quant:
                target_base_qty = base_quant.quantity + delta_qty
                base_quant.inventory_quantity = target_base_qty
                quants_to_apply |= base_quant
            else:
                create_vals.append({
                    "product_id": product.id,
                    "location_id": location.id,
                    "inventory_quantity": delta_qty,
                })
            updated_count += 1

        if create_vals:
            quants_to_apply |= Quant.create(create_vals)
        if quants_to_apply:
            quants_to_apply.action_apply_inventory()

        _logger.info(
            "Eplus stock synced to Odoo inventory: warehouse=%s updated=%s unchanged=%s skipped=%s",
            warehouse.display_name,
            updated_count,
            unchanged_count,
            skipped_count,
        )
        return {
            "warehouse": warehouse.display_name,
            "updated": updated_count,
            "unchanged": unchanged_count,
            "skipped": skipped_count,
        }

    @api.model
    def _get_inventory_sync_warehouse(self):
        Warehouse = self.env["stock.warehouse"].sudo()
        warehouse = Warehouse.search([
            ("company_id", "=", self.env.company.id),
            ("name", "=", "ABDIN PHARMACIES"),
        ], limit=1)
        if not warehouse:
            warehouse = Warehouse.search([("company_id", "=", self.env.company.id)], limit=1)
        if not warehouse:
            raise UserError(_("No warehouse is configured for this company."))
        return warehouse

    @api.model
    def _get_inventory_sync_products(self, stock_groups):
        ab_products = self.env["ab_product"].sudo().browse([
            ab_product.id for ab_product, __qty in stock_groups if ab_product
        ])
        templates = self.env["product.template"].sudo().with_context(active_test=False).search([
            ("ab_product_id", "in", ab_products.ids),
        ])
        products_by_ab_product = {}
        for template in templates:
            product = template.product_variant_id or template.product_variant_ids[:1]
            if product:
                products_by_ab_product[template.ab_product_id.id] = product.sudo()
        return products_by_ab_product

    @api.model
    def _get_inventory_sync_current_quantities(self, products, location):
        if not products:
            return {}
        groups = self.env["stock.quant"].sudo()._read_group(
            [
                ("product_id", "in", products.ids),
                ("location_id", "child_of", location.id),
            ],
            groupby=["product_id"],
            aggregates=["quantity:sum"],
        )
        return {product.id: quantity or 0.0 for product, quantity in groups}

    @api.model
    def _get_inventory_sync_base_quants(self, products, location):
        if not products:
            return {}
        quants = self.env["stock.quant"].sudo().with_context(active_test=False).search([
            ("product_id", "in", products.ids),
            ("location_id", "=", location.id),
            ("lot_id", "=", False),
            ("package_id", "=", False),
            ("owner_id", "=", False),
        ])
        return {quant.product_id.id: quant for quant in quants}

    @api.model
    def _fetch_eplus_stock_rows(self):
        with self.connect_eplus(param_str="?", charset="CP1256") as conn:
            with conn.cursor() as cursor:
                cursor.execute(EPLUS_STOCK_SQL)
                columns = [column[0] for column in (cursor.description or [])]
                return [self._normalize_eplus_row(row, columns=columns) for row in cursor.fetchall()]

    @api.model
    def _fetch_eplus_stock_store_rows(self):
        try:
            return self._execute_eplus_stock_store_query(EPLUS_STOCK_STORE_SQL)
        except Exception:
            _logger.warning(
                "Eplus branch stock query with Store metadata failed; retrying with sto_id only.",
                exc_info=True,
            )
            return self._execute_eplus_stock_store_query(EPLUS_STOCK_STORE_BASIC_SQL)

    @api.model
    def _execute_eplus_stock_store_query(self, sql):
        with self.connect_eplus(param_str="?", charset="CP1256") as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                columns = [column[0] for column in (cursor.description or [])]
                rows = cursor.fetchall() or []
                return [
                    self._normalize_eplus_store_row(row, columns=columns)
                    for row in rows
                ]

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
    def _normalize_eplus_store_row(self, row, columns=None):
        if not isinstance(row, dict):
            columns = columns or ["itm_id", "itm_code", "sto_id", "itm_qty"]
            row = dict(zip(columns, row))

        normalized_row = {
            str(key).lower(): value
            for key, value in row.items()
        }
        itm_id = normalized_row.get("itm_id")
        itm_code = normalized_row.get("itm_code")
        sto_id = normalized_row.get("sto_id")
        itm_qty = normalized_row.get("itm_qty")
        extra_data = {
            key: self._json_safe_value(value)
            for key, value in normalized_row.items()
            if key not in {"itm_id", "itm_code", "sto_id", "sto_code", "sto_name_ar", "sto_name_en", "itm_qty"}
        }
        return {
            "itm_id": int(itm_id or 0),
            "itm_code": str(itm_code or "").strip(),
            "sto_id": int(sto_id or 0),
            "sto_code": str(normalized_row.get("sto_code") or "").strip(),
            "store_name_ar": str(normalized_row.get("sto_name_ar") or "").strip(),
            "store_name_en": str(normalized_row.get("sto_name_en") or "").strip(),
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


class EplusStockSnapshotStore(models.Model):
    _name = "ab_eplus_stock_snapshot_store"
    _description = "Eplus Branch Stock Snapshot"
    _order = "itm_code, itm_id, sto_id"

    itm_id = fields.Integer(string="Eplus Item ID", required=True, index=True, readonly=True)
    itm_code = fields.Char(string="Item Code", index=True, readonly=True)
    sto_id = fields.Integer(string="Eplus Store ID", required=True, index=True, readonly=True)
    sto_code = fields.Char(string="Store Code", index=True, readonly=True)
    store_name_ar = fields.Char(string="Store Name Arabic", readonly=True)
    store_name_en = fields.Char(string="Store Name English", readonly=True)
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

    _itm_store_unique = models.UniqueIndex(
        "(itm_id, sto_id)",
        "Each Eplus item can only appear once per branch in the eCommerce branch stock snapshot.",
    )

    @api.model
    def _refresh_from_eplus_rows(self, rows, products_by_serial=None, products_by_code=None, sync_date=None):
        rows = rows or []
        now = sync_date or fields.Datetime.now()
        products_by_serial = products_by_serial or {}
        products_by_code = products_by_code or {}
        keys = [(row["itm_id"], row["sto_id"]) for row in rows]
        existing_by_key = {
            (rec.itm_id, rec.sto_id): rec
            for rec in self.with_context(active_test=False).search([
                ("itm_id", "in", [key[0] for key in keys] or [0]),
                ("sto_id", "in", [key[1] for key in keys] or [0]),
            ])
        }

        vals_to_create = []
        touched_ids = []
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
                "sto_id": row["sto_id"],
                "sto_code": row["sto_code"],
                "store_name_ar": row["store_name_ar"],
                "store_name_en": row["store_name_en"],
                "itm_qty": row["itm_qty"],
                "extra_data": row["extra_data"],
                "product_id": product.id if product else False,
                "matched_by": matched_by,
                "last_sync_date": now,
                "active": True,
            }
            key = (itm_id, row["sto_id"])
            existing = existing_by_key.get(key)
            if existing:
                existing.write(vals)
                touched_ids.append(existing.id)
            else:
                vals_to_create.append(vals)

        if vals_to_create:
            touched_ids.extend(self.create(vals_to_create).ids)

        stale_domain = [("active", "=", True)]
        if touched_ids:
            stale_domain.append(("id", "not in", touched_ids))
        stale_records = self.search(stale_domain)
        if stale_records:
            stale_records.write({"active": False, "last_sync_date": now})

        return {
            "total": len(rows),
            "matched": matched_count,
            "unmatched": unmatched_count,
            "stale": len(stale_records),
        }
