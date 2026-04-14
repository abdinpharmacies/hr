from odoo import api, fields, models
from odoo.tools.translate import _


class ResUsers(models.Model):
    _inherit = 'res.users'

    ab_employee_ids = fields.One2many('ab_hr_employee',
                                      'user_id',
                                      string='Employees')

    ab_department_ids = fields.One2many('ab_hr_department',
                                        'user_id',
                                        string='Department')
