# -*- coding: utf-8 -*-
from odoo import models, fields, api
from .extra_functions import get_modified_name


######################################################################################################################
class EmployeeJobs(models.Model):
    _name = 'ab_hr_job_occupied'
    _description = 'Employee Jobs'
    _rec_name = 'job_id'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abdin_et.extra_tools']

    employee_id = fields.Many2one('ab_hr_employee', required=True, index=True, string='Employee', tracking=True)
    accid = fields.Char(related='employee_id.accid', string="Code", tracking=True)
    internal_working_employee = fields.Boolean(related='employee_id.internal_working_employee', )
    is_working = fields.Boolean(related='employee_id.is_working', )
    job_id = fields.Many2one('ab_hr_job', required=True, index=True, tracking=True, string="Job Title")

    action_date = fields.Date()
    workplace = fields.Many2one('ab_hr_department', required=True, tracking=True)
    job_status = fields.Selection([('active', 'Active'), ('inactive', 'Inactive')],
                                  store=True)
    hiring_date = fields.Date(tracking=True)
    termination_date = fields.Date(tracking=True)

    issue_date = fields.Date(store=True, tracking=True)

    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')], tracking=True)
    region = fields.Char(tracking=True)
    workplace_region = fields.Many2one(related='workplace.workplace_region', tracking=True)
    default_salary = fields.Float(groups="ab_hr.group_ab_hr_payroll_entry", tracking=True)
    is_main_job = fields.Boolean(default=True, tracking=True)
    history_ids = fields.One2many(comodel_name='ab_hr_emp_history', inverse_name='job_id')
    manual_manager = fields.Boolean(default=False)

    job_manager_id = fields.Many2one('ab_hr_employee', string='Job Manager',
                                     store=True, index=True, readonly=False)

    def _get_selection_from_action_type(self):
        model = self.env['ab_hr_history_action_type']
        selection = model.fields_get(allfields=['type'])['type']['selection']
        return selection

    @api.depends('employee_id.name', 'job_id.name', 'workplace.name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s/%s/%s' % (
                rec.employee_id.name or '',
                rec.job_id.name or '',
                rec.workplace.name or '',
            )

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return [
            '|', '|',
            ('employee_id.name', operator, value),
            ('job_id.name', operator, mod_name),
            ('id', '=ilike', value),
        ]
