# -*- coding: utf-8 -*-
from datetime import date, datetime
from email.policy import default
from multiprocessing.dummy import Value
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
from odoo import models, fields, api


class AbdinTrainingCourses(models.Model):
    _name = "ab_hr_course"
    _description = "Abdin Training Courses"
    applicant_id = fields.Many2one('ab_hr_application')
    specialty = fields.Char(required=True)
    organization = fields.Char()
    time_period = fields.Char()
    grade = fields.Char()
