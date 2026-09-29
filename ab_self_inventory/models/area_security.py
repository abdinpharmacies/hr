from odoo import api, models


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _compute_domain_context_values(self):
        yield from super()._compute_domain_context_values()
        # HR assignments are mutable. Include current branches in the rule-cache
        # key so moving a manager/department cannot retain old branch access.
        # Elevated HR lookups skip this extension, avoiding recursive rule checks.
        if not self.env.su and self.env.user._is_self_inventory_area_reader():
            yield tuple(sorted(self.env.user._get_self_inventory_area_branch_ids()))


class ResGroups(models.Model):
    _inherit = 'res.groups'

    @api.constrains('user_ids', 'implied_ids')
    def _check_self_inventory_area_role_memberships(self):
        # Also cover assignments through the Groups screen and implied roles.
        self.sudo().all_user_ids._check_self_inventory_area_roles()
