from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import parse_version
from odoo.addons.ab_crm_core.models.core import _INTERNAL

from .messaging import _EDIT, _MUTATION
from .media import validate_media


class Message(models.Model):
    _inherit = 'ab_crm_message'

    provider_edit_content = fields.Json(readonly=True, copy=False)
    provider_edit_history = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, values_list):
        protected = {'provider_edit_content', 'provider_edit_history'}
        if any(protected & values.keys() for values in values_list) or any(
            'default_' + key in self.env.context for key in protected
        ):
            raise AccessError(_('Message delivery evidence is managed by the gateway.'))
        return super().create(values_list)

    def write(self, values):
        if {'provider_edit_content', 'provider_edit_history'} & values.keys() and not _EDIT.get():
            raise AccessError(_('Message delivery evidence is managed by the gateway.'))
        if _EDIT.get() and any(record.direction != 'in' for record in self):
            raise AccessError(_('Message delivery evidence is managed by the gateway.'))
        return super().write(values)

    def _current_media(self):
        self.ensure_one()
        if self.provider_edit_content:
            return self.media_ids.filtered(lambda media: media.id == self.provider_edit_content.get('media_id'))
        return self.media_ids


class Event(models.Model):
    _inherit = 'ab_crm_messaging_event'

    media_id = fields.Many2one('ab_crm_message_media', readonly=True, ondelete='restrict')
    edit_payload = fields.Json(readonly=True)


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    @api.model
    def get_capabilities(self, account_code, provider_account):
        self._account(account_code, provider_account)
        installed = self.env.ref('base.module_ab_crm_messaging').sudo().latest_version
        return {'message_edits': parse_version(installed or '0') >= parse_version('19.0.1.7.0')}

    def _receive_edit(self, account, event, timestamp, location, fingerprint, clean_context):
        edit = event['edit']
        if (
            account.provider != 'telegram'
            or not isinstance(edit, dict)
            or set(edit) != {'reference', 'date', 'sequence'}
            or not isinstance(edit['reference'], str)
            or not edit['reference'].isascii()
            or not edit['reference'].isdecimal()
            or not isinstance(edit['date'], str)
            or len(edit['reference']) > 256
            or type(edit['sequence']) is not int
            or not 0 <= edit['sequence'] < 2 ** 63
            or event['id'] != 'edit:' + str(edit['sequence'])
            or event.get('contact')
            or 'reaction' in event
        ):
            raise ValidationError(_('Invalid incoming messaging event.'))
        try:
            edited_at = fields.Datetime.to_datetime(edit['date'])
        except (ValueError, TypeError):
            edited_at = None
        if not edited_at or edited_at < timestamp or edited_at > fields.Datetime.now() + timedelta(minutes=5):
            raise ValidationError(_('Invalid incoming messaging event.'))
        metadata = event.get('media')
        if metadata:
            validate_media(metadata, translate=self.env._)
            if not isinstance(metadata.get('file_id'), str) or not 1 <= len(metadata['file_id']) <= 512:
                raise ValidationError(_('Invalid media.'))
        ledger = self.env['ab_crm_messaging_event'].sudo().with_context(clean_context)
        existing = ledger.search([('account_id', '=', account.id), ('event_key', '=', event['id'])], limit=1)
        if existing:
            if existing.fingerprint != fingerprint:
                raise ValidationError(_('An event identity cannot be reused with different content.'))
            return {'message_id': existing.message_id.id, 'media_required': bool(existing.media_id)}
        messages = ledger.search([
            ('account_id', '=', account.id),
            ('event_key', 'not =like', 'reaction:%'),
            ('edit_payload', '=', False),
            ('message_id.conversation_id.channel_id', '=', account.channel_id.id),
            ('message_id.conversation_id.external_key', '=', event['sender']),
            ('message_id.branch_id', '=', account.branch_id.id),
            ('message_id.company_id', '=', account.company_id.id),
            ('message_id.direction', '=', 'in'),
            ('message_id.provider_reference', '=', edit['reference']),
        ], limit=2).message_id
        if len(messages) > 1:
            raise ValidationError(_('Invalid incoming messaging event.'))
        message = messages
        media = self.env['ab_crm_message_media']
        mutation, internal, editing = _MUTATION.set(True), _INTERNAL.set(True), _EDIT.set(True)
        try:
            if message:
                message.lock_for_update()
                message.invalidate_recordset()
                previous = message.provider_edit_content or {}
                newer = not previous or (edit['date'], edit['sequence']) > (previous['date'], previous['sequence'])
                if newer:
                    original_media = message._current_media()
                    if not previous and len(original_media) == 1:
                        ledger.search([('account_id', '=', account.id), ('message_id', '=', message.id), ('media_id', '=', False), ('edit_payload', '=', False)]).write({'media_id': original_media.id})
                    if metadata:
                        media = self.env['ab_crm_message_media'].sudo().with_context(clean_context).create({
                            'message_id': message.id, 'branch_id': message.branch_id.id,
                            'company_id': message.company_id.id, 'name': metadata['name'],
                            'kind': metadata['kind'], 'mimetype': metadata['mimetype'],
                            'size': metadata['size'], 'duration': metadata.get('duration', 0),
                            'provider_file_id': metadata['file_id'],
                        })
                    body = _('Unsupported attachment received. Staff review is required.') if event['unsupported'] else event['body']
                    if location:
                        location = dict(location, timestamp=fields.Datetime.to_string(edited_at))
                        body = '\n'.join(filter(None, [
                            _('Location snapshot') if location['is_live_snapshot'] else _('Location'),
                            location['name'], location['address'],
                            f"{location['latitude']}, {location['longitude']}",
                        ]))
                    history = message.provider_edit_history or [{
                        'body': message.body, 'location': message.location_snapshot,
                        'media_ids': original_media.ids,
                    }]
                    content = dict(edit, event_id=event['id'], body=body, location=location or False,
                                   media_id=media.id, source_digest=event['source_digest'])
                    history = history + [dict(content, actor=self.env.uid, received_at=fields.Datetime.to_string(fields.Datetime.now()))]
                    message.write({'body': body, 'provider_edit_content': content, 'provider_edit_history': history})
            ledger.create({
                'account_id': account.id, 'event_key': event['id'], 'fingerprint': fingerprint,
                'provider_timestamp': edited_at, 'message_id': message.id, 'media_id': media.id,
                'edit_payload': event, 'branch_id': account.branch_id.id, 'company_id': account.company_id.id,
            })
        finally:
            _EDIT.reset(editing)
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
        return {'message_id': message.id, 'media_required': bool(media)}
