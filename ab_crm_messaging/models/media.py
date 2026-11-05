import base64
import binascii
import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL

MIMES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'audio/ogg',
    'audio/mpeg',
    'audio/mp4',
    'audio/webm',
    'video/webm',
}


def validate_media(metadata, data=None, translate=_):
    _ = translate
    if not isinstance(metadata, dict) or metadata.keys() - {
        'kind',
        'name',
        'mimetype',
        'size',
        'duration',
        'file_id',
        'data',
    }:
        raise ValidationError(_('Invalid media.'))
    kind = metadata.get('kind')
    size = metadata.get('size', 0)
    duration = metadata.get('duration', 0)
    if (
        kind not in ('image', 'document', 'audio', 'voice')
        or type(size) is not int
        or size < 0
        or metadata.get('mimetype') not in MIMES
        or not isinstance(metadata.get('name'), str)
        or not 1 <= len(metadata['name']) <= 255
        or not isinstance(duration, (float, int))
        or not math.isfinite(duration)
        or not 0 <= duration <= 300
    ):
        raise ValidationError(_('Invalid media type, size or recording duration.'))
    mime = metadata['mimetype']
    if (
        (kind == 'document' and not mime.startswith('application/'))
        or (
            kind in ('audio', 'voice')
            and not (mime.startswith('audio/') or mime == 'video/webm')
        )
        or (kind == 'image' and not mime.startswith('image/'))
    ):
        raise ValidationError(_('Media content does not match its declared type.'))
    limit = (10 if kind == 'image' else 20) * 1024 * 1024
    if size > limit:
        raise ValidationError(
            _(
                'Media exceeds the 20 MB file, 10 MB image or five-minute recording limit.'
            )
        )
    if data is not None:
        try:
            if not isinstance(data, (str, bytes)) or len(data) > (limit * 4 // 3 + 8):
                raise ValueError()
            raw = base64.b64decode(data, validate=True)
            if not raw or len(raw) > limit or len(raw) != size:
                raise ValueError()
        except (ValueError, binascii.Error):
            raise ValidationError(_('Invalid media content or size.')) from None
        mime = metadata['mimetype']
        valid = (
            (mime == 'image/jpeg' and raw.startswith(b'\xff\xd8\xff'))
            or (mime == 'image/png' and raw.startswith(b'\x89PNG\r\n\x1a\n'))
            or (
                mime == 'image/webp'
                and raw.startswith(b'RIFF')
                and raw[8:12] == b'WEBP'
            )
            or (mime == 'application/pdf' and raw.startswith(b'%PDF-'))
            or (mime == 'application/msword' and raw.startswith(b'\xd0\xcf\x11\xe0'))
            or (mime.endswith('wordprocessingml.document') and raw.startswith(b'PK'))
            or (mime == 'audio/ogg' and raw.startswith(b'OggS'))
            or (
                mime in ('audio/webm', 'video/webm')
                and raw.startswith(b'\x1a\x45\xdf\xa3')
            )
            or (mime == 'audio/mp4' and raw[4:8] == b'ftyp')
            or (mime == 'audio/mpeg' and (raw.startswith(b'ID3') or raw[:1] == b'\xff'))
        )
        if not valid or (kind == 'image') != mime.startswith('image/'):
            raise ValidationError(_('Media content does not match its declared type.'))
        return raw


class Media(models.Model):
    _name = 'ab_crm_message_media'
    _inherit = 'ab_crm_scoped'
    _description = 'Private Message Media'

    message_id = fields.Many2one('ab_crm_message', required=True, ondelete='restrict')
    name = fields.Char(required=True)
    kind = fields.Selection(
        [(k, k.title()) for k in ('image', 'document', 'audio', 'voice')], required=True
    )
    mimetype = fields.Char(required=True)
    size = fields.Integer(required=True)
    duration = fields.Float()
    provider_file_id = fields.Char()
    data = fields.Binary(attachment=False)
    state = fields.Selection(
        [
            ('pending', 'Pending download'),
            ('ready', 'Ready'),
            ('failed', 'Download failed'),
        ],
        default='pending',
        required=True,
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get():
            raise AccessError(_('Media is managed by the conversation workflow.'))
        return super().create(values_list)

    def write(self, values):
        if not _INTERNAL.get():
            raise AccessError(_('Media is managed by the conversation workflow.'))
        return super().write(values)

    def download(self):
        self.ensure_one()
        self._authorize('read')
        conversation = self.message_id.conversation_id
        if hasattr(conversation, '_workspace_scope'):
            conversation._workspace_scope()
        if self.state != 'ready':
            raise ValidationError(_('Media is not available yet.'))
        return {
            'data': self.data.decode() if isinstance(self.data, bytes) else self.data,
            'name': self.name,
            'mimetype': self.mimetype,
            'kind': self.kind,
        }


class Message(models.Model):
    _inherit = 'ab_crm_message'

    media_ids = fields.One2many('ab_crm_message_media', 'message_id', readonly=True)
    reply_reference = fields.Char(readonly=True)
    reaction = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get() and any(
            {'media_ids', 'reply_reference', 'reaction'} & values.keys()
            for values in values_list
        ):
            raise AccessError(_('Media is managed by the conversation workflow.'))
        if not _INTERNAL.get():
            values_list = [
                dict(values, reply_reference=False, reaction=False, media_ids=[])
                for values in values_list
            ]
        return super().create(values_list)

    def _outgoing_extra(self):
        self.ensure_one()
        return {
            'reply_reference': self.reply_reference or '',
            'reaction': self.reaction or '',
            'media': [
                {
                    'kind': m.kind,
                    'name': m.name,
                    'mimetype': m.mimetype,
                    'size': m.size,
                    'duration': m.duration,
                    'data': m.data.decode() if isinstance(m.data, bytes) else m.data,
                }
                for m in self.media_ids
            ],
        }


class Operation(models.Model):
    _inherit = 'ab_crm_messaging_operation'

    content = fields.Json(readonly=True)


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _receive_event_extra(self, account, event, message):
        result = super()._receive_event_extra(account, event, message)
        reference = event.get('reply_reference', '')
        if not isinstance(reference, str) or len(reference) > 256:
            raise ValidationError(_('Invalid incoming messaging event.'))
        if reference:
            message._internal_write({'reply_reference': reference})
        reaction = event.get('reaction')
        if reaction is not None:
            if not isinstance(reaction, str) or len(reaction) > 64:
                raise ValidationError(_('Invalid incoming messaging event.'))
            message._internal_write({'reaction': reaction})
        metadata = event.get('media')
        if metadata:
            validate_media(metadata, translate=self.env._)
            if (
                not isinstance(metadata.get('file_id'), str)
                or not 1 <= len(metadata['file_id']) <= 512
            ):
                raise ValidationError(_('Invalid media.'))
            self.env['ab_crm_message_media'].sudo().create(
                {
                    'message_id': message.id,
                    'branch_id': message.branch_id.id,
                    'company_id': message.company_id.id,
                    'name': metadata['name'],
                    'kind': metadata['kind'],
                    'mimetype': metadata['mimetype'],
                    'size': metadata['size'],
                    'duration': metadata.get('duration', 0),
                    'provider_file_id': metadata['file_id'],
                }
            )
        return result

    @api.model
    def receive_media(self, account_code, provider_account, event_id, data, failed=''):
        account = self._account(account_code, provider_account)
        event = (
            self.env['ab_crm_messaging_event']
            .sudo()
            .search(
                [
                    ('account_id', '=', account.id),
                    ('event_key', '=', event_id),
                ],
                limit=1,
            )
        )
        media = event.message_id.media_ids
        if (
            len(media) != 1
            or media.company_id != account.company_id
            or media.branch_id != account.branch_id
        ):
            raise AccessError(_('Invalid media.'))
        media.lock_for_update()
        if media.state == 'ready':
            stored = (
                media.data.decode() if isinstance(media.data, bytes) else media.data
            )
            if data and data != stored:
                raise ValidationError(_('Media content cannot be replaced.'))
            return True
        if failed:
            media._internal_write({'state': 'failed'})
            return True
        try:
            size = (
                len(base64.b64decode(data, validate=True))
                if isinstance(data, str) and len(data) <= 28 * 1024 * 1024
                else -1
            )
        except (ValueError, binascii.Error):
            raise ValidationError(_('Invalid media content or size.')) from None
        metadata = {
            'kind': media.kind,
            'name': media.name,
            'mimetype': media.mimetype,
            'size': size,
            'duration': media.duration,
        }
        validate_media(metadata, data, translate=self.env._)
        media._internal_write(
            {'data': data, 'size': metadata['size'], 'state': 'ready'}
        )
        return True
