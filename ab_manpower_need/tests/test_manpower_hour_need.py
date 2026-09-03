# -*- coding: utf-8 -*-
from unittest.mock import patch

from lxml import etree

from odoo.tests.common import TransactionCase


class TestManpowerHourNeed(TransactionCase):

    def _get_available_department(self):
        used_department_ids = self.env['ab_hr_manpower_hour_need'].search([
            ('job_title', '=', False),
        ]).mapped('workplace').ids
        domain = [('id', 'not in', used_department_ids)] if used_department_ids else []
        department = self.env['ab_hr_department'].search(domain, limit=1)
        if not department:
            self.skipTest('No existing HR department is available in this database.')
        return department

    def test_capacity_status_and_display_helpers(self):
        plan = self.env['ab_hr_manpower_hour_need'].new({})

        self.assertEqual(plan._get_capacity_status(-10), 'shortage')
        self.assertEqual(plan._get_capacity_status(5), 'increase')
        self.assertEqual(plan._get_capacity_status(0), 'balanced')

        self.assertEqual(plan._format_capacity_display(-20.0), '-20')
        self.assertEqual(plan._format_capacity_display(3), '3')
        self.assertEqual(plan._format_capacity_display(0), '0')

    def test_employee_variance_computes_current_minus_required(self):
        plan = self.env['ab_hr_manpower_hour_need'].new({
            'required_employee_count': 8,
        })

        test_cases = [
            (5, -3, 'shortage', '-3'),
            (10, 2, 'increase', '2'),
            (8, 0, 'balanced', '0'),
        ]
        for current_employees, expected_variance, expected_status, expected_display in test_cases:
            with self.subTest(current_employees=current_employees):
                plan.current_employee_count = current_employees
                plan._compute_employee_shortage_count()
                plan._compute_capacity_displays()

                self.assertEqual(plan.employee_shortage_count, expected_variance)
                self.assertEqual(plan.employee_capacity_status, expected_status)
                self.assertEqual(plan.employee_shortage_display, expected_display)

    def test_hours_variance_computes_actual_minus_required(self):
        plan = self.env['ab_hr_manpower_hour_need'].new({
            'required_operating_hours': 80.0,
        })

        test_cases = [
            (60.0, -20.0, 'shortage', '-20'),
            (100.0, 20.0, 'increase', '20'),
            (80.0, 0.0, 'balanced', '0'),
        ]
        for actual_hours, expected_variance, expected_status, expected_display in test_cases:
            with self.subTest(actual_hours=actual_hours):
                plan.actual_available_hours = actual_hours
                plan._compute_shortage_hours()
                plan._compute_capacity_displays()

                self.assertEqual(plan.shortage_hours, expected_variance)
                self.assertEqual(plan.hours_capacity_status, expected_status)
                self.assertEqual(plan.shortage_hours_display, expected_display)

    def test_onchange_uses_actual_minus_required_variance(self):
        plan = self.env['ab_hr_manpower_hour_need'].new({
            'required_operating_hours': 80.0,
        })
        capacity_values = {
            'actual_employee_ids': [(6, 0, [])],
            'employee_line_ids': [(5, 0, 0)],
            'actual_available_hours': 60.0,
        }

        with patch.object(type(plan), '_get_actual_capacity_values', return_value=capacity_values):
            plan._onchange_capacity_inputs()

        self.assertEqual(plan.actual_available_hours, 60.0)
        self.assertEqual(plan.shortage_hours, -20.0)

    def test_shortage_filter_targets_negative_variance(self):
        view = self.env.ref('ab_manpower_need.manpower_hour_need_search')
        arch = etree.fromstring(view.arch_db.encode())
        shortage_filter = arch.xpath("//filter[@name='filter_shortage']")[0]

        self.assertEqual(shortage_filter.get('domain'), "[('shortage_hours', '<', 0)]")

    def test_visual_indicators_treat_negative_values_as_shortage(self):
        list_view = self.env.ref('ab_manpower_need.manpower_hour_need_view_list')
        list_arch = etree.fromstring(list_view.arch_db.encode())

        for field_name in ('employee_shortage_count', 'shortage_hours'):
            field_node = list_arch.xpath(f"//field[@name='{field_name}']")[0]
            self.assertEqual(field_node.get('decoration-danger'), f'{field_name} < 0')
            self.assertEqual(field_node.get('decoration-success'), f'{field_name} > 0')

        kanban_view = self.env.ref('ab_manpower_need.manpower_hour_need_view_kanban')
        kanban_arch = etree.fromstring(kanban_view.arch_db.encode())
        employee_class = kanban_arch.xpath("//strong[field[@name='employee_shortage_display']]")[0].get('t-att-class')
        hours_class = kanban_arch.xpath("//strong[field[@name='shortage_hours_display']]")[0].get('t-att-class')

        self.assertIn("record.employee_shortage_count.raw_value < 0 ? 'text-danger'", employee_class)
        self.assertIn("record.employee_shortage_count.raw_value > 0 ? 'text-success'", employee_class)
        self.assertIn("record.shortage_hours.raw_value < 0 ? 'text-danger'", hours_class)
        self.assertIn("record.shortage_hours.raw_value > 0 ? 'text-success'", hours_class)

    def test_auto_fetch_behavior_is_still_called_on_create_and_write(self):
        department = self._get_available_department()
        ManpowerHourNeed = self.env['ab_hr_manpower_hour_need']

        with patch.object(type(ManpowerHourNeed), '_auto_fetch_actual_capacity', return_value=None) as auto_fetch:
            plan = ManpowerHourNeed.create({
                'workplace': department.id,
                'required_employee_count': 2,
                'required_operating_hours': 80.0,
                'actual_available_hours': 60.0,
            })
            self.assertEqual(auto_fetch.call_count, 1)

            plan.write({'default_actual_daily_hours': 7.5})
            self.assertEqual(auto_fetch.call_count, 2)
