from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestPharmacyDeliveryManagement(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Users = self.env["res.users"].sudo().with_context(no_reset_password=True)
        self.group_user = self.env.ref("base.group_user")
        self.group_manager = self.env.ref("ab_orders_management.group_ab_pharmacy_delivery_manager")
        self.group_basic = self.env.ref("ab_orders_management.group_ab_pharmacy_delivery_user")

        self.manager_user = self.Users.create(
            {
                "name": "Pharmacy Manager",
                "login": "pharmacy.manager.test",
                "email": "pharmacy.manager.test@example.com",
                "group_ids": [(6, 0, [self.group_user.id, self.group_manager.id])],
            }
        )
        self.basic_user = self.Users.create(
            {
                "name": "Delivery User",
                "login": "pharmacy.user.test",
                "email": "pharmacy.user.test@example.com",
                "group_ids": [(6, 0, [self.group_user.id, self.group_basic.id])],
            }
        )

        self.branch_allowed = self.env["ab_pharmacy_delivery_branch"].sudo().create(
            {
                "name": "الاقصر - المتاحة",
                "user_ids": [(6, 0, [self.basic_user.id])],
            }
        )
        self.branch_hidden = self.env["ab_pharmacy_delivery_branch"].sudo().create(
            {
                "name": "الاقصر - المخفية",
            }
        )
        self.pilot_allowed = self.env["ab_pharmacy_delivery_pilot"].sudo().create(
            {
                "name": "مندوب اختبار 1",
                "branch_id": self.branch_allowed.id,
            }
        )
        self.pilot_hidden = self.env["ab_pharmacy_delivery_pilot"].sudo().create(
            {
                "name": "مندوب اختبار 2",
                "branch_id": self.branch_hidden.id,
            }
        )

    def test_status_change_creates_assignment_and_updates_counters(self):
        delivery_wizard = self.env["ab_pharmacy_delivery_assignment_wizard"].sudo().create(
            {
                "pilot_id": self.pilot_allowed.id,
                "target_status": "in_delivery",
                "order_number": "ORD-1001",
                "transaction_type": "order",
                "branch_id": self.branch_allowed.id,
                "note": "Initial assignment",
            }
        )
        delivery_wizard.action_apply()

        self.pilot_allowed.invalidate_recordset()
        self.assertEqual(self.pilot_allowed.status, "in_delivery")
        self.assertEqual(self.pilot_allowed.order_assigned_count, 1)
        self.assertEqual(self.pilot_allowed.delivery_assigned_count, 0)
        self.assertEqual(self.pilot_allowed.order_completed_count, 0)
        self.assertEqual(self.pilot_allowed.handled_item_count, 0)

        assignment = self.env["ab_pharmacy_delivery_assignment"].sudo().search(
            [("pilot_id", "=", self.pilot_allowed.id), ("status", "=", "assigned")],
            limit=1,
        )
        self.assertTrue(assignment)

        close_wizard = self.env["ab_pharmacy_delivery_assignment_wizard"].sudo().create(
            {
                "pilot_id": self.pilot_allowed.id,
                "target_status": "free",
                "note": "Completed successfully",
            }
        )
        close_wizard.action_apply()

        self.pilot_allowed.invalidate_recordset()
        self.assertEqual(self.pilot_allowed.status, "free")
        self.assertEqual(self.pilot_allowed.order_completed_count, 1)
        self.assertEqual(self.pilot_allowed.delivery_completed_count, 0)
        self.assertEqual(self.pilot_allowed.handled_item_count, 1)
        assignment.invalidate_recordset()
        self.assertEqual(assignment.status, "done")
        self.assertTrue(assignment.end_datetime)

        second_start = self.env["ab_pharmacy_delivery_assignment_wizard"].sudo().create(
            {
                "pilot_id": self.pilot_allowed.id,
                "target_status": "in_delivery",
                "order_number": "DLV-2001",
                "transaction_type": "delivery",
                "branch_id": self.branch_allowed.id,
                "note": "Inter-branch supply transfer",
            }
        )
        second_start.action_apply()
        self.pilot_allowed.invalidate_recordset()
        self.assertEqual(self.pilot_allowed.delivery_assigned_count, 1)
        self.assertEqual(self.pilot_allowed.order_assigned_count, 0)

        second_close = self.env["ab_pharmacy_delivery_assignment_wizard"].sudo().create(
            {
                "pilot_id": self.pilot_allowed.id,
                "target_status": "free",
                "note": "Completed delivery run",
            }
        )
        second_close.action_apply()
        self.pilot_allowed.invalidate_recordset()
        self.assertEqual(self.pilot_allowed.delivery_completed_count, 1)
        self.assertEqual(self.pilot_allowed.order_completed_count, 1)
        self.assertEqual(self.pilot_allowed.handled_item_count, 2)

    def test_basic_user_is_limited_to_allowed_branch(self):
        allowed_count = self.env["ab_pharmacy_delivery_pilot"].with_user(self.basic_user).search_count(
            [("id", "=", self.pilot_allowed.id)]
        )
        hidden_count = self.env["ab_pharmacy_delivery_pilot"].with_user(self.basic_user).search_count(
            [("id", "=", self.pilot_hidden.id)]
        )
        self.assertEqual(allowed_count, 1)
        self.assertEqual(hidden_count, 0)

        with self.assertRaises(AccessError):
            self.pilot_allowed.with_user(self.basic_user).write({"name": "Blocked Update"})

    def test_force_back_to_free_without_open_assignment(self):
        self.pilot_allowed.write({"status": "in_delivery"})
        open_assignments = self.env["ab_pharmacy_delivery_assignment"].search(
            [("pilot_id", "=", self.pilot_allowed.id), ("status", "=", "assigned")]
        )
        open_assignments.unlink()

        close_wizard = self.env["ab_pharmacy_delivery_assignment_wizard"].sudo().create(
            {
                "pilot_id": self.pilot_allowed.id,
                "target_status": "free",
                "note": "Force close without active assignment",
            }
        )
        close_wizard.action_apply()
        self.pilot_allowed.invalidate_recordset()
        self.assertEqual(self.pilot_allowed.status, "free")

    def test_dashboard_payload_includes_sign_in_fields(self):
        first_sign_in = fields.Datetime.now()
        second_sign_in = first_sign_in + timedelta(hours=1)
        second_pilot = self.env["ab_pharmacy_delivery_pilot"].sudo().create(
            {
                "name": "مندوب اختبار 3",
                "branch_id": self.branch_allowed.id,
                "pilot_code": "7002",
                "shift": "3م-1ص",
                "sign_in_datetime": second_sign_in,
            }
        )
        self.pilot_allowed.write(
            {
                "pilot_code": "7001",
                "shift": "8ص-6م",
                "sign_in_datetime": first_sign_in,
            }
        )
        payload = self.env["ab_pharmacy_delivery_pilot"].get_dashboard_payload(self.branch_allowed.id)
        pilot_data = next((pilot for pilot in payload["pilots"] if pilot["id"] == self.pilot_allowed.id), None)
        self.assertTrue(pilot_data)
        self.assertEqual(pilot_data["pilot_code"], "7001")
        self.assertEqual(pilot_data["shift"], "8ص-6م")
        self.assertTrue(pilot_data["sign_in_datetime"])
        self.assertEqual(pilot_data["sign_in_order"], 1)
        self.assertEqual(pilot_data["daily_handle_count"], 0)
        second_data = next((pilot for pilot in payload["pilots"] if pilot["id"] == second_pilot.id), None)
        self.assertTrue(second_data)
        self.assertEqual(second_data["sign_in_order"], 2)
