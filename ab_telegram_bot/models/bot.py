import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

from . import transport


METHODS = {
    'sendMessage', 'sendDocument', 'sendPhoto', 'sendVideo', 'sendAudio', 'sendVoice',
    'sendAnimation', 'sendMediaGroup', 'editMessageText', 'editMessageCaption',
    'deleteMessage', 'forwardMessage', 'copyMessage', 'setMessageReaction', 'sendChatAction',
}


def chat_id(value):
    value = str(value or '').strip()
    if not re.fullmatch(r'-?[1-9][0-9]*|@[A-Za-z][A-Za-z0-9_]{4,}', value):
        raise ValidationError(_('Enter a numeric Telegram chat ID or a public @username.'))
    return value


def plain_chunks(text, limit=4000):
    """Conservative UTF-16 limit; prefer newline boundaries without losing content."""
    while text:
        count, end, newline = 0, 0, 0
        for character in text:
            units = 2 if ord(character) > 0xffff else 1
            if count + units > limit:
                break
            count += units
            end += 1
            if character == '\n':
                newline = end
        if end < len(text) and newline:
            end = newline
        yield text[:end]
        text = text[end:]


class TelegramBot(models.Model):
    _name = 'ab_telegram_bot'
    _description = 'Telegram Bot'
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    token = fields.Char(required=True, copy=False, exportable=False, groups='ab_telegram_bot.group_administrator')
    bot_id = fields.Char(string='Telegram Bot ID', readonly=True, copy=False)
    username = fields.Char(readonly=True, copy=False)
    operator_ids = fields.Many2many('res.users', string='Authorized Users', domain=[('share', '=', False)])
    checked_at = fields.Datetime(readonly=True)
    connection_note = fields.Char(readonly=True)
    next_send_at = fields.Datetime(readonly=True, copy=False)
    _unique_bot = models.Constraint('UNIQUE(company_id, bot_id)', 'This Telegram bot is already registered in this company.')

    @api.constrains('token')
    def _check_token(self):
        for bot in self:
            if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', bot.token or ''):
                raise ValidationError(_('Enter a valid bot token from BotFather.'))

    def export_data(self, fields_to_export):
        if 'token' in fields_to_export:
            raise AccessError(_('Bot tokens cannot be exported.'))
        return super().export_data(fields_to_export)

    def _require_operator(self):
        self.ensure_one()
        self.check_access('read')
        if not (self.env.user.has_group('ab_telegram_bot.group_operator')
                or self.env.user.has_group('ab_telegram_bot.group_administrator')):
            raise AccessError(_('Telegram Operator access is required.'))
        if not self.active or self.company_id not in self.env.companies:
            raise UserError(_('Choose an active bot in an allowed company.'))

    def _call(self, method, payload=None, files=None):
        self.ensure_one()
        return transport.request(self.sudo().token, method, payload or {}, files)

    def _read_api(self, method, payload=None):
        self._require_operator()
        try:
            return self._call(method, payload)
        except transport.TelegramFailure as exc:
            raise UserError(_('Telegram request failed (HTTP code %s). Check the token, destination and bot permissions.', exc.code)) from None

    def action_check_connection(self):
        for bot in self:
            result = bot._read_api('getMe')
            bot.write({'bot_id': str(result['id']), 'username': result.get('username'),
                       'checked_at': fields.Datetime.now(), 'connection_note': _('Connection successful.')})
        return True

    def get_me(self):
        return self._read_api('getMe')

    def get_chat(self, destination):
        return self._read_api('getChat', {'chat_id': chat_id(destination)})

    def get_chat_member(self, destination, user_id):
        return self._read_api('getChatMember', {'chat_id': chat_id(destination), 'user_id': int(user_id)})

    def get_file(self, file_id):
        return self._read_api('getFile', {'file_id': str(file_id)})

    def download_file(self, file_id, filename='telegram-file'):
        info = self.get_file(file_id)
        if info.get('file_size', 0) > 20 * 1024 * 1024:
            raise UserError(_('Telegram file downloads are limited to 20 MiB.'))
        try:
            content = transport.download(self.sudo().token, info['file_path'])
        except transport.TelegramFailure:
            raise UserError(_('Telegram file download failed.')) from None
        return self.env['ir.attachment'].create({'name': filename, 'raw': content,
                                               'company_id': self.company_id.id}).id

    def _queue(self, method, destination, values=None, uploads=None, **options):
        self._require_operator()
        if method not in METHODS:
            raise ValidationError(_('Unsupported Telegram method.'))
        payload = dict(values or {}, **options)
        payload['chat_id'] = chat_id(destination)
        return self.env['ab_telegram_bot_message']._enqueue(self, method, payload, uploads=uploads)

    def send_message(self, destination, text, **options):
        self._require_operator()
        return self.env['ab_telegram_bot_message']._enqueue_text(self, destination, text, options=options)

    def _media(self, method, key, destination, source, caption=None, **options):
        uploads = {}
        if isinstance(source, (int, dict)):
            uploads[key] = source
            source = 'attach://' + key
        values = {key: source}
        if caption is not None:
            values['caption'] = caption
        return self._queue(method, destination, values, uploads, **options)

    def send_document(self, destination, source, caption=None, **options):
        return self._media('sendDocument', 'document', destination, source, caption, **options)

    def send_file(self, destination, source, caption=None, **options):
        return self.send_document(destination, source, caption, **options)

    def send_photo(self, destination, source, caption=None, **options):
        return self._media('sendPhoto', 'photo', destination, source, caption, **options)

    def send_image(self, destination, source, caption=None, **options):
        return self.send_photo(destination, source, caption, **options)

    def send_video(self, destination, source, caption=None, **options):
        return self._media('sendVideo', 'video', destination, source, caption, **options)

    def send_audio(self, destination, source, caption=None, **options):
        return self._media('sendAudio', 'audio', destination, source, caption, **options)

    def send_voice(self, destination, source, caption=None, **options):
        return self._media('sendVoice', 'voice', destination, source, caption, **options)

    def send_animation(self, destination, source, caption=None, **options):
        return self._media('sendAnimation', 'animation', destination, source, caption, **options)

    def send_media_group(self, destination, media, **options):
        if not isinstance(media, list) or not 2 <= len(media) <= 10:
            raise ValidationError(_('A media group requires 2 to 10 items.'))
        uploads, items = {}, []
        for index, item in enumerate(media):
            item = dict(item)
            if item.get('type') not in ('photo', 'video', 'audio', 'document'):
                raise ValidationError(_('Unsupported media group item type.'))
            source = item.get('media')
            if isinstance(source, (int, dict)):
                key = 'file%s' % index
                uploads[key] = source
                item['media'] = 'attach://' + key
            items.append(item)
        kinds = {item['type'] for item in items}
        if ('audio' in kinds or 'document' in kinds) and len(kinds) > 1:
            raise ValidationError(_('Audio and document albums must contain only their own media type.'))
        return self._queue('sendMediaGroup', destination, {'media': items}, uploads, **options)

    def edit_message_text(self, destination, message_id, text, **options):
        return self._queue('editMessageText', destination, {'message_id': int(message_id), 'text': text}, **options)

    def edit_message_caption(self, destination, message_id, caption, **options):
        return self._queue('editMessageCaption', destination, {'message_id': int(message_id), 'caption': caption}, **options)

    def delete_message(self, destination, message_id):
        return self._queue('deleteMessage', destination, {'message_id': int(message_id)})

    def forward_message(self, destination, from_chat_id, message_id, **options):
        return self._queue('forwardMessage', destination, {'from_chat_id': chat_id(from_chat_id), 'message_id': int(message_id)}, **options)

    def copy_message(self, destination, from_chat_id, message_id, **options):
        return self._queue('copyMessage', destination, {'from_chat_id': chat_id(from_chat_id), 'message_id': int(message_id)}, **options)

    def set_message_reaction(self, destination, message_id, emoji=None):
        return self._queue('setMessageReaction', destination, {'message_id': int(message_id),
                           'reaction': [{'type': 'emoji', 'emoji': emoji}] if emoji else []})

    def send_chat_action(self, destination, action='typing', **options):
        return self._queue('sendChatAction', destination, {'action': action}, **options)


class TelegramClient(models.Model):
    _name = 'ab_telegram_bot_client'
    _description = 'Telegram Client'
    _rec_name = 'client_name'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    client_id = fields.Char(required=True, string='Telegram User ID')
    client_name = fields.Char(required=True)
    username = fields.Char()
    private_chat_id = fields.Char()
    started_bot_ids = fields.Many2many('ab_telegram_bot', check_company=True,
        string='Started Bots (Manual)', help='Manually recorded; incoming Telegram updates are not collected.')
    _unique_client = models.Constraint('UNIQUE(company_id, client_id)', 'This Telegram client is already registered.')

    @api.constrains('client_id', 'private_chat_id')
    def _check_ids(self):
        for client in self:
            if not re.fullmatch(r'[1-9][0-9]*', client.client_id or ''):
                raise ValidationError(_('Telegram User ID must be a positive numeric ID.'))
            if client.private_chat_id:
                chat_id(client.private_chat_id)


class TelegramGroup(models.Model):
    _name = 'ab_telegram_bot_group'
    _description = 'Telegram Group'
    _check_company_auto = True

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    chat_id = fields.Char(required=True)
    chat_type = fields.Selection([('group', 'Group'), ('supergroup', 'Supergroup'), ('channel', 'Channel')], default='supergroup')
    bot_ids = fields.Many2many('ab_telegram_bot', check_company=True, string='Bots')
    validation_note = fields.Text(readonly=True)
    checked_at = fields.Datetime(readonly=True)
    _unique_chat = models.Constraint('UNIQUE(company_id, chat_id)', 'This Telegram group is already registered.')

    @api.constrains('chat_id')
    def _check_chat(self):
        for group in self:
            chat_id(group.chat_id)

    def action_validate_group(self):
        for group in self:
            group.check_access('read')
            if not group.bot_ids:
                raise UserError(_('Add at least one bot to validate the group.'))
            notes = []
            for bot in group.bot_ids:
                info = bot.get_chat(group.chat_id)
                if info.get('type') not in ('group', 'supergroup', 'channel'):
                    raise ValidationError(_('This chat is not a group or channel.'))
                member = bot.get_chat_member(group.chat_id, bot.get_me()['id'])
                notes.append('%s: %s' % (bot.name, member.get('status', 'unknown')))
            group.sudo().write({'name': info.get('title') or group.name, 'chat_type': info['type'],
                         'validation_note': '\n'.join(notes), 'checked_at': fields.Datetime.now()})
        return True


class TelegramSubscription(models.Model):
    _name = 'ab_telegram_bot_module_subscription'
    _description = 'Telegram Module Subscription'
    _rec_name = 'module_id'
    _check_company_auto = True

    active = fields.Boolean(default=True)
    enabled = fields.Boolean(default=False)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    module_id = fields.Many2one('ir.module.module', required=True, ondelete='cascade', domain=[('state', '=', 'installed')])
    bot_id = fields.Many2one('ab_telegram_bot', required=True, check_company=True, ondelete='restrict')
    default_group_id = fields.Many2one('ab_telegram_bot_group', check_company=True, ondelete='restrict')
    default_group_chat_id = fields.Char(string='Default Group Chat ID')
    topic_id = fields.Integer(string='Default Topic ID')
    language = fields.Selection([('en_US', 'English'), ('ar', 'Arabic'), ('ar_001', 'Arabic (World)')], default='en_US', required=True)
    _unique_subscription = models.Constraint('UNIQUE(company_id, module_id)', 'Only one subscription per module and company is allowed.')

    @api.constrains('default_group_id', 'default_group_chat_id', 'enabled', 'bot_id', 'topic_id')
    def _check_destination(self):
        for sub in self:
            if sub.default_group_chat_id:
                chat_id(sub.default_group_chat_id)
            if sub.topic_id < 0:
                raise ValidationError(_('Topic ID cannot be negative.'))
            if sub.enabled and (not sub.bot_id.active or not sub._destination()):
                raise ValidationError(_('An enabled subscription requires an active bot and a default destination.'))
            if sub.default_group_id and sub.bot_id not in sub.default_group_id.bot_ids:
                raise ValidationError(_('The selected bot must be associated with the selected group.'))

    def _destination(self):
        self.ensure_one()
        return self.default_group_chat_id or self.default_group_id.chat_id

    def action_send_test(self):
        self.ensure_one()
        self.check_access('read')
        if not self._destination():
            raise UserError(_('Set a default destination first.'))
        self.bot_id.send_message(self._destination(), _('Telegram connection test from Odoo.'),
                                 message_thread_id=self.topic_id or None)
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': _('Telegram'), 'message': _('Test message queued.'), 'type': 'success'}}
