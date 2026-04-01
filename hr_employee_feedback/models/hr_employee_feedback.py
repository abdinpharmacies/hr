# -*- coding: utf-8 -*-
"""Core models for employee complaints and suggestions.

This file contains:
1) hr.employee.feedback: Main business object used by employees and managers.
2) hr.feedback.stage: Workflow columns used by list/kanban grouping.
"""

import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class HrEmployeeFeedback(models.Model):
    """Employee feedback item used for complaints and suggestions management."""

    _name = 'hr.employee.feedback'
    _description = 'Employee Feedback - Complaints & Suggestions'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, date_submitted desc'
    _rec_name = 'issue_uid'  # Public issue ID is the business-facing identifier.

    # Core identification fields.
    reference = fields.Char(
        string='Reference',
        default=lambda self: _('New'),
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    issue_uid = fields.Char(
        string='Issue ID',
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
    )
    name = fields.Char(string='Title', required=True, index=True, tracking=True)

    # Employee and organizational context.
    employee_id = fields.Many2one(
        'ab_hr_employee',
        string='Employee',
        required=True,
        default=lambda self: self._default_employee(),
        index=True,
        tracking=True,
    )
    department_id = fields.Many2one(
        string='Department',
        related='employee_id.department_id',
        store=False,
        readonly=True,
    )
    # Manager defaults from the selected employee hierarchy in ab_hr.
    manager_id = fields.Many2one(
        'ab_hr_employee',
        string='Manager',
        default=lambda self: self._default_manager(),
        readonly=False,
        tracking=True,
    )
    assigned_hr_user_id = fields.Many2one(
        'res.users',
        string='Assigned HR',
        readonly=True,
        copy=False,
        tracking=True,
    )

    # Content fields.
    message_type = fields.Selection(
        [('complaint', 'Complaint'), ('suggestion', 'Suggestion')],
        string='Type',
        required=True,
        default='suggestion',
        index=True,
        tracking=True,
    )
    description = fields.Text(string='Description', required=True, tracking=True)
    manager_reply = fields.Text(string='Manager Reply', tracking=True)

    # Workflow and priority.
    stage_id = fields.Many2one(
        'hr.feedback.stage',
        string='Stage',
        required=True,
        default=lambda self: self._default_stage(),
        group_expand='_read_group_stage_id',
        index=True,
        tracking=True,
    )
    priority = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
        string='Priority',
        default='medium',
        index=True,
        tracking=True,
    )

    # Priority color helper for kanban/list badge decorations.
    priority_color = fields.Integer(string='Priority Color', compute='_compute_priority_color')
    progress_percent = fields.Integer(string='Progress', compute='_compute_progress_percent')

    # Timestamps.
    date_submitted = fields.Datetime(
        string='Submitted',
        default=fields.Datetime.now,
        readonly=True,
        index=True,
    )
    date_resolved = fields.Datetime(string='Resolved', tracking=True)
    date_last_stage_update = fields.Datetime(
        string='Last Stage Update',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )

    # Generic state flags.
    active = fields.Boolean(default=True)
    is_resolved = fields.Boolean(string='Resolved', compute='_compute_is_resolved', store=True)

    # UI helper field.
    days_open = fields.Integer(string='Days Open', compute='_compute_days_open')
    can_write_manager_reply = fields.Boolean(
        string='Can Write Manager Reply',
        compute='_compute_can_write_manager_reply',
    )
    followup_ids = fields.One2many(
        'hr.employee.feedback.followup',
        'feedback_id',
        string='Follow-Up History',
    )

    _TEXT_WITH_LETTERS_PATTERN = re.compile(r"[A-Za-z\u0600-\u06FF]")

    @api.depends('priority')
    def _compute_priority_color(self):
        """Map priority levels to integer color tags used in web client widgets."""
        priority_colors = {
            'low': 2,      # Green semantic hint.
            'medium': 1,   # Yellow semantic hint.
            'high': 3,     # Orange semantic hint.
            'urgent': 4,   # Red semantic hint.
        }
        for record in self:
            record.priority_color = priority_colors.get(record.priority, 1)

    @api.depends('stage_id', 'stage_id.is_final')
    def _compute_is_resolved(self):
        """Flag record as resolved whenever its stage is marked as final."""
        for record in self:
            record.is_resolved = bool(record.stage_id.is_final)

    @api.depends('date_submitted')
    def _compute_days_open(self):
        """Compute number of days since submission for operational visibility."""
        now_value = fields.Datetime.now()
        for record in self:
            if record.date_submitted:
                record.days_open = (now_value - record.date_submitted).days
            else:
                record.days_open = 0

    @api.depends('stage_id')
    def _compute_progress_percent(self):
        """Expose stage progress as an integer for compact kanban progress bars."""
        under_review = self.env.ref('hr_employee_feedback.stage_under_review', raise_if_not_found=False)
        in_progress = self.env.ref('hr_employee_feedback.stage_in_progress', raise_if_not_found=False)
        resolved = self.env.ref('hr_employee_feedback.stage_resolved', raise_if_not_found=False)
        rejected = self.env.ref('hr_employee_feedback.stage_rejected', raise_if_not_found=False)
        progress_map = {
            under_review.id if under_review else 0: 25,
            in_progress.id if in_progress else 0: 65,
            resolved.id if resolved else 0: 100,
            rejected.id if rejected else 0: 100,
        }
        for record in self:
            record.progress_percent = progress_map.get(record.stage_id.id, 0)

    @api.depends('manager_id', 'assigned_hr_user_id')
    def _compute_can_write_manager_reply(self):
        """Allow action updates only for the direct manager, assigned HR, or admin/HR roles.

        Employees still read the reply and follow-up history, but they cannot post
        action updates from this field.
        """
        current_user = self.env.user
        is_full_admin = current_user.has_group('base.group_system')
        is_hr_role = self._is_hr_or_admin_role()
        for record in self:
            record.can_write_manager_reply = bool(
                is_full_admin
                or is_hr_role
                or record.manager_id.user_id == current_user
                or record.assigned_hr_user_id == current_user
            )

    @api.model
    def _default_stage(self):
        """Default all new tickets to Under Review."""
        return self.env.ref('hr_employee_feedback.stage_under_review', raise_if_not_found=False) or \
            self.env['hr.feedback.stage'].search([], order='sequence, id', limit=1)

    @api.model
    def _default_employee(self):
        """Default employee from ab_hr using the logged-in user.

        Some users, such as administrators, may be linked to more than one
        `ab_hr_employee` row. Prefer the record whose employee name matches
        the user display name, then fall back to the first linked record.
        """
        employees = self.env['ab_hr_employee'].search([('user_id', '=', self.env.uid)])
        if not employees:
            return self.env['ab_hr_employee']
        exact_match = employees.filtered(lambda e: e.name == self.env.user.name)[:1]
        return exact_match or employees[:1]

    @api.model
    def _default_manager(self):
        """Default manager from the logged-in user's employee hierarchy."""
        employee = self._default_employee()
        return employee.parent_id

    @api.model
    def _next_reference(self, message_type):
        """Generate complaint/suggestion specific references.

        Complaint tickets use the `CO` prefix while suggestion tickets use `SU`.
        This keeps business references readable and removes the old generic `FB`
        prefix from new records.
        """
        sequence_code = {
            'complaint': 'hr.employee.feedback.complaint',
            'suggestion': 'hr.employee.feedback.suggestion',
        }.get(message_type or 'suggestion', 'hr.employee.feedback.suggestion')
        return self.env['ir.sequence'].next_by_code(sequence_code) or _('New')

    @api.model
    def _next_issue_uid(self):
        """Generate a unique public-facing issue identifier.

        This identifier is stable across all ticket types and is the value shown
        to users in list/form views for future follow-up.
        """
        return self.env['ir.sequence'].next_by_code('hr.employee.feedback.issue') or _('New')

    @api.model
    def _allowed_stages(self):
        """Return the fixed 4-stage workflow in display order."""
        xmlids = [
            'hr_employee_feedback.stage_under_review',
            'hr_employee_feedback.stage_in_progress',
            'hr_employee_feedback.stage_resolved',
            'hr_employee_feedback.stage_rejected',
        ]
        stages = self.env['hr.feedback.stage']
        for xmlid in xmlids:
            stage = self.env.ref(xmlid, raise_if_not_found=False)
            if stage:
                stages |= stage
        return stages.sorted(lambda s: (s.sequence, s.id))

    @api.model
    def _read_group_stage_id(self, stages, domain):
        """Show only fixed workflow stages in kanban columns, including empty ones."""
        allowed = self._allowed_stages()
        return allowed or self.env['hr.feedback.stage'].search([], order='sequence, id')

    def _is_status_editor_role(self):
        """Return True for roles that are allowed to update status only.

        This includes feedback managers and HR users/managers.
        """
        user = self.env.user
        return any([
            user.has_group('hr_employee_feedback.group_employee_feedback_manager'),
            user.has_group('hr.group_hr_user'),
            user.has_group('hr.group_hr_manager'),
            user.has_group('ab_hr.group_ab_hr_manager'),
            user.has_group('ab_hr.group_ab_hr_admin'),
            user.has_group('ab_hr.group_ab_hr_co'),
        ])

    def _is_hr_or_admin_role(self):
        """Return True for HR or system admin users."""
        user = self.env.user
        return any([
            user.has_group('hr.group_hr_user'),
            user.has_group('hr.group_hr_manager'),
            user.has_group('ab_hr.group_ab_hr_manager'),
            user.has_group('ab_hr.group_ab_hr_admin'),
            user.has_group('ab_hr.group_ab_hr_co'),
            user.has_group('base.group_system'),
        ])

    def _is_direct_manager_user(self):
        """Return True only when the current user is the assigned line manager."""
        self.ensure_one()
        return self.manager_id.user_id == self.env.user

    def _is_assigned_hr_user(self):
        """Return True when the current user is the HR assignee on the issue."""
        self.ensure_one()
        return self.assigned_hr_user_id == self.env.user

    @api.onchange('employee_id')
    def _onchange_employee_id_set_manager(self):
        """Always bind manager from selected employee hierarchy in ab_hr."""
        for record in self:
            record.manager_id = record.employee_id.parent_id

    @api.constrains('name', 'description')
    def _check_text_fields_have_letters(self):
        """Reject numeric-only titles/descriptions.

        The business requirement is to ensure users enter meaningful text, not
        only digits. Accept Latin and Arabic letters.
        """
        for record in self:
            title = (record.name or '').strip()
            description = (record.description or '').strip()
            if title and not self._TEXT_WITH_LETTERS_PATTERN.search(title):
                raise ValidationError(_("Title must contain letters, not only numbers or symbols."))
            if description and not self._TEXT_WITH_LETTERS_PATTERN.search(description):
                raise ValidationError(_("Description must contain letters, not only numbers or symbols."))

    @api.model_create_multi
    def create(self, vals_list):
        """Generate unique reference numbers and initialize manager/stage timestamps."""
        for vals in vals_list:
            # Assign human-friendly sequence unless caller provides one explicitly.
            if not vals.get('reference') or vals.get('reference') == _('New'):
                vals['reference'] = self._next_reference(vals.get('message_type'))
            if not vals.get('issue_uid') or vals.get('issue_uid') == _('New'):
                vals['issue_uid'] = self._next_issue_uid()

            # Always source employee from the logged-in user's ab_hr profile for
            # non-admin users. This keeps ticket ownership aligned with the
            # authenticated employee account and avoids manual reassignment in UI/RPC.
            default_employee = self._default_employee()
            is_full_admin = self.env.user.has_group('base.group_system')
            if default_employee and (not is_full_admin or not vals.get('employee_id')):
                vals['employee_id'] = default_employee.id

            # Force manager from employee hierarchy (employee chooses own manager).
            if vals.get('employee_id'):
                employee = self.env['ab_hr_employee'].browse(vals['employee_id'])
                vals['manager_id'] = employee.parent_id.id

            # Maintain stage transition timestamp at creation.
            vals.setdefault('date_last_stage_update', fields.Datetime.now())

            # Priority can only be selected by HR/Admin at create time.
            if not self._is_hr_or_admin_role():
                vals['priority'] = 'medium'

        records = super().create(vals_list)

        # Safety net: keep tickets inside the fixed 4-stage workflow.
        allowed_ids = set(self._allowed_stages().ids)
        fallback_stage = self._default_stage()
        for record in records:
            if allowed_ids and record.stage_id.id not in allowed_ids and fallback_stage:
                record.with_context(bypass_feedback_status_lock=True).stage_id = fallback_stage.id

        # Auto-set resolved timestamp when created directly in a final stage.
        for record in records:
            if record.stage_id.is_final and not record.date_resolved:
                record.date_resolved = fields.Datetime.now()
            self.env['hr.employee.feedback.followup'].sudo().create({
                'feedback_id': record.id,
                'note': _("Employee submission:\n%s") % (record.description or ''),
                'stage_id': record.stage_id.id,
                'priority': record.priority,
            })
        return records

    def write(self, vals):
        """Track stage transitions and enforce status-only editing for privileged roles.

        Employees are already blocked by ACL from editing existing records.
        Managers/HR/Admin can only update workflow status-related fields.
        """
        # Technical bypass for controlled maintenance/migration scripts.
        # Full admins keep unrestricted edit permission for testing/support.
        current_user = self.env.user
        is_full_admin = current_user.has_group('base.group_system')
        if not self.env.context.get('bypass_feedback_status_lock') and not is_full_admin:
            for record in self:
                if self._is_hr_or_admin_role():
                    allowed_fields = {
                        'stage_id', 'date_resolved', 'date_last_stage_update',
                        'manager_reply', 'priority', 'assigned_hr_user_id',
                    }
                elif record._is_direct_manager_user() or record._is_assigned_hr_user():
                    allowed_fields = {'manager_reply'}
                else:
                    allowed_fields = set()
                blocked_fields = set(vals) - allowed_fields
                if blocked_fields:
                    raise UserError(_(
                        "You can only update permitted follow-up fields on this issue. Restricted fields: %s"
                    ) % ', '.join(sorted(blocked_fields)))

        if 'stage_id' in vals:
            allowed_ids = set(self._allowed_stages().ids)
            if allowed_ids and vals.get('stage_id') not in allowed_ids:
                raise UserError(_("Only the fixed workflow stages are allowed on tickets."))
            vals['date_last_stage_update'] = fields.Datetime.now()

        under_review_stage = self.env.ref('hr_employee_feedback.stage_under_review', raise_if_not_found=False)
        in_progress_stage = self.env.ref('hr_employee_feedback.stage_in_progress', raise_if_not_found=False)

        # HR/Admin acceptance path:
        # when the first operational reply is added while a ticket is still under
        # review, move it automatically to In Progress so employees can track it.
        if (
            vals.get('manager_reply')
            and not vals.get('stage_id')
            and self._is_hr_or_admin_role()
            and in_progress_stage
        ):
            for record in self:
                if under_review_stage and record.stage_id == under_review_stage:
                    vals['stage_id'] = in_progress_stage.id
                    vals['date_last_stage_update'] = fields.Datetime.now()
                    break

        # Moving a ticket from Under Review to In Progress requires an HR/admin
        # reply so employees can see what action or escalation started.
        if vals.get('stage_id') and in_progress_stage and vals['stage_id'] == in_progress_stage.id:
            for record in self:
                if under_review_stage and record.stage_id == under_review_stage:
                    new_reply = (vals.get('manager_reply') or '').strip()
                    existing_reply = (record.manager_reply or '').strip()
                    if not (new_reply or existing_reply):
                        raise UserError(_("A manager reply is required before moving a ticket to In Progress."))

        # Manager reply is allowed only after approval (not in Under Review).
        if vals.get('manager_reply') and not self.env.context.get('bypass_feedback_status_lock'):
            target_stage = self.env['hr.feedback.stage'].browse(vals['stage_id']) if vals.get('stage_id') else False
            for record in self:
                effective_stage = target_stage or record.stage_id
                if (
                    under_review_stage
                    and effective_stage == under_review_stage
                    and not self._is_hr_or_admin_role()
                ):
                    raise UserError(_("Manager reply can be set only after HR/admin approval moves the ticket out of Under Review."))

        # First HR/admin action owns the HR assignment so the same HR can keep
        # updating the operational response later.
        if (
            not vals.get('assigned_hr_user_id')
            and self._is_hr_or_admin_role()
            and any(key in vals for key in ('stage_id', 'priority', 'manager_reply'))
        ):
            for record in self:
                if not record.assigned_hr_user_id:
                    vals['assigned_hr_user_id'] = current_user.id
                    break

        tracked_before = {
            record.id: {
                'stage': record.stage_id.name,
                'priority': record.priority,
                'reply': record.manager_reply or '',
            }
            for record in self
        }
        result = super().write(vals)

        # Post-write pass to set/clear resolved timestamp based on current stage.
        if 'stage_id' in vals:
            now_value = fields.Datetime.now()
            for record in self:
                if record.stage_id.is_final and not record.date_resolved:
                    record.date_resolved = now_value
                elif not record.stage_id.is_final and record.date_resolved:
                    record.date_resolved = False

        # Publish a concise timeline entry so employees can follow the process
        # without having edit permissions on the ticket.
        if any(key in vals for key in ('stage_id', 'priority', 'manager_reply')):
            priority_labels = dict(self._fields['priority'].selection)
            for record in self:
                before = tracked_before[record.id]
                updates = []
                actor_name = current_user.display_name
                if before['stage'] != record.stage_id.name:
                    updates.append(_("Stage: %s -> %s") % (before['stage'], record.stage_id.name))
                if before['priority'] != record.priority:
                    updates.append(_("Priority: %s -> %s") % (
                        priority_labels.get(before['priority'], before['priority'] or '-'),
                        priority_labels.get(record.priority, record.priority or '-'),
                    ))
                if vals.get('manager_reply') and (before['reply'] != (record.manager_reply or '')):
                    updates.append(_("Action taken by %s: %s") % (actor_name, record.manager_reply or ''))
                if updates:
                    self.env['hr.employee.feedback.followup'].sudo().create({
                        'feedback_id': record.id,
                        'note': "\n".join(updates),
                        'stage_id': record.stage_id.id,
                        'priority': record.priority,
                    })
                    record.message_post(body="<br/>".join(updates), subtype_xmlid='mail.mt_note')
        return result

    def action_mark_resolved(self):
        """Quick action: move item to the configured Resolved stage."""
        resolved_stage = self.env.ref('hr_employee_feedback.stage_resolved', raise_if_not_found=False)
        if resolved_stage:
            self.write({'stage_id': resolved_stage.id})
        return True

    def action_reopen(self):
        """Quick action: return item to Under Review and clear resolved timestamp."""
        under_review_stage = self.env.ref('hr_employee_feedback.stage_under_review', raise_if_not_found=False)
        if under_review_stage:
            self.write({'stage_id': under_review_stage.id, 'date_resolved': False})
        return True


class HrFeedbackStage(models.Model):
    """Configurable stage model used as Trello-like columns in Kanban."""

    _name = 'hr.feedback.stage'
    _description = 'Feedback Stage'
    _order = 'sequence, id'

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    description = fields.Text(string='Stage Description')
    is_final = fields.Boolean(string='Is Final Stage?')
    color = fields.Integer(string='Color')
    # Related tickets shown in stage detail to provide operational context.
    feedback_ids = fields.One2many('hr.employee.feedback', 'stage_id', string='Tickets')

    color_label = fields.Selection(
        [
            ('0', 'Gray - Low'),
            ('1', 'Blue - Medium'),
            ('2', 'Green - Normal'),
            ('3', 'Orange - High'),
            ('4', 'Red - Urgent'),
            ('5', 'Purple - Critical'),
            ('6', 'Cyan - Info'),
            ('7', 'Pink - Special'),
            ('8', 'Brown - Escalated'),
            ('9', 'Light Gray - Neutral'),
            ('10', 'Dark Blue - Internal'),
            ('11', 'Dark Purple - Confidential'),
        ],
        string='Color / Priority Visual',
        compute='_compute_color_label',
        inverse='_inverse_color_label',
        store=False,
    )

    @api.depends('color')
    def _compute_color_label(self):
        """Expose integer stage color as a readable color dropdown label."""
        for record in self:
            record.color_label = str(record.color or 0)

    def _inverse_color_label(self):
        """Persist dropdown color selection back to Odoo integer color field."""
        for record in self:
            record.color = int(record.color_label or 0)


class HrEmployeeFeedbackFollowup(models.Model):
    """Structured follow-up history for ticket processing.

    This model complements chatter with a business-facing timeline that users can
    read in a dedicated notebook page.
    """

    _name = 'hr.employee.feedback.followup'
    _description = 'Employee Feedback Follow-Up'
    _order = 'create_date desc, id desc'

    feedback_id = fields.Many2one(
        'hr.employee.feedback',
        string='Issue',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string='Updated By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    note = fields.Text(string='Follow-Up Note', required=True)
    stage_id = fields.Many2one('hr.feedback.stage', string='Stage', readonly=True)
    priority = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')],
        string='Priority',
        readonly=True,
    )
