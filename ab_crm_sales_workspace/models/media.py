import base64
import binascii
import math

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.ab_crm_messaging.models.media import validate_media


def validate_workspace_attachment(attachment, translate):
    if not isinstance(attachment, dict):
        raise ValidationError(translate('Invalid media content or size.'))
    if attachment.get('kind') != 'video':
        return validate_media(attachment, attachment.get('data'), translate=translate)
    size = attachment.get('size')
    encoded = attachment.get('data')
    duration = attachment.get('duration', 0)
    limit = 16 * 1024 * 1024
    if (
        attachment.keys() - {'kind', 'name', 'mimetype', 'size', 'duration', 'data'}
        or attachment.get('mimetype') != 'video/mp4'
        or type(size) is not int
        or not 0 < size <= limit
        or not isinstance(encoded, (str, bytes))
        or len(encoded) > limit * 4 // 3 + 8
        or not isinstance(attachment.get('name'), str)
        or not 1 <= len(attachment['name']) <= 255
        or type(duration) not in (int, float)
        or not math.isfinite(duration)
        or not 0 <= duration <= 300
    ):
        raise ValidationError(translate('Invalid media content or size.'))
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) != size or raw[4:8] != b'ftyp':
            raise ValueError()
    except (ValueError, binascii.Error):
        raise ValidationError(translate('Invalid media content or size.')) from None
    return raw


def preserve_video_history(records):
    if records:
        raise UserError(_('Message history is immutable.'))


class Media(models.Model):
    _inherit = 'ab_crm_message_media'

    kind = fields.Selection(
        selection_add=[('video', 'Video')], ondelete={'video': preserve_video_history}
    )
