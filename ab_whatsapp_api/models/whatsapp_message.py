from odoo import fields, models


class AbWhatsAppMessage(models.Model):
    _name = "ab.whatsapp.message"
    _description = "AB WhatsApp Message"
    _order = "id desc"

    direction = fields.Selection(
        selection=[
            ("incoming", "Incoming"),
            ("outgoing", "Outgoing"),
        ],
        required=True,
        index=True,
    )
    contact_id = fields.Many2one(
        comodel_name="ab.whatsapp.contact",
        required=True,
        ondelete="cascade",
        index=True,
    )
    wa_id = fields.Char(
        related="contact_id.wa_id",
        store=True,
        index=True,
        readonly=True,
    )
    phone_number_id = fields.Char(index=True)
    message_type = fields.Char(required=True, default="text", index=True)
    text_content = fields.Text()
    media_id = fields.Char()
    media_mime_type = fields.Char()
    media_filename = fields.Char()
    status = fields.Char(index=True)
    meta_message_id = fields.Char(index=True)
    reply_to_meta_message_id = fields.Char(index=True)
    reaction_target_meta_message_id = fields.Char(index=True)
    is_deleted = fields.Boolean(default=False, index=True)
    edited_from_text = fields.Text()
    edited_at = fields.Datetime()
    raw_payload = fields.Json(groups="base.group_system")
