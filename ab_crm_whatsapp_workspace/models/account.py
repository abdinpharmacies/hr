from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    whatsapp_migrated = fields.Boolean(string='WhatsApp Queue Ownership', copy=False)
    whatsapp_webhook_enabled = fields.Boolean(
        string='Signed WhatsApp Reception', copy=False
    )
    whatsapp_template_ids = fields.Many2many(
        'ab.whatsapp.template',
        'ab_crm_whatsapp_account_template_rel',
        'account_id',
        'template_id',
        string='Authorized WhatsApp Templates',
    )

    @api.constrains(
        'whatsapp_migrated',
        'provider',
        'legacy_worker_disabled',
        'whatsapp_webhook_enabled',
    )
    def _check_whatsapp_migration(self):
        for record in self:
            if record.whatsapp_migrated and (
                record.provider != 'whatsapp' or not record.legacy_worker_disabled
            ):
                raise ValidationError(
                    _(
                        'WhatsApp queue ownership requires a WhatsApp account with direct sending disabled.'
                    )
                )
            if record.whatsapp_webhook_enabled and not record.whatsapp_migrated:
                raise ValidationError(
                    _('Migrate the WhatsApp account before enabling signed reception.')
                )

    @api.model_create_multi
    def create(self, values_list):
        if any(
            set(values)
            & {'whatsapp_migrated', 'whatsapp_template_ids', 'whatsapp_webhook_enabled'}
            for values in values_list
        ):
            self._check_whatsapp_manager()
        return super().create(values_list)

    def _check_whatsapp_manager(self):
        if not self.env.user.has_group(
            'base.group_system'
        ) and not self.env.user.has_group('ab_crm_core.group_manager'):
            raise AccessError(
                _('Only CRM managers can configure WhatsApp queue ownership.')
            )

    def write(self, values):
        if set(values) & {
            'whatsapp_migrated',
            'whatsapp_template_ids',
            'whatsapp_webhook_enabled',
        }:
            self._check_whatsapp_manager()
            self._authorize()
            if values.get('whatsapp_migrated') is False and any(
                self.mapped('whatsapp_migrated')
            ):
                raise UserError(
                    _(
                        'Queue ownership cannot be reversed without reconciling messaging history.'
                    )
                )
        return super().write(values)

    def _queue_eligibility(self, conversation):
        code, reason = super()._queue_eligibility(conversation)
        if (
            not code
            and self.provider == 'whatsapp'
            and (
                not self.whatsapp_migrated
                or not self.outgoing_enabled
                or not conversation.active
            )
        ):
            return 'account_disabled', _(
                'WhatsApp queue sending is disabled for this account.'
            )
        return code, reason

    def _eligible_message(self, message):
        if self.provider != 'whatsapp':
            return super()._eligible_message(message)
        if message.whatsapp_template_id:
            code, reason = self._queue_eligibility(message.conversation_id)
            if code:
                raise UserError(reason)
            message._whatsapp_template_payload()
            return False
        for media in message.media_ids:
            limit = (
                (
                    5
                    if media.kind == 'image'
                    else 16 if media.kind in ('audio', 'voice', 'video') else 20
                )
                * 1024
                * 1024
            )
            if (
                media.size > limit
                or (
                    media.kind == 'image'
                    and media.mimetype not in ('image/jpeg', 'image/png')
                )
                or (
                    media.kind == 'audio'
                    and media.mimetype in ('audio/webm', 'video/webm')
                )
            ):
                raise UserError(
                    _('This attachment type or size is not supported by WhatsApp.')
                )
        if message.reaction:
            message.conversation_id._whatsapp_reference(
                message.reply_reference, reaction=True
            )
        return super()._eligible_message(message)

    def _whatsapp_conversation(self, destination):
        self.ensure_one()
        conversation = (
            self.env['ab_crm_conversation']
            .with_context(active_test=False)
            .search(
                [
                    ('channel_id', '=', self.channel_id.id),
                    ('external_key', '=', destination),
                ],
                limit=1,
            )
        )
        if not conversation:
            identity = self.env['ab_crm_identity'].search(
                [
                    ('channel_id', '=', self.channel_id.id),
                    ('external_key', '=', destination),
                    ('branch_id', '=', self.branch_id.id),
                    ('company_id', '=', self.company_id.id),
                ],
                limit=1,
            )
            conversation = self.env['ab_crm_conversation'].create(
                {
                    'name': destination,
                    'external_key': destination,
                    'channel_id': self.channel_id.id,
                    'branch_id': self.branch_id.id,
                    'company_id': self.company_id.id,
                    'customer_id': identity.customer_id.id,
                }
            )
        return conversation

    def action_link_whatsapp_history(self, limit=200, after_id=0):
        self.ensure_one()
        self._check_whatsapp_manager()
        self._authorize()
        if (
            not self.whatsapp_migrated
            or type(limit) is not int
            or not 1 <= limit <= 500
            or type(after_id) is not int
            or after_id < 0
        ):
            raise UserError(
                _(
                    'Select a migrated WhatsApp account and a batch of at most 500 records.'
                )
            )
        self.lock_for_update()
        rows = (
            self.env['ab.whatsapp.message']
            .sudo()
            .search(
                [
                    ('phone_number_id', '=', self.provider_account),
                    ('crm_message_id', '=', False),
                    ('is_deleted', '=', False),
                ],
                order='id',
                limit=limit,
            )
        )
        linked = 0
        for record in rows:
            if (
                record.meta_message_id
                and self.env['ab.whatsapp.message']
                .sudo()
                .search_count(
                    [
                        ('phone_number_id', '=', self.provider_account),
                        ('meta_message_id', '=', record.meta_message_id),
                    ],
                    limit=2,
                )
                > 1
            ):
                continue
            if record.wa_id and record.wa_id.isascii() and record.wa_id.isdecimal():
                record._project_history(self)
                linked += 1
        return {
            'linked': linked,
            'examined': len(rows),
            'next_after_id': rows[-1:].id or after_id,
        }

    def action_link_whatsapp_history_batch(self):
        self.action_link_whatsapp_history()
        return False


class Template(models.Model):
    _inherit = 'ab.whatsapp.template'

    raw_payload = fields.Json(groups='base.group_system')

    crm_account_ids = fields.Many2many(
        'ab_crm_messaging_account',
        'ab_crm_whatsapp_account_template_rel',
        'template_id',
        'account_id',
        readonly=True,
        groups='base.group_system',
    )

    def write(self, values):
        if 'crm_account_ids' in values:
            raise AccessError(
                _('Configure authorized templates on the messaging account.')
            )
        return super().write(values)
