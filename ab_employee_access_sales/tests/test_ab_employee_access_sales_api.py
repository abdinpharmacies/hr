from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestAbSalesHrApi(TransactionCase):
    def setUp(self):
        super().setUp()

        Users = self.env["res.users"].with_context(no_reset_password=True)
        group_user = self.env.ref("base.group_user")
        group_manager = self.env.ref("ab_employee_access_sales.group_ab_employee_access_sales_manager")

        self.service_user = Users.create({
            "name": "Branch Service User",
            "login": "branch_service_user",
            "email": "branch_service_user@example.com",
            "groups_id": [(6, 0, [group_user.id])],
        })
        self.hr_manager_user = Users.create({
            "name": "POS HR Manager User",
            "login": "pos_hr_manager_user",
            "email": "pos_hr_manager_user@example.com",
            "groups_id": [(6, 0, [group_user.id, group_manager.id])],
        })
        self.normal_user = Users.create({
            "name": "Normal POS User",
            "login": "normal_pos_user",
            "email": "normal_pos_user@example.com",
            "groups_id": [(6, 0, [group_user.id])],
        })

        self.store = self.env["ab_store"].sudo().create({
            "name": "POS HR Test Store",
            "code": "POS-HR",
            "allow_sale": True,
            "pos_service_user_id": self.service_user.id,
        })
        self.store_2 = self.env["ab_store"].sudo().create({
            "name": "POS HR Test Store 2",
            "code": "POS-HR-2",
            "allow_sale": True,
            "pos_service_user_id": self.service_user.id,
        })

        self.cashier_role = self.env["ab_employee_access_sales_role"].sudo().create({
            "name": "Cashier",
            "allow_pos_screen": True,
        })
        self.manager_role = self.env["ab_employee_access_sales_role"].sudo().create({
            "name": "Manager",
            "allow_pos_screen": True,
            "allow_return_screen": True,
        })

        self.cashier_employee = self.env["ab_hr_employee"].sudo().create({
            "name": "Cashier Employee",
            "barcode": "EMP100",
        })
        self.cashier_profile = self.env["ab_employee_access"].sudo().create({
            "employee_id": self.cashier_employee.id,
            "pos_pin": "1234",
            "pos_role_id": self.cashier_role.id,
            "pos_allowed_store_ids": [(6, 0, [self.store.id, self.store_2.id])],
        })
        self.manager_employee = self.env["ab_hr_employee"].sudo().create({
            "name": "Manager Employee",
            "barcode": "MGR900",
        })
        self.manager_costcenter = self.env["ab_costcenter"].sudo().create({
            "name": "Manager Costcenter",
            "code": "MGR-900",
            "bc_id": 900,
            "eplus_serial": 700900,
        })
        self.manager_employee.write({"costcenter_id": self.manager_costcenter.id})
        self.manager_profile = self.env["ab_employee_access"].sudo().create({
            "employee_id": self.manager_employee.id,
            "pos_pin": "9999",
            "pos_role_id": self.manager_role.id,
            "pos_allowed_store_ids": [(6, 0, [self.store.id, self.store_2.id])],
        })

        uom_category = self.env["ab_product_uom_category"].sudo().create({"name": "Unit"})
        uom = self.env["ab_product_uom"].sudo().create({
            "name": "Piece",
            "category_id": uom_category.id,
            "uom_type": "reference",
            "factor": 1.0,
        })
        product_card = self.env["ab_product_card"].sudo().create({
            "name": "POS HR Product Card",
            "allow_sale": True,
        })
        self.product = self.env["ab_product"].sudo().create({
            "product_card_id": product_card.id,
            "name": "POS HR Product",
            "product_card_name": "POS HR Product",
            "default_price": 100.0,
            "code": "P-100",
            "uom_category_id": uom_category.id,
            "uom_id": uom.id,
            "allow_sale": True,
            "eplus_serial": 123456,
        })

    def _login_cashier(self):
        return self.env["ab_employee_access_sales_pos_api"].with_user(self.service_user).employee_login(
            employee_id=self.cashier_employee.id,
            pin="1234",
            store_id=self.store.id,
            device_uid="TEST_DEVICE",
            device_name="Unit Test Device",
        )

    def _login_cashier_without_store(self):
        return self.env["ab_employee_access_sales_pos_api"].with_user(self.service_user).employee_login(
            employee_id=self.cashier_employee.id,
            pin="1234",
            store_id=False,
            device_uid="TEST_DEVICE",
            device_name="Unit Test Device",
        )

    def _mock_action_submit(self, recordset):
        for rec in recordset:
            rec.write({
                "status": "pending",
                "eplus_serial": rec.eplus_serial or (900000 + rec.id),
            })
        return True

    def test_employee_login_opens_session(self):
        payload = self._login_cashier()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["employee"]["id"], self.cashier_employee.id)
        self.assertEqual(payload["store"]["id"], self.store.id)
        self.assertNotIn("idle_lock_seconds", payload)
        self.assertNotIn("idle_lock_seconds", payload["permissions"])

        session = self.env["ab_employee_access_sales_pos_session"].sudo().browse(payload["session_id"])
        self.assertEqual(session.state, "active")
        self.assertEqual(session.employee_id, self.cashier_employee)
        self.assertEqual(session.profile_id, self.cashier_profile)
        self.assertFalse(payload["shift_id"])

    def test_custom_permissions_payload_excludes_idle_timeout(self):
        self.cashier_profile.write({
            "pos_use_custom_permissions": True,
            "pos_allow_pos_screen": True,
        })
        payload = self._login_cashier()
        self.assertNotIn("idle_lock_seconds", payload)
        self.assertNotIn("idle_lock_seconds", payload["permissions"])

    def test_employee_login_without_store_uses_allowed_default(self):
        payload = self._login_cashier_without_store()
        session = self.env["ab_employee_access_sales_pos_session"].sudo().browse(payload["session_id"])
        self.assertTrue(payload["token"])
        self.assertEqual(session.employee_id, self.cashier_employee)
        self.assertIn(payload["store"]["id"], self.cashier_profile.pos_allowed_store_ids.ids)

    def test_change_store_updates_active_session(self):
        payload = self._login_cashier()
        updated = self.env["ab_employee_access_sales_pos_api"].with_user(self.service_user).change_store(
            session_token=payload["token"],
            store_id=self.store_2.id,
        )
        session = self.env["ab_employee_access_sales_pos_session"].sudo().browse(payload["session_id"])
        self.assertEqual(updated["store"]["id"], self.store_2.id)
        self.assertEqual(session.store_id, self.store_2)

    def test_eplus_employee_uses_return_login_session_employee(self):
        payload = self.env["ab_employee_access_sales_pos_api"].with_user(self.service_user).employee_login(
            employee_id=self.manager_employee.id,
            pin="9999",
            store_id=self.store.id,
            device_uid="RETURN_DEVICE",
            device_name="Return Device",
        )
        header = self.env["ab_sales_header"].sudo().create({
            "store_id": self.store.id,
            "description": "Return employee test",
        })
        resolved = header.with_context(ab_return_session_token=payload["token"])._get_eplus_emp_id()
        self.assertEqual(resolved, self.manager_costcenter.eplus_serial)

    def test_pos_submit_tracks_employee_session_and_log(self):
        login_payload = self._login_cashier()
        pos_api = self.env["ab_sales_pos_api"].with_user(self.service_user)
        model_cls = type(self.env["ab_sales_header"])

        with patch.object(model_cls, "action_submit", autospec=True, side_effect=self._mock_action_submit):
            result = pos_api.pos_submit({
                "header": {
                    "store_id": self.store.id,
                    "description": "POS HR tracked submit",
                    "pos_client_token": "tok_submit_1",
                },
                "lines": [
                    {
                        "product_id": self.product.id,
                        "qty_str": "1",
                        "sell_price": 100.0,
                        "uom_id": self.product.uom_id.id,
                    }
                ],
                "pos_hr_session_token": login_payload["token"],
            })

        header = self.env["ab_sales_header"].sudo().browse(result["id"])
        self.assertEqual(header.employee_id, self.cashier_employee)
        self.assertEqual(header.pos_hr_employee_id, self.cashier_employee)
        self.assertEqual(header.pos_hr_profile_id, self.cashier_profile)
        self.assertFalse(header.pos_hr_shift_id)
        self.assertTrue(header.pos_hr_session_id)
        self.assertEqual(header.pos_hr_device_uid, "TEST_DEVICE")
        self.assertTrue(header.pos_hr_device_ip is not None)

        submit_log = self.env["ab_employee_access_sales_operation_log"].sudo().search([
            ("header_id", "=", header.id),
            ("operation_type", "=", "sale_submit"),
            ("operation_status", "=", "success"),
        ], limit=1)
        self.assertTrue(submit_log)
        self.assertEqual(submit_log.employee_id, self.cashier_employee)
        self.assertEqual(submit_log.profile_id, self.cashier_profile)

    def test_pos_submit_keeps_actual_salesperson_and_tracks_logged_employee(self):
        login_payload = self._login_cashier()
        pos_api = self.env["ab_sales_pos_api"].with_user(self.service_user)
        model_cls = type(self.env["ab_sales_header"])

        with patch.object(model_cls, "action_submit", autospec=True, side_effect=self._mock_action_submit):
            result = pos_api.pos_submit({
                "header": {
                    "store_id": self.store.id,
                    "description": "Actual salesperson override",
                    "employee_id": self.manager_employee.id,
                    "pos_client_token": "tok_submit_override_1",
                },
                "lines": [
                    {
                        "product_id": self.product.id,
                        "qty_str": "1",
                        "sell_price": 100.0,
                        "uom_id": self.product.uom_id.id,
                    }
                ],
                "pos_hr_session_token": login_payload["token"],
            })

        header = self.env["ab_sales_header"].sudo().browse(result["id"])
        self.assertEqual(header.employee_id, self.manager_employee)
        self.assertEqual(header.pos_hr_employee_id, self.cashier_employee)

    def test_role_creation_requires_manager_group(self):
        with self.assertRaises(AccessError):
            self.env["ab_employee_access_sales_role"].with_user(self.normal_user).create({
                "name": "Forbidden Role",
            })
