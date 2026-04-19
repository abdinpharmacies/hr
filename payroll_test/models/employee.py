from odoo import models, fields, api
from .engines import ENGINE_TYPES

class AbHrEmployee(models.Model):
    _inherit = 'ab_hr_employee'

    working_hours_per_day = fields.Float(
        string='Daily Working Hours',
        default=8.0
    )
    
    shift_scheduled_start = fields.Float(
        string='Scheduled Start Time',
        default=8.0
    )
    
    hourly_rate_basic = fields.Float(
        string='Hourly Basic Wage'
    )
    
    hourly_rate_allowances = fields.Float(
        string='Hourly Allowances'
    )
    
    extra_allowance_ids = fields.One2many(
        'daily.hours.extra.allowance',
        'ab_employee_id',
        string='Extra Allowances'
    )
    
    is_delivery_staff = fields.Boolean(
        string='Delivery Staff'
    )
    
    sector = fields.Char(
        string='Sector'
    )
    
    social_insurance = fields.Float(
        string='Social Insurance'
    )
    
    health_insurance = fields.Float(
        string='Health Insurance'
    )
    
    syndicate_fund = fields.Float(
        string='Syndicate Fund'
    )
    
    payroll_rule_system_id = fields.Many2one(
        'payroll.rule.system',
        string='Payroll Policy'
    )
    
    payroll_system = fields.Selection(
        ENGINE_TYPES,
        string='Payroll Type',
        default='daily_hours'
    )
    
    weekly_off_day_1 = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='First Weekly Off', required=True, default='4')

    weekly_off_day_2 = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Second Weekly Off')

    agreement_salary = fields.Float(
        string='Agreed Salary',
        compute='_compute_agreement_salary',
        store=True
    )

    @api.depends('hourly_rate_basic', 'hourly_rate_allowances', 'working_hours_per_day', 'extra_allowance_ids.amount')
    def _compute_agreement_salary(self):
        for record in self:
            hourly_total = (record.hourly_rate_basic or 0) + (record.hourly_rate_allowances or 0)
            base_daily = hourly_total * (record.working_hours_per_day or 8.0)
            extra = sum(record.extra_allowance_ids.mapped('amount') or [0])
            record.agreement_salary = base_daily + extra