from odoo import fields, models


class DeployManualResolution(models.TransientModel):
    _name = 'ab_deploy_manual_resolution'
    _description = 'Manual Deployment Resolution'

    job_id = fields.Many2one('ab_deploy_job', required=True, readonly=True)
    undo = fields.Boolean(readonly=True)
    note = fields.Text(string='Resolution Note / Undo Reason', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.job_id._confirm_manual_resolution(self.note, undo=self.undo)
        return {'type': 'ir.actions.act_window_close'}
