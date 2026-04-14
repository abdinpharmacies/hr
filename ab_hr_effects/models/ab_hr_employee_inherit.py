from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta
from odoo.exceptions import ValidationError
from dateutil.rrule import DAILY, rrule


class AbHrJobOccupied(models.Model):
    _name = 'ab_hr_employee'
    _inherit = ['ab_hr_employee', 'ab_hr_effect_mixin']

    attendance_time = fields.Selection(string="Attendance Time",
                                       selection=lambda self: self._generate_time_slots(),
                                       compute='_compute_basic_effects')

    attendance_out_time = fields.Char(string="Attendance Out Time", compute='_compute_attendance_out_time')

    basic_working_hour_number = fields.Float(string="Basic Working Hour Number",
                                             compute='_compute_basic_effects',
                                             digits=(6, 2))

    # أيام الأجازة (مثلا جمعة وسبت)
    day_off = fields.One2many('ab_hr_basic_effect', 'employee_id', string="Day Off",
                              domain=[('is_attendance_time_effect', '=', False),
                                      ('is_day_off_date', '=', False),
                                      ('select_day_off_number', '=', False),
                                      ('basic_working_hour_number', '=', False)])

    # مثلا هيكون 2 لموظف في الإدارة -- جمعة وسبت -- بس ممكن يكون مجمع لحد تاني
    weekly_day_off_number = fields.Selection(string="Weekly Day Off Number",
                                             selection=[('1', '1'), ('2', '2'), ('3', '3'),
                                                        ('4', '4'), ('5', '5'), ('6', '6')],
                                             compute='_compute_basic_effects',
                                             default='1')

    weekly_day_off_integer = fields.Integer(string="Weekly Day Off Number",
                                            compute='_compute_weekly_day_off_integer')

    # للسماح بمؤثرات شهر سابق -- صلاحية بيفتحها الكورديناتور
    delay_to_send_effect = fields.Boolean(string="Show Previous Month Dates", default=False)

    # التواريخ الفعلية وليس الافتراضية
    day_off_dates = fields.One2many('ab_hr_basic_effect', 'employee_id', string="Day Off Dates",
                                    domain=[('is_day_off_date', '=', True)])

    effects_ids = fields.One2many('ab_hr_effect', 'employee_id', string="Applied Effects")
    effects_wiz_ids = fields.One2many('ab_hr_effect_wizard', 'employee_id', string="Current Effects",
                                      domain=[('effect_status', '!=', 'archived')])

    # الموظف الذي له أجازات مجمعة -- ليس له تاريخ أجازة
    day_off_exist = fields.Boolean(string="Day Off Exist", compute='_compute_day_off_exist')

    @api.model
    def _compute_basic_effects(self):
        for rec in self:
            is_attendance_time_effect = rec.env['ab_hr_basic_effect'].search([
                ('employee_id', '=', rec.id),
                ('is_attendance_time_effect', '=', True)], limit=1)
            select_day_off_number = rec.env['ab_hr_basic_effect'].search(
                [('employee_id', '=', rec.id), ('select_day_off_number', '=', True)], limit=1)
            basic_working_hour_effect = rec.env['ab_hr_basic_effect'].search([
                ('employee_id', '=', rec.id),
                ('basic_working_hour_number', '=', True)], limit=1)
            rec.attendance_time = is_attendance_time_effect.effect_value if is_attendance_time_effect else False
            rec.weekly_day_off_number = select_day_off_number.effect_value if select_day_off_number else '1'
            rec.basic_working_hour_number = rec._parse_working_hour_value(
                basic_working_hour_effect.effect_value if basic_working_hour_effect else False)

    def _parse_working_hour_value(self, value):
        if value in (None, False):
            return False
        if isinstance(value, (int, float)):
            return float(value)
        if not isinstance(value, str):
            return False
        raw = value.strip()
        if not raw:
            return False
        if ':' in raw:
            parts = raw.split(':', 1)
            try:
                hours = int(parts[0])
                minutes = int(parts[1])
            except (ValueError, TypeError):
                return False
            return hours + (minutes / 60.0)
        try:
            return float(raw)
        except (ValueError, TypeError):
            return False

    @api.depends('attendance_time', 'basic_working_hour_number')
    def _compute_attendance_out_time(self):
        for rec in self:
            if not rec.attendance_time or not rec.basic_working_hour_number:
                rec.attendance_out_time = False
                continue
            try:
                hours_str, minutes_str = rec.attendance_time.split(':', 1)
                attendance_minutes = (int(hours_str) * 60) + int(minutes_str)
            except (ValueError, AttributeError):
                rec.attendance_out_time = False
                continue

            total_minutes = attendance_minutes + int(round(rec.basic_working_hour_number * 60))
            total_minutes %= (24 * 60)
            out_hours = total_minutes // 60
            out_minutes = total_minutes % 60
            rec.attendance_out_time = f"{out_hours:02d}:{out_minutes:02d}"

    @api.depends('day_off_dates')
    def _compute_day_off_exist(self):
        for record in self:
            record.day_off_exist = bool(record.day_off_dates.filtered(lambda r: r.active))

    @api.depends('weekly_day_off_number')
    def _compute_weekly_day_off_integer(self):
        for rec in self:
            if rec.weekly_day_off_number:
                rec.weekly_day_off_integer = int(rec.weekly_day_off_number)
            else:
                rec.weekly_day_off_integer = 1

    @api.model
    def _generate_time_slots(self):
        return self.env['ab_hr_effect_wizard']._generate_time_slots()

    # في حالة فتح صلاحية الشهر السابق
    @api.model
    def _get_previous_month_date_selection(self):
        today = fields.Date.context_today(self)
        if today.day < 21:
            start = (today.replace(day=1) - timedelta(days=32)).replace(day=21)
            end = (today.replace(day=1) - timedelta(days=1)).replace(day=20)
        else:
            start = (today.replace(day=1) - timedelta(days=1)).replace(day=21)
            end = today.replace(day=20)

        dates = [
            (d.strftime('%Y-%m-%d'), d.strftime('%d-%m-%Y'))
            for d in rrule(DAILY, dtstart=start, until=end)
        ]
        return dates

    def _get_allowed_effect_date_selection(self):
        self.ensure_one()
        if self.delay_to_send_effect:
            return self._get_previous_month_date_selection()
        return self._get_effect_date_selection()

    # تحويل أيام الأسبوع لأرقام
    def _get_weekly_vacancy_dates(self, weekday_name):
        weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2,
                       'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
        weekday_index = weekday_map.get(weekday_name)
        if weekday_index is None:
            return []

        return [
            (dt_str, label)
            for dt_str, label in self._get_allowed_effect_date_selection()
            if date.fromisoformat(dt_str).weekday() == weekday_index]

    # التحكم في عرض تواريخ الشهر السابق عبر زر واحد
    def action_toggle_delay_to_send_effect(self):
        self.ensure_one()
        self = self.with_context(replication=True)
        user = self.env.user
        is_reviewer = user.has_group('ab_hr.group_ab_hr_payroll_reviewer')
        is_co = user.has_group('ab_hr.group_ab_hr_co')
        can_add_effect = self._can_user_add_effect(user)

        if self.delay_to_send_effect:
            if not can_add_effect:
                raise UserError(
                    _("You don't have the authority to disable -show previous month dates- for this job"))
            self.sudo().write({'delay_to_send_effect': False})
        else:
            if not (is_co or is_reviewer):
                raise UserError(
                    _("You don't have the authority to enable -show previous month dates- for this job"))
            self.sudo().write({'delay_to_send_effect': True})

    def _can_user_add_effect(self, user):
        group_payroll_reviewer = self.env.ref('ab_hr.group_ab_hr_payroll_reviewer')
        group_co = self.env.ref('ab_hr.group_ab_hr_co')
        group_basic_data = self.env.ref('ab_hr.group_ab_hr_basic_data')
        is_allowed_supervision_type = self.supervision_type in ['myself', 'direct', 'indirect']
        return (group_payroll_reviewer in user.group_ids
                or group_co in user.group_ids
                or (group_basic_data in user.group_ids and self.supervision_type in ['direct', 'indirect'])
                or is_allowed_supervision_type)

    def action_open_wizard_effects_by_status(self):
        self.ensure_one()
        status = self.env.context.get('wizard_status')
        if not status:
            raise UserError(_("No status was provided."))

        start, end = self._pay_period_bounds()
        start_str = fields.Date.to_string(start)
        end_str = fields.Date.to_string(end)

        domain = [
            ('employee_id', '=', self.id),
            ('effect_status', '=', status),
            '|',
            '&', ('effect_date', '>=', start_str), ('effect_date', '<=', end_str),
            '&', ('end_date', '>=', start_str), ('end_date', '<=', end_str),
        ]

        return {
            'name': _('Effects Wizard (%s)') % status,
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_effect_wizard',
            'view_mode': 'list,form',
            'views': [
                (self.env.ref('ab_hr_effects.ab_hr_effect_wizard_view_tree_employee').id, 'list'),
                (False, 'form'),
            ],
            'target': 'new',
            'domain': domain,
            'context': {
                'default_employee_id': self.id,
                'active_model': 'ab_hr_employee',
                'active_id': self.id,
                'active_ids': [self.id],
                'sudo_wizard_create': True,
            },
        }

    # تحديث تواريخ الأجازات الأسبوعية للشهر الجديد
    def action_apply_weekly_days_off(self):
        self.ensure_one()
        BasicEffect = self.env['ab_hr_basic_effect']
        PayrollEffectType = self.env['ab_hr_effect_type']
        allowed_dates = self._get_allowed_effect_date_selection()
        valid_dates_set = {d[0] for d in allowed_dates}
        all_weekly_days = {int(v) for v in self.day_off_dates.mapped('weekly_day_off_integer') if v}
        weekly_day_key_by_order = {}
        for rec in self.day_off.filtered(lambda r: r.active and r.effect_value and r.weekly_day_off_integer):
            weekly_day_key_by_order[int(rec.weekly_day_off_integer)] = (rec.effect_value or '').lower()
        if not all_weekly_days:
            all_weekly_days = set(weekly_day_key_by_order.keys())

        def get_target_dates(day_off_order):
            weekday_key = weekly_day_key_by_order.get(day_off_order)
            if weekday_key:
                weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2,
                               'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
                weekday_idx = weekday_map.get(weekday_key)
                if weekday_idx is None:
                    return []
                return [dt_str for dt_str, _label in allowed_dates
                        if date.fromisoformat(dt_str).weekday() == weekday_idx]
            return []

        existing_effects = BasicEffect.search([
            ('employee_id', '=', self.id),
            ('is_day_off_date', '=', True),
            ('active', '=', True)])
        existing_dates = {rec.effect_value for rec in existing_effects if rec.effect_value}

        if not existing_dates.issubset(valid_dates_set):
            existing_effects.sudo().unlink()

            for day_off_int in all_weekly_days:
                target_dates = get_target_dates(day_off_int)
                effect_type_id = PayrollEffectType.search([
                    ('is_day_off_date', '=', True),
                    ('weekly_day_off_integer', '=', day_off_int)], limit=1)
                if not effect_type_id:
                    continue

                for date_str in target_dates:
                    BasicEffect.sudo().create({
                        'employee_id': self.id,
                        'effect_type_id': effect_type_id.id,
                        'effect_value': date_str,
                        'weekly_day_off_integer': day_off_int,
                        'is_day_off_date': True,
                        'active': True})
        else:
            raise UserError(_("There are no dates need to be updated."))

    #
    def btn_add_effect(self):
        self.ensure_one()
        user = self.env.user
        if not self._can_user_add_effect(user):
            raise ValidationError(_("You don`t have the authority to add effect to this job"))

        valid_dates = {d[0] for d in self._get_allowed_effect_date_selection()}
        out_of_range = self.day_off_dates.filtered(
            lambda r: r.active and r.effect_value and r.effect_value not in valid_dates
        )
        if out_of_range:
            self.with_context(skip_weekly_day_off_full_change_validation=True).action_apply_weekly_days_off()

        return {
            'name': _('Add Effect'),
            'type': 'ir.actions.act_window',
            'res_model': 'ab_hr_effect_wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('ab_hr_effects.view_ab_hr_effect_wizard_form').id,
            'target': 'new',
            'context': {
                'default_employee_id': self.id,
                'active_model': 'ab_hr_employee',
                'active_id': self.id,
                'active_ids': [self.id],
                'sudo_wizard_create': True,
            },
        }
