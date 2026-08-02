# -*- coding: utf-8 -*-

from odoo import api, fields, models


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
    smart_expected_source_stock_qty = fields.Float(
        string="Expected Stock",
        digits=(16, 3),
        compute="_compute_smart_expected_source_stock_qty",
        readonly=True,
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

    @api.depends("smart_source_stock_qty", "product_id", "from_store_id")
    def _compute_smart_expected_source_stock_qty(self):
        valid_lines = self.filtered(lambda line: line.product_id and line.from_store_id)
        reserved_qty_by_key = {}
        if valid_lines:
            reserved_qty_by_key = self.env[
                "ab_transfer_header"
            ]._read_smart_active_reserved_qty_by_product_store(
                valid_lines.mapped("product_id").ids,
                valid_lines.mapped("from_store_id").ids,
            )

        for line in self:
            reserved_qty = reserved_qty_by_key.get(
                (line.product_id.id, line.from_store_id.id),
                0.0,
            )
            line.smart_expected_source_stock_qty = (
                float(line.smart_source_stock_qty or 0.0) - reserved_qty
            )
