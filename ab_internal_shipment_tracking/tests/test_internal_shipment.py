from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestInternalShipment(TransactionCase):
    def setUp(self):
        super().setUp()
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        group_user = self.env.ref("base.group_user")
        admin_user = self.env.ref("base.user_admin")
        group_sender = self.env.ref("ab_internal_shipment_tracking.group_ab_internal_shipment_sender")

        users = Users.search(
            [
                ("group_ids", "in", group_user.id),
                ("id", "!=", admin_user.id),
                ("share", "=", False),
            ],
            limit=3,
        )
        self.assertGreaterEqual(
            len(users),
            3,
            "Expected at least three non-admin internal users in the test database.",
        )
        users.write({"group_ids": [(4, group_sender.id)]})

        self.sender_user = users[0]
        self.recipient_user = users[1]
        self.unrelated_user = users[2]

        self.sender_user.write(
            {
                "name": "Shipment Sender Test",
            }
        )
        self.recipient_user.write(
            {
                "name": "Shipment Recipient Test",
            }
        )
        self.unrelated_user.write(
            {
                "name": "Shipment Unrelated Test",
            }
        )

        Employee = self.env["ab_hr_employee"].sudo()
        self.sender_employee = Employee.create(
            {
                "name": "Sender Employee",
                "user_id": self.sender_user.id,
            }
        )
        self.recipient_employee = Employee.create(
            {
                "name": "Recipient Employee",
                "user_id": self.recipient_user.id,
            }
        )

    def _create_shipment(self):
        Shipment = self.env["ab_internal_shipment"].with_user(self.sender_user)
        return Shipment.create(
            {
                "subject": "Employee Contract Files",
                "sender_type": "employee",
                "sender_employee_id": self.sender_employee.id,
                "recipient_type": "employee",
                "recipient_employee_id": self.recipient_employee.id,
                "shipment_type": "documents",
                "delivery_method": "hand_delivery",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "item_name": "Signed Contract",
                            "quantity": 1,
                        },
                    )
                ],
            }
        )

    def test_receipt_requires_delivered_state_and_tracks_history(self):
        shipment = self._create_shipment()

        with self.assertRaises(UserError):
            shipment.with_user(self.recipient_user).action_receive()

        shipment.action_send()
        with self.assertRaises(UserError):
            shipment.with_user(self.recipient_user).action_receive()

        shipment.action_deliver()
        self.assertEqual(shipment.state, "delivered")
        self.assertEqual(shipment.current_holder_employee_id, self.recipient_employee)

        shipment.with_user(self.recipient_user).action_receive()
        self.assertEqual(shipment.state, "received")
        self.assertEqual(shipment.received_by_id, self.recipient_user)
        self.assertIn("received", shipment.history_ids.mapped("action"))

    def test_unrelated_user_cannot_read_shipment(self):
        shipment = self._create_shipment()

        relevant_count = self.env["ab_internal_shipment"].with_user(self.sender_user).search_count(
            [("id", "=", shipment.id)]
        )
        self.assertEqual(relevant_count, 1)

        unrelated_count = self.env["ab_internal_shipment"].with_user(self.unrelated_user).search_count(
            [("id", "=", shipment.id)]
        )
        self.assertEqual(unrelated_count, 0)

        with self.assertRaises(AccessError):
            shipment.with_user(self.unrelated_user).read(["name"])
