import json
from concurrent.futures import ThreadPoolExecutor

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


def _ssh_test_reason(code, env):
    # Translation stays on the request thread; workers return plain codes only.
    return {
        'ok': False,
        'authentication': env._('Authentication failed.'),
        'timeout': env._('Connection timed out.'),
        'hostname': env._('The SSH hostname could not be resolved.'),
        'unreachable': env._('The server is unreachable.'),
        'refused': env._('The server refused the SSH connection.'),
        'host_key': env._('SSH host key verification failed.'),
        'failed': env._('SSH connection or remote shell check failed.'),
        'alias': env._('The configured SSH alias is invalid.'),
        'client': env._('The SSH client could not be started.'),
    }[code]


ENVIRONMENTS = [('development', 'Development'), ('test', 'Test'),
                ('pilot', 'Pilot'), ('production', 'Production')]
REQUEST_STATES = [('draft', 'Draft'), ('requested', 'Requested'),
                  ('approved', 'Approved'), ('rejected', 'Rejected'),
                  ('cancelled', 'Cancelled')]


class DeployAuditLog(models.Model):
    _name = 'ab_deploy_audit_log'
    _description = 'Deployment Audit Log'
    _order = 'id desc'
    _rec_name = 'record_name'

    record_model = fields.Char(required=True)
    record_id = fields.Integer(required=True)
    record_name = fields.Char(required=True)
    action = fields.Selection([('create', 'Created'), ('write', 'Updated'), ('unlink', 'Removed')], required=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    occurred_at = fields.Datetime(required=True)
    before_values = fields.Text()
    after_values = fields.Text()

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Audit records can only be created by the deployment workflow.'))

    def write(self, vals):
        raise AccessError(_('Deployment audit history cannot be modified.'))

    def unlink(self):
        raise AccessError(_('Deployment audit history cannot be deleted.'))

    @api.model
    def _append(self, values):
        # Only private, validated business methods call this narrow elevation.
        super(DeployAuditLog, self.sudo()).create(values)


class DeployGuard(models.AbstractModel):
    _name = 'ab_deploy_guard'
    _description = 'Deployment Record Guard'

    def _require_role(self, role):
        if not (self.env.user.has_group('ab_deploy.group_administrator')
                or self.env.user.has_group('ab_deploy.group_' + role)):
            raise AccessError(_('You do not have the required deployment role.'))
        self.check_access('write' if self else 'create')

    def _lock(self):
        self.lock_for_update()
        self.invalidate_recordset()

    def _audit(self, action, before=None, values=None, after=None):
        values_list = []
        for record in self:
            values_list.append({
                'record_model': record._name, 'record_id': record.id,
                'record_name': record.display_name, 'action': action,
                'user_id': self.env.uid, 'occurred_at': fields.Datetime.now(),
                'before_values': json.dumps(record._audit_values((before or {}).get(record.id, {})), default=str, ensure_ascii=False),
                'after_values': json.dumps(record._audit_values(after.get(record.id, {}) if after is not None else (values or {})), default=str, ensure_ascii=False),
            })
        if values_list:
            self.env['ab_deploy_audit_log']._append(values_list)

    def _audit_values(self, values):
        return {key: value for key, value in values.items()
                if key not in {'ssh_key_reference', 'host_fingerprint', 'lease_token'}}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        field_names = list(set().union(*(vals.keys() for vals in vals_list)))
        snapshots = {row['id']: row for row in records.read(field_names, load=None)}
        records._audit('create', after=snapshots)
        return records

    def write(self, vals):
        before = {r['id']: r for r in self.read(list(vals), load=None)}
        result = super().write(vals)
        self._audit('write', before=before, values=vals)
        return result

    def unlink(self):
        raise UserError(_('Deployment records must be retained. Archive or cancel them instead.'))


class DeployServer(models.Model):
    _name = 'ab_deploy_server'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Server'
    _order = 'name, id'

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    ssh_alias = fields.Char(string='SSH Alias', required=True, index=True)
    environment = fields.Selection(ENVIRONMENTS, required=True, default='test')
    hostname = fields.Char(string='Address (Informational)')
    serial = fields.Char()
    db_serial = fields.Char(string='Database Serial')
    odoo_url = fields.Char(string='Odoo URL')
    contact = fields.Char()
    area = fields.Char()
    active = fields.Boolean(default=True)
    maintenance_mode = fields.Boolean()
    monitor_timeout_seconds = fields.Integer(default=600, required=True)
    odoo_log_path = fields.Char(string='Odoo Log Path', default='/opt/odoo19/odoo.log')
    odoo_server_path = fields.Char(string='Odoo Server Path', default='/opt/odoo19')
    odoo_config_path = fields.Char(string='Odoo Server Config', default='/opt/odoo19/odoo19.conf')
    odoo_python_path = fields.Char(string='Odoo Python Venv', default='/opt/odoo19/venv19/bin/python')

    _log_path_fields = ('odoo_log_path', 'odoo_server_path', 'odoo_config_path', 'odoo_python_path')

    @api.constrains(*_log_path_fields)
    def _check_log_paths(self):
        for record in self:
            for name in self._log_path_fields:
                value = record[name]
                if value and (not value.startswith('/') or any(ord(c) < 32 or ord(c) == 127 for c in value)):
                    raise ValidationError(_('Odoo paths must be absolute and contain no control characters.'))

    _unique_code = models.Constraint('UNIQUE(code)', 'Server code must be unique.')
    _unique_alias = models.Constraint('UNIQUE(ssh_alias)', 'SSH alias must be unique.')

    @api.constrains('ssh_alias', 'monitor_timeout_seconds')
    def _check_settings(self):
        from ..runner.engine import validate_server
        for record in self:
            try:
                validate_server(record.read(['ssh_alias', 'monitor_timeout_seconds'])[0])
            except ValueError as exc:
                raise ValidationError(_(str(exc))) from exc

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('administrator')
        return super().create(vals_list)

    def write(self, vals):
        self._require_role('administrator')
        self._lock()
        return super().write(vals)


class DeployRequest(models.Model):
    _name = 'ab_deploy_request'
    _inherit = ['ab_deploy_guard', 'mail.thread', 'mail.activity.mixin']
    _description = 'Deployment Request'
    _order = 'id desc'

    name = fields.Char(required=True, readonly=True, copy=False, default='/')
    title = fields.Char(required=True)
    description = fields.Text()
    active = fields.Boolean(default=True)
    developer_id = fields.Many2one('res.users', required=True, default=lambda self: self.env.user)
    approver_id = fields.Many2one('res.users', required=True)
    get_recent_odoo_log = fields.Boolean(string='Get Recent Odoo Log', default=False)
    restart_required = fields.Boolean()
    upgrade_required = fields.Boolean(string='Module Upgrade Required')
    database_impact = fields.Selection([('none', 'No Database Change'), ('schema', 'Schema Change'),
                                       ('data', 'Data Change'), ('both', 'Schema and Data Change')], default='none', required=True)
    backup_policy = fields.Selection([('none', 'None'), ('files', 'Files'), ('database', 'Database'),
                                     ('both', 'Files and Database')], default='none', required=True)
    command_ids = fields.One2many('ab_deploy_request_command', 'request_id', string='Commands', copy=True)
    target_ids = fields.One2many('ab_deploy_target', 'request_id', string='Target Servers', copy=True)
    server_ids = fields.Many2many('ab_deploy_server', string='Target Servers',
                                 compute='_compute_server_ids', inverse='_inverse_server_ids',
                                 context={'active_test': False})
    job_ids = fields.One2many('ab_deploy_job', 'request_id', string='Execution Jobs', readonly=True)
    queued = fields.Boolean(readonly=True, copy=False)
    state = fields.Selection(REQUEST_STATES, default='draft', readonly=True, required=True, copy=False, tracking=True)
    requested_by = fields.Many2one('res.users', readonly=True, copy=False)
    requested_at = fields.Datetime(readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', readonly=True, copy=False)
    approved_at = fields.Datetime(readonly=True, copy=False)
    decision_note = fields.Text(string='Decision / Withdrawal Reason')
    approval_activity_id = fields.Many2one('mail.activity', readonly=True, copy=False, ondelete='set null')

    _unique_name = models.Constraint('UNIQUE(name)', 'Request reference must be unique.')
    _protected = {'name', 'state', 'queued', 'requested_by', 'requested_at', 'approved_by', 'approved_at', 'approval_activity_id', 'job_ids'}

    @api.depends('target_ids.server_id')
    def _compute_server_ids(self):
        for record in self:
            record.server_ids = record.target_ids.server_id

    def _inverse_server_ids(self):
        # Preserve the edited values before locking invalidates the request cache.
        selections = {record.id: record.server_ids for record in self}
        self._draft()
        for record in self:
            selected = selections[record.id]
            selected.check_access('read')
            if any(not server.active or server.maintenance_mode for server in selected):
                raise ValidationError(_('Targets must be active and outside maintenance.'))
            existing = record.target_ids
            removed = existing.filtered(lambda target: target.server_id not in selected)
            added = selected - existing.server_id
            removed.unlink()
            if added:
                self.env['ab_deploy_target'].create([
                    {'request_id': record.id, 'server_id': server.id} for server in added])

    def _add_environment_servers(self, environment):
        self._draft()
        servers = self.env['ab_deploy_server'].search(
            fields.Domain('environment', '=', environment)
            & fields.Domain('active', '=', True)
            & fields.Domain('maintenance_mode', '=', False))
        for record in self:
            missing = servers - record.target_ids.server_id
            self.env['ab_deploy_target'].create([
                {'request_id': record.id, 'server_id': server.id} for server in missing])
        return True

    def action_add_development_servers(self):
        return self._add_environment_servers('development')

    def action_add_production_servers(self):
        return self._add_environment_servers('production')

    def action_test_selected_ssh(self):
        self.ensure_one()
        self.check_access('read')
        if not (self.env.user.has_group('ab_deploy.group_administrator')
                or self.env.user.has_group('ab_deploy.group_executor')):
            raise AccessError(_('You do not have the required deployment role.'))
        targets = self.target_ids.filtered('deploy').sorted('id')
        targets.check_access('read')
        targets.server_id.check_access('read')
        if not targets:
            return {'type': 'ir.actions.client', 'tag': 'display_notification',
                    'params': {'title': _('Test Selected SSH'),
                               'message': _('Select at least one server to test SSH.'),
                               'type': 'warning', 'sticky': False}}
        # Materialize all ORM data before starting worker threads.
        servers = [(target.server_id.name, target.server_id.ssh_alias or '') for target in targets]
        from ..runner import engine
        with ThreadPoolExecutor(max_workers=min(70, len(servers))) as pool:
            results = list(pool.map(engine.test_ssh, [alias for name, alias in servers]))
        failures = [(name, _ssh_test_reason(code, self.env)) for (name, alias), code in zip(servers, results) if code != 'ok']
        message = _('Tested: %(total)s; Successful: %(success)s; Failed: %(failed)s.',
                    total=len(servers), success=len(servers) - len(failures), failed=len(failures))
        if failures:
            message += ' ' + '; '.join('%s: %s' % failure for failure in failures)
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Test Selected SSH'), 'message': message,
                           'type': 'warning' if failures else 'success', 'sticky': bool(failures)}}

    def action_select_all_targets(self):
        return self._select_targets(True)

    def action_select_all_ssh_failures(self):
        return self._select_targets(True, retry=True)

    def action_clear_target_selection(self):
        return self._select_targets(False)

    def _select_targets(self, selected, retry=False):
        self._require_role('executor')
        self.sorted('id')._lock()
        if any(request.state != 'approved' for request in self):
            raise UserError(_('Deployment selection requires an approved request.'))
        self.target_ids._clear_selection()
        if selected:
            targets = self.target_ids.filtered(lambda target: target._ssh_retry_job() if retry else not target.job_ids)
            targets.write({'deploy': True})
        return True

    def _selected_targets(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError(_('Only approved requests can queue selected servers.'))
        targets = self.target_ids.filtered('deploy')
        if not targets:
            raise UserError(_('Select at least one delayed server for deployment.'))
        if any(target.job_ids for target in targets):
            raise UserError(_('Queue Selected Servers accepts only delayed servers. Clear SSH failures or other executed servers from the selection.'))
        return targets

    def _draft(self):
        self._require_role('developer')
        self._lock()
        if any(r.state != 'draft' or r.queued for r in self):
            raise UserError(_('Return the request to draft before editing it.'))

    @api.model_create_multi
    def create(self, vals_list):
        self._require_role('developer')
        for vals in vals_list:
            if self._protected.intersection(vals):
                raise AccessError(_('Workflow fields can only be set using deployment actions.'))
            vals['name'] = self.env['ir.sequence'].next_by_code('ab_deploy_request')
            vals['state'] = 'draft'
        return super().create(vals_list)

    def write(self, vals):
        if self._protected.intersection(vals):
            raise AccessError(_('Workflow fields can only be set using deployment actions.'))
        if set(vals) <= {'decision_note'}:
            self._require_role('viewer')
            self._lock()
        elif set(vals) <= {'active'}:
            self._require_role('developer')
        elif set(vals) == {'target_ids'} and all(r.state == 'approved' for r in self):
            self._require_role('executor')
            self.sorted('id')._lock()
            allowed = set(self.target_ids.ids)
            for command in vals['target_ids']:
                if (len(command) != 3 or command[0] != fields.Command.UPDATE
                        or command[1] not in allowed or set(command[2]) != {'deploy'}):
                    raise AccessError(_('Only deployment selection can change on approved targets.'))
        else:
            self._draft()
        return super().write(vals)

    def _transition(self, vals):
        return super().write(vals)

    def _clear_activity(self):
        self.mapped('approval_activity_id').sudo().unlink()

    def action_submit(self):
        self._draft()
        for record in self:
            if not record.command_ids or not record.target_ids:
                raise ValidationError(_('Select commands and at least one target server.'))
            approver = record.approver_id
            if not approver.active or not (approver.has_group('ab_deploy.group_approver') or approver.has_group('ab_deploy.group_administrator')):
                raise ValidationError(_('Choose an active user with the Approver or Administrator role.'))
            if approver == self.env.user:
                raise ValidationError(_('A deployment request must be approved by a different user.'))
            record.target_ids._freeze()
            record._transition({'state': 'requested', 'requested_by': self.env.uid, 'requested_at': fields.Datetime.now(),
                                'approved_by': False, 'approved_at': False, 'decision_note': False})
            activity = record.activity_schedule('mail.mail_activity_data_todo', user_id=approver.id,
                                               summary=_('Review deployment request'))
            record._transition({'approval_activity_id': activity.id})
        return True

    def _decision(self):
        self._require_role('approver')
        self._lock()
        if any(r.state != 'requested' for r in self):
            raise UserError(_('Only requested deployments can be approved or rejected.'))
        if any(r.requested_by == self.env.user for r in self):
            raise AccessError(_('You cannot approve or reject your own deployment request.'))
        if not self.env.user.has_group('ab_deploy.group_administrator') and any(r.approver_id != self.env.user for r in self):
            raise AccessError(_('Only the assigned approver or a deployment administrator can decide this request.'))

    def action_approve(self):
        self._decision()
        self.target_ids._validate_check_snapshot()
        self._clear_activity()
        self._transition({'state': 'approved', 'approved_by': self.env.uid, 'approved_at': fields.Datetime.now()})
        return True

    def action_reject(self):
        self._decision()
        if any(not (r.decision_note or '').strip() for r in self):
            raise ValidationError(_('Enter a reason before rejecting the request.'))
        self._clear_activity()
        self._transition({'state': 'rejected'})
        return True

    def action_withdraw(self):
        self._require_role('developer')
        self._lock()
        if any(r.queued for r in self):
            raise UserError(_('Queued requests are immutable. Create a new request for another attempt.'))
        self._clear_activity()
        self._transition({'state': 'draft', 'requested_by': False, 'requested_at': False, 'approved_by': False, 'approved_at': False})
        return True

    def action_cancel(self):
        self._require_role('developer')
        self._lock()
        self._clear_activity()
        self._transition({'state': 'cancelled'})
        self.mapped('job_ids').filtered(lambda j: j.state == 'queued')._set({'state': 'cancelled'})
        return True

    def action_queue(self):
        self._require_role('executor')
        self.ensure_one()
        self._lock()
        targets = self._selected_targets()
        targets.server_id.sorted('id')._lock()
        conflicts = self._queue_conflicts()
        if conflicts:
            return self.env['ab_deploy_conflict']._open(self, conflicts)
        return self._queue_confirmed()

    def _queue_conflicts(self):
        return self.env['ab_deploy_job'].sudo().search(
            fields.Domain('server_id', 'in', self._selected_targets().server_id.ids)
            & fields.Domain('state', 'in', ['queued', 'running', 'unknown'])
            & fields.Domain('request_id', '!=', self.id), order='id')

    def _queue_confirmed(self):
        self.ensure_one()
        self._require_role('executor')
        self._lock()
        targets = self._selected_targets()
        targets._check_available()
        targets.sorted('id')._lock()
        jobs = self.env['ab_deploy_job']._make(targets)
        targets._clear_selection()
        self._transition({'queued': True})
        self._schedule_run(jobs)
        return True


class DeployTarget(models.Model):
    _name = 'ab_deploy_target'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Target'
    _rec_name = 'server_id'

    request_id = fields.Many2one('ab_deploy_request', required=True, ondelete='restrict', index=True)
    server_id = fields.Many2one('ab_deploy_server', required=True, ondelete='restrict', index=True)
    server_serial = fields.Char(string='Serial', related='server_id.serial', readonly=True)
    server_area = fields.Char(string='Area', related='server_id.area', readonly=True)
    server_odoo_url = fields.Char(string='Odoo URL', related='server_id.odoo_url', readonly=True)
    script = fields.Text(string='Approved Script', readonly=True, copy=False)
    script_hash = fields.Char(string='Script SHA-256', readonly=True, copy=False)
    snapshot = fields.Json(readonly=True, copy=False)
    job_key = fields.Char(readonly=True, copy=False)
    job_ids = fields.One2many('ab_deploy_job', 'target_id', readonly=True)
    deploy = fields.Boolean(string='Selected', default=False, copy=False)
    selection_eligible = fields.Boolean(compute='_compute_selection_eligible')
    deployment_status = fields.Selection([
        ('delayed', 'Delayed'), ('queued', 'Queued'), ('running', 'Running'),
        ('unknown', 'Unknown'), ('succeeded', 'Succeeded'), ('failed', 'Failed'),
        ('cancelled', 'Cancelled'), ('manually_resolved', 'Manually Resolved')], string='Status', compute='_compute_deployment_status')

    @api.depends('job_ids.state', 'request_id.state')
    def _compute_deployment_status(self):
        for target in self:
            latest = target.job_ids.sorted('id', reverse=True)[:1]
            target.deployment_status = latest.state if latest else (
                'cancelled' if target.request_id.state == 'cancelled' else 'delayed')

    def action_test_ssh(self):
        self.ensure_one()
        self.check_access('read')
        self.request_id.check_access('read')
        self.server_id.check_access('read')
        if not (self.env.user.has_group('ab_deploy.group_administrator')
                or self.env.user.has_group('ab_deploy.group_executor')):
            raise AccessError(_('You do not have the required deployment role.'))
        from ..runner import engine
        reason = _ssh_test_reason(engine.test_ssh(self.server_id.ssh_alias or ''), self.env)
        title = _('SSH connection failed: %s', self.server_id.name) if reason else _('SSH connection successful: %s', self.server_id.name)
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': title, 'message': reason or _('SSH authentication and remote command execution succeeded.'),
                           'type': 'danger' if reason else 'success', 'sticky': bool(reason)}}

    def _ssh_retry_job(self):
        self.ensure_one()
        latest = self.job_ids.sorted('id', reverse=True)[:1]
        return latest.filtered(lambda job: job.failure_kind == 'ssh' and job.state in ('failed', 'unknown'))

    @api.depends('job_ids.state', 'job_ids.failure_kind')
    def _compute_selection_eligible(self):
        for target in self:
            target.selection_eligible = not target.job_ids or bool(target._ssh_retry_job())

    def _clear_selection(self):
        return super(DeployTarget, self).write({'deploy': False})

    _unique_target = models.Constraint('UNIQUE(request_id, server_id)', 'A server may appear only once in a deployment request.')

    @api.model_create_multi
    def create(self, vals_list):
        # Inline rows may include defaults and readonly display values. Never
        # trust those values: recompute them from the server and execution data.
        display_fields = {
            'server_serial', 'server_area', 'server_odoo_url',
            'deployment_status', 'selection_eligible', 'display_status_rank',
            'display_serial_kind', 'display_serial_length',
            'display_serial_value', 'display_server_name',
        }
        clean_vals_list = []
        for incoming in vals_list:
            vals = dict(incoming)
            for field in display_fields:
                vals.pop(field, None)
            if 'deploy' in vals and (vals['deploy'] is False or type(vals['deploy']) is int and vals['deploy'] == 0):
                vals.pop('deploy')
            if set(vals) - {'request_id', 'server_id'}:
                raise AccessError(_('Target workflow fields cannot be set manually.'))
            vals.setdefault('request_id', self.env.context.get('default_request_id'))
            clean_vals_list.append(vals)
        self.env['ab_deploy_request'].browse([v['request_id'] for v in clean_vals_list])._draft()
        # Override context defaults too: new targets must start unselected.
        return super().create([dict(vals, deploy=False) for vals in clean_vals_list])

    def write(self, vals):
        if set(vals) == {'deploy'}:
            requests = self.mapped('request_id')
            requests._require_role('executor')
            requests.sorted('id')._lock()
            self.sorted('id')._lock()
            if any(r.state != 'approved' for r in requests):
                raise UserError(_('Deployment selection requires an approved request.'))
            self.job_ids.sorted('id')._lock()
            if vals['deploy'] and any(t.job_ids and not t._ssh_retry_job() for t in self):
                raise UserError(_('Only delayed servers or SSH failures can be selected.'))
            return super().write(vals)
        if set(vals) - {'server_id'}:
            raise AccessError(_('The target request and workflow fields cannot be changed.'))
        self.mapped('request_id')._draft()
        return super().write(vals)

    def unlink(self):
        self.mapped('request_id')._draft()
        self._audit('unlink')
        return super(DeployGuard, self).unlink()

    def _check_available(self):
        servers = self.mapped('server_id')
        servers._lock()
        if any(not t.server_id.active or t.server_id.maintenance_mode for t in self):
            raise ValidationError(_('Targets must be active and outside maintenance.'))

    def _validate_check_snapshot(self):
        from ..runner import engine
        for target in self:
            snapshot = target.snapshot or {}
            if not snapshot.get('check_policy_version'):
                continue  # Preserve pre-policy submissions and their frozen scripts.
            commands = snapshot.get('commands', [])
            types = [command.get('command_type') for command in commands]
            policy = snapshot['check_policy_version']
            valid_order = types == sorted(types) if policy == 1 else self._valid_check_blocks(commands)
            if (policy not in (1, 2) or not types or 'check' not in types
                    or any(kind not in ('action', 'check') for kind in types)
                    or not valid_order
                    or target.script != engine.render(commands)
                    or target.script_hash != engine.checksum(target.script)):
                raise ValidationError(_('The approved post-deployment checks are missing or inconsistent. Return this request to draft and submit it again.'))

    @staticmethod
    def _valid_check_blocks(commands):
        pending = []
        parent = None
        standalone = False
        for command in commands:
            if pending:
                if (command.get('command_type') != 'check'
                        or command.get('parent_line_id') != parent
                        or command.get('command_id') != pending.pop(0)):
                    return False
            elif command.get('command_type') == 'action':
                if standalone or command.get('parent_line_id') or not command.get('line_id'):
                    return False
                pending = list(command.get('required_check_ids') or [])
                if not pending or len(pending) != len(set(pending)):
                    return False
                parent = command['line_id']
            elif command.get('command_type') == 'check' and not command.get('parent_line_id'):
                standalone = True
            else:
                return False
        return not pending

    def _freeze(self):
        import uuid
        from ..runner import engine
        self._check_available()
        requests = self.mapped('request_id')
        commands = requests.command_ids.command_id
        commands.sorted('id')._lock()
        commands.with_context(active_test=False).required_check_ids.sorted('id')._lock()
        commands._validate_required_checks()
        requests._sync_linked_checks()
        for target in self:
            if target.request_id.get_recent_odoo_log and any(not (target.server_id[name] or '').strip() for name in target.server_id._log_path_fields):
                raise ValidationError(_('Complete all four Odoo paths for server %s before requesting log collection.', target.server_id.name))
            lines = target.request_id.command_ids
            lines.mapped('command_id').sorted('id')._lock()
            lines = lines.sorted(lambda l: (l.execution_sequence, l.id))
            if any(not line.command_id.active for line in lines):
                raise ValidationError(_('Select active commands before requesting approval.'))
            if not any(line.command_id.command_type == 'check' for line in lines):
                raise ValidationError(_('Add at least one active Post-deployment Check before requesting approval.'))
            lines._freeze_type()
            commands = [{'name': l.command_id.name, 'bash': l.command_id.template,
                         'command_type': l.command_id.command_type, 'sequence': l.sequence,
                         'line_id': l.id, 'command_id': l.command_id.id,
                         'parent_line_id': l.parent_line_id.id or False,
                         'required_check_ids': l.command_id.required_check_ids.sorted(
                             lambda check: (check.check_sequence, check.id)).ids} for l in lines]
            script = engine.render(commands)
            snapshot = {'check_policy_version': 2, 'ssh_alias': target.server_id.ssh_alias,
                        'timeout': target.server_id.monitor_timeout_seconds, 'commands': commands}
            if target.request_id.get_recent_odoo_log:
                snapshot['odoo_log'] = {name: target.server_id[name] for name in target.server_id._log_path_fields}
            super(DeployTarget, target).write({'script': script, 'script_hash': engine.checksum(script),
                                              'snapshot': snapshot, 'job_key': uuid.uuid4().hex})
