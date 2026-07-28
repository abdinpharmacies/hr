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

    @api.constrains("is_doctor_prescription", "doctor_id")
    def _check_doctor_prescription_has_doctor(self):
        for rec in self:
            if rec.is_doctor_prescription and not rec.doctor_id:
                raise ValidationError(_("Doctor is required for doctor prescription bills."))

    def _doctor_prescription_lines(self):
        return self.mapped("line_ids").filtered(
            lambda line: (
                line.header_id.is_doctor_prescription
                and line.header_id.doctor_id
                and line.product_id
                and line.is_doctor_prescription_product
            )
        )

    def _sync_doctor_prescription_products(self):
        lines = self._doctor_prescription_lines()
        if not lines:
            return self.env["ab_product_doctor_prescription"]

        doctor_ids = lines.mapped("header_id.doctor_id").ids
        product_ids = lines.mapped("product_id").ids
        Prescription = self.env["ab_product_doctor_prescription"].sudo()
        existing = Prescription.search([
            ("doctor_id", "in", doctor_ids),
            ("product_id", "in", product_ids),
        ])
        existing_by_key = {
            (rec.doctor_id.id, rec.product_id.id): rec
            for rec in existing
        }

        created = Prescription.browse()
        to_create = []
        for line in lines:
            key = (line.header_id.doctor_id.id, line.product_id.id)
            vals = line._prepare_doctor_prescription_values()
            record = existing_by_key.get(key)
            if record:
                record.write(vals)
            else:
                to_create.append(vals)
        if to_create:
            created = Prescription.create(to_create)
        return existing | created

    def action_submit(self):
        result = True
        for rec in self:
            if rec.is_doctor_prescription:
                if not rec.doctor_id:
                    raise UserError(_("Doctor is required for doctor prescription bills."))
                if not rec.line_ids.filtered("is_doctor_prescription_product"):
                    raise UserError(_("At least one line must be marked as a prescription product."))
            result = super(AbSalesHeader, rec).action_submit()
            rec._sync_doctor_prescription_products()
        return result

