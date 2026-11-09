from odoo import fields, models


class EmployeePayroll(models.Model):
    _inherit = 'ab_hr_employee'

    user_line_owner = fields.Many2one(
        'res.users', domain=lambda self: [('account_auth_ids', '!=', False)])
    payment_name = fields.Char(
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_accountant')
    payment_no = fields.Char(
        groups='ab_hr.group_ab_hr_co,ab_hr.group_ab_hr_payroll_accountant')


class OccupiedJobPayroll(models.Model):
    _inherit = 'ab_hr_job_occupied'

    default_salary = fields.Float(
        groups='ab_hr.group_ab_hr_payroll_entry', tracking=True)
