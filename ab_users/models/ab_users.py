from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbUsers(models.Model):
    _name = "ab_users"
    _description = "Odoo User Sync Placeholder"
    _order = "id"

    name = fields.Char(default=lambda self: _("Sync User Placeholder"))
    login = fields.Char(index=True)
    active = fields.Boolean(default=True, index=True)

    def unlink(self):
        raise UserError(_("Synchronized user placeholders cannot be deleted."))

