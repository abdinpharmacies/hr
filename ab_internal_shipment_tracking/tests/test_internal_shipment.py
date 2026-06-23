from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase


class TestInternalShipment(TransactionCase):
    def setUp(self):
        super().setUp()
        Users = self.env["res.users"].sudo().with_context(active_test=False)
        group_user = self.env.ref("base.group_user")
        admin_user = self.env.ref("base.user_admin")
        group_shipment_user = self.env.ref("ab_internal_shipment_tracking.group_ab_internal_shipment_user")

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
        users.write({"group_ids": [(4, group_shipment_user.id)]})

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
        self.unrelated_employee = Employee.create(
            {
                "name": "Unrelated Employee",
                "user_id": self.unrelated_user.id,
            }
        )
        Store = self.env["ab_store"].sudo()
        self.recipient_store = Store.create(
            {
                "name": "Recipient Branch",
                "code": "SHIP-REC",
                "store_type": "branch",
            }
        )
        self.other_store = Store.create(
            {
                "name": "Other Branch",
                "code": "SHIP-OTHER",
                "store_type": "branch",
            }
        )
        Department = self.env["ab_hr_department"].sudo()
        self.recipient_department = Department.create(
            {
                "name": "Recipient Department",
                "manager_id": self.recipient_employee.id,
                "store_id": self.recipient_store.id,
            }
        )
        self.other_department = Department.create(
            {
                "name": "Other Department",
                "manager_id": self.unrelated_employee.id,
                "store_id": self.other_store.id,
            }
        )
        self.recipient_employee.department_id = self.recipient_department
        self.unrelated_employee.department_id = self.other_department

    def _create_shipment(self, extra_vals=None):
        Shipment = self.env["ab_internal_shipment"].with_user(self.sender_user)
        vals = {
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
        if extra_vals:
            vals.update(extra_vals)
        return Shipment.create(vals)

    def _deliver_shipment(self, shipment):
        shipment.action_send()
        shipment.action_deliver()
        self.assertEqual(shipment.state, "awaiting_receipt")

    def _assert_only_recipient_sees_awaiting_receipt(self, shipment, recipient_user=None):
        recipient_user = recipient_user or self.recipient_user
        recipient_count = self.env["ab_internal_shipment"].with_user(recipient_user).search_count(
            [("is_receipt_confirmation_user", "=", True), ("id", "=", shipment.id)]
        )
        self.assertEqual(recipient_count, 1)

        unrelated_count = self.env["ab_internal_shipment"].with_user(self.unrelated_user).search_count(
            [("is_receipt_confirmation_user", "=", True), ("id", "=", shipment.id)]
        )
        self.assertEqual(unrelated_count, 0)

    def test_receipt_requires_delivered_state_and_tracks_history(self):
        shipment = self._create_shipment()

        with self.assertRaises(UserError):
            shipment.with_user(self.recipient_user).action_receive()

        shipment.action_send()
        with self.assertRaises(UserError):
            shipment.with_user(self.recipient_user).action_receive()

        shipment.action_deliver()
        self.assertEqual(shipment.state, "awaiting_receipt")
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

    def test_recipient_can_read_but_not_write_awaiting_receipt_shipment(self):
        shipment = self._create_shipment()
        shipment.action_send()
        shipment.action_deliver()

        recipient_shipment = shipment.with_user(self.recipient_user)
        self.assertEqual(recipient_shipment.read(["name"])[0]["name"], shipment.name)

        with self.assertRaises(AccessError):
            recipient_shipment.write({"notes": "Not allowed from awaiting receipt tab"})

    def test_employee_recipient_sees_awaiting_receipt_and_can_confirm(self):
        shipment = self._create_shipment()
        self._deliver_shipment(shipment)

        self._assert_only_recipient_sees_awaiting_receipt(shipment)
        self.assertTrue(shipment.with_user(self.recipient_user).is_receipt_confirmation_user)
        self.assertFalse(shipment.with_user(self.unrelated_user).is_receipt_confirmation_user)

        shipment.with_user(self.recipient_user).action_receive()
        self.assertEqual(shipment.state, "received")

    def test_department_recipient_routes_to_department_manager(self):
        shipment = self._create_shipment(
            {
                "recipient_type": "department",
                "recipient_employee_id": False,
                "recipient_department_id": self.recipient_department.id,
            }
        )
        self._deliver_shipment(shipment)

        self._assert_only_recipient_sees_awaiting_receipt(shipment)
        self.assertTrue(shipment.with_user(self.recipient_user).is_receipt_confirmation_user)
        self.assertFalse(shipment.with_user(self.unrelated_user).is_receipt_confirmation_user)

        shipment.with_user(self.recipient_user).action_receive()
        self.assertEqual(shipment.state, "received")

    def test_branch_recipient_routes_to_branch_employees(self):
        shipment = self._create_shipment(
            {
                "recipient_type": "branch",
                "recipient_employee_id": False,
                "recipient_store_id": self.recipient_store.id,
            }
        )
        self._deliver_shipment(shipment)

        self._assert_only_recipient_sees_awaiting_receipt(shipment)
        self.assertTrue(shipment.with_user(self.recipient_user).is_receipt_confirmation_user)
        self.assertFalse(shipment.with_user(self.unrelated_user).is_receipt_confirmation_user)

        shipment.with_user(self.recipient_user).action_receive()
        self.assertEqual(shipment.state, "received")
