from dateutil.relativedelta import relativedelta

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date


class AbHrPayrollEffect(models.Model):
    _name = 'ab_hr_effect'
    _description = 'ab_hr_effect'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'abdin_et.extra_tools', 'ab_hr_effect_mixin']
    _rec_name = 'employee_id'
    _order = "effect_date desc, effect_type_id"

    accid = fields.Char(string="ePlus Code", related='employee_id.accid')

    employee_id = fields.Many2one('ab_hr_employee', string="Employee", required=True)

    job_id = fields.Many2one(string="Job", related='employee_id.job_id')

    job_status = fields.Selection(string="Job Status", related='employee_id.job_status')

    workplace = fields.Many2one('ab_hr_department', string='Workplace', store=True, related='employee_id.department_id')

    job_title = fields.Many2one('ab_hr_job', string='Job Title', store=True, related='employee_id.job_id')

    internal_working_employee = fields.Boolean(related='employee_id.internal_working_employee')

    effect_type_id = fields.Many2one('ab_hr_effect_type', string="Effect Type", required=True, tracking=True)

    effect_numerical_value = fields.Float(string="Effect Numerical Value", digits=(6, 2), tracking=True)

    hour_value = fields.Selection(selection=lambda self: self._generate_time_slots(),
                                  string="Hour Value", tracking=True)

    second_hour_value = fields.Selection(selection=lambda self: self._generate_time_slots(),
                                         string="Second Hour Value", tracking=True)

    effect_reason = fields.Text(string="Effect Reason", tracking=True)

    effect_date = fields.Date(string="Effect Date", tracking=True)

    entitlement_month = fields.Char(string="Entitlement Month", compute='_compute_entitlement_month',
                                    store=True, readonly=True)

    current_month_match = fields.Boolean(string="Current Month Effect", compute='_compute_current_month_match',
                                         search='_search_current_month_match', store=False)

    monthly_weekly_vacancies = fields.Date(tracking=True, string="Previous Day Off")

    effect_weekday = fields.Selection([('saturday', 'Saturday'), ('sunday', 'Sunday'), ('monday', 'Monday'),
                                       ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'), ('thursday', 'Thursday'),
                                       ('friday', 'Friday')], string="WeekDay", tracking=True)

    supervision_type = fields.Selection(string="Supervision Type", related='employee_id.supervision_type')
    user_id = fields.Many2one('res.users', readonly=True, default=lambda self: self.env.user.id)
    active = fields.Boolean(default=True)
    attached_file = fields.Binary(string="Attached File")

    wizard_id = fields.Many2one('ab_hr_effect_wizard', index=True)

    @api.model
    def _generate_time_slots(self):
        return self.env['ab_hr_effect_wizard'].sudo()._generate_time_slots()

    @api.depends('effect_date')
    def _compute_entitlement_month(self):
        for record in self:
            if record.effect_date:
                effect_date = fields.Date.from_string(record.effect_date)

                if effect_date.day >= 21:
                    # shift to next month using relativedelta
                    entitlement_date = (effect_date + relativedelta(months=+1)).replace(day=1)
                else:
                    entitlement_date = effect_date.replace(day=1)

                # format as MM-YYYY
                record.entitlement_month = entitlement_date.strftime("%m-%Y")
            else:
                record.entitlement_month = False

    def _compute_current_month_match(self):
        today = date.today()

        # use dateutil.relativedelta for month shifting
        if today.day >= 21:
            current_entitlement_date = (today + relativedelta(months=+1)).replace(day=1)
        else:
            current_entitlement_date = today.replace(day=1)

        # format as MM-YYYY
        current_entitlement_month = current_entitlement_date.strftime("%m-%Y")

        for rec in self:
            rec.current_month_match = (rec.entitlement_month == current_entitlement_month)

    def _search_current_month_match(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        ids = []
        curr_mo_eff = self.env['ab_hr_effect'].sudo()

        for rec in curr_mo_eff.search([]):

            if rec.current_month_match:
                ids.append(rec.id)

        if operator != '=':
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    def _check_valid_effect(self):
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('effect_numerical_value', '=', self.effect_numerical_value),
            ('second_hour_value', '=', self.second_hour_value),
            ('effect_reason', '=', self.effect_reason),
            ('monthly_weekly_vacancies', '=', self.monthly_weekly_vacancies),
            ('id', '!=', self.id)
        ]
        existing = False
        if not self.effect_type_id.is_basic_effect:
            domain += [('effect_weekday', '=', self.effect_weekday),
                       ('hour_value', '=', self.hour_value),
                       ('effect_date', '=', self.effect_date)]

            existing = self.search(domain)
        else:
            if self.effect_type_id.is_attendance_time_effect:
                domain += [('effect_weekday', '=', self.effect_weekday)]
                valid_record = self.search(domain, order='id desc', limit=1)
                if valid_record.hour_value == self.hour_value:
                    existing = True

            if self.effect_type_id.weekly_day_off_integer >= 1:
                domain += [('hour_value', '=', self.hour_value)]
                valid_record = self.search(domain, order='id desc', limit=1)
                if valid_record.effect_weekday == self.effect_weekday:
                    existing = True
        if existing:
            raise ValidationError("The effect cannot be duplicated with the same values!")

    def _apply_basic_effects_if_need(self):
        # basic_effect creation
        if self.effect_type_id.is_basic_effect:
            if self.effect_type_id.is_attendance_time_effect:
                self._apply_attendance()

            if self.effect_type_id.select_day_off_number:
                self._apply_job_day_off_number()

            if self.effect_type_id.basic_working_hour_number:
                self._apply_basic_working_hour_number()

            if (self.effect_type_id.weekly_day_off_integer >= 1
                    and not self.effect_type_id.is_day_off_date):
                self._apply_day_off()
                self._apply_day_off_date()

    def _apply_attendance(self):
        self._apply_basic_effect(self.hour_value)

    def _apply_day_off(self):
        self._apply_basic_effect(self.effect_weekday)

    def _apply_job_day_off_number(self):
        effect_value = (self.wizard_id.weekly_day_off_number
                        or self.effect_type_id.weekly_day_off_number)
        self._apply_basic_effect(effect_value)

    def _apply_basic_working_hour_number(self):
        self.ensure_one()
        value = self.effect_numerical_value
        if value is None:
            return
        try:
            effect_value = ("%0.2f" % float(value)).rstrip('0').rstrip('.')
        except (TypeError, ValueError):
            return
        self._apply_basic_effect(effect_value)

    def _apply_day_off_date(self):
        self.ensure_one()
        BasicEffect = self.env['ab_hr_basic_effect']
        target_dates = self._get_effect_weekday_options()

        if self.effect_type_id.weekly_day_off_integer >= 1:

            existing_effects = BasicEffect.search([
                ('employee_id', '=', self.employee_id.id),
                ('is_day_off_date', '=', True),
                ('weekly_day_off_integer', '=', self.effect_type_id.weekly_day_off_integer),
                ('active', '=', True)])

            new_effect_type = self.env['ab_hr_effect_type'].search(
                [('is_day_off_date', '=', True),
                 ('weekly_day_off_number', '=', self.effect_type_id.weekly_day_off_integer)
                 ], limit=1)
        else:
            return

        existing_dates = {rec.effect_value for rec in existing_effects if rec.effect_value}
        dates_to_create = list(set(target_dates) - existing_dates)
        effects_to_delete = [rec for rec in existing_effects if rec.effect_value not in target_dates]

        for rec in effects_to_delete:
            rec.sudo().unlink()

        for date_str in dates_to_create:
            BasicEffect.sudo().create({
                'employee_id': self.employee_id.id,
                'effect_type_id': new_effect_type.id,
                'effect_value': date_str,
                'active': True})

    def _apply_basic_effect(self, effect_value):
        self.ensure_one()
        BasicEffect = self.env['ab_hr_basic_effect']

        existing_effect = BasicEffect.search([
            ('employee_id', '=', self.employee_id.id),
            ('effect_type_id', '=', self.effect_type_id.id),
            ('active', '=', True)
        ], limit=1)

        if existing_effect:
            existing_effect.sudo().write({'effect_value': effect_value})

        else:
            BasicEffect.sudo().create({
                'employee_id': self.employee_id.id,
                'effect_type_id': self.effect_type_id.id,
                'effect_value': effect_value,
                'active': True
            })

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
