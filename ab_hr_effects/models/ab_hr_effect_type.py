# Sherif Modifications
from odoo import fields, models, api


class AbHrPayrollEffectType(models.Model):
    _name = 'ab_hr_effect_type'
    _description = 'ab_hr_effect_type'

    name = fields.Char(translate=True)
    is_basic_effect = fields.Boolean(default=False)
    # effect_logic = fields.Selection(
    #     selection=[
    #         ('add_basic_effect', 'Add Basic Effect'),
    #         ('update_basic_effect', 'Update Basic Effect'),
    #     ], )

    is_number = fields.Boolean(default=False)
    is_day_off_date = fields.Boolean(default=False)
    is_paid_vacancy = fields.Boolean(default=False)
    weekly_vacation_work_permit = fields.Boolean(default=False)
    is_hourly_effect = fields.Boolean(default=False)
    is_dual_hour_effect = fields.Boolean(default=False)
    is_reason_required = fields.Boolean(default=False)
    is_attachment_required = fields.Boolean(default=False)
    is_attendance_time_effect = fields.Boolean(default=False)
    weekly_day_off_number = fields.Selection(selection=[('1', '1'), ('2', '2'), ('3', '3'),
                                                        ('4', '4'), ('5', '5'), ('6', '6')],
                                             default=False)
    weekly_day_off_integer = fields.Integer(
        string="Weekly Day Off (Int)",
        compute='_compute_weekly_day_off_integer',
        store=True
    )
    select_day_off_number = fields.Boolean(default=False)
    basic_working_hour_number = fields.Boolean(string="Basic Working Hour Number", default=False)
    is_weekly_effect = fields.Boolean(default=False)
    is_weekday_effect = fields.Boolean(default=False)
    is_period = fields.Boolean(default=False)
    change_day_off_date = fields.Boolean(default=False)
    double_approval = fields.Boolean(string='Double Approval', default=False)
    automated_effects_note = fields.Text(string='notes')
    monthly_max_effect = fields.Integer(default=0)
    yearly_max_effect = fields.Integer(default=0)
    max_start_days_limit = fields.Integer(default=0)

    @api.depends('weekly_day_off_number')
    def _compute_weekly_day_off_integer(self):
        for rec in self:
            rec.weekly_day_off_integer = int(rec.weekly_day_off_number)
