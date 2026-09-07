from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestAssignmentSync(TransactionCase):
    def setUp(self):
        super().setUp()
        self.branches = self.env['ab_hr_department'].create([
            {'name': 'Manpower sync test A'}, {'name': 'Manpower sync test B'},
        ])
        self.jobs = self.env['ab_hr_job'].create([
            {'name': 'Manpower sync job A'}, {'name': 'Manpower sync job B'},
        ])
        self.employee = self.env['ab_hr_employee'].create({'name': 'Manpower sync employee'})
        self.plan_model = self.env['ab_hr_manpower_hour_need']
        self.plans = self.plan_model.create([
            {'workplace': branch.id, 'job_title': job_id,
             'required_employee_count': 1, 'required_operating_hours': 8,
             'default_actual_daily_hours': 8}
            for branch in self.branches for job_id in [False] + self.jobs.ids
        ])
        self.plan = self.plans.filtered(
            lambda p: p.workplace == self.branches[0] and p.job_title == self.jobs[0])

    def assignment(self, **extra):
        return self.env['ab_hr_job_occupied'].create(dict({
            'employee_id': self.employee.id, 'workplace': self.branches[0].id,
            'job_id': self.jobs[0].id,
        }, **extra))

    def test_create_updates_count_hours_and_status(self):
        self.assertEqual(self.plan.employee_capacity_status, 'shortage')
        self.assignment()
        self.assertEqual(self.plan.current_employee_count, 1)
        self.assertEqual(self.plan.actual_employee_ids, self.employee)
        self.assertEqual(self.plan.employee_line_ids.employee_id, self.employee)
        self.assertEqual(self.plan.actual_available_hours, 8)
        self.assertEqual(self.plan.employee_shortage_count, 0)
        self.assertEqual(self.plan.employee_capacity_status, 'balanced')
        self.assertEqual(self.plan.hours_capacity_status, 'balanced')

    def test_only_matching_and_branch_wide_plans_refresh(self):
        refreshed = []
        original = type(self.plan)._auto_fetch_actual_capacity
        def capture(plans):
            refreshed.extend(plans.ids)
            return original(plans)
        with patch.object(type(self.plan), '_auto_fetch_actual_capacity', capture):
            self.assignment()
        expected = self.plans.filtered(lambda p: p.workplace == self.branches[0]
                                       and (not p.job_title or p.job_title == self.jobs[0]))
        self.assertEqual(set(refreshed), set(expected.ids))
        self.assertTrue(all(p.current_employee_count == 1 for p in expected))
        self.assertTrue(all(p.current_employee_count == 0 for p in self.plans - expected))

    def test_dates_exclude_and_clearing_dates_restores(self):
        assignment = self.assignment(issue_date=fields.Date.today())
        self.assertEqual(self.plan.current_employee_count, 0)
        assignment.write({'issue_date': False})
        self.assertEqual(self.plan.current_employee_count, 1)
        assignment.write({'termination_date': fields.Date.today()})
        self.assertEqual(self.plan.current_employee_count, 0)
        self.assertFalse(self.plan.employee_line_ids)
        self.assertEqual(self.plan.actual_available_hours, 0)
        assignment.write({'termination_date': False})
        self.assertEqual(self.plan.current_employee_count, 1)

    def test_transfer_refreshes_old_and_new_combinations(self):
        assignment = self.assignment()
        assignment.write({'workplace': self.branches[1].id, 'job_id': self.jobs[1].id})
        for plan in self.plans:
            expected = int(plan.workplace == self.branches[1]
                           and (not plan.job_title or plan.job_title == self.jobs[1]))
            self.assertEqual(plan.current_employee_count, expected)

    def test_delete_does_not_recount_employee_department(self):
        self.employee.write({'department_id': self.branches[0].id, 'job_id': self.jobs[0].id})
        assignment = self.assignment()
        assignment.unlink()
        self.assertEqual(self.plan.current_employee_count, 0)
        self.assertEqual(self.plan.employee_capacity_status, 'shortage')
        self.assertFalse(self.plan.actual_employee_ids)

    def test_batch_create_write_delete_and_unique_employees(self):
        values = {'employee_id': self.employee.id, 'job_id': self.jobs[0].id,
                  'workplace': self.branches[0].id}
        assignments = self.env['ab_hr_job_occupied'].create([dict(values), dict(values)])
        self.assertEqual(self.plan.current_employee_count, 1)
        assignments.write({'issue_date': fields.Date.today()})
        self.assertEqual(self.plan.current_employee_count, 0)
        assignments.write({'issue_date': False})
        assignments.unlink()
        self.assertEqual(self.plan.current_employee_count, 0)

    def test_employee_replacement_rebuilds_lines(self):
        assignment = self.assignment()
        replacement = self.env['ab_hr_employee'].create({'name': 'Manpower replacement'})
        assignment.write({'employee_id': replacement.id})
        self.assertEqual(self.plan.actual_employee_ids, replacement)
        self.assertEqual(self.plan.employee_line_ids.employee_id, replacement)

    def test_unauthorized_assignment_does_not_refresh_plans(self):
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            self.env['ab_hr_job_occupied'].with_user(public).create({
                'employee_id': self.employee.id, 'workplace': self.branches[0].id,
                'job_id': self.jobs[0].id,
            })
        self.assertEqual(self.plan.current_employee_count, 0)
