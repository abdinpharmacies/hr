from odoo import fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    ab_stock_recycling_branch_store_id = fields.Many2one(
        "ab_store",
        string="Stock Recycling Branch Store",
        help="Branch role users are restricted to this sending store.",
    )
