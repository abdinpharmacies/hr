from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class DeployRecovery(models.TransientModel):
    _name = 'ab_deploy_recovery'
    _description = 'Recover Deployment Jobs'

    summary = fields.Text(readonly=True, default=lambda self: self._summary())

    def _check_admin(self):
        if not self.env.user.has_group('ab_deploy.group_administrator'):
            raise AccessError(_('Only Deployment Administrators can recover executions.'))

    @api.model
    def _summary(self):
        self._check_admin()
        jobs = self.env['ab_deploy_job'].search(fields.Domain('state', 'in', ['queued', 'running', 'unknown'])
                                                   | fields.Domain('odoo_log_status', 'in', ['pending', 'error']))
        return _('Queued: %(queued)s; Running: %(running)s; Unknown: %(unknown)s; Logs needing attention: %(logs)s',
                 queued=len(jobs.filtered(lambda j: j.state == 'queued')),
                 running=len(jobs.filtered(lambda j: j.state == 'running')),
                 unknown=len(jobs.filtered(lambda j: j.state == 'unknown')),
                 logs=len(jobs.filtered(lambda j: j.odoo_log_status in ('pending', 'error'))))

    def action_recover(self):
        self.ensure_one()
        self._check_admin()
        jobs = self.env['ab_deploy_job'].search(fields.Domain('state', 'in', ['queued', 'running', 'unknown'])
                                                   | fields.Domain('odoo_log_status', 'in', ['pending', 'error']))
        # Scope comes only from deployment records, never arbitrary queue-job IDs.
        jobs.mapped('request_id')._schedule_run()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Deployment Recovery'),
                           'message': _('Recovery scheduled for %s requests. Active queue tasks will finish normally.', len(jobs.request_id)),
                           'type': 'success', 'sticky': False,
                           'next': {'type': 'ir.actions.act_window_close'}}}
