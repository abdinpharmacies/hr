from odoo import api, fields, models, _


class AbCustodyEmployeeData(models.Model):
    _name = 'ab_custody_employee_data'
    _description = 'ab_custody_employee_data'

    employee_id = fields.Many2one('ab_hr_employee')
    job_title_id = fields.Many2one(related='employee_id.job_id')
    employee_code = fields.Char(related='employee_id.costcenter_id.code')
    custody_type = fields.Selection([('visa', 'Visa'), ('cash', 'Cash')])
    department_id = fields.Many2one(related='employee_id.department_id')
    workplace_region_id = fields.Many2one(related='department_id.workplace_region')
    bank = fields.Char()
    account_number = fields.Char()
    employee_bank = fields.Char()
    attachment = fields.Binary()
    is_custody = fields.Boolean(default=True)

    active = fields.Boolean(default=True)

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.bank} [{rec.account_number}]"))
        return res

    @api.depends('account_number', 'bank')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)
