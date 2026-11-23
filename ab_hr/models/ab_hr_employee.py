from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .extra_functions import with_normalized_name


class Employee(models.Model):
    _name = 'ab_hr_employee'
    _description = 'Employee'
    _rec_names_search = ['name', 'accid']
    _parent_store = True

    name = fields.Char(required=True)
    english_name = fields.Char()
    costcenter_id = fields.Many2one('ab_costcenter', string='Cost Center', index=True)
    accid = fields.Char(string='ePlus Code', index=True)
    work_email = fields.Char()
    parent_id = fields.Many2one('ab_hr_employee', string='Manager', index=True, ondelete='restrict')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('ab_hr_employee', 'parent_id', string='Direct Reports')
    job_id = fields.Many2one('ab_hr_job', index=True)
    department_id = fields.Many2one('ab_hr_department', index=True)
    hiring_date = fields.Date()
    termination_date = fields.Date()
    issue_date = fields.Date()
    job_status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')])
    territory = fields.Selection([('1', 'North'), ('2', 'South'), ('3', 'Both')])
    is_working = fields.Boolean(string='Working')
    active = fields.Boolean(default=True)

    @api.constrains('parent_id')
    def _check_manager_hierarchy(self):
        if self._has_cycle():
            raise ValidationError(_('An employee cannot be their own direct or indirect manager.'))

    @api.model
    def _search_display_name(self, operator, value):
        domain = super()._search_display_name(operator, value)
        return with_normalized_name(domain, operator, value)
