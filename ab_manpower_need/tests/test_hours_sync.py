from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestHoursSync(TransactionCase):
    def setUp(self):
        super().setUp()
        if 'ab_hr_basic_effect' not in self.env.registry.models:
            self.skipTest('Install ab_hr_effects to test Basic Working Hours propagation.')
        self.employee = self.env['ab_hr_employee'].create({'name': 'Manpower hours test'})
        self.branch = self.env['ab_hr_department'].create({'name': 'Manpower hours test'})
        self.job = self.env['ab_hr_job'].create({'name': 'Manpower hours test'})
        self.effect_type = self.env['ab_hr_effect_type'].create({
            'name': 'Manpower test basic hours', 'is_basic_effect': True,
            'basic_working_hour_number': True,
        })
        self.env['ab_hr_job_occupied'].create({
            'employee_id': self.employee.id, 'workplace': self.branch.id,
            'job_id': self.job.id,
        })
        self.plans = self.env['ab_hr_manpower_hour_need'].with_context(lang='en_US').create([
            {'workplace': self.branch.id, 'job_title': job,
             'required_employee_count': 1, 'required_operating_hours': 8,
             'default_actual_daily_hours': 8}
            for job in (False, self.job.id)
        ])

    def assert_capacity(self, hours, status):
        for plan in self.plans:
            self.assertEqual(plan.employee_line_ids.actual_hours, hours)
            self.assertEqual(plan.actual_available_hours, hours)
            self.assertEqual(plan.shortage_hours, hours - 8)
            self.assertEqual(plan.hours_capacity_status, status)
            self.assertEqual(plan.shortage_hours_display, f'{hours - 8:g}')
            self.assertEqual(plan.hours_status_label, status.title())
            self.assertEqual(plan.current_employee_count, 1)
            self.assertEqual(plan.employee_shortage_count, 0)
            self.assertEqual(plan.employee_capacity_status, 'balanced')

    def new_effect(self, value):
        return self.env['ab_hr_basic_effect'].create({
            'employee_id': self.employee.id, 'effect_type_id': self.effect_type.id,
            'effect_value': str(value),
        })

    def test_basic_hours_change_recomputes_lines_and_all_totals(self):
        effect = self.new_effect(8)
        self.assert_capacity(8, 'balanced')  # Warm caches before the source write.
        line_ids = self.plans.employee_line_ids.ids
        for hours, status in ((6, 'shortage'), (10, 'increase'), (8, 'balanced'), (0, 'shortage')):
            effect.write({'effect_value': str(hours)})
            # No plan write, fetch action, cache invalidation or explicit recompute.
            self.assert_capacity(hours, status)
            self.assertEqual(self.plans.employee_line_ids.ids, line_ids)

    def test_effect_lifecycle_recomputes_hours(self):
        self.assert_capacity(8, 'balanced')
        effect = self.new_effect(6)
        self.assert_capacity(6, 'shortage')
        effect.write({'active': False})
        self.assert_capacity(8, 'balanced')
        effect.write({'active': True})
        self.assert_capacity(6, 'shortage')
        self.effect_type.write({'basic_working_hour_number': False})
        self.assert_capacity(8, 'balanced')
        self.effect_type.write({'basic_working_hour_number': True})
        self.assert_capacity(6, 'shortage')
        replacement = self.env['ab_hr_employee'].create({'name': 'Other hours employee'})
        effect.write({'employee_id': replacement.id})
        self.assert_capacity(8, 'balanced')
        effect.write({'employee_id': self.employee.id})
        self.assert_capacity(6, 'shortage')

    def test_legacy_assigned_employees_without_lines(self):
        self.plans.employee_line_ids.unlink()
        effect = self.new_effect(8)
        self.assertEqual(self.plans.mapped('actual_available_hours'), [8, 8])
        effect.write({'effect_value': '6'})
        self.assertEqual(self.plans.mapped('actual_available_hours'), [6, 6])
        self.assertEqual(self.plans.mapped('shortage_hours'), [-2, -2])
        self.assertEqual(self.plans.mapped('hours_capacity_status'), ['shortage', 'shortage'])
