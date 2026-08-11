from odoo import fields, models


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    sales_channel_id = fields.Many2one(
        "ab_sales_channel",
        string="Sales Channel",
        ondelete="restrict",
    )
