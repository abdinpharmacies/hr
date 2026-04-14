# -*- coding: utf-8 -*-
from datetime import date, datetime
from email.policy import default
from multiprocessing.dummy import Value
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from odoo import models, fields, api


class AbdinExperience(models.Model):
    _name = "ab_hr_experience"
    _description = "Experiences"
    _rec_name = "company_name"
    applicant_id = fields.Many2one('ab_hr_application')
    company_name = fields.Char(required=True)
    job_title = fields.Char()
    starting_date = fields.Date()
    ending_date = fields.Date()
    reason_for_leaving = fields.Char()
    salary = fields.Integer()
