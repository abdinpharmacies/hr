from odoo import fields, models


class TrainingTaskRejectWizard(models.TransientModel):
    _name = 'ab.training.task.reject.wizard'
    _description = 'Reject Training Task'

    task_id = fields.Many2one('ab.training.task', required=True, readonly=True)
    reason = fields.Text(required=True)

    def action_reject(self):
        self.ensure_one()
        self.task_id._reject_with_reason(self.reason)
        return {'type': 'ir.actions.act_window_close'}
