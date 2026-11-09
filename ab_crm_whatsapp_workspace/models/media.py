import base64
import binascii

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.ab_crm_messaging.models.media import validate_media

DOCUMENT_MIMES = {
    'text/plain',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}


def validate_whatsapp_attachment(attachment, translate):
    if not isinstance(attachment, dict):
        raise ValidationError(translate('Invalid media content or size.'))
    mime = attachment.get('mimetype')
    if mime not in DOCUMENT_MIMES | {'video/mp4', 'video/3gpp'}:
        return validate_media(attachment, attachment.get('data'), translate=translate)
    kind = 'video' if mime.startswith('video/') else 'document'
    size = attachment.get('size')
    encoded = attachment.get('data')
    limit = (16 if kind == 'video' else 20) * 1024 * 1024
    if (
        attachment.keys() - {'kind', 'name', 'mimetype', 'size', 'duration', 'data'}
        or attachment.get('kind') != kind
        or type(size) is not int
        or not 0 < size <= limit
        or not isinstance(encoded, (str, bytes))
        or len(encoded) > limit * 4 // 3 + 8
        or not isinstance(attachment.get('name'), str)
        or not 1 <= len(attachment['name']) <= 255
    ):
        raise ValidationError(translate('Invalid media content or size.'))
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != size:
            raise ValueError()
        if kind == 'video' and raw[4:8] != b'ftyp':
            raise ValueError()
        if mime.startswith('application/vnd.openxmlformats') and not raw.startswith(
            b'PK'
        ):
            raise ValueError()
        if mime in (
            'application/vnd.ms-excel',
            'application/vnd.ms-powerpoint',
        ) and not raw.startswith(b'\xd0\xcf\x11\xe0'):
            raise ValueError()
        if mime == 'text/plain':
            raw.decode('utf-8')
    except (ValueError, binascii.Error, UnicodeError):
        raise ValidationError(translate('Invalid media content or size.')) from None
    return raw


def preserve_video_history(records):
    if records:
        raise UserError(_('Integrated WhatsApp history is immutable.'))


class Media(models.Model):
    _inherit = 'ab_crm_message_media'

    kind = fields.Selection(
        selection_add=[('video', 'Video')], ondelete={'video': preserve_video_history}
    )
