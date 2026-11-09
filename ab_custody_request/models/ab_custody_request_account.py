from odoo import api, fields, models, _


class CustodyRequestAccount(models.Model):
    _name = 'ab_custody_request_account'
    _description = 'ab_custody_request_account'

    name = fields.Char()
    job_title_id = fields.Many2one('ab_hr_job')
    department_id = fields.Many2one('ab_hr_department')
    telegram_group = fields.Char(string='Telegram Group')
    telegram_group_id = fields.Float(string='Telegram Group ID', digits=(13, 0),
                                     compute='_compute_telegram_group_id', store=True)
    account_id = fields.Many2one('ab_accounting_account_guide', string='Linked to Account')
    occupied_job_ids = fields.Many2many('ab_hr_job_occupied',
                                        compute='_compute_occupied_job_ids')
    department_manager_id = fields.Many2one(related='department_id.manager_id')
    is_recon = fields.Boolean()

    @api.depends('telegram_group')
    def _compute_telegram_group_id(self):
        for rec in self:
            try:
                final_id_str = str(abs(int(rec.telegram_group)))

                if len(final_id_str) == 10:
                    final_id_str = f"-100{final_id_str}"
                elif len(final_id_str) == 13:
                    final_id_str = f"-{final_id_str}"
                else:
                    final_id_str = "0"
            except ValueError:
                final_id_str = "0"

            rec.telegram_group_id = float(final_id_str)

    @api.depends('job_title_id', 'department_id')
    def _compute_occupied_job_ids(self):
        for rec in self:
            if rec.job_title_id or rec.department_id:
                rec.occupied_job_ids = self.env['ab_hr_job_occupied'].search(
                    [
                        ('job_status', '=', 'active'),
                        '|',
                        ('job_id', '=', rec.job_title_id.id),
                        (not rec.job_title_id, '=', 1),
                        '|',
                        ('workplace', 'child_of', rec.department_id.id),
                        (not rec.department_id, '=', 1),
                    ])
            else:
                rec.occupied_job_ids = self.env['ab_hr_job_occupied']
