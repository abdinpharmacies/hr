from odoo import fields, models
from odoo.tools.translate import _


class AbWhatsAppTemplate(models.Model):
    _name = "ab.whatsapp.template"
    _description = "AB WhatsApp Template"
    _order = "name asc, language asc, id desc"

    name = fields.Char(required=True, index=True)
    template_uid = fields.Char(required=True, index=True)
    language = fields.Char(required=True, index=True)
    status = fields.Char(index=True)
    category = fields.Char(index=True)
    quality_score = fields.Char()
    body_preview = fields.Text()
    has_placeholders = fields.Boolean(default=False, index=True)
    components_payload = fields.Json()
    raw_payload = fields.Json()
    last_synced_at = fields.Datetime(index=True)

    _uniq_template_uid = models.Constraint(
        "UNIQUE(template_uid)",
        _("Template id must be unique."),
    )
