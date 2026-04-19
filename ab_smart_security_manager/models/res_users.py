from odoo import Command, api, fields, models


class AbResUsers(models.Model):
    _inherit = "res.users"

    ab_role_ids = fields.Many2many(
        "ab_security_role",
        "ab_security_role_user_rel",
        "user_id",
        "role_id",
        string="Smart Security Roles",
    )

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._sync_ab_role_group_membership()
        return users

    def write(self, vals):
        res = super().write(vals)
        if "ab_role_ids" in vals and not self.env.context.get("ab_security_skip_role_sync"):
            self._sync_ab_role_group_membership()
        return res

    def _sync_ab_role_group_membership(self):
        if self.env.context.get("ab_security_skip_role_sync"):
            return
        for user in self:
            target_groups = user.ab_role_ids.mapped("group_id")
            managed_groups_to_remove = user.group_ids.filtered(
                lambda group: group.ab_security_managed and group not in target_groups
            )
            commands = [Command.link(group.id) for group in target_groups if group not in user.group_ids]
            commands += [Command.unlink(group.id) for group in managed_groups_to_remove]
            if commands:
                user.with_context(ab_security_skip_role_sync=True).sudo().write({"group_ids": commands})
