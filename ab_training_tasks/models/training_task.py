from collections import defaultdict
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class TrainingTask(models.Model):
    _name = 'ab.training.task'
    _description = 'Training Task'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'completion_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(string='Task Title', required=True, tracking=True)
    member_id = fields.Many2one(
        'res.users',
        string='Member',
        required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        required=True,
        default=lambda self: self.env.company,
        ondelete='restrict',
        index=True,
    )
    currency_id = fields.Many2one(related='company_id.currency_id', readonly=True)
    wallet_id = fields.Many2one(
        'ab.training.wallet',
        required=True,
        readonly=True,
        ondelete='restrict',
        check_company=True,
        index=True,
    )
    task_type_id = fields.Many2one(
        'ab.training.task.type',
        string='Task Type',
        required=True,
        ondelete='restrict',
        check_company=True,
        tracking=True,
    )
    category_id = fields.Many2one(
        'ab.training.task.category',
        string='Material Category',
        required=True,
        ondelete='restrict',
        check_company=True,
        tracking=True,
        domain="[('active', '=', True)]",
    )
    incentive_value = fields.Monetary(
        currency_field='currency_id',
        required=True,
        readonly=True,
        tracking=True,
        help='Snapshot of the task type incentive when the task is submitted.',
    )
    completion_date = fields.Date(
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    description = fields.Text(string='Work Summary', required=True, tracking=True)
    material_reference = fields.Char(
        string='Material / Reference',
        help='Optional link, document reference, lesson, or material identifier.',
    )
    state = fields.Selection(
        [('pending', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected')],
        required=True,
        default='pending',
        tracking=True,
        index=True,
    )
    rejection_reason = fields.Text(readonly=True, tracking=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False, ondelete='restrict')
    approved_at = fields.Datetime(readonly=True, copy=False)
    rejected_by = fields.Many2one('res.users', readonly=True, copy=False, ondelete='restrict')
    rejected_at = fields.Datetime(readonly=True, copy=False)
    wallet_reset_line_id = fields.Many2one(
        'ab.training.wallet.reset.line',
        string='Payout Line',
        readonly=True,
        copy=False,
        ondelete='restrict',
        index=True,
    )
    paid_at = fields.Datetime(related='wallet_reset_line_id.reset_at', readonly=True)
    is_paid = fields.Boolean(compute='_compute_is_paid')
    material_ids = fields.One2many(
        'ab.training.material',
        'task_id',
        string='Training Materials',
        copy=False,
    )
    file_upload_allowed = fields.Boolean(compute='_compute_allowed_file_types')
    allowed_file_types_display = fields.Char(
        string='Allowed File Types',
        compute='_compute_allowed_file_types',
    )
    allowed_file_extensions = fields.Char(
        string='Allowed File Extensions',
        compute='_compute_allowed_file_types',
    )

    @api.depends('wallet_reset_line_id')
    def _compute_is_paid(self):
        for task in self:
            task.is_paid = bool(task.wallet_reset_line_id)

    @api.depends(
        'category_id.allow_image_files',
        'category_id.allow_pdf_files',
        'category_id.allow_ppt_files',
        'category_id.allow_video_files',
        'category_id.allow_audio_files',
    )
    @api.depends_context('lang')
    def _compute_allowed_file_types(self):
        for task in self:
            labels = task.category_id._allowed_file_type_labels() if task.category_id else []
            task.file_upload_allowed = bool(labels)
            task.allowed_file_types_display = ', '.join(labels) if labels else _('No file uploads allowed')
            task.allowed_file_extensions = (
                task.category_id._allowed_file_extensions() if task.category_id else ''
            )

    @api.onchange('category_id')
    def _onchange_category_id(self):
        if self.task_type_id and self.task_type_id.category_id != self.category_id:
            self.task_type_id = False
            self.incentive_value = 0.0

    @api.onchange('task_type_id')
    def _onchange_task_type_id(self):
        if self.task_type_id:
            self.incentive_value = self.task_type_id.incentive_value
            self.company_id = self.task_type_id.company_id

    @api.constrains('member_id', 'company_id', 'category_id', 'task_type_id', 'wallet_id')
    def _check_task_ownership(self):
        for task in self:
            if task.task_type_id.category_id != task.category_id:
                raise ValidationError(_(
                    'The selected task type does not belong to the selected material category.'
                ))
            if task.task_type_id.company_id != task.company_id:
                raise ValidationError(_('The task type must belong to the task company.'))
            if task.wallet_id.user_id != task.member_id or task.wallet_id.company_id != task.company_id:
                raise ValidationError(_('The selected wallet does not match the task member and company.'))
            if task.company_id not in task.member_id.company_ids:
                raise ValidationError(_('The member must have access to the task company.'))

    @api.model_create_multi
    def create(self, vals_list):
        is_manager = self.env.user.has_group('ab_training_tasks.group_training_tasks_manager')
        prepared_vals = []
        wallet_model = self.env['ab.training.wallet'].sudo()
        for incoming in vals_list:
            vals = dict(incoming)
            member = self.env['res.users'].browse(vals.get('member_id') or self.env.user.id).exists()
            category = self.env['ab.training.task.category'].browse(vals.get('category_id')).exists()
            task_type = self.env['ab.training.task.type'].browse(vals.get('task_type_id')).exists()
            if not member or not category or not task_type:
                raise ValidationError(_('A valid member, material category, and task type are required.'))
            if task_type.category_id != category:
                raise ValidationError(_(
                    'The selected task type does not belong to the selected material category.'
                ))
            if not is_manager and member != self.env.user:
                raise AccessError(_('Members can only create their own training tasks.'))
            company = task_type.company_id
            if vals.get('company_id') and vals['company_id'] != company.id:
                raise ValidationError(_('The task company must match the task type company.'))
            if company not in member.company_ids:
                raise ValidationError(_('The member must have access to the task company.'))
            wallet = wallet_model._get_or_create(member, company)
            vals.update({
                'member_id': member.id,
                'category_id': category.id,
                'company_id': company.id,
                'wallet_id': wallet.id,
                'incentive_value': task_type.incentive_value,
                'state': 'pending',
                'rejection_reason': False,
                'approved_by': False,
                'approved_at': False,
                'rejected_by': False,
                'rejected_at': False,
                'wallet_reset_line_id': False,
            })
            prepared_vals.append(vals)
        return super().create(prepared_vals)

    def write(self, vals):
        is_manager = self.env.user.has_group('ab_training_tasks.group_training_tasks_manager')
        transition_operation = self.env.context.get('training_task_transition')
        reset_allowed = self.env.context.get('training_wallet_reset_operation')
        protected_transition_fields = {
            'state', 'rejection_reason', 'approved_by', 'approved_at',
            'rejected_by', 'rejected_at',
        }
        protected_system_fields = {'wallet_id', 'incentive_value', 'company_id', 'wallet_reset_line_id'}
        requested_fields = set(vals)

        if requested_fields & protected_transition_fields and transition_operation not in {
            'approve', 'reject', 'resubmit',
        }:
            raise AccessError(_('Task decisions must use the approval workflow actions.'))
        if requested_fields & protected_transition_fields:
            if transition_operation in {'approve', 'reject'} and not is_manager:
                raise AccessError(_('Only training managers can approve or reject tasks.'))
            if transition_operation == 'resubmit' and not is_manager:
                allowed_resubmit_fields = {'state', 'rejection_reason', 'rejected_by', 'rejected_at'}
                invalid_resubmit_values = (
                    vals.get('state') != 'pending'
                    or any(vals.get(field_name) for field_name in allowed_resubmit_fields - {'state'})
                    or bool((requested_fields & protected_transition_fields) - allowed_resubmit_fields)
                )
                if invalid_resubmit_values or any(
                    task.member_id != self.env.user or task.state != 'rejected' for task in self
                ):
                    raise AccessError(_('Members can only resubmit their own rejected tasks.'))
        if 'wallet_reset_line_id' in requested_fields and (not reset_allowed or not is_manager):
            raise AccessError(_('Task payout links can only be changed through the wallet reset workflow.'))
        if requested_fields & (protected_system_fields - {'wallet_reset_line_id'}):
            raise AccessError(_('Task incentive and wallet values are managed automatically.'))

        business_fields = {
            'name', 'member_id', 'category_id', 'task_type_id', 'completion_date',
            'description', 'material_reference', 'material_ids',
        }
        if not is_manager and requested_fields & business_fields:
            if any(task.member_id != self.env.user for task in self):
                raise AccessError(_('Members can only edit their own training tasks.'))
            if any(task.state not in ('pending', 'rejected') for task in self):
                raise UserError(_('Approved tasks can no longer be edited by members.'))
            if 'member_id' in requested_fields:
                raise AccessError(_('Members cannot reassign training tasks.'))

        snapshot_fields = {'member_id', 'category_id', 'task_type_id'}
        if requested_fields & snapshot_fields and any(task.wallet_reset_line_id for task in self):
            raise UserError(_('Paid tasks cannot be reassigned or recategorized.'))
        if requested_fields & {'category_id', 'task_type_id'} and any(
            task.state == 'approved' for task in self
        ):
            raise UserError(_('The task classification cannot be changed after approval.'))

        if len(self) > 1 and requested_fields & snapshot_fields:
            for task in self:
                task.write(dict(vals))
            return True

        if requested_fields & snapshot_fields:
            self.ensure_one()
            member = self.env['res.users'].browse(vals.get('member_id', self.member_id.id)).exists()
            category = self.env['ab.training.task.category'].browse(
                vals.get('category_id', self.category_id.id)
            ).exists()
            task_type = self.env['ab.training.task.type'].browse(vals.get('task_type_id', self.task_type_id.id)).exists()
            if not member or not category or not task_type:
                raise ValidationError(_('A valid member, material category, and task type are required.'))
            if task_type.category_id != category:
                raise ValidationError(_(
                    'The selected task type does not belong to the selected material category.'
                ))
            incompatible_materials = self.material_ids.filtered(
                lambda material: not category._allows_file_type(material.file_type)
            )
            if incompatible_materials:
                raise ValidationError(_(
                    'The task type cannot be changed because existing training materials use disallowed file types.'
                ))
            company = task_type.company_id
            if company not in member.company_ids:
                raise ValidationError(_('The member must have access to the task company.'))
            wallet = self.env['ab.training.wallet'].sudo()._get_or_create(member, company)
            vals.update({
                'member_id': member.id,
                'category_id': category.id,
                'company_id': company.id,
                'wallet_id': wallet.id,
                'incentive_value': task_type.incentive_value,
            })
        return super().write(vals)

    def unlink(self):
        if any(task.wallet_reset_line_id for task in self):
            raise UserError(_('Paid tasks cannot be deleted because they belong to a payout log.'))
        return super().unlink()

    def _ensure_manager(self):
        if not self.env.user.has_group('ab_training_tasks.group_training_tasks_manager'):
            raise AccessError(_('Only training managers can approve or reject tasks.'))

    def action_approve(self):
        self._ensure_manager()
        invalid = self.filtered(lambda task: task.state != 'pending')
        if invalid:
            raise UserError(_('Only pending tasks can be approved.'))
        self.with_context(training_task_transition='approve').write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_at': fields.Datetime.now(),
            'rejection_reason': False,
            'rejected_by': False,
            'rejected_at': False,
        })
        return True

    def action_open_reject_wizard(self):
        self.ensure_one()
        self._ensure_manager()
        if self.state != 'pending':
            raise UserError(_('Only pending tasks can be rejected.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject Training Task'),
            'res_model': 'ab.training.task.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_task_id': self.id},
        }

    def _reject_with_reason(self, reason):
        self.ensure_one()
        self._ensure_manager()
        reason = (reason or '').strip()
        if not reason:
            raise ValidationError(_('A rejection reason is required.'))
        if self.state != 'pending':
            raise UserError(_('Only pending tasks can be rejected.'))
        self.with_context(training_task_transition='reject').write({
            'state': 'rejected',
            'rejection_reason': reason,
            'rejected_by': self.env.user.id,
            'rejected_at': fields.Datetime.now(),
            'approved_by': False,
            'approved_at': False,
        })
        return True

    def action_resubmit(self):
        for task in self:
            is_manager = self.env.user.has_group('ab_training_tasks.group_training_tasks_manager')
            if not is_manager and task.member_id != self.env.user:
                raise AccessError(_('Members can only resubmit their own tasks.'))
            if task.state != 'rejected':
                raise UserError(_('Only rejected tasks can be resubmitted.'))
            previous_reason = task.rejection_reason
            task.with_context(training_task_transition='resubmit').write({
                'state': 'pending',
                'rejection_reason': False,
                'rejected_by': False,
                'rejected_at': False,
            })
            task.message_post(body=_('Task resubmitted. Previous rejection reason: %s') % previous_reason)
        return True

    @api.model
    def get_dashboard_data(self, month=None):
        is_manager = self.env.user.has_group('ab_training_tasks.group_training_tasks_manager')
        is_member = self.env.user.has_group('ab_training_tasks.group_training_tasks_member')
        if not is_manager and not is_member:
            raise AccessError(_('You do not have access to the training dashboard.'))

        month_start = self._parse_dashboard_month(month)
        next_month = month_start + relativedelta(months=1)
        company = self.env.company
        base_domain = [('company_id', '=', company.id)]
        if not is_manager:
            base_domain.append(('member_id', '=', self.env.user.id))
        month_domain = base_domain + [
            ('completion_date', '>=', fields.Date.to_string(month_start)),
            ('completion_date', '<', fields.Date.to_string(next_month)),
        ]
        monthly_tasks = self.search(month_domain)
        current_wallet_tasks = self.search(base_domain + [
            ('state', 'in', ('pending', 'approved')),
            ('wallet_reset_line_id', '=', False),
        ])
        trend_start = month_start - relativedelta(months=5)
        trend_tasks = self.search(base_domain + [
            ('completion_date', '>=', fields.Date.to_string(trend_start)),
            ('completion_date', '<', fields.Date.to_string(next_month)),
        ])
        recent_tasks = self.search(base_domain, limit=8, order='completion_date desc, id desc')

        data = {
            'role': 'manager' if is_manager else 'member',
            'month': month_start.strftime('%Y-%m'),
            'currency_code': company.currency_id.name,
            'currency_symbol': company.currency_id.symbol,
            'wallet': self._wallet_summary(current_wallet_tasks),
            'monthly': self._state_summary(monthly_tasks),
            'categories': self._category_summary(monthly_tasks),
            'trend': self._monthly_trend(trend_tasks, trend_start, month_start),
            'recent': [self._dashboard_task_values(task) for task in recent_tasks],
        }
        if is_manager:
            data['top_members'] = self._top_member_summary(monthly_tasks)
        return data

    @api.model
    def _parse_dashboard_month(self, month):
        if not month:
            today = fields.Date.context_today(self)
            return today.replace(day=1)
        try:
            return date.fromisoformat('%s-01' % month)
        except (TypeError, ValueError):
            raise ValidationError(_('The dashboard month must use the YYYY-MM format.'))

    @api.model
    def _wallet_summary(self, tasks):
        approved = tasks.filtered(lambda task: task.state == 'approved')
        pending = tasks.filtered(lambda task: task.state == 'pending')
        return {
            'approved_amount': sum(approved.mapped('incentive_value')),
            'approved_count': len(approved),
            'pending_amount': sum(pending.mapped('incentive_value')),
            'pending_count': len(pending),
        }

    @api.model
    def _state_summary(self, tasks):
        values = {'total_count': len(tasks)}
        for state in ('approved', 'pending', 'rejected'):
            state_tasks = tasks.filtered(lambda task, task_state=state: task.state == task_state)
            values['%s_count' % state] = len(state_tasks)
            values['%s_amount' % state] = sum(state_tasks.mapped('incentive_value'))
        values['active_member_count'] = len(tasks.mapped('member_id'))
        return values

    @api.model
    def _category_summary(self, tasks):
        grouped = defaultdict(lambda: {'count': 0, 'approved_amount': 0.0})
        categories = {}
        for task in tasks:
            category_id = task.category_id.id
            categories[category_id] = task.category_id.display_name
            grouped[category_id]['count'] += 1
            if task.state == 'approved':
                grouped[category_id]['approved_amount'] += task.incentive_value
        return [
            {
                'id': category_id,
                'label': categories[category_id],
                'count': values['count'],
                'approved_amount': values['approved_amount'],
            }
            for category_id, values in sorted(
                grouped.items(),
                key=lambda item: (-item[1]['count'], categories[item[0]]),
            )
        ]

    @api.model
    def _monthly_trend(self, tasks, trend_start, selected_month):
        values = defaultdict(lambda: {'task_count': 0, 'approved_amount': 0.0})
        for task in tasks:
            key = task.completion_date.strftime('%Y-%m')
            values[key]['task_count'] += 1
            if task.state == 'approved':
                values[key]['approved_amount'] += task.incentive_value
        result = []
        cursor = trend_start
        while cursor <= selected_month:
            key = cursor.strftime('%Y-%m')
            result.append({'month': key, **values[key]})
            cursor += relativedelta(months=1)
        return result

    @api.model
    def _top_member_summary(self, tasks):
        grouped = defaultdict(lambda: {
            'task_count': 0,
            'approved_count': 0,
            'pending_count': 0,
            'approved_amount': 0.0,
            'pending_amount': 0.0,
        })
        members = {}
        for task in tasks:
            member_id = task.member_id.id
            members[member_id] = task.member_id
            values = grouped[member_id]
            values['task_count'] += 1
            if task.state == 'approved':
                values['approved_count'] += 1
                values['approved_amount'] += task.incentive_value
            elif task.state == 'pending':
                values['pending_count'] += 1
                values['pending_amount'] += task.incentive_value
        ranked = sorted(
            grouped.items(),
            key=lambda item: (-item[1]['task_count'], -item[1]['approved_amount'], members[item[0]].name),
        )[:10]
        return [
            {
                'id': member_id,
                'name': members[member_id].display_name,
                'avatar_url': '/web/image/res.users/%s/avatar_128' % member_id,
                **values,
            }
            for member_id, values in ranked
        ]

    @api.model
    def _dashboard_task_values(self, task):
        state_labels = {
            'pending': _('Pending Approval'),
            'approved': _('Approved'),
            'rejected': _('Rejected'),
        }
        return {
            'id': task.id,
            'name': task.name,
            'member': task.member_id.display_name,
            'category': task.category_id.display_name,
            'task_type': task.task_type_id.display_name,
            'state': task.state,
            'state_label': state_labels[task.state],
            'completion_date': fields.Date.to_string(task.completion_date),
            'incentive_value': task.incentive_value,
            'is_paid': task.is_paid,
        }
