import base64
import binascii

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError


from .common import _DASHBOARD, _BRIDGE


class Service(models.Model):
    _inherit = 'ab.whatsapp.service'

    def _settings(self):
        values = super()._settings()
        version = self._config_value('whatsapp_api_version', 'v26.0')
        if version != 'v26.0':
            raise UserError(_('WhatsApp requires the validated Graph API version v26.0.'))
        return dict(values, api_version=version)

    def _normalize_wa_id(self, value):
        if _BRIDGE.get() and isinstance(value, str) and 1 <= len(value) <= 256 and value.isascii() and all(33 <= ord(char) <= 126 for char in value):
            return value
        if not isinstance(value, str) or not value.isascii() or not value.isdecimal():
            raise UserError(_('Unsupported WhatsApp identity requires review.'))
        return value

    def _validate_phone_number_id(self, phone_number_id, recipient_wa_id=None):
        self._normalize_wa_id(phone_number_id)
        return super()._validate_phone_number_id(phone_number_id, recipient_wa_id)

    def _post_graph_json(self, url, payload, headers):
        if url.rstrip('/').endswith('/messages'):
            raise AccessError(_('Use the durable gateway for WhatsApp sending.'))
        return super()._post_graph_json(url, payload, headers)

    def _queue_account(self, to, phone_number_id):
        self._ensure_system_access()
        destination = self._normalize_wa_id(to)
        contact = (
            self.env['ab.whatsapp.contact']
            .sudo()
            .search([('wa_id', '=', destination)], limit=1)
        )
        phone = (
            phone_number_id
            or contact.preferred_phone_number_id
            or self._settings()['default_phone_number_id']
        )
        if not phone:
            if (
                self.env['ab_crm_messaging_account']
                .sudo()
                .with_context(active_test=False)
                .search_count([('whatsapp_migrated', '=', True)])
            ):
                raise UserError(_('Select an explicit WhatsApp sender account.'))
            phone = self._resolve_sender_phone_number_id(destination, phone_number_id)
        phone = self._validate_phone_number_id(phone, destination)
        account = (
            self.env['ab_crm_messaging_account']
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    ('provider', '=', 'whatsapp'),
                    ('provider_account', '=', phone),
                    ('whatsapp_migrated', '=', True),
                ],
                limit=1,
            )
        )
        if account:
            account = account.with_env(self.env)
            account._authorize('read')
            if not destination or not destination.isascii():
                raise UserError(_('Recipient WhatsApp number is required.'))
        if not account:
            raise UserError(_('Configure WhatsApp queue ownership before sending.'))
        return account, destination

    def _queue_message(
        self,
        account,
        destination,
        body='',
        attachment=None,
        reply_reference=None,
        reaction=None,
        template_id=None,
        parameters=None,
        contact_name=None,
    ):
        account._authorize('read')
        account.lock_for_update()
        if contact_name:
            self._find_or_create_contact(
                wa_id=destination,
                name=contact_name,
                preferred_phone_number_id=account.provider_account,
            )
        conversation = account._whatsapp_conversation(destination)
        flag = _DASHBOARD.set(True)
        try:
            if template_id:
                message_id = conversation.action_whatsapp_template(
                    template_id, parameters
                )
            else:
                reply = (
                    conversation._whatsapp_reference(
                        reply_reference, reaction=bool(reaction)
                    )
                    if reply_reference
                    else self.env['ab_crm_message']
                )
                message_id = conversation.action_reply(
                    body,
                    attachments=[attachment] if attachment else [],
                    reply_id=reply.id,
                    reaction=reaction,
                )
        finally:
            _DASHBOARD.reset(flag)
        history = self.env['ab.whatsapp.message'].search(
            [('crm_message_id', '=', message_id)], limit=1
        )
        return {
            'ok': True,
            'message': self._serialize_message(history),
            'response': {'queued': True},
        }

    @api.model
    def api_send_text(
        self,
        to,
        message,
        contact_name=None,
        phone_number_id=None,
        reply_to_meta_message_id=None,
    ):
        account, destination = self._queue_account(to, phone_number_id)
        if not account:
            return super().api_send_text(
                to, message, contact_name, phone_number_id, reply_to_meta_message_id
            )
        return self._queue_message(
            account,
            destination,
            body=message,
            reply_reference=reply_to_meta_message_id,
            contact_name=contact_name,
        )

    @api.model
    def api_send_template(
        self,
        to,
        template_id,
        contact_name=None,
        phone_number_id=None,
        template_params=None,
    ):
        account, destination = self._queue_account(to, phone_number_id)
        if not account:
            return super().api_send_template(
                to, template_id, contact_name, phone_number_id, template_params
            )
        return self._queue_message(
            account,
            destination,
            template_id=template_id,
            parameters=template_params,
            contact_name=contact_name,
        )

    @api.model
    def api_send_media_base64(
        self,
        to,
        filename,
        content_type,
        data_base64,
        caption=None,
        contact_name=None,
        phone_number_id=None,
        reply_to_meta_message_id=None,
    ):
        account, destination = self._queue_account(to, phone_number_id)
        if not account:
            return super().api_send_media_base64(
                to,
                filename,
                content_type,
                data_base64,
                caption,
                contact_name,
                phone_number_id,
                reply_to_meta_message_id,
            )
        if not isinstance(data_base64, str) or len(data_base64) > 28 * 1024 * 1024:
            raise UserError(_('Invalid media content or size.'))
        try:
            raw = base64.b64decode(data_base64, validate=True)
        except (ValueError, binascii.Error):
            raise UserError(_('Invalid media content or size.')) from None
        attachment = {
            'kind': self._infer_message_type(content_type),
            'name': filename,
            'mimetype': content_type,
            'size': len(raw),
            'data': data_base64,
        }
        return self._queue_message(
            account,
            destination,
            body=caption or '',
            attachment=attachment,
            contact_name=contact_name,
            reply_reference=reply_to_meta_message_id,
        )

    @api.model
    def api_send_reaction(
        self, to, message_meta_id, emoji, contact_name=None, phone_number_id=None
    ):
        account, destination = self._queue_account(to, phone_number_id)
        if not account:
            return super().api_send_reaction(
                to, message_meta_id, emoji, contact_name, phone_number_id
            )
        return self._queue_message(
            account,
            destination,
            reaction=emoji,
            reply_reference=message_meta_id,
            contact_name=contact_name,
        )

    def _serialize_message(self, message):
        result = super()._serialize_message(message)
        result['integrated'] = bool(message.crm_account_id)
        if message.crm_account_id and message.crm_message_id.media_ids:
            result['media_id'] = message.media_id or 'crm-' + str(message.id)
        return result

    @api.model
    def api_list_conversation(self, wa_id, limit=300):
        self._ensure_system_access()
        messages = self.env['ab.whatsapp.message'].search(
            [
                ('wa_id', '=', self._normalize_wa_id(wa_id)),
                ('crm_account_id', '!=', False),
            ],
            limit=max(1, min(int(limit or 300), 1000)),
            order='id desc',
        )
        return [self._serialize_message(m) for m in reversed(messages)]

    @api.model
    def api_upsert_contact(self, wa_id, name=None, preferred_phone_number_id=None):
        self._queue_account(wa_id, preferred_phone_number_id)
        return super().api_upsert_contact(wa_id, name, preferred_phone_number_id)

    @api.model
    def api_list_templates(self):
        self._ensure_system_access()
        accounts = self.env['ab_crm_messaging_account'].search(
            [('provider', '=', 'whatsapp'), ('whatsapp_migrated', '=', True)]
        )
        if accounts:
            return [
                self._serialize_template(template)
                for account in accounts
                for template in account._available_whatsapp_templates()
            ]
        return super().api_list_templates()

    def _serialize_contact(self, contact, latest_message=None):
        if latest_message is None:
            latest_message = self.env['ab.whatsapp.message'].search(
                [('contact_id', '=', contact.id)], order='id desc', limit=1
            )
        result = super()._serialize_contact(contact, latest_message)
        account = self.env['ab_crm_messaging_account'].search(
            [
                ('provider', '=', 'whatsapp'),
                ('whatsapp_migrated', '=', True),
                ('provider_account', '=', contact.preferred_phone_number_id),
            ],
            limit=1,
        )
        result['integrated'] = bool(account or latest_message.crm_account_id)
        return result

    @api.model
    def api_list_contacts(self, limit=300):
        self._ensure_system_access()
        messages = self.env['ab.whatsapp.message'].search(
            [('crm_account_id', '!=', False)], order='id desc', limit=5000
        )
        latest = {}
        for message in messages:
            latest.setdefault(message.contact_id.id, message)
        accounts = self.env['ab_crm_messaging_account'].search(
            [('provider', '=', 'whatsapp'), ('whatsapp_migrated', '=', True)]
        )
        contacts = (
            self.env['ab.whatsapp.contact']
            .sudo()
            .search(
                [
                    '|',
                    ('id', 'in', list(latest)),
                    (
                        'preferred_phone_number_id',
                        'in',
                        accounts.mapped('provider_account'),
                    ),
                ],
                order='last_message_at desc, id desc',
                limit=max(1, min(int(limit or 300), 1000)),
            )
        )
        return [
            self._serialize_contact(
                contact, latest.get(contact.id, self.env['ab.whatsapp.message'])
            )
            for contact in contacts
        ]

    @api.model
    def api_mark_incoming_read(self, wa_id, limit=100):
        self._ensure_system_access()
        if (
            self.env['ab.whatsapp.message']
            .sudo()
            .search_count(
                [
                    ('wa_id', '=', self._normalize_wa_id(wa_id)),
                    ('crm_account_id', '!=', False),
                ]
            )
        ):
            return {'ok': True, 'updated': 0}
        return super().api_mark_incoming_read(wa_id, limit)

    def process_webhook_payload(self, payload):
        raise AccessError(_('Use the signed gateway webhook for WhatsApp reception.'))

    def get_message_media_content(self, message_id):
        self._ensure_system_access()
        message = (
            self.env['ab.whatsapp.message'].with_user(self.env.user).browse(message_id)
        )
        message.check_access('read')
        if message.crm_account_id:
            media = message.crm_message_id.media_ids[:1]
            if media and media.state == 'ready':
                return base64.b64decode(media.data), media.mimetype, media.name
        return super().get_message_media_content(message_id)
