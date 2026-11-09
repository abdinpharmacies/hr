from odoo import fields, models


class AbHrEmployee(models.Model):
    _inherit = 'ab_hr_employee'

    employee_account_ids = fields.One2many(
        comodel_name='ab_custody_employee_data',
        inverse_name='employee_id',
        string='Employee Accounts',
        context={'active_test': False}
    )
