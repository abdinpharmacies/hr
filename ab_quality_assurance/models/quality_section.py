from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AbQualityAssuranceSection(models.Model):
    _name = "ab_quality_assurance_section"
    _description = "Quality Assurance Section"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    name = fields.Char(required=True)
    department_id = fields.Many2one(
        "ab_hr_department",
        string="Responsible Department",
        ondelete="restrict",
        index=True,
    )
    department_manager_id = fields.Many2one(
        "ab_hr_employee",
        related="department_id.manager_id",
        store=True,
        readonly=True,
    )
    standard_ids = fields.One2many("ab_quality_assurance_standard", "section_id", string="Standards")
    standard_count = fields.Integer(compute="_compute_standard_count")

    _ab_quality_assurance_section_name_uniq = models.Constraint(
        "UNIQUE(name)",
        "Section name must be unique.",
    )

    @api.depends("standard_ids")
    def _compute_standard_count(self):
        for record in self:
            record.standard_count = len(record.standard_ids)

    @api.constrains("name")
    def _check_name(self):
        for record in self:
            if not record.name.strip():
                raise ValidationError(_("Section name cannot be empty."))

    @api.model
    def _prepare_vals(self, vals):
        prepared_vals = dict(vals or {})
        if prepared_vals.get("name"):
            prepared_vals["name"] = prepared_vals["name"].strip()
        return prepared_vals

    def _sync_visit_department_followers(self):
        visits = self.env["ab_quality_assurance_visit"].sudo().search(
            [("visit_section_ids.section_id", "in", self.ids)]
        )
        visits._sync_section_department_followers()
