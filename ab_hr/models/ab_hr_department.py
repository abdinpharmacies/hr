# -*- coding: utf-8 -*-
from odoo import models, fields, api
from .extra_functions import get_modified_name


class Departments(models.Model):
    _name = 'ab_hr_department'
    _description = 'ab_hr_department'

    _parent_store = True
    _parent_name = "parent_id"  # optional if field is 'parent_id'
    parent_path = fields.Char(index=True)

    child_ids = fields.One2many(
        'ab_hr_department', 'parent_id',
        string='Children')
    parent_id = fields.Many2one('ab_hr_department', 'Superior Department',
                                index=True,
                                ondelete='restrict'
                                )

    name = fields.Char(required=True)
    manager_id = fields.Many2one('ab_hr_employee',
                                 string='Department Manager',
                                 store=True)

    workplace_region = fields.Many2one('ab_hr_region')
    manpower_ids = fields.One2many('ab_hr_manpower', inverse_name='workplace')
    active = fields.Boolean(default=True)
    job_title_ids = fields.Many2many(
        comodel_name='ab_hr_job',
        relation='ab_hr_job_department_rel',
        column1='department_id',
        column2='job_title_id',
        string='Managerial Job Titles')

    occupied_job_ids = fields.One2many(
        "ab_hr_job_occupied",
        "workplace")

    store_id = fields.Many2one('ab_store', index=True)
    user_id = fields.Many2one('res.users', groups='base.group_system')

    @api.model
    def _search_display_name(self, operator, value):
        mod_name = get_modified_name(value)
        return ['|', ('name', operator, value), ('name', operator, mod_name)]
