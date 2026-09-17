import base64
import binascii
import datetime
import json
import re
import uuid

from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.modules.registry import Registry
from odoo.addons.queue_job.exception import RetryableJobError

from .bot import METHODS, chat_id, plain_chunks
from . import transport


class TelegramMessage(models.Model):
    _name = 'ab_telegram_bot_message'
    _description = 'Telegram Delivery'
    _order = 'id desc'
    _rec_name = 'method'

    company_id = fields.Many2one('res.company', required=True, readonly=True)
    bot_id = fields.Many2one('ab_telegram_bot', required=True, readonly=True, ondelete='restrict')
    chat_id = fields.Char(required=True, readonly=True)
    method = fields.Char(required=True, readonly=True)
    payload = fields.Json(readonly=True)
    upload_map = fields.Json(readonly=True)
    attachment_ids = fields.Many2many('ir.attachment', readonly=True)
    state = fields.Selection([('queued', 'Queued'), ('sending', 'Sending'), ('sent', 'Sent'),
                              ('failed', 'Failed'), ('unknown', 'Delivery Unknown'), ('cancelled', 'Cancelled')],
                             default='queued', required=True, readonly=True)
    attempts = fields.Integer(readonly=True)
    error = fields.Text(readonly=True)
    telegram_message_ids = fields.Char(string='Telegram Message IDs', readonly=True)
    sent_at = fields.Datetime(readonly=True)
    retry_at = fields.Datetime(readonly=True)
    dedupe_key = fields.Char(required=True, readonly=True, index=True)
    order_key = fields.Char(required=True, readonly=True, index=True)
    queue_job_id = fields.Many2one('queue.job', readonly=True, ondelete='set null')
    source_model = fields.Char(readonly=True)
    source_id = fields.Integer(readonly=True)
    _unique_delivery = models.Constraint('UNIQUE(company_id, dedupe_key)', 'This notification is already queued.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Use a bot messaging method to create deliveries.'))

    def write(self, vals):
        raise AccessError(_('Delivery history can only be changed by delivery actions.'))

    def unlink(self):
        raise AccessError(_('Delivery history cannot be deleted.'))

    def _set(self, vals):
        return super().write(vals)

    @api.model
    def _enqueue_text(self, bot, destination, text, options=None, dedupe_key=None, order_key=None,
                      source_model=None, source_id=None):
        if not isinstance(text, str) or not text.strip():
            raise ValidationError(_('Message text cannot be empty.'))
        options = dict(options or {})
        chunks = list(plain_chunks(text))
        if len(chunks) > 1 and (options.get('parse_mode') or options.get('entities')):
            raise ValidationError(_('Split formatted messages into blocks of at most 4000 UTF-16 units before sending.'))
        key = dedupe_key or uuid.uuid4().hex
        messages = self.browse()
        for index, chunk in enumerate(chunks):
            messages |= self._enqueue(bot, 'sendMessage', dict(options, chat_id=chat_id(destination), text=chunk),
                dedupe_key='%s:%s' % (key, index), order_key=order_key or key,
                source_model=source_model, source_id=source_id)
        return messages

    @api.model
    def _enqueue(self, bot, method, payload, uploads=None, dedupe_key=None, order_key=None,
                 source_model=None, source_id=None):
        bot.ensure_one()
        if method not in METHODS or not bot.active:
            raise ValidationError(_('Choose an active bot and a supported method.'))
        payload = json.loads(json.dumps(payload))
        destination = chat_id(payload.get('chat_id'))
        for item in [payload] + payload.get('media', []):
            for field, limit in [('text', 4096), ('caption', 1024)]:
                value = item.get(field)
                if value is not None and (not isinstance(value, str) or len(value.encode('utf-16-le')) // 2 > limit):
                    raise ValidationError(_('Telegram text or caption exceeds the supported length.'))
        key = dedupe_key or uuid.uuid4().hex
        # Serialize creation by bot; notification callers additionally hold source locks.
        bot.sudo().lock_for_update()
        existing = self.sudo().search(fields.Domain('company_id', '=', bot.company_id.id)
                                      & fields.Domain('dedupe_key', '=', key), limit=1)
        if existing:
            return existing
        snapshots = {}
        for parameter, source in (uploads or {}).items():
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', parameter):
                raise ValidationError(_('Invalid upload parameter.'))
            if isinstance(source, int):
                attachment = self.env['ir.attachment'].browse(source).exists()
                if not attachment:
                    raise ValidationError(_('Attachment not found.'))
                attachment.check_access('read')
                if attachment.company_id and attachment.company_id != bot.company_id:
                    raise AccessError(_('The attachment and bot must belong to the same company.'))
                raw, name = attachment.raw, attachment.name
            elif isinstance(source, dict) and set(source) <= {'data', 'filename'}:
                try:
                    raw = base64.b64decode(source.get('data', ''), validate=True)
                except (ValueError, binascii.Error):
                    raise ValidationError(_('Upload data must be valid base64.')) from None
                name = source.get('filename') or parameter
            else:
                raise ValidationError(_('Use an attachment ID, base64 upload, or Telegram file ID.'))
            photo = method == 'sendPhoto' or any(i.get('type') == 'photo' and i.get('media') == 'attach://' + parameter for i in payload.get('media', []))
            if not raw or len(raw) > (10 if photo else 50) * 1024 * 1024:
                raise ValidationError(_('Uploads must be nonempty and no larger than 10 MiB for photos or 50 MiB for other media.'))
            snapshots[parameter] = (raw, str(name).replace('/', '_')[:200])
        message = super(TelegramMessage, self.sudo()).create({
            'company_id': bot.company_id.id, 'bot_id': bot.id, 'chat_id': destination,
            'method': method, 'payload': payload, 'dedupe_key': key, 'order_key': order_key or key,
            'source_model': source_model, 'source_id': source_id})
        mapping, attachments = {}, self.env['ir.attachment'].sudo().browse()
        for parameter, (raw, name) in snapshots.items():
            attachment = self.env['ir.attachment'].sudo().create({'name': name, 'raw': raw,
                'company_id': bot.company_id.id, 'res_model': self._name, 'res_id': message.id})
            mapping[parameter] = attachment.id
            attachments |= attachment
        message._set({'upload_map': mapping, 'attachment_ids': [fields.Command.set(attachments.ids)]})
        message._schedule()
        return message

    def _schedule(self):
        for message in self:
            pending = message.with_delay(channel='root.telegram', max_retries=0,
                identity_key='telegram:%s' % message.id, description=_('Telegram delivery %s', message.id))._deliver()
            message._set({'queue_job_id': pending.db_record().id})

    def action_retry(self):
        for message in self:
            message.check_access('read')
            message.bot_id._require_operator()
            message.lock_for_update()
            message.invalidate_recordset()
            if message.queue_job_id.state in ('pending', 'enqueued', 'started', 'wait_dependencies'):
                raise UserError(_('A queue job is already handling this delivery.'))
            if message.state not in ('failed', 'unknown', 'sending'):
                raise UserError(_('Only failed or uncertain deliveries can be retried.'))
            message.sudo()._set({'state': 'queued', 'attempts': 0, 'error': False, 'retry_at': False})
            message.sudo()._schedule()
        return True

    def action_cancel(self):
        for message in self:
            message.check_access('read')
            message.bot_id._require_operator()
            message.lock_for_update()
            message.invalidate_recordset()
            if message.state == 'sending':
                raise UserError(_('A sending delivery cannot be cancelled while its queue job is active.'))
            if message.state in ('queued', 'failed', 'unknown'):
                message.sudo()._set({'state': 'cancelled'})
        return True

    def _deliver(self):
        """Persist send intent before HTTP; a recovered worker must not blindly resend."""
        self.ensure_one()
        dbname, message_id = self.env.cr.dbname, self.id

        def transaction(callback):
            with Registry(dbname).cursor() as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                message = env[self._name].browse(message_id)
                result = callback(message)
                cr.commit()
                return result

        def claim(message):
            # Consistent lock order with enqueue: bot, then delivery.
            bot = message.bot_id
            bot.lock_for_update()
            bot.invalidate_recordset()
            message.lock_for_update()
            message.invalidate_recordset()
            if message.state == 'sending':
                message._set({'state': 'unknown', 'error': _('Previous delivery was interrupted after send intent. Review Telegram before retrying.')})
                return None
            if message.state != 'queued':
                return None
            older = message.search(fields.Domain('company_id', '=', message.company_id.id)
                & fields.Domain('order_key', '=', message.order_key) & fields.Domain('id', '<', message.id)
                & fields.Domain('state', 'in', ['queued', 'sending']), limit=1)
            now = fields.Datetime.now()
            wait = max([0] + [(stamp - now).total_seconds() for stamp in (bot.next_send_at, message.retry_at) if stamp])
            if older or wait > 0:
                return {'wait': max(5, wait)}
            if not bot.active or not bot.token:
                message._set({'state': 'failed', 'error': _('Bot is inactive or its token is missing.')})
                return None
            message._set({'state': 'sending', 'attempts': message.attempts + 1, 'error': False})
            # Conservative shared pacing also covers group chat limits.
            bot.write({'next_send_at': now + datetime.timedelta(seconds=3)})
            files = {key: (message.env['ir.attachment'].browse(aid).name,
                           message.env['ir.attachment'].browse(aid).raw)
                     for key, aid in (message.upload_map or {}).items()}
            return {'token': bot.token, 'method': message.method, 'payload': message.payload, 'files': files}

        work = transaction(claim)
        if not work:
            return
        if 'wait' in work:
            raise RetryableJobError('Telegram delivery is waiting for its turn.', seconds=work['wait'], ignore_retry=True)
        try:
            result = transport.request(work['token'], work['method'], work['payload'], work['files'] or None)
        except transport.TelegramFailure as failure:
            def fail(message):
                if failure.kind == 'retry' and message.attempts < 5:
                    delay = max(failure.retry_after, min(300, 15 * 2 ** message.attempts))
                    message._set({'state': 'queued', 'retry_at': fields.Datetime.now() + datetime.timedelta(seconds=delay),
                                  'error': _('Telegram temporarily unavailable (HTTP code %s).', failure.code)})
                    return delay
                message._set({'state': 'unknown' if failure.kind == 'unknown' else 'failed',
                              'error': _('Telegram delivery failed or could not be confirmed (HTTP code %s). Check the destination, token and permissions.', failure.code)})
                return 0
            delay = transaction(fail)
            if delay:
                raise RetryableJobError('Telegram delivery will retry.', seconds=delay, ignore_retry=True) from None
            return
        items = result if isinstance(result, list) else [result]
        ids = [str(item['message_id']) for item in items if isinstance(item, dict) and 'message_id' in item]
        transaction(lambda message: message._set({'state': 'sent', 'sent_at': fields.Datetime.now(),
                    'telegram_message_ids': ','.join(ids), 'error': False, 'retry_at': False}))
