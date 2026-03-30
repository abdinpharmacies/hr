from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import AccessError, UserError
from unittest.mock import patch


@tagged("post_install", "-at_install")
class TestAbWhatsAppApi(TransactionCase):
    def test_status_progression_is_monotonic(self):
        service = self.env["ab.whatsapp.service"].sudo()
        wa_id = "201555000111"
        meta_message_id = "wamid.TEST_STATUS_MONOTONIC_1"

        message = service._create_message(
            direction="outgoing",
            wa_id=wa_id,
            phone_number_id="965292690006920",
            message_type="text",
            text_content="status monotonic",
            status="sent",
            meta_message_id=meta_message_id,
            raw_payload={"test": True},
        )
        self.assertEqual(message.status, "sent")

        service._update_outgoing_message_status(
            meta_message_id=meta_message_id,
            status="read",
            recipient_wa_id=wa_id,
            phone_number_id="965292690006920",
        )
        service._update_outgoing_message_status(
            meta_message_id=meta_message_id,
            status="delivered",
            recipient_wa_id=wa_id,
            phone_number_id="965292690006920",
        )

        message.invalidate_recordset(["status"])
        self.assertEqual(message.status, "read")

    def test_internal_user_cannot_upsert_contact(self):
        company = self.env.company
        user = self.env["res.users"].with_context(no_reset_password=True).create(
            {
                "name": "AB WhatsApp Internal",
                "login": "ab_whatsapp_internal_user",
                "email": "ab_whatsapp_internal_user@example.com",
                "company_id": company.id,
                "company_ids": [(6, 0, [company.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

        service = self.env["ab.whatsapp.service"].with_user(user)
        with self.assertRaises(AccessError):
            service.api_upsert_contact(wa_id="201555000222", name="Contact A")

    def test_webhook_stores_reply_and_reaction_metadata(self):
        service = self.env["ab.whatsapp.service"].sudo()
        wa_id = "201555000333"
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "965292690006920"},
                                "contacts": [
                                    {
                                        "wa_id": wa_id,
                                        "profile": {"name": "Contact B"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": wa_id,
                                        "id": "wamid.REPLY_TARGET_1",
                                        "type": "text",
                                        "text": {"body": "first"},
                                    },
                                    {
                                        "from": wa_id,
                                        "id": "wamid.REPLY_CHILD_1",
                                        "type": "text",
                                        "context": {"id": "wamid.REPLY_TARGET_1"},
                                        "text": {"body": "replying"},
                                    },
                                    {
                                        "from": wa_id,
                                        "id": "wamid.REACTION_1",
                                        "type": "reaction",
                                        "reaction": {"message_id": "wamid.REPLY_TARGET_1", "emoji": "👍"},
                                    },
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        result = service.process_webhook_payload(payload)
        self.assertEqual(len(result["created"]), 3)

        Message = self.env["ab.whatsapp.message"].sudo()
        reply_message = Message.search([("meta_message_id", "=", "wamid.REPLY_CHILD_1")], limit=1)
        reaction_message = Message.search([("meta_message_id", "=", "wamid.REACTION_1")], limit=1)

        self.assertEqual(reply_message.reply_to_meta_message_id, "wamid.REPLY_TARGET_1")
        self.assertEqual(reaction_message.message_type, "reaction")
        self.assertEqual(reaction_message.reaction_target_meta_message_id, "wamid.REPLY_TARGET_1")
        self.assertEqual(reaction_message.text_content, "👍")

    def test_mark_incoming_messages_as_read(self):
        service = self.env["ab.whatsapp.service"].sudo()
        wa_id = "201555000334"
        message = service._create_message(
            direction="incoming",
            wa_id=wa_id,
            phone_number_id="965292690006920",
            message_type="text",
            text_content="unread message",
            status="received",
            meta_message_id="wamid.READ_RECEIPT_1",
            raw_payload={"test": True},
        )

        mocked_settings = {
            "token": "test-token",
            "default_phone_number_id": "965292690006920",
            "verify_token": "verify",
            "waba_id": "",
            "api_version": "v22.0",
        }
        with patch.object(type(service), "_settings", return_value=mocked_settings), patch.object(
            type(service), "_post_graph_json", return_value={"success": True}
        ) as mock_post:
            result = service.api_mark_incoming_read(wa_id=wa_id)

        self.assertTrue(result["ok"])
        self.assertEqual(result["attempted"], 1)
        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(mock_post.call_count, 1)

        message.invalidate_recordset(["status"])
        self.assertEqual(message.status, "read")

    def test_webhook_stores_location_message(self):
        service = self.env["ab.whatsapp.service"].sudo()
        wa_id = "201555000335"
        payload = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "965292690006920"},
                                "contacts": [
                                    {
                                        "wa_id": wa_id,
                                        "profile": {"name": "Contact Location"},
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": wa_id,
                                        "id": "wamid.LOCATION_1",
                                        "type": "location",
                                        "location": {
                                            "latitude": 30.0444,
                                            "longitude": 31.2357,
                                            "name": "Downtown",
                                            "address": "Cairo",
                                        },
                                    }
                                ],
                            }
                        }
                    ]
                }
            ]
        }

        result = service.process_webhook_payload(payload)
        self.assertEqual(len(result["created"]), 1)

        message = self.env["ab.whatsapp.message"].sudo().search(
            [("meta_message_id", "=", "wamid.LOCATION_1")],
            limit=1,
        )
        self.assertEqual(message.message_type, "location")
        self.assertIn("https://maps.google.com/?q=30.0444,31.2357", message.text_content or "")

    def test_edit_and_delete_message_locally(self):
        service = self.env["ab.whatsapp.service"].sudo()
        message = service._create_message(
            direction="outgoing",
            wa_id="201555000444",
            phone_number_id="965292690006920",
            message_type="text",
            text_content="Initial text",
            status="sent",
            meta_message_id="wamid.EDIT_DELETE_1",
            raw_payload={"test": True},
        )

        edited = service.api_edit_message_local(message.id, "Updated text")
        self.assertEqual(edited["text_content"], "Updated text")
        self.assertEqual(edited["edited_from_text"], "Initial text")

        deleted = service.api_delete_message_local(message.id)
        self.assertTrue(deleted["is_deleted"])
        self.assertEqual(deleted["message_type"], "deleted")

    def test_delete_contact_cascades_messages(self):
        service = self.env["ab.whatsapp.service"].sudo()
        wa_id = "201555000555"
        message = service._create_message(
            direction="incoming",
            wa_id=wa_id,
            phone_number_id="965292690006920",
            message_type="text",
            text_content="hello",
            status="received",
            meta_message_id="wamid.CONTACT_DELETE_1",
            raw_payload={"test": True},
        )
        self.assertTrue(message.contact_id.exists())

        result = service.api_delete_contact(wa_id=wa_id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["wa_id"], wa_id)

        contact = self.env["ab.whatsapp.contact"].sudo().search([("wa_id", "=", wa_id)], limit=1)
        self.assertFalse(contact)

        message.invalidate_recordset(["contact_id"])
        self.assertFalse(message.exists())

    def test_sync_templates_stores_templates(self):
        service = self.env["ab.whatsapp.service"].sudo()
        mocked_settings = {
            "token": "test-token",
            "default_phone_number_id": "965292690006920",
            "verify_token": "verify",
            "waba_id": "1234567890",
            "api_version": "v22.0",
        }
        mocked_response = {
            "data": [
                {
                    "id": "123",
                    "name": "order_ready",
                    "language": "en_US",
                    "status": "APPROVED",
                    "category": "UTILITY",
                    "quality_score": "GREEN",
                    "components": [
                        {"type": "BODY", "text": "Your order is ready."},
                    ],
                },
                {
                    "id": "124",
                    "name": "order_eta",
                    "language": "en_US",
                    "status": "APPROVED",
                    "category": "UTILITY",
                    "quality_score": "GREEN",
                    "components": [
                        {"type": "BODY", "text": "Your order {{1}} is on the way."},
                    ],
                },
            ],
            "paging": {},
        }

        with patch.object(type(service), "_settings", return_value=mocked_settings), patch.object(
            type(service), "_require_token", return_value="test-token"
        ), patch.object(type(service), "_get_graph_json", return_value=mocked_response):
            result = service.api_sync_templates(page_limit=100)

        self.assertTrue(result["ok"])
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["fetched"], 2)

        plain_template = self.env["ab.whatsapp.template"].sudo().search([("template_uid", "=", "123")], limit=1)
        placeholder_template = self.env["ab.whatsapp.template"].sudo().search(
            [("template_uid", "=", "124")],
            limit=1,
        )
        self.assertTrue(plain_template.exists())
        self.assertEqual(plain_template.body_preview, "Your order is ready.")
        self.assertFalse(plain_template.has_placeholders)
        self.assertTrue(placeholder_template.has_placeholders)

    def test_send_template_creates_outgoing_message(self):
        service = self.env["ab.whatsapp.service"].sudo()
        template = self.env["ab.whatsapp.template"].sudo().create(
            {
                "name": "order_ready",
                "template_uid": "901",
                "language": "en_US",
                "status": "APPROVED",
                "category": "UTILITY",
                "has_placeholders": False,
            }
        )
        mocked_settings = {
            "token": "test-token",
            "default_phone_number_id": "965292690006920",
            "verify_token": "verify",
            "waba_id": "1234567890",
            "api_version": "v22.0",
        }
        mocked_send_response = {"messages": [{"id": "wamid.TEMPLATE_SEND_1"}]}

        with patch.object(type(service), "_settings", return_value=mocked_settings), patch.object(
            type(service), "_require_token", return_value="test-token"
        ), patch.object(
            type(service),
            "_resolve_sender_phone_number_id",
            return_value="965292690006920",
        ), patch.object(type(service), "_post_graph_json", return_value=mocked_send_response) as mock_post:
            result = service.api_send_template(
                to="201555000777",
                template_id=template.id,
                contact_name="Template Contact",
            )

        self.assertTrue(result["ok"])
        payload = mock_post.call_args[0][1]
        self.assertEqual(payload["type"], "template")
        self.assertEqual(payload["template"]["name"], "order_ready")
        self.assertEqual(payload["template"]["language"]["code"], "en_US")

        message = self.env["ab.whatsapp.message"].sudo().search(
            [("meta_message_id", "=", "wamid.TEMPLATE_SEND_1")],
            limit=1,
        )
        self.assertTrue(message.exists())
        self.assertEqual(message.message_type, "template")
        self.assertIn("order_ready", message.text_content or "")

    def test_submit_template_creates_template_on_meta_and_local(self):
        service = self.env["ab.whatsapp.service"].sudo()
        mocked_settings = {
            "token": "test-token",
            "default_phone_number_id": "965292690006920",
            "verify_token": "verify",
            "waba_id": "1234567890",
            "api_version": "v22.0",
        }
        mocked_response = {
            "id": "321",
            "status": "PENDING",
            "category": "UTILITY",
        }

        with patch.object(type(service), "_settings", return_value=mocked_settings), patch.object(
            type(service), "_require_token", return_value="test-token"
        ), patch.object(type(service), "_post_graph_json", return_value=mocked_response) as mock_post:
            result = service.api_submit_template(
                name="Order Ready Update",
                body="Your order is ready for pickup.",
                language="en_US",
                category="UTILITY",
            )

        self.assertTrue(result["ok"])
        self.assertEqual(result["template_uid"], "321")
        self.assertEqual(result["status"], "PENDING")
        payload = mock_post.call_args[0][1]
        self.assertEqual(payload["name"], "order_ready_update")
        self.assertEqual(payload["language"], "en_US")
        self.assertEqual(payload["category"], "UTILITY")
        self.assertEqual(payload["components"][0]["text"], "Your order is ready for pickup.")

        template = self.env["ab.whatsapp.template"].sudo().search([("template_uid", "=", "321")], limit=1)
        self.assertTrue(template.exists())
        self.assertEqual(template.name, "order_ready_update")
        self.assertEqual(template.status, "PENDING")

    def test_submit_template_with_placeholders_adds_example_payload(self):
        service = self.env["ab.whatsapp.service"].sudo()
        mocked_settings = {
            "token": "test-token",
            "default_phone_number_id": "965292690006920",
            "verify_token": "verify",
            "waba_id": "1234567890",
            "api_version": "v22.0",
        }
        mocked_response = {
            "id": "654",
            "status": "PENDING",
            "category": "UTILITY",
        }

        with patch.object(type(service), "_settings", return_value=mocked_settings), patch.object(
            type(service), "_require_token", return_value="test-token"
        ), patch.object(type(service), "_post_graph_json", return_value=mocked_response) as mock_post:
            result = service.api_submit_template(
                name="Order Delivery ETA",
                body="Order {{1}} will arrive at {{2}}.",
                language="en_US",
                category="UTILITY",
            )

        self.assertTrue(result["ok"])
        payload = mock_post.call_args[0][1]
        body_component = payload["components"][0]
        self.assertEqual(body_component["text"], "Order {{1}} will arrive at {{2}}.")
        self.assertEqual(body_component["example"]["body_text"], [["sample_1", "sample_2"]])

        template = self.env["ab.whatsapp.template"].sudo().search([("template_uid", "=", "654")], limit=1)
        self.assertTrue(template.exists())
        self.assertTrue(template.has_placeholders)

    def test_send_template_with_placeholders_uses_template_params(self):
        service = self.env["ab.whatsapp.service"].sudo()
        template = self.env["ab.whatsapp.template"].sudo().create(
            {
                "name": "order_delivery_eta",
                "template_uid": "777",
                "language": "en_US",
                "status": "APPROVED",
                "category": "UTILITY",
                "body_preview": "Order {{1}} will arrive at {{2}}.",
                "has_placeholders": True,
                "components_payload": [
                    {"type": "BODY", "text": "Order {{1}} will arrive at {{2}}."},
                ],
            }
        )
        mocked_settings = {
            "token": "test-token",
            "default_phone_number_id": "965292690006920",
            "verify_token": "verify",
            "waba_id": "1234567890",
            "api_version": "v22.0",
        }
        mocked_send_response = {"messages": [{"id": "wamid.TEMPLATE_SEND_2"}]}

        with patch.object(type(service), "_settings", return_value=mocked_settings), patch.object(
            type(service), "_require_token", return_value="test-token"
        ), patch.object(
            type(service),
            "_resolve_sender_phone_number_id",
            return_value="965292690006920",
        ), patch.object(type(service), "_post_graph_json", return_value=mocked_send_response) as mock_post:
            result = service.api_send_template(
                to="201555000888",
                template_id=template.id,
                template_params=["A100", "10:30 AM"],
            )

        self.assertTrue(result["ok"])
        payload = mock_post.call_args[0][1]
        self.assertEqual(payload["template"]["name"], "order_delivery_eta")
        self.assertEqual(
            payload["template"]["components"][0]["parameters"],
            [
                {"type": "text", "text": "A100"},
                {"type": "text", "text": "10:30 AM"},
            ],
        )

        with self.assertRaises(UserError):
            service.api_send_template(
                to="201555000888",
                template_id=template.id,
                template_params=["A100"],
            )
