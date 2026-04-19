from odoo import models, fields, api
from .engines import get_engine

class DailyHoursSalaryStructure(models.Model):
    _name = 'daily.hours.salary.structure'
    _description = 'Salary Structure'

    name = fields.Char(string='اسم الهيكل', compute='_compute_name')
    employee_id = fields.Many2one('ab_hr_employee', string='Employee', required=True)
    period_id = fields.Many2one('daily.hours.payroll.period', string='Payroll Period', required=True)
    
    basic_salary = fields.Float(string='الراتب الأساسي', compute='_compute_salaries', store=True)
    working_days_in_period = fields.Integer(string='أيام العمل في الفترة', compute='_compute_working_days_in_period', store=True)
    
    # Allowances
    allowance_nature_of_work = fields.Float(string='طبيعة عمل (30%)', compute='_compute_salaries', store=True)
    allowance_performance = fields.Float(string='أداء (30%)', compute='_compute_salaries', store=True)
    allowance_cost_of_living = fields.Float(string='غلاء معيشة (20%)', compute='_compute_salaries', store=True)
    allowance_dedication = fields.Float(string='تفرغ (20%)', compute='_compute_salaries', store=True)
    total_basic_allowances = fields.Float(string='إجمالي البدلات الأساسية', compute='_compute_salaries', store=True)
    
    # Extra Allowances
    extra_allowances = fields.Float(string='إجمالي البدلات الإضافية', compute='_compute_extra_allowances', store=True)
    extra_allowances_fixed = fields.Float(string='بدلات إضافية ثابتة', compute='_compute_extra_allowances', store=True)
    extra_allowances_prorated = fields.Float(string='بدلات إضافية تناسبية', compute='_compute_extra_allowances', store=True)
    extra_allowances_custom = fields.Float(string='بدلات إضافية مخصصة', compute='_compute_extra_allowances', store=True)

    attendance_percentage = fields.Float(string='نسبة الحضور (%)', compute='_compute_salaries', store=True)
    agreement_salary = fields.Float(string='راتب الاتفاق', compute='_compute_salaries', store=True)
    
    # New Penalties 
    penalty_late_arrival = fields.Float(string='جزاء تأخير', compute='_compute_salaries', store=True)
    penalty_unauthorized_shift = fields.Float(string='جزاء تغيير وردية', compute='_compute_salaries', store=True)
    penalty_shortage_hours = fields.Float(string='خصم نقص الساعات', compute='_compute_salaries', store=True)
    
    # New Earnings / Overtime
    earning_grace_period_overtime = fields.Float(string='إضافي فترة سماح', compute='_compute_salaries', store=True)
    earning_authorized_overtime = fields.Float(string='إضافي بإذن', compute='_compute_salaries', store=True)
    earning_two_hour_permission = fields.Float(string='تعويض إذن ساعتين', compute='_compute_salaries', store=True)
    earning_manual_bonus = fields.Float(string='مكافآت (يدوي)')

    # Daily Values
    day_basic = fields.Float(string='قيمة اليوم (أساسي)', compute='_compute_daily_values', store=True)
    day_allowances = fields.Float(string='قيمة اليوم (بدلات)', compute='_compute_daily_values', store=True)
    day_total = fields.Float(string='قيمة اليوم (إجمالي)', compute='_compute_daily_values', store=True)

    # Hourly Values
    hour_basic = fields.Float(string='قيمة الساعة (أساسي)', compute='_compute_hourly_values', store=True)
    hour_allowances = fields.Float(string='قيمة الساعة (بدلات أساسية)', compute='_compute_hourly_values', store=True)
    hour_total = fields.Float(string='قيمة الساعة (إجمالي)', compute='_compute_hourly_values', store=True)

    # Penalty
    forget_fingerprint_count = fields.Integer(string='عدد مرات نسيان البصمة', compute='_compute_forget_penalty', store=True)
    forget_fingerprint_penalty = fields.Float(string='جزاء نسيان البصمة', compute='_compute_forget_penalty', store=True)

    def _get_engine(self):
        self.ensure_one()
        return get_engine(self)

    @api.depends('employee_id', 'period_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id and record.period_id:
                record.name = f"هيكل راتب {record.employee_id.name} - {record.period_id.name}"
            else:
                record.name = "هيكل جديد"

    @api.depends(
        'employee_id.hourly_rate_basic',
        'employee_id.hourly_rate_allowances',
        'employee_id.working_hours_per_day',
        'employee_id.payroll_system',
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

    @api.depends('employee_id.extra_allowances_ids', 'employee_id.extra_allowances_ids.amount', 'employee_id.extra_allowances_ids.allowance_type_id.calculation_type')
    def _compute_extra_allowances(self):
        for record in self:
            alws = record.employee_id.extra_allowances_ids
            fixed = sum(alws.filtered(lambda a: a.calculation_type == 'fixed').mapped('amount'))
            prorated = sum(alws.filtered(lambda a: a.calculation_type == 'prorated').mapped('amount'))
            custom = sum(alws.filtered(lambda a: a.calculation_type == 'custom').mapped('amount'))
            
            record.update({
                'extra_allowances_fixed': fixed,
                'extra_allowances_prorated': prorated,
                'extra_allowances_custom': custom,
                'extra_allowances': fixed + prorated + custom
            })

    @api.depends('employee_id.weekly_off_day_1', 'employee_id.weekly_off_day_2', 'period_id.start_date', 'period_id.end_date')
    def _compute_working_days_in_period(self):
        for record in self:
            if record.employee_id and record.period_id:
                record.working_days_in_period = record.period_id.calculate_days_required(
                    record.employee_id.weekly_off_day_1,
                    record.employee_id.weekly_off_day_2
                )
            else:
                record.working_days_in_period = 0

    @api.depends('basic_salary', 'total_basic_allowances', 'extra_allowances', 'working_days_in_period')
    def _compute_daily_values(self):
        for record in self:
            engine = record._get_engine()
            if engine:
                vals = engine.calculate_daily_hourly_values(
                    record.basic_salary, record.total_basic_allowances, record.extra_allowances, record.working_days_in_period
                )
                record.update({
                    'day_basic': vals.get('day_basic', 0.0),
                    'day_allowances': vals.get('day_allowances', 0.0),
                    'day_total': vals.get('day_total', 0.0),
                })
            else:
                record.update({'day_basic': 0.0, 'day_allowances': 0.0, 'day_total': 0.0})

    @api.depends('employee_id', 'period_id', 'day_basic')
    def _compute_forget_penalty(self):
        for record in self:
            engine = record._get_engine()
            if engine:
                vals = engine.calculate_forget_penalty(record.day_basic)
                record.update(vals)
            else:
                record.update({'forget_fingerprint_count': 0, 'forget_fingerprint_penalty': 0.0})

    @api.depends('day_basic', 'total_basic_allowances', 'working_days_in_period', 'employee_id.working_hours_per_day')
    def _compute_hourly_values(self):
        for record in self:
            engine = record._get_engine()
            if engine:
                vals = engine.calculate_daily_hourly_values(
                    record.basic_salary, record.total_basic_allowances, record.extra_allowances, record.working_days_in_period
                )
                record.update({
                    'hour_basic': vals.get('hour_basic', 0.0),
                    'hour_allowances': vals.get('hour_allowances', 0.0),
                    'hour_total': vals.get('hour_total', 0.0),
                })
            else:
                record.update({'hour_basic': 0.0, 'hour_allowances': 0.0, 'hour_total': 0.0})
