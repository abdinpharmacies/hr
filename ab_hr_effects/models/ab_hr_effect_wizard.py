from odoo import api, fields, models, _
from datetime import date, timedelta, datetime
from odoo.exceptions import UserError, ValidationError


class AbHrEffectsWizard(models.Model):
    _name = 'ab_hr_effect_wizard'
    _description = 'ab_hr_effect_wizard'
    _inherit = 'ab_hr_effect_mixin'

    employee_id = fields.Many2one('ab_hr_employee', string="Employee", readonly=True,
                                  default=lambda self: self._get_context_employee_id())

    effect_type_id = fields.Many2one('ab_hr_effect_type', string="Effect Type", required=True)
    allowed_effect_type_ids = fields.Many2many(
        'ab_hr_effect_type',
        compute='_compute_allowed_effect_type_ids',
        store=False,
    )

    basic_effect = fields.Boolean(related='effect_type_id.is_basic_effect')

    is_number = fields.Boolean(related='effect_type_id.is_number')

    is_hourly_effect = fields.Boolean(related='effect_type_id.is_hourly_effect')

    is_dual_hour_effect = fields.Boolean(related='effect_type_id.is_dual_hour_effect')

    is_reason_required = fields.Boolean(related='effect_type_id.is_reason_required')

    is_attachment_required = fields.Boolean(related='effect_type_id.is_attachment_required')

    is_attendance_time_effect = fields.Boolean(related='effect_type_id.is_attendance_time_effect')

    select_day_off_number = fields.Boolean(related='effect_type_id.select_day_off_number')
    basic_working_hour_number = fields.Boolean(related='effect_type_id.basic_working_hour_number')

    is_weekly_effect = fields.Boolean(related='effect_type_id.is_weekly_effect')
    is_weekday_effect = fields.Boolean(related='effect_type_id.is_weekday_effect')
    change_day_off_date = fields.Boolean(related='effect_type_id.change_day_off_date')

    weekly_vacation_work_permit = fields.Boolean(related='effect_type_id.weekly_vacation_work_permit')

    weekly_day_off_integer = fields.Integer(related='effect_type_id.weekly_day_off_integer')

    is_day_off_date = fields.Boolean(related='effect_type_id.is_day_off_date')

    is_period = fields.Boolean(related='effect_type_id.is_period')

    delay_to_send_effect = fields.Boolean(related='employee_id.delay_to_send_effect')

    automated_effects_note = fields.Text(related='effect_type_id.automated_effects_note')

    monthly_max_effect = fields.Integer(related='effect_type_id.monthly_max_effect')

    yearly_max_effect = fields.Integer(related='effect_type_id.yearly_max_effect')

    double_approval = fields.Boolean(compute='_compute_double_approval', store=False)

    max_effects_info_html = fields.Html(string="Effect Info", compute="_compute_html_effects_info", sanitize=True)

    max_start_days_limit = fields.Integer(related='effect_type_id.max_start_days_limit')

    accid = fields.Char(string="ePlus Code", related='employee_id.accid')

    workplace = fields.Many2one('ab_hr_department', string="Department", related='employee_id.department_id')

    job_title = fields.Many2one('ab_hr_job', string="Job", related='employee_id.job_id')

    job_info_html = fields.Html(string="Job Info", compute="_compute_job_info_html", sanitize=True)

    effect_month_count = fields.Integer(string="Count in Month", compute='_compute_effect_month_count', store=False)

    effect_payroll_year_count = fields.Integer(string="Count in Payroll Year",
                                               compute='_compute_effect_count_from_dec21')

    day_off = fields.One2many(related='employee_id.day_off')

    day_off_exist = fields.Boolean(related='employee_id.day_off_exist')

    day_off_dates = fields.One2many(related='employee_id.day_off_dates')

    supervision_type = fields.Selection(string="Supervision Type",
                                        related='employee_id.supervision_type', readonly=True)

    attendance_time = fields.Selection(string="Attendance Time", related='employee_id.attendance_time')

    periodic_effect = fields.Boolean(string="Periodic Effect", default=False)

    weekly_effect = fields.Boolean(string="Weekly Effect", default=False)

    yearly_effect = fields.Boolean(string="Weekly Effect", default=False)

    effect_numerical_value = fields.Float(string="Numeric Value", digits=(6, 2))

    hour_value = fields.Selection(string="Hour Value", selection=lambda self: self._generate_time_slots())

    second_hour_value = fields.Selection(string="Second Hour Value",
                                         selection=lambda self: self._generate_time_slots())

    effect_reason = fields.Text(string="Reason / Notes")

    effect_date = fields.Date(string="Effect Date", required=True)

    end_date = fields.Date(string="End Date", help="Must be within the allowed effect date range.")

    monthly_weekly_vacancies = fields.Date(string="Weekly Vacancies")

    effect_weekday = fields.Selection(selection='_get_week_days_selection', string="Weekday")

    weekly_day_off_number = fields.Selection(string="Weekly Day Off Number",
                                             selection=[('1', '1'), ('2', '2'), ('3', '3'),
                                                        ('4', '4'), ('5', '5'), ('6', '6')])

    attached_file = fields.Binary(string="Attachment")
    effect_status = fields.Selection([
        ('draft', 'Draft'),
        ('direct_manager_review', 'Direct Manager Review'),
        ('upper_manager_review', 'Upper Manager Review'),
        ('under_application', 'Under Application'),
        ('applied', 'Applied'),
        ('rejected', 'Rejected'),
        ('archived', 'Archived'),
    ], string="Effect Status", default='draft', tracking=True, index=True)
    is_hr_manager = fields.Boolean(compute='_compute_is_hr_manager', store=False)
    is_payroll_user = fields.Boolean(compute='_compute_is_payroll_user', store=False)
    can_edit_postsave = fields.Boolean(compute='_compute_can_edit_postsave', store=False)

    effect_line_ids = fields.One2many('ab_hr_effect', 'wizard_id', string='Effects')

    def _get_context_employee_id(self):
        ctx = self.env.context
        employee_id = ctx.get('default_employee_id')
        if employee_id:
            return employee_id

        params = ctx.get('params') or {}
        if params.get('model') == 'ab_hr_employee' and params.get('id'):
            return params['id']

        if ctx.get('active_model') == 'ab_hr_employee':
            if ctx.get('active_id'):
                return ctx['active_id']
            active_ids = ctx.get('active_ids') or []
            if len(active_ids) == 1:
                return active_ids[0]
        return False

    @api.model_create_multi
    def create(self, vals_list):
        context_employee_id = self._get_context_employee_id()
        for vals in vals_list:
            if not vals.get('employee_id') and context_employee_id:
                vals['employee_id'] = context_employee_id
            effect_type_id = vals.get('effect_type_id') or self.env.context.get('default_effect_type_id')
            if (effect_type_id
                    and vals.get('monthly_weekly_vacancies')
                    and self.env['ab_hr_effect_type'].browse(effect_type_id).weekly_vacation_work_permit):
                vals.setdefault('effect_date', vals['monthly_weekly_vacancies'])
        if self.env.context.get('sudo_wizard_create'):
            return super(AbHrEffectsWizard, self.sudo()).create(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if 'monthly_weekly_vacancies' in vals:
            effect_type_id = vals.get('effect_type_id')
            if not effect_type_id and len(self) == 1:
                effect_type_id = self.effect_type_id.id
            if (effect_type_id
                    and self.env['ab_hr_effect_type'].browse(effect_type_id).weekly_vacation_work_permit):
                vals = dict(vals)
                vals.setdefault('effect_date', vals['monthly_weekly_vacancies'])
        return super().write(vals)

    # @api.depends('effect_month_count')
    @api.depends('employee_id')
    def _compute_job_info_html(self):
        for rec in self:
            accid = rec.accid or ""
            employee = rec.employee_id.name or ""
            job_title = rec.job_title.name or ""
            workplace = rec.workplace.name or ""

            rec.job_info_html = f"""
                <div style="text-align: center; font-size: 16px; color: #333;">
                    <h2 style="margin-bottom: 10px; font-size: 32px; color: #888;">{accid}</h2>
                    <h2 style="margin-bottom: 20px; color: #17a2b8;">{employee}</h3>
    
                    <table style="margin: auto; border-collapse: collapse;">
                        <tr>
                            <td style="padding: 8px 16px; border: 1px solid #ccc; color: #17a2b8;">{job_title}</td>
                            <td style="padding: 8px 16px; border: 1px solid #ccc; color: #17a2b8;">{workplace}</td>
                        </tr>
                    </table>
                </div>
            """

    @api.depends('effect_month_count', 'effect_payroll_year_count', 'monthly_max_effect', 'yearly_max_effect')
    def _compute_html_effects_info(self):
        for rec in self:
            monthly_limit = rec.monthly_max_effect or _("No limit")
            yearly_limit = rec.yearly_max_effect or _("No limit")

            rec.max_effects_info_html = f"""
                    <div style="font-size: 14px;">
                        <table style="width: 100%; border-collapse: collapse;">
                            <thead>
                                <tr style="background-color: #f0f0f0;">
                                    <th style="padding: 8px; border: 1px solid #ccc;">{_("Monthly Count")}</th>
                                    <th style="padding: 8px; border: 1px solid #ccc;">{_("Monthly Limit")}</th>
                                    <th style="padding: 8px; border: 1px solid #ccc;">{_("Yearly Count")}</th>
                                    <th style="padding: 8px; border: 1px solid #ccc;">{_("Yearly Limit")}</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td style="padding: 8px; border: 1px solid #ccc;">{rec.effect_month_count}</td>
                                    <td style="padding: 8px; border: 1px solid #ccc;">{monthly_limit}</td>
                                    <td style="padding: 8px; border: 1px solid #ccc;">{rec.effect_payroll_year_count}
                                    </td>
                                    <td style="padding: 8px; border: 1px solid #ccc;">{yearly_limit}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                """

    @api.depends_context('uid')
    def _compute_is_hr_manager(self):
        is_manager = self.env.user.has_group('ab_hr.group_ab_hr_manager')
        for rec in self:
            rec.is_hr_manager = is_manager

    @api.depends_context('uid')
    def _compute_is_payroll_user(self):
        user = self.env.user
        is_payroll = (user.has_group('ab_hr.group_ab_hr_payroll_specialist')
                      or user.has_group('ab_hr.group_ab_hr_co'))
        for rec in self:
            rec.is_payroll_user = is_payroll

    @api.depends_context('uid')
    def _compute_can_edit_postsave(self):
        user = self.env.user
        can_edit = (user.has_group('ab_hr.group_ab_hr_co')
                    or user.has_group('ab_hr.group_ab_hr_payroll_reviewer'))
        for rec in self:
            rec.can_edit_postsave = can_edit

    def _get_effect_type_domain_for_supervision(self):
        self.ensure_one()

        user = self.env.user
        is_reviewer = user.has_group('ab_hr.group_ab_hr_payroll_reviewer')
        is_co = user.has_group('ab_hr.group_ab_hr_co')

        domain = fields.Domain('is_day_off_date', '=', False)

        if self.supervision_type in ['myself', 'workplace_manager_job']:
            domain &= fields.Domain('is_basic_effect', '=', False)
            domain &= fields.Domain('weekly_day_off_integer', '=', 0)

        if not (is_reviewer or is_co):
            domain &= fields.Domain('select_day_off_number', '=', False)
            domain &= fields.Domain('basic_working_hour_number', '=', False)

        employee_weekly_day_off_integer = self.employee_id.weekly_day_off_integer if self.employee_id else 0
        if employee_weekly_day_off_integer:
            domain &= (
                    fields.Domain('is_basic_effect', '=', False)
                    | fields.Domain('weekly_day_off_integer', '<=', employee_weekly_day_off_integer)
            )

        return list(domain)

    @api.depends('employee_id', 'supervision_type')
    @api.depends_context('uid')
    def _compute_allowed_effect_type_ids(self):
        effect_type_model = self.env['ab_hr_effect_type']
        for rec in self:
            rec.allowed_effect_type_ids = effect_type_model.search(rec._get_effect_type_domain_for_supervision())

    @api.depends('effect_type_id.double_approval', 'is_attendance_time_effect', 'hour_value', 'attendance_time')
    def _compute_double_approval(self):
        fmt = "%H:%M"
        for rec in self:
            needs_double = False
            if rec.is_attendance_time_effect and rec.is_hourly_effect and rec.hour_value:
                original_time = rec._get_original_attendance_time_value()
                if original_time:
                    attendance_dt = datetime.strptime(original_time, fmt)
                    hour_value_dt = datetime.strptime(rec.hour_value, fmt)
                    diff = (hour_value_dt - attendance_dt).total_seconds() / 60
                    if 0 <= diff <= 60:
                        needs_double = True
            rec.double_approval = bool(rec.effect_type_id.double_approval or needs_double)

    def _get_original_attendance_time_value(self):
        self.ensure_one()
        if not self.employee_id:
            return False

        basic_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_type_id.is_attendance_time_effect', '=', True),
            ('effect_type_id.is_hourly_effect', '=', True),
            ('active', '=', True),
        ]
        basic = self.env['ab_hr_basic_effect'].search(basic_domain, limit=1)
        if basic and basic.effect_value:
            return basic.effect_value

        start, end = self._pay_period_bounds()
        wizard_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_type_id.is_attendance_time_effect', '=', True),
            ('effect_type_id.is_hourly_effect', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected']),
        ]
        if self.id:
            wizard_domain.append(('id', '!=', self.id))

        for wiz in self.search(wizard_domain, order='id desc'):
            dates = wiz._get_requested_effect_dates(use_yearly_scope=False)
            if not dates and wiz.effect_date:
                dates = [fields.Date.to_date(wiz.effect_date)]
            if any(start <= d <= end for d in dates) and wiz.hour_value:
                return wiz.hour_value

        return False

    def _has_attendance_time_effect_in_pay_period(self):
        self.ensure_one()
        if not self.employee_id:
            return False

        start, end = self._pay_period_bounds()
        basic_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_type_id.is_attendance_time_effect', '=', True),
            ('effect_type_id.is_hourly_effect', '=', True),
            ('active', '=', True),
        ]
        if self.env['ab_hr_basic_effect'].search(basic_domain, limit=1):
            return True

        wizard_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_type_id.is_attendance_time_effect', '=', True),
            ('effect_type_id.is_hourly_effect', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected', 'applied']),
        ]
        if self.id:
            wizard_domain.append(('id', '!=', self.id))

        for wiz in self.search(wizard_domain):
            dates = wiz._get_requested_effect_dates(use_yearly_scope=False)
            if not dates and wiz.effect_date:
                dates = [fields.Date.to_date(wiz.effect_date)]
            if any(start <= d <= end for d in dates):
                return True

        return False

    def _has_any_attendance_time_effect(self):
        self.ensure_one()
        if not self.employee_id:
            return False

        basic_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_type_id.is_attendance_time_effect', '=', True),
            ('effect_type_id.is_hourly_effect', '=', True),
            ('active', '=', True),
        ]
        if self.env['ab_hr_basic_effect'].search(basic_domain, limit=1):
            return True

        wizard_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_type_id.is_attendance_time_effect', '=', True),
            ('effect_type_id.is_hourly_effect', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected']),
        ]
        if self.id:
            wizard_domain.append(('id', '!=', self.id))
        return bool(self.search(wizard_domain, limit=1))

    def _get_monthly_weekly_vacancies(self):
        candidates = self._get_monthly_weekly_vacancy_candidates()
        return [(v, v) for v in candidates]

    def _get_monthly_weekly_vacancy_candidates(self):
        employee = self.employee_id
        if not employee:
            employee_id = self.env.context.get('default_employee_id')
            if employee_id:
                employee = self.env['ab_hr_employee'].browse(employee_id)

        if not employee:
            return []

        allowed_dates = {d[0] for d in self._get_effect_date_selection()}
        base_dates = set()
        weekly_day_offs = employee.day_off.filtered(lambda r: r.active and r.effect_value)
        for rec in weekly_day_offs:
            weekday_key = rec.effect_value.lower()
            base_dates.update(
                dt_str for dt_str, _ in employee._get_weekly_vacancy_dates(weekday_key)
                if dt_str in allowed_dates
            )

        day_off_effects = employee.day_off_dates.filtered(
            lambda r: r.active and r.effect_value in allowed_dates
        ).sorted(key=lambda r: r.effect_value)
        day_off_values = {v for v in day_off_effects.mapped('effect_value') if v}
        base_dates.update(day_off_values)

        weekday_indexes = {date.fromisoformat(v).weekday() for v in day_off_values}
        if self.change_day_off_date or self.weekly_vacation_work_permit:
            old_dates = self._get_changed_weekly_day_off_old_dates(employee, allowed_dates)
            weekday_indexes.update({date.fromisoformat(v).weekday() for v in old_dates})
        for idx in weekday_indexes:
            for dt_str, _ in self._get_effect_date_selection():
                if dt_str in allowed_dates and date.fromisoformat(dt_str).weekday() == idx:
                    base_dates.add(dt_str)

        if base_dates:
            values = set(base_dates)
            if self.change_day_off_date or self.weekly_vacation_work_permit:
                replacements = self._get_changed_weekly_day_off_replacements(employee, allowed_dates)
                old_dates = {old_val for old_val, _new_val in replacements}
                new_dates = {new_val for _old_val, new_val in replacements}
                values -= old_dates
                values |= new_dates
            return sorted(values)

        current_weekly = self.weekly_day_off_integer or 0
        effect_domain = [
            ('employee_id', '=', employee.id),
            ('effect_type_id.is_paid_vacancy', '=', True),
            ('effect_type_id.is_weekday_effect', '=', True),
            ('active', '=', True),
        ]
        wizard_domain = [
            ('employee_id', '=', employee.id),
            ('effect_type_id.is_paid_vacancy', '=', True),
            ('effect_type_id.is_weekday_effect', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected']),
        ]
        if current_weekly:
            effect_domain.append(('effect_type_id.weekly_day_off_integer', '!=', current_weekly))
            wizard_domain.append(('effect_type_id.weekly_day_off_integer', '!=', current_weekly))

        weekdays = set()
        for eff in self.env['ab_hr_effect'].search(effect_domain, order='effect_date desc'):
            if eff.effect_weekday:
                weekdays.add(eff.effect_weekday)
        if self.id:
            wizard_domain.append(('id', '!=', self.id))
        for wiz in self.search(wizard_domain):
            if wiz.effect_weekday:
                weekdays.add(wiz.effect_weekday)

        fallback_dates = set()
        for weekday in weekdays:
            fallback_dates.update(self._get_dates_for_weekday_in_period(weekday))

        if self.change_day_off_date or self.weekly_vacation_work_permit:
            replacements = self._get_changed_weekly_day_off_replacements(employee, allowed_dates)
            old_dates = {old_val for old_val, _new_val in replacements}
            new_dates = {new_val for _old_val, new_val in replacements}
            fallback_dates -= old_dates
            fallback_dates |= new_dates
        return sorted(fallback_dates)

    def _get_changed_weekly_day_off_replacements(self, employee, allowed_dates):
        replacements = []

        effect_domain = [
            ('employee_id', '=', employee.id),
            ('effect_type_id.change_day_off_date', '=', True),
            ('active', '=', True),
        ]
        for eff in self.env['ab_hr_effect'].search(effect_domain):
            if not (eff.monthly_weekly_vacancies and eff.effect_date):
                continue
            old_val = fields.Date.to_string(eff.monthly_weekly_vacancies)
            new_val = fields.Date.to_string(eff.effect_date)
            if old_val in allowed_dates and new_val in allowed_dates:
                replacements.append((old_val, new_val))

        wizard_domain = [
            ('employee_id', '=', employee.id),
            ('effect_type_id.change_day_off_date', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected']),
        ]
        if self.id:
            wizard_domain.append(('id', '!=', self.id))
        for wiz in self.search(wizard_domain):
            if not (wiz.monthly_weekly_vacancies and wiz.effect_date):
                continue
            old_val = fields.Date.to_string(wiz.monthly_weekly_vacancies)
            new_val = fields.Date.to_string(wiz.effect_date)
            if old_val in allowed_dates and new_val in allowed_dates:
                replacements.append((old_val, new_val))

        return replacements

    def _get_changed_weekly_day_off_old_dates(self, employee, allowed_dates):
        old_dates = set()

        effect_domain = [
            ('employee_id', '=', employee.id),
            ('effect_type_id.change_day_off_date', '=', True),
            ('active', '=', True),
        ]
        for eff in self.env['ab_hr_effect'].search(effect_domain):
            if not eff.monthly_weekly_vacancies:
                continue
            old_val = fields.Date.to_string(eff.monthly_weekly_vacancies)
            if old_val in allowed_dates:
                old_dates.add(old_val)

        wizard_domain = [
            ('employee_id', '=', employee.id),
            ('effect_type_id.change_day_off_date', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected']),
        ]
        if self.id:
            wizard_domain.append(('id', '!=', self.id))
        for wiz in self.search(wizard_domain):
            if not wiz.monthly_weekly_vacancies:
                continue
            old_val = fields.Date.to_string(wiz.monthly_weekly_vacancies)
            if old_val in allowed_dates:
                old_dates.add(old_val)

        return old_dates

    def _get_dates_for_weekday_in_period(self, weekday_key):
        weekday_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }
        target_weekday = weekday_map.get(weekday_key)
        if target_weekday is None:
            return []
        dates = self._get_effect_date_selection()
        return [
            dt_str for dt_str, _ in dates
            if date.fromisoformat(dt_str).weekday() == target_weekday
        ]

    def _get_allowed_monthly_weekly_vacancy_values(self):
        return set(self._get_monthly_weekly_vacancy_candidates())

    @api.model
    def _get_effect_date_selection(self):
        employee = self.employee_id
        if not employee:
            employee_id = self.env.context.get('default_employee_id')
            if employee_id:
                employee = self.env['ab_hr_employee'].browse(employee_id)

        if employee and employee.delay_to_send_effect:
            return employee._get_previous_month_date_selection()

        return super()._get_effect_date_selection()

    def _get_effect_weekday_options(self):
        weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                       'friday': 4, 'saturday': 5, 'sunday': 6}
        target_weekday = weekday_map.get(self.effect_weekday)
        if target_weekday is None:
            return []

        dates = self._get_effect_date_selection()
        return [
            dt_str for dt_str, _ in dates
            if date.fromisoformat(dt_str).weekday() == target_weekday
        ]

    def _ensure_effect_dates_within_selection(self):
        allowed = {d[0] for d in self._get_effect_date_selection()}
        if self.effect_date:
            effect_date_str = fields.Date.to_string(self.effect_date)
            if effect_date_str not in allowed:
                raise ValidationError(_("Effect date must be within the allowed date range."))
        if self.end_date:
            end_date_str = fields.Date.to_string(self.end_date)
            if end_date_str not in allowed:
                raise ValidationError(_("End date must be within the allowed date range."))

    def _ensure_weekday_required(self):
        self.ensure_one()
        if (self.is_weekday_effect or self.weekly_effect) and not self.effect_weekday:
            raise ValidationError(_("Week Day is required for this effect type."))

    def _get_effect_yearly_weekday_options(self):
        today = fields.Date.context_today(self)
        weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2,
                       'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
        target_weekday = weekday_map.get(self.effect_weekday)
        if target_weekday is None:
            return []

        if today < (today.replace(month=12)).replace(day=21):
            if today.day < 21:
                start = (today.replace(day=1) - timedelta(days=1)).replace(day=21)
                end = date(today.year, 12, 20)
            else:
                start = today.replace(day=21)
                end = date(today.year, 12, 20)
        else:
            start = date(today.year, 12, 21)
            end = date(today.year + 1, 12, 20)
        delta = end - start
        dates = [(start + timedelta(days=i)).isoformat() for i in range(delta.days + 1)]
        return [
            dt_str for dt_str in dates
            if date.fromisoformat(dt_str).weekday() == target_weekday
        ]

    def _get_requested_effect_dates(self, use_yearly_scope=False):
        self.ensure_one()
        if self.periodic_effect:
            if not self.effect_date:
                return []
            start = fields.Date.from_string(self.effect_date)
            end = fields.Date.from_string(self.end_date) if self.end_date else start
            if end < start:
                return []
            return [start + timedelta(days=i) for i in range((end - start).days + 1)]

        if self.weekly_effect and self.effect_weekday:
            if use_yearly_scope and self.yearly_effect:
                dates = self._get_effect_yearly_weekday_options()
            else:
                dates = self._get_effect_weekday_options()
            return [date.fromisoformat(dt_str) for dt_str in dates]

        if self.effect_date:
            return [fields.Date.from_string(self.effect_date)]

        return []

    def _get_paid_vacancy_validation_dates(self):
        self.ensure_one()
        if self.is_weekday_effect and self.effect_weekday:
            dates = self._get_effect_weekday_options()
            return [date.fromisoformat(dt_str) for dt_str in dates]
        return self._get_requested_effect_dates(use_yearly_scope=True)

    def _get_count_between(self, start, end):
        ds, de = start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')

        base_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('active', '=', True),
            ('effect_date', '>=', ds),
            ('effect_date', '<=', de)
        ]
        effects_count = self.env['ab_hr_effect'].search_count(base_domain)
        wizard_count = self._get_wizard_count_between(start, end)

        return effects_count + wizard_count

    def _get_wizard_count_between(self, start, end):
        if not self.employee_id or not self.effect_type_id:
            return 0

        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('effect_status', 'not in', ['archived', 'rejected', 'applied']),
        ]
        if self.id:
            domain.append(('id', '!=', self.id))

        total = 0
        for wiz in self.search(domain):
            dates = wiz._get_requested_effect_dates(use_yearly_scope=True)
            total += sum(1 for d in dates if start <= d <= end)
        return total

    @api.depends('employee_id', 'effect_type_id', 'effect_date')
    def _compute_effect_month_count(self):
        for rec in self:
            start, end = rec._pay_period_bounds()
            rec.effect_month_count = rec._get_count_between(start, end)

    @api.depends('employee_id', 'effect_type_id', 'effect_date')
    def _compute_effect_count_from_dec21(self):
        for rec in self:
            start, end = rec._get_payroll_year_bounds()
            rec.effect_payroll_year_count = rec._get_count_between(start, end)

    def _check_max(self, start, end, limit, msg, use_yearly_scope=False):
        if not limit:
            return

        existing = self._get_count_between(start, end)
        new_count = len([
            d for d in self._get_requested_effect_dates(use_yearly_scope=use_yearly_scope)
            if start <= d <= end
        ])

        if not new_count:
            return

        if existing + new_count > limit:
            raise ValidationError(msg % {
                'name': self.effect_type_id.name,
                'limit': limit,
                'actual': existing + new_count,
                'start': start.strftime('%Y-%m-%d'),
                'end': end.strftime('%Y-%m-%d'),
            })

    def _check_effect_dates_in_job_period(self):
        if not self.employee_id:
            return

        effect_dates = self._get_requested_effect_dates(use_yearly_scope=True)
        if not effect_dates:
            return

        start_date = min(effect_dates)
        end_date = max(effect_dates)
        hiring_date = self.employee_id.hiring_date
        termination_date = self.employee_id.termination_date
        max_start_days_limit = self.max_start_days_limit or 0

        if hiring_date and start_date < hiring_date and not self.effect_type_id.is_basic_effect:
            raise ValidationError(_("Effect date cannot be before the hiring date (%s).") % hiring_date)
        if hiring_date and max_start_days_limit > 0:
            limit_date = hiring_date + timedelta(days=max_start_days_limit)
            if start_date < limit_date:
                raise ValidationError(_(
                    "Effect date cannot be earlier   than %s days after the hiring date (%s).")
                                      % (max_start_days_limit, hiring_date))

        if termination_date:
            latest_allowed = termination_date + timedelta(days=7)
            if end_date > latest_allowed:
                raise ValidationError(_("Effect date cannot be later than 7 days after end of service (%s).")
                                      % termination_date)

    def _check_duplicate_wizard_data(self):
        self.ensure_one()
        if not self.employee_id or not self.effect_type_id:
            return

        domain = [
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('effect_status', 'not in', ['archived', 'rejected']),
            ('effect_date', '=', self.effect_date),
            ('end_date', '=', self.end_date),
            ('periodic_effect', '=', self.periodic_effect),
            ('weekly_effect', '=', self.weekly_effect),
            ('yearly_effect', '=', self.yearly_effect),
            ('effect_weekday', '=', self.effect_weekday),
            ('hour_value', '=', self.hour_value),
            ('second_hour_value', '=', self.second_hour_value),
            ('effect_numerical_value', '=', self.effect_numerical_value),
            ('monthly_weekly_vacancies', '=', self.monthly_weekly_vacancies),
            ('weekly_day_off_number', '=', self.weekly_day_off_number),
        ]

        if self.search_count(domain):
            raise ValidationError(_("This effect request already exists."))

    def _check_duplicate_effect_dates(self):
        self.ensure_one()
        if not self.employee_id or not self.effect_type_id:
            return

        requested_dates = self._get_requested_effect_dates(use_yearly_scope=True)
        if not requested_dates:
            return

        date_values = [d.strftime('%Y-%m-%d') for d in requested_dates]

        effect_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('effect_date', 'in', date_values),
            ('active', '=', True),
        ]
        if self.env['ab_hr_effect'].search_count(effect_domain):
            raise ValidationError(_("The employee already has the same effect on one or more selected dates."))

        wizard_domain = [
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('effect_status', 'not in', ['archived', 'rejected', 'applied']),
        ]
        for wiz in self.search(wizard_domain):
            existing_dates = wiz._get_requested_effect_dates(use_yearly_scope=True)
            if any(d in requested_dates for d in existing_dates):
                raise ValidationError(_("The employee already has a pending request for the same effect dates."))

    def _check_basic_effect_unique_in_pay_period(self):
        self.ensure_one()
        if not (self.employee_id and self.effect_type_id and self.basic_effect):
            return

        start, end = self._pay_period_bounds()
        effect_domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('active', '=', True),
            ('effect_date', '>=', start.strftime('%Y-%m-%d')),
            ('effect_date', '<=', end.strftime('%Y-%m-%d')),
        ]
        if self.env['ab_hr_effect'].search_count(effect_domain):
            raise ValidationError(_("A basic effect of this type already exists in the payroll month. "
                                    "Archive the previous effect first."))

        wizard_domain = [
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('effect_status', '!=', 'archived'),
        ]
        for wiz in self.search(wizard_domain):
            dates = wiz._get_requested_effect_dates(use_yearly_scope=False)
            if not dates and wiz.effect_date:
                dates = [fields.Date.to_date(wiz.effect_date)]
            if any(start <= d <= end for d in dates):
                raise ValidationError(_("A basic effect of this type already exists in the payroll month. "
                                        "Archive the previous effect first."))

    def _validate_limits_and_dates(self):
        self.ensure_one()
        if self._is_hr_manager():
            return
        if not self.employee_id or not self.effect_type_id:
            return

        self._ensure_weekday_required()

        self._ensure_effect_dates_within_selection()

        if (self.is_attendance_time_effect
                and self.is_hourly_effect
                and not self.basic_effect
                and not self._has_any_attendance_time_effect()):
            raise ValidationError(
                "Shift change is not allowed unless the employee has an original assigned shift time.")

        if self.periodic_effect and self.effect_date and self.end_date:
            start = fields.Date.from_string(self.effect_date)
            end = fields.Date.from_string(self.end_date)
            if end < start:
                raise ValidationError(_("The end date of the period cannot be earlier than the start date."))

        if not self._is_hr_manager():
            start, end = self._pay_period_bounds()
            monthly_limit = self.monthly_max_effect or 0
            if monthly_limit:
                self._check_max(start, end, monthly_limit,
                                _("Monthly limit exceeded for %(name)s (%(actual)s/%(limit)s) between %(start)s and %(end)s."),
                                use_yearly_scope=False)

            y_start, y_end = self._get_payroll_year_bounds()
            yearly_limit = self.yearly_max_effect or 0
            if yearly_limit:
                self._check_max(y_start, y_end, yearly_limit,
                                _("Yearly limit exceeded for %(name)s (%(actual)s/%(limit)s) between %(start)s and %(end)s."),
                                use_yearly_scope=True)

        self._check_effect_dates_in_job_period()
        self._check_duplicate_wizard_data()
        self._check_duplicate_effect_dates()
        self._check_basic_effect_unique_in_pay_period()

    def _validate_all_before_save(self):
        self.ensure_one()
        if self._is_hr_manager():
            return
        self._validate_limits_and_dates()
        self._ensure_no_weekly_day_off_conflict_with_paid_leave()
        self._ensure_no_paid_vacancy_conflict()
        self._ensure_monthly_weekly_vacancies_allowed()

    def _ensure_monthly_weekly_vacancies_allowed(self):
        self.ensure_one()
        if not (self.change_day_off_date or self.weekly_vacation_work_permit):
            return
        if (self.change_day_off_date or self.weekly_vacation_work_permit) and not self.monthly_weekly_vacancies:
            raise ValidationError(_("A previous day-off date is required."))
        if not self.monthly_weekly_vacancies:
            return

        allowed = self._get_allowed_monthly_weekly_vacancy_values()
        if not allowed:
            raise ValidationError(_("No allowed previous day-off dates are available."))

        vacancy_val = fields.Date.to_string(self.monthly_weekly_vacancies)
        allowed_dates = {d[0] for d in self._get_effect_date_selection()}
        excluded_old_dates = self._get_changed_weekly_day_off_old_dates(self.employee_id, allowed_dates)
        if vacancy_val in excluded_old_dates:
            raise ValidationError(_("The selected previous day-off date is outside allowed dates."))

        if vacancy_val not in allowed:
            if vacancy_val in allowed_dates and self._is_weekly_day_off_date(vacancy_val):
                return
            raise ValidationError(_("The selected previous day-off date is outside allowed dates."))

    def _is_weekly_day_off_date(self, date_str):
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return False

        weekday_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }

        allowed_weekdays = set()
        weekly_day_offs = employee.day_off.filtered(lambda r: r.active and r.effect_value)
        for rec in weekly_day_offs:
            key = (rec.effect_value or '').lower()
            if key in weekday_map:
                allowed_weekdays.add(weekday_map[key])

        for dt_str in employee.day_off_dates.filtered(lambda r: r.active and r.effect_value).mapped('effect_value'):
            try:
                allowed_weekdays.add(date.fromisoformat(dt_str).weekday())
            except ValueError:
                continue

        old_dates = self._get_changed_weekly_day_off_old_dates(
            employee, {d[0] for d in self._get_effect_date_selection()}
        )
        for dt_str in old_dates:
            try:
                allowed_weekdays.add(date.fromisoformat(dt_str).weekday())
            except ValueError:
                continue

        if not allowed_weekdays:
            return False

        try:
            return date.fromisoformat(date_str).weekday() in allowed_weekdays
        except ValueError:
            return False

    @api.constrains('employee_id', 'effect_type_id', 'effect_date', 'end_date',
                    'periodic_effect', 'weekly_effect', 'yearly_effect', 'effect_weekday',
                    'hour_value', 'second_hour_value', 'effect_numerical_value',
                    'monthly_weekly_vacancies', 'weekly_day_off_number')
    def _check_effect_limits_and_dates(self):
        for rec in self:
            if rec._is_hr_manager():
                continue
            rec._validate_all_before_save()

    @api.onchange('effect_weekday')
    def _onchange_effect_weekday(self):
        for rec in self:
            dates = rec._get_effect_weekday_options()
            if dates:
                rec.effect_date = dates[0]

    @api.onchange('monthly_weekly_vacancies', 'weekly_vacation_work_permit')
    def _onchange_monthly_weekly_vacancies(self):
        for rec in self:
            if rec.weekly_vacation_work_permit and rec.monthly_weekly_vacancies:
                rec.effect_date = rec.monthly_weekly_vacancies

    @api.onchange('employee_id', 'effect_type_id')
    def _onchange_all(self):
        clear_fields = ['effect_date', 'effect_weekday', 'hour_value', 'second_hour_value', 'end_date', 'effect_reason',
                        'monthly_weekly_vacancies', 'effect_numerical_value', 'periodic_effect', 'weekly_effect']

        for rec in self:
            start, end = rec._pay_period_bounds()
            rec.effect_month_count = rec._get_count_between(start, end)
            today = fields.Date.context_today(rec)
            y_start = date(today.year - 1, 12, 21)
            y_end = date(today.year, 12, 20)
            rec.effect_payroll_year_count = rec._get_count_between(y_start, y_end)

            for fld in clear_fields:
                setattr(rec, fld, False)

            if (rec.effect_type_id and rec.effect_type_id.is_basic_effect
                    and not rec.effect_type_id.basic_working_hour_number
                    and not rec.effect_type_id.select_day_off_number):
                fd, _ = rec._pay_period_bounds()
                rec.effect_date = fd.strftime('%Y-%m-%d')

    @api.onchange('periodic_effect')
    def _onchange_periodic_effect(self):

        clear_fields = ['effect_date', 'effect_weekday', 'hour_value', 'second_hour_value', 'end_date', 'effect_reason',
                        'monthly_weekly_vacancies', 'effect_numerical_value', 'weekly_effect']

        for rec in self:
            for fld in clear_fields:
                setattr(rec, fld, False)

    @api.onchange('weekly_effect')
    def _onchange_weekly_effect(self):

        clear_fields = ['effect_date', 'effect_weekday', 'hour_value', 'second_hour_value', 'end_date', 'effect_reason',
                        'monthly_weekly_vacancies', 'effect_numerical_value', 'periodic_effect']

        for rec in self:
            for fld in clear_fields:
                setattr(rec, fld, False)

    @api.onchange('employee_id', 'supervision_type')
    def _onchange_supervision_type(self):
        for rec in self:
            if rec.effect_type_id and rec.effect_type_id not in rec.allowed_effect_type_ids:
                rec.effect_type_id = False

    def btn_change_status(self):
        target = self.env.context.get('effect_target')
        self.action_change_state(target)

    def _add_hr_effect(self):
        self.ensure_one()
        if not self.employee_id:
            return self.env['ab_hr_effect']

        weekly_pattern = bool(self.weekly_effect and self.effect_weekday)
        if not self.effect_date and not weekly_pattern:
            raise ValidationError(_("A date or a weekly pattern is required to create the effect."))

        effect_dates = []
        if self.is_weekly_effect and self.weekly_effect and not self.periodic_effect and not self.yearly_effect:
            dates = self._get_effect_weekday_options()
            effect_dates = [date.fromisoformat(dt_str) for dt_str in dates]
        elif self.is_weekly_effect and self.weekly_effect and not self.periodic_effect and self.yearly_effect:
            dates = self._get_effect_yearly_weekday_options()
            effect_dates = [date.fromisoformat(dt_str) for dt_str in dates]
        else:
            start = fields.Date.to_date(self.effect_date)
            end = fields.Date.to_date(self.end_date) if self.end_date else start
            if end < start:
                raise ValidationError(_("The end date of the period cannot be earlier than the start date."))
            effect_dates = [start + timedelta(days=i) for i in range((end - start).days + 1)]

        if not effect_dates:
            raise ValidationError(_("No matching dates found for the effect."))

        if self.weekly_effect:
            numerical_value = self.weekly_day_off_number or self.effect_numerical_value
        else:
            numerical_value = self.effect_numerical_value

        values = []
        for day in effect_dates:
            data = {
                'employee_id': self.employee_id.id,
                'wizard_id': self.id,
                'effect_type_id': self.effect_type_id.id,
                'effect_date': fields.Date.to_string(day),
                'effect_numerical_value': numerical_value,
                'hour_value': self.hour_value,
                'second_hour_value': self.second_hour_value,
                'effect_reason': self.effect_reason,
                'monthly_weekly_vacancies': self.monthly_weekly_vacancies,
                'attached_file': self.attached_file,
                'workplace': self.workplace.id,
                'job_title': self.job_title.id,
            }
            if not self.weekly_effect:
                data['effect_weekday'] = self.effect_weekday
            values.append(data)

        effects = self.env['ab_hr_effect'].sudo().create(values)

        if self.change_day_off_date and self.monthly_weekly_vacancies and self.effect_date:
            effect_date_str = fields.Date.to_string(self.effect_date)
            monthly_vacancy_val = fields.Date.to_string(self.monthly_weekly_vacancies)
            day_off_records = self.employee_id.day_off_dates.filtered(
                lambda r: r.effect_value == monthly_vacancy_val
            )
            for rec in day_off_records:
                rec.sudo().write({'effect_value': effect_date_str})

        return effects

    def action_save(self):
        self.ensure_one()
        if self.env.context.get('sudo_wizard_create') and not self.env.su:
            return self.sudo().with_context(sudo_wizard_create=True).action_save()

        self._validate_before_save()

        if (self.select_day_off_number or self.basic_working_hour_number) and self.effect_status != 'applied':
            self.action_change_state('applied')

        return {'type': 'ir.actions.act_window_close'}

    def _validate_before_save(self):
        self.ensure_one()
        self._validate_all_before_save()

    def _ensure_no_weekly_day_off_conflict_with_paid_leave(self):
        self.ensure_one()
        if not (self.employee_id and self.effect_type_id):
            return
        if not (self.effect_type_id.is_day_off_date or self.periodic_effect):
            return

        requested_dates = self._get_paid_vacancy_validation_dates()
        if not requested_dates and self.effect_date:
            requested_dates = [fields.Date.to_date(self.effect_date)]

        if not requested_dates:
            return

        date_values = [d.strftime('%Y-%m-%d') for d in requested_dates]
        conflict = self.env['ab_hr_effect'].search([
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_paid_vacancy', '=', True),
            ('effect_date', 'in', date_values),
            ('active', '=', True),
        ], limit=1)
        if conflict:
            raise ValidationError(
                _("The selected date(s) cannot be used because they are already"
                  " used as a paid leave date in the effects."))

    def _ensure_no_paid_vacancy_conflict(self):
        self.ensure_one()
        if not self.employee_id:
            return
        if not (self.effect_type_id and self.effect_type_id.is_paid_vacancy):
            return

        requested_dates = self._get_paid_vacancy_validation_dates()
        if not requested_dates:
            return

        date_values = [d.strftime('%Y-%m-%d') for d in requested_dates]

        conflict_effect = self.env['ab_hr_effect'].search([
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_paid_vacancy', '=', True),
            ('active', '=', True),
            ('effect_date', 'in', date_values),
        ], limit=1)
        if conflict_effect:
            raise ValidationError(
                _("A paid leave effect already exists on one or more of the selected dates."))

        conflict_wizard = self.search([
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_paid_vacancy', '=', True),
            ('effect_status', 'not in', ['archived', 'rejected', 'applied']),
        ], limit=1)
        if conflict_wizard:
            existing_dates = conflict_wizard._get_requested_effect_dates(use_yearly_scope=True)
            existing_values = {d.strftime('%Y-%m-%d') for d in existing_dates}
            if existing_values.intersection(date_values):
                raise ValidationError(
                    _("A paid leave request already exists on one or more of the selected dates."))

    def _is_hr_manager(self):
        return self.env.user.has_group('ab_hr.group_ab_hr_manager')

    def _is_payroll_applicant(self):
        user = self.env.user
        return (user.has_group('ab_hr.group_ab_hr_payroll_specialist')
                or user.has_group('ab_hr.group_ab_hr_co'))

    def _is_co_or_reviewer(self):
        user = self.env.user
        return (user.has_group('ab_hr.group_ab_hr_co')
                or user.has_group('ab_hr.group_ab_hr_payroll_reviewer'))

    def _is_employee_self(self):
        return self.supervision_type == 'myself'

    def _is_direct_manager(self):
        return self.supervision_type == 'direct'

    def _is_upper_manager(self):
        return self.supervision_type == 'indirect'

    def _get_allowed_targets(self):
        self.ensure_one()
        if self.effect_status == 'draft':
            return {'direct_manager_review', 'archived'}
        if self.effect_status == 'direct_manager_review':
            targets = {'rejected', 'draft'}
            if self.double_approval:
                targets.add('upper_manager_review')
            else:
                targets.add('under_application')
            return targets
        if self.effect_status == 'upper_manager_review':
            return {'under_application', 'rejected', 'draft'}
        if self.effect_status == 'under_application':
            return {'applied', 'draft'}
        if self.effect_status == 'rejected':
            return {'archived'}
        if self.effect_status == 'archived':
            return {'draft'}
        return set()

    def _ensure_transition_allowed(self, target):
        self.ensure_one()
        if self._is_hr_manager():
            return

        allowed = self._get_allowed_targets()
        if target not in allowed:
            selection = dict(self._fields['effect_status'].selection)
            raise UserError(_("You cannot move from '%s' to '%s'.") %
                            (selection.get(self.effect_status, self.effect_status),
                             selection.get(target, target)))

        if target == 'draft' and self._is_co_or_reviewer():
            return

        if self.effect_status == 'draft':
            if target == 'direct_manager_review' and not (
                    self._is_employee_self() or self._is_direct_manager() or self._is_upper_manager()):
                raise ValidationError(_("User does not have authority for this action."))
            if target == 'archived' and not (
                    self.create_uid == self.env.user or self._is_employee_self() or self._is_direct_manager()):
                raise ValidationError(_("User does not have authority for this action."))
        elif self.effect_status == 'direct_manager_review':
            if target == 'upper_manager_review':
                if not (self.double_approval and (self._is_direct_manager() or self._is_upper_manager())):
                    raise ValidationError(_("User does not have authority for this action."))
            elif target == 'under_application':
                if self.double_approval:
                    user = self.env.user
                    is_reviewer = user.has_group('ab_hr.group_ab_hr_payroll_reviewer')
                    is_co = user.has_group('ab_hr.group_ab_hr_co')
                    if not (self._is_direct_manager() or self._is_upper_manager() or is_co or is_reviewer):
                        raise ValidationError(_("User does not have authority for this action."))
                elif not (self._is_direct_manager() or self._is_upper_manager()):
                    raise ValidationError(_("User does not have authority for this action."))
            elif target in {'rejected', 'draft'}:
                if not (self._is_direct_manager() or self._is_upper_manager()):
                    raise ValidationError(_("User does not have authority for this action."))
        elif self.effect_status == 'upper_manager_review':
            if target == 'under_application' and not self._is_upper_manager():
                raise ValidationError(_("User does not have authority for this action."))
            if target in {'rejected', 'draft'} and not (self._is_direct_manager() or self._is_upper_manager()):
                raise ValidationError(_("User does not have authority for this action."))
        elif self.effect_status == 'under_application':
            if target == 'applied' and not self._is_payroll_applicant():
                raise ValidationError(_("User does not have authority for this action."))
            if target == 'draft' and not (self._is_direct_manager() or self._is_upper_manager()):
                raise ValidationError(_("User does not have authority for this action."))
        elif self.effect_status == 'rejected':
            if target == 'archived' and not (self._is_direct_manager() or self._is_upper_manager()):
                raise ValidationError(_("User does not have authority for this action."))
        elif self.effect_status == 'archived':
            if target == 'draft' and not self._is_payroll_applicant():
                raise ValidationError(_("User does not have authority for this action."))

    def action_change_state(self, target):
        if not target:
            raise UserError(_("No target state was provided."))

        selection = dict(self._fields['effect_status'].selection)
        if target not in selection:
            raise UserError(_("Invalid target state."))

        if self.env.context.get('sudo_wizard_create') and not self.env.su:
            return self.sudo().with_context(sudo_wizard_create=True).action_change_state(target)

        for rec in self:
            if not ((rec.select_day_off_number or rec.basic_working_hour_number)
                    and target == 'applied' and rec.effect_status == 'draft'):
                rec._ensure_transition_allowed(target)
            if target != 'archived' and (target != 'draft' or rec.effect_status == 'archived'):
                rec._validate_limits_and_dates()

            if target == 'applied':
                rec._apply_basic_effects_first_in_pay_period()
                effects = rec._add_hr_effect()
                for effect in effects:
                    if not rec._is_hr_manager():
                        effect._check_valid_effect()
                    effect._apply_basic_effects_if_need()
            rec.effect_status = target

    def _apply_basic_effects_first_in_pay_period(self):
        self.ensure_one()
        if not self.employee_id:
            return

        if self.basic_effect:
            return

        start, end = self._pay_period_bounds()
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id.is_basic_effect', '=', True),
            ('effect_status', '=', 'under_application'),
            ('id', '!=', self.id),
        ]
        candidates = self.search(domain, order='id')
        for wiz in candidates:
            dates = wiz._get_requested_effect_dates(use_yearly_scope=False)
            if not dates and wiz.effect_date:
                dates = [fields.Date.to_date(wiz.effect_date)]
            if any(start <= d <= end for d in dates):
                wiz.action_change_state('applied')

    def action_apply_under_application_batch(self):
        records = self.browse(self.env.context.get('active_ids', []))
        records = records.filtered(lambda r: r.effect_status == 'under_application')
        if not records:
            records = self.search([('effect_status', '=', 'under_application')])
        if not records:
            return True

        groups = {}
        for rec in records:
            start, end = rec._pay_period_bounds()
            key = (rec.employee_id.id, start, end)
            groups.setdefault(key, self.env['ab_hr_effect_wizard'])
            groups[key] |= rec

        for _key, group in groups.items():
            basic_records = group.filtered(lambda r: r.basic_effect)
            non_basic_records = group - basic_records

            for rec in basic_records.sorted(lambda r: r.id):
                rec.action_change_state('applied')

            for rec in non_basic_records.sorted(lambda r: r.id):
                rec.action_change_state('applied')

        return True

    def action_reset_to_draft_batch(self):
        records = self.browse(self.env.context.get('active_ids', []))
        records = records.filtered(lambda r: r.effect_status != 'draft')
        if not records:
            return True

        for rec in records.sorted(lambda r: r.id):
            rec.action_change_state('draft')

        return True
