from contextvars import ContextVar
from uuid import UUID

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ConcurrencyError, LockError, UserError, ValidationError


_PREFERENCE = ContextVar('website_target_preference', default=False)


class TargetPreference(models.Model):
    _name = 'ab_crm_website_target_preference'
    _description = 'Personal Website Chat Preference'

    account_id = fields.Many2one('ab_crm_messaging_account', required=True, ondelete='restrict')
    company_id = fields.Many2one(related='account_id.company_id', store=True)
    branch_id = fields.Many2one(related='account_id.branch_id', store=True)
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    employee_id = fields.Many2one('ab_hr_employee', required=True, ondelete='restrict')
    kind = fields.Selection([('order', 'Order'), ('livechat', 'Support')], required=True)
    target_uuid = fields.Char(required=True)
    last_message_id = fields.Integer()
    _unique_target = models.Constraint('UNIQUE(account_id, user_id, employee_id, kind, target_uuid)', 'Chat preference already exists.')

    @api.model_create_multi
    def create(self, values_list):
        if not _PREFERENCE.get():
            raise AccessError(_('Use personal chat controls.'))
        return super().create(values_list)

    def write(self, values):
        if not _PREFERENCE.get():
            raise AccessError(_('Use personal chat controls.'))
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Use personal chat controls.'))


class WebsiteOrder(models.Model):
    _inherit = 'ab_crm_website_order'

    origin_kind = fields.Selection([('guest', 'Guest'), ('account', 'Account')], readonly=True)
    visitor_identity = fields.Char(readonly=True, index=True)

    def write(self, values):
        if {'origin_kind', 'visitor_identity'} & values.keys():
            raise AccessError(_('Website evidence is immutable.'))
        return super().write(values)


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    def _website_targets(self):
        self.ensure_one()
        self._workspace_scope()
        streams = self._website_timeline_streams()
        scope = fields.Domain('account_id', '=', self.messaging_account_id.id) & fields.Domain('branch_id', '=', self.branch_id.id) & fields.Domain('company_id', '=', self.company_id.id)
        orders = self.env['ab_crm_website_order'].search(scope & (
            fields.Domain('conversation_id', 'in', streams.ids)
            | fields.Domain('account_identity', '=', self.website_account_identity or '__unbound__')),
            order='id desc')
        sessions = self.env['ab_crm_website_session'].search(scope & fields.Domain('conversation_id', 'in', streams.ids), order='id desc')
        return orders, sessions

    def _website_target(self, target, allow_default=False):
        orders, sessions = self._website_targets()
        if target is None and allow_default:
            record = sessions.filtered(lambda item: not item.ended)[:1] or sessions[:1]
            if record:
                return 'livechat', record
            if orders:
                return 'order', orders[:1]
            return False, False
        try:
            if not isinstance(target, dict) or set(target) != {'kind', 'uuid'} or str(UUID(target['uuid'])) != target['uuid']:
                raise ValueError()
            kind = target['kind']
            record = (orders.filtered(lambda item: item.order_uuid == target['uuid']) if kind == 'order'
                      else sessions.filtered(lambda item: item.session_uuid == target['uuid']) if kind == 'livechat' else False)
            if not record:
                raise ValueError()
        except (ValueError, TypeError, AttributeError, KeyError):
            raise AccessError(_('Invalid website target.')) from None
        return kind, record

    def _website_target_domain(self, kind, record):
        if kind == 'order':
            events = self.env['ab_crm_website_event'].search([
                ('account_id', '=', self.messaging_account_id.id), ('order_uuid', '=', record.order_uuid)])
            return fields.Domain('website_order_id', '=', record.id) | (
                fields.Domain('website_order_id', '=', False) & fields.Domain('provider_reference', 'in', events.mapped('event_uuid')))
        return fields.Domain('website_session_id', '=', record.id)

    def _workspace_visible_domain(self):
        domain = fields.Domain(super()._workspace_visible_domain())
        if len(self) != 1:
            return list(domain)
        target = self.env.context.get('ab_website_target')
        channel = self.env.context.get('ab_website_channel_targets')
        if channel is not None and self.channel_id.provider == 'website':
            if not isinstance(channel, list):
                raise AccessError(_('Invalid website target.'))
            domain &= fields.Domain.OR([self._website_target_domain(*self._website_target(item)) for item in channel])
        elif target and self.channel_id.provider == 'website':
            kind, record = self._website_target(target)
            domain &= self._website_target_domain(kind, record)
        return list(domain)

    def _website_lock_account(self):
        try:
            self.messaging_account_id.lock_for_update()
        except LockError:
            raise ConcurrencyError('Concurrent website chat update') from None

    def _website_preference(self, kind, record, create=False):
        actor, stores = self._workspace_scope()
        target_uuid = record.order_uuid if kind == 'order' else record.session_uuid
        preferences = self.env['ab_crm_website_target_preference'].sudo()
        domain = [('account_id', '=', self.messaging_account_id.id), ('user_id', '=', self.env.uid),
                  ('employee_id', '=', actor.employee_id.id), ('kind', '=', kind), ('target_uuid', '=', target_uuid)]
        preference = preferences.search(domain, limit=1)
        if not preference and create:
            self._website_lock_account()
            preference = preferences.search(domain, limit=1)
            if not preference:
                positions = self.env['ab_crm_workspace_read'].sudo().search([
                    ('conversation_id', 'in', self._website_timeline_streams().ids), ('user_id', '=', self.env.uid),
                    ('employee_id', '=', actor.employee_id.id), ('company_id', '=', self.company_id.id)])
                seen = {position.conversation_id.id: position.last_message_id.id for position in positions}
                messages = self._website_target_messages(kind, record).filtered(lambda item:
                    item.direction == 'in' and not item.historical and not item.website_closure_notice)
                unread = messages.filtered(lambda item: item.id > seen.get(item.conversation_id.id, 0))
                initial = max(messages.filtered(lambda item: not unread or item.id < unread[0].id).ids, default=0)
                flag = _PREFERENCE.set(True)
                try:
                    preference = preferences.create({key: value for key, operator, value in domain} | {
                        'last_message_id': initial})
                finally:
                    _PREFERENCE.reset(flag)
        return preference

    def _website_target_messages(self, kind, record):
        return self.env['ab_crm_message'].search(
            fields.Domain('conversation_id', 'in', self._website_timeline_streams().ids)
            & self._website_target_domain(kind, record), order='id')

    def _website_target_data(self, kind, record):
        preference = self._website_preference(kind, record, create=True)
        messages = self._website_target_messages(kind, record).filtered(lambda item:
            item.direction == 'in' and not item.historical and not item.website_closure_notice)
        return {'kind': kind, 'uuid': record.order_uuid if kind == 'order' else record.session_uuid,
            'label': (record.public_reference or record.reference) if kind == 'order' else _('Support') + ' · ' + record.session_uuid[:8],
            'closed': record.chat_closed if kind == 'order' else record.ended,
            'unread': len(messages.filtered(lambda item: item.id > preference.last_message_id)) if preference else 0}

    def workspace_reply(self, message_id, target=None, combine=False):
        if self.channel_id.provider != 'website':
            return super().workspace_reply(message_id)
        kind, record = self._website_target(target)
        message = self._website_target_messages(kind, record).filtered(lambda item: item.id == message_id)
        if not message or message.website_closure_notice:
            return {'available': False}
        detail = self.workspace_detail(target=target, through_id=message.id, combine=combine)
        return {'available': True, 'focus_message_id': message.id,
                'messages': detail['messages'], 'has_older': detail['has_older']}

    def workspace_focus(self, message_id):
        if self.channel_id.provider != 'website':
            return super().workspace_focus(message_id)
        self._workspace_scope()
        orders, sessions = self._website_targets()
        for kind, records in [('order', orders), ('livechat', sessions)]:
            for record in records:
                message = self._website_target_messages(kind, record).filtered(lambda item: item.id == message_id)
                if message and not message.website_closure_notice:
                    target = {'kind': kind, 'uuid': record.order_uuid if kind == 'order' else record.session_uuid}
                    detail = self.workspace_detail(target=target, through_id=message.id)
                    detail['focus_message_id'] = message.id
                    return detail
        raise AccessError(_('Invalid website target.'))

    def workspace_acknowledge(self, message_id, target=None, combine=False):
        if self.channel_id.provider != 'website':
            return super().workspace_acknowledge(message_id)
        kind, record = self._website_target(target or self.env.context.get('ab_website_target'))
        if type(message_id) is not int:
            raise AccessError(_('Invalid read position.'))
        message = self._website_target_messages(kind, record).filtered(lambda item: item.id == message_id)
        if not message or message.website_closure_notice:
            raise AccessError(_('Invalid read position.'))
        if type(combine) is not bool:
            raise ValidationError(_('Invalid conversation search.'))
        if combine:
            orders, sessions = self._website_targets()
            for item in orders if kind == 'order' else sessions:
                incoming = self._website_target_messages(kind, item).filtered(lambda value:
                    not value.website_closure_notice and value.direction == 'in'
                    and (value.timeline_at, value.id) <= (message.timeline_at, message.id))
                if incoming:
                    self.workspace_acknowledge(max(incoming.ids), target={'kind': kind,
                        'uuid': item.order_uuid if kind == 'order' else item.session_uuid})
            return True
        self._website_lock_account()
        preference = self._website_preference(kind, record, create=True)
        if message.id > preference.last_message_id:
            flag = _PREFERENCE.set(True)
            try:
                preference.write({'last_message_id': message.id})
            finally:
                _PREFERENCE.reset(flag)
        return True

    def _workspace_unread_messages(self, session):
        messages = super()._workspace_unread_messages(session).filtered(lambda item: not item.website_closure_notice)
        visible = self.env['ab_crm_message']
        for conversation in self:
            scoped = messages.filtered(lambda item: item.conversation_id == conversation)
            if conversation.channel_id.provider != 'website':
                visible |= scoped
                continue
            orders, sessions = conversation._website_targets()
            remaining = scoped
            for kind, records in [('order', orders), ('livechat', sessions)]:
                for record in records:
                    target_messages = conversation._website_target_messages(kind, record) & scoped
                    preference = conversation._website_preference(kind, record, create=True)
                    visible |= target_messages.filtered(lambda item: item.id > preference.last_message_id)
                    remaining -= target_messages
            visible |= remaining
        return visible

    def _workspace_inbox_rows(self, session):
        self = self.with_context(ab_website_target=None, ab_website_channel_targets=None)
        rows = super()._workspace_inbox_rows(session)
        for row in rows:
            conversation = self.browse(row['id'])
            if conversation.channel_id.provider != 'website':
                continue
            messages = self.env['ab_crm_message'].search([
                ('conversation_id', 'in', conversation._website_timeline_streams().ids),
                ('website_closure_notice', '=', False)], order='id desc', limit=1)
            row['preview'] = messages.body or ''
            orders, sessions = conversation._website_targets()
            row['website_targets'] = [conversation._website_target_data('order', item) for item in orders] + [
                conversation._website_target_data('livechat', item) for item in sessions]
            row['unread'] = sum(item['unread'] for item in row['website_targets'])
        return rows

    def _workspace_activity(self):
        if self.channel_id.provider != 'website':
            return super()._workspace_activity()
        messages = self.env['ab_crm_message'].search([
            ('conversation_id', 'in', self._website_timeline_streams().ids),
            ('website_closure_notice', '=', False), ('historical', '=', False), ('direction', '=', 'in')])
        return max(((fields.Datetime.to_string(message.create_date), message.id)
                    for message in messages),
                   default=('1970-01-01 00:00:00', 0))

    def website_action_reply(self, body, website_order_id=False, attachments=None, reply_id=False,
                           website_session_id=False, submission_uuid=False, target=None):
        self._workspace_scope()
        if target is not None:
            kind, record = self._website_target(target)
            website_order_id, website_session_id = (record.id, False) if kind == 'order' else (False, record.id)
        elif website_order_id or website_session_id:
            orders, sessions = self._website_targets()
            record = orders.filtered(lambda item: item.id == website_order_id) if website_order_id else sessions.filtered(lambda item: item.id == website_session_id)
            if not record or (website_order_id and website_session_id):
                raise AccessError(_('Invalid website target.'))
            target = {'kind': 'order' if website_order_id else 'livechat',
                'uuid': record.order_uuid if website_order_id else record.session_uuid}
        elif not website_order_id and not website_session_id and not reply_id:
            orders, sessions = self._website_targets()
            if len(orders.filtered(lambda item: item.chat_ready and not item.chat_closed)) + len(sessions.filtered(lambda item: not item.ended)) != 1:
                raise ValidationError(_('Select a Support session or order.'))
        with self.env.cr.savepoint():
            return super(Conversation, self.with_context(ab_website_target=target) if target else self).website_action_reply(body, website_order_id, attachments, reply_id,
                website_session_id, submission_uuid)

    def workspace_detail(self, *args, target=None, combine=False, **kwargs):
        if self.channel_id.provider != 'website':
            return super().workspace_detail(*args, **kwargs)
        self._workspace_scope()
        if self.website_canonical_id:
            return self.website_canonical_id.workspace_detail(*args, target=target, combine=combine, **kwargs)
        if type(combine) is not bool:
            raise ValidationError(_('Invalid conversation search.'))
        kind, record = self._website_target(target or self.env.context.get('ab_website_target'), allow_default=True)
        if not record:
            return super().workspace_detail(*args, **kwargs)
        orders, sessions = self._website_targets()
        targets = [(item_kind, item, self._website_target_data(item_kind, item))
            for item_kind, records in [('livechat', sessions), ('order', orders)] for item in records]
        channel = [(kind, record)]
        if combine:
            visible = [(item_kind, item) for item_kind, item, data in targets]
            channel = [(item_kind, item) for item_kind, item in visible if item_kind == kind]
            if not channel and visible:
                kind = visible[0][0]
                channel = [(item_kind, item) for item_kind, item in visible if item_kind == kind]
            if channel:
                opened = [(item_kind, item) for item_kind, item in channel
                    if not (item.chat_closed if item_kind == 'order' else item.ended)]
                if (kind, record) not in (opened or channel):
                    kind, record = (opened or channel)[0]
        selected = {'kind': kind, 'uuid': record.order_uuid if kind == 'order' else record.session_uuid}
        channel_targets = [{'kind': item_kind, 'uuid': item.order_uuid if item_kind == 'order' else item.session_uuid}
            for item_kind, item in channel]
        scoped = self.with_context(ab_website_target=selected,
            ab_website_channel_targets=channel_targets if combine else None)
        result = super(Conversation, scoped).workspace_detail(*args, **kwargs)
        result['website_targets'] = [data for item_kind, item, data in targets]
        result['website_target'] = selected
        result['website_combined'] = combine
        result['website_header_origin_kind'] = kind
        result['website_header_origin'] = _('Support') if kind == 'livechat' else _('Orders')
        result['website_reply_order_id'] = record.id if kind == 'order' else False
        result['website_reply_session_id'] = record.id if kind == 'livechat' else False
        closed = record.chat_closed if kind == 'order' else record.ended
        result['website_target_closed'] = bool(closed or not channel)
        result['can_send'] = bool(result['can_send'] and not closed and channel)
        if closed:
            result['send_reason'] = _('This website chat has ended.')
        incoming = self.env['ab_crm_message']
        target_messages = {}
        target_by_message = {}
        for item_kind, item in channel:
            item_target = {'kind': item_kind, 'uuid': item.order_uuid if item_kind == 'order' else item.session_uuid}
            messages = self._website_target_messages(item_kind, item)
            target_messages[item_target['uuid']] = messages
            target_by_message.update({message.id: item_target for message in messages})
            preference = self._website_preference(item_kind, item, create=True)
            incoming |= messages.filtered(lambda value: value.direction == 'in' and not value.historical
                and not value.website_closure_notice and value.id > preference.last_message_id)
        result['first_unread_message_id'] = min(incoming.ids, default=False)
        result['unread_count'] = len(incoming)
        for message in result['messages']:
            evidence = self.env['ab_crm_message'].browse(message['id'])
            message['website_target'] = target_by_message.get(message['id'])
            message['item_type'] = 'information' if evidence.website_closure_notice else 'message'
            if evidence.website_closure_notice:
                message.update(media=[], quote=False, reactions=[], can_reply=False, actions={})
        events = self.env['ab_crm_website_chat_event'].search([
            ('account_id', '=', self.messaging_account_id.id),
            ('branch_id', '=', self.branch_id.id), ('company_id', '=', self.company_id.id)], order='id')
        for item_kind, item in channel:
            item_target = {'kind': item_kind, 'uuid': item.order_uuid if item_kind == 'order' else item.session_uuid}
            if target_messages[item_target['uuid']].filtered('website_closure_notice'):
                continue
            lifecycle = events.filtered(lambda value: value.envelope.get('destination') == item_target
                and value.envelope.get('kind') == ('order_dispatched' if item_kind == 'order' else 'session_ended'))[:1]
            if lifecycle and (item_kind == 'order' or (item.identity_kind == 'visitor' and not item.account_identity)):
                result['messages'].append({'id': -lifecycle.id, 'item_type': 'information',
                    'website_target': item_target,
                    'body': _('This chat has ended. Your order has been sent for delivery.') if item_kind == 'order' else _('The guest has left the conversation.'),
                    'timestamp': fields.Datetime.to_string(lifecycle.create_date), 'direction': 'information',
                    'historical': False, 'media': [], 'reactions': [], 'quote': False, 'actions': {}})
        information = {}
        for item in result['messages']:
            if item['item_type'] == 'information':
                key = (item.get('website_target') or selected)['uuid']
                previous = information.get(key)
                if not previous or (item['timestamp'] or '', item['id']) < (previous['timestamp'] or '', previous['id']):
                    information[key] = item
        if information:
            result['messages'] = [item for item in result['messages'] if item['item_type'] != 'information'
                or information[(item.get('website_target') or selected)['uuid']] is item]
            result['website_has_closure_notice'] = True
            if closed:
                result['send_reason'] = ''
        if kwargs.get('query') or kwargs.get('message_ids') is not None:
            result['messages'] = [item for item in result['messages'] if item['item_type'] != 'information']
        elif kwargs.get('before_id') or kwargs.get('through_id'):
            anchor = self.env['ab_crm_message'].browse(kwargs.get('before_id') or kwargs.get('through_id')).exists()
            if anchor and anchor.id in target_by_message:
                result['messages'] = [item for item in result['messages'] if item['item_type'] != 'information'
                    or item['timestamp'] < fields.Datetime.to_string(anchor.timeline_at)]
        result['messages'].sort(key=lambda item: (item['timestamp'] or '', item['item_type'] == 'information', item['id']))
        return result
