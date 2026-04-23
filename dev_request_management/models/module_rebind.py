# -*- coding: utf-8 -*-
import logging

from odoo import api, models
from ..hooks import _ensure_admin_group_membership

_logger = logging.getLogger(__name__)


class DevRequestModuleRebind(models.AbstractModel):
    _name = "dev.request.module.rebind"
    _description = "Development Request Module Rebind"

    @api.model
    def _register_hook(self):
        result = super()._register_hook()
        self._rebind_module_records()
        return result

    @api.model
    def _rebind_module_records(self):
        self = self.sudo().with_context(active_test=False)
        self._ensure_model_entries()
        self._rebind_security_records()
        _ensure_admin_group_membership(self.env)
        self._rebind_seed_records()
        self._rebind_views_and_actions()
        self._rebind_menus()
        self._fix_broken_actions()
        self._fix_broken_menu_actions()
        self._fix_global_broken_window_actions()

    @api.model
    def _ensure_model_entries(self):
        model_names = [
            "development.request",
            "development.request.stage",
            "development.request.team",
            "development.request.category",
            "development.request.followup",
            "ui.appearance.settings",
        ]
        ir_model = self.env["ir.model"].sudo()
        existing = set(ir_model.search([("model", "in", model_names)]).mapped("model"))
        missing = [model_name for model_name in model_names if model_name not in existing]
        if missing:
            ir_model.with_context(module="dev_request_management")._reflect_models(missing)

    @api.model
    def _ensure_xmlid_binding(self, xmlid, model_name, finder, create_values=None, noupdate=True):
        module, name = xmlid.split(".", 1)
        imd = self.env["ir.model.data"].sudo()
        model = self.env[model_name].sudo().with_context(active_test=False)
        binding = imd.search([("module", "=", module), ("name", "=", name)], limit=1)
        record = model.browse()
        if binding:
            record = model.browse(binding.res_id).exists()
            if record:
                if binding.model != model_name or binding.noupdate != noupdate:
                    binding.write({"model": model_name, "noupdate": noupdate})
                return record
        record = finder()
        if not record and create_values:
            record = model.create(create_values)
        if not record:
            return model.browse()
        if binding:
            binding.write({"model": model_name, "res_id": record.id, "noupdate": noupdate})
        else:
            imd.create(
                {
                    "module": module,
                    "name": name,
                    "model": model_name,
                    "res_id": record.id,
                    "noupdate": noupdate,
                }
            )
        return record

    @api.model
    def _find_by_name(self, model_name, name, extra_domain=None):
        domain = [("name", "=", name)]
        if extra_domain:
            domain += list(extra_domain)
        return self.env[model_name].sudo().with_context(active_test=False).search(domain, limit=1)

    @api.model
    def _rebind_security_records(self):
        category = self._ensure_xmlid_binding(
            "dev_request_management.module_category_development_request_management",
            "ir.module.category",
            lambda: self._find_by_name("ir.module.category", "Development Request Management"),
            {"name": "Development Request Management", "sequence": 35},
            noupdate=False,
        )
        privilege = self._ensure_xmlid_binding(
            "dev_request_management.development_request_groups_privilege",
            "res.groups.privilege",
            lambda: self._find_by_name(
                "res.groups.privilege",
                "Development Requests",
                [("category_id", "=", category.id)],
            ),
            {"name": "Development Requests", "category_id": category.id},
            noupdate=False,
        )
        groups = [
            (
                "dev_request_management.group_development_request_user",
                "Development Request Requester",
                "Can create and monitor their own development requests.",
            ),
            (
                "dev_request_management.group_development_request_developer",
                "Development Request Developer",
                "Can review, execute, and update development requests.",
            ),
            (
                "dev_request_management.group_development_request_lead",
                "Development Request Team Lead",
                "Can prioritize, approve, reject, and reassign requests.",
            ),
            (
                "dev_request_management.group_development_request_admin",
                "Development Request Administrator",
                "Can configure the module and see all analytics.",
            ),
            (
                "dev_request_management.group_development_request_ui_customizer",
                "Development Request UI Customizer",
                "Can preview and manage personal appearance customization for the module.",
            ),
        ]
        for xmlid, name, comment in groups:
            self._ensure_xmlid_binding(
                xmlid,
                "res.groups",
                lambda group_name=name: self._find_by_name("res.groups", group_name),
                {
                    "name": name,
                    "comment": comment,
                    "privilege_id": privilege.id,
                },
                noupdate=False,
            )

    @api.model
    def _rebind_seed_records(self):
        for xmlid, values in [
            ("dev_request_management.development_request_stage_draft", {"name": "Draft", "code": "draft", "sequence": 10}),
            ("dev_request_management.development_request_stage_submitted", {"name": "Submitted", "code": "submitted", "sequence": 20}),
            ("dev_request_management.development_request_stage_under_review", {"name": "Under Review", "code": "under_review", "sequence": 30}),
            ("dev_request_management.development_request_stage_approved", {"name": "Approved", "code": "approved", "sequence": 40}),
            ("dev_request_management.development_request_stage_in_progress", {"name": "In Progress", "code": "in_progress", "sequence": 50}),
            ("dev_request_management.development_request_stage_testing", {"name": "Testing", "code": "testing", "sequence": 60}),
            ("dev_request_management.development_request_stage_done", {"name": "Done", "code": "done", "sequence": 70, "fold": True}),
            ("dev_request_management.development_request_stage_rejected", {"name": "Rejected", "code": "rejected", "sequence": 80, "fold": True}),
        ]:
            code = values["code"]
            self._ensure_xmlid_binding(
                xmlid,
                "development.request.stage",
                lambda stage_code=code: self.env["development.request.stage"].sudo().search([("code", "=", stage_code)], limit=1),
                values,
            )
        for xmlid, values in [
            ("dev_request_management.development_request_team_product", {"name": "Product", "sequence": 10, "board_color": "green", "color": 10}),
            ("dev_request_management.development_request_team_marketing", {"name": "Marketing", "sequence": 20, "board_color": "yellow", "color": 3}),
            ("dev_request_management.development_request_team_sales", {"name": "Sales", "sequence": 30, "board_color": "yellow", "color": 2}),
            ("dev_request_management.development_request_team_support", {"name": "Support", "sequence": 40, "board_color": "red", "color": 1}),
            ("dev_request_management.development_request_team_people", {"name": "People", "sequence": 50, "board_color": "pink", "color": 9}),
            ("dev_request_management.development_request_team_it", {"name": "IT", "sequence": 60, "board_color": "dark_blue", "color": 11}),
            ("dev_request_management.development_request_team_analytics", {"name": "Analytics", "sequence": 70, "board_color": "light_blue", "color": 7}),
            ("dev_request_management.development_request_team_executive", {"name": "Executive", "sequence": 80, "board_color": "orange", "color": 4}),
        ]:
            team_name = values["name"]
            self._ensure_xmlid_binding(
                xmlid,
                "development.request.team",
                lambda current_name=team_name: self._find_by_name("development.request.team", current_name),
                values,
            )
        for xmlid, values in [
            ("dev_request_management.development_request_category_product", {"name": "Product / Development", "color": 10}),
            ("dev_request_management.development_request_category_marketing", {"name": "Marketing / Sales", "color": 3}),
            ("dev_request_management.development_request_category_analytics", {"name": "Analytics / Data", "color": 7}),
            ("dev_request_management.development_request_category_it", {"name": "IT / Infrastructure", "color": 11}),
            ("dev_request_management.development_request_category_support", {"name": "Documentation / Support", "color": 1}),
            ("dev_request_management.development_request_category_executive", {"name": "Executive / High-Level Strategy", "color": 4}),
            ("dev_request_management.development_request_category_people", {"name": "People / HR", "color": 9}),
        ]:
            category_name = values["name"]
            self._ensure_xmlid_binding(
                xmlid,
                "development.request.category",
                lambda current_name=category_name: self._find_by_name("development.request.category", current_name),
                values,
            )
        self._ensure_xmlid_binding(
            "dev_request_management.seq_development_request",
            "ir.sequence",
            lambda: self.env["ir.sequence"].sudo().search([("code", "=", "development.request")], limit=1),
            {
                "name": "Development Request",
                "code": "development.request",
                "prefix": "DRQ%(y)s",
                "padding": 4,
                "company_id": False,
            },
        )
        self._ensure_xmlid_binding(
            "dev_request_management.ui_appearance_settings_default_global",
            "ui.appearance.settings",
            lambda: self.env["ui.appearance.settings"].sudo().search([("scope", "=", "global")], limit=1),
            self.env["ui.appearance.settings"].sudo()._default_theme_values() | {
                "name": "Global Development Requests Theme",
                "scope": "global",
            },
        )
        for xmlid, name, code in [
            (
                "dev_request_management.ir_cron_development_request_deadline_watch",
                "Development Request Deadline Watch",
                "model._cron_deadline_watch()",
            ),
            (
                "dev_request_management.ir_cron_development_request_recurring",
                "Development Request Recurring Generator",
                "model._cron_generate_recurring_requests()",
            ),
        ]:
            self._ensure_xmlid_binding(
                xmlid,
                "ir.cron",
                lambda cron_name=name, cron_code=code: self.env["ir.cron"].sudo().search(
                    [("name", "=", cron_name), ("code", "=", cron_code)],
                    limit=1,
                ),
                {
                    "name": name,
                    "model_id": self.env.ref("dev_request_management.model_development_request").id,
                    "state": "code",
                    "code": code,
                    "interval_number": 1,
                    "interval_type": "days",
                    "active": True,
                },
            )

    @api.model
    def _rebind_views_and_actions(self):
        for xmlid, model_name, view_name in [
            ("dev_request_management.view_development_request_search", "development.request", "development.request.search"),
            ("dev_request_management.view_development_request_list", "development.request", "development.request.list"),
            ("dev_request_management.view_development_request_kanban", "development.request", "development.request.kanban"),
            ("dev_request_management.view_development_request_board_kanban", "development.request", "development.request.board.kanban"),
            ("dev_request_management.view_development_request_form", "development.request", "development.request.form"),
            ("dev_request_management.view_development_request_pivot", "development.request", "development.request.pivot"),
            ("dev_request_management.view_development_request_graph", "development.request", "development.request.graph"),
            ("dev_request_management.view_development_request_calendar", "development.request", "development.request.calendar"),
            ("dev_request_management.view_ui_appearance_settings_list", "ui.appearance.settings", "ui.appearance.settings.list"),
            ("dev_request_management.view_ui_appearance_settings_form", "ui.appearance.settings", "ui.appearance.settings.form"),
        ]:
            self._ensure_xmlid_binding(
                xmlid,
                "ir.ui.view",
                lambda current_name=view_name, current_model=model_name: self.env["ir.ui.view"].sudo().search(
                    [("name", "=", current_name), ("model", "=", current_model)],
                    limit=1,
                ),
                noupdate=False,
            )
        for xmlid, values in [
            (
                "dev_request_management.action_development_request",
                {
                    "name": "Development Requests",
                    "res_model": "development.request",
                    "view_mode": "kanban,list,form,pivot,graph,calendar,activity",
                },
            ),
            (
                "dev_request_management.action_development_request_board",
                {
                    "name": "Overview Board",
                    "res_model": "development.request",
                    "view_mode": "kanban,list,graph,pivot,form",
                },
            ),
            (
                "dev_request_management.action_development_request_reporting",
                {
                    "name": "Analytics",
                    "res_model": "development.request",
                    "view_mode": "pivot,graph,list",
                },
            ),
            (
                "dev_request_management.action_development_request_stages",
                {
                    "name": "Stages",
                    "res_model": "development.request.stage",
                    "view_mode": "list,form",
                },
            ),
            (
                "dev_request_management.action_development_request_teams",
                {
                    "name": "Teams",
                    "res_model": "development.request.team",
                    "view_mode": "list,form",
                },
            ),
            (
                "dev_request_management.action_development_request_categories",
                {
                    "name": "Categories",
                    "res_model": "development.request.category",
                    "view_mode": "list,form",
                },
            ),
            (
                "dev_request_management.action_development_request_followups",
                {
                    "name": "Follow-ups",
                    "res_model": "development.request.followup",
                    "view_mode": "list,form",
                },
            ),
            (
                "dev_request_management.action_ui_appearance_settings",
                {
                    "name": "Appearance Settings",
                    "res_model": "ui.appearance.settings",
                    "view_mode": "list,form",
                },
            ),
        ]:
            action_name = values["name"]
            res_model = values["res_model"]
            self._ensure_xmlid_binding(
                xmlid,
                "ir.actions.act_window",
                lambda current_name=action_name, current_model=res_model: self.env["ir.actions.act_window"].sudo().search(
                    [("name", "=", current_name), ("res_model", "=", current_model)],
                    limit=1,
                ),
                values,
                noupdate=False,
            )

    @api.model
    def _rebind_menus(self):
        root_menu = self._ensure_xmlid_binding(
            "dev_request_management.menu_development_request_root",
            "ir.ui.menu",
            lambda: self._find_by_name("ir.ui.menu", "Development Requests"),
            {"name": "Development Requests", "sequence": 10},
            noupdate=False,
        )
        config_menu = self._ensure_xmlid_binding(
            "dev_request_management.menu_development_request_configuration",
            "ir.ui.menu",
            lambda: self.env["ir.ui.menu"].sudo().search(
                [("name", "=", "Configuration"), ("parent_id", "=", root_menu.id)],
                limit=1,
            ),
            {"name": "Configuration", "parent_id": root_menu.id, "sequence": 90},
            noupdate=False,
        )
        for xmlid, name, parent, sequence in [
            ("dev_request_management.menu_development_request_requests", "Requests", root_menu, 10),
            ("dev_request_management.menu_development_request_board", "Overview Board", root_menu, 20),
            ("dev_request_management.menu_development_request_reporting", "Analytics", root_menu, 30),
            ("dev_request_management.menu_development_request_stages_action", "Stages", config_menu, 10),
            ("dev_request_management.menu_development_request_teams_action", "Teams", config_menu, 20),
            ("dev_request_management.menu_development_request_categories_action", "Tags", config_menu, 30),
            ("dev_request_management.menu_development_request_followups_action", "Follow-up Log", config_menu, 40),
            ("dev_request_management.menu_ui_appearance_settings_action", "Appearance Settings", config_menu, 50),
        ]:
            self._ensure_xmlid_binding(
                xmlid,
                "ir.ui.menu",
                lambda current_name=name, parent_id=parent.id: self.env["ir.ui.menu"].sudo().search(
                    [("name", "=", current_name), ("parent_id", "=", parent_id)],
                    limit=1,
                ),
                {"name": name, "parent_id": parent.id, "sequence": sequence},
                noupdate=False,
            )

    @api.model
    def _fix_broken_actions(self):
        for action_xmlid, fallback_view_xmlid, fallback_search_xmlid in [
            (
                "dev_request_management.action_development_request",
                False,
                "dev_request_management.view_development_request_search",
            ),
            (
                "dev_request_management.action_development_request_board",
                "dev_request_management.view_development_request_board_kanban",
                "dev_request_management.view_development_request_search",
            ),
            (
                "dev_request_management.action_development_request_reporting",
                False,
                "dev_request_management.view_development_request_search",
            ),
            (
                "dev_request_management.action_ui_appearance_settings",
                False,
                False,
            ),
        ]:
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            if not action or action._name != "ir.actions.act_window":
                continue
            values = {}
            if "res_id" in action._fields and action.res_id and action.res_model in self.env:
                if not self.env[action.res_model].sudo().browse(action.res_id).exists():
                    values["res_id"] = False
            if action.view_id and not action.view_id.exists():
                fallback_view = self.env.ref(fallback_view_xmlid, raise_if_not_found=False) if fallback_view_xmlid else False
                values["view_id"] = fallback_view.id if fallback_view else False
            if action.search_view_id and not action.search_view_id.exists():
                fallback_search = self.env.ref(fallback_search_xmlid, raise_if_not_found=False) if fallback_search_xmlid else False
                values["search_view_id"] = fallback_search.id if fallback_search else False
            if values:
                action.sudo().write(values)

    @api.model
    def _is_valid_menu_action(self, menu):
        action_ref = menu.action
        if not action_ref:
            return False
        return bool(action_ref.exists())

    @api.model
    def _fix_broken_menu_actions(self):
        mapping = {
            "dev_request_management.menu_development_request_requests": "dev_request_management.action_development_request",
            "dev_request_management.menu_development_request_board": "dev_request_management.action_development_request_board",
            "dev_request_management.menu_development_request_reporting": "dev_request_management.action_development_request_reporting",
            "dev_request_management.menu_development_request_stages_action": "dev_request_management.action_development_request_stages",
            "dev_request_management.menu_development_request_teams_action": "dev_request_management.action_development_request_teams",
            "dev_request_management.menu_development_request_categories_action": "dev_request_management.action_development_request_categories",
            "dev_request_management.menu_development_request_followups_action": "dev_request_management.action_development_request_followups",
            "dev_request_management.menu_ui_appearance_settings_action": "dev_request_management.action_ui_appearance_settings",
        }
        for menu_xmlid, action_xmlid in mapping.items():
            menu = self.env.ref(menu_xmlid, raise_if_not_found=False)
            action = self.env.ref(action_xmlid, raise_if_not_found=False)
            if not menu or not action:
                continue
            if not self._is_valid_menu_action(menu):
                menu.sudo().write({"action": f"{action._name},{action.id}"})

    @api.model
    def _fix_global_broken_window_actions(self):
        fixed = []
        actions = self.env["ir.actions.act_window"].sudo().search([("res_id", "!=", False)])
        for action in actions:
            model_name = action.res_model
            broken = False
            if not model_name or model_name not in self.env:
                broken = True
            elif not self.env[model_name].sudo().browse(action.res_id).exists():
                broken = True
            if broken:
                fixed.append(
                    {
                        "id": action.id,
                        "name": action.name,
                        "model": model_name,
                        "broken_res_id": action.res_id,
                    }
                )
                action.write({"res_id": False})
        for item in fixed:
            _logger.warning(
                "Cleared broken ir.actions.act_window res_id: id=%s name=%s model=%s broken_res_id=%s",
                item["id"],
                item["name"],
                item["model"],
                item["broken_res_id"],
            )
        return fixed
