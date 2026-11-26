from odoo.addons.ab_crm_sales_workspace.models.request_cache import cached_scope
from contextvars import ContextVar
from uuid import UUID

from psycopg2.errors import UniqueViolation

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
    _actor_scope_idx = models.Index('(user_id, employee_id, company_id, last_message_id)')
    _unique_target = models.Constraint('UNIQUE(account_id, user_id, employee_id, kind, target_uuid)', 'Chat preference already exists.')

    @api.model_create_multi
    def create(self, values_list):
        if not _PREFERENCE.get():
            raise AccessError(_('Use personal chat controls.'))
        return super().create(values_list)

    def write(self, values):
        if not _PREFERENCE.get():
            raise AccessError(_('Use personal chat controls.'))
        result = super().write(values)
        self._invalidate_workspace()
        return result

    def _invalidate_workspace(self):
        for preference in self:
            account = preference.account_id
            self.env['ab_crm_conversation'].sudo().search([
                ('channel_id', '=', account.channel_id.id),
                ('company_id', '=', preference.company_id.id),
                ('branch_id', '=', preference.branch_id.id)], limit=1)._invalidate_workspace()

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

    @cached_scope
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

    @cached_scope
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

    @cached_scope
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
            if not isinstance(channel, list) or len(channel) != 1:
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

    @cached_scope
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
                streams = self._website_timeline_streams()
                message_domain = (fields.Domain('conversation_id', 'in', streams.ids)
                          & self._website_target_domain(kind, record)
                          & fields.Domain('direction', '=', 'in')
                          & fields.Domain('historical', '=', False)
                          & fields.Domain('website_closure_notice', '=', False))
                message_model = self.env['ab_crm_message']
                unread = message_model.search(message_domain & super(Conversation, streams)._workspace_unread_domain(actor),
                                              order='id', limit=1)
                initial_domain = message_domain & fields.Domain('id', '<', unread.id) if unread else message_domain
                initial = message_model.search(initial_domain, order='id desc', limit=1).id or 0
                flag = _PREFERENCE.set(True)
                try:
                    try:
                        with self.env.cr.savepoint():
                            preference = preferences.create({key: value for key, operator, value in domain} | {
                                'last_message_id': initial})
                            preference.flush_recordset()
                    except UniqueViolation as error:
                        if error.diag.constraint_name != 'ab_crm_website_target_preference_unique_target':
                            raise
                        raise ConcurrencyError('Concurrent website chat preference creation') from None
                finally:
                    _PREFERENCE.reset(flag)
        return preference

    def _website_target_messages(self, kind, record):
        return self.env['ab_crm_message'].search(
            fields.Domain('conversation_id', 'in', self._website_timeline_streams().ids)
            & self._website_target_domain(kind, record), order='id')

    def _website_target_data(self, kind, record):
        preference = self._website_preference(kind, record, create=True)
        domain = (fields.Domain('conversation_id', 'in', self._website_timeline_streams().ids)
                  & self._website_target_domain(kind, record)
                  & fields.Domain('direction', '=', 'in') & fields.Domain('historical', '=', False)
                  & fields.Domain('website_closure_notice', '=', False)
                  & fields.Domain('id', '>', preference.last_message_id))
        unread = self.env['ab_crm_message'].search_count(domain) if preference else 0
        return {'kind': kind, 'uuid': record.order_uuid if kind == 'order' else record.session_uuid,
            'label': (record.public_reference or record.reference) if kind == 'order' else _('Support') + ' · ' + record.session_uuid[:8],
            'closed': record.chat_closed if kind == 'order' else record.ended,
            'unread': unread}

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

    def workspace_focus(self, message_id, target=None):
        if self.channel_id.provider != 'website':
            return super().workspace_focus(message_id)
        self._workspace_scope()
        orders, sessions = self._website_targets()
        if target is not None:
            kind, record = self._website_target(target)
            orders, sessions = (record, sessions.browse()) if kind == 'order' else (orders.browse(), record)
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

    def _workspace_chat_candidates(self, session):
        ordinary = self.filtered(lambda conversation: conversation.channel_id.provider != 'website')
        result = super(Conversation, ordinary)._workspace_chat_candidates(session)
        websites = self - ordinary
        if not websites:
            return result
        aliases = websites.with_context(active_test=False).search([
            ('website_canonical_id', 'in', websites.ids),
            ('company_id', '=', session.company_id.id)])
        streams = websites | aliases
        canonical = {item.id: (item.website_canonical_id or item).id for item in streams}
        accounts = websites.messaging_account_id
        orders = self.env['ab_crm_website_order'].search([
            ('account_id', 'in', accounts.ids), ('company_id', '=', session.company_id.id),
            ('branch_id', 'in', websites.branch_id.ids),
            '|', ('conversation_id', 'in', streams.ids),
            ('account_identity', 'in', websites.mapped('website_account_identity'))])
        sessions = self.env['ab_crm_website_session'].search([
            ('account_id', 'in', accounts.ids), ('company_id', '=', session.company_id.id),
            ('branch_id', 'in', websites.branch_id.ids), ('conversation_id', 'in', streams.ids)])
        owners = {(item.messaging_account_id.id, item.website_account_identity): item.id
                  for item in websites if item.website_account_identity}
        targets = {}
        by_uuid = {}
        for kind, records in [('order', orders), ('livechat', sessions)]:
            for record in records:
                cid = canonical.get(record.conversation_id.id)
                if kind == 'order':
                    cid = owners.get((record.account_id.id, record.account_identity), cid)
                if not cid:
                    continue
                uuid = record.order_uuid if kind == 'order' else record.session_uuid
                key = f'website:{record.account_id.id}:{kind}:{uuid}'
                targets[(kind, record.id)] = dict(id=cid, group_key=key,
                    website_target={'kind': kind, 'uuid': uuid},
                    activity_cursor=['1970-01-01 00:00:00', 0, key])
                if kind == 'order':
                    by_uuid[(record.account_id.id, uuid)] = record.id
        message_model = self.env['ab_crm_message']
        incoming = [('conversation_id', 'in', streams.ids), ('direction', '=', 'in'),
                    ('historical', '=', False), ('website_closure_notice', '=', False)]
        for field, kind in [('website_order_id', 'order'), ('website_session_id', 'livechat')]:
            groups = message_model._read_group(incoming + [(field, '!=', False)],
                [field], ['create_date:max', 'id:max'])
            for record, at, mid in groups:
                candidate = targets.get((kind, record.id))
                if candidate:
                    candidate['activity_cursor'] = [fields.Datetime.to_string(at), mid, candidate['group_key']]
        events = self.env['ab_crm_website_event'].search([
            ('account_id', 'in', accounts.ids), ('order_uuid', 'in', orders.mapped('order_uuid'))])
        event_targets = {event.event_uuid: by_uuid.get((event.account_id.id, event.order_uuid)) for event in events}
        if event_targets:
            legacy = message_model._read_group(incoming + [
                ('website_order_id', '=', False), ('provider_reference', 'in', list(event_targets))],
                ['provider_reference'], ['create_date:max', 'id:max'])
            for reference, at, mid in legacy:
                candidate = targets.get(('order', event_targets[reference]))
                if candidate:
                    activity = [fields.Datetime.to_string(at), mid, candidate['group_key']]
                    candidate['activity_cursor'] = max(candidate['activity_cursor'], activity)
        return result + list(targets.values())

    def _workspace_serialize_candidate(self, session, candidate):
        if self.channel_id.provider != 'website':
            return super()._workspace_serialize_candidate(session, candidate)
        target = candidate['website_target']
        self._website_target(target)
        row = {'id': self.id, 'customer_id': self.customer_id.id, 'destination': self.external_key,
               'display_destination': self._display_destination(), 'name': self._customer_display_name(),
               'provider': 'website', 'channels': ['website']}

        rows = self._workspace_chat_rows(row, selected_target=target)
        return next(item for item in rows if item['group_key'] == candidate['group_key'])

    def _workspace_chat_rows(self, row, selected_target=None):
        if self.channel_id.provider != 'website':
            return super()._workspace_chat_rows(row)
        orders, sessions = self._website_targets()
        if selected_target is not None:
            kind, record = self._website_target(selected_target)
            orders, sessions = (record, sessions.browse()) if kind == 'order' else (orders.browse(), record)
        items = []
        for kind, records in [('order', orders), ('livechat', sessions)]:
            for record in records:
                data = self._website_target_data(kind, record)
                target = {'kind': kind, 'uuid': data['uuid']}
                domain = (fields.Domain('conversation_id', 'in', self._website_timeline_streams().ids)
                          & self._website_target_domain(kind, record)
                          & fields.Domain('website_closure_notice', '=', False))
                message_model = self.env['ab_crm_message']
                groups = message_model._read_group(
                    domain & fields.Domain('direction', '=', 'in') & fields.Domain('historical', '=', False),
                    [], ['create_date:max', 'id:max'])
                at, mid = groups[0]
                activity = (fields.Datetime.to_string(at), mid) if mid else ('1970-01-01 00:00:00', 0)
                preview = message_model.search(domain, order='timeline_at desc, id desc', limit=1).body or ''
                key = f"website:{self.messaging_account_id.id}:{kind}:{data['uuid']}"
                item = dict(row, website_target=target, website_target_label=data['label'],
                            website_target_closed=data['closed'], unread=data['unread'],
                            preview=preview,
                            group_key=key, activity_cursor=[*activity, key])
                item['streams'] = [dict(item, account_id=self.messaging_account_id.id, label=data['label'])]
                items.append(item)
        return items

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
        selected = {'kind': kind, 'uuid': record.order_uuid if kind == 'order' else record.session_uuid}
        scoped = self.with_context(ab_website_target=selected,
            ab_website_channel_targets=None)
        result = super(Conversation, scoped).workspace_detail(*args, **kwargs)
        result['website_targets'] = [data for item_kind, item, data in targets]
        result['website_target'] = selected
        result['website_combined'] = False
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


class ChatterAPI(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    def _notification_streams(self, conversation):
        if conversation.channel_id.provider == 'website':
            return conversation._website_timeline_streams()
        return super()._notification_streams(conversation)

    def _notification_group_domain(self, conversation, target):
        if conversation.channel_id.provider == 'website':
            kind, record = conversation._website_target(target)
            return (fields.Domain('conversation_id', 'in', conversation._website_timeline_streams().ids)
                    & conversation._website_target_domain(kind, record))
        return super()._notification_group_domain(conversation, target)

    def _notification_candidate_domain(self, session):
        domain = fields.Domain(super()._notification_candidate_domain(session))
        domain &= fields.Domain('website_closure_notice', '=', False)
        preferences = self.env['ab_crm_website_target_preference'].sudo().search([
            ('user_id', '=', self.env.uid), ('employee_id', '=', session.employee_id.id),
            ('company_id', '=', session.company_id.id), ('last_message_id', '>', 0)])
        orders = preferences.filtered(lambda item: item.kind == 'order')
        events = self.env['ab_crm_website_event'].search([
            ('account_id', 'in', orders.account_id.ids),
            ('order_uuid', 'in', orders.mapped('target_uuid'))]) if orders else self.env['ab_crm_website_event']
        references = {}
        for event in events:
            references.setdefault((event.account_id.id, event.order_uuid), []).append(event.event_uuid)
        for preference in preferences:
            uuid_field, message_field = (
                ('order_uuid', 'website_order_id') if preference.kind == 'order'
                else ('session_uuid', 'website_session_id'))
            channel = fields.Domain('conversation_id.channel_id', '=', preference.account_id.channel_id.id)
            target = fields.Domain(message_field + '.' + uuid_field, '=', preference.target_uuid) & channel
            if preference.kind == 'order':
                target |= (channel & fields.Domain('website_order_id', '=', False)
                           & fields.Domain('provider_reference', 'in',
                               references.get((preference.account_id.id, preference.target_uuid), [])))
            domain &= ~target | fields.Domain('id', '>', preference.last_message_id)
        return list(domain)

    def _notification_conversation(self, conversation):
        if conversation.channel_id.provider == 'website':
            return conversation.website_canonical_id or conversation
        return super()._notification_conversation(conversation)

    def _alert_conversations(self, conversation, target):
        if conversation.channel_id.provider == 'website':
            conversation._website_target(target)
            return conversation._website_timeline_streams()
        return super()._alert_conversations(conversation, target)

    @cached_scope
    def _notification_chat(self, message):
        conversation = message.conversation_id
        if conversation.channel_id.provider != 'website':
            return super()._notification_chat(message)
        conversation._workspace_scope()
        if message.website_order_id:
            target = {'kind': 'order', 'uuid': message.website_order_id.order_uuid}
        elif message.website_session_id:
            target = {'kind': 'livechat', 'uuid': message.website_session_id.session_uuid}
        else:
            event = self.env['ab_crm_website_event'].search([
                ('account_id', '=', conversation.messaging_account_id.id),
                ('event_uuid', '=', message.provider_reference)], limit=1)
            if not event:
                return super()._notification_chat(message)
            target = {'kind': 'order', 'uuid': event.order_uuid}
        conversation._website_target(target)
        return f"website:{conversation.messaging_account_id.id}:{target['kind']}:{target['uuid']}", target
