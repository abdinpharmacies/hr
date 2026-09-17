from odoo import fields, models


class DeployResolution(models.TransientModel):
    _name = 'ab_deploy_resolution'
    _description = 'Resolve Execution'

    job_id = fields.Many2one('ab_deploy_job', required=True, readonly=True)
    note = fields.Text(string='Inspection Note', required=True)

    def action_resolve(self):
        self.ensure_one()
        self.job_id._resolve(self.note)
        return {'type': 'ir.actions.act_window_close'}
