from .request_cache import request_cache
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class AlertPosition(models.Model):
    _name = 'ab_crm_workspace_alert'
    _description = 'Employee Conversation Alert Acknowledgment'

    conversation_id = fields.Many2one(
        'ab_crm_conversation', required=True, ondelete='restrict'
    )
    user_id = fields.Many2one('res.users', required=True, ondelete='restrict')
    employee_id = fields.Many2one('ab_hr_employee', required=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, ondelete='restrict')
    branch_id = fields.Many2one(related='conversation_id.branch_id', store=True)
    acknowledged_ids = fields.Many2many(
        'ab_crm_message', string='Acknowledged messages'
    )
    _actor_scope_idx = models.Index('(user_id, employee_id, company_id, conversation_id)')
    _alert_unique = models.Constraint(
        'UNIQUE(conversation_id, user_id, employee_id, company_id)',
        'Only one alert position per employee and conversation is allowed.',
    )

    @api.model_create_multi
    def create(self, values_list):
        if not self.env.su:
            raise AccessError(
                _('Use conversation notifications to acknowledge messages.')
            )
        return super().create(values_list)

    def write(self, values):
        if not self.env.su:
            raise AccessError(
                _('Use conversation notifications to acknowledge messages.')
            )
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Use conversation notifications to acknowledge messages.'))


class ChatterAPI(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    def _notification_message_domain(self):
        return []

    def _notification_conversation(self, conversation):
        return conversation

    def _alert_conversations(self, conversation, target):
        return conversation

    def _notification_chat(self, message):
        return str(message.conversation_id.id), None

    @api.model
    @request_cache
    def notifications(self, token, after_id=0):
        session = self._session(token)
        if type(after_id) is not int or after_id < 0:
            raise AccessError(_('Invalid notification position.'))
        branches = self._directory_branches(session)
        conversations = self.env['ab_crm_conversation'].search(
            [
                ('company_id', '=', session.company_id.id),
                ('branch_id', 'in', branches.ids),
                ('message_ids.direction', '=', 'in'),
                ('id', '>', after_id),
            ],
            order='id',
            limit=51,
        )
        page = conversations[:50]
        alert_conversations = page.browse()
        for conversation in page:
            alert_conversations |= self._notification_conversation(conversation)
        positions = (
            self.env['ab_crm_workspace_alert']
            .sudo()
            .search(
                [
                    ('user_id', '=', self.env.uid),
                    ('employee_id', '=', session.employee_id.id),
                    ('company_id', '=', session.company_id.id),
                    ('conversation_id', 'in', alert_conversations.ids),
                ]
            )
        )
        acknowledged = {
            row.conversation_id.id: set(row.acknowledged_ids.ids) for row in positions
        }
        authorized = page.browse()
        for conversation in page.sorted(lambda record: (record.branch_id.id, record.id)):
            try:
                conversation.with_context(ab_chatter_session_token=token)._workspace_scope()
            except (AccessError, UserError):
                continue
            conversation.with_context(ab_chatter_session_token=token)._auto_link_matching_customer()
            authorized |= conversation
        messages = authorized.with_context(ab_chatter_session_token=token)._workspace_unread_messages(session).filtered_domain(self._notification_message_domain())
        groups = {}
        unread_counts = {}
        for message in messages:
            cid = self._notification_conversation(message.conversation_id).id
            key, target = self._notification_chat(message)
            unread_counts[key] = unread_counts.get(key, 0) + 1
            if message.id not in acknowledged.get(cid, set()):
                groups.setdefault((cid, key), (target, []))[1].append(message)
        return {
            'cursor': page[-1:].id or after_id,
            'has_more': len(conversations) > 50,
            'items': [self._notification_item(session, cid, key, target, pending, unread_counts[key])
                      for (cid, key), (target, pending) in groups.items()],
        }

    @api.model
    @request_cache
    def notifications_v2(self, token, cursor=0, limit=100, conversation_ids=None):
        session = self._session(token)
        if (type(cursor) is not int or cursor < 0 or type(limit) is not int
                or not 1 <= limit <= 100 or (conversation_ids is not None and (
                    not isinstance(conversation_ids, list) or len(conversation_ids) > 50
                    or any(type(cid) is not int or cid <= 0 for cid in conversation_ids)))):
            raise AccessError(self.env._('Invalid notification position.'))
        actor = [('user_id', '=', self.env.uid),
                 ('employee_id', '=', session.employee_id.id),
                 ('company_id', '=', session.company_id.id)]
        branches = self._directory_branches(session)
        scope = fields.Domain('conversation_id.company_id', '=', session.company_id.id)
        scope &= fields.Domain('conversation_id.branch_id', 'in', branches.ids)
        scope &= fields.Domain('conversation_id.channel_id.active', '=', True)
        scope &= fields.Domain('conversation_id.active', '=', True)
        requested = self.env['ab_crm_conversation'].with_context(ab_chatter_session_token=token)
        if conversation_ids is not None:
            requested = requested.browse(conversation_ids).exists()
            if len(requested) != len(set(conversation_ids)):
                raise AccessError(self.env._('Invalid notification position.'))
            streams = requested.browse()
            for conversation in requested:
                conversation._workspace_scope()
                canonical = self._notification_conversation(conversation)
                streams |= self._notification_streams(canonical)
            scope &= fields.Domain('conversation_id', 'in', streams.ids)
        positions = self.env['ab_crm_workspace_read'].sudo().search(actor + [
            ('conversation_id.company_id', '=', session.company_id.id),
            ('conversation_id.branch_id', 'in', branches.ids)])
        buckets = {}
        for position in positions:
            buckets.setdefault(position.last_message_id.id or 0, []).append(position.conversation_id.id)
        unread = fields.Domain('conversation_id', 'not in', positions.conversation_id.ids)
        unread |= fields.Domain.OR([
            fields.Domain('conversation_id', 'in', ids) & fields.Domain('id', '>', mid)
            for mid, ids in buckets.items()])
        unread_domain = (scope & unread & fields.Domain('direction', '=', 'in')
                         & fields.Domain('historical', '=', False)
                         & fields.Domain(self._notification_message_domain())
                         & fields.Domain(self.env['ab_crm_conversation']._workspace_visible_domain())
                         & fields.Domain(self._notification_candidate_domain(session)))
        domain = (unread_domain & fields.Domain('id', '>', cursor)
                  & fields.Domain('id', 'in', self.env['ab_crm_message'].sudo()._search(
                      fields.Domain('workspace_alert_ids', 'not any',
                                    self.env['ab_crm_workspace_alert'].sudo()._search(actor)))))
        messages = self.env['ab_crm_message'].with_context(ab_chatter_session_token=token).search(
            domain, order='id', limit=limit + 1)
        page = messages[:limit]
        authorized = page.conversation_id.browse()
        for conversation in page.conversation_id:
            try:
                conversation._workspace_scope()
            except (AccessError, UserError):
                continue
            authorized |= conversation
        groups = {}
        for message in page:
            if message.conversation_id not in authorized:
                continue
            key, target = self._notification_chat(message)
            cid = self._notification_conversation(message.conversation_id).id
            groups.setdefault((cid, key), (target, []))[1].append(message)
        counts = self.env['ab_crm_message'].with_context(ab_chatter_session_token=token)._read_group(
            unread_domain & fields.Domain('conversation_id', 'in', authorized.ids),
            ['conversation_id'], ['__count'])
        counts = {conversation.id: count for conversation, count in counts}
        items = []
        for (cid, key), (target, pending) in groups.items():
            count = counts.get(cid, 0)
            if target is not None:
                conversation = self.env['ab_crm_conversation'].with_context(
                    ab_chatter_session_token=token).browse(cid)
                count = self.env['ab_crm_message'].with_context(ab_chatter_session_token=token).search_count(
                    unread_domain & self._notification_group_domain(conversation, target))
            items.append(self._notification_item(session, cid, key, target, pending, count))
        return {
            'version': 2,
            'cursor': page[-1:].id or cursor,
            'has_more': len(messages) > limit,
            'replace_conversation_ids': requested.ids if conversation_ids is not None else None,
            'items': items,
        }

    def _notification_group_domain(self, conversation, target):
        return fields.Domain('conversation_id', '=', conversation.id)

    def _notification_candidate_domain(self, session):
        return []

    def _notification_streams(self, conversation):
        return conversation

    def _notification_item(self, session, cid, key, target, pending, unread_count=None):
        message = pending[-1]
        conversation = message.conversation_id
        return {
            'alert_key': f'{self.env.uid}:{session.employee_id.id}:{session.company_id.id}:{key}',
            'conversation_id': cid, 'website_target': target,
            'customer_group_key': conversation.customer_group_key,
            'display_destination': conversation._display_destination(),
            'conversation_label': conversation.messaging_account_id.name,
            'unread_count': len(pending) if unread_count is None else unread_count,
            'latest_message_id': message.id,
            'message_ids': [item.id for item in pending], 'count': len(pending),
            'preview': (message.body or '')[:160],
            'name': conversation._customer_display_name(),
            'provider': conversation.channel_id.provider,
        }

    @api.model
    def acknowledge_alert(self, token, conversation_id, message_ids, target=None):
        session = self._session(token)
        if (
            not isinstance(message_ids, list)
            or not message_ids
            or any(type(mid) is not int or mid <= 0 for mid in message_ids)
        ):
            raise AccessError(_('Invalid notification position.'))
        conversation = (
            self.env['ab_crm_conversation']
            .with_context(ab_chatter_session_token=token)
            .browse(conversation_id)
            .exists()
        )
        conversation._workspace_scope()
        allowed = self._alert_conversations(conversation, target)
        messages = self.env['ab_crm_message'].with_context(ab_chatter_session_token=token).browse(message_ids).exists()
        messages.check_access('read')
        if len(messages) != len(set(message_ids)) or any(
            message.conversation_id not in allowed or message.direction != 'in'
            for message in messages
        ):
            raise AccessError(_('Invalid notification position.'))
        chats = {self._notification_chat(message)[0] for message in messages}
        if len(chats) != 1 or any(self._notification_chat(message)[1] != target for message in messages):
            raise AccessError(_('Invalid notification position.'))
        conversation.lock_for_update()
        conversation.write({})
        positions = self.env['ab_crm_workspace_alert'].sudo()
        domain = [
            ('conversation_id', '=', conversation.id),
            ('user_id', '=', self.env.uid),
            ('employee_id', '=', session.employee_id.id),
            ('company_id', '=', session.company_id.id),
        ]
        position = positions.search(domain, limit=1)
        if not position:
            position = positions.create(
                dict((key, value) for key, operator, value in domain)
            )
        position.write(
            {'acknowledged_ids': [fields.Command.link(mid) for mid in messages.ids]}
        )
        return True


class Message(models.Model):
    _inherit = 'ab_crm_message'

    workspace_alert_ids = fields.Many2many(
        'ab_crm_workspace_alert', 'ab_crm_message_ab_crm_workspace_alert_rel',
        'ab_crm_message_id', 'ab_crm_workspace_alert_id',
        string='Acknowledged messages', readonly=True, groups='base.group_system')
