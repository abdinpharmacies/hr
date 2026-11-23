from uuid import UUID, uuid4, uuid5

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext

from .adapter import _CAPTURE
from odoo.addons.mail.tools.discuss import Store
from ..protocol import fingerprint


class SessionEnded(ValidationError):
    pass


def opaque(source, value):
    return str(uuid5(UUID(source), value))


def customer_metadata(user):
    partner = user.partner_id
    result = {'name': (partner.name or user.name)[:256], 'phone': (partner.phone or '')[:64]}
    return result


class ChatEvent(models.Model):
    _name = 'ab_storefront_callcenter_chat_event'
    _description = 'Callcenter Chat Event'
    _order = 'id'

    endpoint_id = fields.Many2one('ab_storefront_callcenter_endpoint', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='endpoint_id.company_id', store=True)
    event_uuid = fields.Char(required=True, index=True)
    message_id = fields.Many2one('mail.message', required=True, ondelete='restrict')
    envelope = fields.Json(required=True)
    exchange_version = fields.Integer(string="Exchange version", default=2, readonly=True)
    acknowledged = fields.Boolean(default=False)
    _unique_event = models.Constraint('UNIQUE(endpoint_id, event_uuid)', 'Event already exists.')
    _unique_message = models.Constraint('UNIQUE(endpoint_id, message_id)', 'Message already captured.')

    @api.model
    def _capture(self, endpoint, destination, identity, body, message, event_uuid=None):
        if not endpoint.enabled or not endpoint.chat_enabled:
            raise AccessError(_('Website intake is disabled.'))
        attachments = self.env['ir.attachment']._ab_media_descriptors(message.attachment_ids)
        if attachments and not endpoint.media_enabled:
            raise ValidationError(_('Website media is unavailable.'))
        event = {'version': 4 if attachments else 2, 'source': endpoint.source, 'event_uuid': event_uuid or str(uuid4()),
                 'destination': destination, 'identity': identity, 'body': body}
        if attachments:
            event['attachments'] = attachments
        event['fingerprint'] = fingerprint(event)
        guard = _CAPTURE.set(True)
        try:
            return self.sudo().create({'endpoint_id': endpoint.id, 'message_id': message.id,
                                      'event_uuid': event['event_uuid'], 'envelope': event, 'exchange_version': event['version']})
        finally:
            _CAPTURE.reset(guard)

    @api.model_create_multi
    def create(self, values_list):
        if not _CAPTURE.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if not _CAPTURE.get() or set(values) - {'acknowledged'}:
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Website evidence is immutable.'))


class ChatReply(models.Model):
    _name = 'ab_storefront_callcenter_chat_reply'
    _description = 'Callcenter Native Chat Reply'

    endpoint_id = fields.Many2one('ab_storefront_callcenter_endpoint', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='endpoint_id.company_id', store=True)
    token = fields.Char(required=True)
    destination_kind = fields.Selection([('order', 'Order'), ('livechat', 'Live Chat')], required=True)
    destination_uuid = fields.Char(required=True)
    body = fields.Text()
    media_fingerprint = fields.Char()
    message_id = fields.Many2one('mail.message', required=True, ondelete='restrict')
    _unique_reply = models.Constraint('UNIQUE(endpoint_id, token)', 'Reply already exists.')

    @api.model_create_multi
    def create(self, values_list):
        if not _CAPTURE.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        raise AccessError(_('Website evidence is immutable.'))

    def unlink(self):
        raise AccessError(_('Website evidence is immutable.'))


class LiveChat(models.Model):
    _inherit = 'im_livechat.channel'

    def _ab_callcenter_endpoint(self):
        self.ensure_one()
        return self.env['ab_storefront_callcenter_endpoint'].sudo().search([
            ('livechat_channel_id', '=', self.id), ('enabled', '=', True),
            ('chat_enabled', '=', True), ('website_id.channel_id', '=', self.id),
        ], limit=1)

    def get_livechat_info(self, username=None):
        result = super().get_livechat_info(username=username)
        endpoint = self._ab_callcenter_endpoint()
        if endpoint:
            result['options']['ab_callcenter'] = True
            result['options']['ab_callcenter_lifecycle'] = endpoint.lifecycle_enabled
        return result

    def _get_available_operators_by_livechat_channel(self, users=None):
        result = super()._get_available_operators_by_livechat_channel(users)
        for channel in self:
            endpoint = channel._ab_callcenter_endpoint()
            if endpoint and endpoint.bridge_operator_id.active:
                result[channel] = endpoint.bridge_operator_id
        return result

    def _get_operator_info(self, **kwargs):
        endpoint = self._ab_callcenter_endpoint()
        if endpoint:
            from odoo.http import request
            if request and endpoint.website_id != request.env['website'].get_current_website():
                raise AccessError(_('Invalid website source.'))
            operator = endpoint.bridge_operator_id
            if not operator.active:
                raise AccessError(_('Website intake is disabled.'))
            return {'agent': operator, 'chatbot_script': self.env['chatbot.script'],
                    'operator_partner': operator.partner_id, 'operator_model': 'res.users'}
        return super()._get_operator_info(**kwargs)

    def _is_livechat_available(self):
        return bool(self._ab_callcenter_endpoint()) or super()._is_livechat_available()

    def _get_livechat_discuss_channel_vals(self, **kwargs):
        values = super()._get_livechat_discuss_channel_vals(**kwargs)
        endpoint = self._ab_callcenter_endpoint()
        if endpoint:
            user = self.env.user
            guest = self.env['mail.guest']._get_guest_from_context()
            if user._is_public() and not guest:
                raise AccessError(_('Invalid website source.'))
            previous = self.env['discuss.channel'].sudo().search([
                ('ab_callcenter_endpoint_id', '=', endpoint.id),
                ('ab_callcenter_identity_kind', '=', 'visitor'), ('livechat_end_dt', '=', False),
                ('channel_member_ids.guest_id', '=', guest.id),
            ], order='id desc', limit=1) if user._is_public() else False
            trusted_visitor = False
            if user._is_public() and endpoint.guest_metadata_enabled:
                from odoo.http import request
                if request:
                    from odoo.addons.ab_ecommerce_storefront.controllers.submission_security import submission_owner
                    trusted_visitor = opaque(endpoint.source, 'checkout:' + submission_owner())
            values.update(
                ab_callcenter_session_uuid=str(uuid4()),
                ab_callcenter_identity_uuid=(trusted_visitor or (previous.ab_callcenter_identity_uuid if previous else str(uuid4())))
                    if user._is_public() else opaque(endpoint.source, 'account:' + str(user.id)),
                ab_callcenter_identity_kind='visitor' if user._is_public() else 'customer',
                ab_callcenter_user_id=False if user._is_public() else user.id,
                ab_callcenter_endpoint_id=endpoint.id,
            )
        return values


class Session(models.Model):
    _inherit = 'discuss.channel'

    ab_callcenter_user_id = fields.Many2one('res.users', string='Verified conversation owner', readonly=True, copy=False, ondelete='restrict', groups='base.group_system')
    ab_callcenter_session_uuid = fields.Char(copy=False, readonly=True, index=True)
    ab_callcenter_identity_uuid = fields.Char(copy=False, readonly=True)
    ab_callcenter_identity_kind = fields.Selection([('customer', 'Customer'), ('visitor', 'Visitor')], readonly=True)
    ab_callcenter_endpoint_id = fields.Many2one('ab_storefront_callcenter_endpoint', readonly=True, ondelete='restrict')
    ab_callcenter_queued = fields.Boolean(readonly=True)
    _unique_session = models.Constraint('UNIQUE(ab_callcenter_session_uuid)', 'Session already exists.')

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            if any(key.startswith('ab_callcenter_') for key in values):
                endpoint = self.env['ab_storefront_callcenter_endpoint'].sudo().browse(
                    values.get('ab_callcenter_endpoint_id')).exists()
                if (not self.env.su or not endpoint or not endpoint.enabled or not endpoint.chat_enabled
                        or values.get('livechat_channel_id') != endpoint.livechat_channel_id.id
                        or values.get('livechat_operator_id') != endpoint.bridge_operator_id.partner_id.id):
                    raise AccessError(_('Website evidence is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if any(key.startswith('ab_callcenter_') for key in values) and not _CAPTURE.get():
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)

    def _ab_callcenter_authorize(self, handoff=False):
        self.ensure_one()
        endpoint = self.ab_callcenter_endpoint_id.sudo()
        if not endpoint or not endpoint.enabled or not endpoint.chat_enabled:
            raise AccessError(_('Website intake is disabled.'))
        user = self.env.user
        guest = self.env['mail.guest']._get_guest_from_context()
        if handoff:
            if user._is_public() or self.ab_callcenter_identity_kind != 'visitor' or not guest:
                raise AccessError(_('Invalid website source.'))
        elif self.ab_callcenter_identity_kind == 'customer':
            if user._is_public() or opaque(endpoint.source, 'account:' + str(user.id)) != self.ab_callcenter_identity_uuid:
                raise AccessError(_('Invalid website source.'))
            return
        elif not user._is_public():
            raise AccessError(_('Start a new chat after signing in.'))
        if not guest or not self.sudo().channel_member_ids.filtered(lambda member: member.guest_id == guest):
            raise AccessError(_('Invalid website source.'))

    def _ab_callcenter_bind_account(self):
        self._ab_callcenter_authorize(handoff=True)
        if not self.ab_callcenter_endpoint_id.sudo().lifecycle_enabled:
            raise AccessError(_('Website intake is disabled.'))
        self.lock_for_update()
        self.invalidate_recordset()
        self._ab_callcenter_authorize(handoff=True)
        if self.livechat_end_dt:
            raise SessionEnded(_('This website chat has ended.'))
        identity = opaque(self.ab_callcenter_endpoint_id.source, 'account:' + str(self.env.uid))
        guest = self.env['mail.guest']._get_guest_from_context()
        guard = _CAPTURE.set(True)
        try:
            self.sudo().write({'ab_callcenter_identity_kind': 'customer', 'ab_callcenter_identity_uuid': identity,
                               'ab_callcenter_user_id': self.env.uid})
            self.sudo()._add_members(partners=self.env.user.partner_id, post_joined_message=False)
            self.sudo()._action_unfollow(guest=guest, post_leave_message=False)
            self._ab_callcenter_lifecycle('identity_bound')
        finally:
            _CAPTURE.reset(guard)

    def _ab_callcenter_lifecycle(self, kind):
        endpoint = self.ab_callcenter_endpoint_id.sudo()
        if not endpoint.lifecycle_enabled:
            return
        event = {'version': 3, 'source': endpoint.source, 'event_uuid': str(uuid5(UUID(self.ab_callcenter_session_uuid), kind)),
            'kind': kind, 'destination': {'kind': 'livechat', 'uuid': self.ab_callcenter_session_uuid},
            'identity': {'kind': self.ab_callcenter_identity_kind, 'uuid': self.ab_callcenter_identity_uuid}}
        verified_user = self.sudo().ab_callcenter_user_id
        if kind == 'identity_bound' and verified_user:
            event['identity'].update(customer_metadata(verified_user))
        event['fingerprint'] = fingerprint(event)
        guard = _CAPTURE.set(True)
        try:
            events = self.env['ab_storefront_callcenter_lifecycle'].sudo()
            if not events.search_count([('endpoint_id', '=', endpoint.id), ('event_uuid', '=', event['event_uuid'])]):
                events.create({'endpoint_id': endpoint.id, 'event_uuid': event['event_uuid'], 'envelope': event})
        finally:
            _CAPTURE.reset(guard)

    def _close_livechat_session(self, **kwargs):
        if not self.ab_callcenter_endpoint_id:
            return super()._close_livechat_session(**kwargs)
        if not self.env.user._is_internal():
            self._ab_callcenter_authorize()
        self.lock_for_update()
        self.invalidate_recordset()
        if not self.env.user._is_internal():
            self._ab_callcenter_authorize()
        guard = _CAPTURE.set(True)
        try:
            result = super()._close_livechat_session(**kwargs)
        finally:
            _CAPTURE.reset(guard)
        self._ab_callcenter_lifecycle('session_ended')
        return result

    def _to_store_defaults(self, target):
        return super()._to_store_defaults(target) + [Store.Attr('ab_callcenter_session_uuid'), Store.Attr('ab_callcenter_identity_kind')]

    def _get_livechat_session_fields_to_store(self):
        return super()._get_livechat_session_fields_to_store() + ['ab_callcenter_session_uuid', 'ab_callcenter_identity_kind']

    def message_post(self, **kwargs):
        endpoint = self.ab_callcenter_endpoint_id.sudo()
        if not endpoint or _CAPTURE.get() or (self.env.user._is_internal() and not self.env.context.get('ab_customer_native')):
            return super().message_post(**kwargs)
        self._ab_callcenter_authorize()
        self.lock_for_update()
        self.invalidate_recordset()
        self._ab_callcenter_authorize()
        body = html2plaintext(kwargs.get('body') or '').strip()
        if len(body) > 4096 or (not body and not kwargs.get('attachment_ids')):
            raise ValidationError(_('Invalid website message.'))
        token = self.env.context.get('ab_message_uuid')
        if token:
            try:
                if str(UUID(token)) != token:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ValidationError(_('Invalid website message.')) from None
            existing = self.env['ab_storefront_callcenter_chat_event'].sudo().search([
                ('endpoint_id', '=', endpoint.id), ('event_uuid', '=', token),
            ], limit=1)
            if existing:
                if (existing.envelope['destination']['uuid'] != self.ab_callcenter_session_uuid
                        or existing.envelope['body'] != body
                        or sorted(item['id'] for item in existing.envelope.get('attachments', [])) != sorted(str(i) for i in kwargs.get('attachment_ids', []))):
                    raise ValidationError(_('Conflicting website reply.'))
                return existing.message_id
        if self.livechat_end_dt:
            raise SessionEnded(_('This website chat has ended.'))
        return super().message_post(**kwargs)

    def _message_post_after_hook(self, message, msg_vals):
        result = super()._message_post_after_hook(message, msg_vals)
        endpoint = self.ab_callcenter_endpoint_id.sudo()
        if not endpoint or _CAPTURE.get() or message.message_type != 'comment':
            return result
        visitor = self.sudo().channel_member_ids.filtered(lambda member:
            member.livechat_member_type == 'visitor' and (
                (message.author_guest_id and member.guest_id == message.author_guest_id)
                or (message.author_id and member.partner_id == message.author_id)))
        if not visitor:
            return result
        if not endpoint.enabled or not endpoint.chat_enabled:
            raise AccessError(_('Website intake is disabled.'))
        identity = self.ab_callcenter_identity_uuid
        body = html2plaintext(message.body or '').strip()
        if len(body) > 4096 or (not body and not message.attachment_ids):
            raise ValidationError(_('Invalid website message.'))
        customer_identity = {'kind': self.ab_callcenter_identity_kind, 'uuid': identity}
        verified_user = self.sudo().ab_callcenter_user_id
        if self.ab_callcenter_identity_kind == 'customer' and verified_user:
            customer_identity.update(customer_metadata(verified_user))
        self.env['ab_storefront_callcenter_chat_event']._capture(
            endpoint, {'kind': 'livechat', 'uuid': self.ab_callcenter_session_uuid},
            customer_identity, body, message,
            event_uuid=self.env.context.get('ab_message_uuid'))
        if not self.ab_callcenter_queued:
            guard = _CAPTURE.set(True)
            try:
                self.sudo().write({'ab_callcenter_queued': True})
                self.sudo().message_post(
                    author_id=endpoint.bridge_operator_id.partner_id.id,
                    body=self.with_context(lang=self.livechat_lang_id.code or self.env.lang).env._(
                        'Your message is queued for Callcenter. An agent will reply here.'),
                    message_type='comment', subtype_xmlid='mail.mt_comment')
            finally:
                _CAPTURE.reset(guard)
        return result

    def _forward_human_operator(self, chatbot_script_step=None, users=None):
        if self.ab_callcenter_endpoint_id:
            return self.env['mail.message']
        return super()._forward_human_operator(chatbot_script_step, users)


class Exchange(models.AbstractModel):
    _inherit = 'ab_storefront_callcenter_api'

    def _pending_order_ids(self, endpoint):
        return self.env['ab_storefront_callcenter_event'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('acknowledged', '=', False),
        ]).order_id.ids

    def _fetch_chat_events(self, endpoint, version):
        domain = (fields.Domain('endpoint_id', '=', endpoint.id)
                  & fields.Domain('acknowledged', '=', False)
                  & fields.Domain('exchange_version', '=', version))
        pending = self._pending_order_ids(endpoint)
        if pending:
            domain &= ~(fields.Domain('message_id.model', '=', 'sale.order')
                        & fields.Domain('message_id.res_id', 'in', pending))
        return self.env['ab_storefront_callcenter_chat_event'].sudo().search(
            domain, order='id', limit=50).mapped('envelope')

    @api.model
    def fetch_v2(self, source):
        endpoint = self._endpoint(source)
        return self._fetch_chat_events(endpoint, 2)

    @api.model
    def acknowledge_v2(self, source, event_uuid, fingerprint):
        endpoint = self._endpoint(source)
        event = self.env['ab_storefront_callcenter_chat_event'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('event_uuid', '=', event_uuid),
        ], limit=1)
        if not event or event.envelope['fingerprint'] != fingerprint:
            raise ValidationError(_('Invalid website acknowledgement.'))
        guard = _CAPTURE.set(True)
        try:
            event.write({'acknowledged': True})
        finally:
            _CAPTURE.reset(guard)
        return True

    @api.model
    def receive_v2(self, source, destination_kind, destination_uuid, token, body):
        return self._receive_reply(source, destination_kind, destination_uuid, token, body)

    def _receive_reply(self, source, destination_kind, destination_uuid, token, body, attachments=None):
        endpoint = self._endpoint(source)
        if not endpoint.chat_enabled or not endpoint.outgoing_enabled:
            raise AccessError(_('Website replies are disabled.'))
        if (not isinstance(token, str) or not 1 <= len(token) <= 128
                or not isinstance(body, str) or len(body.strip()) > 4096 or (not body.strip() and not attachments)
                or destination_kind not in ('order', 'livechat')):
            raise ValidationError(_('Invalid website reply.'))
        from ..media_protocol import validate_attachments
        try:
            validate_attachments(attachments or [])
        except ValueError:
            raise ValidationError(_('Invalid website media.')) from None
        media_fingerprint = fingerprint({'attachments': attachments or []})
        endpoint.lock_for_update()
        replies = self.env['ab_storefront_callcenter_chat_reply'].sudo()
        existing = replies.search([('endpoint_id', '=', endpoint.id), ('token', '=', token)], limit=1)
        if existing:
            if (existing.destination_kind != destination_kind or existing.destination_uuid != destination_uuid
                    or (existing.body or '') != body or (existing.media_fingerprint or fingerprint({'attachments': []})) != media_fingerprint):
                raise ValidationError(_('Conflicting website reply.'))
            return {'reference': token}
        if destination_kind == 'order':
            target = self.env['sale.order'].sudo().search([
                ('ab_callcenter_endpoint_id', '=', endpoint.id), ('ab_callcenter_uuid', '=', destination_uuid),
                ('website_id', '=', endpoint.website_id.id), ('company_id', '=', endpoint.company_id.id),
            ], limit=1)
            if target:
                target._ab_callcenter_require_chat()
        else:
            target = self.env['discuss.channel'].sudo().search([
                ('ab_callcenter_endpoint_id', '=', endpoint.id),
                ('ab_callcenter_session_uuid', '=', destination_uuid),
                ('livechat_channel_id', '=', endpoint.livechat_channel_id.id),
            ], limit=1)
        if not target:
            raise AccessError(_('Invalid website order.'))
        target.lock_for_update()
        target.invalidate_recordset()
        if destination_kind == 'order':
            target._ab_callcenter_require_open()
        if destination_kind == 'livechat' and target.livechat_end_dt:
            raise SessionEnded(_('This website chat has ended.'))
        author = endpoint.bridge_operator_id
        if not author.active or author.share or endpoint.company_id not in author.company_ids:
            raise AccessError(_('Use a dedicated Live Chat bridge operator.'))
        files = self.env['ir.attachment']._ab_exchange_files(endpoint, destination_kind, destination_uuid, token, attachments or [])
        guard = _CAPTURE.set(True)
        try:
            message = target.with_context(allowed_company_ids=endpoint.company_id.ids).message_post(
                author_id=author.partner_id.id, body=Markup('<p>%s</p>') % escape(body), attachment_ids=files.ids,
                message_type='comment', subtype_xmlid='mail.mt_comment')
            files.write({'res_model': target._name, 'res_id': target.id, 'public': False})
            voice = files.filtered(lambda file: (file.ab_website_media or {}).get('kind') == 'voice')
            if voice:
                voice._set_voice_metadata()
            replies.create({'endpoint_id': endpoint.id, 'token': token, 'destination_kind': destination_kind,
                'destination_uuid': destination_uuid, 'body': body, 'media_fingerprint': media_fingerprint, 'message_id': message.id})
        finally:
            _CAPTURE.reset(guard)
        return {'reference': token}


class EndpointLifecycle(models.Model):
    _inherit = 'ab_storefront_callcenter_endpoint'

    lifecycle_enabled = fields.Boolean(string='Enable verified conversation lifecycle', default=False)


class Lifecycle(models.Model):
    _name = 'ab_storefront_callcenter_lifecycle'
    _inherit = 'ab_storefront_callcenter_chat_event'
    _description = 'Website Conversation Lifecycle'

    message_id = fields.Many2one('mail.message', required=False, ondelete='restrict')


class LifecycleExchange(models.AbstractModel):
    _inherit = 'ab_storefront_callcenter_api'

    @api.model
    def fetch_v3(self, source):
        endpoint = self._endpoint(source)
        events = self.env['ab_storefront_callcenter_lifecycle'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('acknowledged', '=', False),
        ], order='id').mapped('envelope')
        initial = self.env['sale.order'].sudo().browse(self._pending_order_ids(endpoint))
        waiting = set(initial.mapped('ab_callcenter_uuid'))
        events = [event for event in events if event['destination']['kind'] != 'order'
                  or event['destination']['uuid'] not in waiting]
        if not any(event['kind'] in ('order_dispatched', 'session_ended') for event in events):
            return events[:50]
        pending = self.env['ab_storefront_callcenter_chat_event'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('acknowledged', '=', False),
        ]).mapped('envelope')
        blocked = {(event['destination']['kind'], event['destination']['uuid']) for event in pending}
        blocked.update(('order', value) for value in waiting)
        return [event for event in events if event['kind'] not in ('order_dispatched', 'session_ended')
                or (event['destination']['kind'], event['destination']['uuid']) not in blocked][:50]

    @api.model
    def acknowledge_v3(self, source, event_uuid, fingerprint):
        endpoint = self._endpoint(source)
        event = self.env['ab_storefront_callcenter_lifecycle'].sudo().search([
            ('endpoint_id', '=', endpoint.id), ('event_uuid', '=', event_uuid),
        ], limit=1)
        if not event or event.envelope['fingerprint'] != fingerprint:
            raise ValidationError(_('Invalid website acknowledgement.'))
        guard = _CAPTURE.set(True)
        try:
            event.write({'acknowledged': True})
        finally:
            _CAPTURE.reset(guard)
        return True


class NativeMessageAccess(models.Model):
    _inherit = 'mail.message'

    def _search(self, domain, offset=0, limit=None, order=None, *, bypass_access=False, **kwargs):
        if not self.env.su and not self.env.user._is_internal():
            channels = self.env['discuss.channel'].sudo()._search([
                ('ab_callcenter_endpoint_id', '!=', False), ('ab_callcenter_identity_kind', '=', 'customer'),
                ('ab_callcenter_user_id', '!=', self.env.uid),
            ])
            domain = fields.Domain(domain) & (fields.Domain('model', '!=', 'discuss.channel')
                | fields.Domain('res_id', 'not in', channels))
        return super()._search(domain, offset, limit, order, bypass_access=bypass_access, **kwargs)

    def _get_forbidden_access(self, operation):
        forbidden = super()._get_forbidden_access(operation)
        if self.env.su or self.env.user._is_internal():
            return forbidden
        messages = self.sudo().filtered(lambda message: message.model == 'discuss.channel' and message.res_id)
        channels = self.env['discuss.channel'].sudo().search([
            ('id', 'in', messages.mapped('res_id')), ('ab_callcenter_endpoint_id', '!=', False),
            ('ab_callcenter_identity_kind', '=', 'customer'), ('ab_callcenter_user_id', '!=', self.env.uid),
        ])
        denied = set(channels.ids)
        return forbidden | self.browse(messages.filtered(lambda message: message.res_id in denied).ids)
