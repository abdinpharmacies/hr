# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestManpowerHourNeed(TransactionCase):

    def test_shortage_is_calculated_from_required_and_actual_hours(self):
        department = self.env['ab_hr_department'].create({'name': 'Branch A'})
        pharmacist_job = self.env['ab_hr_job'].create({'name': 'Pharmacist'})
        cashier_job = self.env['ab_hr_job'].create({'name': 'Cashier'})
        pharmacist = self.env['ab_hr_employee'].create({'name': 'Pharmacist Employee'})
        cashier = self.env['ab_hr_employee'].create({'name': 'Cashier Employee'})
        self.env['ab_hr_job_occupied'].create({
            'employee_id': pharmacist.id,
            'job_id': pharmacist_job.id,
            'workplace': department.id,
        })
        self.env['ab_hr_job_occupied'].create({
            'employee_id': cashier.id,
            'job_id': cashier_job.id,
            'workplace': department.id,
        })

        shortage_plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': department.id,
            'job_title': pharmacist_job.id,
            'required_employee_count': 2,
            'required_operating_hours': 80.0,
            'default_actual_daily_hours': 60.0,
        })
        accounting_plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': department.id,
            'job_title': cashier_job.id,
            'required_operating_hours': 80.0,
            'default_actual_daily_hours': 70.0,
        })

        self.assertEqual(shortage_plan.actual_available_hours, 60.0)
        self.assertEqual(shortage_plan.shortage_hours, 20.0)
        self.assertEqual(shortage_plan.shortage_hours_display, '-20')
        self.assertEqual(shortage_plan.hours_capacity_status, 'shortage')
        self.assertEqual(shortage_plan.current_employee_count, 1)
        self.assertEqual(shortage_plan.employee_shortage_count, 1)
        self.assertEqual(shortage_plan.employee_shortage_display, '-1')
        self.assertEqual(shortage_plan.employee_capacity_status, 'shortage')
        self.assertEqual(shortage_plan.actual_employee_ids, pharmacist)
        self.assertEqual(shortage_plan.employee_line_ids.employee_id, pharmacist)
        self.assertEqual(shortage_plan.employee_line_ids.actual_hours, 60.0)

        self.assertEqual(accounting_plan.actual_available_hours, 70.0)
        self.assertEqual(accounting_plan.shortage_hours, 10.0)
        self.assertEqual(accounting_plan.current_employee_count, 1)
        self.assertEqual(accounting_plan.actual_employee_ids, cashier)
        grouped_hours = self.env['ab_hr_manpower_hour_need'].read_group(
            [('workplace', '=', department.id)],
            ['shortage_hours:sum'],
            ['workplace'],
        )
        self.assertEqual(grouped_hours[0]['shortage_hours'], 30.0)

        all_department_plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': department.id,
            'required_employee_count': 1,
            'required_operating_hours': 80.0,
            'default_actual_daily_hours': 8.0,
        })
        self.assertIn(pharmacist, all_department_plan.actual_employee_ids)
        self.assertIn(cashier, all_department_plan.actual_employee_ids)
        self.assertEqual(all_department_plan.employee_shortage_count, -1)
        self.assertEqual(all_department_plan.employee_shortage_display, '+1')
        self.assertEqual(all_department_plan.employee_capacity_status, 'increase')

        increase_department = self.env['ab_hr_department'].create({'name': 'Branch B'})
        increase_job = self.env['ab_hr_job'].create({'name': 'Increase Job'})
        increase_employee = self.env['ab_hr_employee'].create({'name': 'Increase Employee'})
        self.env['ab_hr_job_occupied'].create({
            'employee_id': increase_employee.id,
            'job_id': increase_job.id,
            'workplace': increase_department.id,
        })
        increase_plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': increase_department.id,
            'job_title': increase_job.id,
            'required_operating_hours': 50.0,
            'default_actual_daily_hours': 60.0,
        })
        self.assertEqual(increase_plan.shortage_hours, -10.0)
        self.assertEqual(increase_plan.shortage_hours_display, '+10')
        self.assertEqual(increase_plan.hours_capacity_status, 'increase')
