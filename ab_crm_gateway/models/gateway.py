import json
from hashlib import sha256

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.ab_crm_core.models.core import _INTERNAL


class Gateway(models.AbstractModel):
    _name = 'ab_crm_gateway_api'
    _description = 'CRM Gateway API'

    def _worker(self):
        if not self.env.user.has_group('ab_crm_gateway.group_gateway'):
            raise AccessError(_('Only the gateway service can exchange messages.'))

    @api.model
    def receive_message(self, channel_code, event_id, external_key, body):
        self._worker()
        if not all(isinstance(v, str) and v for v in (channel_code, event_id, external_key, body)) or len(body) > 20000 or len(event_id) > 256 or len(external_key) > 256:
            raise ValidationError(_('Invalid incoming message.'))
        channel = self.env['ab_crm_channel'].search(fields.Domain('code', '=', channel_code), limit=1)
        channel.ensure_one()
        channel._authorize('read')
        channel.lock_for_update()
        key = sha256(json.dumps([channel_code, event_id]).encode()).hexdigest()
        existing = self.env['ab_crm_message'].search(fields.Domain('provider_event', '=', key), limit=1)
        if existing:
            if existing.body != body or existing.conversation_id.external_key != external_key:
                raise ValidationError(_('An event ID cannot be reused with different content.'))
            return {'received': True, 'id': existing.id}
        conversation = self.env['ab_crm_conversation'].search(fields.Domain('channel_id', '=', channel.id) & fields.Domain('external_key', '=', external_key), limit=1)
        if not conversation:
            conversation = self.env['ab_crm_conversation'].create({'name': external_key, 'external_key': external_key,
                'channel_id': channel.id, 'branch_id': channel.branch_id.id, 'company_id': channel.company_id.id})
        token = _INTERNAL.set(True)
        try:
            message = self.env['ab_crm_message'].create({'conversation_id': conversation.id, 'body': body, 'direction': 'in',
                'delivery_state': 'sent', 'provider_event': key, 'branch_id': channel.branch_id.id, 'company_id': channel.company_id.id})
        finally:
            _INTERNAL.reset(token)
        return {'received': True, 'id': message.id}

    @api.model
    def lease_reply(self):
        self._worker()
        message = self.env['ab_crm_message'].search(fields.Domain('delivery_state', '=', 'approved') & fields.Domain('direction', '=', 'out'), order='id', limit=1)
        if not message:
            return False
        message._authorize()
        message.lock_for_update()
        message._internal_write({'delivery_state': 'unknown'})
        return {'id': message.id, 'token': message.token, 'channel': message.conversation_id.channel_id.code,
                'provider': message.conversation_id.channel_id.provider, 'destination': message.conversation_id.external_key, 'body': message.body}

    @api.model
    def report_reply(self, message_id, token, provider_reference):
        self._worker()
        message = self.env['ab_crm_message'].browse(message_id).exists()
        message.ensure_one()
        message._authorize()
        message.lock_for_update()
        if message.token != token or message.delivery_state not in ('unknown', 'sent') or not isinstance(provider_reference, str) or not provider_reference:
            raise UserError(_('Invalid outbound delivery evidence.'))
        if message.provider_reference and message.provider_reference != provider_reference:
            raise UserError(_('Invalid outbound delivery evidence.'))
        message._internal_write({'delivery_state': 'sent', 'provider_reference': provider_reference})
        return True
