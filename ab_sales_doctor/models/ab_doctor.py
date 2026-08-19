from odoo import api, fields, models


class AbDoctor(models.Model):
    _name = "ab_doctor"
    _description = "Doctor"
    _order = "name"

    name = fields.Char(required=True, index=True)
    code = fields.Char(index=True)
    phone = fields.Char(index=True)
    specialty = fields.Char()
    active = fields.Boolean(default=True)
    prescription_product_ids = fields.One2many(
        "ab_product_doctor_prescription",
        "doctor_id",
        string="Prescription Products",
    )

    @api.depends("code", "name", "specialty")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = " - ".join(
                part
                for part in (
                    (rec.code or "").strip(),
                    (rec.name or "").strip(),
                    (rec.specialty or "").strip(),
                )
                if part
            )

    @api.model
    def _search_display_name(self, operator, value):
        domains = [
            fields.Domain("code", operator, value),
            fields.Domain("name", operator, value),
            fields.Domain("specialty", operator, value),
        ]
        domain = fields.Domain.OR(domains)
        if operator in fields.Domain.NEGATIVE_OPERATORS:
            domain = ["!"] + domain
        return list(domain)
