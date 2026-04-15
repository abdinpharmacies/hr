from odoo import fields, models


class AbResGroups(models.Model):
    _inherit = "res.groups"

    ab_security_managed = fields.Boolean(
        string="Managed By Smart Security Manager",
        default=False,
        copy=False,
    )
    ab_security_role_id = fields.Many2one(
        "ab_security_role",
        string="Smart Security Role",
        copy=False,
        ondelete="set null",
    )
