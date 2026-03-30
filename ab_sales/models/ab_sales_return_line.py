# -*- coding: utf-8 -*-
import math

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError
import decimal

PARAM_STR = '?'  # ظ†ظپط³ ط§ظ„ظ…طھط؛ظٹط± ط§ظ„ظ…ظˆط¬ظˆط¯ ط¹ظ†ط¯ظƒ


def _to_native(v):
    """Normalize all values so Odoo never receives Decimal or strange types."""
    if isinstance(v, decimal.Decimal):
        # int ظ„ظˆ ظ…ظپظٹط´ ظƒط³ظˆط± â€“ ط؛ظٹط± ظƒط¯ظ‡ float
        if v == v.to_integral():
            return int(v)
        return float(v)
    if v is None:
        return False
    return v


class AbdinSalesReturnLine(models.Model):
    _name = 'ab_sales_return_line'
    _description = 'E-Plus Sales Return Line'
    _inherit = ['ab_product_qty']
    _order = 'id'

    header_id = fields.Many2one(
        'ab_sales_return_header',
        string="Return Header",
        required=True,
        ondelete='cascade',
    )

    sale_line_id = fields.Integer(
        string="Original Line (optional)",
    )

    qty_str = fields.Char(
        string='Qty',
        required=True,
        default='0',
        help='Enter arithmetic expression, e.g. 1/3, 2.5*4, 10-3, 2*1.25',
    )

    product_id = fields.Many2one(
        'ab_product',
        string="Product",
        required=False,
        readonly=True,
    )
    product_uom_category_id = fields.Many2one(
        related='product_id.uom_category_id',
        readonly=True,
        store=False,
    )
    uom_id = fields.Many2one(
        'ab_product_uom',
        string="UoM",
        domain="[('category_id', '=', product_uom_category_id)]",
    )

    source_itm_unit = fields.Integer(
        string="Source Unit",
        readonly=True,
        help="Original sales_trans_d.itm_unit value.",
    )
    source_uom_factor = fields.Float(
        string="Source UoM Factor",
        digits=(16, 6),
        readonly=True,
        help="Number of small units in one source unit.",
    )
    item_unit1_unit2 = fields.Float(
        string="itm_unit1_unit2",
        digits=(16, 6),
        readonly=True,
    )
    item_unit1_unit3 = fields.Float(
        string="itm_unit1_unit3",
        digits=(16, 6),
        readonly=True,
    )

    qty_sold = fields.Float(string="Sold Qty", readonly=True)
    qty_sold_source = fields.Float(string="Sold Qty (source)", readonly=True)
    max_returnable_qty = fields.Float(
        digits=(10,4),
        string="Max Returnable",
        help="Maximum quantity allowed to be returned for this line.",
        readonly=True,
    )
    max_returnable_source = fields.Float(
        digits=(10, 4),
        string="Max Returnable (source)",
        readonly=True,
    )
    qty_to_return = fields.Float(string="Qty to return")

    sell_price = fields.Float(string="Sell Price", readonly=True, )
    cost = fields.Float(string="Cost", readonly=True, )

    line_value = fields.Float(
        string="Line Value",
        compute='_compute_line_value',
        store=True,
    )

    # ظ…ظپط§طھظٹط­ ط§ظ„ط±ط¨ط· ظ…ط¹ E-Plus
    itm_eplus_id = fields.Integer(
        string="E-Plus Item ID (itm_id)",
        help="Item ID in E-Plus (item_catalog.itm_id).", readonly=True,
    )
    sth_id = fields.Integer(
        string="sth_id",
        help="Original sales_trans_h.sth_id (E-Plus header ID).",
        readonly=True,
    )
    sto_id = fields.Integer(
        string="sto_id",
        help="Store ID in Item_Class_Store / sales_trans_d.",
        readonly=True,
    )
    c_id = fields.Integer(
        string="c_id",
        help="Class/source ID used in sales_trans_d and Item_Class_Store (batch).",
        readonly=True,
    )
    std_id = fields.Integer(
        string="std_id",
        help="Row ID inside sales_trans_d. ظ†ط­طھط§ط¬ظ‡ ظپظٹ WHERE ط¨طھط­ط¯ظٹط« ط³ط·ط± ط§ظ„ظپط§طھظˆط±ط©.",
        readonly=True,
    )

    itm_nexist = fields.Boolean(default=False, readonly=True, )

    @api.depends('qty', 'sell_price')
    def _compute_line_value(self):
        for rec in self:
            rec.line_value = (rec.qty or 0.0) * (rec.sell_price or 0.0)

    @staticmethod
    def _fmt_qty(value):
        try:
            value = float(value or 0.0)
        except Exception:
            value = 0.0
        return f"{value:.4f}".rstrip('0').rstrip('.') or "0"

    def _get_selected_factor(self):
        self.ensure_one()
        factor = float(self.uom_id.factor or 0.0) if self.uom_id else 0.0
        if factor <= 0:
            factor = float(self.source_uom_factor or 0.0)
        if factor <= 0:
            factor = 1.0
        return factor

    def _get_source_factor(self):
        self.ensure_one()
        factor = float(self.source_uom_factor or 0.0)
        if factor <= 0:
            factor = 1.0
        return factor

    def _qty_to_source_unit(self, qty=None):
        self.ensure_one()
        selected_factor = self._get_selected_factor()
        source_factor = self._get_source_factor()
        if qty is None:
            qty = float(self.qty or 0.0)
        else:
            qty = float(qty or 0.0)
        if selected_factor <= 0 or source_factor <= 0:
            return qty
        return qty * selected_factor / source_factor

    def _price_to_source_unit(self, price=None):
        self.ensure_one()
        selected_factor = self._get_selected_factor()
        source_factor = self._get_source_factor()
        if price is None:
            price = float(self.sell_price or 0.0)
        else:
            price = float(price or 0.0)
        if selected_factor <= 0 or source_factor <= 0:
            return price
        return price * source_factor / selected_factor

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        for rec in self:
            source_factor = rec._get_source_factor()
            new_factor = rec._get_selected_factor()
            old_factor = new_factor
            if rec._origin and rec._origin.uom_id and rec._origin.uom_id.factor:
                old_factor = float(rec._origin.uom_id.factor or 0.0) or new_factor
            elif source_factor > 0:
                old_factor = source_factor

            # Keep current qty meaning stable across unit switch.
            current_qty = float(rec.qty or 0.0)
            qty_in_small = current_qty * old_factor
            next_qty = qty_in_small / (new_factor or 1.0)
            rec.qty_str = self._fmt_qty(next_qty)

            # Keep source-based numbers stable while displaying in selected UoM.
            sold_source = float(rec.qty_sold_source or 0.0)
            rem_source = float(rec.max_returnable_source or 0.0)
            rec.qty_sold = sold_source * source_factor / (new_factor or 1.0)
            rec.max_returnable_qty = rem_source * source_factor / (new_factor or 1.0)

            # Convert displayed price from old UoM to new UoM via source-unit price.
            sell_source = float(rec.sell_price or 0.0) * (source_factor or 1.0) / (old_factor or 1.0)
            cost_source = float(rec.cost or 0.0) * (source_factor or 1.0) / (old_factor or 1.0)
            rec.sell_price = sell_source * (new_factor or 1.0) / (source_factor or 1.0)
            rec.cost = cost_source * (new_factor or 1.0) / (source_factor or 1.0)

    @api.constrains('qty', 'max_returnable_qty')
    def _check_qty_limits(self):
        for rec in self:
            if rec.qty < 0:
                raise UserError(_("Return quantity cannot be negative."))
            if rec.max_returnable_qty and rec.qty > rec.max_returnable_qty and not math.isclose(
                float(rec.qty or 0.0), float(rec.max_returnable_qty or 0.0), rel_tol=0.0, abs_tol=1e-4
            ):
                raise UserError(_("Return quantity exceeds max returnable quantity."))
