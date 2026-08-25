from odoo import fields, models


class AbDoctor(models.Model):
    _name = "ab_doctor"
    _description = "Doctor"
    _order = "name"

    name = fields.Char(required=False, index=True)
    code = fields.Char(index=True)
    phone = fields.Char(index=True)
    specialty = fields.Char()
    active = fields.Boolean(default=True)
    prescription_product_ids = fields.One2many(
        "ab_product_doctor_prescription",
        "doctor_id",
        string="Prescription Products",
    )
