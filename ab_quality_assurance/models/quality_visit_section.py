from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

QUALITY_EDITOR_GROUPS = (
    "ab_quality_assurance.group_ab_quality_assurance_user",
    "ab_quality_assurance.group_ab_quality_assurance_manager",
)


class AbQualityAssuranceVisitSection(models.Model):
    _name = "ab_quality_assurance_visit_section"
    _description = "Quality Assurance Visit Section"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    visit_id = fields.Many2one("ab_quality_assurance_visit", required=True, ondelete="cascade")
    section_id = fields.Many2one("ab_quality_assurance_section", required=True, ondelete="restrict")
    name = fields.Char(related="section_id.name", store=True, readonly=True)
    department_id = fields.Many2one(related="section_id.department_id", store=True, readonly=True)
    department_manager_id = fields.Many2one(related="section_id.department_manager_id", store=True, readonly=True)
    visit_line_ids = fields.One2many("ab_quality_assurance_visit_line", "visit_section_id", string="Standards")
    earned_score = fields.Float(compute="_compute_totals", store=True)
    max_score = fields.Float(compute="_compute_totals", store=True)
    percentage = fields.Float(compute="_compute_totals", store=True)
    active = fields.Boolean(default=True)

    _ab_quality_assurance_visit_section_visit_section_uniq = models.Constraint(
        "UNIQUE(visit_id, section_id)",
        "Each section can only appear once per visit.",
    )

    @api.depends("visit_line_ids", "visit_line_ids.score", "visit_line_ids.max_score")
    def _compute_totals(self):
        for record in self:
            scored_lines = record.visit_line_ids.filtered(lambda line: line.score is not False)
            record.earned_score = sum(record.visit_line_ids.mapped("score"))
            record.max_score = sum(record.visit_line_ids.mapped("max_score"))
            scored_max_total = sum(scored_lines.mapped("max_score"))
            record.percentage = (
                        sum(scored_lines.mapped("score")) / scored_max_total * 100) if scored_max_total else 0.0

    @api.onchange("section_id")
    def _onchange_section_id(self):
        if not self.section_id or (self.visit_id and self.visit_id.state == "submitted"):
            return
        self.visit_line_ids = self._build_line_commands(self._get_active_standards())

    @api.constrains("visit_line_ids", "section_id")
    def _check_lines_match_section(self):
        for record in self:
            invalid_lines = record.visit_line_ids.filtered(
                lambda line: line.standard_id.section_id != record.section_id)
            if invalid_lines:
                raise ValidationError(_("All standards in a visit section must belong to the same section."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_vals(vals, for_create=True) for vals in vals_list]
        records = super().create(prepared_vals_list)
        records._check_visit_is_editable()
        return records

    def write(self, vals):
        self._check_visit_is_editable()
        return super().write(self._prepare_vals(vals, for_create=False))

    def unlink(self):
        self._check_visit_is_editable()
        return super().unlink()

    def _check_visit_is_editable(self):
        if any(section.visit_id.state == "submitted" for section in self):
            raise UserError(_("Submitted visits cannot be modified."))
        user = self.env.user
        can_edit_own = any(user.has_group(group) for group in QUALITY_EDITOR_GROUPS)
        can_manage_all = user.has_group("ab_quality_assurance.group_ab_quality_assurance_manager")
        if not can_manage_all and (not can_edit_own or any(section.visit_id.user_id != user for section in self)):
            raise AccessError(_("Only the visit creator or a quality assurance manager can modify visit sections."))

    def _get_active_standards(self):
        self.ensure_one()
        return self.section_id.standard_ids.filtered("active").sorted(lambda record: (record.sequence, record.id))

    @api.model
    def _build_line_commands(self, standards):
        return [
            fields.Command.create(
                {
                    "sequence": standard.sequence,
                    "standard_id": standard.id,
                    "score": False,
                }
            )
            for standard in standards
        ]

    @api.model
    def _prepare_vals(self, vals, for_create=False):
        prepared_vals = dict(vals or {})
        section_id = prepared_vals.get("section_id")
        if section_id and "visit_line_ids" not in prepared_vals:
            section = self.env["ab_quality_assurance_section"].browse(section_id)
            standards = section.standard_ids.filtered("active").sorted(lambda record: (record.sequence, record.id))
            prepared_vals["visit_line_ids"] = self._build_line_commands(standards)
        return prepared_vals
