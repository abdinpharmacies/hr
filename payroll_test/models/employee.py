from odoo import models, fields, api

class AbHrEmployee(models.Model):
    _inherit = 'ab_hr_employee'

    daily_working_hours = fields.Float(
        string='Daily Working Hours',
        default=8.0
    )

    shift_start_time = fields.Float(
        string='Shift Start Time',
        default=8.0
    )

    hourly_basic_rate = fields.Float(
        string='Hourly Basic Rate'
    )

    hourly_allowance_rate = fields.Float(
        string='Hourly Allowance Rate'
    )

    payroll_type = fields.Selection([
        ('daily_hours', 'Daily Hours System'),
        ('monthly', 'Fixed Monthly System'),
        ('daily_wage', 'Daily Wage System'),
        ('hybrid', 'Hybrid System'),
    ], string='Payroll Type', default='daily_hours')

    payroll_rule_system_id = fields.Many2one(
        'payroll.rule.system',
        string='Payroll Rule System',
        help='Select the rule system to use for this employee'
    )

    weekly_off_1 = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='First Weekly Off', default='4')

    weekly_off_2 = fields.Selection([
        ('0', 'Monday'),
        ('1', 'Tuesday'),
        ('2', 'Wednesday'),
        ('3', 'Thursday'),
        ('4', 'Friday'),
        ('5', 'Saturday'),
        ('6', 'Sunday'),
    ], string='Second Weekly Off')

    computed_daily_rate = fields.Float(
        string='Daily Rate',
        compute='_compute_daily_rate',
        store=True
    )

    @api.depends('hourly_basic_rate', 'hourly_allowance_rate', 'daily_working_hours')
    def _compute_daily_rate(self):
        for rec in self:
            total_hourly = (rec.hourly_basic_rate or 0) + (rec.hourly_allowance_rate or 0)
            rec.computed_daily_rate = total_hourly * (rec.daily_working_hours or 8.0)

    @api.model
    def _get_translated_selection_label(self, field_name, value):
        if not value:
            return value
        field_info = self.fields_get([field_name]).get(field_name, {})
        selection = dict(field_info.get("selection", []))
        return selection.get(value, value)