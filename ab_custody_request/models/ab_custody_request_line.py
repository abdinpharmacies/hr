from odoo import api, fields, models, _


class AbCustodyRequestLine(models.Model):
    _name = 'ab_custody_request_line'
    _description = 'ab_custody_request_line'

    header_id = fields.Many2one('ab_custody_request_header', required=True, ondelete='cascade')
    value = fields.Float(required=True)
    custody_account_id = fields.Many2one('ab_custody_request_account', required=True, domain=[('is_recon', '=', False)])
    # concerned_occupied_job_ids = fields.Many2many(related='custody_account_id.occupied_job_ids')
    # occupied_job_ids = fields.Many2many('ab_hr_job_occupied', required=True)
    # occupied_job_id = fields.Many2one('ab_hr_job_occupied', required=True, string='Concerned Employee')
    due_date = fields.Date()
    description = fields.Text()
    attachment = fields.Binary()
    invoice_code = fields.Char()
    competent_department_id = fields.Many2one('ab_hr_department')
    # direct_manager_approval = fields.Boolean(string="Manager App.")
    # concerned_management_approval = fields.Boolean(string="Concerned App.")

    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)

    # def btn_send_to_competent_department(self):

    # @api.onchange('custody_account_id')
    # def _onchange_ab_custody_request_line(self):
    #     self.occupied_job_id = False
