# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class DevelopmentRequest(models.Model):
    _name = "development.request"
    _description = "Development Request"
    _inherit = ["mail.thread.main.attachment", "mail.activity.mixin"]
    _order = "priority_level desc, deadline asc, create_date desc"

    name = fields.Char(string="Title", required=True, tracking=True)
    sequence = fields.Char(string="Request ID", copy=False, readonly=True, default="New")
    active = fields.Boolean(default=True)
    description = fields.Html(required=True)
    requester_id = fields.Many2one(
        "res.users",
        string="Requester",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    requester_department_id = fields.Many2one(
        "development.request.team",
        string="Requester Department",
        tracking=True,
    )
    responsible_team_id = fields.Many2one(
        "development.request.team",
        string="Responsible Team",
        tracking=True,
    )
    department_lead_user_id = fields.Many2one(
        "res.users",
        related="responsible_team_id.lead_user_id",
        string="Department Lead",
        store=True,
        readonly=True,
    )
    stage_id = fields.Many2one(
        "development.request.stage",
        string="Stage",
        required=True,
        default=lambda self: self._default_stage_id(),
        tracking=True,
        group_expand="_read_group_stage_ids",
    )
    stage_code = fields.Selection(related="stage_id.code", store=True, readonly=True)
    priority = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ],
        default="medium",
        required=True,
        tracking=True,
    )
    priority_level = fields.Integer(compute="_compute_priority_level", store=True)
    request_type = fields.Selection(
        [
            ("bug", "Bug"),
            ("feature", "Feature"),
            ("improvement", "Improvement"),
        ],
        string="Request Type",
        required=True,
        default="feature",
        tracking=True,
    )
    category_ids = fields.Many2many(
        "development.request.category",
        "development_request_category_rel",
        "request_id",
        "category_id",
        string="Tags",
        tracking=True,
    )
    assigned_user_ids = fields.Many2many(
        "res.users",
        "development_request_user_rel",
        "request_id",
        "user_id",
        string="Assigned Developers",
        tracking=True,
    )
    reviewer_id = fields.Many2one("res.users", copy=False, readonly=True, tracking=True)
    approved_by_id = fields.Many2one("res.users", copy=False, readonly=True, tracking=True)
    completed_by_id = fields.Many2one("res.users", copy=False, readonly=True, tracking=True)
    deadline = fields.Date(tracking=True)
    discussion_date = fields.Datetime(tracking=True)
    estimated_hours = fields.Float(tracking=True)
    actual_hours = fields.Float(tracking=True)
    need_discussion = fields.Boolean(tracking=True)
    next_action = fields.Char(tracking=True)
    state_notes = fields.Text(string="State Notes", tracking=True)
    implemented_solution = fields.Html(tracking=True)
    completion_note = fields.Text(tracking=True)
    completed_date = fields.Datetime(copy=False, readonly=True, tracking=True)
    submitted_date = fields.Datetime(copy=False, readonly=True)
    review_date = fields.Datetime(copy=False, readonly=True)
    approved_date = fields.Datetime(copy=False, readonly=True)
    in_progress_date = fields.Datetime(copy=False, readonly=True)
    testing_date = fields.Datetime(copy=False, readonly=True)
    rejected_date = fields.Datetime(copy=False, readonly=True)
    last_stage_update = fields.Datetime(copy=False, readonly=True, tracking=True)
    is_overdue = fields.Boolean(compute="_compute_is_overdue", search="_search_is_overdue")
    deadline_status = fields.Selection(
        [
            ("on_track", "On Track"),
            ("due_today", "Due Today"),
            ("overdue", "Overdue"),
            ("done", "Done"),
        ],
        compute="_compute_deadline_status",
        search="_search_deadline_status",
    )
    progress_percent = fields.Integer(compute="_compute_progress_percent")
    followup_ids = fields.One2many("development.request.followup", "request_id", string="Follow-ups")
    followup_count = fields.Integer(compute="_compute_followup_count")
    is_recurring = fields.Boolean(tracking=True)
    recurring_interval = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("yearly", "Yearly"),
        ],
        default="monthly",
        tracking=True,
    )
    next_recurrence_date = fields.Date(copy=False, readonly=True)
    git_reference = fields.Char(tracking=True)
    git_commit_url = fields.Char(tracking=True)
    related_project_ref = fields.Char(string="Related Project / Task", tracking=True)
    business_requirement_ref = fields.Char(string="Business Requirement Reference", tracking=True)
    completion_days = fields.Float(compute="_compute_completion_days", store=True, aggregator="avg")
    aging_days = fields.Integer(compute="_compute_aging_days")
    kanban_color_class = fields.Char(compute="_compute_kanban_style", store=True)
    kanban_top_color = fields.Char(compute="_compute_kanban_style", store=True)
    board_section = fields.Selection(
        [
            ("teams", "Teams"),
            ("priorities", "Priorities"),
            ("current_projects", "Current Projects"),
            ("completed_projects", "Completed Projects"),
        ],
        compute="_compute_board_section",
        store=True,
        group_expand="_read_group_board_section",
    )

    _sequence_unique = models.Constraint("UNIQUE (sequence)", "Request identifier must be unique.")

    @api.depends("priority")
    def _compute_priority_level(self):
        mapping = {"low": 1, "medium": 2, "high": 3, "critical": 4}
        for record in self:
            record.priority_level = mapping.get(record.priority or "medium", 2)

    @api.depends("followup_ids")
    def _compute_followup_count(self):
        for record in self:
            record.followup_count = len(record.followup_ids)

    @api.depends("stage_code", "deadline")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = bool(
                record.deadline
                and record.deadline < today
                and record.stage_code not in ("done", "rejected")
            )

    @api.depends("stage_code", "deadline")
    def _compute_deadline_status(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.stage_code in ("done", "rejected"):
                record.deadline_status = "done"
            elif record.deadline and record.deadline < today:
                record.deadline_status = "overdue"
            elif record.deadline and record.deadline == today:
                record.deadline_status = "due_today"
            else:
                record.deadline_status = "on_track"

    @api.depends("stage_code")
    def _compute_progress_percent(self):
        mapping = {
            "draft": 10,
            "submitted": 20,
            "under_review": 35,
            "approved": 50,
            "in_progress": 70,
            "testing": 85,
            "done": 100,
            "rejected": 0,
        }
        for record in self:
            record.progress_percent = mapping.get(record.stage_code, 0)

    @api.depends("responsible_team_id.board_color", "is_overdue")
    def _compute_kanban_style(self):
        mapping = {
            "green": "o_dev_request_green",
            "yellow": "o_dev_request_yellow",
            "light_blue": "o_dev_request_light_blue",
            "dark_blue": "o_dev_request_dark_blue",
            "red": "o_dev_request_red",
            "orange": "o_dev_request_orange",
            "pink": "o_dev_request_pink",
        }
        for record in self:
            record.kanban_top_color = mapping.get(record.responsible_team_id.board_color or "green", "o_dev_request_green")
            record.kanban_color_class = "%s %s" % (
                record.kanban_top_color,
                "o_dev_request_overdue" if record.is_overdue else "",
            )

    @api.depends("stage_code", "priority")
    def _compute_board_section(self):
        for record in self:
            if record.stage_code == "done":
                record.board_section = "completed_projects"
            elif record.stage_code in ("in_progress", "testing"):
                record.board_section = "current_projects"
            elif record.priority in ("high", "critical") or record.stage_code in ("under_review", "approved"):
                record.board_section = "priorities"
            else:
                record.board_section = "teams"

    @api.depends("create_date", "completed_date")
    def _compute_completion_days(self):
        for record in self:
            if record.create_date and record.completed_date:
                delta = record.completed_date - record.create_date
                record.completion_days = delta.total_seconds() / 86400.0
            else:
                record.completion_days = 0.0

    @api.depends("create_date")
    def _compute_aging_days(self):
        today = fields.Date.context_today(self)
        for record in self:
            if record.create_date:
                record.aging_days = (today - record.create_date.date()).days
            else:
                record.aging_days = 0

    @api.model
    def _search_is_overdue(self, operator, value):
        if operator not in ("=", "!="):
            raise UserError(_("Unsupported operator for overdue search."))
        today = fields.Date.context_today(self)
        overdue_domain = [
            ("deadline", "!=", False),
            ("deadline", "<", today),
            ("stage_code", "not in", ["done", "rejected"]),
        ]
        not_overdue_domain = [
            "|",
            "|",
            ("deadline", "=", False),
            ("deadline", ">=", today),
            ("stage_code", "in", ["done", "rejected"]),
        ]
        return overdue_domain if (operator == "=" and value) or (operator == "!=" and not value) else not_overdue_domain

    @api.model
    def _search_deadline_status(self, operator, value):
        if operator != "=":
            raise UserError(_("Unsupported operator for deadline status search."))
        today = fields.Date.context_today(self)
        mapping = {
            "done": [("stage_code", "in", ["done", "rejected"])],
            "overdue": [("deadline", "<", today), ("stage_code", "not in", ["done", "rejected"])],
            "due_today": [("deadline", "=", today), ("stage_code", "not in", ["done", "rejected"])],
            "on_track": [
                ("stage_code", "not in", ["done", "rejected"]),
                "|",
                ("deadline", "=", False),
                ("deadline", ">", today),
            ],
        }
        return mapping.get(value, [])

    @api.model
    def _default_stage_id(self):
        return self.env.ref("dev_request_management.development_request_stage_draft").id

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        return self.env["development.request.stage"].search([], order="sequence, id")

    @api.model
    def _read_group_board_section(self, values, domain):
        return ["teams", "priorities", "current_projects", "completed_projects"]

    @api.constrains("estimated_hours", "actual_hours")
    def _check_hours(self):
        for record in self:
            if record.estimated_hours < 0 or record.actual_hours < 0:
                raise ValidationError(_("Estimated and actual hours cannot be negative."))

    @api.constrains("deadline", "discussion_date")
    def _check_dates(self):
        for record in self:
            if record.deadline and record.discussion_date and record.discussion_date.date() > record.deadline:
                raise ValidationError(_("Discussion date cannot be later than the deadline."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("sequence", "New") == "New":
                vals["sequence"] = self.env["ir.sequence"].next_by_code("development.request") or "New"
        records = super().create(vals_list)
        for record in records:
            record._subscribe_default_partners()
            record.message_post(body=_("Development request created."))
        return records

    def write(self, vals):
        if "stage_id" in vals:
            stage = self.env["development.request.stage"].browse(vals["stage_id"])
            for record in self:
                record._validate_stage_transition(stage.code)
        result = super().write(vals)
        if "stage_id" in vals:
            stage = self.env["development.request.stage"].browse(vals["stage_id"])
            self._after_stage_changed(stage)
        if "assigned_user_ids" in vals:
            for record in self:
                record._subscribe_default_partners()
                record.message_post(body=_("Assignments were updated."))
        return result

    def unlink(self):
        for record in self:
            if record.stage_code not in ("draft", "rejected") and not self.env.user.has_group("dev_request_management.group_development_request_admin"):
                raise UserError(_("Only draft or rejected requests can be deleted."))
        return super().unlink()

    def _subscribe_default_partners(self):
        partner_ids = {self.requester_id.partner_id.id} if self.requester_id.partner_id else set()
        partner_ids |= {user.partner_id.id for user in self.assigned_user_ids if user.partner_id}
        if self.department_lead_user_id and self.department_lead_user_id.partner_id:
            partner_ids.add(self.department_lead_user_id.partner_id.id)
        if partner_ids:
            self.message_subscribe(partner_ids=list(partner_ids))

    def _validate_stage_transition(self, new_code):
        allowed_transitions = {
            "draft": {"submitted", "rejected"},
            "submitted": {"draft", "under_review", "rejected"},
            "under_review": {"submitted", "approved", "rejected"},
            "approved": {"under_review", "in_progress", "rejected"},
            "in_progress": {"approved", "testing", "rejected"},
            "testing": {"in_progress", "done", "rejected"},
            "done": set(),
            "rejected": {"draft", "under_review"},
        }
        if not self.stage_code:
            return
        if self.env.user.has_group("dev_request_management.group_development_request_lead") or self.env.user.has_group(
            "dev_request_management.group_development_request_admin"
        ):
            return
        if new_code not in allowed_transitions.get(self.stage_code, set()):
            raise UserError(_("Transition from %s to %s is not allowed.") % (self.stage_id.name, new_code))
        if new_code in ("approved", "rejected") and not self.env.user.has_group("dev_request_management.group_development_request_lead"):
            raise AccessError(_("Only Team Leads or Administrators can approve or reject requests."))
        if new_code in ("in_progress", "testing", "done") and not self._is_execution_user():
            raise AccessError(_("Only assigned developers, Team Leads, or Administrators can move execution stages."))

    def _is_execution_user(self):
        self.ensure_one()
        return bool(
            self.env.user in self.assigned_user_ids
            or self.env.user.has_group("dev_request_management.group_development_request_lead")
            or self.env.user.has_group("dev_request_management.group_development_request_admin")
        )

    def _after_stage_changed(self, stage):
        now = fields.Datetime.now()
        for record in self:
            update_vals = {"last_stage_update": now}
            if stage.code == "submitted" and not record.submitted_date:
                update_vals["submitted_date"] = now
            elif stage.code == "under_review":
                update_vals["review_date"] = now
                update_vals["reviewer_id"] = self.env.user.id
            elif stage.code == "approved":
                update_vals["approved_date"] = now
                update_vals["approved_by_id"] = self.env.user.id
            elif stage.code == "in_progress" and not record.in_progress_date:
                update_vals["in_progress_date"] = now
            elif stage.code == "testing":
                update_vals["testing_date"] = now
            elif stage.code == "done":
                update_vals["completed_date"] = now
                update_vals["completed_by_id"] = self.env.user.id
                if record.is_recurring:
                    update_vals["next_recurrence_date"] = record._compute_next_recurrence_date(record.deadline or fields.Date.today())
            elif stage.code == "rejected":
                update_vals["rejected_date"] = now
            super(DevelopmentRequest, record).write(update_vals)
            record._schedule_stage_activity(stage.code)
            record.message_post(body=_("Stage updated to <b>%s</b>.") % stage.name)

    def _schedule_stage_activity(self, stage_code):
        self.ensure_one()
        summary_map = {
            "under_review": _("Review development request"),
            "approved": _("Start implementation"),
            "testing": _("Validate implemented work"),
            "done": _("Share completion details"),
            "rejected": _("Communicate rejection decision"),
        }
        if stage_code not in summary_map:
            return
        users = self.assigned_user_ids or self.department_lead_user_id
        users = users if isinstance(users, models.Model) else self.env["res.users"].browse(users.id)
        for user in users:
            if not user:
                continue
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                summary=summary_map[stage_code],
                note=self.next_action or self.state_notes or self.name,
            )

    def _change_stage(self, xmlid):
        stage = self.env.ref(xmlid)
        for record in self:
            record.write({"stage_id": stage.id})
        return True

    def action_submit(self):
        for record in self:
            if not record.description or not record.responsible_team_id:
                raise UserError(_("Description and responsible team are required before submission."))
        return self._change_stage("dev_request_management.development_request_stage_submitted")

    def action_review(self):
        return self._change_stage("dev_request_management.development_request_stage_under_review")

    def action_approve(self):
        return self._change_stage("dev_request_management.development_request_stage_approved")

    def action_start_progress(self):
        for record in self:
            if not record.assigned_user_ids:
                raise UserError(_("Assign at least one developer before starting progress."))
        return self._change_stage("dev_request_management.development_request_stage_in_progress")

    def action_send_testing(self):
        return self._change_stage("dev_request_management.development_request_stage_testing")

    def action_mark_done(self):
        for record in self:
            if not record.implemented_solution:
                raise UserError(_("Implemented solution is required before marking a request done."))
        return self._change_stage("dev_request_management.development_request_stage_done")

    def action_reject(self):
        return self._change_stage("dev_request_management.development_request_stage_rejected")

    def action_reset_draft(self):
        return self._change_stage("dev_request_management.development_request_stage_draft")

    def action_view_followups(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Follow-ups"),
            "res_model": "development.request.followup",
            "view_mode": "list,form",
            "domain": [("request_id", "=", self.id)],
            "context": {"default_request_id": self.id},
        }

    def _compute_next_recurrence_date(self, base_date):
        if not base_date:
            return False
        base = fields.Date.to_date(base_date)
        interval_map = {
            "monthly": relativedelta(months=1),
            "quarterly": relativedelta(months=3),
            "yearly": relativedelta(years=1),
        }
        return base + interval_map.get(self.recurring_interval or "monthly", relativedelta(months=1))

    def action_generate_recurring_copy(self):
        self.ensure_one()
        if not self.is_recurring:
            raise UserError(_("Recurring is not enabled on this request."))
        new_deadline = self._compute_next_recurrence_date(self.deadline or fields.Date.today())
        new_request = self.copy(
            default={
                "sequence": "New",
                "stage_id": self.env.ref("dev_request_management.development_request_stage_draft").id,
                "completed_date": False,
                "completed_by_id": False,
                "approved_by_id": False,
                "reviewer_id": False,
                "submitted_date": False,
                "review_date": False,
                "approved_date": False,
                "in_progress_date": False,
                "testing_date": False,
                "rejected_date": False,
                "last_stage_update": False,
                "deadline": new_deadline,
                "next_recurrence_date": False,
                "name": _("%s (Recurring)") % self.name,
            }
        )
        self.next_recurrence_date = new_deadline
        self.message_post(body=_("Recurring copy created: %s") % new_request.sequence)
        return {
            "type": "ir.actions.act_window",
            "res_model": "development.request",
            "res_id": new_request.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.model
    def _cron_deadline_watch(self):
        requests = self.search(
            [
                ("deadline", "!=", False),
                ("deadline", "<=", fields.Date.today()),
                ("stage_code", "not in", ["done", "rejected"]),
            ]
        )
        for request in requests:
            message = _("Request is overdue.") if request.deadline < fields.Date.today() else _("Request is due today.")
            request.message_post(body=message)
            users = request.assigned_user_ids or request.department_lead_user_id
            users = users if isinstance(users, models.Model) else self.env["res.users"].browse(users.id)
            for user in users:
                if not user:
                    continue
                request.activity_schedule(
                    "mail.mail_activity_data_warning",
                    user_id=user.id,
                    summary=_("Development request deadline alert"),
                    note=message,
                    date_deadline=request.deadline,
                )

    @api.model
    def _cron_generate_recurring_requests(self):
        today = fields.Date.today()
        requests = self.search(
            [
                ("is_recurring", "=", True),
                ("next_recurrence_date", "!=", False),
                ("next_recurrence_date", "<=", today),
                ("stage_code", "=", "done"),
            ]
        )
        for request in requests:
            request.action_generate_recurring_copy()
