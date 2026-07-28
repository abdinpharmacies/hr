from odoo import api, fields, models, _


class AbProductDoctorPrescription(models.Model):
    _name = "ab_product_doctor_prescription"
    _description = "Doctor Prescription Product"
    _order = "doctor_id, product_id"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    doctor_id = fields.Many2one(
        "ab_doctor",
        required=True,
        index=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(
        "ab_product",
        required=True,
        index=True,
        ondelete="restrict",
    )
    product_code = fields.Char(related="product_id.code", string="Code", store=True)
    uom_id = fields.Many2one("ab_product_uom", string="UoM")
    qty = fields.Float(default=1.0)
    sell_price = fields.Float()
    last_sales_header_id = fields.Many2one(
        "ab_sales_header",
        string="Last Bill",
        readonly=True,
        ondelete="set null",
    )
    last_sales_line_id = fields.Many2one(
        "ab_sales_line",
        string="Last Bill Line",
        readonly=True,
        ondelete="set null",
    )
    note = fields.Char()
    active = fields.Boolean(default=True)

    _uniq_doctor_product = models.Constraint(
        "UNIQUE(doctor_id, product_id)",
        _("This product is already registered for this doctor."),
    )

    @api.depends("doctor_id.name", "product_id.name", "product_id.product_card_name")
    def _compute_name(self):
        for rec in self:
            doctor_name = rec.doctor_id.display_name or ""
            product_name = rec.product_id.display_name or ""
            rec.name = " - ".join(part for part in [doctor_name, product_name] if part)
