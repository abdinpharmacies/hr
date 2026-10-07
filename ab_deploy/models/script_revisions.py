import copy
import difflib
import uuid

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .deployment import DeployTarget
from .jobs import DeployJob
from .batch import ACTIVE_QUEUE
from ..runner import engine


class DeployRequestRevisions(models.Model):
    _inherit = 'ab_deploy_request'

    revision_ids = fields.One2many('ab_deploy_script_revision', 'request_id', string='Script Revisions', readonly=True, copy=False)

    commands_update_available = fields.Boolean(compute='_compute_commands_update_available')

    @api.depends_context('uid', 'lang')
    @api.depends('state', 'target_ids.deployment_status', 'target_ids.selection_eligible', 'target_ids.script', 'target_ids.snapshot',
                 'command_ids.command_id.template', 'command_ids.command_id.active',
                 'command_ids.command_id.name', 'command_ids.command_id.command_type',
                 'command_ids.command_id.collect_health_report',
                 'request_purpose',
                 'command_ids.command_id.parameter_ids.value', 'command_ids.command_id.parameter_ids.bash_placeholder',
                 'command_ids.command_id.parameter_ids.server_id',
                 'command_ids.command_id.parameter_default_ids.value',
                 'command_ids.command_id.parameter_default_ids.bash_placeholder',
                 'command_ids.command_id.required_check_ids',
                 'command_ids.command_id.required_check_ids.template',
                 'command_ids.command_id.required_check_ids.name',
                 'command_ids.command_id.required_check_ids.active',
                 'command_ids.command_id.required_check_ids.command_type',
                 'command_ids.command_id.required_check_ids.check_sequence',
                 'command_ids.command_id.required_check_ids.parameter_ids.value',
                 'command_ids.command_id.required_check_ids.parameter_ids.bash_placeholder',
                 'command_ids.command_id.required_check_ids.parameter_ids.server_id',
                 'command_ids.command_id.required_check_ids.parameter_default_ids.value',
                 'command_ids.command_id.required_check_ids.parameter_default_ids.bash_placeholder',
                 'target_ids.server_id.database_name', 'target_ids.server_id.odoo_python_path',
                 'target_ids.server_id.odoo_config_path', 'target_ids.server_id.odoo_server_path',
                 'target_ids.server_id.odoo_log_path')
    def _compute_commands_update_available(self):
        admin = self.env.user.has_group('ab_deploy.group_administrator')
        for request in self:
            available = False
            if admin and request.state == 'approved':
                targets = request._command_update_targets()
                if targets:
                    try:
                        available = bool(targets._revision_proposals(lock=False))
                    except (UserError, ValidationError):
                        # Show the action so the administrator can inspect rendering errors.
                        available = True
            request.commands_update_available = available

    def _check_revision_admin(self):
        self.ensure_one()
        self._require_role('administrator')
        self._lock()
        if self.state != 'approved':
            raise UserError(_('Script updates require an approved deployment request.'))
        if self._pending_revision():
            raise UserError(_('Cancel the existing pending script revision before preparing a new update.'))

    def _command_update_proposals(self):
        self._check_revision_admin()
        targets = self._command_update_targets()
        proposals = targets._revision_proposals()
        if not proposals:
            if self.request_purpose == 'health':
                raise UserError(_('No changed commands were found for idle health collection servers.'))
            raise UserError(_('No changed commands were found for Delayed or Failed servers.'))
        return proposals

    def _command_update_targets(self):
        return self.target_ids.filtered(lambda target: target._can_update_commands())

    def action_update_commands(self):
        proposals = self._command_update_proposals()
        wizard = self.env['ab_deploy_script_update']._open(self, proposals)
        return {'type': 'ir.actions.act_window', 'name': _('Update Commands'),
                'res_model': wizard._name, 'res_id': wizard.id, 'view_mode': 'form', 'target': 'new'}

    def _pending_revision(self):
        return self.env['ab_deploy_script_revision'].sudo().search(
            fields.Domain('request_id', 'in', self.ids) & fields.Domain('state', '=', 'pending'))


class DeployTargetRevisions(models.Model):
    _inherit = 'ab_deploy_target'

    revision_id = fields.Many2one('ab_deploy_script_revision', string='Script Revision', readonly=True, copy=False, ondelete='restrict')

    def _can_update_commands(self):
        self.ensure_one()
        return self._health_repeat_eligible() if self.request_id.request_purpose == 'health' else self.deployment_status in ('delayed', 'failed')

    @api.model_create_multi
    def create(self, vals_list):
        return super(DeployTargetRevisions, self.with_context(default_revision_id=False)).create(vals_list)

    def _pending_revision_targets(self):
        return self.request_id._pending_revision().line_ids.target_id & self.sudo()

    def _validate_dependencies(self):
        if self._pending_revision_targets():
            raise UserError(_('Cancel the existing pending script revision before queueing or retrying these servers.'))
        if self._commands_need_update():
            raise UserError(_('Commands have changed or are invalid. An administrator must confirm Update Commands before deploying these servers.'))
        return super()._validate_dependencies()

    def _commands_need_update(self):
        """Check the catalog under locks without requiring a revision-eligible state."""
        targets = self.sudo()
        commands = targets.request_id.command_ids.filtered(lambda line: not line.parent_line_id).command_id.with_context(active_test=False)
        commands.sorted('id')._lock()
        commands.required_check_ids.sorted('id')._lock()
        try:
            return bool(targets._revision_proposals(lock=False))
        except (UserError, ValidationError):
            # Invalid catalog edits must never allow the old approved script to launch.
            return True

    def _check_revision_eligible(self):
        self.check_access('read')
        self.request_id.sorted('id')._lock()
        self.server_id.sorted('id')._lock()
        self.sorted('id')._lock()
        self.job_ids.sorted('id')._lock()
        if not self or any(t.request_id.state != 'approved' or not t._can_update_commands() for t in self):
            if self.filtered(lambda target: target.request_id.request_purpose == 'health'):
                raise UserError(_('Select only idle health collection servers from an approved request.'))
            raise UserError(_('Select only Delayed or Failed servers from an approved request.'))
        runs = self.env['ab_deploy_run'].sudo().search(fields.Domain('job_ids', 'in', self.job_ids.ids))
        if any(run.queue_job_id.state in ACTIVE_QUEUE for run in runs):
            raise UserError(_('Wait for active queue runs on the selected servers to finish before updating scripts.'))

    def _revision_proposals(self, lock=True):
        """Build current catalog scripts without editing approved command rows."""
        if lock:
            self.request_id.sorted('id')._lock()
            self.server_id.sorted('id')._lock()
            self.sorted('id')._lock()
            self.job_ids.sorted('id')._lock()
        roots = self.request_id.command_ids.filtered(lambda line: not line.parent_line_id).sorted(
            lambda line: (line.execution_sequence, line.id))
        commands = roots.command_id.with_context(active_test=False)
        if lock:
            commands.sorted('id')._lock()
        checks = commands.with_context(active_test=False).required_check_ids
        if lock:
            checks.sorted('id')._lock()
        for command in commands:
            required = command.with_context(active_test=False).required_check_ids
            if command.command_type == 'action' and (not required or any(check.command_type != 'check' for check in required)):
                raise ValidationError(_('The updated script must include valid required post-deployment checks.'))
            if command.command_type == 'check' and required:
                raise ValidationError(_('The updated script must include valid required post-deployment checks.'))
        if any(not command.active for command in commands | checks):
            raise ValidationError(_('Select active commands before requesting approval.'))
        if any(line.command_type != line.command_id.command_type for line in roots):
            raise ValidationError(_('A command type changed. Create a new deployment request to change command types.'))
        health_command_ids = set((commands | checks).filtered('collect_health_report').ids)
        proposals = []
        for target in self:
            catalog = []
            for line in roots.filtered(lambda line: line.request_id == target.request_id):
                command = line.command_id
                linked = command.required_check_ids.sorted(lambda check: (check.check_sequence, check.id))
                catalog.append({'name': command.with_context(lang='en_US').name,
                    'bash': command._resolve_server_script(target.server_id), 'command_type': command.command_type,
                    'sequence': line.sequence, 'line_id': line.id, 'command_id': command.id,
                    'parent_line_id': False, 'required_check_ids': linked.ids})
                for check in linked:
                    catalog.append({'name': check.with_context(lang='en_US').name,
                        'bash': check._resolve_server_script(target.server_id), 'command_type': 'check',
                        'sequence': check.check_sequence, 'line_id': 'check:%s:%s' % (line.id, check.id),
                        'command_id': check.id, 'parent_line_id': line.id, 'required_check_ids': []})
            if not any(c['command_type'] == 'check' for c in catalog) or not self._valid_check_blocks(catalog):
                raise ValidationError(_('The updated script must include valid required post-deployment checks.'))
            snapshot = copy.deepcopy(target.snapshot)
            health_collection = snapshot.get('request_purpose') == 'health'
            if health_collection:
                if any(c['command_type'] != 'check' or c['command_id'] not in health_command_ids for c in catalog):
                    raise ValidationError(_('Health collection accepts only health-report check commands.'))
                catalog = [dict(command, collect_health_report=True) for command in catalog]
            snapshot.update(commands=catalog, check_policy_version=2)
            script = engine.render(catalog, health_collection)
            if script == target.script:
                continue
            old_commands = (target.snapshot or {}).get('commands', [])
            old = {(c.get('parent_line_id'), c.get('command_id')): c for c in old_commands}
            new = {(c.get('parent_line_id'), c.get('command_id')): c for c in catalog}
            changed = sorted({c['name'] for key, c in new.items() if key not in old or c.get('bash') != old[key].get('bash') or c.get('name') != old[key].get('name')}
                             | {c['name'] for key, c in old.items() if key not in new})
            proposals.append({'target_id': target.id, 'before_script': target.script,
                'before_hash': target.script_hash, 'before_snapshot': target.snapshot,
                'baseline_job_id': target.job_ids.sorted('id', reverse=True)[:1].id or False,
                'after_script': script, 'after_hash': engine.checksum(script), 'after_snapshot': snapshot,
                'changed_commands': ', '.join(changed),
                'script_diff': ''.join(difflib.unified_diff((target.script or '').splitlines(True), script.splitlines(True),
                                                         fromfile='approved', tofile='proposed'))})
        if lock and proposals:
            self.browse([row['target_id'] for row in proposals])._check_revision_eligible()
        return proposals

    def _retry_job(self):
        self.ensure_one()
        latest = self.job_ids.sorted('id', reverse=True)[:1]
        if latest.state == 'failed' and self.revision_id and latest.execution_revision_id != self.revision_id:
            return latest
        return super()._retry_job()

    @api.depends('job_ids.state', 'job_ids.failure_kind', 'revision_id', 'job_ids.execution_revision_id')
    def _compute_selection_eligible(self):
        super()._compute_selection_eligible()


class DeployJobSnapshots(models.Model):
    _inherit = 'ab_deploy_job'

    execution_script = fields.Text(string='Frozen Script', readonly=True, copy=False)
    execution_script_hash = fields.Char(string='Frozen Script SHA-256', readonly=True, copy=False)
    execution_snapshot = fields.Json(string='Frozen Execution Settings', readonly=True, copy=False)
    execution_revision_id = fields.Many2one('ab_deploy_script_revision', string='Script Revision', readonly=True, copy=False, ondelete='restrict')
    script_for_review = fields.Text(string='Execution Script', compute='_compute_script_for_review')
    can_retry_revised = fields.Boolean(compute='_compute_can_retry_revised')

    @api.depends('state', 'execution_revision_id', 'target_id.revision_id', 'target_id.job_ids')
    def _compute_can_retry_revised(self):
        for job in self:
            job.can_retry_revised = job.state == 'failed' and job._uses_revised_script() and job.target_id._retry_job() == job

    @api.depends('execution_script', 'execution_snapshot', 'target_id.script')
    def _compute_script_for_review(self):
        for job in self:
            job.script_for_review = job._execution_values()['script']

    def _execution_values(self):
        self.ensure_one()
        if self.execution_snapshot:
            return {'script': self.execution_script, 'script_hash': self.execution_script_hash, 'snapshot': self.execution_snapshot}
        return {'script': self.target_id.script, 'script_hash': self.target_id.script_hash, 'snapshot': self.target_id.snapshot}

    def _preserve_execution(self):
        for job in self.filtered(lambda job: not job.execution_snapshot):
            values = job._execution_values()
            super(DeployJob, job.sudo()).write({'execution_script': values['script'],
                'execution_script_hash': values['script_hash'], 'execution_snapshot': values['snapshot'],
                'execution_revision_id': job.target_id.revision_id.id})

    def _uses_revised_script(self):
        self.ensure_one()
        return bool(self.target_id.revision_id and self.execution_revision_id != self.target_id.revision_id)


class DeployScriptRevision(models.Model):
    _name = 'ab_deploy_script_revision'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Script Revision'
    _order = 'id desc'

    name = fields.Char(string='Revision', required=True, readonly=True)
    request_id = fields.Many2one('ab_deploy_request', required=True, readonly=True, ondelete='restrict', index=True)
    reason = fields.Text(string='Update Reason', required=True, readonly=True)
    state = fields.Selection([('pending', 'Pending Approval'), ('approved', 'Approved'), ('rejected', 'Rejected'),
                              ('cancelled', 'Cancelled')], default='approved', required=True, readonly=True)
    submitted_by = fields.Many2one('res.users', readonly=True, required=True)
    submitted_at = fields.Datetime(readonly=True, required=True)
    decided_by = fields.Many2one('res.users', readonly=True)
    decided_at = fields.Datetime(readonly=True)
    decision_note = fields.Text(string='Decision Reason', readonly=True)
    activity_id = fields.Many2one('mail.activity', readonly=True, ondelete='set null')
    line_ids = fields.One2many('ab_deploy_script_revision_line', 'revision_id', string='Updated Servers', readonly=True)
    can_cancel = fields.Boolean(compute='_compute_permissions')

    @api.depends_context('uid')
    @api.depends('state', 'submitted_by', 'request_id.developer_id', 'request_id.approver_id')
    def _compute_permissions(self):
        admin = self.env.user.has_group('ab_deploy.group_administrator')
        for revision in self:
            revision.can_cancel = revision.state == 'pending' and admin

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Script revisions can only be created through Update Commands.'))

    def write(self, vals):
        raise AccessError(_('Script revision snapshots and workflow fields cannot be edited.'))

    def unlink(self):
        raise AccessError(_('Script revision history cannot be deleted.'))

    def _note(self, event):
        self.ensure_one()
        # Escaped, translated summaries only; full scripts remain in revision views.
        body = Markup('<p>%s</p><p>%s</p><p>%s</p><p>%s</p><p>%s</p><p>%s</p>') % (
            event, self._get_html_link(),
            _('Servers: %s', ', '.join(self.line_ids.target_id.server_id.mapped('name'))),
            _('Updated commands: %s', '; '.join(dict.fromkeys(filter(None, self.line_ids.mapped('changed_commands'))))),
            _('Reason: %s', self.reason),
            _('Submitted by %(submitter)s; action by %(actor)s. %(decision)s',
              submitter=self.submitted_by.name, actor=self.env.user.name, decision=self.decision_note or ''))
        self.request_id.message_post(body=body, subtype_xmlid='mail.mt_note')

    @api.model
    def _confirm(self, request, reason, proposals):
        request._check_revision_admin()
        if not (reason or '').strip():
            raise UserError(_('Enter an update reason before confirming.'))
        # Regenerate under locks: neither catalog edits nor target changes may
        # silently change what the administrator reviewed.
        current = request._command_update_proposals()
        if current != proposals:
            raise UserError(_('Commands or server executions changed since preview. Close this dialog and reopen Update Commands.'))
        targets = self.env['ab_deploy_target'].browse([row['target_id'] for row in current])
        number = self.sudo().search_count(fields.Domain('request_id', '=', request.id)) + 1
        now = fields.Datetime.now()
        revision = super(DeployScriptRevision, self).create({'name': '%s / R%s' % (request.name, number),
            'request_id': request.id, 'reason': reason.strip(), 'submitted_by': self.env.uid,
            'submitted_at': now, 'state': 'approved', 'line_ids': [],
            'decided_by': self.env.uid, 'decided_at': now, 'decision_note': False, 'activity_id': False})
        Line = self.env['ab_deploy_script_revision_line']
        super(DeployScriptRevisionLine, Line).create([dict(row, revision_id=revision.id) for row in current])
        targets.job_ids._preserve_execution()
        for line in revision.line_ids:
            super(DeployTarget, line.target_id.sudo()).write({'script': line.after_script, 'script_hash': line.after_hash,
                'snapshot': line.after_snapshot, 'revision_id': revision.id, 'job_key': uuid.uuid4().hex})
        targets._validate_check_snapshot()
        revision._note(_('Commands updated and approved.'))
        return revision

    def action_cancel(self):
        self.ensure_one()
        self.check_access('write')
        self.request_id._require_role('administrator')
        self.request_id._lock()
        self._lock()
        if self.state != 'pending':
            raise UserError(_('Only pending script updates can be cancelled.'))
        self._finish('cancelled', _('Script update cancelled. Previously approved scripts remain available.'))
        return True

    def _finish(self, state, message):
        super(DeployScriptRevision, self).write({'state': state, 'decided_by': self.env.uid, 'decided_at': fields.Datetime.now()})
        self.activity_id.sudo().unlink()
        self._note(message)

    def _action(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'current'}


class DeployScriptRevisionLine(models.Model):
    _name = 'ab_deploy_script_revision_line'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Script Revision Server'
    _rec_name = 'target_id'

    revision_id = fields.Many2one('ab_deploy_script_revision', required=True, readonly=True, ondelete='restrict')
    request_id = fields.Many2one(related='revision_id.request_id', store=True, index=True)
    target_id = fields.Many2one('ab_deploy_target', required=True, readonly=True, ondelete='restrict')
    baseline_job_id = fields.Many2one('ab_deploy_job', readonly=True, ondelete='restrict')
    before_script = fields.Text(string='Previously Approved Script', required=True, readonly=True)
    before_hash = fields.Char(string='Previous SHA-256', required=True, readonly=True)
    before_snapshot = fields.Json(readonly=True, required=True)
    after_script = fields.Text(string='Proposed Script', required=True, readonly=True)
    after_hash = fields.Char(string='Proposed SHA-256', required=True, readonly=True)
    after_snapshot = fields.Json(readonly=True, required=True)
    changed_commands = fields.Text(string='Updated Commands', readonly=True)
    script_diff = fields.Text(string='Script Changes', readonly=True)
    _unique_target = models.Constraint('UNIQUE(revision_id, target_id)', 'A server may appear only once in a script revision.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Script revision snapshots and workflow fields cannot be edited.'))

    def write(self, vals):
        raise AccessError(_('Script revision snapshots and workflow fields cannot be edited.'))

    def unlink(self):
        raise AccessError(_('Script revision history cannot be deleted.'))
