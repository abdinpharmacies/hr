from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

HR_RESOLUTION_GROUP = "ab_hr.group_ab_hr_personnel_spec"


class AbRequestFollowup(models.Model):
    _name = "ab_request_followup"
    _description = "Request Follow-up"
    _order = "date desc, id desc"

    request_id = fields.Many2one(
        "ab_request",
        required=True,
        ondelete="cascade",
        index=True,
    )
    user_id = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        ondelete="restrict",
    )
    description = fields.Text(required=True)
    date = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    is_resolved_solution = fields.Boolean(string="Resolved", readonly=True, copy=False, index=True)
    relative_time_label = fields.Char(compute="_compute_relative_time_label", string="Relative Time")
    resolution_label = fields.Char(compute="_compute_resolution_label", string="Status")

    @api.depends("date")
    def _compute_relative_time_label(self):
        now = fields.Datetime.now()
        for record in self:
            if not record.date:
                record.relative_time_label = False
                continue
            delta = now - fields.Datetime.to_datetime(record.date)
            total_seconds = max(int(delta.total_seconds()), 0)
            minutes = total_seconds // 60
            hours = minutes // 60
            days = hours // 24
            if days == 0:
                if minutes < 1:
                    record.relative_time_label = _("Just now")
                elif minutes < 60:
                    record.relative_time_label = _("%s min ago") % minutes
                else:
                    record.relative_time_label = _("%s hour(s) ago") % hours
            elif days == 1:
                record.relative_time_label = _("Yesterday")
            elif days < 7:
                record.relative_time_label = _("%s day(s) ago") % days
            else:
                record.relative_time_label = fields.Datetime.to_string(record.date)

    @api.depends("is_resolved_solution")
    def _compute_resolution_label(self):
        for record in self:
            record.resolution_label = _("Official Solution") if record.is_resolved_solution else _("Note")

    @api.model_create_multi
    def create(self, vals_list):
        """Create follow-ups with request-level permission checks."""
        requests = self.env["ab_request"].browse([vals["request_id"] for vals in vals_list if vals.get("request_id")])
        requests._check_followup_creation_rights()
        prepared_vals_list = [self._prepare_vals(vals) for vals in vals_list]
        records = super().create(prepared_vals_list)
        for record in records:
            message = record.request_id.message_post(
                body=record.description,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )
            message.ab_is_followup_message = True
        return records

    def write(self, vals):
        """Prevent edits to follow-ups after creation."""
        if self.env.context.get("allow_followup_resolution_write") and set(vals) <= {"is_resolved_solution"}:
            return super().write(vals)
        raise ValidationError(_("Follow-ups cannot be edited once created."))

    def action_mark_as_solution(self):
        """Move the official solution marker to this follow-up row."""
        if not self.env.user.has_group(HR_RESOLUTION_GROUP):
            raise UserError(_("Only HR users can change the official solution follow-up."))
        for record in self:
            record.request_id.followup_ids.filtered("is_resolved_solution").with_context(
                allow_followup_resolution_write=True
            ).write({"is_resolved_solution": False})
            record.with_context(allow_followup_resolution_write=True).write({"is_resolved_solution": True})
        return True

    def unlink(self):
        """Prevent follow-up deletion to keep the timeline auditable."""
        raise ValidationError(_("Follow-ups cannot be deleted."))

    @api.model
    def _prepare_vals(self, vals):
        """Normalize follow-up values."""
        prepared_vals = dict(vals or {})
        prepared_vals["description"] = (prepared_vals.get("description") or "").strip()
        if not prepared_vals["description"]:
            raise ValidationError(_("Follow-up description is required."))
        prepared_vals.setdefault("user_id", self.env.user.id)
        prepared_vals.setdefault("date", fields.Datetime.now())
        return prepared_vals
