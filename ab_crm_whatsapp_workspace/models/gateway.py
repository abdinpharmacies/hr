import hashlib
import json

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import bridge_mutation


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
                chatter._branch_scope(session, account.branch_id)
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

    @api.model
    def receive_status(
        self, account_code, provider_account, reference, destination, status
    ):
        account = self._account(account_code, provider_account)
        if account.provider == 'whatsapp' and not account.whatsapp_webhook_enabled:
            raise UserError(_('Signed WhatsApp reception is disabled.'))
        return super().receive_status(
            account_code, provider_account, reference, destination, status
        )

    def _receive_event_extra(self, account, event, message):
        result = super()._receive_event_extra(account, event, message)
        if account.provider == 'whatsapp':
            with bridge_mutation():
                canonical = (
                    self.env['ab.whatsapp.service']
                    .sudo()
                    ._create_message(
                        direction='incoming',
                        wa_id=event['sender'],
                        phone_number_id=account.provider_account,
                        message_type='location' if message.location_snapshot else 'unsupported' if event['unsupported'] else 'text',
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
