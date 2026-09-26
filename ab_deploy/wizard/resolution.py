from odoo import fields, models, _
from odoo.exceptions import UserError


class DeployResolution(models.TransientModel):
    _name = 'ab_deploy_resolution'
    _description = 'Resolve Execution'

    job_id = fields.Many2one('ab_deploy_job', required=True, readonly=True)
    note = fields.Text(string='Inspection Note', required=True)
    conflict_id = fields.Many2one('ab_deploy_conflict', readonly=True, ondelete='set null')

    def action_resolve(self):
        self.ensure_one()
        conflict = self.conflict_id.exists()
        if conflict:
            conflict.check_access('write')
            conflict.request_id._require_role('executor')
            conflict.request_id._lock()
            if self.job_id not in conflict.request_id._queue_conflicts():
                raise UserError(_('This execution is no longer a conflict. Reopen the deployment queue to review current blockers.'))
        self.job_id._resolve(self.note)
        if conflict:
            return conflict._refresh()
        return {'type': 'ir.actions.act_window_close'}
