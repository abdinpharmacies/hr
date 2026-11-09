# -*- coding: utf-8 -*-
import datetime

from odoo import models, fields, api, SUPERUSER_ID, _
from odoo.exceptions import UserError, ValidationError
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
                                  compute='_compute_job_status',
                                  store=True)
    hiring_date = fields.Date(tracking=True)
    termination_date = fields.Date(tracking=True)

    issue_date = fields.Date(compute="_compute_issue_date", store=True, tracking=True)

    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')], tracking=True)
    region = fields.Char(tracking=True)
    workplace_region = fields.Many2one(related='workplace.workplace_region', tracking=True)
    is_main_job = fields.Boolean(default=True, tracking=True)
    history_ids = fields.One2many(comodel_name='ab_hr_emp_history', inverse_name='job_id')
    manual_manager = fields.Boolean(default=False)

    job_manager_id = fields.Many2one('ab_hr_employee', string='Job Manager',
                                     compute="_compute_job_manager_id",
                                     store=True, index=True, readonly=False)

    # parent_department_id = fields.Many2one(related='workplace.parent_id', string='Superior Department')

    @api.depends('workplace.manager_id', 'workplace.parent_id.manager_id', 'manual_manager')
    def _compute_job_manager_id(self):
        for rec in self:
            if rec.manual_manager:
                # do not compute if it's manual and working manager
                continue

            rec.job_manager_id = rec.employee_id.compute_responsible(rec.workplace, rec.employee_id.id)

    @api.depends('history_ids.action_date', 'history_ids.action_type')
    def _compute_issue_date(self):
        history = self.env['ab_hr_emp_history'].sudo()
        for job in self:
            # if job(<NewId origin=xxx>,) continue
            if not job.id:
                continue

            history_ids = history.search([('job_id', '=', job.id)], order='action_date desc')
            for history_id in history_ids:
                if history_id.action_type.action_date_type in ['clear_issue']:
                    job.sudo().issue_date = None
                    break
                elif history_id.action_type.action_date_type in ['pending_issue', 'direct_issue']:
                    job.sudo().issue_date = history_id.action_date
                    break
            else:
                job.sudo().issue_date = None

    def _get_selection_from_action_type(self):
        model = self.env['ab_hr_history_action_type']
        selection = model.fields_get(allfields=['type'])['type']['selection']
        return selection

    @api.depends('termination_date')
    def _compute_job_status(self):
        for rec in self:
            if rec.termination_date:
                rec.job_status = 'inactive'
            else:
                rec.job_status = 'active'

    # def write(self, values):
    #     model = self.env['ab_hr_employee']
    #     emp_ids = self.mapped('employee_id.id')
    #
    #     res = super().write(values)
    #     if values:
    #         if values.get('employee_id', False):
    #             emp_ids.append(values.get('employee_id'))
    #     self.env.all.tocompute[model._fields['department_id']].update(emp_ids)
    #     model._recompute_recordset()
    #     return res

    @api.constrains('employee_id', 'job_id', 'workplace', 'job_status', 'manual_manager', 'job_manager_id')
    def ab_hr_job_occupied_constrains(self):
        for rec in self:
            job_manager_job_child = self.search([('job_manager_id', '=', rec.employee_id.id)], limit=1)
            job_manager_child = job_manager_job_child.employee_id
            job_manager = job_manager_job_child.job_manager_id
            parent_child = self.employee_id.search([('parent_id', '=', rec.employee_id.id)], limit=1)
            parent = parent_child.parent_id
            # if not rec.internal_working_employee:
            #     if job_manager_child:
            #         raise ValidationError(
            #             _("Can not set %s with code %s,\n as job manager for %s with code %s"
            #               ".\nManager must be working employee!")
            #             % (job_manager.name, job_manager.accid,
            #                job_manager_child.name, job_manager_child.accid))
            #     if parent:
            #         raise ValidationError(
            #             _("Can not set %s with code %s,\n as manager for %s with code %s"
            #               ".\nManager must be working employee!")
            #             % (parent.name, parent.accid,
            #                parent_child.name, parent_child.accid))

            if rec.job_status == 'active':
                job = self.env['ab_hr_job_occupied'].search([
                    ('id', '!=', rec.id),
                    ('job_status', '=', 'active'),
                    ('employee_id', '=', rec.employee_id.id),
                    ('job_id', '=', rec.job_id.id),
                    ('workplace', '=', rec.workplace.id),
                ], limit=1)

                if job and job[0]:
                    raise ValidationError("""Duplicated active job for the same employee
                    \nName: %s\n Job Title: %s\n Workplace: %s\n Hiring Date: %s\n Region: %s\n""" % (
                        job.employee_id.name,
                        job.job_id.name,
                        job.workplace.name,
                        job.hiring_date,
                        job.region,
                    ))

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, '%s/%s/%s' % (
                rec.employee_id.name, rec.job_id.name, rec.workplace.name,)))
        return res

    @api.depends('employee_id', 'job_id', 'workplace')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        mod_name = get_modified_name(name)
        args += ['|', '|',
                 ('employee_id.name', operator, name),
                 ('job_id.name', operator, mod_name),
                 ('id', '=ilike', name),
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

    def btn_change_job(self):

        return {
            'name': _("Add Movement"),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_job_wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_employee_id': self.employee_id.id,
                'default_job_id': self.id,
                'default_type_of_action': '2', }
        }
