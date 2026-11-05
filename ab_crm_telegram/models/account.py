from contextvars import ContextVar

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    provider = fields.Selection(
        selection_add=[('telegram', 'Telegram')],
        ondelete={'telegram': lambda records: records._prevent_provider_removal()},
    )

    def _queue_eligibility(self, conversation):
        code, reason = super()._queue_eligibility(conversation)
        if code:
            return code, reason
        if self.provider == 'telegram' and not self.outgoing_enabled:
            return 'outgoing_disabled', _(
                'Outgoing sending is disabled. No request has been queued.'
            )
        if self.provider == 'telegram' and not conversation.external_key.isdecimal():
            return 'private_chat_required', _(
                'Only Telegram private chats are supported.'
            )
        return False, False


_CONTACT = ContextVar('ab_crm_telegram_contact', default=False)


class Message(models.Model):
    _inherit = 'ab_crm_message'

    telegram_phone = fields.Char(readonly=True)
    telegram_contact_owned = fields.Boolean(readonly=True)
    telegram_request_contact = fields.Boolean(readonly=True)

    def _outgoing_extra(self):
        result = super()._outgoing_extra()
        if self.telegram_request_contact:
            result['contact_button'] = _('Share contact')
        return result

    @api.model_create_multi
    def create(self, values_list):
        protected = {
            'telegram_phone',
            'telegram_contact_owned',
            'telegram_request_contact',
        }
        if not _CONTACT.get():
            if any(protected & values.keys() for values in values_list):
                raise AccessError(
                    _('Telegram contact evidence is managed by the gateway.')
                )
            values_list = [
                dict(
                    values,
                    telegram_phone=False,
                    telegram_contact_owned=False,
                    telegram_request_contact=False,
                )
                for values in values_list
            ]
        return super().create(values_list)

    def write(self, values):
        if (
            not _CONTACT.get()
            and {'telegram_phone', 'telegram_contact_owned', 'telegram_request_contact'}
            & values.keys()
        ):
            raise AccessError(_('Telegram contact evidence is managed by the gateway.'))
        return super().write(values)


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    telegram_profile_name = fields.Char(readonly=True)
    telegram_username = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not _INTERNAL.get() and any(
            {'telegram_profile_name', 'telegram_username'} & v.keys()
            for v in values_list
        ):
            raise AccessError(_('Telegram profile evidence is managed by the gateway.'))
        return super().create(values_list)

    def write(self, values):
        if (
            not _INTERNAL.get()
            and {'telegram_profile_name', 'telegram_username'} & values.keys()
        ):
            raise AccessError(_('Telegram profile evidence is managed by the gateway.'))
        return super().write(values)

    def _contact_request(self):
        self.ensure_one()
        return self.env['ab_crm_message'].search(
            [
                ('conversation_id', '=', self.id),
                ('telegram_request_contact', '=', True),
                ('messaging_operation_ids.state', '!=', 'cancelled'),
            ],
            limit=1,
        )

    def action_request_contact(self):
        self.ensure_one()
        self._staff_action()
        self._authorize()
        if self.channel_id.provider != 'telegram':
            raise UserError(_('Contact sharing is available only in Telegram.'))
        self.messaging_account_id._eligible(self, 'contact')
        self.lock_for_update()
        existing = self._contact_request()
        if existing:
            return existing.id
        token = _CONTACT.set(True)
        try:
            message = self.env['ab_crm_message'].create(
                {
                    'conversation_id': self.id,
                    'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id,
                    'direction': 'out',
                    'body': _(
                        'Please share your phone using the Share contact button.'
                    ),
                    'telegram_request_contact': True,
                }
            )
            message.action_approve()
            return message.id
        finally:
            _CONTACT.reset(token)


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    def _receive_event_extra(self, account, event, message):
        super()._receive_event_extra(
            account, {k: v for k, v in event.items() if k != 'contact'}, message
        )
        profile = event.get('profile')
        if profile is not None:
            if (
                not isinstance(profile, dict)
                or set(profile) != {'name', 'username'}
                or any(not isinstance(v, str) or len(v) > 256 for v in profile.values())
            ):
                raise ValidationError(_('Invalid Telegram profile event.'))
            message.conversation_id._internal_write(
                {
                    'telegram_profile_name': profile['name'],
                    'telegram_username': profile['username'],
                }
            )
        contact = event.get('contact')
        if contact is None:
            return self._automatic_contact(account, message.conversation_id)
        if (
            account.provider != 'telegram'
            or not isinstance(contact, dict)
            or set(contact) != {'phone', 'user_id', 'sender_id'}
        ):
            raise ValidationError(_('Invalid Telegram contact event.'))
        if (
            not isinstance(contact['phone'], str)
            or not 1 <= len(contact['phone']) <= 64
            or contact['sender_id'] != event['sender']
            or not isinstance(contact['user_id'], str)
        ):
            raise ValidationError(_('Invalid Telegram contact event.'))
        token = _CONTACT.set(True)
        try:
            message.write(
                {
                    'telegram_phone': contact['phone'],
                    'telegram_contact_owned': contact['user_id'] == event['sender'],
                }
            )
        finally:
            _CONTACT.reset(token)

    def _automatic_contact(self, account, conversation):
        if (
            account.provider != 'telegram'
            or not account.outgoing_enabled
            or not account.contact_automation
            or conversation.customer_id
        ):
            return
        conversation.lock_for_update()
        if conversation._contact_request():
            return
        token = _CONTACT.set(True)
        mutation = _MUTATION.set(True)
        internal = _INTERNAL.set(True)
        try:
            body = _('Please share your phone using the Share contact button.')
            account.sudo()._eligible(conversation, body)
            message = (
                self.env['ab_crm_message']
                .sudo()
                .create(
                    {
                        'conversation_id': conversation.id,
                        'branch_id': account.branch_id.id,
                        'company_id': account.company_id.id,
                        'direction': 'out',
                        'body': body,
                        'telegram_request_contact': True,
                        'delivery_state': 'approved',
                        'approved_by': self.env.uid,
                        'approved_at': fields.Datetime.now(),
                    }
                )
            )
            self.env['ab_crm_messaging_operation'].sudo().create(
                {
                    'account_id': account.id,
                    'message_id': message.id,
                    'body': body,
                    'destination': conversation.external_key,
                    'branch_id': account.branch_id.id,
                    'company_id': account.company_id.id,
                    'approved_by': self.env.uid,
                    'approved_at': message.approved_at,
                    'content': {'contact_button': _('Share contact')},
                }
            )
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)
            _CONTACT.reset(token)

    @api.model
    def lease_outgoing(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if account.provider == 'telegram' and not account.outgoing_enabled:
            return False
        result = super().lease_outgoing(account_code, provider_account)
        if result and result['provider'] == 'telegram':
            account = self._account(account_code, provider_account)
            operation = self._operation(account, result['token'], result['attempt'])
            if operation.message_id.telegram_request_contact and not result.get('contact_button'):
                result['contact_button'] = _('Share contact')
        return result

    @api.model
    def authorize_send(self, account_code, provider_account, token, attempt, receipt):
        account = self._account(account_code, provider_account)
        return bool(
            (account.provider != 'telegram' or account.outgoing_enabled)
            and super().authorize_send(
                account_code, provider_account, token, attempt, receipt
            )
        )
