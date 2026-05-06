from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AbQualityAssuranceVisitLine(models.Model):
    _name = "ab_quality_assurance_visit_line"
    _description = "Quality Assurance Visit Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    visit_section_id = fields.Many2one("ab_quality_assurance_visit_section", required=True, ondelete="cascade")
    visit_id = fields.Many2one(related="visit_section_id.visit_id", store=True, readonly=True)
    section_id = fields.Many2one(related="visit_section_id.section_id", store=True, readonly=True)
    standard_id = fields.Many2one("ab_quality_assurance_standard", required=True, ondelete="restrict")
    department_id = fields.Many2one(related="visit_id.department_id", store=True, readonly=True)
    title = fields.Char(related="standard_id.title", store=True, readonly=True)
    max_score = fields.Float(related="standard_id.max_score", store=True, readonly=True, string="Max Score")
    percentage = fields.Float(compute="_compute_percentage", store=True, readonly=True)
    score = fields.Float(default=False)
    attachment = fields.Binary(attachment=True)
    attachment_name = fields.Char()
    has_attachment = fields.Boolean(compute="_compute_has_attachment")
    active = fields.Boolean(default=True)

    _ab_quality_assurance_visit_line_section_standard_uniq = models.Constraint(
        "UNIQUE(visit_section_id, standard_id)",
        "Each standard can only appear once per section review.",
    )

    @api.depends("attachment")
    def _compute_has_attachment(self):
        for record in self:
            record.has_attachment = bool(record.attachment)

    @api.depends("score", "max_score")
    def _compute_percentage(self):
        for record in self:
            if record.score is not False and record.max_score:
                record.percentage = (record.score / record.max_score) * 100
                continue
            record.percentage = 0.0

    @api.onchange("score")
    def _onchange_score(self):
        for record in self:
            record._validate_score_range()

    @api.constrains("score")
    def _check_score_range(self):
        for record in self:
            record._validate_score_range()

    @api.constrains("section_id", "standard_id")
    def _check_standard_section(self):
        for record in self:
            if record.standard_id.section_id != record.section_id:
                raise ValidationError(_("Visit line standards must belong to the selected section."))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._check_visit_is_editable()
        return records

    def write(self, vals):
        self._check_visit_is_editable()
        return super().write(vals)

    def unlink(self):
        self._check_visit_is_editable()
        return super().unlink()

    def _check_visit_is_editable(self):
        if any(line.visit_id.state == "submitted" for line in self):
            raise UserError(_("Submitted visits cannot be modified."))

    def _validate_score_range(self):
        for record in self:
            if record.score is False:
                continue
            if record.max_score and 0 <= record.score <= record.max_score:
                continue
            raise ValidationError(_("Score must be between 0 and the standard maximum score."))
