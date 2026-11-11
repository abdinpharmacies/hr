# Copyright (C) 2023-TODAY Cybrosys Technologies (https://www.cybrosys.com).
# Original author: Yadhukrishnan K. Odoo 19 adaptation: emadco88.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).
from odoo import api, fields, models
from odoo.exceptions import AccessError


class ResUsers(models.Model):
    _inherit = 'res.users'

    enable_idle = fields.Boolean(string='Enable Idle Logout', default=True)
    idle_time = fields.Integer(string='Idle Timeout (Minutes)', default=10)
    _idle_time_positive = models.Constraint('CHECK(idle_time >= 1)', 'Idle timeout must be at least one minute.')

    def _check_idle_policy_access(self, values):
        if {'enable_idle', 'idle_time'} & values.keys() and not (
            self.env.su or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(self.env._('Only administrators can change idle logout settings.'))

    @api.model_create_multi
    def create(self, vals_list):
        for values in vals_list:
            self._check_idle_policy_access(values)
        return super().create(vals_list)

    def write(self, values):
        self._check_idle_policy_access(values)
        return super().write(values)
