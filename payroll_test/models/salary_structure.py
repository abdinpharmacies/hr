from odoo import models, fields, api
from .engines import get_engine

class DailyHoursSalaryStructure(models.Model):
    _name = 'daily.hours.salary.structure'
    _description = 'Salary Structure'

    name = fields.Char(string='Structure Name', compute='_compute_name')
    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    period_id = fields.Many2one('daily.hours.payroll.period', string='Payroll Period', required=True)
    
    basic_salary = fields.Float(string='Basic Salary', compute='_compute_salaries', store=True)
    working_days_in_period = fields.Integer(string='Working Days', compute='_compute_working_days_in_period', store=True)
    
    allowance_nature_of_work = fields.Float(string='Nature of Work (30%)', compute='_compute_salaries', store=True)
    allowance_performance = fields.Float(string='Performance (30%)', compute='_compute_salaries', store=True)
    allowance_cost_of_living = fields.Float(string='Cost of Living (20%)', compute='_compute_salaries', store=True)
    allowance_dedication = fields.Float(string='Dedication (20%)', compute='_compute_salaries', store=True)
    total_basic_allowances = fields.Float(string='Total Basic Allowances', compute='_compute_salaries', store=True)
    
    extra_allowances = fields.Float(string='Total Extra Allowances', compute='_compute_extra_allowances', store=True)
    extra_allowances_fixed = fields.Float(string='Fixed Allowances', compute='_compute_extra_allowances', store=True)
    extra_allowances_prorated = fields.Float(string='Prorated Allowances', compute='_compute_extra_allowances', store=True)
    extra_allowances_custom = fields.Float(string='Custom Allowances', compute='_compute_extra_allowances', store=True)

    attendance_percentage = fields.Float(string='Attendance (%)', compute='_compute_salaries', store=True)
    agreement_salary = fields.Float(string='Agreed Salary', compute='_compute_salaries', store=True)
    
    penalty_late_arrival = fields.Float(string='Late Arrival Penalty', compute='_compute_salaries', store=True)
    penalty_unauthorized_shift = fields.Float(string='Unauthorized Shift Penalty', compute='_compute_salaries', store=True)
    penalty_shortage_hours = fields.Float(string='Shortage Hours Penalty', compute='_compute_salaries', store=True)
    
    earning_grace_period_overtime = fields.Float(string='Grace Period Overtime', compute='_compute_salaries', store=True)
    earning_authorized_overtime = fields.Float(string='Authorized Overtime', compute='_compute_salaries', store=True)
    earning_two_hour_permission = fields.Float(string='Two Hour Permission', compute='_compute_salaries', store=True)
    earning_manual_bonus = fields.Float(string='Manual Bonus')

    day_basic = fields.Float(string='Day Basic', compute='_compute_daily_values', store=True)
    day_allowances = fields.Float(string='Day Allowances', compute='_compute_daily_values', store=True)
    day_total = fields.Float(string='Day Total', compute='_compute_daily_values', store=True)

    hour_basic = fields.Float(string='Hour Basic', compute='_compute_hourly_values', store=True)
    hour_allowances = fields.Float(string='Hour Allowances', compute='_compute_hourly_values', store=True)
    hour_total = fields.Float(string='Hour Total', compute='_compute_hourly_values', store=True)

    forget_fingerprint_count = fields.Integer(string='Forget Fingerprint Count', compute='_compute_forget_penalty', store=True)
    forget_fingerprint_penalty = fields.Float(string='Forget Fingerprint Penalty', compute='_compute_forget_penalty', store=True)

    def _get_engine(self):
        self.ensure_one()
        return get_engine(self)

    @api.depends('employee_id', 'period_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.period_id:
                record.name = f"Salary Structure {record.employee_id.name} - {record.period_id.name}"
            else:
                record.name = 'هيكل جديد' if record.env.lang == 'ar_001' else 'New Structure'

    @api.depends(
        'employee_id.hourly_basic_rate',
        'employee_id.hourly_allowance_rate',
        'employee_id.daily_working_hours',
        'employee_id.payroll_type',
        'working_days_in_period'
    )
    def _compute_salaries(self):
        for record in self:
            engine = record._get_engine()
            if engine:
                vals = engine.calculate_salaries()
                record.update(vals)
            else:
                record.update({
                    'basic_salary': 0.0,
                    'allowance_nature_of_work': 0.0,
                    'allowance_performance': 0.0,
                    'allowance_cost_of_living': 0.0,
                    'allowance_dedication': 0.0,
                    'total_basic_allowances': 0.0,
                    'attendance_percentage': 0.0,
                    'agreement_salary': 0.0,
                    'penalty_late_arrival': 0.0,
                    'penalty_unauthorized_shift': 0.0,
                    'penalty_shortage_hours': 0.0,
                    'earning_grace_period_overtime': 0.0,
                    'earning_authorized_overtime': 0.0,
                    'earning_two_hour_permission': 0.0,
                })

    @api.depends('employee_id.hourly_basic_rate', 'employee_id.hourly_allowance_rate')
    def _compute_extra_allowances(self):
        for record in self:
            basic = record.employee_id.hourly_basic_rate or 0
            allowance = record.employee_id.hourly_allowance_rate or 0
            record.extra_allowances_fixed = 0
            record.extra_allowances_prorated = 0
            record.extra_allowances_custom = 0
            record.extra_allowances = basic + allowance

    @api.depends('employee_id.weekly_off_1', 'employee_id.weekly_off_2', 'period_id.start_date', 'period_id.end_date')
    def _compute_working_days_in_period(self):
        for record in self:
            if record.employee_id and record.period_id:
                record.working_days_in_period = record.period_id.calculate_days_required(
                    record.employee_id.weekly_off_1,
                    record.employee_id.weekly_off_2
                )
            else:
                record.working_days_in_period = 0

    @api.depends('basic_salary', 'total_basic_allowances', 'extra_allowances', 'working_days_in_period')
    def _compute_daily_values(self):
        for record in self:
            if record.basic_salary:
                days = record.working_days_in_period or 1
                record.day_basic = record.basic_salary / days
                record.day_allowances = record.total_basic_allowances / days
                record.day_total = record.day_basic + record.day_allowances
            else:
                record.day_basic = 0.0
                record.day_allowances = 0.0
                record.day_total = 0.0

    @api.depends('employee_id', 'period_id', 'day_basic')
    def _compute_forget_penalty(self):
        for record in self:
            record.forget_fingerprint_count = 0
            record.forget_fingerprint_penalty = 0.0

    @api.depends('day_basic', 'total_basic_allowances', 'working_days_in_period', 'employee_id.daily_working_hours')
    def _compute_hourly_values(self):
        for record in self:
            if record.day_basic:
                hours = record.employee_id.daily_working_hours or 1
                record.hour_basic = record.day_basic / hours
                record.hour_allowances = record.day_allowances / hours
                record.hour_total = record.hour_basic + record.hour_allowances
            else:
                record.hour_basic = 0.0
                record.hour_allowances = 0.0
                record.hour_total = 0.0