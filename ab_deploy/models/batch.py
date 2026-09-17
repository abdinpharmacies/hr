"""Durable batch execution; only the main thread ever accesses the ORM."""
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError, LockError
from odoo.modules.registry import Registry
from psycopg2 import OperationalError
from odoo.service.model import PG_CONCURRENCY_ERRORS_TO_RETRY

from ..runner import engine, threaded

BATCH_SECONDS = 3600

STAGES = [
        ('waiting', 'Waiting'), ('connecting', 'Connecting'), ('ssh_connected', 'SSH Connected'),
        ('script_created', 'Script Created'), ('tmux_started', 'Tmux Started'),
        ('script_running', 'Script Running'), ('finished', 'Finished'),
        ('needs_check', 'Status Needs Checking')]

ACTIVE_QUEUE = ('pending', 'enqueued', 'started', 'wait_dependencies')


class DeployAttempt(models.Model):
    _name = 'ab_deploy_attempt'
    _description = 'Deployment Connection Attempt'
    _order = 'id desc'

    job_id = fields.Many2one('ab_deploy_job', required=True, readonly=True, ondelete='restrict')
    run_id = fields.Many2one('ab_deploy_run', required=True, readonly=True, ondelete='restrict')
    started_at = fields.Datetime(default=fields.Datetime.now, readonly=True)
    finished_at = fields.Datetime(readonly=True)
    stage = fields.Selection(STAGES, readonly=True)
    outcome = fields.Selection([('ssh', 'SSH Failure'), ('setup', 'Setup Failure'), ('script', 'Script Failure'),
        ('timeout', 'Monitoring Timeout'), ('monitor', 'Monitoring Interrupted'), ('succeeded', 'Succeeded'),
        ('failed', 'Failed'), ('unknown', 'Status Unknown'), ('interrupted', 'Interrupted')], readonly=True)
    detail = fields.Text(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Execution history is managed by the deployment workflow.'))

    def write(self, vals):
        raise AccessError(_('Execution history cannot be modified manually.'))

    def unlink(self):
        raise AccessError(_('Execution history cannot be deleted.'))

    @api.model
    def _start(self, job, run):
        return super(DeployAttempt, self.sudo()).create({'job_id': job.id, 'run_id': run.id, 'stage': job.stage})

    def _update(self, vals):
        return super(DeployAttempt, self.sudo()).write(vals)


class DeployJobProgress(models.Model):
    _inherit = 'ab_deploy_job'

    stage = fields.Selection(STAGES, default='waiting', readonly=True)
    failure_kind = fields.Selection([
        ('ssh', 'SSH Failure'), ('setup', 'Setup Failure'), ('script', 'Script Failure'),
        ('timeout', 'Monitoring Timeout'), ('monitor', 'Monitoring Interrupted')], readonly=True)
    launch_intent = fields.Boolean(readonly=True)
    command_log_offset = fields.Char(default='0', readonly=True)
    command_log_status = fields.Selection([('pending', 'Collecting'), ('done', 'Collected'), ('error', 'Collection Error')], default='pending', readonly=True)
    command_log_part_ids = fields.One2many('ab_deploy_log_part', 'job_id', domain=[('kind', '=', 'command')], readonly=True, string='Command Log Parts')
    attempt_ids = fields.One2many('ab_deploy_attempt', 'job_id', readonly=True, string='Connection Attempts')
    cancelled_by_id = fields.Many2one('res.users', readonly=True, string='Cancelled By')
    superseded_by_id = fields.Many2one('ab_deploy_request', readonly=True, string='Replaced By')
    waiting_for_ids = fields.Many2many('ab_deploy_job', compute='_compute_waiting', string='Waiting for Executions')

    def _audit_values(self, values):
        # Full output lives in immutable parts; avoid duplicating 64 KiB previews
        # into the audit table on every two-second heartbeat.
        return super()._audit_values({key: value for key, value in values.items()
                                     if key not in ('log_tail', 'odoo_log_preview')})

    @api.depends('request_id.name', 'server_id.name')
    def _compute_display_name(self):
        for job in self:
            job.display_name = f'{job.request_id.name} / {job.server_id.name}'

    @api.depends('state', 'server_id')
    def _compute_waiting(self):
        older = self.sudo().search(fields.Domain('server_id', 'in', self.server_id.ids)
                                  & fields.Domain('state', 'in', ['queued', 'running', 'unknown']), order='id')
        for job in self:
            job.waiting_for_ids = older.filtered(lambda o: o.server_id == job.server_id and o.id != job.id
                and (o.state in ('running', 'unknown') or o.id < job.id)) if job.state == 'queued' else False

    def action_retry_ssh(self):
        requests = self.request_id
        requests._require_role('executor')
        requests.sorted('id')._lock()
        self.sorted('id')._lock()
        if any(j.failure_kind != 'ssh' or j.state not in ('failed', 'unknown') for j in self):
            raise UserError(_('Only SSH failures can be retried. Other command failures require a new deployment.'))
        self._check_not_busy()
        for job in self:
            job._set({'state': 'unknown' if job.launch_intent else 'queued', 'error': False,
                      'stage': 'needs_check' if job.launch_intent else 'waiting', 'finished_at': False})
        for request in requests:
            request._schedule_run(self.filtered(lambda j: j.request_id == request), retry=True)
        return True

    def action_resume(self):
        self.request_id._require_role('executor')
        self.request_id.sorted('id')._lock()
        self._check_not_busy()
        if any(j.state not in ('queued', 'running', 'unknown') and not j._needs_logs() for j in self):
            raise UserError(_('Resume is for unfinished executions or incomplete logs only.'))
        for request in self.request_id:
            request._schedule_run(self.filtered(lambda j: j.request_id == request))
        return True

    def _check_not_busy(self):
        runs = self.env['ab_deploy_run'].sudo().search(fields.Domain('job_ids', 'in', self.ids))
        if any(run.queue_job_id.state in ACTIVE_QUEUE for run in runs):
            raise UserError(_('An active queue job is already handling these executions.'))

    def _needs_logs(self):
        return self.failure_kind != 'setup' and self.state in ('succeeded', 'failed') and (self.launch_intent or (self.started_at and not self.attempt_ids)) and (
            self.command_log_status != 'done' or self.odoo_log_status in ('pending', 'error'))


class DeployRequestBatch(models.Model):
    _inherit = 'ab_deploy_request'

    run_ids = fields.One2many('ab_deploy_run', 'request_id', readonly=True, string='Queue Runs')
    # Include the parent workflow fields: ordinary writes may never forge queue runs.
    _protected = {'name', 'state', 'queued', 'requested_by', 'requested_at', 'approved_by', 'approved_at',
                  'approval_activity_id', 'job_ids', 'run_ids'}

    def _schedule_run(self, jobs=None, retry=False):
        for request in self.sorted('id'):
            request._lock()
            selected = jobs if jobs is not None else request.job_ids.filtered(
                lambda j: j.state in ('queued', 'running', 'unknown') or j._needs_logs())
            selected = selected.filtered(lambda j: j.request_id == request and j.state != 'cancelled')
            active = request.run_ids.filtered(lambda r: r.queue_job_id.state in ACTIVE_QUEUE)
            selected -= active.job_ids
            if selected:
                run = self.env['ab_deploy_run']._make(request, selected)
                pending = run.sudo().with_delay(channel='root.deployment', identity_key=f'ab_deploy:run:{run.id}',
                    max_retries=5, description=_('%s: SSH retry', request.name) if retry else _('%s: execute and monitor', request.name))._execute()
                run._update({'queue_job_id': pending.db_record().id})
                selected._set({'queue_job_id': pending.db_record().id})

    def _coordinate(self, generation=None, phase=None):
        """One-time handoff for queue records serialized before the batch upgrade."""
        self._schedule_run()

    def action_resume(self):
        self._require_role('executor')
        self._schedule_run()
        return True

    def action_retry_ssh(self):
        self._require_role('executor')
        failed = self.job_ids.filtered(lambda j: j.failure_kind == 'ssh' and j.state in ('failed', 'unknown'))
        if not failed:
            raise UserError(_('There are no SSH failures to retry.'))
        return failed.action_retry_ssh()


class DeployRun(models.Model):
    _name = 'ab_deploy_run'
    _description = 'Deployment Queue Run'
    _order = 'id desc'
    _rec_name = 'request_id'

    request_id = fields.Many2one('ab_deploy_request', required=True, readonly=True, ondelete='restrict')
    job_ids = fields.Many2many('ab_deploy_job', readonly=True, string='Executions')
    queue_job_id = fields.Many2one('queue.job', readonly=True, ondelete='set null')
    queue_state = fields.Selection(related='queue_job_id.state', string='Queue State')
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    requested_by_id = fields.Many2one('res.users', readonly=True, string='Requested By')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Queue runs can only be created by deployment actions.'))

    def write(self, vals):
        raise AccessError(_('Queue runs cannot be modified manually.'))

    def unlink(self):
        raise AccessError(_('Queue runs cannot be deleted.'))

    @api.model
    def _make(self, request, jobs):
        return super(DeployRun, self.sudo()).create({'request_id': request.id, 'job_ids': [fields.Command.set(jobs.ids)],
                                                  'requested_by_id': self.env.uid})

    def _update(self, vals):
        return super(DeployRun, self.sudo()).write(vals)

    def _claim(self, excluded, limit):
        payloads = []
        blockers = self.env['ab_deploy_job'].search(
            fields.Domain('server_id', 'in', self.job_ids.filtered(lambda j: j.state == 'queued').server_id.ids)
            & fields.Domain('state', 'in', ['running', 'unknown']))
        # A waiting batch can observe stale blockers without replaying their commands
        # or occupying its channel while a separate recovery task waits behind it.
        for job in (self.job_ids | blockers).sorted('id'):
            if job.id in excluded or len(payloads) == limit:
                continue
            job.server_id._lock()
            job._lock()
            if job not in self.job_ids and any(a.run_id != self and a.run_id.queue_job_id.state == 'started'
                                               for a in job.attempt_ids.filtered(lambda a: not a.finished_at)):
                continue
            if job.state == 'cancelled' or (job.state in ('failed', 'succeeded') and not job._needs_logs()):
                excluded.add(job.id)
                continue
            if job.state == 'queued':
                if job.request_id.state != 'approved':
                    job._set({'state': 'cancelled'})
                    excluded.add(job.id)
                    continue
                blockers = self.env['ab_deploy_job'].search(
                    fields.Domain('server_id', '=', job.server_id.id) & fields.Domain('id', '!=', job.id)
                    & (fields.Domain('state', 'in', ['running', 'unknown'])
                       | (fields.Domain('state', '=', 'queued') & fields.Domain('id', '<', job.id))))
                if blockers:
                    continue
                if not job.server_id.active or job.server_id.maintenance_mode or engine.checksum(job.target_id.script or '') != job.target_id.script_hash:
                    job._set({'state': 'failed', 'failure_kind': 'setup', 'error': _('Server unavailable or approved script invalid.')})
                    excluded.add(job.id)
                    continue
            # Older executions have no intent field but must never be relaunched.
            intent = job.launch_intent or (not job.attempt_ids and job.state in ('running', 'unknown', 'succeeded', 'failed'))
            vals = {'stage': 'needs_check' if intent else 'connecting', 'launch_intent': intent}
            if job.state not in ('succeeded', 'failed'):
                vals.update(state='running', started_at=job.started_at or fields.Datetime.now(), error=False)
            if job.command_log_status == 'error':
                vals['command_log_status'] = 'pending'
            if job.odoo_log_status == 'error':
                vals.update(odoo_log_status='pending', odoo_log_failures=0)
            job._set(vals)
            job.attempt_ids.filtered(lambda a: not a.finished_at and (
                a.run_id == self or a.run_id.queue_job_id.state not in ACTIVE_QUEUE))._update(
                    {'outcome': 'interrupted', 'finished_at': fields.Datetime.now()})
            attempt = self.env['ab_deploy_attempt']._start(job, self)
            snapshot = job.target_id.snapshot
            payloads.append({'id': job.id, 'attempt': attempt.id, 'alias': snapshot['ssh_alias'],
                'key': job.job_key, 'script': job.target_id.script, 'digest': job.target_id.script_hash,
                'capture': snapshot.get('odoo_log'), 'timeout': snapshot.get('timeout', 600), 'intent': intent,
                'command_offset': int(job.command_log_offset or '0'), 'odoo_offset': int(job.odoo_log_offset or '0')})
        return payloads

    def _event(self, event, attempt_id):
        job = self.env['ab_deploy_job'].browse(event['id'])
        job._lock()
        attempt = self.env['ab_deploy_attempt'].browse(attempt_id)
        kind = event['kind']
        if job.state == 'cancelled':
            return False
        if kind == 'intent':
            job._set({'launch_intent': True})
            return True
        if kind == 'stage':
            job._set({'stage': event['stage'], 'last_checked_at': fields.Datetime.now()})
            attempt._update({'stage': event['stage']})
            return True
        if kind == 'failure':
            terminal = job.state in ('succeeded', 'failed')
            vals = {'error': _('SSH observation ended: %s', event.get('detail', '')), 'last_checked_at': fields.Datetime.now()}
            if not terminal:
                vals.update(state='failed' if event['failure'] == 'setup' or not event['intent'] else 'unknown', failure_kind=event['failure'], stage='finished' if event['failure'] == 'setup' or not event['intent'] else 'needs_check')
            if job.command_log_status == 'pending':
                vals['command_log_status'] = 'error'
            if job.odoo_log_status == 'pending':
                vals.update(odoo_log_status='error', odoo_log_error=_('Log download interrupted. Resume monitoring to collect remaining output.'))
            job._set(vals)
            attempt._update({'outcome': event['failure'], 'detail': event.get('detail'), 'finished_at': fields.Datetime.now()})
            return False
        report = event['report']
        vals = {'last_checked_at': fields.Datetime.now()}
        tail = report.get('log', '')[-65536:]
        if tail != (job.log_tail or ''):
            vals['log_tail'] = tail
        if report['state'] in ('succeeded', 'failed'):
            if job.state not in ('succeeded', 'failed'):
                vals.update(state=report['state'], exit_code=report['exit_code'], stage='finished', error=False,
                            failure_kind='script' if report['state'] == 'failed' else False)
        elif report['alive']:
            if job.state not in ('succeeded', 'failed'):
                vals.update(state='running', stage='script_running', error=False)
        else:
            if job.state not in ('succeeded', 'failed'):
                vals.update(state='unknown', stage='needs_check', failure_kind='monitor',
                            error=_('Remote completion is not confirmed. Resume monitoring or inspect the execution.'))
        offset = int(job.command_log_offset or '0')
        if report['command_offset'] != offset or report['command_size'] < offset:
            vals.update(command_log_status='error', error=_('Command log changed; downloaded parts were preserved.'))
        else:
            data = report['command_chunk']
            if data:
                self.env['ab_deploy_log_part']._store(job, offset, data, kind='command')
                offset += len(data)
                vals['command_log_offset'] = str(offset)
            vals['command_log_status'] = 'done' if report['state'] in ('succeeded', 'failed') and offset >= report['command_size'] else 'pending'
        job._set(vals)
        if job.odoo_log_status == 'pending':
            job._accept_log_chunk(report)
        done = job.state in ('succeeded', 'failed') and job.command_log_status in ('done', 'error') and job.odoo_log_status != 'pending'
        unknown = job.state == 'unknown'
        if done or unknown:
            attempt._update({'outcome': job.state, 'stage': job.stage, 'finished_at': fields.Datetime.now()})
        return not (done or unknown)

    def _execute(self):
        """The queue-job transaction only owns queue_job; progress uses fresh cursors."""
        self.ensure_one()
        dbname, run_id = self.env.cr.dbname, self.id

        def transaction(callback):
            for retry in range(5):
                try:
                    with Registry(dbname).cursor() as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        result = callback(env['ab_deploy_run'].browse(run_id))
                        cr.commit()
                        return result
                except (OperationalError, LockError) as exc:
                    if (not isinstance(exc, LockError) and exc.pgcode not in PG_CONCURRENCY_ERRORS_TO_RETRY) or retry == 4:
                        raise
                    time.sleep(.05 * (retry + 1))

        transaction(lambda run: run._update({'started_at': fields.Datetime.now(), 'finished_at': False}))
        deadline = time.monotonic() + BATCH_SECONDS
        events, stop = queue.Queue(maxsize=140), threading.Event()
        excluded, pending, observed = set(), {}, {}
        next_claim = 0
        pool = ThreadPoolExecutor(max_workers=70, thread_name_prefix='ab_deploy_ssh')
        try:
            while time.monotonic() < deadline:
                if time.monotonic() >= next_claim and len(pending) < 70:
                    candidates = transaction(lambda run: run._claim(excluded | set(pending) | {key for key, until in observed.items() if until > time.monotonic()}, 70 - len(pending)))
                    for payload in candidates:
                        pending[payload['id']] = (pool.submit(threaded.host, payload, events, stop, deadline), payload['attempt'])
                    next_claim = time.monotonic() + (2 if candidates else 30)
                try:
                    event = events.get(timeout=.25)
                except queue.Empty:
                    event = None
                if event:
                    attempt_id = pending[event['id']][1]
                    keep = transaction(lambda run: run._event(event, attempt_id))
                    event['ack'].put(keep)
                for job_id, (future, attempt) in list(pending.items()):
                    if future.done():
                        future.result()
                        own = transaction(lambda run: job_id in run.job_ids.ids)
                        if own:
                            excluded.add(job_id)
                        else:
                            observed[job_id] = time.monotonic() + 60
                        del pending[job_id]
                        next_claim = min(next_claim, time.monotonic())
                if not pending:
                    remaining = transaction(lambda run: bool(run.job_ids.filtered(lambda j: j.id not in excluded and
                        (j.state in ('queued', 'running', 'unknown') or j._needs_logs()))))
                    if not remaining:
                        break
        finally:
            stop.set()
            pool.shutdown(wait=True, cancel_futures=True)
            def finish(run):
                for job_id, (future, attempt_id) in pending.items():
                    job = run.env['ab_deploy_job'].browse(job_id)
                    job._lock()
                    vals = {}
                    if job.state == 'running':
                        vals.update(state='unknown', stage='needs_check', failure_kind='timeout',
                                    error=_('Observation stopped; the remote script was not terminated.'))
                    if job.command_log_status == 'pending':
                        vals['command_log_status'] = 'error'
                    if job.odoo_log_status == 'pending':
                        vals.update(odoo_log_status='error', odoo_log_error=_('Log download interrupted. Resume monitoring to collect remaining output.'))
                    if vals:
                        job._set(vals)
                    run.env['ab_deploy_attempt'].browse(attempt_id)._update({'outcome': 'interrupted', 'finished_at': fields.Datetime.now()})
                run._update({'finished_at': fields.Datetime.now()})
            transaction(finish)
