"""On-demand health collection using the existing deployment execution records."""
import base64
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from ..runner import health

HEALTH = [('healthy', 'Healthy'), ('warning', 'Warning'), ('critical', 'Critical'), ('unknown', 'Unknown')]
COLLECTION = [('collecting', 'Collecting'), ('complete', 'Complete'), ('incomplete', 'Incomplete'), ('failed', 'Failed')]


class DeployHealthCommand(models.Model):
    _inherit = 'ab_deploy_command'

    collect_health_report = fields.Boolean(string='Collect Health Report',
        help='For check commands that emit one marked health JSON block. Output and diagnostics must not contain secrets.')

    @api.constrains('collect_health_report', 'command_type')
    def _check_health_command(self):
        if any(command.collect_health_report and command.command_type != 'check' for command in self):
            raise ValidationError(_('Only check commands can collect health reports.'))


class DeployHealthRequest(models.Model):
    _inherit = 'ab_deploy_request'

    request_purpose = fields.Selection([('deployment', 'Deployment'), ('health', 'Health Collection')],
                                      required=True, default='deployment', tracking=True)
    health_report_ids = fields.One2many('ab_deploy_health_report', 'request_id', string='Health Reports', readonly=True, copy=False)

    def action_run_health_checks(self):
        self.ensure_one()
        self._require_role('executor')
        if self.request_purpose != 'health':
            raise UserError(_('Run Selected Health Checks is only available for health collection requests.'))
        return self.action_queue()

    def _selected_targets(self):
        self.ensure_one()
        if self.request_purpose != 'health':
            return super()._selected_targets()
        if self.state != 'approved':
            raise UserError(_('Only approved requests can queue selected servers.'))
        self._validate_executor()
        targets = self.target_ids.filtered('deploy')
        if not targets:
            raise UserError(_('Select at least one server for health collection.'))
        if any(not target._health_repeat_eligible() for target in targets):
            raise UserError(_('Finish or resolve earlier health executions and collect their remaining output before running these servers again.'))
        return targets

    def _validate_health_commands(self):
        for request in self.filtered(lambda request: request.request_purpose == 'health'):
            if not request.command_ids or any(line.command_id.command_type != 'check' or not line.command_id.collect_health_report for line in request.command_ids):
                raise ValidationError(_('Health collection accepts only health-report check commands.'))


class DeployHealthTarget(models.Model):
    _inherit = 'ab_deploy_target'

    def _health_repeat_eligible(self):
        self.ensure_one()
        return self.request_id.request_purpose == 'health' and self.request_id.state == 'approved' and not any(
            job.state in ('queued', 'running', 'unknown') or job._needs_logs() for job in self.job_ids)

    def _validate_health_repeat(self):
        self.server_id.sorted('id')._lock()
        self.sorted('id')._lock()
        jobs = self.job_ids
        jobs.sorted('id')._lock()
        if any(not target._health_repeat_eligible() for target in self):
            raise UserError(_('Finish or resolve earlier health executions and collect their remaining output before running these servers again.'))
        jobs._check_not_busy()

    @api.depends('request_id.request_purpose', 'request_id.state', 'job_ids.state',
                 'job_ids.command_log_status', 'job_ids.odoo_log_status',
                 'job_ids.launch_intent', 'job_ids.started_at', 'job_ids.attempt_ids')
    def _compute_selection_eligible(self):
        super()._compute_selection_eligible()
        for target in self.filtered(lambda target: target.request_id.request_purpose == 'health'):
            target.selection_eligible = target._health_repeat_eligible()

    def _freeze(self):
        self.request_id.command_ids.command_id.sorted('id')._lock()
        self.request_id._validate_health_commands()
        return super()._freeze()

    def _validate_check_snapshot(self):
        result = super()._validate_check_snapshot()
        for target in self:
            snapshot = target.snapshot or {}
            is_health = snapshot.get('request_purpose') == 'health'
            if is_health != (target.request_id.request_purpose == 'health') or (is_health and any(
                    command.get('command_type') != 'check' or not command.get('collect_health_report')
                    for command in snapshot.get('commands', []))):
                raise ValidationError(_('The approved health collection settings are missing or inconsistent.'))
        return result


class DeployHealthJob(models.Model):
    _inherit = 'ab_deploy_job'

    health_report_ids = fields.One2many('ab_deploy_health_report', 'job_id', string='Health Reports', readonly=True, copy=False)
    health_collection_status = fields.Selection(COLLECTION, compute='_compute_health_status', string='Health Collection Status')
    reported_health = fields.Selection(HEALTH, compute='_compute_health_status', string='Reported Health')

    @api.depends('health_report_ids.collection_status', 'health_report_ids.health_status')
    def _compute_health_status(self):
        for job in self:
            report = job.health_report_ids[:1]
            job.health_collection_status = report.collection_status
            job.reported_health = report.health_status

    @api.model
    def _make(self, targets, retry_of=None):
        if not retry_of:
            targets.filtered(lambda target: target.request_id.request_purpose == 'health')._validate_health_repeat()
        jobs = super()._make(targets, retry_of=retry_of)
        self.env['ab_deploy_health_report']._create_for_jobs(jobs)
        return jobs

    def _set(self, vals):
        result = super()._set(vals)
        if {'state', 'command_log_status', 'command_log_offset', 'failure_kind', 'started_at', 'finished_at'} & vals.keys():
            self.sudo().health_report_ids._refresh()
        return result


class DeployHealthServer(models.Model):
    _inherit = 'ab_deploy_server'

    latest_health_report_id = fields.Many2one('ab_deploy_health_report', compute='_compute_latest_health',
                                             string='Latest Health Report', compute_sudo=False)
    latest_health = fields.Selection(HEALTH, compute='_compute_latest_health', string='Latest Health', compute_sudo=False)
    last_health_collection_at = fields.Datetime(compute='_compute_latest_health', string='Last Health Collection', compute_sudo=False)

    @api.depends_context('uid')
    def _compute_latest_health(self):
        reports = self.env['ab_deploy_health_report'].search(fields.Domain('server_id', 'in', self.ids),
                                                           order='started_at desc, id desc')
        latest = {}
        for report in reports:
            latest.setdefault(report.server_id.id, report)
        for server in self:
            report = latest.get(server.id, self.env['ab_deploy_health_report'])
            server.latest_health_report_id = report
            server.latest_health = report.health_status
            server.last_health_collection_at = report.finished_at


class DeployHealthReport(models.Model):
    _name = 'ab_deploy_health_report'
    _description = 'Deployment Health Report'
    _order = 'started_at desc, id desc'
    _rec_name = 'job_id'

    job_id = fields.Many2one('ab_deploy_job', required=True, readonly=True, ondelete='restrict', index=True)
    request_id = fields.Many2one(related='job_id.request_id', store=True, index=True)
    target_id = fields.Many2one(related='job_id.target_id', store=True)
    server_id = fields.Many2one(related='job_id.server_id', store=True, index=True)
    started_at = fields.Datetime(string='Collection Started', required=True, readonly=True, index=True)
    finished_at = fields.Datetime(string='Collection Finished', readonly=True)
    collection_status = fields.Selection(COLLECTION, default='collecting', required=True, readonly=True, index=True)
    health_status = fields.Selection(HEALTH, default='unknown', required=True, readonly=True, index=True)
    check_count = fields.Integer(string='Checks', readonly=True)
    warning_count = fields.Integer(string='Warnings', readonly=True)
    critical_count = fields.Integer(string='Critical Checks', readonly=True)
    unknown_count = fields.Integer(string='Unknown Checks', readonly=True)
    payload = fields.Json(string='Health JSON', readonly=True)
    collection_error = fields.Text(string='Collection Error', readonly=True)
    source_revision = fields.Char(readonly=True, groups='ab_deploy.group_administrator')
    check_details = fields.Text(string='Check Details', compute='_compute_preview')
    json_preview = fields.Text(string='JSON Preview', compute='_compute_preview')
    json_download = fields.Binary(string='Download JSON', compute='_compute_preview', attachment=False)
    json_filename = fields.Char(compute='_compute_preview')

    _unique_job = models.Constraint('UNIQUE(job_id)', 'An execution can have only one health report.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Health reports can only be created by the execution workflow.'))

    def write(self, vals):
        raise AccessError(_('Health reports cannot be modified manually.'))

    def unlink(self):
        raise AccessError(_('Health report history cannot be deleted.'))

    @api.depends('payload', 'job_id.job_key')
    def _compute_preview(self):
        labels = dict(self._fields['health_status']._description_selection(self.env))
        for report in self:
            payload = report.payload or {}
            report.check_details = '\n\n'.join('%s — %s\n%s' % (
                row['id'], labels.get(row['status'], row['status']), row.get('details', ''))
                for row in payload.get('checks', []))
            report.json_preview = json.dumps(payload, ensure_ascii=False, indent=2)
            report.json_download = base64.b64encode(report.json_preview.encode())
            report.json_filename = f'health-{report.job_id.job_key}.json'

    def action_download_json(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_url', 'url': f'/web/content/ab_deploy_health_report/{self.id}/json_download/{self.json_filename}?download=true', 'target': 'download'}

    @api.model
    def _create_for_jobs(self, jobs):
        values = []
        for job in jobs:
            if job._execution_values()['snapshot'].get('request_purpose') == 'health':
                values.append({'job_id': job.id, 'started_at': job.started_at or job.create_date,
                               'payload': {'schema_version': 1, 'checks': []}})
        if values:
            super(DeployHealthReport, self.sudo()).create(values)
            jobs.server_id.invalidate_recordset(['latest_health_report_id', 'latest_health', 'last_health_collection_at'])

    def _refresh(self):
        for report in self:
            job = report.job_id
            revision = f'{job.state}:{job.command_log_status}:{job.command_log_offset}:{job.failure_kind}:{job.started_at}:{job.finished_at}'
            if report.source_revision == revision:
                continue
            done = job.state in ('succeeded', 'failed', 'cancelled', 'manually_resolved')
            interrupted = job.state == 'unknown' or job.command_log_status == 'error'
            if not done and not interrupted:
                started = job.started_at or job.create_date
                if report.collection_status != 'collecting' or report.started_at != started:
                    super(DeployHealthReport, report).write({'collection_status': 'collecting', 'started_at': started, 'finished_at': False, 'source_revision': revision})
                    job.server_id.invalidate_recordset(['latest_health_report_id', 'latest_health', 'last_health_collection_at'])
                continue
            commands = job._execution_values()['snapshot']['commands']
            parts = job.command_log_part_ids.sorted(lambda part: int(part.byte_offset))
            def chunks():
                offset = 0
                for part in parts:
                    if int(part.byte_offset) != offset:
                        raise ValueError('Command log parts are not contiguous.')
                    data = base64.b64decode(part.with_context(bin_size=False).data or b'', validate=True)
                    if len(data) != part.byte_size:
                        raise ValueError('Command log part size is invalid.')
                    offset += len(data)
                    yield data
            checks, errors = health.parse(chunks(), commands, translate=self.env._)
            complete = job.command_log_status == 'done' and done and not errors and bool(checks)
            if not complete and not errors:
                message = _('Health output collection is incomplete. Resume monitoring to collect remaining output.')
                errors.append(message)
                if len(checks) >= health.MAX_CHECKS:
                    priority = {'critical': 0, 'unknown': 1, 'warning': 2, 'healthy': 3}
                    checks = sorted(checks, key=lambda row: priority[row['status']])[:health.MAX_CHECKS - 1]
                checks.append({'id': 'collection_error', 'status': 'unknown', 'details': message})
            status = 'complete' if complete else ('incomplete' if job.launch_intent or parts else 'failed')
            started = job.started_at or job.create_date
            payload = {'schema_version': 1, 'server': {'id': job.server_id.id, 'code': job.server_id.code,
                       'pharmacy_serial': job.server_id.serial, 'database_serial': job.server_id.db_serial},
                       'execution_key': job.job_key, 'request_id': job.request_id.id,
                       'started_at': fields.Datetime.to_string(started),
                       'finished_at': fields.Datetime.to_string(job.finished_at) if done else None,
                       'timezone': 'UTC', 'checks': checks}
            super(DeployHealthReport, report).write({'started_at': started, 'finished_at': job.finished_at if done else False,
                'collection_status': status, 'health_status': health.overall(checks), 'payload': payload,
                'collection_error': '\n'.join(errors) or False, 'source_revision': revision,
                'check_count': len(checks), 'warning_count': sum(row['status'] == 'warning' for row in checks),
                'critical_count': sum(row['status'] == 'critical' for row in checks),
                'unknown_count': sum(row['status'] == 'unknown' for row in checks)})
            # Server summaries are nonstored and access-filtered; invalidate cached
            # values after a report changes in the current transaction.
            job.server_id.invalidate_recordset(['latest_health_report_id', 'latest_health', 'last_health_collection_at'])
