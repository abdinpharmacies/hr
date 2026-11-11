import base64
import binascii
import hashlib
import hmac
from io import BytesIO

from PIL import Image

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


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _validate_incoming_media(self, account, metadata, data=None):
        if account.provider != 'whatsapp':
            return super()._validate_incoming_media(account, metadata, data)
        if not isinstance(metadata, dict) or metadata.keys() - {
            'kind', 'name', 'mimetype', 'size', 'duration', 'file_id', 'data',
            'sha256', 'sticker', 'animated',
        }:
            raise ValidationError(_('Invalid media.'))
        clean = {key: value for key, value in metadata.items()
                 if key not in ('sha256', 'sticker', 'animated', 'file_id')}
        kind, mime = clean.get('kind'), clean.get('mimetype')
        size, duration = clean.get('size', 0), clean.get('duration', 0)
        limit = (5 if kind == 'image' else 16 if kind in ('audio', 'voice', 'video') else 20) * 1024 * 1024
        if metadata.get('sticker'):
            limit = (500 if metadata.get('animated') else 100) * 1024
        if (type(size) is not int or not 0 <= size <= limit
                or type(duration) not in (int, float) or not 0 <= duration <= 300
                or not isinstance(clean.get('name'), str) or not 1 <= len(clean['name']) <= 255
                or metadata.get('sticker') and mime != 'image/webp'):
            raise ValidationError(_('Invalid media type, size or recording duration.'))
        if data is not None:
            try:
                raw = base64.b64decode(data, validate=True)
                digest = metadata.get('sha256')
                if digest and (not isinstance(digest, str) or not any(hmac.compare_digest(value, digest) for value in (
                        hashlib.sha256(raw).hexdigest(), base64.b64encode(hashlib.sha256(raw).digest()).decode()))):
                    raise ValueError()
                if kind == 'image' and mime != 'image/webp':
                    with Image.open(BytesIO(raw)) as image:
                        expected = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}
                        if image.format != expected.get(mime) or image.width * image.height > 40000000:
                            raise ValueError()
                        image.verify()
                if mime == 'image/webp' and (len(raw) < 16 or int.from_bytes(raw[4:8], 'little') + 8 != len(raw)):
                    raise ValueError()
            except (ValueError, OSError, binascii.Error, Image.DecompressionBombError):
                raise ValidationError(_('Invalid media content or size.')) from None
        extra = mime in DOCUMENT_MIMES | {'video/mp4', 'video/3gpp', 'audio/aac', 'audio/amr'}
        if extra:
            expected = 'video' if mime.startswith('video/') else 'audio' if mime.startswith('audio/') else 'document'
            if kind != expected:
                raise ValidationError(_('Media content does not match its declared type.'))
            if data is None:
                return
            clean['data'] = data
            if mime in ('audio/aac', 'audio/amr'):
                try:
                    raw = base64.b64decode(data, validate=True)
                    if len(raw) != size or not raw or not (
                        raw.startswith(b'#!AMR') if mime == 'audio/amr' else raw[:1] == b'\xff'
                    ):
                        raise ValueError()
                    return raw
                except (ValueError, binascii.Error):
                    raise ValidationError(_('Invalid media content or size.')) from None
            return validate_whatsapp_attachment(clean, self.env._)
        return validate_media(clean, data, translate=self.env._)
