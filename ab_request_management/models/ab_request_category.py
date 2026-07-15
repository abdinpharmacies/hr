from odoo import api, fields, models


class AbRequestCategory(models.Model):
    _name = 'ab_request_category'
    _description = "Request/Complaint Category"

    name = fields.Char(string="Name", translate=True)
    type = fields.Selection(
        [
            ("complaint", "Complaint"),
            ("other", "Other"),
        ],
        default="other",
        string="Type",
        required=True,
    )
