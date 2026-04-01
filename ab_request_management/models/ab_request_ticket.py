from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

TICKET_SEQUENCE_CODE = "ab_request_ticket.ticket_number"


class AbRequestTicket(models.Model):
    _name = "ab_request_ticket"
    _description = "Request Ticket"
    _order = "id desc"
    _rec_name = "ticket_number"
    _inherit = ["abdin_telegram"]

    _uniq_ticket_number = models.Constraint(
        "UNIQUE(ticket_number)",
        "Ticket number must be unique.",
    )

    ticket_number = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default="New",
    )
    title = fields.Char(required=True)
    description = fields.Text(required=True)
    requester = fields.Many2one(
        "res.users",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        index=True,
    )
    assigned_to = fields.Many2one(
        "res.users",
        string="Assigned To",
        domain=[("share", "=", False)],
        index=True,
    )
    request_type_id = fields.Many2one(
        "ab_request_type",
        string="Request Type",
        required=True,
        ondelete="restrict",
        index=True,
    )
    priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        required=True,
        default="medium",
        index=True,
    )
    stage = fields.Selection(
        [
            ("new", "New"),
            ("in_progress", "In Progress"),
            ("requester_confirmation", "Under Requester Confirmation"),
            ("satisfied", "Satisfied"),
            ("add_notes", "Add Notes"),
            ("closed_by_dev", "Closed By Dev"),
        ],
        required=True,
        default="new",
        copy=False,
        index=True,
    )
    notes = fields.Text()
    requester_confirmation = fields.Boolean(readonly=True, copy=False, default=False)
    start_date = fields.Date()
    expected_close_date = fields.Date()
    actual_close_date = fields.Date(readonly=True, copy=False)
    duration_days = fields.Integer(required=True, default=1)
    attachments = fields.Many2many(
        "ir.attachment",
        "ab_request_ticket_ir_attachment_rel",
        "ticket_id",
        "attachment_id",
        string="Attachments",
    )
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute="_compute_display_name", store=True)

    is_requester = fields.Boolean(compute="_compute_user_flags")
    is_responsible_user = fields.Boolean(compute="_compute_user_flags")
    is_request_manager = fields.Boolean(compute="_compute_user_flags")

    @api.depends("ticket_number", "title")
    def _compute_display_name(self):
        for rec in self:
            title = rec.title or ""
            ticket_number = rec.ticket_number or ""
            rec.display_name = f"{ticket_number} - {title}".strip(" -") or _("Request Ticket")

    @api.depends_context("uid")
    def _compute_user_flags(self):
        is_manager = self.env.user.has_group("ab_request_management.group_ab_request_management_manager")
        for rec in self:
            rec.is_request_manager = is_manager
            rec.is_requester = rec.requester == self.env.user
            rec.is_responsible_user = is_manager or rec.assigned_to == self.env.user

    @api.constrains("duration_days")
    def _check_duration_days(self):
        for rec in self:
            if rec.duration_days < 1:
                raise ValidationError(_("Duration days must be at least 1."))

    @api.constrains("start_date", "expected_close_date", "actual_close_date")
    def _check_dates(self):
        for rec in self:
            if rec.start_date and rec.expected_close_date and rec.expected_close_date < rec.start_date:
                raise ValidationError(_("Expected close date cannot be earlier than the start date."))
            if rec.start_date and rec.actual_close_date and rec.actual_close_date < rec.start_date:
                raise ValidationError(_("Actual close date cannot be earlier than the start date."))

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = []
        for vals in vals_list:
            prepared_vals = self._prepare_create_vals(vals)
            self._validate_stage_on_create(prepared_vals)
            prepared_vals_list.append(prepared_vals)

        records = super().create(prepared_vals_list)
        records._notify_ticket_event("New Ticket")
        return records

    def write(self, vals):
        if not isinstance(vals, dict):
            return super().write(vals)

        for rec in self:
            previous_stage = rec.stage
            prepared_vals = rec._prepare_write_vals(vals)
            rec._validate_stage_write(prepared_vals)
            super(AbRequestTicket, rec).write(prepared_vals)

            if prepared_vals.get("stage") and prepared_vals["stage"] != previous_stage:
                rec._notify_stage_change(previous_stage)
        return True

    @api.model
    def _prepare_create_vals(self, vals):
        prepared_vals = dict(vals or {})
        if not prepared_vals.get("ticket_number") or prepared_vals.get("ticket_number") == "New":
            prepared_vals["ticket_number"] = (
                self.env["ir.sequence"].sudo().next_by_code(TICKET_SEQUENCE_CODE) or "New"
            )
        prepared_vals.setdefault("requester", self.env.user.id)
        prepared_vals.setdefault("stage", "new")
        return self._prepare_expected_close_vals(prepared_vals)

    def _prepare_write_vals(self, vals):
        prepared_vals = dict(vals or {})
        return self._prepare_expected_close_vals(prepared_vals)

    def _prepare_expected_close_vals(self, vals):
        prepared_vals = dict(vals or {})

        if prepared_vals.get("title"):
            prepared_vals["title"] = prepared_vals["title"].strip()

        if prepared_vals.get("description"):
            prepared_vals["description"] = prepared_vals["description"].strip()

        start_date = prepared_vals.get("start_date", self.start_date if self else False)
        duration_days = prepared_vals.get("duration_days", self.duration_days if self else 1)
        expected_close_present = "expected_close_date" in prepared_vals

        if start_date and duration_days and not expected_close_present:
            start_date_value = fields.Date.to_date(start_date)
            prepared_vals["expected_close_date"] = start_date_value + timedelta(days=int(duration_days) - 1)

        return prepared_vals

    @api.model
    def _validate_stage_on_create(self, vals):
        if vals.get("stage") != "new":
            raise UserError(_("Tickets must start in the New stage."))

    def _validate_stage_write(self, vals):
        target_stage = vals.get("stage")
        if not target_stage:
            return

        if target_stage == "closed_by_dev" and self.stage != "satisfied":
            raise UserError(_("You cannot move a ticket to Closed By Dev unless it is Satisfied."))

        if self.env.context.get("allow_stage_write"):
            return

        allowed_transitions = {
            "new": {"new"},
            "in_progress": {"in_progress"},
            "requester_confirmation": {"requester_confirmation"},
            "satisfied": {"satisfied"},
            "add_notes": {"add_notes"},
            "closed_by_dev": {"closed_by_dev"},
        }
        if target_stage not in allowed_transitions.get(self.stage, set()):
            raise UserError(_("Stage changes must use the workflow buttons."))

    def _notify_stage_change(self, previous_stage):
        self.ensure_one()
        previous_label = dict(self._fields["stage"].selection).get(previous_stage, previous_stage)
        current_label = dict(self._fields["stage"].selection).get(self.stage, self.stage)
        self._notify_ticket_event(
            "Stage Updated",
            extra_lines=[
                ("From", previous_label),
                ("To", current_label),
            ],
        )

    def _notify_ticket_event(self, title, extra_lines=None):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        stage_labels = dict(self._fields["stage"].selection)
        priority_labels = dict(self._fields["priority"].selection)
        before = f"<b>##### {title} #####</b>\n\n"

        for rec in self:
            lines = [
                ("Ticket", rec.ticket_number),
                ("Title", rec.title),
                ("Requester", rec.requester.name),
                ("Assigned To", rec.assigned_to.name or "-"),
                ("Request Type", rec.request_type_id.display_name or rec.request_type_id.name),
                ("Priority", priority_labels.get(rec.priority, rec.priority)),
                ("Stage", stage_labels.get(rec.stage, rec.stage)),
                ("Duration (Days)", rec.duration_days),
            ]
            if extra_lines:
                lines.extend(extra_lines)
            if rec.notes:
                lines.append(("Notes", rec.notes))

            msg = "".join(f"<div>{label}: {value}</div>" for label, value in lines)
            link = f"{base_url}/web#id={rec.id}&model={rec._name}&view_type=form" if base_url else ""
            after = f"\n\nBy {self.env.user.name}"
            if link:
                after += f"\n<a href='{link}'>Goto Link -></a>"

            rec.send_by_bot(
                rec.get_chat_id("telegram_request_management_group_chat_id"),
                msg=msg,
                before=before,
                after=after,
                attachment=None,
            )

    def _check_requester_action_allowed(self):
        for rec in self:
            if rec.requester != self.env.user:
                raise UserError(_("Only the requester can perform this action."))

    def _check_responsible_action_allowed(self):
        for rec in self:
            if rec.assigned_to != self.env.user and not rec.is_request_manager:
                raise UserError(_("Only the assigned user or a request manager can perform this action."))

    def action_start_progress(self):
        for rec in self:
            rec._check_responsible_action_allowed()
            if rec.stage not in {"new", "add_notes"}:
                raise UserError(_("Only New or Add Notes tickets can move to In Progress."))
            rec.with_context(allow_stage_write=True).write(
                {
                    "stage": "in_progress",
                    "requester_confirmation": False,
                    "start_date": rec.start_date or fields.Date.today(),
                    "actual_close_date": False,
                }
            )
        return True

    def action_send_for_requester_confirmation(self):
        for rec in self:
            rec._check_responsible_action_allowed()
            if rec.stage != "in_progress":
                raise UserError(_("Only In Progress tickets can move to Under Requester Confirmation."))
            rec.with_context(allow_stage_write=True).write(
                {
                    "stage": "requester_confirmation",
                }
            )
        return True

    def action_mark_satisfied(self):
        for rec in self:
            rec._check_requester_action_allowed()
            if rec.stage != "requester_confirmation":
                raise UserError(_("Only tickets under requester confirmation can be marked as Satisfied."))
            rec.with_context(allow_stage_write=True).write(
                {
                    "stage": "satisfied",
                    "requester_confirmation": True,
                }
            )
        return True

    def action_add_notes(self):
        for rec in self:
            rec._check_requester_action_allowed()
            if rec.stage != "requester_confirmation":
                raise UserError(_("Notes can only be added while the ticket is under requester confirmation."))
            if not (rec.notes or "").strip():
                raise ValidationError(_("Please add notes before sending the ticket back to development."))
            rec.with_context(allow_stage_write=True).write(
                {
                    "stage": "add_notes",
                    "requester_confirmation": False,
                }
            )
        return True

    def action_close_by_dev(self):
        for rec in self:
            rec._check_responsible_action_allowed()
            if rec.stage != "satisfied":
                raise UserError(_("You cannot close a ticket unless it is Satisfied."))
            rec.with_context(allow_stage_write=True).write(
                {
                    "stage": "closed_by_dev",
                    "actual_close_date": rec.actual_close_date or fields.Date.today(),
                }
            )
        return True
