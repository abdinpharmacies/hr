from odoo import fields, models


class WhatsAppIdentity(models.Model):
    _inherit = "ab_storefront_auth_identity"

    kind = fields.Selection(selection_add=[("whatsapp", "WhatsApp")], ondelete={"whatsapp": "cascade"})
