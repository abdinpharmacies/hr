from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    is_doctor_prescription = fields.Boolean(
        string="Doctor Prescription",
        default=False,
        index=True,
    )
    doctor_id = fields.Many2one(
        "ab_doctor",
        string="Doctor",
        index=True,
    )
