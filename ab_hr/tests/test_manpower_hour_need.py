# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase


class TestManpowerHourNeed(TransactionCase):

    def test_shortage_is_calculated_from_required_and_actual_hours(self):
        department = self.env['ab_hr_department'].create({'name': 'Branch A'})
        pharmacist_job = self.env['ab_hr_job'].create({'name': 'Pharmacist'})
        cashier_job = self.env['ab_hr_job'].create({'name': 'Cashier'})
        pharmacist = self.env['ab_hr_employee'].create({'name': 'Pharmacist Employee'})
        cashier = self.env['ab_hr_employee'].create({'name': 'Cashier Employee'})
        user = self.env['res.users'].create({
            'name': 'Branch User',
            'login': 'branch_user_manpower_test',
        })
        user_employee = self.env['ab_hr_employee'].create({
            'name': 'User Linked Employee',
            'user_id': user.id,
        })
        department.user_id = user

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
            'required_operating_hours': 80.0,
            'default_actual_daily_hours': 60.0,
        })
        accounting_plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': department.id,
            'job_title': cashier_job.id,
            'required_operating_hours': 80.0,
            'default_actual_daily_hours': 70.0,
        })

        shortage_plan.action_fetch_employees()
        accounting_plan.action_fetch_employees()

        self.assertEqual(shortage_plan.actual_available_hours, 60.0)
        self.assertEqual(shortage_plan.shortage_hours, 20.0)
        self.assertEqual(shortage_plan.actual_employee_ids, pharmacist)
        self.assertEqual(shortage_plan.employee_line_ids.employee_id, pharmacist)
        self.assertEqual(shortage_plan.employee_line_ids.actual_hours, 60.0)

        self.assertEqual(accounting_plan.actual_available_hours, 70.0)
        self.assertEqual(accounting_plan.shortage_hours, 10.0)
        self.assertEqual(accounting_plan.actual_employee_ids, cashier)
        grouped_hours = self.env['ab_hr_manpower_hour_need'].read_group(
            [('workplace', '=', department.id)],
            ['shortage_hours:sum'],
            ['workplace'],
        )
        self.assertEqual(grouped_hours[0]['shortage_hours'], 30.0)

        all_department_plan = self.env['ab_hr_manpower_hour_need'].create({
            'workplace': department.id,
            'required_operating_hours': 80.0,
            'default_actual_daily_hours': 8.0,
        })
        all_department_plan.action_fetch_employees()
        self.assertIn(user_employee, all_department_plan.actual_employee_ids)
