# -*- coding: utf-8 -*-

from odoo import Command, api, models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _ab_request_management_sync_groups(self):
        if self.env.context.get("skip_ab_request_group_sync"):
            return

        request_user = self.env.ref(
            "ab_request_management.group_ab_request_management_user",
            raise_if_not_found=False,
        )
        request_manager = self.env.ref(
            "ab_request_management.group_ab_request_management_manager",
            raise_if_not_found=False,
        )
        base_group_user = self.env.ref("base.group_user", raise_if_not_found=False)
        manager_sources = [
            self.env.ref("ab_hr.group_ab_hr_co", raise_if_not_found=False),
            self.env.ref("ab_hr.group_ab_hr_manager", raise_if_not_found=False),
        ]

        if not request_user or not base_group_user:
            return

        requester_users = self.filtered(
            lambda user: base_group_user in user.group_ids and request_user not in user.group_ids
        )
        if requester_users:
            requester_users.with_context(skip_ab_request_group_sync=True).sudo().write(
                {"group_ids": [Command.link(request_user.id)]}
            )

        if request_manager:
            manager_users = self.filtered(
                lambda user: any(group and group in user.group_ids for group in manager_sources)
                and request_manager not in user.group_ids
            )
            if manager_users:
                manager_users.with_context(skip_ab_request_group_sync=True).sudo().write(
                    {"group_ids": [Command.link(request_manager.id)]}
                )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._ab_request_management_sync_groups()
        return users

    def write(self, vals):
        res = super().write(vals)
        self._ab_request_management_sync_groups()
        return res
