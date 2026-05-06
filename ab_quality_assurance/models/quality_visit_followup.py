from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

QUALITY_EDITOR_GROUPS = (
    "ab_quality_assurance.group_ab_quality_assurance_user",
    "ab_quality_assurance.group_ab_quality_assurance_manager",
)
FOLLOW_UP_RESPONSE_WRITE_FIELDS = {"response"}
FOLLOW_UP_RESPONSE_MANAGED_FIELDS = {"response", "response_user_id", "response_date"}
BRANCH_PREFIX = "فرع"


class AbQualityAssuranceVisitFollowup(models.Model):
    _name = "ab_quality_assurance_visit_followup"
    _description = "Quality Assurance Visit Follow Up"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    visit_id = fields.Many2one("ab_quality_assurance_visit", required=True, ondelete="cascade")
    visit_state = fields.Selection(related="visit_id.state", readonly=True)
    department_id = fields.Many2one("ab_hr_department", required=True, ondelete="restrict", string="Management")
    response = fields.Text(copy=False)
    response_user_id = fields.Many2one("res.users", readonly=True, copy=False, string="Responded By")
    response_date = fields.Datetime(readonly=True, copy=False, string="Responded On")
    can_edit_response = fields.Boolean(compute="_compute_permissions")
    can_manage_follow_up = fields.Boolean(compute="_compute_permissions")
    active = fields.Boolean(default=True)

    _ab_quality_assurance_visit_followup_department_uniq = models.Constraint(
        "UNIQUE(visit_id, department_id)",
        "Each management can only be added once per visit follow-up.",
    )

    @api.depends("department_id", "visit_id.user_id")
    @api.depends_context("uid")
    def _compute_permissions(self):
        user = self.env.user
        user_departments = user.ab_department_ids
        can_edit_own = any(user.has_group(group) for group in QUALITY_EDITOR_GROUPS)
        can_manage_all = user.has_group("ab_quality_assurance.group_ab_quality_assurance_manager")
        for record in self:
            record.can_manage_follow_up = bool(can_manage_all or (can_edit_own and record.visit_id.user_id == user))
            record.can_edit_response = bool(record.department_id in user_departments)

    @api.constrains("department_id")
    def _check_department(self):
        for record in self:
            if not record.department_id:
                raise ValidationError(_("Please select a management for the follow-up."))
            if (record.department_id.name or "").startswith(BRANCH_PREFIX):
                raise ValidationError(_("Follow-up responses can only be assigned to management departments."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            visit = self.env["ab_quality_assurance_visit"].browse(vals.get("visit_id"))
            self._check_can_manage_visit_follow_up(visit)
            self._check_response_values_for_create(vals)
        return super().create(vals_list)

    def write(self, vals):
        requested_fields = set((vals or {}).keys())
        if requested_fields & FOLLOW_UP_RESPONSE_MANAGED_FIELDS:
            if self._can_write_response():
                if requested_fields - FOLLOW_UP_RESPONSE_WRITE_FIELDS:
                    raise AccessError(_("Only selected departments can add follow-up responses."))
                values = dict(vals)
                values.update(
                    {
                        "response_user_id": self.env.user.id,
                        "response_date": fields.Datetime.now(),
                    }
                )
                return super().write(values)
            raise AccessError(_("Only selected departments can add follow-up responses."))
        self._check_can_manage_visit_follow_up(self.mapped("visit_id"))
        return super().write(vals)

    def unlink(self):
        self._check_can_manage_visit_follow_up(self.mapped("visit_id"))
        return super().unlink()

    def _can_write_response(self):
        user_departments = self.env.user.ab_department_ids
        return bool(self) and all(follow_up.department_id in user_departments for follow_up in self)

    def _check_response_values_for_create(self, vals):
        if not any(vals.get(field_name) for field_name in FOLLOW_UP_RESPONSE_MANAGED_FIELDS):
            return True
        department = self.env["ab_hr_department"].browse(vals.get("department_id")).exists()
        if department and department in self.env.user.ab_department_ids:
            vals.update(
                {
                    "response_user_id": self.env.user.id,
                    "response_date": fields.Datetime.now(),
                }
            )
            return True
        raise AccessError(_("Only selected departments can add follow-up responses."))

    def _check_can_manage_visit_follow_up(self, visits):
        visits = visits.exists()
        user = self.env.user
        can_edit_own = any(user.has_group(group) for group in QUALITY_EDITOR_GROUPS)
        can_manage_all = user.has_group("ab_quality_assurance.group_ab_quality_assurance_manager")
        if can_manage_all or (can_edit_own and all(visit.user_id == user for visit in visits)):
            return True
        raise AccessError(_("Only the visit creator or a quality assurance manager can manage follow-up departments."))
