# -*- coding: utf-8 -*-
import datetime

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _


class ReportModel(models.Model):
    _name = 'ab_hr_report_model'
    _description = 'ab_hr_report_model'

    name = fields.Char(required=True)
    base_action_ids = fields.Many2many(comodel_name='ab_hr_history_action_type',
                                       relation='ab_hr_report_model_action_base_rel',
                                       column1='report_id',
                                       column2='action_type_id')
    depend_action_ids = fields.Many2many(comodel_name='ab_hr_history_action_type',
                                         relation='ab_hr_report_model_action_depend_rel',
                                         column1='report_id',
                                         column2='action_type_id')

    target_field_id = fields.Many2one('ir.model.fields',
                                      domain=[('model', '=', 'ab_hr_emp_history'),
                                              ('selectable', '=', True)])

    job_has_issue = fields.Boolean()


class ReportWizard(models.TransientModel):
    _name = 'ab_hr_report_wizard'
    _description = 'ab_hr_report_wizard'

    action_date = fields.Date(default=fields.Date.today().replace(day=1) - relativedelta(month=1))
    report_model_id = fields.Many2one('ab_hr_report_model',
                                      default=lambda self: self.env['ab_hr_report_model'].search([], limit=1).id, )

    job_title_ids = fields.Many2many('ab_hr_job')
    workplace_ids = fields.Many2many('ab_hr_department', string='Workplaces')
    territory = fields.Selection(selection=[('1', 'North'), ('2', 'South'), ('3', 'Both')], string='Territory')
    parent_department_ids = fields.Many2many(
        comodel_name='ab_hr_department',
        relation='ab_hr_department_report_region_rel',
        column1='report_id',
        column2='region_id',
        string='Superior Departments')

    html = fields.Html(readonly=True)

    def btn_termination_feedback(self):
        data = self._get_termination_feedback()
        if len(data.get('rows', 0)) > 200:
            data['rows'] = data['rows'][0:200]
        html = self.env['ir.qweb']._render('ab_hr.template_termination_feedback', data)
        self.write({'html': html})

    def _get_territory_name(self, territory):
        selection = self.fields_get(allfields=['territory'])['territory']['selection']
        selection_dict = dict(selection)
        return selection_dict.get(territory, "")

    def btn_export_excel_termination_feedback(self):
        action = self.env.ref('ab_hr.action_export_termination_feedback_excel')
        action[0].name = self.report_model_id.name
        return action.report_action(self)

    def _get_termination_feedback(self):
        headers = ['employee_code', 'employee', 'job title', 'workplace', 'territory', 'action_type', 'action_date',
                   ]
        rows = []
        # @todo fields security
        # @todo show group list and make manager choose groups for his  departmernt's employees

        domain = [('action_date', '>=', self.action_date),
                  ('action_type', 'in', self.report_model_id.base_action_ids.ids),
                  ]
        if self.report_model_id.job_has_issue:
            domain.append(('job_id.issue_date', '!=', False), )

        if self.job_title_ids:
            domain.append(('old_job_title', 'in', self.job_title_ids.ids), )

        if self.workplace_ids:
            domain.append(('old_workplace', 'in', self.workplace_ids.ids), )

        if self.territory:
            domain.append(('territory', '=', self.territory), )

        if self.parent_department_ids:
            domain.append(('workplace_region', 'in', self.parent_department_ids.ids), )

        target_jobs = self.env['ab_hr_emp_history'].search(domain).mapped('job_id')

        feedback_types = self.report_model_id.depend_action_ids
        feedback_dict = {feedback.id: '' for feedback in feedback_types}
        report_col_names = feedback_types.mapped('name')
        headers.extend(report_col_names)
        target_fld = self.report_model_id.target_field_id.name
        for job in target_jobs:
            issue_history = job.history_ids.filtered(lambda rec: rec.action_type.id
                                                                 in self.report_model_id.base_action_ids.ids)

            # my guardian if
            if not issue_history:
                continue
            if self.report_model_id.job_has_issue and issue_history[0].action_date != issue_history[0].issue_date:
                continue

            action_type_name = issue_history[0].action_type.name or ""
            feedbacks = job.history_ids.filtered(lambda rec: (rec.action_date >= self.action_date
                                                              and rec.action_type.id
                                                              in self.report_model_id.depend_action_ids.ids))

            history_line = issue_history and issue_history[0]

            if target_fld:
                for feedback in feedback_types:
                    feedbacks_with_type = feedbacks.filtered(lambda rec: rec.action_type.id == feedback.id)
                    feedback_dict[feedback.id] = '--'.join(
                        str(getattr(f, target_fld, None)) for f in feedbacks_with_type if getattr(f, target_fld, None))

            rows.append((job.employee_id.costcenter_id.code, job.employee_id.name, job.job_id.name,
                         job.workplace.name, self._get_territory_name(job.territory), action_type_name,
                         history_line.action_date,
                         *feedback_dict.values()))

        return {
            'headers': headers,
            'rows': rows
        }
