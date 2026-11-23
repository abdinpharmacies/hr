import hashlib
import json
from pathlib import PurePath

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from ..media_protocol import validate_attachments


class Endpoint(models.Model):
    _inherit = 'ab_storefront_callcenter_endpoint'

    media_enabled = fields.Boolean(string='Enable v4 website media', default=False)


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    ab_website_media = fields.Json(copy=False)

    def _ab_protect_media(self):
        captured = self.env['ab_storefront_callcenter_chat_event'].sudo().search_count([
            ('message_id.attachment_ids', 'in', self.ids),
        ], limit=1) or self.env['ab_storefront_callcenter_chat_reply'].sudo().search_count([
            ('message_id.attachment_ids', 'in', self.ids),
        ], limit=1)
        if captured:
            raise AccessError(_('Website evidence is immutable.'))

    def write(self, values):
        if {'raw', 'datas', 'name', 'mimetype', 'public', 'ab_website_media'} & values.keys():
            self._ab_protect_media()
        return super().write(values)

    def unlink(self):
        self._ab_protect_media()
        return super().unlink()

    @api.model
    def _ab_media_descriptors(self, attachments):
        result = []
        for attachment in attachments.sudo():
            mime = attachment.mimetype or 'application/octet-stream'
            voice = 'voice_ids' in attachment._fields and bool(attachment.voice_ids)
            kind = 'voice' if voice else next((kind for kind in ('image', 'audio', 'video') if mime.startswith(kind + '/')), 'document')
            if kind == 'image' and mime not in ('image/jpeg', 'image/png', 'image/gif', 'image/webp'):
                kind = 'document'
            raw = attachment.raw or b''
            result.append({'id': str(attachment.id), 'name': PurePath(attachment.name.replace('\\', '/')).name[:255],
                'mimetype': mime, 'size': len(raw), 'digest': hashlib.sha256(raw).hexdigest(),
                'kind': (attachment.ab_website_media or {}).get('kind', kind),
                'duration': (attachment.ab_website_media or {}).get('duration', 0)})
        try:
            return validate_attachments(result)
        except ValueError:
            raise ValidationError(_('Invalid website media.')) from None

    @api.model
    def _ab_owned_files(self, target, descriptors):
        if not isinstance(descriptors, list) or len(descriptors) > 4:
            raise ValidationError(_('Invalid website media.'))
        attachments = self.browse()
        for item in descriptors:
            if (not isinstance(item, dict) or set(item) != {'id', 'token'} or type(item['id']) is not int
                    or (item['token'] is not None and (not isinstance(item['token'], str) or len(item['token']) > 1024))):
                raise AccessError(_('Invalid website media.'))
            attachment = self.browse(item['id']).exists()
            if (not attachment or not attachment._has_attachments_ownership([item['token']])
                    or (attachment.sudo().res_model, attachment.sudo().res_id) not in (
                        ('mail.compose.message', 0), (target._name, target.id))):
                raise AccessError(_('Invalid website media.'))
            attachments |= attachment
        if len(attachments) != len(descriptors):
            raise ValidationError(_('Invalid website media.'))
        self._ab_media_descriptors(attachments)
        company = target.ab_callcenter_endpoint_id.company_id
        attachments.sudo().filtered(lambda file: file.company_id != company or file.public).write({
            'company_id': company.id, 'public': False,
        })
        return attachments.sudo()

    @api.model
    def _ab_exchange_key(self, endpoint, kind, destination, token, item):
        key = json.dumps([endpoint.id, kind, destination, token, item], sort_keys=True)
        return 'website-v4:' + hashlib.sha256(key.encode()).hexdigest()

    @api.model
    def _ab_exchange_files(self, endpoint, kind, destination, token, descriptors):
        files = self.sudo().browse()
        for item in descriptors:
            attachment = self.sudo().search([
                ('res_model', '=', endpoint._name), ('res_id', '=', endpoint.id),
                ('description', '=', self._ab_exchange_key(endpoint, kind, destination, token, item)),
            ], limit=1)
            if not attachment:
                raise ValidationError(_('Website media is unavailable.'))
            files |= attachment
        return files


class MediaExchange(models.AbstractModel):
    _inherit = 'ab_storefront_callcenter_api'

    @api.model
    def capabilities_v4(self, source):
        endpoint = self._endpoint(source)
        return {'version': 4 if endpoint.media_enabled else 3}

    @api.model
    def fetch_v4(self, source):
        endpoint = self._endpoint(source)
        if not endpoint.media_enabled:
            raise AccessError(_('Website media is unavailable.'))
        return self._fetch_chat_events(endpoint, 4)

    @api.model
    def acknowledge_v4(self, source, event_uuid, fingerprint):
        return self.acknowledge_v2(source, event_uuid, fingerprint)

    @api.model
    def receive_v4(self, source, destination_kind, destination_uuid, token, body, attachments):
        endpoint = self._endpoint(source)
        if not endpoint.media_enabled:
            raise AccessError(_('Website media is unavailable.'))
        return self._receive_reply(source, destination_kind, destination_uuid, token, body, attachments)
