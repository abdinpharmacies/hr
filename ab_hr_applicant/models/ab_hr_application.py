# -*- coding: utf-8 -*-
from datetime import date, datetime
from email.policy import default
from multiprocessing.dummy import Value
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from odoo import models, fields, api


class hrabdin(models.Model):
    _name = 'ab_hr_application'
    _description = "Abdin HR Applicants"

    _unique_application_code = models.Constraint(
        "UNIQUE(code)",
        "Application code must be unique.",
    )

    @api.model
    def _default_required_job_id(self):
        RequiredJob = self.env['ab_required_job'].sudo()
        ctx = self.env.context or {}

        required_job_id = ctx.get('default_required_job_id') or ctx.get('required_job_id')
        if required_job_id:
            required_job = RequiredJob.browse(required_job_id)
            if required_job.exists():
                return required_job.id

        legacy_job_id = ctx.get('default_job_id') or ctx.get('job_id')
        if legacy_job_id:
            required_job = RequiredJob.browse(legacy_job_id)
            if required_job.exists():
                return required_job.id
            mapped_job = RequiredJob.search([('job_id', '=', legacy_job_id)], limit=1)
            if mapped_job:
                return mapped_job.id

        unknown_job = RequiredJob.search([('name', '=', 'غير محدد')], limit=1)
        if unknown_job:
            return unknown_job.id

        fallback_job = RequiredJob.search([], order='id', limit=1)
        return fallback_job.id if fallback_job else False

    name = fields.Char(required=True)
    code = fields.Char(string='Code', readonly=True, copy=False, index=True)
    national_identity = fields.Char(required=True)
    military_status = fields.Selection(
        selection=[('perform', 'Perform'),
                   ('did_not_perform', 'Did not perform '),
                   ('delayed', 'Delayed'),
                   ('exempt', 'exempt'),
                   ('unrequired', 'unrequired')],
        required=True)
    birth_date = fields.Date(required=True)
    city_id = fields.Many2one('ab_city', required=True, domain="[('state_id','=',governorate_id)]")
    governorate_id = fields.Many2one('res.country.state', required=True)
    address = fields.Char(required=True)
    religion = fields.Selection(
        selection=[('muslim', 'Muslim'),
                   ('christian', 'Christian'),
                   ('jewish', 'Jewish'), ('undefined', 'Undefined')],
        required=True)
    mobile = fields.Char(required=True)
    telephone = fields.Char()
    email = fields.Char()
    gender = fields.Selection(selection=[('male', 'Male'), ('female', 'Female')], required=True)
    qualification = fields.Char(required=True)
    nationality = fields.Many2one('res.country', default=lambda self: self._get_nationality_default(), required=True)
    graduate_date = fields.Date(required=True)
    marital_status = fields.Selection(
        selection=[('single', 'Single'),
                   ('married', 'Married'),
                   ('divorced', 'Divorced'),
                   ('widower', 'Widower')],
        required=True)
    experience_ids = fields.One2many('ab_hr_experience', 'applicant_id')
    trainingcourses_ids = fields.One2many('ab_hr_course', 'applicant_id')
    type_of_form = fields.Selection(selection=[('recruit', 'Recruit'), ('training', 'Training')], required=True)
    required_job_id = fields.Many2one(
        'ab_required_job',
        required=True,
        string='Required Job',
        default=lambda self: self._default_required_job_id(),
    )
    expected_salary = fields.Integer(required=True)
    bconnect_experience = fields.Boolean()
    morning = fields.Boolean(default=True)
    evening = fields.Boolean(default=True)
    after_midnight = fields.Boolean(default=True)
    Interviews_ids = fields.One2many('ab_hr_interview', 'applicant_id')
    last_action = fields.Selection(selection=[
        ('accepted_job_offer', 'Accepted Job Offer'),
        ('accepted_short_list', 'Accepted Short List'),
        ('accepted_waiting_list', 'Accepted Waiting List'),
        ('training', 'Training'),
        ('advanced_training', 'Advanced Training'),
        ('duplicated_training', 'Duplicated Training'),
        ('re_appraisal_interview', 'Re-Appraisal Interview'),
        ('archived', 'Archived'),
        ('s_list', 'S.List'),
        ('rejected', 'Rejected')
    ], compute="_get_action_default")
    applicant_status = fields.Selection(
        selection=[('current_employee', 'Current employee'),
                   ('former_employee', 'Former employee')],
        compute=lambda self: self._get_applicant_status())

    def _get_nationality_default(self):
        egypt = self.env['res.country'].sudo().search(
            [('name', 'ilike', 'Egy')], limit=1)
        return egypt.id

    @api.model
    def _next_application_code(self):
        sequence = self.env['ir.sequence'].sudo()
        for _attempt in range(30):
            code = sequence.next_by_code('ab_hr_application.code')
            if code and not self.sudo().search_count([('code', '=ilike', code)]):
                return code
        return f"APP/{int(fields.Datetime.now().timestamp())}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                continue

            mssql_app_id = vals.get('mssql_app_id')
            if mssql_app_id:
                try:
                    mssql_number = int(mssql_app_id)
                except (TypeError, ValueError):
                    mssql_number = 0

                if mssql_number > 0:
                    candidate = f'APP/{mssql_number}'
                    if not self.sudo().search_count([('code', '=ilike', candidate)]):
                        vals['code'] = candidate
                        continue

            vals['code'] = self._next_application_code()

        return super().create(vals_list)

    # _sql_constraints = [
    #     ('unique_Aplicant', 'unique (name,type_of_form,required_job_id)', 'Name must be unique!'),
    # ]

    @api.depends("Interviews_ids", "Interviews_ids.action", "Interviews_ids.interview_date", "Interviews_ids.applicant_id")
    def _get_action_default(self):
        if not self:
            return

        interviews = self.env['ab_hr_interview'].sudo().search(
            [('applicant_id', 'in', self.ids)],
            order='applicant_id, interview_date desc, id desc',
        )
        latest_action_by_applicant = {}
        for interview in interviews:
            applicant_id = interview.applicant_id.id
            if applicant_id not in latest_action_by_applicant:
                latest_action_by_applicant[applicant_id] = interview.action

        for record in self:
            record.last_action = latest_action_by_applicant.get(record.id, False)

    @api.constrains('name', 'national_identity', 'birth_date', 'mobile', 'experience_ids', 'expected_salary', 'morning',
                    'evening', 'after_midnight')
    def _check_record(self):
        for record in self:
            age = relativedelta(datetime.today(), record.birth_date).years
            # if len(record.name.split()) < 4:
            #     raise ValidationError("Invalid Name-Please Enter a Full Name")
            # if len(record.national_identity) != 14:
            #     raise ValidationError("Invalid National Identity")
            # if age < 18:
            #     raise ValidationError("Invalid Birth Date-Age Must Be Over 18 Years Old")
            # if len(record.mobile) != 11:
            #     raise ValidationError("Invalid mobile Number")
            # if record.expected_salary > 100000:
            #     raise ValidationError("The maximum salary is 100000")
            # if record.morning != True and record.evening != True and record.after_midnight != True:
            #     raise ValidationError("Please select At least one work shift")

    def _get_applicant_status(self):
        for record in self:
            employee = self.env['ab_hr_employee'].sudo().search([('national_identity', '=', record.national_identity)],
                                                                limit=1)
            if employee:
                if employee.active:
                    record.applicant_status = 'current_employee'
                else:
                    record.applicant_status = 'former_employee'
            else:
                record.applicant_status = False
