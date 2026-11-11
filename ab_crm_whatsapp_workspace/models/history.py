from datetime import datetime, timezone

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import _BRIDGE, bridge_mutation


class WhatsAppMessage(models.Model):
    _inherit = 'ab.whatsapp.message'

    crm_account_id = fields.Many2one(
        'ab_crm_messaging_account', readonly=True, ondelete='restrict', index=True
    )
    crm_message_id = fields.Many2one(
        'ab_crm_message', readonly=True, ondelete='restrict', index=True
    )
    crm_timestamp = fields.Datetime(readonly=True)
    crm_location_snapshot = fields.Json(related='crm_message_id.location_snapshot', readonly=True)
    _crm_projection_unique = models.Constraint(
        'UNIQUE(crm_message_id)', 'WhatsApp history must have one CRM projection.'
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _BRIDGE.get():
            if any(
                set(v) & {'crm_account_id', 'crm_message_id', 'crm_timestamp', 'crm_location_snapshot'}
                for v in values_list
            ):
                raise AccessError(_('Integrated WhatsApp history is immutable.'))
            phones = [
                v.get('phone_number_id')
                for v in values_list
                if v.get('phone_number_id')
            ]
            if phones and self.env['ab_crm_messaging_account'].sudo().with_context(
                active_test=False
            ).search_count(
                [
                    ('provider_account', 'in', phones),
                    ('whatsapp_migrated', '=', True),
                ]
            ):
                raise AccessError(
                    _('Use the durable gateway for this WhatsApp account.')
                )
        return super().create(values_list)

    def write(self, values):
        if not _BRIDGE.get() and (
            any(self.mapped('crm_account_id'))
            or set(values) & {'crm_account_id', 'crm_message_id', 'crm_timestamp', 'crm_location_snapshot'}
        ):
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().write(values)

    def unlink(self):
        if any(self.mapped('crm_account_id')):
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().unlink()

    @api.constrains('crm_account_id', 'crm_message_id', 'phone_number_id')
    def _check_crm_projection(self):
        for record in self.filtered('crm_account_id'):
            account, message = record.crm_account_id, record.crm_message_id
            if (
                not message
                or account.provider_account != record.phone_number_id
                or account.channel_id != message.conversation_id.channel_id
                or account.branch_id != message.branch_id
                or account.company_id != message.company_id
                or record.wa_id != message.conversation_id.external_key
            ):
                raise ValidationError(
                    _(
                        'WhatsApp history and its projection must use the same account and destination.'
                    )
                )

    def _project_history(self, account):
        self.ensure_one()
        self.lock_for_update()
        if self.crm_message_id:
            return self.crm_message_id
        conversation = account._whatsapp_conversation(self.wa_id)
        timestamp = None
        try:
            timestamp = datetime.fromtimestamp(
                int((self.raw_payload or {}).get('timestamp')), timezone.utc
            ).replace(tzinfo=None)
            if timestamp > fields.Datetime.now():
                timestamp = None
        except (ValueError, TypeError, OverflowError, OSError, AttributeError):
            pass
        with bridge_mutation():
            message = conversation.env['ab_crm_message'].create(
                {
                    'conversation_id': conversation.id,
                    'branch_id': account.branch_id.id,
                    'company_id': account.company_id.id,
                    'historical': True,
                    'original_timestamp': timestamp or self.create_date,
                    'direction': 'in' if self.direction == 'incoming' else 'out',
                    'body': self.text_content or self.media_filename or _('Attachment'),
                    'delivery_state': (
                        'sent'
                        if self.direction == 'incoming'
                        or self.status in ('sent', 'accepted', 'delivered', 'read')
                        else 'unknown'
                    ),
                    'provider_reference': self.meta_message_id,
                    'reply_reference': self.reply_to_meta_message_id
                    or self.reaction_target_meta_message_id,
                    'reaction': (
                        self.text_content if self.message_type == 'reaction' else False
                    ),
                }
            )
            self.write(
                {
                    'crm_account_id': account.id,
                    'crm_message_id': message.id,
                    'crm_timestamp': timestamp or self.create_date,
                }
            )
        return message


class WhatsAppContact(models.Model):
    _inherit = 'ab.whatsapp.contact'

    def write(self, values):
        if 'wa_id' in values and self.env['ab.whatsapp.message'].sudo().search_count(
            [
                ('contact_id', 'in', self.ids),
                ('crm_account_id', '!=', False),
            ]
        ):
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().write(values)

    def unlink(self):
        if (
            self.env['ab.whatsapp.message']
            .sudo()
            .search_count(
                [
                    ('contact_id', 'in', self.ids),
                    ('crm_account_id', '!=', False),
                ]
            )
        ):
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().unlink()


class Message(models.Model):
    _inherit = 'ab_crm_message'

    whatsapp_payload = fields.Json(readonly=True)
    whatsapp_reaction_event = fields.Boolean(readonly=True)

    whatsapp_history_ids = fields.One2many(
        'ab.whatsapp.message', 'crm_message_id', readonly=True
    )
    whatsapp_template_id = fields.Many2one(
        'ab.whatsapp.template', readonly=True, ondelete='restrict'
    )
    whatsapp_template_params = fields.Json(readonly=True)
    whatsapp_session_id = fields.Many2one(
        'ab_crm_chatter_session',
        readonly=True,
        ondelete='restrict',
        groups='base.group_system,ab_crm_core.group_manager',
    )

    @api.model_create_multi
    def create(self, values_list):
        if not _BRIDGE.get() and any(
            set(v)
            & {
                'whatsapp_payload',
                'whatsapp_reaction_event',
                'whatsapp_history_ids',
                'whatsapp_template_id',
                'whatsapp_template_params',
                'whatsapp_session_id',
            }
            for v in values_list
        ):
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().create(values_list)

    def write(self, values):
        if not _BRIDGE.get() and set(values) & {
            'whatsapp_payload',
            'whatsapp_reaction_event',
            'whatsapp_history_ids',
            'whatsapp_template_id',
            'whatsapp_template_params',
            'whatsapp_session_id',
        }:
            raise AccessError(_('Integrated WhatsApp history is immutable.'))
        return super().write(values)

    def _whatsapp_template_payload(self):
        self.ensure_one()
        template = self.whatsapp_template_id
        account = self.conversation_id.messaging_account_id
        if (
            template not in account._available_whatsapp_templates()
            or (template.status or '').upper() != 'APPROVED'
        ):
            raise UserError(
                _('Select an approved template authorized for this WhatsApp account.')
            )
        if template._layout_error():
            raise UserError(template._layout_error())
        indexes = self.env[
            'ab.whatsapp.service'
        ]._template_required_placeholder_indexes(template)
        params = self.whatsapp_template_params or []
        if (
            not isinstance(params, list)
            or len(params) != len(indexes)
            or any(
                not isinstance(p, str) or not p.strip() or len(p) > 1024 for p in params
            )
        ):
            raise UserError(
                _('Provide one nonempty value for each template parameter.')
            )
        payload = {'name': template.name, 'language': {'code': template.language}}
        if params:
            payload['components'] = [
                {
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': p} for p in params],
                }
            ]
        return payload

    def _outgoing_extra(self):
        values = super()._outgoing_extra()
        if self.whatsapp_template_id:
            values['template'] = self._whatsapp_template_payload()
        return values

    def action_approve(self):
        for message in self.filtered(
            lambda r: r.conversation_id.channel_id.provider == 'whatsapp'
        ):
            if message.whatsapp_history_ids:
                raise UserError(_('Historical WhatsApp messages cannot be sent again.'))
            session, stores = message.conversation_id._owned()
            if session:
                with bridge_mutation():
                    message.sudo().write({'whatsapp_session_id': session.id})
        result = super().action_approve()
        for message in self.filtered(
            lambda r: r.conversation_id.channel_id.provider == 'whatsapp'
        ):
            account = message.conversation_id.messaging_account_id
            media = message.media_ids[:1]
            kind = (
                'template'
                if message.whatsapp_template_id
                else (
                    'reaction'
                    if message.reaction
                    else (
                        ('audio' if media.kind == 'voice' else media.kind)
                        if media
                        else 'text'
                    )
                )
            )
            with bridge_mutation():
                canonical = self.env['ab.whatsapp.service']._create_message(
                    direction='outgoing',
                    wa_id=message.conversation_id.external_key,
                    phone_number_id=account.provider_account,
                    message_type=kind,
                    text_content=message.body,
                    status='queued',
                    reply_to_meta_message_id=(
                        message.reply_reference if not message.reaction else None
                    ),
                    reaction_target_meta_message_id=(
                        message.reply_reference if message.reaction else None
                    ),
                    media_mime_type=media.mimetype,
                    media_filename=media.name,
                )
                canonical.write(
                    {
                        'crm_account_id': account.id,
                        'crm_message_id': message.id,
                        'crm_timestamp': fields.Datetime.now(),
                    }
                )
        return result


class Operation(models.Model):
    _inherit = 'ab_crm_messaging_operation'

    def write(self, values):
        result = super().write(values)
        if set(values) & {'state', 'provider_reference'}:
            with bridge_mutation():
                for operation in self:
                    history = operation.message_id.whatsapp_history_ids.sudo()
                    if history:
                        state = {
                            'leased': 'queued',
                            'received': 'queued',
                            'review': 'uncertain',
                            'resolved': 'uncertain',
                            'cancelled': 'failed',
                        }.get(operation.state, operation.state)
                        history.write(
                            {
                                'status': state,
                                'meta_message_id': operation.provider_reference,
                            }
                        )
        return result
