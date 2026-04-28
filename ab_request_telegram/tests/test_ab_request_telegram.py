from unittest.mock import patch

from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestAbRequestTelegram(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        self.Employees = self.env["ab_hr_employee"].sudo()
        self.Departments = self.env["ab_hr_department"].sudo()
        self.RequestCategories = self.env["ab_request_category"].sudo()
        self.HrBot = self.env["ab_hr_bot"].sudo()
        self.group_user = self.env.ref("base.group_user")
        self.request_user_group = self.env.ref("ab_request_management.group_ab_request_management_user")
        self.request_manager_group = self.env.ref("ab_request_management.group_ab_request_management_manager")

        self.requester_user = self._create_user("Requester User", "requester_tg_user", [self.request_user_group.id])
        self.manager_user = self._create_user("Manager User", "manager_tg_user", [self.request_manager_group.id])
        self.requester_employee = self._create_employee("Requester Employee", self.requester_user)
        self.manager_employee = self._create_employee("Manager Employee", self.manager_user)
        self.department = self.Departments.create({"name": "Support", "manager_id": self.manager_employee.id})
        self.requester_employee.department_id = self.department.id
        self.manager_employee.department_id = self.department.id
        self.request_category = self.RequestCategories.create({"name": "Complaints"})
        self.request_type = self.env["ab_request_type"].sudo().create(
            {
                "name": "Late Response Complaint",
                "department_id": self.department.id,
                "category_id": self.request_category.id,
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
        return self.Employees.create({"name": name, "user_id": user.id})

    def test_register_employee_chat_does_not_block_employee_reassignment(self):
        original_link = self.HrBot.create(
            {
                "employee_id": self.manager_employee.id,
                "chat_id": "1001",
            }
        )

        # Should not raise ValidationError anymore
        link = self.HrBot.register_employee_chat(self.manager_employee.id, "2002")

        # Integrity check: should still be linked to 1001
        self.assertEqual(link.id, original_link.id)
        self.assertEqual(link.chat_id, "1001")
        self.assertEqual(link.employee_id.id, self.manager_employee.id)

    def test_register_employee_chat_uses_employee_table_id_column(self):
        link = self.HrBot.register_employee_chat(self.manager_employee.id, "3003", telegram_username="@manager_test")

        self.assertEqual(link.employee_id.id, self.manager_employee.id)
        self.assertEqual(link.employee_ref_id, self.manager_employee.id)
        self.assertEqual(link.telegram_username, "manager_test")

    def test_register_employee_chat_reuses_existing_binding_for_same_pair(self):
        original_link = self.HrBot.create(
            {
                "employee_id": self.manager_employee.id,
                "chat_id": "3003",
                "telegram_username": "original_name",
            }
        )

        link = self.HrBot.register_employee_chat(self.manager_employee.id, "3003", telegram_username="@manager_test")

        self.assertEqual(link.id, original_link.id)
        self.assertEqual(link.chat_id, "3003")
        self.assertEqual(link.telegram_username, "original_name")

    def test_process_telegram_update_rejects_invalid_employee_id(self):
        with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", return_value=True):
            result = self.HrBot.process_telegram_update(
                {
                    "message": {
                        "chat": {"id": 7788},
                        "from": {"id": 42, "is_bot": False},
                        "text": "999999",
                    }
                }
            )

        self.assertFalse(result["ok"])
        self.assertFalse(self.HrBot.search([("chat_id", "=", "7788")], limit=1))

    def test_process_telegram_update_blocks_chat_hijack_attempt(self):
        self.HrBot.create(
            {
                "employee_id": self.manager_employee.id,
                "chat_id": "7788",
            }
        )
        sent_messages = []

        def _capture_send(service_self, chat_id, message):
            sent_messages.append((chat_id, message))
            return True

        with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", _capture_send):
            result = self.HrBot.process_telegram_update(
                {
                    "message": {
                        "chat": {"id": 7788, "type": "private"},
                        "from": {"id": 42, "is_bot": False, "username": "attacker"},
                        "text": str(self.requester_employee.id),
                    }
                }
            )

        link = self.HrBot.search([("chat_id", "=", "7788")], limit=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "binding_conflict")
        self.assertEqual(link.employee_id.id, self.manager_employee.id)
        self.assertEqual(len(sent_messages), 2)
        self.assertIn("Validation Warning", sent_messages[0][1])
        self.assertIn("Validation Error", sent_messages[1][1])

    def test_write_does_not_raise_on_binding_mutation_attempt(self):
        link = self.HrBot.create(
            {
                "employee_id": self.manager_employee.id,
                "chat_id": "556677",
            }
        )

        # Should not raise, but should skip the update to chat_id
        link.write({"chat_id": "998877"})
        self.assertEqual(link.chat_id, "556677")

        # Should not raise, but should skip the update to employee_id
        link.write({"employee_id": self.requester_employee.id})
        self.assertEqual(link.employee_id.id, self.manager_employee.id)

    def test_process_telegram_update_warns_when_employee_has_different_chat(self):
        self.HrBot.create(
            {
                "employee_id": self.manager_employee.id,
                "chat_id": "556677",
            }
        )
        sent_messages = []

        def _capture_send(service_self, chat_id, message):
            sent_messages.append((chat_id, message))
            return True

        with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", _capture_send):
            result = self.HrBot.process_telegram_update(
                {
                    "message": {
                        "chat": {"id": 889900, "type": "private"},
                        "from": {"id": 43, "is_bot": False, "username": "manager_tg_user"},
                        "text": str(self.manager_employee.id),
                    }
                }
            )

        link = self.HrBot.search([("employee_id", "=", self.manager_employee.id)], limit=1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["message"], "binding_conflict")
        self.assertEqual(link.chat_id, "556677")
        self.assertEqual(len(sent_messages), 1)
        self.assertIn("different Telegram chat_id", sent_messages[0][1])

    def test_submit_request_sends_manager_telegram_notification(self):
        self.HrBot.create(
            {
                "employee_id": self.manager_employee.id,
                "chat_id": "556677",
            }
        )
        sent_messages = []

        def _capture_send(service_self, chat_id, message):
            sent_messages.append((chat_id, message))
            return True

        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request = self.env["ab_request"].with_user(self.requester_user).create(
                {
                    "subject": "Counter complaint",
                    "description": "Customer reported unacceptable delay.",
                    "request_type_id": self.request_type.id,
                }
            )
            with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", _capture_send):
                request.with_user(self.requester_user).action_submit_request()

        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(sent_messages[0][0], "556677")
        self.assertIn("New Complaint", sent_messages[0][1])
        self.assertIn("Counter complaint", sent_messages[0][1])

    def test_submit_request_auto_registers_manager_from_telegram_updates(self):
        sent_messages = []
        updates = [
            {
                "update_id": 1,
                "message": {
                    "chat": {"id": 991122, "type": "private"},
                    "from": {"id": 91, "is_bot": False, "username": "other_user"},
                    "text": "unrelated",
                },
            },
            {
                "update_id": 2,
                "message": {
                    "chat": {"id": 445566, "type": "private"},
                    "from": {"id": 92, "is_bot": False, "username": self.manager_user.login},
                    "text": "hello bot",
                },
            },
        ]

        def _capture_send(service_self, chat_id, message):
            sent_messages.append((chat_id, message))
            return True

        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request = self.env["ab_request"].with_user(self.requester_user).create(
                {
                    "subject": "Auto register complaint",
                    "description": "Manager should be linked automatically.",
                    "request_type_id": self.request_type.id,
                }
            )
            with patch.object(type(self.env["ab.telegram.service"]), "get_updates", return_value=updates):
                with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", _capture_send):
                    request.with_user(self.requester_user).action_submit_request()

        bot_link = self.HrBot.search([("employee_id", "=", self.manager_employee.id)], limit=1)
        self.assertTrue(bot_link)
        self.assertEqual(bot_link.chat_id, "445566")
        self.assertEqual(bot_link.telegram_username, self.manager_user.login)
        self.assertEqual(len(sent_messages), 1)
        self.assertEqual(sent_messages[0][0], "445566")

    def test_submit_request_does_not_send_when_manager_never_contacted_bot(self):
        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request = self.env["ab_request"].with_user(self.requester_user).create(
                {
                    "subject": "No manager mapping",
                    "description": "No Telegram contact yet.",
                    "request_type_id": self.request_type.id,
                }
            )
            with patch.object(type(self.env["ab.telegram.service"]), "get_updates", return_value=[]):
                with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", return_value=True) as send_mock:
                    request.with_user(self.requester_user).action_submit_request()

        self.assertFalse(self.HrBot.search([("employee_id", "=", self.manager_employee.id)], limit=1))
        self.assertFalse(send_mock.called)

    def test_submit_request_uses_latest_matching_update_when_multiple_exist(self):
        sent_messages = []
        updates = [
            {
                "update_id": 10,
                "message": {
                    "chat": {"id": 10001, "type": "private"},
                    "from": {"id": 100, "is_bot": False, "username": "first_match"},
                    "text": str(self.manager_employee.id),
                },
            },
            {
                "update_id": 11,
                "message": {
                    "chat": {"id": 10002, "type": "private"},
                    "from": {"id": 101, "is_bot": False, "username": "latest_match"},
                    "text": str(self.manager_employee.id),
                },
            },
        ]

        def _capture_send(service_self, chat_id, message):
            sent_messages.append((chat_id, message))
            return True

        with patch("odoo.addons.mail.models.mail_thread.MailThread.message_post", autospec=True):
            request = self.env["ab_request"].with_user(self.requester_user).create(
                {
                    "subject": "Latest update complaint",
                    "description": "Latest matching update should win.",
                    "request_type_id": self.request_type.id,
                }
            )
            with patch.object(type(self.env["ab.telegram.service"]), "get_updates", return_value=updates):
                with patch.object(type(self.env["ab.telegram.service"]), "send_telegram_message", _capture_send):
                    request.with_user(self.requester_user).action_submit_request()

        bot_link = self.HrBot.search([("employee_id", "=", self.manager_employee.id)], limit=1)
        self.assertEqual(bot_link.chat_id, "10002")
        self.assertEqual(bot_link.telegram_username, "latest_match")
        self.assertEqual(sent_messages[0][0], "10002")
