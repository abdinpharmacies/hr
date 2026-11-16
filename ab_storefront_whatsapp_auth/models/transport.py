import json
import re
import secrets
from datetime import timedelta
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class WhatsAppTransport(models.Model):
    _name = 'ab_storefront_whatsapp_transport'
    _description = 'WhatsApp Authentication Transport'

    name = fields.Char(required=True)
    source = fields.Char(default=lambda self: str(uuid4()), required=True, copy=False, readonly=True, index=True)
    enabled = fields.Boolean(default=False)
    website_id = fields.Many2one('website', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='website_id.company_id', store=True)
    service_user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    sender = fields.Char(required=True)
    template_en = fields.Char(required=True)
    template_ar = fields.Char(required=True)
    language_en = fields.Char(default='en_US', required=True)
    language_ar = fields.Char(default='ar', required=True)

    _unique_source = models.Constraint('UNIQUE(source)', 'Authentication sources must be unique.')
    _unique_website = models.Constraint('UNIQUE(website_id)', 'Configure one authentication transport per website.')

    @api.constrains('sender', 'template_en', 'template_ar', 'language_en', 'language_ar', 'source', 'service_user_id', 'website_id', 'enabled')
    def _validate_configuration(self):
        from uuid import UUID
        for transport in self:
            try:
                valid_source = str(UUID(transport.source)) == transport.source
            except (ValueError, TypeError):
                valid_source = False
            user = transport.service_user_id
            if (not valid_source or not re.fullmatch(r'[0-9]{1,40}', transport.sender or '')
                    or any(not re.fullmatch(r'[a-z0-9_]{1,100}', value or '') for value in (transport.template_en, transport.template_ar))
                    or not re.fullmatch(r'en(?:_[A-Z]{2})?', transport.language_en or '')
                    or not re.fullmatch(r'ar(?:_[A-Z]{2})?', transport.language_ar or '')
                    or not user.active or user.share
                    or not user.has_group('ab_storefront_whatsapp_auth.group_auth_transport')
                    or transport.company_id not in user.company_ids):
                raise ValidationError(_('Invalid WhatsApp authentication configuration.'))

    def _scope_hash(self):
        self.ensure_one()
        return self.env['ab_storefront_auth_service']._digest('wa-scope:' + json.dumps([self.source, self.website_id.id, self.company_id.id, self.service_user_id.id, self.sender, self.template_en, self.template_ar, self.language_en, self.language_ar]))

    def _authorize(self):
        self.ensure_one()
        user = self.env.user
        if (self.env.su or not user.active
                or not user.has_group('ab_storefront_whatsapp_auth.group_auth_transport')):
            raise AccessError(_('Authentication transport access denied.'))
        transport = self.sudo()
        if (not transport.enabled or transport.service_user_id.id != user.id
                or transport.company_id.id not in user.company_ids.ids):
            raise AccessError(_('Authentication transport access denied.'))
        return transport

    def _exchange(self, operation, data):
        transport = self._authorize()
        service = self.env['ab_storefront_auth_service'].sudo()
        Event = self.env['ab_storefront_auth_event'].sudo()
        now = fields.Datetime.now()
        if operation == 'lease':
            service._lock('whatsapp-lease:' + transport.source)
            expired = Event.search([('wa_transport_id', '=', transport.id), ('state', 'in', ['wa_leased', 'wa_dispatching']), ('wa_lease_until', '<=', now)])
            for event in expired:
                if event.state == 'wa_dispatching':
                    event.write({'state': 'wa_unknown', 'payload': False})
                else:
                    event.write({'state': 'wa_pending', 'wa_lease_hash': False})
            events = Event.search([('wa_transport_id', '=', transport.id), ('state', '=', 'wa_pending'), ('next_attempt', '<=', now)], order='id', limit=20)
            for event in events:
                service._lock('event:' + str(event.id))
                event.invalidate_recordset()
                if event.state != 'wa_pending':
                    continue
                challenge = event.challenge_id
                service._lock('challenge:' + challenge.token_hash)
                challenge.invalidate_recordset()
                if not service._wa_deliverable(event):
                    event.write({'state': 'done', 'payload': False})
                    continue
                lease = secrets.token_urlsafe(32)
                event.write({'state': 'wa_leased', 'wa_lease_hash': service._digest('wa-lease:' + lease), 'wa_lease_until': now + timedelta(seconds=30)})
                return {'delivery': event.wa_uuid, 'lease': lease}
            return None
        delivery = data.get('delivery')
        if not isinstance(delivery, str) or len(delivery) > 50:
            raise ValidationError(_('Invalid delivery receipt.'))
        event = Event.search([('wa_uuid', '=', delivery), ('wa_transport_id', '=', transport.id)], limit=1)
        if not event:
            raise AccessError(_('Authentication transport access denied.'))
        service._lock('event:' + str(event.id))
        event.invalidate_recordset()
        if operation == 'status':
            reference = data.get('reference')
            state = data.get('status')
            if (state not in ('accepted', 'delivered', 'read', 'failed')
                    or not isinstance(reference, str) or not 1 <= len(reference) <= 200
                    or event.state not in ('wa_dispatching', 'wa_unknown', 'wa_accepted', 'wa_delivered', 'wa_read', 'failed')
                    or (event.wa_reference and event.wa_reference != reference)):
                raise ValidationError(_('Invalid delivery receipt.'))
            return transport._status(event, state, reference)
        lease = data.get('lease')
        if not isinstance(lease, str) or not secrets.compare_digest(event.wa_lease_hash or '', service._digest('wa-lease:' + lease)):
            raise AccessError(_('Authentication transport access denied.'))
        if operation == 'dispatch':
            if event.state != 'wa_leased' or event.wa_lease_until <= now or not service._wa_deliverable(event):
                if event.state == 'wa_leased':
                    event.write({'state': 'done', 'payload': False})
                return None
            payload = json.loads(service._cipher().decrypt(event.payload.encode()).decode())
            event.write({'state': 'wa_dispatching', 'wa_lease_until': now + timedelta(seconds=45), 'attempts': event.attempts + 1})
            return {**payload, 'delivery': event.wa_uuid, 'sender': transport.sender,
                    'expires_at': fields.Datetime.to_string(event.challenge_id.expires_at)}
        if operation != 'report':
            raise ValidationError(_('Invalid delivery receipt.'))
        status = data.get('status')
        if status not in ('accepted', 'rejected', 'transient', 'unknown'):
            raise ValidationError(_('Invalid delivery receipt.'))
        if event.state != 'wa_dispatching':
            return True
        if status == 'accepted':
            reference = data.get('reference')
            if not isinstance(reference, str) or not 1 <= len(reference) <= 200:
                raise ValidationError(_('Invalid delivery receipt.'))
            return transport._status(event, 'accepted', reference)
        if status == 'transient' and event.attempts < 3 and service._wa_deliverable(event):
            event.write({'state': 'wa_pending', 'next_attempt': now + timedelta(seconds=30), 'wa_lease_hash': False})
        else:
            event.write({'state': 'wa_unknown' if status == 'unknown' else 'failed', 'payload': False})
        return True

    def _status(self, event, state, reference):
        ranks = {'wa_dispatching': 0, 'wa_unknown': 0, 'failed': 0, 'wa_accepted': 1, 'wa_delivered': 2, 'wa_read': 3}
        target = 'failed' if state == 'failed' else 'wa_' + state
        if ranks[target] >= ranks[event.state]:
            event.write({'state': target, 'wa_reference': reference, 'payload': False})
        return True


class WhatsAppChallenge(models.Model):
    _inherit = 'ab_storefront_auth_challenge'

    wa_transport_id = fields.Many2one('ab_storefront_whatsapp_transport', ondelete='restrict', groups='base.group_system')


class WhatsAppEvent(models.Model):
    _inherit = 'ab_storefront_auth_event'

    wa_uuid = fields.Char(copy=False, index=True, groups='base.group_system')
    wa_transport_id = fields.Many2one('ab_storefront_whatsapp_transport', ondelete='restrict', index=True, groups='base.group_system')
    wa_scope_hash = fields.Char(groups='base.group_system')
    wa_lease_hash = fields.Char(groups='base.group_system')
    wa_lease_until = fields.Datetime(groups='base.group_system')
    wa_reference = fields.Char(groups='base.group_system')
    state = fields.Selection(selection_add=[
        ('wa_pending', 'Queued'), ('wa_leased', 'Leased'), ('wa_dispatching', 'Dispatching'),
        ('wa_accepted', 'Accepted'), ('wa_delivered', 'Delivered'),
        ('wa_read', 'Read'), ('wa_unknown', 'Unknown outcome'),
    ], ondelete={key: 'set default' for key in ('wa_pending', 'wa_leased', 'wa_dispatching', 'wa_accepted', 'wa_delivered', 'wa_read', 'wa_unknown')})

    _unique_wa_uuid = models.Constraint('UNIQUE(wa_uuid)', 'Delivery identifiers must be unique.')
