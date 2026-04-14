from datetime import date

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class AbHrPayrollEffect(models.Model):
    _name = 'ab_hr_basic_effect'
    _description = 'ab_hr_basic_effect'
    _rec_name = 'employee_id'
    _order = 'employee_id, is_day_off_date, effect_value'

    accid = fields.Char(string="ePlus Code", related='employee_id.accid')

    employee_id = fields.Many2one('ab_hr_employee', string="Employee", required=True)

    job_status = fields.Selection(string="Job Status", related='employee_id.job_status')

    workplace = fields.Many2one('ab_hr_department', string='Workplace', related='employee_id.department_id')

    job_title = fields.Many2one('ab_hr_job', string='Job Title', related='employee_id.job_id')

    effect_type_id = fields.Many2one('ab_hr_effect_type', string="Effect Type",
                                     domain=[('is_basic_effect', '=', True)], required=True)

    weekly_day_off_integer = fields.Integer(related='effect_type_id.weekly_day_off_integer')

    select_day_off_number = fields.Boolean(related='effect_type_id.select_day_off_number')

    basic_working_hour_number = fields.Boolean(related='effect_type_id.basic_working_hour_number')
    basic_working_hour_value = fields.Float(string="Basic Working Hour Number",
                                            compute='_compute_basic_working_hour_value',
                                            digits=(6, 2))

    is_attendance_time_effect = fields.Boolean('ab_hr_effect_type',
                                               related='effect_type_id.is_attendance_time_effect')

    is_day_off_date = fields.Boolean('ab_hr_effect_type', related='effect_type_id.is_day_off_date')

    effect_value = fields.Char(string="Effect Value")

    supervision_type = fields.Selection(string="Supervision Type", related='employee_id.supervision_type')

    internal_working_employee = fields.Boolean(related='employee_id.internal_working_employee',
                                               store=True)

    active = fields.Boolean(default=True)
    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)

    @api.model
    def _get_day_off_number(self):
        day_off_number = [('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6')]
        return day_off_number

    @api.constrains('employee_id', 'effect_type_id', 'effect_value',
                    'is_day_off_date', 'weekly_day_off_integer', 'active')
    def _validate_all_constraints(self):
        previous_dates = self.env['ab_hr_employee'].sudo()._get_previous_month_date_selection()
        effect_dates = self.env['ab_hr_effect_wizard'].sudo()._get_effect_date_selection()

        weekdays_keys = [val[0] for val in self.env['ab_hr_effect_wizard'].sudo()._get_week_days_selection()]
        time_slots_keys = [val[0] for val in self.env['ab_hr_effect_wizard'].sudo()._generate_time_slots()]
        day_off_dates_keys = [val[0] for val in (previous_dates + effect_dates)]
        day_off_number_keys = [val[0] for val in self._get_day_off_number()]

        cache = {
            'weekdays_keys': set(weekdays_keys),
            'time_slots_keys': set(time_slots_keys),
            'day_off_dates_keys': set(day_off_dates_keys),
            'day_off_number_keys': set(day_off_number_keys),
        }

        for rec in self:
            rec._validate_select_right_value(cache)
            rec._validate_unique_effects_constraints()
            rec._validate_invalid_full_change_of_weekly_day_off_dates()

    def _validate_select_right_value(self, cache):
        self.ensure_one()
        rec = self

        if not rec.effect_type_id or not rec.effect_value:
            return

        if rec.basic_working_hour_number:
            try:
                float((rec.effect_value or "").strip())
            except (ValueError, AttributeError):
                raise ValidationError(_("A valid numeric value must be selected for this type of effect."))
            return

        if rec.effect_type_id.is_attendance_time_effect and rec.effect_value not in cache['time_slots_keys']:
            raise ValidationError(_("A suitable time must be selected for this type of effect."))

        if (not rec.is_day_off_date
                and rec.weekly_day_off_integer >= 1
                and rec.effect_value
                not in cache['weekdays_keys']):
            raise ValidationError(_("A suitable weekday must be selected for this type of effect."))

        if rec.is_day_off_date and rec.effect_value not in cache['day_off_dates_keys']:
            raise ValidationError(_("A valid date must be selected for this type of effect."))

        if rec.select_day_off_number and rec.effect_value not in cache['day_off_number_keys']:
            raise ValidationError(_("A valid number must be selected for this type of effect."))

    def _validate_unique_effects_constraints(self):
        self.ensure_one()
        rec = self

        if not rec.employee_id or not rec.effect_type_id:
            return

        if not rec.is_day_off_date:
            duplicate_type = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('effect_type_id', '=', rec.effect_type_id.id),
                ('active', '=', True),
            ], limit=1)
            if duplicate_type:
                raise ValidationError(_("This type of effect cannot be duplicated for the same job."))

        if rec.is_day_off_date:
            dates_count = self.search_count([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('effect_type_id', '=', rec.effect_type_id.id),
                ('active', '=', True),
            ])
            if dates_count >= 5:
                raise ValidationError(_("You cannot enter more than five weekly day-off dates."))

        if not rec.is_day_off_date and rec.weekly_day_off_integer >= 1 and rec.effect_value:
            duplicate_day = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('effect_value', '=', rec.effect_value),
                ('effect_type_id.weekly_day_off_integer', '>=', 1),
                ('active', '=', True),
            ], limit=1)
            if duplicate_day:
                raise ValidationError(
                    _("The same weekly day-off day cannot be selected more than once for the same job."))

        if rec.is_day_off_date and rec.effect_value:
            duplicate_day = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('effect_value', '=', rec.effect_value),
                ('effect_type_id.is_day_off_date', '=', True),
                ('active', '=', True),
            ], limit=1)
            if duplicate_day:
                raise ValidationError(
                    _("The same weekly day-off date cannot be selected more than once for the same job."))

        if rec.weekly_day_off_integer > 1 and not rec.is_day_off_date:
            has_primary = self.search([
                ('id', '!=', rec.id),
                ('employee_id', '=', rec.employee_id.id),
                ('effect_type_id.weekly_day_off_integer', '=', rec.weekly_day_off_integer - 1),
                ('active', '=', True),
            ], limit=1)
            if not has_primary:
                raise ValidationError(_("Weekly days off must be selected in order: first, then second, and so on."))

    def _validate_invalid_full_change_of_weekly_day_off_dates(self):
        self.ensure_one()
        rec = self
        if self.env.context.get('skip_weekly_day_off_full_change_validation'):
            return

        if not (rec.is_day_off_date
                and rec.active
                and rec.weekly_day_off_integer
                and rec.effect_value
                and rec.employee_id):
            return

        job = rec.employee_id
        week_off_order = rec.weekly_day_off_integer

        week_day_record = self.search([
            ('employee_id', '=', job.id),
            ('is_day_off_date', '=', False),
            ('weekly_day_off_integer', '=', week_off_order),
            ('active', '=', True),
        ], limit=1)

        if not week_day_record or not week_day_record.effect_value:
            return

        weekday_key = week_day_record.effect_value.lower()

        related_effects = self.search([
            ('employee_id', '=', job.id),
            ('is_day_off_date', '=', True),
            ('weekly_day_off_integer', '=', week_off_order),
            ('active', '=', True),
        ])

        others = related_effects.filtered(lambda r: r.id != rec.id)
        all_dates = {rec.effect_value} | {r.effect_value for r in others if r.effect_value}

        if len(all_dates) == 5:
            valid_dates = {dt_str for dt_str, __ in job._get_weekly_vacancy_dates(weekday_key)}
            if not (all_dates & valid_dates):
                raise ValidationError(_("You cannot change all weekly day-off dates"
                                        " for a specific weekly day off when the total is 5 days."))

    @api.depends_context('show_effect_value_only')
    @api.depends('effect_value', 'employee_id')
    def _compute_display_name(self):
        use_effect_value = self.env.context.get('show_effect_value_only')
        for record in self:
            if use_effect_value:
                record.display_name = record.effect_value or 'No Value'
            else:
                record.display_name = (record.employee_id.display_name
                                       or record.effect_value
                                       or '')

    @api.depends('effect_value', 'basic_working_hour_number')
    def _compute_basic_working_hour_value(self):
        for rec in self:
            if not rec.basic_working_hour_number or not rec.effect_value:
                rec.basic_working_hour_value = 0.0
                continue
            raw = rec.effect_value.strip() if isinstance(rec.effect_value, str) else rec.effect_value
            if isinstance(raw, (int, float)):
                rec.basic_working_hour_value = float(raw)
                continue
            if isinstance(raw, str) and ':' in raw:
                parts = raw.split(':', 1)
                try:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                except (ValueError, TypeError):
                    rec.basic_working_hour_value = 0.0
                    continue
                rec.basic_working_hour_value = hours + (minutes / 60.0)
                continue
            try:
                rec.basic_working_hour_value = float(raw)
            except (ValueError, TypeError):
                rec.basic_working_hour_value = 0.0

    # def _constrains_ab_hr_effect_wiz(self):
    #     self._check_monthly_max_effect()
    #     self._check_yearly_max_effect()
    #     self._check_monthly_weekly_vacancies()
    #     self._check_effect_date_within_job_period()
    #     self._check_original_fp_time()
    #
    # def _check_monthly_max_effect(self):
    #     start, end = self._pay_period_bounds()
    #     limit = self.effect_type_id.monthly_max_effect or 0
    #
    #     msg = _("The annual maximum limit for '%(name)s' in the period "
    #             "%(start)s → %(end)s is %(limit)s. You are trying to assign %(actual)s %(name)s to the employee.")
    #
    #     self._check_max(start, end, limit, msg)
    #
    # def _check_yearly_max_effect(self):
    #     start, end = self._get_payroll_year_bounds()
    #     limit = self.effect_type_id.yearly_max_effect or 0
    #
    #     msg = _("The annual maximum number of '%(name)s' allowed during the period "
    #             "%(start)s → %(end)s is %(limit)s. You are trying to assign %(actual)s %(name)s to the employee.")
    #
    #     self._check_max(start, end, limit, msg)
    #
    # def _check_monthly_weekly_vacancies(self):
    #     valid = [d[0] for d in self._get_effect_date_selection()]
    #     for wiz in self:
    #         if wiz.monthly_weekly_vacancies and wiz.monthly_weekly_vacancies not in valid:
    #             raise ValidationError(_("You can`t replace a day-off for a previous month"))
    #
    # def _check_effect_date_within_job_period(self):
    #     today = date.today()
    #     if not self.effect_date or not self.employee_id:
    #         return
    #
    #     # تحويل effect_date من str إلى date
    #     effect_date = fields.Date.from_string(self.effect_date)
    #
    #     hiring_date = self.employee_id.hiring_date
    #     termination_date = self.employee_id.termination_date
    #     max_start_days_limit = self.max_start_days_limit
    #
    #     if hiring_date and effect_date < hiring_date and not self.basic_effect:
    #         raise ValidationError(_("Effect date can`t be before hiring date."))
    #
    #     if termination_date and effect_date > termination_date:
    #         print(termination_date)
    #         raise ValidationError(_("Effect date can`t be after termination date."))
    #
    #     if termination_date and today > (termination_date + timedelta(days=7)):
    #         raise ValidationError(_("You only allowed to add effect 7 days after termination date."))
    #
    #     if hiring_date and max_start_days_limit > 0 and \
    #             effect_date < (hiring_date + timedelta(days=max_start_days_limit)):
    #         raise ValidationError(_(
    #             "Effect date can't be before %s days after hiring date.") % max_start_days_limit)
    #
    # def _check_original_fp_time(self):
    #     if self.basic_effect:
    #         return
    #
    #     original_attendance = self.sudo().attendance_time
    #     if self.is_attendance_time_effect and not original_attendance:
    #         raise ValidationError(_("Shift change is not allowed unless the employee has"
    #                                 " an original assigned shift time."))
    #
    #     if self.is_attendance_time_effect and self.hour_value and self.attendance_time:
    #         if self.supervision_type == 'indirect':
    #             return
    #
    #         fmt = "%H:%M"
    #         try:
    #             attendance_dt = datetime.strptime(self.attendance_time, fmt)
    #             hour_value_dt = datetime.strptime(self.hour_value, fmt)
    #         except ValueError:
    #             raise ValidationError(_("Time format must be HH:MM, e.g. 08:30 or 17:00"))
    #
    #         diff = (hour_value_dt - attendance_dt).total_seconds() / 60
    #
    #         if 0 <= diff <= 60:
    #             raise ValidationError(_("You cannot change the shift time for a direct subordinate to a time "
    #                                     "less than one hour after the general shift time. "
    #                                     "Please contact your manager to explain the reason for the shift change "
    #                                     "so they can apply this effect for the employee."))
