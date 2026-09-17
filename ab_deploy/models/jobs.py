import subprocess

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from ..runner import engine

TERMINAL = {'succeeded', 'failed', 'cancelled'}


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
                              ('succeeded', 'Succeeded'), ('failed', 'Failed'), ('cancelled', 'Cancelled')],
                             required=True, default='queued', readonly=True)
    started_at = fields.Datetime(readonly=True)
    finished_at = fields.Datetime(readonly=True)
    exit_code = fields.Integer(readonly=True)
    log_tail = fields.Text(string='Recent Log', readonly=True)
    error = fields.Text(readonly=True)
    resolution_note = fields.Text(readonly=True)
    queue_job_id = fields.Many2one('queue.job', string='Queue Job', readonly=True, ondelete='set null')
    tick = fields.Integer(default=0, readonly=True)
    last_checked_at = fields.Datetime(readonly=True)
    monitor_deadline = fields.Datetime(readonly=True)

    _unique_target = models.Constraint('UNIQUE(target_id)', 'A target can have only one execution job.')
    _unique_key = models.Constraint('UNIQUE(job_key)', 'Job identifier must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Jobs can only be created by the execution workflow.'))

    def write(self, vals):
        raise AccessError(_('Job results can only be changed by the execution workflow.'))

    def _set(self, vals):
        if vals.get('state') in TERMINAL:
            vals = dict(vals, finished_at=fields.Datetime.now())
        # Human permissions are checked at workflow boundaries. Workers can only
        # mutate their execution record through private methods.
        return super(DeployJob, self.sudo()).write(vals)

    @api.model
    def _make(self, targets):
        for target in targets:
            if not target.script or engine.checksum(target.script) != target.script_hash:
                raise UserError(_('The approved script is missing or its checksum is invalid.'))
        return super(DeployJob, self.sudo()).create([
            {'target_id': target.id, 'job_key': target.job_key,
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

    def action_resolve(self):
        self._require_role('administrator')
        self.ensure_one()
        if self.state != 'unknown':
            raise UserError(_('Only unknown executions can be resolved.'))
        return {'type': 'ir.actions.act_window', 'name': _('Resolve Execution'),
                'res_model': 'ab_deploy_resolution', 'view_mode': 'form', 'target': 'new',
                'context': {'default_job_id': self.id}}

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
        self._set({'state': state, 'exit_code': report.get('exit_code', 1), 'resolution_note': note,
                   'log_tail': report.get('log', '')[-65536:], 'error': False})
        if self.odoo_log_status in ('pending', 'error'):
            self._set({'odoo_log_status': 'pending', 'odoo_log_failures': 0})
            self.request_id._schedule_run()
