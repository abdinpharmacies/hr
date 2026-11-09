from datetime import timedelta

from odoo import fields, models, _
from odoo.exceptions import AccessError, UserError

from .common import _DASHBOARD, bridge_mutation
from .media import validate_whatsapp_attachment


class Conversation(models.Model):
    _inherit = 'ab_crm_conversation'

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
                allowed = not send_reason
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
                media=enabled,
                reactions=enabled,
                customer_read=account.whatsapp_webhook_enabled,
                customer_delivered=account.whatsapp_webhook_enabled,
            )
            result['whatsapp_templates'] = bool(enabled and account.outgoing_enabled)
            history = self.env['ab.whatsapp.message'].search(
                [('crm_message_id', 'in', [row['id'] for row in result['messages']])]
            )
            timestamps = {r.crm_message_id.id: r.crm_timestamp for r in history}
            for row in result['messages']:
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
            }
            for t in account.whatsapp_template_ids
            if (t.status or '').upper() == 'APPROVED'
        ]

    def action_whatsapp_template(self, template_id, parameters=None):
        self.ensure_one()
        self._owned()
        account = self.messaging_account_id
        template = account.whatsapp_template_ids.filtered(lambda t: t.id == template_id)
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
