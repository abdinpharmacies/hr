from odoo.addons.ab_crm_messaging.models.media import validate_media


def validate_workspace_attachment(attachment, translate):
    return validate_media(attachment, attachment.get('data') if isinstance(attachment, dict) else None, translate=translate)
