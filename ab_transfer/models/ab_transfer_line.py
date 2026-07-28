# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class AbTransferLine(models.Model):
    _name = "ab_transfer_line"
    _description = "Transfer Line"
    _order = "id desc"

    header_id = fields.Many2one(
        "ab_transfer_header",
        string="Transfer Header",
        required=True,
        ondelete="cascade",
    )

    from_store_id = fields.Many2one(
        "ab_store",
        string="From Store",
        related="header_id.from_store_id",
        store=True,
        readonly=True,
    )

    to_store_id = fields.Many2one(
        "ab_store",
        string="To Store",
        related="header_id.to_store_id",
        store=True,
        readonly=True,
    )

    product_id = fields.Many2one(
        "ab_product",
        string="Product",
        required=True,
    )

    class_id = fields.Integer(
        string="Class ID",
        required=True,
    )

    qty = fields.Float(
        string="Quantity",
        required=True,
        digits=(16, 3),
        default=1.0,
    )

    expiry_date = fields.Date(
        string="Expiry Date",
        required=True,
    )

    user_id = fields.Many2one(
        "ab_costcenter",
        string="User",
        related="header_id.user_id",
        store=True,
        readonly=True,
    )

    uom_id = fields.Many2one(
        "ab_product_uom",
        string="UOM",
        required=True,
    )

    inventory_json = fields.Json(
        string="Inventory JSON",
        store=True,
        default=dict,
        compute="_recompute_inventory_json",
        help="Structured inventory data: {'data': [...]}",
    )

    sell_price = fields.Float(
        string="Sell Price",
        digits=(16, 3),
        compute="_compute_inventory_metrics",
        store=True,
    )

    cost = fields.Float(
        string="Cost",
        digits=(16, 3),
        compute="_compute_inventory_metrics",
        store=True,
    )

    purchase_price = fields.Float(
        string="Purchase Price",
        digits=(16, 3),
        compute="_compute_inventory_metrics",
        store=True,
    )

    tax_value = fields.Float(
        string="Tax Value",
        digits=(16, 3),
        compute="_compute_inventory_metrics",
        store=True,
    )

    inventory_table_html = fields.Html(
        string="Inventory Table",
        compute="_compute_inventory_table_html",
        sanitize=True,
        store=False,
        readonly=True,
    )

    state = fields.Selection(
        related="header_id.selection",
        store=True,
        string="Status",
    )

    is_submitted = fields.Boolean(
        related="header_id.is_submitted",
        readonly=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
        required=True,
    )

    @api.depends("product_id", "header_id.from_store_id")
    def _recompute_inventory_json(self):
        for rec in self:
            rec.inventory_json = {"data": []}
            if not rec.product_id or not rec.header_id or not rec.header_id.from_store_id:
                continue

            try:
                product_sql_id = rec.header_id._get_ref_id(rec.product_id, "Product")
                from_store_sql_id = rec.header_id._get_ref_id(rec.header_id.from_store_id, "From Store")

                with rec.header_id._get_sql_connection() as conn:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            """
                            SELECT ics.c_id                        AS source_id,
                                   ics.itm_id                      AS product_eplus_serial,
                                   ics.sto_id                      AS store_eplus_serial,
                                   ISNULL(ics.sell_price, 0)       AS sell_price,
                                   ISNULL(ics.itm_qty, 0)          AS qty_in_small_unit,
                                   CASE
                                       WHEN ISNULL(ic.itm_unit1_unit3, 0) = 0 THEN 0
                                       ELSE ISNULL(ics.itm_qty, 0) / ic.itm_unit1_unit3
                                       END                         AS qty,
                                   ISNULL(ics.pharm_price, 0)      AS pharm_price,
                                   ISNULL(ics.sell_tax, 0)         AS sell_tax,
                                   ics.itm_expiry_date             AS exp_date,
                                   ISNULL(ic.itm_purchase_unit, 1) AS itm_purchase_unit,
                                   ISNULL(ic.itm_unit1_unit2, 1)   AS itm_unit1_unit2,
                                   ISNULL(ic.itm_unit1_unit3, 1)   AS itm_unit1_unit3
                            FROM Item_Class_Store ics
                                     INNER JOIN item_catalog ic ON ic.itm_id = ics.itm_id
                            WHERE ics.sto_id = ?
                              AND ics.itm_id = ?
                              AND ISNULL(ics.itm_qty, 0) > 0
                            ORDER BY ics.itm_expiry_date, ics.c_id
                            """,
                            (from_store_sql_id, product_sql_id),
                        )
                        rows = cursor.fetchall() or []
            except Exception:
                _logger.exception(
                    "Failed to recompute transfer inventory JSON for product %s",
                    rec.product_id.id,
                )
                continue

            inventory_rows = []
            for row in rows:
                try:
                    itm_purchase_unit = int(row[9] or 1)
                    itm_unit1_unit2 = int(row[10] or 1)
                    itm_unit1_unit3 = int(row[11] or 1)
                    if itm_purchase_unit == 2:
                        unit_factor = float(itm_unit1_unit2 or 1)
                    elif itm_purchase_unit == 3:
                        unit_factor = float(itm_unit1_unit3 or 1)
                    else:
                        unit_factor = 1.0

                    qty_big = float(row[5] or 0.0)
                    if qty_big < 0.01:
                        continue

                    pharm_price = float(row[6] or 0.0) * unit_factor
                    sell_tax = float(row[7] or 0.0) * unit_factor
                    inventory_rows.append({
                        "store_id": rec.header_id.from_store_id.id,
                        "store_eplus_serial": int(row[2] or 0),
                        "product_id": rec.product_id.id,
                        "product_eplus_serial": int(row[1] or 0),
                        "qty": qty_big,
                        "qty_in_small_unit": float(row[4] or 0.0),
                        "price": float(row[3] or 0.0) * unit_factor,
                        "cost": pharm_price,
                        "sell_tax": sell_tax,
                        "pharm_price": pharm_price,
                        "source_id": int(row[0] or 0),
                        "exp_date": str(row[8] or ""),
                    })
                except Exception:
                    continue

            rec.inventory_json = {"data": inventory_rows}

    @api.depends("inventory_json", "class_id")
    def _compute_inventory_metrics(self):
        for rec in self:
            selected = rec._get_selected_inventory_row()
            rec.sell_price = float(selected.get("price") or 0.0)
            rec.cost = float(selected.get("cost") or 0.0)
            rec.tax_value = float(selected.get("sell_tax") or 0.0)
            rec.purchase_price = float(selected.get("pharm_price") or 0.0)

    def _get_inventory_rows(self):
        self.ensure_one()
        payload = self.inventory_json or {}
        if not isinstance(payload, dict):
            return []
        return payload.get("data") or []

    def _get_selected_inventory_row(self):
        self.ensure_one()
        rows = self._get_inventory_rows()
        if not rows:
            return {}
        if self.class_id:
            for row in rows:
                if int(row.get("source_id") or 0) == int(self.class_id or 0):
                    return row
        return rows[0]

    def _apply_inventory_defaults(self):
        for rec in self:
            if rec.product_id and rec.product_id.uom_id and not rec.uom_id:
                rec.uom_id = rec.product_id.uom_id
            selected = rec._get_selected_inventory_row()
            if not selected:
                continue
            if not rec.class_id:
                rec.class_id = int(selected.get("source_id") or 0)
            exp_text = str(selected.get("exp_date") or "").split(" ")[0]
            if exp_text:
                rec.expiry_date = exp_text

    @api.depends("inventory_json", "product_id")
    def _compute_inventory_table_html(self):
        for rec in self:
            items = rec._get_inventory_rows()

            item_d = defaultdict(float)
            for item in items:
                qty = item.get("qty") or 0.0
                price = item.get("price")
                exp_date = item.get("exp_date")
                exp = exp_date and str(exp_date).split(" ")[0]
                item_d[(price, exp)] += qty

            unique_rows = [
                {"qty": qty, "price": price, "exp": exp}
                for (price, exp), qty in item_d.items()
            ]
            unique_rows.sort(
                key=lambda row: (row["exp"] or "", row["qty"] or 0),
                reverse=True,
            )

            if unique_rows:
                tr_html = []
                for row in unique_rows:
                    qty_txt = (
                        f"{int(row['qty'])}"
                        if isinstance(row["qty"], (int, float)) and float(row["qty"]).is_integer()
                        else f"{row['qty']}"
                    )
                    price_txt = f"{row['price']}"
                    exp_txt = row["exp"] or ""
                    tr_html.append(
                        "<tr>"
                        f"<td>{html_escape(price_txt)}</td>"
                        f"<td>{html_escape(exp_txt)}</td>"
                        f"<td>{html_escape(qty_txt)}</td>"
                        "</tr>"
                    )
                body = "".join(tr_html)
            else:
                body = (
                    "<tr><td colspan='3' "
                    "style='text-align:center;color:#888'>No data</td></tr>"
                )

            rec.inventory_table_html = (
                "<table class='o_list_view table table-sm' style='width:100%;'>"
                "<thead><tr><th>Price</th><th>Exp. Date</th><th>Qty</th></tr></thead>"
                f"<tbody>{body}</tbody>"
                "</table>"
            )

    @api.constrains("qty")
    def _check_qty(self):
        for rec in self:
            if rec.qty <= 0:
                raise ValidationError(_("Quantity must be greater than zero."))

    @api.constrains("from_store_id", "to_store_id")
    def _check_store_difference(self):
        for rec in self:
            if rec.from_store_id and rec.to_store_id and rec.from_store_id == rec.to_store_id:
                raise ValidationError(_("Source store and destination store cannot be the same."))

    @api.constrains("expiry_date")
    def _check_expiry_date(self):
        for rec in self:
            if not rec.expiry_date:
                raise ValidationError(_("Expiry date is required."))

    def _check_header_not_is_submitted(self):
        locked = self.filtered(lambda rec: rec.header_id.is_submitted)
        if locked:
            raise ValidationError(_("Submitted transfer lines cannot be edited."))

    @api.model_create_multi
    def create(self, vals_list):
        header_ids = [vals.get("header_id") for vals in vals_list if vals.get("header_id")]
        if header_ids:
            headers = self.env["ab_transfer_header"].browse(header_ids).exists()
            if any(headers.mapped("is_submitted")):
                raise ValidationError(_("Submitted transfer lines cannot be edited."))
        return super().create(vals_list)

    def write(self, vals):
        allowed_after_submit = {"state", "is_submitted"}
        if vals and set(vals) - allowed_after_submit:
            self._check_header_not_is_submitted()
        return super().write(vals)

    def unlink(self):
        self._check_header_not_is_submitted()
        return super().unlink()

    @api.onchange("header_id")
    def _onchange_header_id(self):
        self._recompute_inventory_json()
        self._apply_inventory_defaults()

    @api.onchange("product_id")
    def _onchange_product_id(self):
        self._recompute_inventory_json()
        self._apply_inventory_defaults()

    @api.onchange("class_id")
    def _onchange_class_id(self):
        for rec in self:
            selected = rec._get_selected_inventory_row()
            exp_text = str(selected.get("exp_date") or "").split(" ")[0]
            if exp_text:
                rec.expiry_date = exp_text

    def name_get(self):
        result = []
        for rec in self:
            name = "%s - %s" % (
                rec.product_id.display_name if rec.product_id else _("Product"),
                rec.qty or 0,
            )
            result.append((rec.id, name))
        return result
