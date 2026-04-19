from .base_engine import BasePayrollEngine


class DailyHoursEngine(BasePayrollEngine):

    def _get_period_attendances(self):
        if not self.employee or not self.period:
            return self.env['daily.hours.attendance']
        return self.env['daily.hours.attendance'].search([
            ('employee_id', '=', self.employee.id),
            ('date', '>=', self.period.start_date),
            ('date', '<=', self.period.end_date),
        ])

    def _get_extra_allowances_breakdown(self):
        extra_allowances = self.employee.extra_allowances_ids
        fixed_val = sum(extra_allowances.filtered(lambda a: a.calculation_type == 'fixed').mapped('amount'))
        prorated_base = sum(extra_allowances.filtered(lambda a: a.calculation_type == 'prorated').mapped('amount'))
        custom_base = sum(extra_allowances.filtered(lambda a: a.calculation_type == 'custom').mapped('amount'))
        return {
            'fixed': fixed_val,
            'prorated': prorated_base,
            'custom': custom_base,
        }

    def _build_metrics(self, required_days, attendances):
        required_days = required_days or 0
        contractual_hours = self.employee.working_hours_per_day or 0.0
        hourly_basic = self.employee.hourly_rate_basic or 0.0
        hourly_allowances = self.employee.hourly_rate_allowances or 0.0

        total_absence = sum(attendances.mapped('absence_days'))
        attendance_days = max(required_days - total_absence, 0.0)
        attendance_ratio = (attendance_days / required_days) if required_days else 0.0

        present_attendances = attendances.filtered(lambda att: not att.absence_days)
        total_worked_hours = sum(present_attendances.mapped('working_hours'))
        total_extra_minutes = sum(present_attendances.mapped('extra_minutes'))
        effective_worked_hours = max(total_worked_hours - (total_extra_minutes / 60.0), 0.0)
        avg_daily_hours = (effective_worked_hours / attendance_days) if attendance_days else 0.0
        allowance_basis_hours = min(max(avg_daily_hours, 0.0), contractual_hours)

        full_basic_salary = hourly_basic * contractual_hours * required_days
        full_allowances_pool = hourly_allowances * contractual_hours * required_days
        effective_allowances_pool = hourly_allowances * allowance_basis_hours * required_days

        day_basic = (full_basic_salary / required_days) if required_days else 0.0
        hour_basic = (day_basic / contractual_hours) if contractual_hours else 0.0
        hour_total = hour_basic + hourly_allowances

        return {
            'required_days': required_days,
            'contractual_hours': contractual_hours,
            'attendance_days': attendance_days,
            'attendance_ratio': attendance_ratio,
            'absence_days': total_absence,
            'total_worked_hours': total_worked_hours,
            'total_extra_minutes': total_extra_minutes,
            'avg_daily_hours': avg_daily_hours,
            'allowance_basis_hours': allowance_basis_hours,
            'full_basic_salary': full_basic_salary,
            'full_allowances_pool': full_allowances_pool,
            'effective_allowances_pool': effective_allowances_pool,
            'day_basic': day_basic,
            'hour_basic': hour_basic,
            'hour_total': hour_total,
        }

    def _calculate_attendance_financials(self, required_days, attendances):
        metrics = self._build_metrics(required_days, attendances)
        extras = self._get_extra_allowances_breakdown()

        effective_allowances = metrics['effective_allowances_pool'] * metrics['attendance_ratio']
        full_allowances = metrics['full_allowances_pool']
        minute_basic = metrics['hour_basic'] / 60.0
        minute_total = metrics['hour_total'] / 60.0

        penalty_late_arrival = 0.0
        penalty_unauthorized_shift = 0.0
        penalty_shortage_hours = 0.0
        earning_grace_period_overtime = 0.0
        earning_authorized_overtime = 0.0
        earning_two_hour_permission = 0.0

        for att in attendances.filtered(lambda attendance: not attendance.absence_days):
            reimbursed_shortage_minutes = 120.0 if att.authorized_two_hour_permission else 0.0
            effective_shortage_minutes = max(att.shortage_minutes - reimbursed_shortage_minutes, 0.0)

            if att.is_late_arrival and not att.authorized_two_hour_permission:
                penalty_late_arrival += 0.25 * metrics['day_basic']

            if att.is_unauthorized_shift and not att.authorized_two_hour_permission:
                penalty_unauthorized_shift += 0.25 * metrics['day_basic']

            if effective_shortage_minutes > 10.0:
                penalty_shortage_hours += effective_shortage_minutes * minute_basic

            if att.authorized_two_hour_permission and att.shortage_minutes > 0:
                earning_two_hour_permission += min(att.shortage_minutes, 120.0) * minute_total

            if att.extra_minutes > 0:
                grace_minutes = min(att.extra_minutes, 30.0)
                earning_grace_period_overtime += grace_minutes * minute_total

                if att.extra_minutes > 30.0 and att.authorized_overtime:
                    earning_authorized_overtime += (att.extra_minutes - 30.0) * minute_total

        prorated_actual = extras['prorated'] * metrics['attendance_ratio']
        custom_actual = extras['custom'] * metrics['attendance_ratio']
        agreement_salary = (
            metrics['full_basic_salary']
            + full_allowances
            + extras['fixed']
            + extras['prorated']
            + extras['custom']
        )

        return {
            'metrics': metrics,
            'agreement_salary': agreement_salary,
            'effective_allowances': effective_allowances,
            'allowance_nature_of_work': effective_allowances * 0.30,
            'allowance_performance': effective_allowances * 0.30,
            'allowance_cost_of_living': effective_allowances * 0.20,
            'allowance_dedication': effective_allowances * 0.20,
            'penalty_late_arrival': penalty_late_arrival,
            'penalty_unauthorized_shift': penalty_unauthorized_shift,
            'penalty_shortage_hours': penalty_shortage_hours,
            'earning_grace_period_overtime': earning_grace_period_overtime,
            'earning_authorized_overtime': earning_authorized_overtime,
            'earning_two_hour_permission': earning_two_hour_permission,
            'extra_allowances_fixed': extras['fixed'],
            'extra_allowances_prorated': prorated_actual,
            'extra_allowances_custom': custom_actual,
            'extra_allowances_actual': extras['fixed'] + prorated_actual + custom_actual,
        }

    def calculate_salaries(self):
        """Daily-hours structure values based on contractual hours and actual attendance."""
        dynamic_results = self.evaluate_rules()
        if dynamic_results:
            results = {
                'basic_salary': dynamic_results.get('basic_salary', 0.0),
                'total_basic_allowances': dynamic_results.get('total_basic_allowances', 0.0),
            }
            results.update(dynamic_results)
            return results

        emp = self.employee
        if emp:
            required_days = 0
            if self.record and hasattr(self.record, 'working_days_in_period'):
                required_days = self.record.working_days_in_period or 0
            elif self.period and hasattr(self.period, 'calculate_days_required'):
                required_days = self.period.calculate_days_required(
                    emp.weekly_off_day_1,
                    emp.weekly_off_day_2,
                )

            summary = self._calculate_attendance_financials(required_days, self._get_period_attendances())
            metrics = summary['metrics']
            return {
                'basic_salary': metrics['full_basic_salary'],
                'allowance_nature_of_work': summary['allowance_nature_of_work'],
                'allowance_performance': summary['allowance_performance'],
                'allowance_cost_of_living': summary['allowance_cost_of_living'],
                'allowance_dedication': summary['allowance_dedication'],
                'total_basic_allowances': summary['effective_allowances'],
                'attendance_percentage': metrics['attendance_ratio'] * 100.0,
                'agreement_salary': summary['agreement_salary'],
                'penalty_late_arrival': summary['penalty_late_arrival'],
                'penalty_unauthorized_shift': summary['penalty_unauthorized_shift'],
                'penalty_shortage_hours': summary['penalty_shortage_hours'],
                'earning_grace_period_overtime': summary['earning_grace_period_overtime'],
                'earning_authorized_overtime': summary['earning_authorized_overtime'],
                'earning_two_hour_permission': summary['earning_two_hour_permission'],
            }
        return {}

    def calculate_daily_hourly_values(self, basic_salary, total_basic_allowances, extra_allowances, working_days):
        """Agreement daily and hourly values for the selected period."""
        days = working_days or 1
        day_basic = basic_salary / days
        day_allowances = (total_basic_allowances + extra_allowances) / days

        hours = self.employee.working_hours_per_day or 1
        hour_basic = day_basic / hours
        hour_allowances_basic = (total_basic_allowances / days) / hours

        return {
            'day_basic': day_basic,
            'day_allowances': day_allowances,
            'day_total': day_basic + day_allowances,
            'hour_basic': hour_basic,
            'hour_allowances': hour_allowances_basic,
            'hour_total': hour_basic + hour_allowances_basic,
        }

    def calculate_forget_penalty(self, day_basic):
        """Penalty for repeated forgot-checkout events."""
        count = self.env['daily.hours.attendance'].search_count([
            ('employee_id', '=', self.employee.id),
            ('date', '>=', self.period.start_date),
            ('date', '<=', self.period.end_date),
            ('attendance_status', '=', 'forget_checkout')
        ])

        days_to_deduct = 0
        if count == 2:
            days_to_deduct = 1
        elif count == 3:
            days_to_deduct = 3
        elif count >= 4:
            days_to_deduct = 5

        return {
            'forget_fingerprint_count': count,
            'forget_fingerprint_penalty': days_to_deduct * day_basic
        }

    def calculate_payslip(self, structure, attendances):
        """Daily-hours payslip aligned with the Excel calculation model."""
        required_days = structure.working_days_in_period or 1
        summary = self._calculate_attendance_financials(required_days, attendances)
        metrics = summary['metrics']
        salary_basic = metrics['full_basic_salary'] - (metrics['absence_days'] * metrics['day_basic'])

        return {
            'attendance_percentage': metrics['attendance_ratio'] * 100.0,
            'agreement_salary': summary['agreement_salary'],
            'salary_basic': salary_basic,
            'allowances_basic_four': summary['effective_allowances'],
            'extra_allowances_fixed': summary['extra_allowances_fixed'],
            'extra_allowances_prorated': summary['extra_allowances_prorated'],
            'extra_allowances_custom': summary['extra_allowances_custom'],
            'extra_allowances': summary['extra_allowances_actual'],
            'penalty_late_arrival': summary['penalty_late_arrival'],
            'penalty_unauthorized_shift': summary['penalty_unauthorized_shift'],
            'penalty_shortage_hours': summary['penalty_shortage_hours'],
            'earning_grace_period_overtime': summary['earning_grace_period_overtime'],
            'earning_authorized_overtime': summary['earning_authorized_overtime'],
            'earning_two_hour_permission': summary['earning_two_hour_permission'],
        }
