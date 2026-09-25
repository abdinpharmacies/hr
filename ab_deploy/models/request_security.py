from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class DeployRequestSecurity(models.Model):
    _inherit = 'ab_deploy_request'

    executor_id = fields.Many2one('res.users', string='Assigned Executor', copy=False, tracking=True,
        domain=lambda self: [('active', '=', True), ('share', '=', False),
                             ('all_group_ids', 'in', [self.env.ref('ab_deploy.group_executor').id])])
    can_assign_executor = fields.Boolean(compute='_compute_assignment_access')
    can_execute = fields.Boolean(compute='_compute_assignment_access')
    can_manage_request = fields.Boolean(compute='_compute_assignment_access')

    @api.depends('state', 'executor_id', 'approver_id', 'developer_id')
    @api.depends_context('uid')
    def _compute_assignment_access(self):
        admin = self.env.user.has_group('ab_deploy.group_administrator')
        approver = self.env.user.has_group('ab_deploy.group_approver')
        executor = self.env.user.has_group('ab_deploy.group_executor')
        for request in self:
            request.can_assign_executor = admin or (request.state == 'requested' and approver
                and request.approver_id == self.env.user and request.requested_by != self.env.user
                and request.developer_id != self.env.user)
            request.can_execute = admin or (executor and request.executor_id == self.env.user)
            request.can_manage_request = admin or request.developer_id == self.env.user

    def _require_role(self, role):
        super()._require_role(role)
        if self.env.user.has_group('ab_deploy.group_administrator'):
            return
        if role == 'developer' and any(r.developer_id != self.env.user for r in self):
            raise AccessError(_('Only the request owner or a deployment administrator can change this request.'))
        if role == 'executor' and any(r.executor_id != self.env.user for r in self):
            raise AccessError(_('Only the assigned executor or a deployment administrator can execute this request.'))

    @api.model_create_multi
    def create(self, vals_list):
        admin = self.env.user.has_group('ab_deploy.group_administrator')
        for vals in vals_list:
            if not admin and (vals.get('developer_id', self.env.uid) != self.env.uid or vals.get('executor_id')):
                raise AccessError(_('Ownership and executor assignment cannot be set for another user.'))
        for vals in vals_list:
            vals.setdefault('developer_id', self.env.uid)
            vals.setdefault('executor_id', False)
        records = super().create(vals_list)
        records.filtered('executor_id')._validate_executor()
        return records

    def copy_data(self, default=None):
        default = dict(default or {})
        default.setdefault('developer_id', self.env.uid)
        return super().copy_data(default)

    def _validate_executor(self):
        for request in self:
            user = request.executor_id
            if not user or not user.active or user.share or not user.has_group('ab_deploy.group_executor'):
                raise ValidationError(_('Choose an active user with the Executor role before approving.'))
            if 'company_id' in request._fields and request.company_id not in user.sudo().company_ids:
                raise ValidationError(_('The assigned executor must have access to the deployment company.'))

    def write(self, vals):
        admin = self.env.user.has_group('ab_deploy.group_administrator')
        if 'decision_note' in vals and not admin and any(
                request.developer_id != self.env.user and not (request.state == 'requested'
                and request.approver_id == self.env.user and self.env.user.has_group('ab_deploy.group_approver'))
                for request in self):
            raise AccessError(_('Only the request owner or a deployment administrator can change this request.'))
        if 'developer_id' in vals and not admin:
            raise AccessError(_('Request ownership cannot be changed.'))
        if 'executor_id' in vals:
            self.check_access('write')
            self.sorted('id')._lock()
            if not admin:
                if set(vals) != {'executor_id'}:
                    raise AccessError(_('Save executor assignment separately from other changes.'))
                self._decision()
            if any(r.state != 'draft' for r in self):
                if self.sudo().job_ids.filtered(lambda j: j.state in ('queued', 'running', 'unknown')) or self.sudo().run_ids.filtered(
                        lambda run: run.queue_job_id.state in ('pending', 'enqueued', 'started', 'wait_dependencies')):
                    raise ValidationError(_('Wait for active executions and queue runs to finish before reassigning the executor.'))
            if set(vals) == {'executor_id'}:
                result = self._transition(vals)
                self._validate_executor()
                return result
        result = super().write(vals)
        if 'executor_id' in vals:
            self._validate_executor()
        return result

    def action_approve(self):
        self._decision()
        self._validate_executor()
        return super().action_approve()

    def _notify_get_recipients(self, message, msg_vals=False, **kwargs):
        recipients = super()._notify_get_recipients(message, msg_vals=msg_vals, **kwargs)
        partner_ids = [recipient['id'] for recipient in recipients if recipient.get('id')]
        users = self.env['res.users'].sudo().search(fields.Domain('partner_id', 'in', partner_ids)
            & fields.Domain('active', '=', True) & fields.Domain('share', '=', False))
        allowed = set()
        for user in users:
            request = self.with_user(user).with_context(allowed_company_ids=user.company_ids.ids)
            if request.has_access('read'):
                allowed.add(user.partner_id.id)
        return [recipient for recipient in recipients if recipient.get('id') in allowed]


class DeployJobSecurity(models.Model):
    _inherit = 'ab_deploy_job'

    queue_job_id = fields.Many2one(groups='ab_deploy.group_administrator')

    can_execute = fields.Boolean(related='request_id.can_execute', compute_sudo=False)


class DeployTargetSecurity(models.Model):
    _inherit = 'ab_deploy_target'

    can_execute = fields.Boolean(related='request_id.can_execute', compute_sudo=False)


class DeployMessageSecurity(models.Model):
    _inherit = 'mail.message'

    ab_deploy_request_id = fields.Many2one('ab_deploy_request', compute='_compute_ab_deploy_request',
        store=True, index=True, compute_sudo=True, readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if 'default_ab_deploy_request_id' in self.env.context or any('ab_deploy_request_id' in vals for vals in vals_list):
            raise AccessError(_('Deployment access links are managed automatically.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'ab_deploy_request_id' in vals:
            raise AccessError(_('Deployment access links are managed automatically.'))
        return super().write(vals)

    @api.depends('model', 'res_id')
    def _compute_ab_deploy_request(self):
        for message in self:
            message.ab_deploy_request_id = (self.env['ab_deploy_request'].browse(message.res_id).exists()
                if message.model == 'ab_deploy_request' and message.res_id else False)


class DeployAttachmentSecurity(models.Model):
    _inherit = 'ir.attachment'

    ab_deploy_request_id = fields.Many2one('ab_deploy_request', compute='_compute_ab_deploy_request',
        store=True, index=True, compute_sudo=True, readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if 'default_ab_deploy_request_id' in self.env.context or any('ab_deploy_request_id' in vals for vals in vals_list):
            raise AccessError(_('Deployment access links are managed automatically.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'ab_deploy_request_id' in vals:
            raise AccessError(_('Deployment access links are managed automatically.'))
        return super().write(vals)

    @api.depends('res_model', 'res_id')
    def _compute_ab_deploy_request(self):
        paths = {'ab_deploy_request': None, 'ab_deploy_target': 'request_id',
                 'ab_deploy_job': 'request_id', 'ab_deploy_request_command': 'request_id',
                 'ab_deploy_run': 'request_id', 'ab_deploy_attempt': 'job_id.request_id',
                 'ab_deploy_log_part': 'job_id.request_id', 'mail.message': 'ab_deploy_request_id'}
        for attachment in self:
            request = False
            if attachment.res_model in paths and attachment.res_id:
                record = self.env[attachment.res_model].browse(attachment.res_id).exists()
                if record:
                    request = record.mapped(paths[attachment.res_model]) if paths[attachment.res_model] else record
            attachment.ab_deploy_request_id = request


class DeployRunSecurity(models.Model):
    _inherit = 'ab_deploy_run'

    queue_job_id = fields.Many2one(groups='ab_deploy.group_administrator')


class DeployBinarySecurity(models.AbstractModel):
    _inherit = 'ir.binary'

    def _find_record(self, xmlid=None, res_model='ir.attachment', res_id=None, access_token=None, field=None):
        record = super()._find_record(xmlid=xmlid, res_model=res_model, res_id=res_id,
                                      access_token=access_token, field=field)
        paths = {'ab_deploy_request': None, 'ab_deploy_target': 'request_id',
                 'ab_deploy_job': 'request_id', 'ab_deploy_request_command': 'request_id',
                 'ab_deploy_run': 'request_id', 'ab_deploy_attempt': 'job_id.request_id',
                 'ab_deploy_log_part': 'job_id.request_id', 'mail.message': 'ab_deploy_request_id',
                 'ir.attachment': 'ab_deploy_request_id'}
        if record._name in paths:
            path = paths[record._name]
            request = record.sudo().mapped(path) if path else record.sudo()
            if request:
                request.with_user(self.env.user).check_access('read')
        return record
