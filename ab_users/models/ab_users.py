from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbUsers(models.Model):
    _name = "ab_users"
    _description = "Odoo User Sync Placeholder"
    _order = "id"

    name = fields.Char()
    login = fields.Char(index=True)
    active = fields.Boolean(default=True, index=True)

    @api.model
    def current_placeholder(self):
        user = self.env.user
        return self.sudo().search(
            [
                "|",
                ("id", "=", user.id),
                ("login", "=", user.login or ""),
            ],
            limit=1,
        )

    @api.model
    def current_placeholder_id(self):
        return self.current_placeholder().id or False

    def unlink(self):
        raise UserError(_("Synchronized user placeholders cannot be deleted."))
