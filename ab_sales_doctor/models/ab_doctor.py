import re

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


DOCTOR_CODE_PATTERN = re.compile(r"^[A-Za-z0-9]+$")


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

    @api.model
    def _normalize_doctor_code(self, code):
        return str(code or "").strip()

    @api.model
    def _normalize_doctor_specialty(self, specialty):
        return str(specialty or "").strip()

    @api.model
    def _validate_doctor_code_format(self, code):
        if not code:
            raise ValidationError(_("Doctor code is required."))
        if not DOCTOR_CODE_PATTERN.fullmatch(code):
            raise ValidationError(_("Doctor code must contain only English letters and digits."))

    @api.model
    def _validate_doctor_specialty_value(self, specialty):
        if not specialty:
            raise ValidationError(_("Doctor specialty is required."))

    @api.model
    def _check_duplicate_doctor_codes_in_values(self, vals_list):
        seen_codes = {}
        for vals in vals_list:
            code = vals.get("code")
            code_key = (code or "").casefold()
            if not code_key:
                continue
            if code_key in seen_codes:
                raise ValidationError(_("Doctor code must be unique."))
            seen_codes[code_key] = code

    @api.model
    def _check_existing_doctor_code_duplicates(self, vals_list, excluded_ids=None):
        codes = [
            vals.get("code")
            for vals in vals_list
            if vals.get("code")
        ]
        if not codes:
            return

        domain = fields.Domain("code", "in", codes)
        for code in codes:
            domain |= fields.Domain("code", "=ilike", code)
        if excluded_ids:
            domain &= fields.Domain("id", "not in", list(set(excluded_ids)))

        existing = self.with_context(active_test=False).search(list(domain), limit=1)
        if existing:
            raise ValidationError(_("Doctor code already exists."))

    @api.model
    def _prepare_doctor_create_values(self, vals_list):
        prepared_vals = []
        for vals in vals_list:
            next_vals = dict(vals)
            code = self._normalize_doctor_code(next_vals.get("code"))
            specialty = self._normalize_doctor_specialty(next_vals.get("specialty"))
            self._validate_doctor_code_format(code)
            self._validate_doctor_specialty_value(specialty)
            next_vals["code"] = code
            next_vals["specialty"] = specialty
            prepared_vals.append(next_vals)

        self._check_duplicate_doctor_codes_in_values(prepared_vals)
        self._check_existing_doctor_code_duplicates(prepared_vals)
        return prepared_vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create(self._prepare_doctor_create_values(vals_list))

    def write(self, vals):
        next_vals = dict(vals)
        changed_code = "code" in next_vals
        changed_specialty = "specialty" in next_vals

        if changed_code:
            code = self._normalize_doctor_code(next_vals.get("code"))
            self._validate_doctor_code_format(code)
            next_vals["code"] = code
            if len(self) > 1:
                raise ValidationError(_("Doctor code must be unique."))
            self._check_existing_doctor_code_duplicates([next_vals], excluded_ids=self.ids)

        if changed_specialty:
            specialty = self._normalize_doctor_specialty(next_vals.get("specialty"))
            self._validate_doctor_specialty_value(specialty)
            next_vals["specialty"] = specialty

        return super().write(next_vals)

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
