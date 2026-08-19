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
    smart_over_need_qty = fields.Float(
        string="Over Need",
        digits=(16, 3),
        compute="_compute_smart_over_need_qty",
        readonly=True,
    )
    smart_distribution_ratio = fields.Float(
        string="Distribution Ratio",
        digits=(16, 6),
        readonly=True,
        copy=False,
    )

    @api.depends("smart_source_stock_qty", "smart_total_need")
    def _compute_smart_over_need_qty(self):
        for line in self:
            line.smart_over_need_qty = (
                float(line.smart_source_stock_qty or 0.0)
                - float(line.smart_total_need or 0.0)
            )

    @api.depends("smart_source_stock_qty", "product_id", "from_store_id", "header_id")
    def _compute_smart_expected_source_stock_qty(self):
        valid_lines = self.filtered(lambda line: line.product_id and line.from_store_id)
        for line in self:
            line.smart_expected_source_stock_qty = float(
                line.smart_source_stock_qty or 0.0
            )

        for header in valid_lines.mapped("header_id"):
            header_lines = valid_lines.filtered(lambda line: line.header_id == header)
            expected_context = header._get_smart_expected_source_stock_context(
                header_lines,
            )
            for line in header_lines:
                opening_qty = expected_context["opening_qty_by_product"].get(
                    line.product_id.id,
                    0.0,
                )
                reserved_qty = expected_context["reserved_qty_by_product"].get(
                    line.product_id.id,
                    0.0,
                )
                line.smart_expected_source_stock_qty = opening_qty - reserved_qty
