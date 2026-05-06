from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

QUALITY_EDITOR_GROUPS = (
    "ab_quality_assurance.group_ab_quality_assurance_user",
    "ab_quality_assurance.group_ab_quality_assurance_manager",
)


class AbQualityAssuranceVisitLine(models.Model):
    _name = "ab_quality_assurance_visit_line"
    _description = "Quality Assurance Visit Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    visit_section_id = fields.Many2one("ab_quality_assurance_visit_section", required=True, ondelete="cascade")
    visit_id = fields.Many2one(related="visit_section_id.visit_id", store=True, readonly=True)
    visit_state = fields.Selection(related="visit_id.state", readonly=True)
    section_id = fields.Many2one(related="visit_section_id.section_id", store=True, readonly=True)
    standard_id = fields.Many2one("ab_quality_assurance_standard", required=True, ondelete="restrict")
    department_id = fields.Many2one(related="visit_id.department_id", store=True, readonly=True)
    title = fields.Char(related="standard_id.title", store=True, readonly=True)
    max_score = fields.Float(related="standard_id.max_score", store=True, readonly=True, string="Max Score")
    percentage = fields.Float(compute="_compute_percentage", store=True, readonly=True)
    score = fields.Float(default=False)
    note = fields.Text(string="Score Note", copy=False)
    attachment = fields.Binary(attachment=True)
    attachment_name = fields.Char()
    has_attachment = fields.Boolean(compute="_compute_has_attachment")
    can_upload_attachment = fields.Boolean(compute="_compute_can_upload_attachment")
    active = fields.Boolean(default=True)

    _ab_quality_assurance_visit_line_section_standard_uniq = models.Constraint(
        "UNIQUE(visit_section_id, standard_id)",
        "Each standard can only appear once per section review.",
    )

    @api.depends("attachment")
    def _compute_has_attachment(self):
        for record in self:
            record.has_attachment = bool(record.attachment)

    @api.depends("visit_state", "visit_id.user_id")
    @api.depends_context("uid")
    def _compute_can_upload_attachment(self):
        user = self.env.user
        can_edit_own = any(user.has_group(group) for group in QUALITY_EDITOR_GROUPS)
        can_manage_all = user.has_group("ab_quality_assurance.group_ab_quality_assurance_manager")
        for record in self:
            can_manage_visit = bool(can_manage_all or (can_edit_own and record.visit_id.user_id == user))
            record.can_upload_attachment = bool(can_manage_visit and record.visit_state != "submitted")

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

    def action_download_attachment(self):
        self.ensure_one()
        if not self.attachment:
            raise UserError(_("There is no attachment to download for this standard."))
        return {
            "type": "ir.actions.act_url",
            "url": (
                "/web/content/%s/%s/attachment?download=true&filename_field=attachment_name"
                % (self._name, self.id)
            ),
            "target": "self",
        }

    def _check_visit_is_editable(self):
        if any(line.visit_id.state == "submitted" for line in self):
            raise UserError(_("Submitted visits cannot be modified."))
        user = self.env.user
        can_edit_own = any(user.has_group(group) for group in QUALITY_EDITOR_GROUPS)
        can_manage_all = user.has_group("ab_quality_assurance.group_ab_quality_assurance_manager")
        if not can_manage_all and (not can_edit_own or any(line.visit_id.user_id != user for line in self)):
            raise AccessError(_("Only the visit creator or a quality assurance manager can modify visit scores."))

    def _validate_score_range(self):
        for record in self:
            if record.score is False:
                continue
            if record.max_score and 0 <= record.score <= record.max_score:
                continue
            raise ValidationError(_("Score must be between 0 and the standard maximum score."))
