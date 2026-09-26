import subprocess
import uuid

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from ..runner import engine

TERMINAL = {'succeeded', 'failed', 'cancelled', 'manually_resolved'}


class DeployJob(models.Model):
    _name = 'ab_deploy_job'
    _inherit = 'ab_deploy_guard'
    _description = 'Deployment Job'
    _order = 'id desc'
    _rec_name = 'job_key'

    target_id = fields.Many2one('ab_deploy_target', required=True, readonly=True, ondelete='restrict')
    request_id = fields.Many2one(related='target_id.request_id', store=True, index=True)
    server_id = fields.Many2one(related='target_id.server_id', store=True, index=True)
    job_key = fields.Char(required=True, readonly=True)
    state = fields.Selection([('queued', 'Queued'), ('running', 'Running'), ('unknown', 'Unknown'),
                              ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('cancelled', 'Cancelled'),
                              ('manually_resolved', 'Manually Resolved')],
                             required=True, default='queued', readonly=True)
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    exit_code = fields.Integer(readonly=True)
    log_tail = fields.Text(string='Recent Log', readonly=True)
    error = fields.Text(readonly=True)
    resolution_note = fields.Text(readonly=True)
    manual_resolved_by_id = fields.Many2one('res.users', string='Manually Resolved By', readonly=True, copy=False)
    manual_resolved_at = fields.Datetime(string='Manually Resolved At', readonly=True, copy=False)
    manual_resolution_note = fields.Text(string='Manual Resolution Note', readonly=True, copy=False)
    manual_undo_note = fields.Text(string='Undo Resolution Reason', readonly=True, copy=False)
    queue_job_id = fields.Many2one('queue.job', string='Queue Job', readonly=True, ondelete='set null')
    tick = fields.Integer(default=0, readonly=True)
    last_checked_at = fields.Datetime(readonly=True)
    monitor_deadline = fields.Datetime(readonly=True)

    retry_of_id = fields.Many2one('ab_deploy_job', string='Retry Of', readonly=True, copy=False, ondelete='restrict', index=True)
    _unique_key = models.Constraint('UNIQUE(job_key)', 'Job identifier must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Jobs can only be created by the execution workflow.'))

    def write(self, vals):
        raise AccessError(_('Job results can only be changed by the execution workflow.'))

    def _set(self, vals):
        # Late worker observations must not rewrite a human resolution.
        self = self.filtered(lambda job: job.state != 'manually_resolved')
        if not self:
            return True
        if vals.get('state') in TERMINAL:
            vals = dict(vals, finished_at=fields.Datetime.now())
        # Human permissions are checked at workflow boundaries. Workers can only
        # mutate their execution record through private methods.
        return super(DeployJob, self.sudo()).write(vals)

    @api.model
    def _make(self, targets, retry_of=None):
        for target in targets:
            if not target.script or engine.checksum(target.script) != target.script_hash:
                raise UserError(_('The approved script is missing or its checksum is invalid.'))
        return super(DeployJob, self.sudo()).create([
            {'target_id': target.id, 'job_key': uuid.uuid4().hex if retry_of else target.job_key,
             'retry_of_id': retry_of.id if retry_of else False,
             'odoo_log_status': 'pending' if target.snapshot.get('odoo_log') else 'disabled'} for target in targets])

    def _schedule(self, delay=0):
        """Compatibility with the first queue-based release."""
        self.mapped('request_id')._schedule_run()

    def _run_tick(self, tick):
        """Existing serialized queue jobs stay callable after this upgrade."""
        self.ensure_one()
        if self.state in TERMINAL or self.tick != tick:
            return
        self.request_id._schedule_run()

    def action_manual_resolve(self):
        return self._open_manual_resolution(False)

    def action_undo_manual_resolution(self):
        return self._open_manual_resolution(True)

    def _open_manual_resolution(self, undo):
        self.ensure_one()
        self.check_access('read')
        self.request_id._require_role('administrator' if undo else 'executor')
        if self.state != ('manually_resolved' if undo else 'failed'):
            raise UserError(_('This execution is not eligible for this resolution action.'))
        return {'type': 'ir.actions.act_window',
                'name': _('Undo Manual Resolution') if undo else _('Mark as Manually Resolved'),
                'res_model': 'ab_deploy_manual_resolution', 'view_mode': 'form', 'target': 'new',
                'context': {'default_job_id': self.id, 'default_undo': undo}}

    def _confirm_manual_resolution(self, note, undo=False):
        self.ensure_one()
        self.check_access('read')
        self.request_id._require_role('administrator' if undo else 'executor')
        self.request_id._lock()
        self.server_id._lock()
        self._lock()
        if self.state != ('manually_resolved' if undo else 'failed'):
            raise UserError(_('This execution is not eligible for this resolution action.'))
        if not undo and self.request_id.state != 'approved':
            raise UserError(_('Manual resolution requires an approved deployment request.'))
        note = (note or '').strip()
        if not note:
            raise UserError(_('Enter a resolution note or an undo reason.'))
        self._check_not_busy()
        if undo:
            vals = {'state': 'failed', 'manual_undo_note': note}
        else:
            vals = {'state': 'manually_resolved', 'manual_resolution_note': note,
                    'manual_resolved_by_id': self.env.uid, 'manual_resolved_at': fields.Datetime.now(),
                    'manual_undo_note': False}
        # Deliberately avoid _set: preserve the original execution finish time,
        # errors and logs. The guard's write records actor, timestamp and values.
        super(DeployJob, self.sudo()).write(vals)
        self.target_id._clear_selection()
        return True

    def action_resolve(self):
        self._require_role('administrator')
        self.ensure_one()
        if self.state != 'unknown':
            raise UserError(_('Only unknown executions can be resolved.'))
        return {'type': 'ir.actions.act_window', 'name': _('Resolve Execution'),
                'res_model': 'ab_deploy_resolution', 'view_mode': 'form', 'target': 'new',
                'context': {'default_job_id': self.id,
                            'default_conflict_id': self.env.context.get('ab_deploy_conflict_id', False)}}

    def _resolve(self, note):
        self._require_role('administrator')
        self.ensure_one()
        self.request_id._lock()
        self.server_id._lock()
        self._lock()
        if self.state != 'unknown' or not (note or '').strip():
            raise UserError(_('An unknown execution and an inspection note are required.'))
        try:
            response = engine.ssh(self.target_id.snapshot['ssh_alias'], engine.monitor_command(self.job_key))
            if response.returncode:
                raise ValueError('SSH failed')
            report = engine.parse_monitor(response.stdout)
        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            raise UserError(_('Cannot verify the remote execution. Restore SSH access before resolving it.')) from exc
        if report['alive']:
            raise UserError(_('The remote tmux session is still running. Wait for it to finish.'))
        state = report['state'] if report['state'] in ('succeeded', 'failed') else 'failed'
        self._set({'state': state, 'stage': 'finished', 'exit_code': report.get('exit_code', 1), 'resolution_note': note.strip(),
                   'log_tail': report.get('log', '')[-65536:], 'error': False})
        if self.odoo_log_status in ('pending', 'error'):
            self._set({'odoo_log_status': 'pending', 'odoo_log_failures': 0})
            self.request_id._schedule_run()
