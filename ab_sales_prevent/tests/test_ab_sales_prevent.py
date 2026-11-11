from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase


class TestAbSalesPrevent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prevent = cls.env["ab_sales_prevent.mixin"]
        cls.param = cls.prevent._SALES_PREVENT_PARAM
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Sales Prevent User",
            "login": "sales_prevent_user",
            "email": "sales_prevent_user@example.com",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _set_prevent_enabled(self, enabled):
        self.env["ir.config_parameter"].sudo().set_param(
            self.param,
            "1" if enabled else "0",
        )
        self.env.registry.clear_cache()

    def _prevented_menu_ids(self):
        menus = self.env["ir.ui.menu"]
        return {
            self.env.ref(xmlid).id
            for xmlid in menus._SALES_PREVENT_MENU_XMLIDS
        }

    def test_prevent_enabled_by_default(self):
        self.assertTrue(self.prevent._sales_prevent_enabled())

    def test_prevent_parser_accepts_only_truthy_values(self):
        param = self.env["ir.config_parameter"].sudo()
        for value in ("0", "false", "no", "off", ""):
            param.set_param(self.param, value)
            self.env.registry.clear_cache()
            self.assertFalse(self.prevent._sales_prevent_enabled())
        for value in ("1", "true", "yes", "on"):
            param.set_param(self.param, value)
            self.env.registry.clear_cache()
            self.assertTrue(self.prevent._sales_prevent_enabled())

    def test_menus_are_blacklisted_only_when_prevent_enabled(self):
        menus = self.env["ir.ui.menu"]
        prevented_ids = self._prevented_menu_ids()
        root_menu = self.env.ref("ab_sales.sales_menu_root")

        self._set_prevent_enabled(True)
        blacklist = set(menus._load_menus_blacklist())
        self.assertTrue(prevented_ids.issubset(blacklist))
        self.assertNotIn(root_menu.id, blacklist)

        self._set_prevent_enabled(False)
        self.assertFalse(prevented_ids & set(menus._load_menus_blacklist()))

    def test_dashboard_action_is_removed_from_sales_root_when_enabled(self):
        menus = self.env["ir.ui.menu"]
        root_menu = self.env.ref("ab_sales.sales_menu_root")
        dashboard_action = self.env.ref("ab_sales.ab_sales_dashboard_action")

        self._set_prevent_enabled(True)
        menu_data = {
            "action_model": "ir.actions.client",
            "action_id": dashboard_action.id,
            "action_path": False,
        }
        menus._sales_prevent_clear_dashboard_menu_action(menu_data, dashboard_action)
        self.assertFalse(menu_data["action_model"])
        self.assertFalse(menu_data["action_id"])

        root_data = {
            "children": [{
                "id": root_menu.id,
                "action": f"ir.actions.client,{dashboard_action.id}",
            }],
        }
        menus._sales_prevent_clear_dashboard_root_action(root_data, root_menu, dashboard_action)
        self.assertFalse(root_data["children"][0]["action"])

    def test_settings_toggle_updates_parameter(self):
        settings = self.env["res.config.settings"].create({
            "ab_sales_prevent_enabled": False,
        })
        settings.set_values()
        self.assertFalse(self.prevent._sales_prevent_enabled())

        settings = self.env["res.config.settings"].create({
            "ab_sales_prevent_enabled": True,
        })
        settings.set_values()
        self.assertTrue(self.prevent._sales_prevent_enabled())

    def test_model_write_access_is_blocked_when_enabled(self):
        self._set_prevent_enabled(True)
        SalesHeader = self.env["ab_sales_header"].with_user(self.user)

        SalesHeader.browse().check_access("read")
        with self.assertRaises(AccessError):
            SalesHeader.sudo().create({})
        with self.assertRaises(AccessError):
            SalesHeader.browse().check_access("write")

    def test_model_access_is_allowed_when_disabled(self):
        self._set_prevent_enabled(False)
        SalesHeader = self.env["ab_sales_header"].with_user(self.user)

        SalesHeader.browse().check_access("read")
        self.assertTrue(SalesHeader.browse().has_access("read"))

    def test_public_api_methods_are_blocked_when_enabled(self):
        self._set_prevent_enabled(True)

        with self.assertRaises(AccessError):
            self.env["ab_sales_pos_api"].pos_default_employee()
        with self.assertRaises(AccessError):
            self.env["ab_sales_ui_api"].bill_wizard_search()
        with self.assertRaises(AccessError):
            self.env["ab_sales_cashier_api"].get_cashier_bootstrap()
        with self.assertRaises(AccessError):
            self.env["ab_sales_lead"].pos_item_report()
        with self.assertRaises(AccessError):
            self.env["ab_sales_header"].get_sales_dashboard_payload()
