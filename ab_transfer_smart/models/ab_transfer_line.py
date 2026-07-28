# -*- coding: utf-8 -*-

from odoo import fields, models


class AbTransferLine(models.Model):
    _inherit = "ab_transfer_line"

    smart_product_location = fields.Char(
        string="Location",
        related="product_id.location",
        store=True,
        readonly=True,
    )
    smart_source_stock_qty = fields.Float(
        string="Source Stock",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_qty_before_int = fields.Float(
        string="Qty Before Int",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_destination_stock_qty = fields.Float(
        string="Destination Stock",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_month1_sales = fields.Float(
        string="Month 1 Sales",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_month2_sales = fields.Float(
        string="Month 2 Sales",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_month3_sales = fields.Float(
        string="Month 3 Sales",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_other_stores_stock_qty = fields.Float(
        string="Other Stores Stock",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_other_stores_month1_sales = fields.Float(
        string="Other Month 1 Sales",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_other_stores_month2_sales = fields.Float(
        string="Other Month 2 Sales",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_other_stores_month3_sales = fields.Float(
        string="Other Month 3 Sales",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_need_destination_store = fields.Float(
        string="Destination Need",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_need_other_store = fields.Float(
        string="Other Stores Need",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_total_need = fields.Float(
        string="Total Need",
        digits=(16, 3),
        readonly=True,
        copy=False,
    )
    smart_distribution_ratio = fields.Float(
        string="Distribution Ratio",
        digits=(16, 6),
        readonly=True,
        copy=False,
    )
