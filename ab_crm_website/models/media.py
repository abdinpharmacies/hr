import base64
import hashlib
import json

from uuid import UUID

from odoo import api, models, _
from ..protocol import fingerprint
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION
from odoo.exceptions import AccessError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from ..media_protocol import validate_attachments, check_bytes


def upload_descriptor(attachment):
    if not isinstance(attachment, dict) or set(attachment) - {'name', 'kind', 'mimetype', 'size', 'data', 'duration'}:
        raise ValueError('Invalid website media')
    if not isinstance(attachment.get('data'), str) or len(attachment['data']) > 28 * 1024 * 1024:
        raise ValueError('Invalid website media')
    raw = base64.b64decode(attachment['data'], validate=True)
    descriptor = {key: attachment[key] for key in ('name', 'kind', 'mimetype', 'size')}
    descriptor.update(id=hashlib.sha256(raw).hexdigest(), digest=hashlib.sha256(raw).hexdigest(), duration=attachment.get('duration', 0))
    check_bytes(descriptor, raw)
    return descriptor


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def _website_submission(self, token, body, attachments, reply_id, order_id, session_id):
        if not token:
            return False
        try:
            if str(UUID(token)) != token:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise ValidationError(_('Invalid website reply.')) from None
        account = self.messaging_account_id
        account.lock_for_update()
        evidence = {'conversation': self.id, 'actor': self.env.uid, 'body': body,
            'employee': self._workspace_actor().employee_id.id,
            'attachments': [self._website_validate_upload(item) for item in attachments],
            'reply_id': reply_id, 'order_id': order_id, 'session_id': session_id}
        digest = fingerprint(evidence)
        ledger = self.env['ab_crm_website_chat_event'].sudo()
        previous = ledger.search([('account_id', '=', account.id), ('event_uuid', '=', 'out:' + token)], limit=1)
        if previous:
            if previous.fingerprint != digest:
                raise ValidationError(_('Conflicting website reply.'))
            return {'result': previous.envelope['result']}
        return {'token': token, 'fingerprint': digest}

    def _website_submission_store(self, submission, result, order, session):
        mutation = _MUTATION.set(True)
        try:
            self.env['ab_crm_website_chat_event'].sudo().create({
                'account_id': self.messaging_account_id.id, 'event_uuid': 'out:' + submission['token'],
                'fingerprint': submission['fingerprint'], 'branch_id': self.branch_id.id, 'company_id': self.company_id.id,
                'envelope': {'result': result, 'destination': {'kind': 'order' if order else 'livechat',
                    'uuid': order.order_uuid if order else session.session_uuid}},
            })
        finally:
            _MUTATION.reset(mutation)

    def _website_attachment_payload(self, attachment):
        if isinstance(attachment, dict) and set(attachment) == {'upload_id'}:
            if type(attachment['upload_id']) is not int:
                raise AccessError(_('Invalid website media.'))
            file = self.env['ir.attachment'].sudo().browse(attachment['upload_id']).exists()
            if (not file or file.create_uid.id != self.env.uid or file.res_model != self._name
                    or file.res_id != self.id or file.company_id != self.company_id):
                raise AccessError(_('Invalid website media.'))
            metadata = json.loads(file.description)
            if metadata.pop('employee_id', None) != self._workspace_actor().employee_id.id:
                raise AccessError(_('Invalid website media.'))
            target = metadata.pop('target', None)
            kind, record = self._website_target(target)
            selected = self.env.context.get('ab_website_target')
            if selected and selected != target:
                raise AccessError(_('Invalid website target.'))
            return dict(metadata, data=base64.b64encode(file.raw).decode())
        return attachment

    def _website_validate_upload(self, attachment):
        try:
            return upload_descriptor(self._website_attachment_payload(attachment))
        except (ValueError, TypeError, KeyError):
            raise ValidationError(_('Invalid website media.')) from None

    def _website_selected_target(self, reply_id=False, order_id=False, session_id=False):
        self.ensure_one()
        if not reply_id:
            return self._website_reply_target(order_id, session_id)
        if type(reply_id) is not int:
            raise AccessError(_('Select a message from this conversation.'))
        message = self.env['ab_crm_message'].search([
            ('id', '=', reply_id), ('conversation_id', 'in', self._website_timeline_streams().ids),
            ('direction', '=', 'in'), ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id),
        ], limit=1)
        if not message:
            raise AccessError(_('Select a message from this conversation.'))
        order, session = message.website_order_id, message.website_session_id
        if not order and not session:
            event = self.env['ab_crm_website_event'].search([
                ('account_id', '=', self.messaging_account_id.id), ('event_uuid', '=', message.provider_reference),
            ], limit=1)
            if event and event.envelope.get('kind') == 'order':
                order = self.env['ab_crm_website_order'].search([
                    ('account_id', '=', self.messaging_account_id.id), ('order_uuid', '=', event.order_uuid),
                ], limit=1)
        if (bool(order) == bool(session) or (order_id and order.id != order_id) or (session_id and session.id != session_id)):
            raise AccessError(_('Invalid website order.'))
        return self._website_reply_target(order.id if order else False, session.id if session else False)


class Gateway(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _website_media_key(self, account, event_uuid, item):
        value = json.dumps([account.id, event_uuid, item], sort_keys=True)
        return 'website-v4:' + hashlib.sha256(value.encode()).hexdigest()

    def _website_link_media(self, account, event, message):
        descriptors = validate_attachments(event['attachments'])
        for item in descriptors:
            attachment = self.env['ir.attachment'].sudo().search([
                ('res_model', '=', account._name), ('res_id', '=', account.id),
                ('description', '=', self._website_media_key(account, event['event_uuid'], item)),
            ], limit=1)
            if not attachment:
                raise ValidationError(_('Website media is unavailable.'))
            raw = check_bytes(item, attachment.raw)
            internal = _INTERNAL.set(True)
            try:
                self.env['ab_crm_message_media'].sudo().create({
                    'message_id': message.id, 'branch_id': account.branch_id.id, 'company_id': account.company_id.id,
                    **{key: item[key] for key in ('name', 'mimetype', 'size', 'kind', 'duration')},
                    'data': base64.b64encode(raw), 'state': 'ready', 'provider_file_id': item['id'],
                })
            finally:
                _INTERNAL.reset(internal)


class Attachment(models.Model):
    _inherit = 'ir.attachment'

    def _website_composer_access(self, values=None):
        values = values or {}
        for attachment in self:
            if attachment.res_model != 'ab_crm_conversation':
                continue
            conversation = self.env['ab_crm_conversation'].browse(attachment.res_id).exists()
            if not conversation or conversation.channel_id.provider != 'website':
                continue
            conversation._owned()
            if attachment.url and attachment.url.startswith('website-composer:'):
                metadata = json.loads(attachment.description or '{}')
                if (attachment.create_uid.id != self.env.uid
                        or metadata.get('employee_id') != conversation._workspace_actor().employee_id.id
                        or set(values) & {'description', 'url', 'res_model', 'res_id', 'company_id'}):
                    raise AccessError(_('Invalid website media.'))

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if values.get('res_model') == 'ab_crm_conversation':
                conversation = self.env['ab_crm_conversation'].browse(values.get('res_id')).exists()
                if conversation and conversation.channel_id.provider == 'website':
                    conversation._owned()
                    if values.get('url', '').startswith('website-composer:') and not _INTERNAL.get():
                        raise AccessError(_('Invalid website media.'))
        return super().create(values_list)

    def write(self, values):
        self._website_composer_access(values)
        if values.get('res_model') == 'ab_crm_conversation':
            conversation = self.env['ab_crm_conversation'].browse(values.get('res_id')).exists()
            if conversation and conversation.channel_id.provider == 'website':
                conversation._owned()
        return super().write(values)

    def unlink(self):
        self._website_composer_access()
        return super().unlink()
