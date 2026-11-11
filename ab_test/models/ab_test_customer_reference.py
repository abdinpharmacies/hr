from odoo import fields, models


class AbTestCustomerReference(models.Model):
    _name = "ab_test_customer_reference"
    _description = "AB Sync Test Customer Reference"
    _order = "reference, id"

    name = fields.Char(required=True)
    reference = fields.Char(required=True, index=True)
    customer_id = fields.Many2one(
        "ab_customer",
        string="Customer",
        required=True,
        ondelete="restrict",
        index=True,
    )
    note = fields.Text()
    active = fields.Boolean(default=True, index=True)

    _uniq_reference = models.Constraint(
        "UNIQUE(reference)",
        "Customer reference must be unique.",
    )
