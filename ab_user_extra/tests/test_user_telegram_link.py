import json
from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo import fields
from odoo.tests.common import TransactionCase


class TestUserTelegramLink(TransactionCase):
    def setUp(self):
        super().setUp()
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        group_user = self.env.ref("base.group_user")
        admin_user = self.env.ref("base.user_admin")

        self.normal_user = Users.search(
            [
                ("group_ids", "in", group_user.id),
                ("id", "!=", admin_user.id),
            ],
            limit=1,
        )
        self.assertTrue(self.normal_user, "Expected at least one non-admin internal user in test database.")
        self.link_user = self.normal_user

    def test_link_flow_generates_pin(self):
        Link = self.env["ab_user_telegram_link"].sudo()
        telegram_user_id = "900001"
        telegram_chat_id = "900001"

        api_key = self.env["res.users.apikeys"].with_user(self.link_user)._generate(
            "rpc",
            "telegram-test-link-flow",
            fields.Datetime.now() + timedelta(days=1),
        )
        Link.bot_process_message(telegram_user_id, telegram_chat_id, "Link Odoo Account")
        Link.bot_process_message(telegram_user_id, telegram_chat_id, self.link_user.login)
        result = Link.bot_process_message(telegram_user_id, telegram_chat_id, api_key)

        self.assertEqual(result["note"], "linked_success")
        link = Link.search([("telegram_user_id", "=", telegram_user_id)], limit=1)
        self.assertEqual(link.user_id, self.link_user)
        self.assertEqual(link.status, "linked")
        self.assertTrue(link.pin.isdigit())
        self.assertEqual(len(link.pin), 4)

    def test_non_system_user_has_no_access(self):
        with self.assertRaises(AccessError):
            self.env["ab_user_telegram_link"].with_user(self.normal_user).search([])

    def test_linked_user_can_query_data_with_ai_flow(self):
        LinkModel = self.env["ab_user_telegram_link"].sudo()
        admin_user = self.env.ref("base.user_admin")
        link = LinkModel.create(
            {
                "telegram_user_id": "900010",
                "telegram_chat_id": "900010",
                "status": "linked",
                "user_id": admin_user.id,
                "login_email": admin_user.login,
                "linked_at": fields.Datetime.now(),
            }
        )

        plan_json = json.dumps(
            {
                "action": "query",
                "model": "ab_user_telegram_link",
                "domain": [["telegram_user_id", "=", "900010"]],
                "fields": ["telegram_user_id", "status", "pin"],
                "limit": 1,
            }
        )

        with (
            patch.object(
                type(LinkModel),
                "_get_openai_settings",
                return_value={
                    "api_key": "test-key",
                    "base_url": "https://api.openai.com/v1",
                    "models": ["gpt-5.2"],
                },
            ),
            patch.object(
                type(LinkModel),
                "_call_openai_with_fallback",
                side_effect=[
                    (plan_json, "gpt-5.2"),
                    ("Here is your link status from Odoo records.", "gpt-5.2"),
                ],
            ),
        ):
            result = link.bot_process_message("900010", "900010", "show my link in ab_user_telegram_link")

        self.assertEqual(result["note"], "ai_answer_sent")
        self.assertIn("Odoo records", result["text"])

    def test_ai_session_menu_status_and_new_session(self):
        LinkModel = self.env["ab_user_telegram_link"].sudo()
        ChatModel = self.env["ab_telegram_chat_message"].sudo()
        admin_user = self.env.ref("base.user_admin")
        link = LinkModel.create(
            {
                "telegram_user_id": "900020",
                "telegram_chat_id": "900020",
                "status": "linked",
                "user_id": admin_user.id,
                "login_email": admin_user.login,
                "linked_at": fields.Datetime.now(),
                "ai_context_token_limit": 1000,
            }
        )
        current_session = link._open_ai_session()
        current_session.write({"token_count": 300, "token_limit": 1000})

        menu_result = LinkModel.bot_process_message("900020", "900020", "AI Session")
        self.assertEqual(menu_result["note"], "ai_session_menu_sent")
        self.assertEqual(menu_result["keyboard_rows"], [["Status", "New Session"], ["Back"]])

        status_result = LinkModel.bot_process_message("900020", "900020", "Status")
        self.assertEqual(status_result["note"], "ai_status_sent")
        self.assertIn("300/1000", status_result["text"])
        self.assertIn("Remain: 700", status_result["text"])

        new_session_result = LinkModel.bot_process_message("900020", "900020", "New Session")
        self.assertEqual(new_session_result["note"], "ai_new_session_opened")

        current_session.invalidate_recordset()
        self.assertEqual(current_session.session_status, "closed")
        self.assertEqual(current_session.close_reason, "manual_new_session")

        opened_sessions = ChatModel.search(
            [
                ("telegram_user_id", "=", "900020"),
                ("linked_user_id", "=", admin_user.id),
                ("session_status", "=", "open"),
            ],
            order="id desc",
            limit=1,
        )
        self.assertTrue(opened_sessions)

    def test_user_settings_menu_link_and_unlink_with_api_key(self):
        Link = self.env["ab_user_telegram_link"].sudo()
        telegram_user_id = "900030"
        telegram_chat_id = "900030"

        menu_payload = Link.bot_process_message(telegram_user_id, telegram_chat_id, "menu")
        self.assertIn(["Get My ID", "User Settings"], menu_payload["keyboard_rows"])
        self.assertNotIn(["Get My ID", "My PIN"], menu_payload["keyboard_rows"])

        settings_payload = Link.bot_process_message(telegram_user_id, telegram_chat_id, "User Settings")
        self.assertEqual(settings_payload["note"], "user_settings_menu_sent")
        self.assertEqual(
            settings_payload["keyboard_rows"],
            [["Link Odoo Account", "Unlink Odoo Account"], ["My PIN", "Back"]],
        )

        expiration = fields.Datetime.now() + timedelta(days=1)
        api_key = self.env["res.users.apikeys"].with_user(self.link_user)._generate(
            "rpc",
            "telegram-link-test-key",
            expiration,
        )

        Link.bot_process_message(telegram_user_id, telegram_chat_id, "Link Odoo Account")
        Link.bot_process_message(telegram_user_id, telegram_chat_id, self.link_user.login)
        link_result = Link.bot_process_message(telegram_user_id, telegram_chat_id, api_key)
        self.assertEqual(link_result["note"], "linked_success")

        link = Link.search([("telegram_user_id", "=", telegram_user_id)], limit=1)
        self.assertEqual(link.user_id, self.link_user)
        self.assertEqual(link.status, "linked")

        session = link._open_ai_session()
        self.assertEqual(session.session_status, "open")

        Link.bot_process_message(telegram_user_id, telegram_chat_id, "Unlink Odoo Account")
        Link.bot_process_message(telegram_user_id, telegram_chat_id, self.link_user.login)
        unlink_result = Link.bot_process_message(telegram_user_id, telegram_chat_id, api_key)
        self.assertEqual(unlink_result["note"], "unlink_success")

        link.invalidate_recordset()
        self.assertEqual(link.status, "new")
        self.assertFalse(link.user_id)

        session.invalidate_recordset()
        self.assertEqual(session.session_status, "closed")
        self.assertEqual(session.close_reason, "manual_unlink")

    def test_user_one_to_one_link_enforced(self):
        Link = self.env["ab_user_telegram_link"].sudo()
        tg1 = ("900040", "900040")
        tg2 = ("900041", "900041")
        api_key = self.env["res.users.apikeys"].with_user(self.link_user)._generate(
            "rpc",
            "telegram-test-one2one",
            fields.Datetime.now() + timedelta(days=1),
        )

        Link.bot_process_message(*tg1, "Link Odoo Account")
        Link.bot_process_message(*tg1, self.link_user.login)
        first_result = Link.bot_process_message(*tg1, api_key)
        self.assertEqual(first_result["note"], "linked_success")

        Link.bot_process_message(*tg2, "Link Odoo Account")
        Link.bot_process_message(*tg2, self.link_user.login)
        second_result = Link.bot_process_message(*tg2, api_key)
        self.assertEqual(second_result["note"], "user_already_linked")

    def test_manual_link_by_admin_sets_linked_state(self):
        LinkModel = self.env["ab_user_telegram_link"].sudo()
        rec = LinkModel.create(
            {
                "telegram_user_id": "900050",
                "telegram_chat_id": "900050",
                "user_id": self.link_user.id,
                "status": "new",
            }
        )
        self.assertEqual(rec.status, "linked")
        self.assertEqual(rec.user_id, self.link_user)
        self.assertEqual(rec.login_email, self.link_user.login)
        self.assertTrue(rec.linked_at)
        self.assertTrue(rec.pin)

    def test_password_change_sync_does_not_break_link(self):
        LinkModel = self.env["ab_user_telegram_link"].sudo()
        rec = LinkModel.create(
            {
                "telegram_user_id": "900060",
                "telegram_chat_id": "900060",
                "user_id": self.link_user.id,
                "status": "linked",
            }
        )

        rec._sync_password_state()
        rec.invalidate_recordset()
        self.assertEqual(rec.status, "linked")
        self.assertEqual(rec.user_id, self.link_user)
