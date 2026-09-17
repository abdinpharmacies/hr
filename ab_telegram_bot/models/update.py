"""Manual, single-batch Bot API consumption with durable local update history."""
import datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

UPDATE_TYPES = ['message', 'edited_message', 'channel_post', 'edited_channel_post', 'my_chat_member']
POLL_FIELDS = {'poll_identity', 'next_update_offset', 'last_fetch_at', 'last_fetch_note'}


class TelegramBotUpdates(models.Model):
    _inherit = 'ab_telegram_bot'

    poll_identity = fields.Char(readonly=True, copy=False, index=True)
    next_update_offset = fields.Char(string='Next Update Offset', default='0', readonly=True, copy=False)
    last_fetch_at = fields.Datetime(readonly=True, copy=False)
    last_fetch_note = fields.Text(readonly=True, copy=False)
    update_count = fields.Integer(string='Incoming Updates', compute='_compute_update_count')
    _unique_poller = models.Constraint('UNIQUE(poll_identity)', 'Another Odoo bot record already receives updates for this Telegram bot.')

    @api.depends_context('uid')
    def _compute_update_count(self):
        counts = dict(self.env['ab_telegram_bot_update']._read_group(
            fields.Domain('bot_id', 'in', self.ids), ['bot_id'], ['__count']))
        for bot in self:
            bot.update_count = counts.get(bot, 0)

    @api.model_create_multi
    def create(self, vals_list):
        if any(POLL_FIELDS & set(vals) for vals in vals_list):
            raise AccessError(_('Polling state can only be changed by Fetch Updates.'))
        return super().create(vals_list)

    def write(self, vals):
        if POLL_FIELDS & set(vals):
            raise AccessError(_('Polling state can only be changed by Fetch Updates.'))
        for bot in self:
            if vals.get('token') and (bot.poll_identity or bot.bot_id):
                if vals['token'].split(':', 1)[0] != (bot.poll_identity or bot.bot_id):
                    raise ValidationError(_('This token belongs to another bot. Create a separate bot record.'))
            if bot.poll_identity and vals.get('company_id', bot.company_id.id) != bot.company_id.id:
                raise ValidationError(_('A bot with incoming history cannot change company.'))
            if bot.poll_identity and 'bot_id' in vals and vals['bot_id'] != bot.poll_identity:
                raise ValidationError(_('The Telegram identity does not match this bot history.'))
        return super().write(vals)

    def _set_poll(self, vals):
        return super(TelegramBotUpdates, self.sudo()).write(vals)

    def action_open_updates(self):
        self.ensure_one()
        self.check_access('read')
        return {'type': 'ir.actions.act_window', 'name': _('Incoming Updates'),
                'res_model': 'ab_telegram_bot_update', 'view_mode': 'list,form',
                'domain': [('bot_id', '=', self.id)]}

    def action_fetch_updates(self):
        self.ensure_one()
        self._require_operator()
        self.sudo().lock_for_update()
        self.invalidate_recordset()
        self._require_operator()
        info = self._read_api('getMe')
        identity = str(info['id'])
        if (self.poll_identity and self.poll_identity != identity) or (self.bot_id and self.bot_id != identity):
            raise ValidationError(_('The Telegram identity does not match this bot history.'))
        if self._read_api('getWebhookInfo').get('url'):
            raise UserError(_('This bot has a webhook. Remove it in the owning application before using Fetch Updates. No webhook was changed.'))
        # Unique constraint claims the Telegram identity before any getUpdates call,
        # preventing independent consumers in different companies in this database.
        self._set_poll({'poll_identity': identity, 'bot_id': identity, 'username': info.get('username') or False})
        self.flush_recordset(['poll_identity'])
        offset = int(self.next_update_offset or '0')
        payload = {'limit': 100, 'timeout': 0, 'allowed_updates': UPDATE_TYPES}
        if offset:
            payload['offset'] = offset
        updates = self._read_api('getUpdates', payload)
        if not isinstance(updates, list) or any(not isinstance(item, dict) or type(item.get('update_id')) is not int or item['update_id'] < 0 for item in updates):
            raise UserError(_('Telegram returned an invalid update batch. The polling offset was not advanced.'))
        model = self.env['ab_telegram_bot_update'].sudo()
        inserted = model.browse()
        duplicates = 0
        for payload in sorted(updates, key=lambda item: item['update_id']):
            existing = model.search(fields.Domain('bot_id', '=', self.id)
                                    & fields.Domain('update_id', '=', str(payload['update_id'])), limit=1)
            if existing:
                duplicates += 1
            else:
                inserted |= model._receive(self, payload)
        # One remote fetch per click: Telegram acknowledges the PREVIOUS committed
        # batch. This new offset and all raw updates commit together on RPC success.
        new_offset = max([offset] + [item['update_id'] + 1 for item in updates])
        self._set_poll({'next_update_offset': str(new_offset), 'last_fetch_at': fields.Datetime.now()})
        inserted._process_saved()
        failed = len(inserted.filtered(lambda update: update.state == 'failed'))
        note = _('Received: %s; new: %s; duplicates: %s; processing failures: %s.', len(updates), len(inserted), duplicates, failed)
        if len(updates) == 100:
            note += ' ' + _('A full batch was received. Click Fetch Updates again to check for more.')
        self._set_poll({'last_fetch_note': note})
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Fetch Updates'), 'message': note,
                           'type': 'warning' if failed else 'success', 'sticky': bool(failed)}}


class TelegramUpdate(models.Model):
    _name = 'ab_telegram_bot_update'
    _description = 'Telegram Incoming Update'
    _order = 'id desc'
    _rec_name = 'update_id'

    bot_id = fields.Many2one('ab_telegram_bot', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one('res.company', required=True, readonly=True)
    update_id = fields.Char(string='Telegram Update ID', required=True, readonly=True, index=True)
    update_type = fields.Char(readonly=True, index=True)
    received_at = fields.Datetime(required=True, default=fields.Datetime.now, readonly=True)
    event_at = fields.Datetime(readonly=True)
    chat_id = fields.Char(readonly=True, index=True)
    sender_id = fields.Char(readonly=True)
    message_id = fields.Char(readonly=True)
    text = fields.Text(string='Text / Caption', readonly=True)
    client_id = fields.Many2one('ab_telegram_bot_client', readonly=True, ondelete='restrict')
    group_id = fields.Many2one('ab_telegram_bot_group', readonly=True, ondelete='restrict')
    raw_update = fields.Json(required=True, readonly=True)
    state = fields.Selection([('received', 'Received'), ('processed', 'Processed'),
                              ('ignored', 'Ignored'), ('failed', 'Failed')], default='received', required=True, readonly=True)
    error = fields.Text(readonly=True)
    _unique_update = models.Constraint('UNIQUE(bot_id, update_id)', 'This Telegram update is already stored for this bot.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Incoming updates can only be created by Fetch Updates.'))

    def write(self, vals):
        raise AccessError(_('Incoming updates cannot be edited manually.'))

    def unlink(self):
        raise AccessError(_('Incoming update history cannot be deleted.'))

    def _set(self, vals):
        return super().write(vals)

    @api.model
    def _receive(self, bot, payload):
        kind = next((key for key in payload if key != 'update_id'), 'unknown')
        return super(TelegramUpdate, self).create({'bot_id': bot.id, 'company_id': bot.company_id.id,
            'update_id': str(payload['update_id']), 'update_type': kind, 'raw_update': payload})

    def _process_saved(self):
        for update in self.sorted(key=lambda record: int(record.update_id)):
            if update.state not in ('received', 'failed'):
                continue
            try:
                with self.env.cr.savepoint():
                    update._process_one()
            except Exception:
                # Raw content and safe retry context remain stored; no token, raw
                # payload or arbitrary remote content is interpolated into errors.
                update._set({'state': 'failed', 'error': _('Processing failed. The raw update was preserved; review it and retry processing.')})

    def action_retry_processing(self):
        self.check_access('read')
        bots = self.mapped('bot_id').sorted('id')
        for bot in bots:
            bot._require_operator()
        bots.sudo().lock_for_update()
        self.sudo().lock_for_update()
        self.invalidate_recordset()
        if any(update.state != 'failed' for update in self):
            raise UserError(_('Only failed updates can be retried.'))
        self.sudo()._process_saved()
        return True

    def _process_one(self):
        self.ensure_one()
        if self.update_type not in UPDATE_TYPES:
            self._set({'state': 'ignored', 'error': False})
            return
        data = self.raw_update[self.update_type]
        chat = data.get('chat', {})
        stamp = int(data.get('edit_date') or data.get('date') or 0)
        at = datetime.datetime.fromtimestamp(stamp, datetime.timezone.utc).replace(tzinfo=None) if stamp else False
        version = [stamp, int(self.update_id)]
        vals = {'event_at': at, 'chat_id': str(chat['id']) if chat.get('id') else False,
                'message_id': str(data['message_id']) if data.get('message_id') else False,
                'text': data.get('text') or data.get('caption') or False, 'state': 'processed', 'error': False}
        sender = data.get('from') or {}
        vals['sender_id'] = str(sender['id']) if sender.get('id') else False
        if sender.get('id') and not sender.get('is_bot'):
            client = self._upsert_client(sender, chat, data, version)
            vals['client_id'] = client.id
        if chat.get('type') in ('group', 'supergroup', 'channel'):
            group = self._upsert_group(chat, data, version)
            vals['group_id'] = group.id
        self._set(vals)

    def _upsert_client(self, sender, chat, data, version):
        model = self.env['ab_telegram_bot_client'].with_context(active_test=False)
        client = model.search(fields.Domain('company_id', '=', self.company_id.id)
                              & fields.Domain('client_id', '=', str(sender['id'])), limit=1)
        name = ' '.join(part for part in (sender.get('first_name'), sender.get('last_name')) if part) or str(sender['id'])
        if not client:
            client = model.create({'company_id': self.company_id.id, 'client_id': str(sender['id']), 'client_name': name})
        client.lock_for_update()
        client.invalidate_recordset()
        vals = {'observed_bot_ids': [fields.Command.link(self.bot_id.id)]}
        if version >= (client.telegram_profile_version or [0, 0]):
            vals.update(client_name=name, username=sender.get('username') or False, telegram_profile_version=version)
        # A group command is never evidence of a private conversation.
        if chat.get('type') == 'private' and str(chat.get('id')) == str(sender['id']):
            vals['private_chat_id'] = str(chat['id'])
            text = data.get('text') or ''
            entities = data.get('entities') or []
            if self.update_type == 'message' and any(e.get('type') == 'bot_command' and e.get('offset') == 0 for e in entities):
                command, _, mention = (text.split(None, 1)[0] if text else '').partition('@')
                if command == '/start' and (not mention or mention.lower() == (self.bot_id.username or '').lower()):
                    vals['started_bot_ids'] = [fields.Command.link(self.bot_id.id)]
        client._apply_update(vals)
        return client

    def _upsert_group(self, chat, data, version):
        model = self.env['ab_telegram_bot_group'].with_context(active_test=False)
        group = model.search(fields.Domain('company_id', '=', self.company_id.id)
                             & fields.Domain('chat_id', '=', str(chat['id'])), limit=1)
        if not group:
            group = model.create({'company_id': self.company_id.id, 'chat_id': str(chat['id']),
                                  'name': chat.get('title') or str(chat['id']), 'chat_type': chat['type']})
        group.lock_for_update()
        group.invalidate_recordset()
        vals = {'observed_bot_ids': [fields.Command.link(self.bot_id.id)]}
        if version >= (group.telegram_profile_version or [0, 0]):
            vals.update(name=chat.get('title') or group.name, chat_type=chat['type'], telegram_profile_version=version)
        stamps = dict(group.telegram_membership_versions or {})
        key = str(self.bot_id.id)
        if version >= stamps.get(key, [0, 0]):
            present = True
            if self.update_type == 'my_chat_member':
                member = data['new_chat_member']
                if str(member['user']['id']) != self.bot_id.poll_identity:
                    raise ValueError('Unexpected membership subject')
                present = member['status'] in ('creator', 'administrator', 'member') or (
                    member['status'] == 'restricted' and member.get('is_member', False))
            vals['bot_ids'] = [fields.Command.link(self.bot_id.id) if present else fields.Command.unlink(self.bot_id.id)]
            stamps[key] = version
            vals['telegram_membership_versions'] = stamps
        group._apply_update(vals)
        return group


class TelegramObservedClient(models.Model):
    _inherit = 'ab_telegram_bot_client'

    observed_bot_ids = fields.Many2many('ab_telegram_bot', 'ab_tg_client_observed_rel',
        'client_id', 'bot_id', string='Observed Bots', readonly=True, check_company=True, copy=False)
    telegram_profile_version = fields.Json(readonly=True, copy=False)
    started_bot_ids = fields.Many2many(string='Started Bots',
        help='Bots started with a private /start received through Fetch Updates, or recorded manually.')

    @api.model_create_multi
    def create(self, vals_list):
        if any({'observed_bot_ids', 'telegram_profile_version'} & set(vals) for vals in vals_list):
            raise AccessError(_('Observation metadata cannot be edited manually.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'observed_bot_ids', 'telegram_profile_version'} & set(vals):
            raise AccessError(_('Observation metadata cannot be edited manually.'))
        return super().write(vals)

    def _apply_update(self, vals):
        return super().write(vals)


class TelegramObservedGroup(models.Model):
    _inherit = 'ab_telegram_bot_group'

    observed_bot_ids = fields.Many2many('ab_telegram_bot', 'ab_tg_group_observed_rel',
        'group_id', 'bot_id', string='Observed Bots', readonly=True, check_company=True, copy=False)
    telegram_profile_version = fields.Json(readonly=True, copy=False)
    telegram_membership_versions = fields.Json(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        if any({'observed_bot_ids', 'telegram_profile_version', 'telegram_membership_versions'} & set(vals) for vals in vals_list):
            raise AccessError(_('Observation metadata cannot be edited manually.'))
        return super().create(vals_list)

    def write(self, vals):
        if {'observed_bot_ids', 'telegram_profile_version', 'telegram_membership_versions'} & set(vals):
            raise AccessError(_('Observation metadata cannot be edited manually.'))
        return super().write(vals)

    def _apply_update(self, vals):
        return super().write(vals)
