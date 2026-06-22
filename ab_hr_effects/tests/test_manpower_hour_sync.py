# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestManpowerHourSync(TransactionCase):

    def test_basic_working_hour_effect_updates_manpower_need_hours(self):
        department = self.env['ab_hr_department'].create({'name': 'Effect Sync Branch'})
        job = self.env['ab_hr_job'].create({'name': 'Effect Sync Job'})
        employee = self.env['ab_hr_employee'].create({
            'name': 'Effect Sync Employee',
            'department_id': department.id,
            'job_id': job.id,
        })
        effect_type = self.env.ref('ab_hr_effects.ab_effect_type_basic_working_hour_number')
        effect = self.env['ab_hr_basic_effect'].create({
            'employee_id': employee.id,
            'effect_type_id': effect_type.id,
            'effect_value': '6',
        })

        plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': department.id,
            'job_title': job.id,
            'required_operating_hours': 10.0,
            'default_actual_daily_hours': 8.0,
        })
        plan.action_fetch_employees()
        self.assertEqual(plan.actual_available_hours, 6.0)
        self.assertEqual(plan.shortage_hours, 4.0)
        self.assertEqual(plan.employee_line_ids.actual_hours, 6.0)

        effect.effect_value = '8'

        self.assertEqual(plan.actual_available_hours, 8.0)
        self.assertEqual(plan.shortage_hours, 2.0)
        self.assertEqual(plan.employee_line_ids.actual_hours, 8.0)
