# -*- coding: utf-8 -*-
from unittest.mock import patch

from odoo.tests.common import TransactionCase


class TestManpowerHourNeed(TransactionCase):

    def test_capacity_status_and_display_helpers(self):
        plan = self.env['ab_hr_manpower_hour_need'].new({})

        self.assertEqual(plan._get_capacity_status(10), 'shortage')
        self.assertEqual(plan._get_capacity_status(-5), 'increase')
        self.assertEqual(plan._get_capacity_status(0), 'balanced')

        self.assertEqual(plan._format_capacity_display(20.0), '-20')
        self.assertEqual(plan._format_capacity_display(-3), '+3')
        self.assertEqual(plan._format_capacity_display(0), '0')

    def test_shortage_computes_from_manual_actual_hours(self):
        used_department_ids = self.env['ab_hr_manpower_hour_need'].search([
            ('job_title', '=', False),
        ]).mapped('workplace').ids
        domain = [('id', 'not in', used_department_ids)] if used_department_ids else []
        department = self.env['ab_hr_department'].search(domain, limit=1)
        if not department:
            self.skipTest('No existing HR department is available in this database.')

        ManpowerHourNeed = self.env['ab_hr_manpower_hour_need']
        with patch.object(type(ManpowerHourNeed), '_auto_fetch_actual_capacity', return_value=None):
            plan = ManpowerHourNeed.create({
                'workplace': department.id,
                'required_employee_count': 2,
                'required_operating_hours': 80.0,
                'actual_available_hours': 60.0,
            })

        self.assertEqual(plan.shortage_hours, 20.0)
        self.assertEqual(plan.shortage_hours_display, '-20')
        self.assertEqual(plan.hours_capacity_status, 'shortage')
