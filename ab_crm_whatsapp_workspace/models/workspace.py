from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


from .common import _BRIDGE, _DASHBOARD, bridge_mutation
from .media import validate_whatsapp_attachment


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

    whatsapp_profile_name = fields.Char(readonly=True)

    @api.model_create_multi
    def create(self, values_list):
        if not _BRIDGE.get() and (any('whatsapp_profile_name' in values for values in values_list)
                                  or 'default_whatsapp_profile_name' in self.env.context):
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if 'whatsapp_profile_name' in values and not _BRIDGE.get():
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().write(values)

    def _provider_display_name(self):
        if self.channel_id.provider == 'whatsapp':
            return self.whatsapp_profile_name
        return super()._provider_display_name()

    def _workspace_visible_domain(self):
        return super()._workspace_visible_domain() + [('whatsapp_reaction_event', '=', False)]

    def _workspace_reactions(self, references):
        if self.channel_id.provider != 'whatsapp':
            return super()._workspace_reactions(references)
        reactions = self.env['ab_crm_message'].search([
            ('conversation_id', '=', self.id), ('reply_reference', 'in', references),
            '|', ('whatsapp_reaction_event', '=', True), ('reaction', '!=', False),
        ], order='timeline_at desc, provider_reference desc, id desc')
        newest = {}
        for reaction in reactions:
            newest.setdefault((reaction.reply_reference, reaction.direction), reaction.id)
        return reactions.browse(list(newest.values()))

    def _owned(self):
        if _DASHBOARD.get() and self.channel_id.provider == 'whatsapp':
            self._authorize()
            self.messaging_account_id._authorize('read')
            self.messaging_account_id.lock_for_update()
            self.lock_for_update()
            return None, self.env['ab_store']
        return super()._owned()

    def _log_workspace_action(self, action, message_id=False):
        if _DASHBOARD.get() and self.channel_id.provider == 'whatsapp':
            self._authorize()
            return
        return super()._log_workspace_action(action, message_id=message_id)

    def _reply_eligibility(self):
        if self.channel_id.provider != 'whatsapp':
            return super()._reply_eligibility()
        try:
            self._authorize()
            if not _DASHBOARD.get():
                self._workspace_scope()
            account = self.messaging_account_id
            if not account:
                raise UserError(
                    _('WhatsApp queue sending is disabled for this account.')
                )
            account._eligible(self, _('Attachment'))
        except (AccessError, UserError) as error:
            return 'provider_restriction', str(error)
        return False, False

    def _whatsapp_reference(self, reference, reaction=False):
        self.ensure_one()
        target = self.env['ab_crm_message'].search(
            [
                ('conversation_id', '=', self.id),
                ('provider_reference', '=', reference),
            ],
            limit=1,
        )
        history = target.whatsapp_history_ids
        if (
            not target
            or not history
            or (
                reaction
                and (
                    history.is_deleted
                    or history.message_type == 'reaction'
                    or not history.crm_timestamp
                    or history.crm_timestamp
                    < fields.Datetime.now() - timedelta(days=30)
                )
            )
        ):
            raise UserError(
                _('Select an eligible WhatsApp message from this conversation.')
            )
        return target

    def _valid_reply_reaction(self, reaction):
        if self.channel_id.provider == 'whatsapp':
            return (
                isinstance(reaction, str)
                and 1 <= len(reaction) <= 16
                and not any(c.isspace() for c in reaction)
                and any(ord(c) >= 0x2300 for c in reaction)
            )
        return super()._valid_reply_reaction(reaction)

    def _validate_reply_attachment(self, attachment):
        if self.channel_id.provider == 'whatsapp':
            return validate_whatsapp_attachment(attachment, self.env._)
        return super()._validate_reply_attachment(attachment)

    def action_reply(self, body, attachments=None, reply_id=False, reaction=False):
        if self.channel_id.provider == 'whatsapp' and reply_id:
            target = self.env['ab_crm_message'].browse(reply_id)
            target.check_access('read')
            if target.conversation_id != self:
                raise AccessError(
                    _('Select an eligible WhatsApp message from this conversation.')
                )
            self._whatsapp_reference(target.provider_reference, reaction=bool(reaction))
        return super().action_reply(
            body, attachments=attachments, reply_id=reply_id, reaction=reaction
        )

    def _workspace_actions(self, message, send_reason):
        result = super()._workspace_actions(message, send_reason)
        if self.channel_id.provider == 'whatsapp':
            try:
                self._whatsapp_reference(message.provider_reference, reaction=True)
                allowed = not send_reason and self.messaging_account_id.whatsapp_extended_enabled
            except (AccessError, UserError):
                allowed = False
            result['react']['enabled'] = allowed
            result['reactions'] = ['👍', '❤', '👎'] if allowed else []
        return result

    def workspace_detail(self, **kwargs):
        result = super().workspace_detail(**kwargs)
        if self.channel_id.provider == 'whatsapp':
            account = self.messaging_account_id
            enabled = bool(account.whatsapp_migrated)
            result['capabilities'].update(
                media=enabled and account.whatsapp_extended_enabled,
                reactions=enabled and account.whatsapp_extended_enabled,
                customer_read=account.whatsapp_webhook_enabled,
                customer_delivered=account.whatsapp_webhook_enabled,
            )
            result['whatsapp_templates'] = bool(enabled and account.outgoing_enabled)
            history = self.env['ab.whatsapp.message'].search(
                [('crm_message_id', 'in', [row['id'] for row in result['messages']])]
            )
            timestamps = {r.crm_message_id.id: r.crm_timestamp for r in history}
            projected = {message.id: message for message in self.env['ab_crm_message'].browse([row['id'] for row in result['messages']])}
            for row in result['messages']:
                row['contact_cards'] = (projected[row['id']].whatsapp_payload or {}).get('cards', [])
                if timestamps.get(row['id']):
                    row['timestamp'] = fields.Datetime.to_string(timestamps[row['id']])
        return result

    def whatsapp_templates(self):
        self.ensure_one()
        self._owned()
        account = self.messaging_account_id
        code, reason = account._queue_eligibility(self)
        if self.channel_id.provider != 'whatsapp' or code:
            raise UserError(
                reason or _('WhatsApp queue sending is disabled for this account.')
            )
        service = self.env['ab.whatsapp.service']
        return [
            {
                'id': t.id,
                'name': t.name,
                'language': t.language,
                'body': t.body_preview or '',
                'parameters': service._template_required_placeholder_indexes(t),
                'unsupported_reason': t._layout_error(),
            }
            for t in account._available_whatsapp_templates()
        ]

    def action_whatsapp_template(self, template_id, parameters=None):
        self.ensure_one()
        self._owned()
        account = self.messaging_account_id
        template = account._available_whatsapp_templates().filtered(lambda t: t.id == template_id)
        if self.channel_id.provider != 'whatsapp' or not template:
            raise AccessError(
                _('Select an approved template authorized for this WhatsApp account.')
            )
        with bridge_mutation():
            message = self.env['ab_crm_message'].create(
                {
                    'conversation_id': self.id,
                    'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id,
                    'direction': 'out',
                    'body': '[template] ' + template.name,
                    'whatsapp_template_id': template.id,
                    'whatsapp_template_params': parameters or [],
                }
            )
        message.action_approve()
        return message.id


class ChatterAPI(models.AbstractModel):
    _inherit = 'ab_crm_chatter_api'

    def _notification_message_domain(self):
        return super()._notification_message_domain() + [('whatsapp_reaction_event', '=', False)]
