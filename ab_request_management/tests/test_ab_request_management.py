from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestAbRequestManagement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        self.group_user = self.env.ref("base.group_user")
        self.request_user_group = self.env.ref("ab_request_management.group_ab_request_management_user")
        self.request_readonly_group = self.env.ref("ab_request_management.group_ab_request_management_readonly")

        self.requester_user = self.Users.create(
            {
                "name": "Requester User",
                "login": "requester_user_test",
                "email": "requester_user_test@example.com",
                "groups_id": [(6, 0, [self.group_user.id, self.request_user_group.id])],
            }
        )
        self.dev_user = self.Users.create(
            {
                "name": "Developer User",
                "login": "developer_user_test",
                "email": "developer_user_test@example.com",
                "groups_id": [(6, 0, [self.group_user.id, self.request_user_group.id])],
            }
        )
        self.outsider_user = self.Users.create(
            {
                "name": "Outsider User",
                "login": "outsider_user_test",
                "email": "outsider_user_test@example.com",
                "groups_id": [(6, 0, [self.group_user.id, self.request_user_group.id])],
            }
        )
        self.readonly_user = self.Users.create(
            {
                "name": "Readonly User",
                "login": "readonly_user_test",
                "email": "readonly_user_test@example.com",
                "groups_id": [(6, 0, [self.group_user.id, self.request_readonly_group.id])],
            }
        )

        self.request_type = self.env["ab_request_type"].sudo().create(
            {
                "name": "Development",
                "code": "dev",
            }
        )

    def _create_ticket(self):
        with patch("odoo.addons.abdin_telegram.models.models.Telegram.send_by_bot", return_value=True):
            return self.env["ab_request_ticket"].with_user(self.requester_user).create(
                {
                    "title": "Need internal API update",
                    "description": "Support and engineering request.",
                    "assigned_to": self.dev_user.id,
                    "request_type_id": self.request_type.id,
                    "priority": "high",
                    "duration_days": 3,
                    "start_date": fields.Date.today(),
                }
            )

    def test_duration_days_must_be_at_least_one(self):
        with self.assertRaises(ValidationError):
            self.env["ab_request_ticket"].sudo().create(
                {
                    "title": "Invalid duration",
                    "description": "Should fail.",
                    "request_type_id": self.request_type.id,
                    "duration_days": 0,
                }
            )

    def test_ticket_workflow_requires_satisfied_before_close(self):
        ticket = self._create_ticket()
        self.assertNotEqual(ticket.ticket_number, "New")

        with patch("odoo.addons.abdin_telegram.models.models.Telegram.send_by_bot", return_value=True):
            ticket.with_user(self.dev_user).action_start_progress()
            ticket.with_user(self.dev_user).action_send_for_requester_confirmation()

            with self.assertRaises(UserError):
                ticket.with_user(self.dev_user).action_close_by_dev()

            ticket.with_user(self.requester_user).action_mark_satisfied()
            ticket.with_user(self.dev_user).action_close_by_dev()

        ticket.invalidate_recordset()
        self.assertEqual(ticket.stage, "closed_by_dev")
        self.assertTrue(ticket.requester_confirmation)
        self.assertTrue(ticket.actual_close_date)

    def test_record_rules_hide_unrelated_tickets(self):
        ticket = self._create_ticket()

        self.assertEqual(
            self.env["ab_request_ticket"].with_user(self.dev_user).search_count([("id", "=", ticket.id)]),
            1,
        )
        self.assertEqual(
            self.env["ab_request_ticket"].with_user(self.outsider_user).search_count([("id", "=", ticket.id)]),
            0,
        )
        with self.assertRaises(AccessError):
            ticket.with_user(self.outsider_user).read(["title"])

    def test_readonly_group_cannot_create_ticket(self):
        with self.assertRaises(AccessError):
            self.env["ab_request_ticket"].with_user(self.readonly_user).create(
                {
                    "title": "Readonly create",
                    "description": "Should fail.",
                    "request_type_id": self.request_type.id,
                    "duration_days": 1,
                }
            )
