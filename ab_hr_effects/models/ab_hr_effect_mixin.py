from datetime import datetime, date, timedelta

from dateutil.rrule import rrule, DAILY

from odoo import api, fields, models


class AbHrEffectMixin(models.AbstractModel):
    _name = 'ab_hr_effect_mixin'
    _description = 'ab_hr_effect_mixin'

    @api.model
    def _get_effect_date_selection(self):
        today = date.today()
        if today.day < 21:
            start = (today.replace(day=1) - timedelta(days=1)).replace(day=21)
            end = today.replace(day=20)
        else:
            start = today.replace(day=21)
            end = (today.replace(day=28) + timedelta(days=4)).replace(day=20)
        dates = []
        cur = start
        while cur <= end:
            dates.append((cur.strftime('%Y-%m-%d'),
                          cur.strftime('%d-%m-%Y')))
            cur += timedelta(days=1)
        return dates

    @api.model
    def _pay_period_bounds(self):
        dates = self._get_effect_date_selection()

        if dates:
            start = datetime.strptime(dates[0][0], '%Y-%m-%d').date()
            end = datetime.strptime(dates[-1][0], '%Y-%m-%d').date()
        else:
            start = end = fields.Date.context_today(self)

        return start, end

    @api.model
    def _get_week_days_selection(self):
        return [('saturday', 'Saturday'), ('sunday', 'Sunday'), ('monday', 'Monday'), ('tuesday', 'Tuesday'),
                ('wednesday', 'Wednesday'), ('thursday', 'Thursday'), ('friday', 'Friday')]

    @api.model
    def _generate_time_slots(self):
        slots = []
        for h in range(24):
            for m in (0, 15, 30, 45):
                v = f"{h:02d}:{m:02d}"
                slots.append((v, v))
        return slots

    @api.model
    def _get_payroll_year_bounds(self):
        today = fields.Date.context_today(self)
        if today < date(today.year, 12, 21):
            start = date(today.year - 1, 12, 21)
            end = date(today.year, 12, 20)
        else:
            start = date(today.year, 12, 21)
            end = date(today.year + 1, 12, 20)
        return start, end
