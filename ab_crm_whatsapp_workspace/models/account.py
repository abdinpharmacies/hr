import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from .common import _BRIDGE, bridge_mutation


class Account(models.Model):
    _inherit = 'ab_crm_messaging_account'

    whatsapp_business_account = fields.Char(readonly=True, copy=False)
    whatsapp_templates_synced_at = fields.Datetime(readonly=True, copy=False)
    whatsapp_templates_error = fields.Char(readonly=True, copy=False)

    whatsapp_migrated = fields.Boolean(string='WhatsApp Queue Ownership', copy=False)
    whatsapp_webhook_enabled = fields.Boolean(
        string='Signed WhatsApp Reception', copy=False
    )
    whatsapp_extended_enabled = fields.Boolean(string='Validated WhatsApp Media and Reactions', copy=False)
    whatsapp_template_ids = fields.Many2many(
        'ab.whatsapp.template',
        'ab_crm_whatsapp_account_template_rel',
        'account_id',
        'template_id',
        string='Authorized WhatsApp Templates',
        copy=False,
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
        if not _BRIDGE.get() and (any({'whatsapp_template_ids', 'whatsapp_business_account'} & values.keys() for values in values_list) or any('default_' + key in self.env.context for key in ('whatsapp_template_ids', 'whatsapp_business_account'))):
            raise AccessError(_('Refresh WhatsApp templates to update the account inventory.'))
        if any(
            set(values)
            & {'whatsapp_migrated', 'whatsapp_template_ids', 'whatsapp_webhook_enabled', 'whatsapp_extended_enabled', 'whatsapp_business_account', 'whatsapp_templates_synced_at', 'whatsapp_templates_error'}
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
        if not _BRIDGE.get() and {'whatsapp_template_ids', 'whatsapp_business_account'} & values.keys():
            raise AccessError(_('Refresh WhatsApp templates to update the account inventory.'))
        if set(values) & {
            'whatsapp_business_account', 'whatsapp_templates_synced_at', 'whatsapp_templates_error',
            'whatsapp_migrated',
            'whatsapp_template_ids',
            'whatsapp_webhook_enabled',
            'whatsapp_extended_enabled',
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

    def _available_whatsapp_templates(self):
        self.ensure_one()
        self._authorize('read')
        return self.whatsapp_template_ids.filtered(lambda template:
            self.whatsapp_business_account
            and template.business_account_id == self.whatsapp_business_account
            and (template.status or '').upper() == 'APPROVED')

    def action_refresh_whatsapp_templates(self):
        self.ensure_one()
        self._check_whatsapp_manager()
        self._authorize()
        if self.provider != 'whatsapp' or not self.whatsapp_migrated:
            raise UserError(_('Select a migrated WhatsApp account.'))
        self.lock_for_update()
        service = self.env['ab.whatsapp.service'].sudo()
        settings = service._settings()
        waba = settings['waba_id']
        if not waba or not str(waba).isascii() or not str(waba).isdecimal():
            raise UserError(_('Configure the WhatsApp business account before synchronizing templates.'))
        headers = service._graph_headers(service._require_token())
        origin = f"https://graph.facebook.com/{settings['api_version']}/{waba}"
        try:
            with self.env.cr.savepoint():
                phones = self._whatsapp_inventory(service, origin + '/phone_numbers', headers, 'id')
                if self.provider_account not in {str(row.get('id')) for row in phones}:
                    raise UserError(_('The sender does not belong to the configured WhatsApp business account.'))
                rows = self._whatsapp_inventory(service, origin + '/message_templates', headers,
                    'id,name,language,status,category,quality_score,components')
                templates = self.env['ab.whatsapp.template'].sudo()
                seen = templates.browse()
                now = fields.Datetime.now()
                for row in rows:
                    if not all(isinstance(row.get(key), str) and row[key] for key in ('id', 'name', 'language', 'status')):
                        raise UserError(_('Meta returned an invalid template inventory.'))
                    components = row.get('components', [])
                    if not isinstance(components, list):
                        raise UserError(_('Meta returned an invalid template inventory.'))
                    template = templates.search([('template_uid', '=', row['id'])], limit=1)
                    if template.business_account_id and template.business_account_id != waba:
                        raise UserError(_('Meta returned an invalid template inventory.'))
                    values = {'name': row['name'], 'language': row['language'], 'status': row['status'],
                              'business_account_id': waba, 'category': row.get('category'),
                              'components_payload': components, 'raw_payload': row,
                              'body_preview': service._template_body_preview(components),
                              'has_placeholders': service._template_has_placeholders(components),
                              'last_synced_at': now}
                    if template:
                        template.write(values)
                    else:
                        template = templates.create(dict(values, template_uid=row['id']))
                    seen |= template
                missing = templates.search([('business_account_id', '=', waba)]) - seen
                missing.write({'status': 'UNAVAILABLE'})
                with bridge_mutation():
                    self.write({'whatsapp_business_account': waba,
                                'whatsapp_template_ids': [fields.Command.set((seen | missing).ids)],
                                'whatsapp_templates_synced_at': now, 'whatsapp_templates_error': False})
        except (UserError, ValueError, TypeError, AttributeError) as error:
            reason = str(error) if isinstance(error, UserError) else _('Meta returned an invalid template inventory.')
            self.write({'whatsapp_templates_error': reason[:1000]})
            return {'ok': False, 'error': reason}
        return {'ok': True, 'count': len(seen), 'last_sync': fields.Datetime.to_string(now)}

    def _whatsapp_inventory(self, service, url, headers, field_names):
        rows, cursors = [], set()
        params = {'fields': field_names, 'limit': 100}
        for page in range(100):
            payload = service._get_graph_json(url=url, headers=headers, params=params)
            data = payload.get('data')
            if not isinstance(data, list) or any(not isinstance(row, dict) for row in data):
                raise UserError(_('Meta returned an invalid template inventory.'))
            rows.extend(data)
            paging = payload.get('paging') or {}
            if not paging.get('next'):
                return rows
            cursor = (paging.get('cursors') or {}).get('after')
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                break
            cursors.add(cursor)
            params['after'] = cursor
        raise UserError(_('Meta template pagination could not be completed.'))

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
        if not code and self.provider == 'whatsapp' and (not conversation.external_key.isascii() or not conversation.external_key.isdecimal()):
            return 'invalid_destination', _('Unsupported WhatsApp identity requires review.')
        return code, reason

    def _eligible_message(self, message):
        if self.provider != 'whatsapp':
            return super()._eligible_message(message)
        if (message.media_ids or message.reaction) and not self.whatsapp_extended_enabled:
            raise UserError(_('WhatsApp media and reactions require pilot validation.'))
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
        self._authorize('read')
        self.env['ab.whatsapp.service']._normalize_wa_id(destination)
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
            from .common import bridge_mutation
            with bridge_mutation():
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
                    ('id', '>', after_id),
                    ('crm_message_id', '=', False),
                    ('is_deleted', '=', False),
                ],
                order='id',
                limit=limit,
            )
        )
        linked = []
        skipped = []
        conflicting = []
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
                conflicting.append(record.id)
                continue
            if record.wa_id and record.wa_id.isascii() and record.wa_id.isdecimal():
                record._project_history(self)
                linked.append(record.id)
            else:
                skipped.append(record.id)
        return {
            'linked': len(linked),
            'linked_ids': linked,
            'skipped_ids': skipped,
            'conflicting_ids': conflicting,
            'has_more': len(rows) == limit,
            'examined': len(rows),
            'next_after_id': rows[-1:].id or after_id,
        }

    @api.model
    def action_prepare_whatsapp_pilot(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only system administrators can prepare the WhatsApp pilot.'))
        telegram = self.search([('code', '=', 'tg-callcenter'), ('provider', '=', 'telegram')], limit=1)
        telegram._authorize('read')
        if not telegram or telegram.company_id != self.env.company:
            raise UserError(_('Prepare the Telegram intake mapping first.'))
        settings = self.env['ab.whatsapp.service']._settings()
        phone = self.env['ab.whatsapp.service']._validate_phone_number_id(settings['default_phone_number_id'])
        if self.env['ab.whatsapp.service']._config_value('whatsapp_api_version') != 'v26.0':
            raise UserError(_('WhatsApp requires the validated Graph API version v26.0.'))
        telegram.lock_for_update()
        service = self.env.ref('ab_crm_whatsapp_workspace.user_whatsapp_gateway')
        existing = self.with_context(active_test=False).search([
            '|', ('code', '=', 'wa-callcenter'), '&', ('provider', '=', 'whatsapp'), ('provider_account', '=', phone),
        ])
        if existing:
            existing._authorize('read')
            if len(existing) != 1 or existing.code != 'wa-callcenter' or existing.provider_account != phone or existing.branch_id != telegram.branch_id or existing.company_id != telegram.company_id or existing.provider != 'whatsapp' or existing.service_user_id != service:
                raise UserError(_('Review the existing WhatsApp account mapping.'))
            return {'account_id': existing.id, 'created': False}
        if service.active:
            raise UserError(_('Review the existing WhatsApp account mapping.'))
        service.write({'company_ids': [fields.Command.set(telegram.company_id.ids)], 'company_id': telegram.company_id.id})
        telegram.branch_id.write({'user_ids': [fields.Command.link(service.id)]})
        channel = self.env['ab_crm_channel'].create({
            'name': 'WhatsApp', 'code': 'wa-callcenter', 'provider': 'whatsapp',
            'branch_id': telegram.branch_id.id, 'company_id': telegram.company_id.id,
        })
        account = self.create({
            'name': 'WhatsApp', 'code': 'wa-callcenter', 'provider': 'whatsapp',
            'provider_account': phone, 'channel_id': channel.id,
            'branch_id': telegram.branch_id.id, 'company_id': telegram.company_id.id,
            'service_user_id': service.id, 'legacy_worker_disabled': True,
            'whatsapp_migrated': True, 'whatsapp_webhook_enabled': False,
            'whatsapp_extended_enabled': False, 'enabled': False, 'outgoing_enabled': False,
        })
        return {'account_id': account.id, 'created': True}

    def action_link_whatsapp_history_batch(self):
        self.action_link_whatsapp_history()
        return False


class Template(models.Model):
    _inherit = 'ab.whatsapp.template'

    raw_payload = fields.Json(groups='base.group_system')
    business_account_id = fields.Char(readonly=True, index=True)

    def _layout_error(self):
        self.ensure_one()
        for component in self.components_payload or []:
            if not isinstance(component, dict):
                return _('This template layout is not supported. Use a template with text and body parameters only.')
            placeholders = re.findall(r'{{(.*?)}}', component.get('text', ''))
            if placeholders and (any(not value.strip().isdigit() for value in placeholders) or sorted(set(int(value.strip()) for value in placeholders)) != list(range(1, len(set(placeholders)) + 1))):
                return _('This template layout is not supported. Use a template with text and body parameters only.')
            kind = component.get('type', '').upper()
            if kind not in ('BODY', 'HEADER', 'FOOTER') or (kind == 'HEADER' and component.get('format', 'TEXT') != 'TEXT') or (kind != 'BODY' and '{{' in component.get('text', '')):
                return _('This template layout is not supported. Use a template with text and body parameters only.')
        return ''

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
