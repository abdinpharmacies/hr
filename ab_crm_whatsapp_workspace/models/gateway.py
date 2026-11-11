import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import bridge_mutation


def valid_contact_cards(cards):
    if not isinstance(cards, list) or len(cards) > 100:
        return False
    schemas = {
        'phones': {'phone', 'wa_id', 'type'}, 'emails': {'email', 'type'},
        'addresses': {'street', 'city', 'state', 'zip', 'country', 'country_code', 'type'},
        'urls': {'url', 'type'},
    }
    for card in cards:
        if not isinstance(card, dict) or card.keys() - {'name', 'phones', 'emails', 'addresses', 'urls', 'org', 'birthday'}:
            return False
        for key, allowed in dict(schemas, name={'formatted_name', 'first_name', 'last_name', 'middle_name', 'suffix', 'prefix'},
                                 org={'company', 'department', 'title'}).items():
            value = card.get(key, [] if key in schemas else {})
            values = value if key in schemas else [value]
            if not isinstance(values, list) or len(values) > 100:
                return False
            if any(not isinstance(item, dict) or item.keys() - allowed
                   or any(not isinstance(text, str) or len(text) > 2000 for text in item.values()) for item in values):
                return False
        if not isinstance(card.get('birthday', ''), str) or len(card.get('birthday', '')) > 32:
            return False
    return True


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    @api.model
    def lease_outgoing(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if account.provider == 'whatsapp' and (
            not account.whatsapp_migrated or not account.outgoing_enabled
        ):
            return False
        return super().lease_outgoing(account_code, provider_account)

    @api.model
    def authorize_send(self, account_code, provider_account, token, attempt, receipt):
        allowed = super().authorize_send(
            account_code, provider_account, token, attempt, receipt
        )
        account = self._account(account_code, provider_account)
        if not allowed or account.provider != 'whatsapp':
            return allowed
        if not account.whatsapp_migrated or not account.outgoing_enabled:
            return False
        operation = self._operation(account, token, attempt)
        actor = operation.approved_by
        message = operation.message_id.with_user(actor).with_context(
            allowed_company_ids=account.company_id.ids
        )
        try:
            if (
                not actor.active
                or account.company_id not in actor.company_ids
                or not (
                    actor.has_group('base.group_system')
                    or actor.has_group('ab_crm_core.group_user')
                )
            ):
                raise AccessError(_('The original sender no longer has permission.'))
            session = operation.message_id.whatsapp_session_id
            if session:
                chatter = (
                    self.env['ab_crm_chatter_api']
                    .with_user(actor)
                    .with_context(allowed_company_ids=account.company_id.ids)
                )
                chatter._require_staff()
                if (
                    session.user_id != actor
                    or session.company_id != account.company_id
                    or session.state != 'active'
                    or session.expires_at <= fields.Datetime.now()
                    or not chatter._eligible(session.profile_id)
                ):
                    raise AccessError(
                        _('The original sender no longer has permission.')
                    )
                chatter._branch_scope(
                    session, account.branch_id.with_env(chatter.env)
                )
            elif not actor.has_group('base.group_system'):
                raise AccessError(_('The original sender no longer has permission.'))
            message._staff_action()
            message._authorize('read')
            account.with_user(actor)._authorize('read')
            account.with_user(actor)._eligible_message(message)
            if message._outgoing_extra() != operation.content:
                raise UserError(
                    _('The approved WhatsApp content is no longer eligible.')
                )
        except (AccessError, UserError):
            error = (
                'window'
                if operation.expires_at
                and operation.expires_at <= fields.Datetime.now()
                else 'rejected'
            )
            return {'allowed': False, 'terminal': True, 'error': error}
        return True

    @api.model
    def receive_event(self, account_code, provider_account, event):
        account = self._account(account_code, provider_account)
        if account.provider == 'whatsapp' and (
            not account.whatsapp_migrated
            or not account.whatsapp_webhook_enabled
            or not account.active
            or not account.enabled
            or not account.channel_id.sudo().active
        ):
            raise UserError(_('Signed WhatsApp reception is disabled.'))
        if account.provider == 'whatsapp' and isinstance(event, dict):
            history = (
                self.env['ab.whatsapp.message']
                .sudo()
                .search(
                    [
                        ('crm_account_id', '=', account.id),
                        ('meta_message_id', '=', event.get('id')),
                        ('direction', '=', 'incoming'),
                    ],
                    limit=2,
                )
            )
            if history:
                raw = history.raw_payload if len(history) == 1 else {}
                source = raw.get('source_digest') if isinstance(raw, dict) else None
                source = (
                    source
                    or hashlib.sha256(
                        json.dumps(raw, sort_keys=True).encode()
                    ).hexdigest()
                )
                if (
                    (
                        isinstance(raw, dict)
                        and raw.get('source_digest')
                        and raw != event
                    )
                    or len(history) != 1
                    or not history.crm_message_id
                    or event.get('sender') != history.wa_id
                    or event.get('source_digest') != source
                    or (
                        history.message_type == 'text'
                        and event.get('body') != history.text_content
                    )
                ):
                    raise ValidationError(
                        _('Conflicting WhatsApp history requires review.')
                    )
                return {'message_id': history.crm_message_id.id}
        return super().receive_event(account_code, provider_account, event)

    def _status_target(self, account, reference, destination, status):
        if (not isinstance(reference, str) or not 1 <= len(reference) <= 256
                or not isinstance(destination, str) or not 1 <= len(destination) <= 256
                or status not in ('accepted', 'delivered', 'read', 'failed')
                or not account._status_allowed(status)):
            raise ValidationError(_('Invalid delivery evidence.'))
        if account.provider != 'whatsapp' or not account.whatsapp_webhook_enabled:
            raise UserError(_('Signed WhatsApp reception is disabled.'))
        operations = self.env['ab_crm_messaging_operation'].sudo().search([
            ('account_id', '=', account.id), ('provider_reference', '=', reference),
            ('destination', '=', destination),
        ], limit=2)
        if operations:
            return ('operation' if len(operations) == 1 else 'ambiguous'), operations
        history = self.env['ab.whatsapp.message'].sudo().search([
            ('phone_number_id', '=', account.provider_account),
            ('meta_message_id', '=', reference), ('wa_id', '=', destination),
            ('direction', '=', 'outgoing'),
        ], limit=2)
        if not history:
            return 'orphan', history
        if len(history) != 1:
            return 'ambiguous', history
        message = history.crm_message_id
        if (history.crm_account_id != account or not message or not message.historical
                or message.direction != 'out' or message.company_id != account.company_id
                or message.branch_id != account.branch_id
                or message.conversation_id.channel_id != account.channel_id
                or message.conversation_id.external_key != destination
                or message.provider_reference != reference
                or message.messaging_operation_ids):
            return 'unverified', history
        return 'historical', history

    @api.model
    def preview_status(self, account_code, provider_account, reference, destination, status):
        account = self._account(account_code, provider_account)
        match, target = self._status_target(account, reference, destination, status)
        return {'match': match}

    @api.model
    def receive_status(
        self, account_code, provider_account, reference, destination, status
    ):
        account = self._account(account_code, provider_account)
        if account.provider != 'whatsapp':
            return super().receive_status(account_code, provider_account, reference, destination, status)
        match, target = self._status_target(account, reference, destination, status)
        if match == 'operation':
            return super().receive_status(account_code, provider_account, reference, destination, status)
        if match != 'historical':
            raise UserError(_('Provider acceptance is not recorded yet. Retry this status later.'))
        target.lock_for_update()
        target.invalidate_recordset(['status'])
        ranks = {'sent': 1, 'accepted': 1, 'delivered': 2, 'read': 3}
        current = target.status
        if (current == status
                or current in ('delivered', 'read') and ranks.get(status, 0) <= ranks[current]
                or current == 'failed' and status in ('accepted', 'failed')
                or current in ('sent', 'accepted') and status == 'accepted'):
            return True
        with bridge_mutation():
            target.write({'status': status})
            target.crm_message_id._internal_write({
                'delivery_state': 'failed' if status == 'failed' else 'sent',
            })
        return True

    def _receive_event_extra(self, account, event, message):
        metadata = event.get('whatsapp', {})
        if metadata and (account.provider != 'whatsapp' or not isinstance(metadata, dict)
                         or metadata.keys() - {'type', 'cards', 'profile_name', 'diagnostic'}
                         or len(json.dumps(metadata)) > 55000):
            raise ValidationError(_('Invalid incoming messaging event.'))
        result = super()._receive_event_extra(account, event, message)
        if account.provider == 'whatsapp':
            cards = metadata.get('cards', [])
            if (not valid_contact_cards(cards)
                    or not isinstance(metadata.get('profile_name', ''), str)
                    or not isinstance(metadata.get('type', ''), str) or len(metadata.get('type', '')) > 64):
                raise ValidationError(_('Invalid incoming messaging event.'))
            with bridge_mutation():
                message.write({'whatsapp_payload': metadata, 'whatsapp_reaction_event': 'reaction' in event})
                if metadata.get('profile_name'):
                    message.conversation_id.write({'whatsapp_profile_name': metadata['profile_name'][:256]})

            with bridge_mutation():
                canonical = (
                    self.env['ab.whatsapp.service']
                    .sudo()
                    ._create_message(
                        direction='incoming',
                        wa_id=event['sender'],
                        phone_number_id=account.provider_account,
                        message_type='unsupported' if event['unsupported'] else metadata.get('type') or ('location' if message.location_snapshot else 'text'),
                        reply_to_meta_message_id=message.reply_reference if 'reaction' not in event else None,
                        reaction_target_meta_message_id=message.reply_reference if 'reaction' in event else None,
                        media_mime_type=message.media_ids[:1].mimetype,
                        media_filename=message.media_ids[:1].name,
                        text_content=message.body,
                        status='received',
                        meta_message_id=event['id'],
                        raw_payload=event,
                    )
                )
                canonical.write(
                    {
                        'crm_account_id': account.id,
                        'crm_message_id': message.id,
                        'crm_timestamp': fields.Datetime.to_datetime(
                            event['timestamp']
                        ),
                    }
                )
        return result
