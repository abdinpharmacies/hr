from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AbQualityAssuranceStandard(models.Model):
    _name = "ab_quality_assurance_standard"
    _description = "Quality Assurance Standard"
    _order = "section_id, sequence, id"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    section_id = fields.Many2one("ab_quality_assurance_section", required=True, ondelete="restrict", index=True)
    title = fields.Char(required=True)
    max_score = fields.Float(required=True, string="Total Score")

    _ab_quality_assurance_standard_title_section_uniq = models.Constraint(
        "UNIQUE(section_id, title)",
        "Standard title must be unique per section.",
    )

    @api.constrains("max_score")
    def _check_positive_values(self):
        for record in self:
            if record.max_score <= 0:
                raise ValidationError(_("Standard total score must be greater than zero."))

    @api.model
    def _prepare_vals(self, vals):
        prepared_vals = dict(vals or {})
        if prepared_vals.get("title"):
            prepared_vals["title"] = prepared_vals["title"].strip()
        return prepared_vals
