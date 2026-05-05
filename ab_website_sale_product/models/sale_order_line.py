from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    ab_product_id = fields.Many2one(
        "ab_product",
        string="Abdin Product",
        related="product_id.ab_product_id",
        store=True,
        readonly=True,
        groups="base.group_user",
    )
