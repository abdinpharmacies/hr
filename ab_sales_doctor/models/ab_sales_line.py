from odoo import fields, models


class AbSalesLine(models.Model):
    _inherit = "ab_sales_line"

    is_doctor_prescription_product = fields.Boolean(
        string="Prescription Product",
        default=False,
        index=True,
        help="Enable when this line is part of the selected doctor's prescription.",
    )
