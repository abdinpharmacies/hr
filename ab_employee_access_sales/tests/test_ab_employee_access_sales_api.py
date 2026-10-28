from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
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
            "group_ids": [(6, 0, [group_user.id])],
        })
        self.hr_manager_user = Users.create({
            "name": "POS HR Manager User",
            "login": "pos_hr_manager_user",
            "email": "pos_hr_manager_user@example.com",
            "group_ids": [(6, 0, [group_user.id, group_manager.id])],
        })
        self.normal_user = Users.create({
            "name": "Normal POS User",
            "login": "normal_pos_user",
            "email": "normal_pos_user@example.com",
            "group_ids": [(6, 0, [group_user.id])],
        })

        self.store = self.env["ab_store"].sudo().create({
            "name": "POS HR Test Store",
            "code": "POS-HR",
            "allow_sale": True,
            "eplus_serial": 81001,
            "pos_service_user_id": self.service_user.id,
        })
        self.store_2 = self.env["ab_store"].sudo().create({
            "name": "POS HR Test Store 2",
            "code": "POS-HR-2",
            "allow_sale": True,
            "eplus_serial": 81002,
            "pos_service_user_id": self.service_user.id,
        })
        self.store_unconfigured = self.env["ab_store"].sudo().create({
            "name": "POS HR Test Store 3",
            "code": "POS-HR-3",
            "allow_sale": True,
            "eplus_serial": 81003,
        })
        self.store_inactive = self.env["ab_store"].sudo().create({
            "name": "POS HR Inactive Store",
            "code": "POS-HR-I",
            "allow_sale": True,
            "active": False,
            "eplus_serial": 81004,
        })
        self.store_sale_disabled = self.env["ab_store"].sudo().create({
            "name": "POS HR Sale Disabled Store",
            "code": "POS-HR-D",
            "allow_sale": False,
            "eplus_serial": 81005,
        })
        administrator = self.env.ref("base.user_admin")
        self.rpc_config = self.env["ab_sales_branch_rpc_config"].sudo().create({
            "name": "POS HR Test RPC",
            "store_id": self.store.id,
            "db_serial": 91001,
            "rpc_url": "https://pos-hr-test.example.com",
            "rpc_db": "pos_hr_test",
            "api_key": "test-api-key-1",
            "administrator_id": administrator.id,
        })
        self.rpc_config.write({"enrollment_state": "ready", "can_post": True})
        self.rpc_config_2 = self.env["ab_sales_branch_rpc_config"].sudo().create({
            "name": "POS HR Test RPC 2",
            "store_id": self.store_2.id,
            "db_serial": 91002,
            "rpc_url": "https://pos-hr-test-2.example.com",
            "rpc_db": "pos_hr_test_2",
            "api_key": "test-api-key-2",
            "administrator_id": administrator.id,
        })
        self.rpc_config_2.write({"enrollment_state": "ready", "can_post": True})

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

    def _mock_local_pos_submit(self, pos_api, payload):
        header, _duplicate, _policy = pos_api._pos_create_prepending_header_from_payload(payload)
        return pos_api._pos_submit_response(header, apply_submit=False)

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

    def test_scope_without_replica_or_profile_restriction_uses_all_sale_stores(self):
        self.cashier_profile.write({"pos_allowed_store_ids": [(5, 0, 0)]})
        scope = self.env["ab_employee_access_sales_pos_api"].with_user(self.normal_user)._resolve_pos_store_scope(
            profile=self.cashier_profile,
        )
        self.assertIn(self.store.id, scope["visible_store_ids"])
        self.assertIn(self.store_2.id, scope["visible_store_ids"])
        self.assertIn(self.store_unconfigured.id, scope["visible_store_ids"])
        self.assertNotIn(self.store_inactive.id, scope["visible_store_ids"])
        self.assertNotIn(self.store_sale_disabled.id, scope["visible_store_ids"])
        self.assertEqual(
            {self.store.id, self.store_2.id},
            {store_id for store_id in scope["available_store_ids"] if store_id in {self.store.id, self.store_2.id}},
        )
        unconfigured = next(row for row in scope["stores"] if row["id"] == self.store_unconfigured.id)
        self.assertFalse(unconfigured["connection_ready"])
        self.assertEqual(unconfigured["connection_state"], "not_configured")
        self.assertEqual(unconfigured["connection_message"], "Branch connection is not configured. Contact support.")

    def test_scope_applies_replica_and_profile_intersection(self):
        replica = self.env["ab_replica_db"].sudo().create({
            "name": "POS HR Replica Scope",
            "db_serial": 99101,
            "allowed_sales_store_ids": [(6, 0, [self.store_2.id])],
            "default_sales_store_id": self.store_2.id,
        })
        replica_model = type(self.env["ab_replica_db"])
        api = self.env["ab_employee_access_sales_pos_api"].with_user(self.normal_user)
        self.cashier_profile.write({"pos_allowed_store_ids": [(5, 0, 0)]})
        with patch.object(replica_model, "get_current_from_config", autospec=True, return_value=replica):
            replica_only = api._resolve_pos_store_scope(profile=self.cashier_profile)
        self.assertEqual(replica_only["visible_store_ids"], [self.store_2.id])
        self.assertEqual(replica_only["default_store"], self.store_2)

        self.cashier_profile.write({"pos_allowed_store_ids": [(6, 0, [self.store.id])]})
        with patch.object(replica_model, "get_current_from_config", autospec=True, return_value=replica):
            disjoint = api._resolve_pos_store_scope(profile=self.cashier_profile)
        self.assertFalse(disjoint["visible_store_ids"])
        self.assertEqual(disjoint["empty_reason"], "permission")
        self.assertEqual(disjoint["empty_message"], "No stores match the Replica DB and employee permissions.")

    def test_scope_does_not_bypass_profile_for_admin_manager_or_service_assignment(self):
        self.cashier_profile.write({"pos_allowed_store_ids": [(6, 0, [self.store.id])]})
        sales_manager = self.hr_manager_user
        sales_manager.write({"group_ids": [(4, self.env.ref("ab_sales.group_ab_sales_manager").id)]})
        self.normal_user.write({"group_ids": [(4, self.env.ref("ab_sales.group_call_center").id)]})
        self.env["ab_hr_department"].sudo().create({
            "name": "POS HR Unrelated Department",
            "store_id": self.store_2.id,
            "user_id": self.normal_user.id,
        })
        api_model = self.env["ab_employee_access_sales_pos_api"]
        for user in (self.env.ref("base.user_admin"), sales_manager, self.normal_user):
            scope = api_model.with_user(user)._resolve_pos_store_scope(profile=self.cashier_profile)
            self.assertIn(self.store.id, scope["available_store_ids"])
            self.assertNotIn(self.store_2.id, scope["visible_store_ids"])

    def test_not_ready_store_is_visible_and_rejected(self):
        self.rpc_config_2.write({"can_post": False})
        scope = self.env["ab_employee_access_sales_pos_api"].with_user(self.service_user)._resolve_pos_store_scope(
            profile=self.cashier_profile,
        )
        row = next(item for item in scope["stores"] if item["id"] == self.store_2.id)
        self.assertFalse(row["connection_ready"])
        self.assertEqual(row["connection_state"], "posting_disabled")
        login = self._login_cashier()
        with self.assertRaisesRegex(UserError, "Branch connection is not configured"):
            self.env["ab_employee_access_sales_pos_api"].with_user(self.service_user).change_store(
                session_token=login["token"],
                store_id=self.store_2.id,
            )

    def test_session_token_is_bound_to_current_internal_user(self):
        login = self._login_cashier()
        with self.assertRaises(UserError):
            self.env["ab_employee_access_sales_pos_api"].with_user(self.normal_user).heartbeat(login["token"])

    def test_product_rpc_rejects_profile_out_of_scope_store(self):
        self.cashier_profile.write({"pos_allowed_store_ids": [(6, 0, [self.store.id])]})
        login = self._login_cashier()
        with self.assertRaises(AccessError):
            self.env["ab_sales_pos_api"].with_user(self.service_user).pos_product_details(
                self.store_2.id,
                self.product.id,
                pos_hr_session_token=login["token"],
            )

    def test_user_can_read_only_own_trusted_callcenter_bill_without_branch_assignment(self):
        own_header = self.env["ab_sales_header"].with_user(self.normal_user)._create_callcenter_order({
            "store_id": self.store.id,
            "description": "Own trusted POS bill",
        })
        other_header = self.env["ab_sales_header"].with_user(self.service_user)._create_callcenter_order({
            "store_id": self.store.id,
            "description": "Other trusted POS bill",
        })
        visible = self.env["ab_sales_header"].with_user(self.normal_user).search([
            ("id", "in", [own_header.id, other_header.id]),
        ])
        self.assertEqual(visible, own_header)

    def test_owner_opens_return_dialog_before_employee_login(self):
        sale_header = self.env["ab_sales_header"].with_user(self.normal_user)._create_callcenter_order({
            "store_id": self.store.id,
            "description": "Owner return dialog",
        })
        sale_header.sudo()._write_branch_state({"status": "saved", "eplus_serial": 881001})
        return_header = self.env["ab_sales_return_header"].with_user(self.normal_user)._create_callcenter_order({
            "store_id": self.store.id,
            "origin_header_id": 881001,
        })
        header_model = type(self.env["ab_sales_header"])
        return_api = self.env["ab_sales_return_ui_api"].with_user(self.normal_user)

        with patch.object(
            header_model,
            "action_open_sales_return",
            autospec=True,
            return_value={"res_id": return_header.id},
        ):
            action = return_api.open_from_sale_header(sale_header.id)

        self.assertEqual(action["tag"], "ab_sales.return_ui")
        self.assertEqual(action["params"]["return_header_id"], return_header.id)
        with self.assertRaisesRegex(UserError, "Employee login is required"):
            return_api.get_state(return_header.id)

        session = self.env["ab_employee_access_sales_pos_api"].with_user(self.normal_user).employee_login(
            employee_id=self.manager_employee.id,
            pin="9999",
            store_id=self.store.id,
            device_uid="OWNER_RETURN_DEVICE",
            device_name="Owner Return Device",
        )
        state = return_api.get_state(return_header.id, session_token=session["token"])
        self.assertEqual(state["id"], return_header.id)

    def test_return_dialog_rejects_invalid_supplied_session(self):
        sale_header = self.env["ab_sales_header"].with_user(self.normal_user)._create_callcenter_order({
            "store_id": self.store.id,
            "description": "Invalid return token",
        })
        with self.assertRaisesRegex(UserError, "Employee POS session is missing or expired"):
            self.env["ab_sales_return_ui_api"].with_user(self.normal_user).open_from_sale_header(
                sale_header.id,
                session_token="expired-return-session",
            )

    def test_other_user_cannot_open_owner_return_dialog(self):
        sale_header = self.env["ab_sales_header"].with_user(self.normal_user)._create_callcenter_order({
            "store_id": self.store.id,
            "description": "Private owner return",
        })
        with self.assertRaises(AccessError):
            self.env["ab_sales_return_ui_api"].with_user(self.service_user).open_from_sale_header(sale_header.id)

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
        resolved = header.with_user(self.service_user).with_context(
            ab_return_session_token=payload["token"],
        )._get_eplus_emp_id()
        self.assertEqual(resolved, self.manager_costcenter.eplus_serial)

    def test_pos_submit_tracks_employee_session_and_log(self):
        login_payload = self._login_cashier()
        pos_api = self.env["ab_sales_pos_api"].with_user(self.service_user)
        pos_api_cls = type(pos_api)

        with patch.object(
            pos_api_cls,
            "_pos_submit_to_branch_rpc",
            autospec=True,
            side_effect=self._mock_local_pos_submit,
        ):
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
        pos_api_cls = type(pos_api)

        with patch.object(
            pos_api_cls,
            "_pos_submit_to_branch_rpc",
            autospec=True,
            side_effect=self._mock_local_pos_submit,
        ):
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
