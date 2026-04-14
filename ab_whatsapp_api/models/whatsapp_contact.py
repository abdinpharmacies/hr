from odoo import fields, models
from odoo.tools.translate import _


class AbWhatsAppContact(models.Model):
    _name = "ab.whatsapp.contact"
    _description = "AB WhatsApp Contact"
    _order = "last_message_at desc, id desc"

    name = fields.Char()
    wa_id = fields.Char(required=True, index=True)
    preferred_phone_number_id = fields.Char(index=True)
    last_message_at = fields.Datetime(index=True)
    last_message_preview = fields.Char()

    message_ids = fields.One2many(
        comodel_name="ab.whatsapp.message",
        inverse_name="contact_id",
        string="Messages",
    )

    _uniq_wa_id = models.Constraint(
        "UNIQUE(wa_id)",
        _("WhatsApp number must be unique."),
    )

