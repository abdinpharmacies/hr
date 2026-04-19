from odoo import fields, models


class AbIrModelAccess(models.Model):
    _inherit = "ir.model.access"

    ab_security_managed = fields.Boolean(
        string="Managed By Smart Security Manager",
        default=False,
        copy=False,
    )
    ab_security_model_access_id = fields.Many2one(
        "ab_security_model_access",
        string="Security Model Access Source",
        copy=False,
        ondelete="set null",
    )
