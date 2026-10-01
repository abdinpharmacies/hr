from odoo import fields, models


class AbSalesHeaderContract(models.Model):
    _inherit = "ab_sales_header"

    contract_id = fields.Many2one("ab_contract", string="Contract")

    # Stored totals for clarity on the header.
    discount = fields.Float(
        string="Total Discount",
        store=True,
        readonly=True,
    )
    total_after_discount = fields.Float(
        string="Total After Discount",
        store=True,
        readonly=True,
    )
