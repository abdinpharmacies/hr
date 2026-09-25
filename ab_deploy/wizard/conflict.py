import json
import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class DeployConflict(models.TransientModel):
    _name = 'ab_deploy_conflict'
    _description = 'Deployment Queue Conflicts'

    request_id = fields.Many2one('ab_deploy_request', required=True, readonly=True)
    conflict_ids = fields.Many2many('ab_deploy_job', readonly=True, string='Existing Executions')
    has_hidden_conflicts = fields.Boolean(readonly=True)
    can_replace = fields.Boolean(readonly=True)
    fingerprint = fields.Text(readonly=True)
    changed = fields.Boolean(readonly=True)

    @api.model
    def _fingerprint(self, jobs, request):
        return hashlib.sha256(json.dumps({'targets': sorted(request._selected_targets().ids),
                           'jobs': [(j.id, j.state) for j in jobs.sorted('id')]}).encode()).hexdigest()

    @api.model
    def _open(self, request, jobs):
        wizard = self.create(dict(self._conflict_values(jobs, request), request_id=request.id))
        return wizard._action()

    @api.model
    def _conflict_values(self, jobs, request):
        visible = self.env['ab_deploy_job'].search(fields.Domain('id', 'in', jobs.ids))
        admin = self.env.user.has_group('ab_deploy.group_administrator')
        manageable = admin or (len(visible) == len(jobs) and all(
            job.request_id.executor_id == self.env.user for job in visible))
        return {'conflict_ids': [fields.Command.set(visible.ids)],
                'has_hidden_conflicts': len(visible) != len(jobs), 'can_replace': manageable,
                'fingerprint': self._fingerprint(jobs, request)}

    def _action(self):
        return {'type': 'ir.actions.act_window', 'name': _('Deployment Queue Conflicts'),
                'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def _confirm(self, replace):
        self.ensure_one()
        request = self.request_id
        request._require_role('executor')
        request._lock()
        request._selected_targets().server_id.sorted('id')._lock()
        jobs = request._queue_conflicts()
        jobs.sorted('id')._lock()
        if self.fingerprint != self._fingerprint(jobs, request):
            self.write(dict(self._conflict_values(jobs, request), changed=True))
            return self._action()
        if replace:
            if not self._conflict_values(jobs, request)['can_replace']:
                raise AccessError(_('Only an assigned executor or administrator can replace conflicting deployments.'))
            waiting = jobs.filtered(lambda j: j.state == 'queued')
            waiting._set({'state': 'cancelled', 'cancelled_by_id': self.env.uid, 'superseded_by_id': request.id})
            waiting.with_user(self.env.user)._audit('write', values={'replaced_by': request.name, 'cancelled_by': self.env.uid})
        request._queue_confirmed()
        return {'type': 'ir.actions.act_window_close'}

    def action_replace(self):
        return self._confirm(True)

    def action_wait(self):
        return self._confirm(False)
