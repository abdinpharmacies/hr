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

    @api.model
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
        positions = (
            self.env['ab_crm_workspace_alert']
            .sudo()
            .search(
                [
                    ('user_id', '=', self.env.uid),
                    ('employee_id', '=', session.employee_id.id),
                    ('company_id', '=', session.company_id.id),
                    ('conversation_id', 'in', page.ids),
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
        messages = authorized._workspace_unread_messages(session).filtered_domain(self._notification_message_domain())
        unread_counts = {conversation.id: len(messages.filtered(lambda message: message.conversation_id == conversation)) for conversation in authorized}
        groups = {}
        for message in messages:
            cid = message.conversation_id.id
            if message.id not in acknowledged.get(cid, set()):
                groups.setdefault(cid, []).append(message)
        return {
            'cursor': page[-1:].id or after_id,
            'has_more': len(conversations) > 50,
            'items': [
                {
                    'alert_key': f'{self.env.uid}:{session.employee_id.id}:{session.company_id.id}:{cid}',
                    'conversation_id': cid,
                    'customer_group_key': pending[-1].conversation_id.customer_group_key,
                    'display_destination': pending[-1].conversation_id._display_destination(),
                    'conversation_label': pending[-1].conversation_id.messaging_account_id.name,
                    'unread_count': unread_counts[cid],
                    'latest_message_id': pending[-1].id,
                    'message_ids': [message.id for message in pending],
                    'count': len(pending),
                    'preview': (pending[-1].body or '')[:160],
                    'name': pending[-1].conversation_id._customer_display_name(),
                    'provider': pending[-1].conversation_id.channel_id.provider,
                }
                for cid, pending in groups.items()
            ],
        }

    @api.model
    def acknowledge_alert(self, token, conversation_id, message_ids):
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
        messages = self.env['ab_crm_message'].browse(message_ids).exists()
        messages.check_access('read')
        if len(messages) != len(set(message_ids)) or any(
            message.conversation_id != conversation or message.direction != 'in'
            for message in messages
        ):
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
