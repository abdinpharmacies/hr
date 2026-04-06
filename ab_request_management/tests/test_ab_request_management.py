from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestAbRequestManagement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        self.Employees = self.env["ab_hr_employee"].sudo()
        self.Departments = self.env["ab_hr_department"].sudo()
        self.group_user = self.env.ref("base.group_user")
        self.request_user_group = self.env.ref("ab_request_management.group_ab_request_management_user")
        self.request_manager_group = self.env.ref("ab_request_management.group_ab_request_management_manager")
        self.request_admin_group = self.env.ref("ab_request_management.group_ab_request_management_admin")

        self.requester_user = self._create_user("Requester User", "requester_user_test", [self.request_user_group.id])
        self.manager_user = self._create_user("Manager User", "manager_user_test", [self.request_manager_group.id])
        self.assignee_user = self._create_user("Assignee User", "assignee_user_test", [self.request_user_group.id])
        self.second_assignee_user = self._create_user(
            "Second Assignee User", "second_assignee_user_test", [self.request_user_group.id]
        )
        self.outsider_user = self._create_user("Outsider User", "outsider_user_test", [self.request_user_group.id])
        self.admin_user = self._create_user("Admin User", "admin_user_test", [self.request_admin_group.id])

        self.requester_employee = self._create_employee("Requester Employee", self.requester_user)
        self.manager_employee = self._create_employee("Manager Employee", self.manager_user)
        self.assignee_employee = self._create_employee("Assignee Employee", self.assignee_user)
        self.second_assignee_employee = self._create_employee("Second Assignee Employee", self.second_assignee_user)
        self.outsider_employee = self._create_employee("Outsider Employee", self.outsider_user)
        self.admin_employee = self._create_employee("Admin Employee", self.admin_user)

        self.department = self.Departments.create(
            {
                "name": "Support",
                "manager_id": self.manager_employee.id,
            }
        )
        self.requester_employee.department_id = self.department.id
        self.manager_employee.department_id = self.department.id
        self.assignee_employee.department_id = self.department.id
        self.second_assignee_employee.department_id = self.department.id
        self.admin_employee.department_id = self.department.id
        self.other_department = self.Departments.create({"name": "Finance"})
        self.outsider_employee.department_id = self.other_department.id

        self.request_type = self.env["ab.request.type"].sudo().create(
            {
                "name": "System Access",
                "department_id": self.department.id,
            }
        )

    def _create_user(self, name, login, extra_groups):
        return self.Users.create(
            {
                "name": name,
                "login": login,
                "email": f"{login}@example.com",
                "group_ids": [(6, 0, [self.group_user.id, *extra_groups])],
            }
        )

    def _create_employee(self, name, user):
        return self.Employees.create(
            {
                "name": name,
                "user_id": user.id,
            }
        )

    def _create_request(self):
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            return self.env["ab.request"].with_user(self.requester_user).create(
                {
                    "subject": "Access to reporting dashboard",
                    "description": "Request access for quarterly review.",
                    "request_type_id": self.request_type.id,
                }
            )

    def test_request_creation_sets_under_review_and_manager(self):
        request = self._create_request()
        self.assertEqual(request.state, "under_review")
        self.assertEqual(request.requester_id, self.requester_employee)
        self.assertEqual(request.manager_id, self.manager_employee)

    def test_subject_and_description_must_contain_letters(self):
        with self.assertRaises(ValidationError):
            self.env["ab.request"].with_user(self.requester_user).create(
                {
                    "subject": "123456",
                    "description": "Valid description",
                    "request_type_id": self.request_type.id,
                }
            )
        with self.assertRaises(ValidationError):
            self.env["ab.request"].with_user(self.requester_user).create(
                {
                    "subject": "Valid subject",
                    "description": "@@@###",
                    "request_type_id": self.request_type.id,
                }
            )

    def test_get_request_admin_partners_uses_implied_group_memberships(self):
        admin_partners = self.env["ab.request"]._get_request_admin_partners()
        self.assertIn(self.admin_user.partner_id, admin_partners)

    def test_subject_and_description_are_immutable(self):
        request = self._create_request()
        with self.assertRaises(UserError):
            request.with_user(self.manager_user).write({"subject": "Changed"})
        with self.assertRaises(UserError):
            request.with_user(self.manager_user).write({"description": "Changed"})

    def test_deadline_cannot_be_in_the_past(self):
        request = self._create_request()
        past_deadline = fields.Datetime.to_string(fields.Datetime.now() - timedelta(days=1))
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.manager_user).action_approve()
        with self.assertRaises(ValidationError):
            request.with_user(self.manager_user).write({"deadline": past_deadline})

    def test_full_request_lifecycle(self):
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.manager_user).action_approve()
            request.with_user(self.manager_user).with_context(allow_assignment_write=True).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id, self.second_assignee_employee.id])],
                    "priority": "high",
                }
            )
            request.with_user(self.manager_user).action_assign()
            request.with_user(self.assignee_user).action_request_confirmation()
            request.with_user(self.requester_user).action_request_changes()
            request.with_user(self.assignee_user).action_request_confirmation()
            request.with_user(self.requester_user).action_mark_satisfied()
            request.with_user(self.assignee_user).action_close()
        self.assertEqual(request.state, "closed")
        self.assertSetEqual(set(request.assigned_employee_ids.ids), {self.assignee_employee.id, self.second_assignee_employee.id})

    def test_manager_can_edit_assignment_details_after_assignment(self):
        request = self._create_request()
        future_deadline = fields.Datetime.to_string(fields.Datetime.now() + timedelta(days=2))
        updated_deadline = fields.Datetime.to_string(fields.Datetime.now() + timedelta(days=4))
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.manager_user).action_approve()
            request.with_user(self.manager_user).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id])],
                    "priority": "medium",
                    "deadline": future_deadline,
                }
            )
            request.with_user(self.manager_user).action_assign()
            request.with_user(self.manager_user).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id, self.second_assignee_employee.id])],
                    "priority": "high",
                    "deadline": updated_deadline,
                }
            )
        self.assertSetEqual(set(request.assigned_employee_ids.ids), {self.assignee_employee.id, self.second_assignee_employee.id})
        self.assertEqual(request.priority, "high")
        self.assertEqual(fields.Datetime.to_string(request.deadline), updated_deadline)

    def test_requester_can_add_followup_before_confirmation(self):
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            followup = self.env["ab.request.followup"].with_user(self.requester_user).create(
                {
                    "request_id": request.id,
                    "description": "Please prioritize this request.",
                }
            )
        self.assertEqual(followup.user_id, self.requester_user)

    def test_requester_followup_restricted_on_closed_request(self):
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.manager_user).action_approve()
            request.with_user(self.manager_user).with_context(allow_assignment_write=True).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id])],
                }
            )
            request.with_user(self.manager_user).action_assign()
            request.with_user(self.assignee_user).action_request_confirmation()
            request.with_user(self.requester_user).action_mark_satisfied()
            request.with_user(self.assignee_user).action_close()
        with self.assertRaises(UserError):
            self.env["ab.request.followup"].with_user(self.requester_user).create(
                {
                    "request_id": request.id,
                    "description": "This should not be allowed after closing.",
                }
            )

    def test_assigned_employee_must_belong_to_request_department(self):
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.manager_user).action_approve()
        with self.assertRaises(ValidationError):
            request.with_user(self.manager_user).with_context(allow_assignment_write=True).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id, self.outsider_employee.id])],
                }
            )

    def test_admin_has_manager_level_access_on_requests(self):
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.admin_user).action_approve()
            request.with_user(self.admin_user).with_context(allow_assignment_write=True).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id, self.second_assignee_employee.id])],
                    "priority": "high",
                }
            )
            request.with_user(self.admin_user).action_assign()
            followup = self.env["ab.request.followup"].with_user(self.admin_user).create(
                {
                    "request_id": request.id,
                    "description": "Admin follow-up.",
                }
            )
            request.with_user(self.admin_user).action_request_confirmation()
            request.with_user(self.requester_user).action_mark_satisfied()
            request.with_user(self.admin_user).action_close()
        self.assertEqual(request.state, "closed")
        self.assertEqual(followup.user_id, self.admin_user)
        self.assertSetEqual(set(request.assigned_employee_ids.ids), {self.assignee_employee.id, self.second_assignee_employee.id})

    def test_admin_can_approve_when_admin_user_is_department_manager(self):
        self.department.manager_id = self.admin_employee.id
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.admin_user).action_approve()
        self.assertEqual(request.state, "scheduled")

    def test_record_rules_hide_unrelated_requests(self):
        request = self._create_request()
        self.assertEqual(self.env["ab.request"].with_user(self.outsider_user).search_count([("id", "=", request.id)]), 0)
        with self.assertRaises(AccessError):
            request.with_user(self.outsider_user).read(["subject"])

    def test_any_assigned_employee_can_access_and_progress_request(self):
        request = self._create_request()
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request.with_user(self.manager_user).action_approve()
            request.with_user(self.manager_user).with_context(allow_assignment_write=True).write(
                {
                    "assigned_employee_ids": [(6, 0, [self.assignee_employee.id, self.second_assignee_employee.id])],
                    "priority": "high",
                }
            )
            request.with_user(self.manager_user).action_assign()

        self.assertEqual(self.env["ab.request"].with_user(self.second_assignee_user).search_count([("id", "=", request.id)]), 1)
        request.with_user(self.second_assignee_user).action_request_confirmation()
        self.assertEqual(request.state, "under_requester_confirmation")

    def test_request_type_requires_department_manager(self):
        unmanaged_department = self.Departments.create({"name": "No Manager"})
        with self.assertRaises(ValidationError):
            self.env["ab.request.type"].sudo().create(
                {
                    "name": "Invalid Type",
                    "department_id": unmanaged_department.id,
                }
            )
