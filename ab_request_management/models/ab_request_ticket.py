from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

REQUEST_SEQUENCE_CODE = "ab_request_ticket.ticket_number"
ASSIGNMENT_FIELDS = {"assigned_employee_id", "priority", "deadline"}


class AbRequest(models.Model):
    _name = "ab.request"
    _table = "ab_request_ticket"
    _description = "Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(
        string="Request Number",
        required=True,
        readonly=True,
        copy=False,
        index=True,
        default="New",
    )
    subject = fields.Char(required=True, tracking=True)
    description = fields.Text(required=True)
    request_type_id = fields.Many2one(
        "ab.request.type",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    requester_id = fields.Many2one(
        "ab_hr_employee",
        required=True,
        readonly=True,
        default=lambda self: self._default_requester_id(),
        ondelete="restrict",
        tracking=True,
    )
    requester_user_id = fields.Many2one(
        "res.users",
        related="requester_id.user_id",
        store=True,
    )
    department_id = fields.Many2one(
        "ab_hr_department",
        related="request_type_id.department_id",
        store=True,
        readonly=True,
    )
    manager_id = fields.Many2one(
        "ab_hr_employee",
        related="request_type_id.manager_id",
        store=True,
        readonly=True,
    )
    manager_user_id = fields.Many2one(
        "res.users",
        related="manager_id.user_id",
        store=True,
    )
    assigned_employee_id = fields.Many2one(
        "ab_hr_employee",
        domain="[('department_id', '=', department_id)]",
        ondelete="restrict",
        tracking=True,
    )
    assigned_user_id = fields.Many2one(
        "res.users",
        related="assigned_employee_id.user_id",
        store=True,
    )
    priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        default="medium",
        tracking=True,
    )
    deadline = fields.Datetime()
    state = fields.Selection(
        [
            ("under_review", "Under Review"),
            ("scheduled", "Scheduled"),
            ("in_progress", "In Progress"),
            ("under_requester_confirmation", "Under Requester Confirmation"),
            ("satisfied", "Satisfied"),
            ("rejected", "Rejected"),
            ("closed", "Closed"),
        ],
        default="under_review",
        required=True,
        copy=False,
        tracking=True,
    )
    followup_ids = fields.One2many("ab.request.followup", "request_id", string="Follow-ups")
    followup_count = fields.Integer(compute="_compute_followup_count")

    is_requester = fields.Boolean(compute="_compute_access_flags")
    is_department_manager = fields.Boolean(compute="_compute_access_flags")
    is_assigned_employee = fields.Boolean(compute="_compute_access_flags")
    is_request_admin = fields.Boolean(compute="_compute_access_flags")
    can_assign = fields.Boolean(compute="_compute_access_flags")
    can_work_on_request = fields.Boolean(compute="_compute_access_flags")
    can_add_followup = fields.Boolean(compute="_compute_access_flags")

    _ab_request_name_uniq = models.Constraint(
        "UNIQUE(name)",
        "Request number must be unique.",
    )

    @api.model
    def _default_requester_id(self):
        """Return the current employee linked to the current user."""
        employee = self.env.user.ab_employee_ids[:1]
        return employee.id

    @api.depends("followup_ids")
    def _compute_followup_count(self):
        for record in self:
            record.followup_count = len(record.followup_ids)

    @api.depends_context("uid")
    @api.depends(
        "requester_user_id",
        "manager_user_id",
        "assigned_user_id",
        "request_type_id",
        "request_type_id.department_id",
        "request_type_id.department_id.manager_id",
        "request_type_id.department_id.manager_id.user_id",
        "state",
    )
    def _compute_access_flags(self):
        current_user = self.env.user
        is_request_admin = current_user.has_group("ab_request_management.group_ab_request_management_admin")
        for record in self:
            record.is_request_admin = is_request_admin
            record.is_requester = record.requester_user_id == current_user
            record.is_department_manager = record._is_current_user_department_manager()
            record.is_assigned_employee = record.assigned_user_id == current_user
            record.can_assign = (record.is_department_manager or is_request_admin) and record.state == "scheduled"
            record.can_work_on_request = record.is_department_manager or record.is_assigned_employee or is_request_admin
            record.can_add_followup = record._can_current_user_add_followup()

    def _is_current_user_department_manager(self):
        """Return whether the current user manages the request type department."""
        self.ensure_one()
        return self.request_type_id.department_id.manager_id.user_id == self.env.user

    @api.constrains("request_type_id")
    def _check_request_type_manager(self):
        """Ensure every request references a department with a manager."""
        for record in self:
            if not record.request_type_id.manager_id:
                raise ValidationError(_("The selected request type must have a department manager."))

    @api.constrains("assigned_employee_id", "department_id")
    def _check_assigned_employee_department(self):
        """Keep assignment scoped to the request department when possible."""
        for record in self:
            if (
                record.assigned_employee_id
                and record.department_id
                and record.assigned_employee_id.department_id
                and record.assigned_employee_id.department_id != record.department_id
            ):
                raise ValidationError(_("The assigned employee must belong to the request department."))

    @api.model_create_multi
    def create(self, vals_list):
        """Create requests in under-review state and notify stakeholders."""
        prepared_vals_list = [self._prepare_create_vals(vals) for vals in vals_list]
        records = super().create(prepared_vals_list)
        records._subscribe_request_partners()
        records._notify_request_created()
        return records

    def write(self, vals):
        """Protect immutable fields and workflow-only state changes."""
        if not vals:
            return super().write(vals)

        self._check_immutable_fields(vals)
        self._check_assignment_write(vals)
        self._check_state_write(vals)
        result = super().write(vals)
        if {"request_type_id", "assigned_employee_id"} & set(vals):
            self._subscribe_request_partners()
        return result

    @api.model
    def _prepare_create_vals(self, vals):
        """Normalize incoming values before request creation."""
        prepared_vals = dict(vals or {})
        prepared_vals["subject"] = (prepared_vals.get("subject") or "").strip()
        prepared_vals["description"] = (prepared_vals.get("description") or "").strip()
        if not prepared_vals.get("subject"):
            raise ValidationError(_("Subject is required."))
        if not prepared_vals.get("description"):
            raise ValidationError(_("Description is required."))
        if not prepared_vals.get("requester_id"):
            requester_id = self._default_requester_id()
            if not requester_id:
                raise ValidationError(_("The current user is not linked to an employee."))
            prepared_vals["requester_id"] = requester_id
        prepared_vals["state"] = "under_review"
        if not prepared_vals.get("name") or prepared_vals.get("name") == "New":
            prepared_vals["name"] = self.env["ir.sequence"].sudo().next_by_code(REQUEST_SEQUENCE_CODE) or "New"
        request_type = self.env["ab.request.type"].browse(prepared_vals["request_type_id"])
        if not request_type.manager_id:
            raise ValidationError(_("The selected request type must have a department manager."))
        return prepared_vals

    def _check_immutable_fields(self, vals):
        """Prevent edits to subject and description after creation."""
        immutable_fields = {"subject", "description"}
        if not immutable_fields & set(vals):
            return
        for record in self:
            for field_name in immutable_fields & set(vals):
                new_value = (vals.get(field_name) or "").strip()
                current_value = (record[field_name] or "").strip()
                if new_value != current_value:
                    raise UserError(_("You cannot modify the subject or description after creation."))

    def _check_assignment_write(self, vals):
        """Restrict assignment field edits to the department manager or request admin before assignment."""
        if self.env.context.get("allow_assignment_write") or not (ASSIGNMENT_FIELDS & set(vals)):
            return
        for record in self:
            if not record._can_department_manager_assign():
                raise UserError(_("Only the department manager or request admin can prepare assignment details."))
            if record.state != "scheduled":
                raise UserError(_("Assignment details can only be updated while the request is scheduled."))

    def _check_state_write(self, vals):
        """Force state changes through workflow actions."""
        if self.env.context.get("allow_state_write") or "state" not in vals:
            return
        raise UserError(_("State changes must be performed through the workflow buttons."))

    def _can_department_manager_assign(self):
        """Return whether the current user can approve, reject, or assign the request."""
        self.ensure_one()
        return self.is_department_manager or self.is_request_admin

    def _check_department_manager_action(self):
        """Validate actions reserved for the department manager or request admin."""
        for record in self:
            if not record._can_department_manager_assign():
                raise UserError(_("Only the department manager or request admin can perform this action."))

    def _check_request_worker(self):
        """Validate actions reserved for the manager, request admin, or assigned employee."""
        for record in self:
            if not record.can_work_on_request:
                raise UserError(_("Only the assigned employee, department manager, or request admin can perform this action."))

    def _check_requester(self):
        """Validate actions reserved for the requester."""
        for record in self:
            if not record.is_requester:
                raise UserError(_("Only the requester can perform this action."))

    def _can_current_user_add_followup(self):
        """Return whether the current user can add follow-ups on this request."""
        self.ensure_one()
        if self.is_department_manager or self.is_assigned_employee or self.is_request_admin:
            return self.state in {"scheduled", "in_progress", "under_requester_confirmation", "satisfied"}
        if self.is_requester:
            return self.state not in {"rejected", "closed"}
        return False

    def _check_followup_creation_rights(self):
        """Validate follow-up creation permissions."""
        for record in self:
            if not record._can_current_user_add_followup():
                if record.is_requester:
                    raise UserError(_("The requester cannot add follow-ups on rejected or closed requests."))
                raise UserError(_("Only the assigned employee, department manager, or request admin can add follow-ups."))

    def _subscribe_request_partners(self):
        """Subscribe requester, manager, and assigned employee to chatter."""
        for record in self:
            partners = (
                record.requester_user_id.partner_id
                | record.manager_user_id.partner_id
                | record.assigned_user_id.partner_id
            )
            if partners:
                record.message_subscribe(partner_ids=partners.ids)

    def _get_request_admin_partners(self):
        """Return partners of request admins."""
        admin_group = self.env.ref("ab_request_management.group_ab_request_management_admin", raise_if_not_found=False)
        if not admin_group:
            return self.env["res.partner"]
        return admin_group.all_user_ids.partner_id

    def _post_notification(self, body, partners=None):
        """Post a chatter notification to specific partners."""
        self.ensure_one()
        self.message_post(
            body=body,
            message_type="notification",
            subtype_xmlid="mail.mt_comment",
            partner_ids=(partners or self.env["res.partner"]).ids,
        )

    def _notify_request_created(self):
        """Notify the manager and request admins when a request is created."""
        for record in self:
            partners = record.manager_user_id.partner_id | record._get_request_admin_partners()
            body = _(
                "Request %(request)s has been created by %(requester)s and is waiting for review."
            ) % {
                "request": record.name,
                "requester": record.requester_id.name,
            }
            record._post_notification(body, partners)

    def _notify_assignment(self):
        """Notify the assigned employee after assignment."""
        for record in self:
            if not record.assigned_user_id:
                continue
            body = _(
                "Request %(request)s has been assigned to %(employee)s with %(priority)s priority."
            ) % {
                "request": record.name,
                "employee": record.assigned_employee_id.name,
                "priority": dict(self._fields["priority"].selection).get(record.priority, record.priority),
            }
            record._post_notification(body, record.assigned_user_id.partner_id)

    def _notify_requester_confirmation(self):
        """Notify the manager when requester feedback is submitted."""
        for record in self:
            if not record.manager_user_id:
                continue
            body = _(
                "Requester %(requester)s has updated request %(request)s."
            ) % {
                "requester": record.requester_id.name,
                "request": record.name,
            }
            record._post_notification(body, record.manager_user_id.partner_id)

    def action_approve(self):
        """Approve a request and move it to scheduled."""
        self._check_department_manager_action()
        for record in self:
            if record.state != "under_review":
                raise UserError(_("Only requests under review can be approved."))
            record.with_context(allow_state_write=True).write({"state": "scheduled"})
        return True

    def action_reject(self):
        """Reject a request."""
        self._check_department_manager_action()
        for record in self:
            if record.state != "under_review":
                raise UserError(_("Only requests under review can be rejected."))
            record.with_context(allow_state_write=True).write({"state": "rejected"})
        return True

    def action_assign(self):
        """Assign the request and start execution."""
        self._check_department_manager_action()
        for record in self:
            if record.state != "scheduled":
                raise UserError(_("Only scheduled requests can be assigned."))
            if not record.assigned_employee_id:
                raise ValidationError(_("Please select an assigned employee before assigning the request."))
            if not record.priority:
                raise ValidationError(_("Please select a priority before assigning the request."))
            values = {
                "state": "in_progress",
            }
            record.with_context(allow_state_write=True, allow_assignment_write=True).write(values)
            record._notify_assignment()
        return True

    def action_mark_in_progress(self):
        """Move a scheduled request into progress."""
        self._check_request_worker()
        for record in self:
            if record.state != "scheduled":
                raise UserError(_("Only scheduled requests can be moved to in progress."))
            if not record.assigned_employee_id:
                raise ValidationError(_("The request must be assigned before it can start."))
            record.with_context(allow_state_write=True).write({"state": "in_progress"})
        return True

    def action_request_confirmation(self):
        """Send the request to the requester for confirmation."""
        self._check_request_worker()
        for record in self:
            if record.state != "in_progress":
                raise UserError(_("Only requests in progress can be sent for requester confirmation."))
            record.with_context(allow_state_write=True).write({"state": "under_requester_confirmation"})
        return True

    def action_mark_satisfied(self):
        """Mark the request as satisfied."""
        self._check_requester()
        for record in self:
            if record.state != "under_requester_confirmation":
                raise UserError(_("Only requests under requester confirmation can be marked as satisfied."))
            record.with_context(allow_state_write=True).write({"state": "satisfied"})
            record._notify_requester_confirmation()
        return True

    def action_request_changes(self):
        """Return the request to in-progress after requester feedback."""
        self._check_requester()
        for record in self:
            if record.state != "under_requester_confirmation":
                raise UserError(_("Only requests under requester confirmation can be sent back for changes."))
            record.with_context(allow_state_write=True).write({"state": "in_progress"})
            record._notify_requester_confirmation()
        return True

    def action_close(self):
        """Close the request."""
        self._check_request_worker()
        for record in self:
            if record.state not in {"satisfied", "rejected"}:
                raise UserError(_("Only satisfied or rejected requests can be closed."))
            record.with_context(allow_state_write=True).write({"state": "closed"})
        return True

    def action_view_followups(self):
        """Open the request follow-ups."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Follow-ups"),
            "res_model": "ab.request.followup",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
            "context": {
                "default_request_id": self.id,
            },
        }
