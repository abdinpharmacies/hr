from odoo import models, fields, api
from datetime import timedelta

class DailyHoursPayrollPeriod(models.Model):
    _name = 'daily.hours.payroll.period'
    _description = 'Payroll Period'

    name = fields.Char(string='Name', compute='_compute_name')
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    total_working_days = fields.Integer(string='Required Working Days', compute='_compute_working_days', store=True)

    @api.depends('start_date', 'end_date')
    def _compute_name(self):
        for record in self:
            if record.start_date and record.end_date:
                record.name = f"From {record.start_date} to {record.end_date}"
            else:
                lang = record.env.lang
                record.name = 'فترة جديدة' if lang == 'ar_001' else 'New Period'

    @api.depends('start_date', 'end_date')
    def _compute_working_days(self):
        for record in self:
            if record.start_date and record.end_date:
                # Default calculation uses Friday ('4') if no employee is specified
                record.total_working_days = record.calculate_days_required('4')
            else:
                record.total_working_days = 0

    def calculate_days_required(self, off_day_str_1, off_day_str_2=False):
        self.ensure_one()
        days_count = 0
        current_date = self.start_date
        off_1 = int(off_day_str_1)
        off_2 = int(off_day_str_2) if off_day_str_2 else None
        
        while current_date <= self.end_date:
            weekday = current_date.weekday()
            if weekday != off_1 and (off_2 is None or weekday != off_2):
                days_count += 1
            current_date += timedelta(days=1)
        return days_count
