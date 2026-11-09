# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
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
                                 compute='_compute_manager_id',
                                 string='Department Manager',
                                 store=True,
                                 domain=[
                                     ('is_working', '=', True),
                                     ('internal_working_employee', '=', True),
                                 ])

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

    @api.depends('occupied_job_ids', 'occupied_job_ids.workplace', 'occupied_job_ids.job_status',
                 'occupied_job_ids.job_id', 'job_title_ids')
    def _compute_manager_id(self):
        for rec in self:
            rec.manager_id = rec._get_manager_id()

    def _get_manager_id(self, exclude=None):

        OccupiedJob = self.env['ab_hr_job_occupied']
        workplace_id = self.id
        if isinstance(workplace_id, int):

            workplaces = self.parent_path.strip('/').split('/')
            workplaces.pop()
            job_title_ids = self.job_title_ids.ids
            occupied_job = OccupiedJob.search(
                [('job_id', 'in', job_title_ids),
                 ('workplace', '=', workplace_id),
                 ('job_status', '=', 'active'),
                 ])
            if occupied_job:
                return occupied_job[0].employee_id.id
            else:
                for workplace in reversed(workplaces):
                    occupied_job = OccupiedJob.search([
                        ('workplace', '=', int(workplace)),
                        ('job_status', '=', 'active')
                    ])
                    if occupied_job:
                        return occupied_job[0].employee_id.id

        # else
        return False

    def btn_add_job_title(self):
        return {
            'name': _("Create New Job"),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_job_wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_workplace': self.id,
                'default_type_of_action': '3',
            }
        }

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|',
                 ('name', operator, name),
                 ('name', operator, mod_name),
                 ]

        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        return ids

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Expose the existing search order through the Odoo 19 public API."""
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]

    _ab_hr_department_unique = models.Constraint('unique(name)', 'DEPARTMENT CAN NOT BE DUPLICATED!')
