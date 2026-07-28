from odoo import api, models


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    _SALES_PREVENT_MENU_XMLIDS = (
        "ab_sales.ab_sales_pos_menu",
        "ab_sales.ab_sales_bill_wizard_menu",
        "ab_sales.ab_sales_header_menu",
        "ab_sales.ab_sales_return_header_menu",
        "ab_sales_cashier.ab_sales_cashier_menu",
        "ab_sales_lead.ab_sales_lead_menu",
    )
    _SALES_PREVENT_ROOT_MENU_XMLID = "ab_sales.sales_menu_root"
    _SALES_PREVENT_DASHBOARD_ACTION_XMLID = "ab_sales.ab_sales_dashboard_action"

    @api.model
    def _sales_prevent_enabled(self):
        return self.env["ab_sales_prevent.mixin"]._sales_prevent_enabled()

    @api.model
    def _sales_prevent_dashboard_refs(self):
        root_menu = self.env.ref(self._SALES_PREVENT_ROOT_MENU_XMLID, raise_if_not_found=False)
        dashboard_action = self.env.ref(self._SALES_PREVENT_DASHBOARD_ACTION_XMLID, raise_if_not_found=False)
        return root_menu, dashboard_action

    @api.model
    def _sales_prevent_clear_dashboard_menu_action(self, menu_data, dashboard_action):
        if not menu_data or not dashboard_action:
            return
        if menu_data.get("action_model") == "ir.actions.client" and menu_data.get("action_id") == dashboard_action.id:
            menu_data["action_model"] = False
            menu_data["action_id"] = False
            menu_data["action_path"] = False

    @api.model
    def _sales_prevent_clear_dashboard_root_action(self, root_data, root_menu, dashboard_action):
        if not root_data or not root_menu or not dashboard_action:
            return
        dashboard_ref = f"ir.actions.client,{dashboard_action.id}"
        for menu_data in root_data.get("children") or []:
            if menu_data.get("id") == root_menu.id and menu_data.get("action") == dashboard_ref:
                menu_data["action"] = False

    def _load_menus_blacklist(self):
        result = super()._load_menus_blacklist()
        if not self._sales_prevent_enabled():
            return result

        for xmlid in self._SALES_PREVENT_MENU_XMLIDS:
            menu = self.env.ref(xmlid, raise_if_not_found=False)
            if menu:
                result.append(menu.id)
        return result

    @api.model
    def load_menus(self, debug):
        result = super().load_menus(debug)
        if self._sales_prevent_enabled():
            root_menu, dashboard_action = self._sales_prevent_dashboard_refs()
            if root_menu:
                result = dict(result)
                result[root_menu.id] = dict(result.get(root_menu.id) or {})
                self._sales_prevent_clear_dashboard_menu_action(result.get(root_menu.id), dashboard_action)
        return result

    @api.model
    def load_menus_root(self):
        result = super().load_menus_root()
        if self._sales_prevent_enabled():
            root_menu, dashboard_action = self._sales_prevent_dashboard_refs()
            result = dict(result)
            result["children"] = [dict(menu_data) for menu_data in result.get("children") or []]
            self._sales_prevent_clear_dashboard_root_action(result, root_menu, dashboard_action)
        return result
