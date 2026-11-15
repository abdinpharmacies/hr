from datetime import date, datetime, timedelta
import secrets
import time
import hashlib
import json
import pytz
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EtaConfig(models.Model):
    _name = 'ab_tax_eta_archive_config'
    _description = 'ETA Archive Configuration'

    name = fields.Char(required=True, default='ETA Archive')
    active = fields.Boolean(default=True)
    taxpayer_rin = fields.Char(string='Taxpayer RIN', groups='ab_tax_eta_archive.group_eta_manager')
    callback_key = fields.Char(string='Callback Pre-shared Key', copy=False,
                               default=lambda self: secrets.token_urlsafe(32),
                               groups='ab_tax_eta_archive.group_eta_manager')
    detail_last_request_at = fields.Datetime(string='Last ETA detail request',
                                             copy=False, readonly=True)
    request_schedule = fields.Json(string='ETA Request Schedule', copy=False, readonly=True,
                                   groups='ab_tax_eta_archive.group_eta_manager')
    access_tokens = fields.Json(string='ETA Authentication Cache', copy=False, readonly=True,
                                groups='ab_tax_eta_archive.group_eta_manager')

    def _eta_auth_headers(self, kind, session=None, force_refresh=False):
        self.ensure_one()
        pos = kind == 'receipt' and self.receipt_auth_mode == 'pos'
        client_id = self.receipt_client_id if pos else self.invoice_client_id
        client_secret = self.receipt_client_secret if pos else self.invoice_client_secret
        if not client_id or not client_secret:
            raise UserError(_('Configure ETA credentials before retrieving export details.'))
        identity_url, api_url = self._base_urls()
        options = {}
        data = {'grant_type': 'client_credentials'}
        if pos:
            required = (self.pos_serial, self.pos_os_version,
                        self.pos_model_framework, self.pos_preshared_key)
            if not all(required):
                raise UserError(_('Configure all ETA POS authentication headers.'))
            options['headers'] = dict(zip(
                ('posserial', 'pososversion', 'posmodelframework', 'presharedkey'), required))
            data.update({'client_id': client_id, 'client_secret': client_secret})
        else:
            options['auth'] = (client_id, client_secret)
        fingerprint = hashlib.sha256(json.dumps(
            [identity_url, client_id, client_secret, options.get('headers')],
            sort_keys=True).encode()).hexdigest()
        cached = (self.access_tokens or {}).get(fingerprint, {})
        token = cached.get('token') if cached.get('expires_at', 0) > time.time() else None
        if force_refresh or not token:
            payload = self.env['ab_tax_eta_archive_sync']._request(
                'POST', f'{identity_url}/connect/token', data=data,
                request_session=session, request_attempts=1, timeout=(5, 10), **options)
            token = payload.get('access_token')
            if not token:
                raise UserError(_('ETA authentication returned no access token.'))
            expires_in = max(0, float(payload.get('expires_in') or 0) - 60)
            if self.try_lock_for_update():
                self.invalidate_recordset(['access_tokens'])
                tokens = {key: value for key, value in (self.access_tokens or {}).items()
                          if value.get('expires_at', 0) > time.time()}
                tokens[fingerprint] = {'token': token, 'expires_at': time.time() + expires_in}
                self.write({'access_tokens': tokens})
        return api_url, {'Authorization': f'Bearer {token}', 'Accept': 'application/json',
                         'Content-Type': 'application/json'}

    def _detail_rate_owner(self, kind):
        """Duplicate connections sharing an ERP/POS identity share its API budget."""
        self.ensure_one()
        pos = kind == 'receipt' and self.receipt_auth_mode == 'pos'
        client_field = 'receipt_client_id' if pos else 'invoice_client_id'
        domain = (fields.Domain('environment', '=', self.environment) &
                  fields.Domain(client_field, '=', self[client_field]))
        if pos:
            domain &= fields.Domain('receipt_auth_mode', '=', 'pos')
        return self.with_context(active_test=False).search(domain, order='id', limit=1)

    def _reserve_detail_request(self, endpoint, deadline):
        """Reserve a subsecond slot across workers; called outside savepoints."""
        from .eta_sync import EtaRequestDeferred
        self.ensure_one()
        if not self.try_lock_for_update():
            raise EtaRequestDeferred()
        self.invalidate_recordset(['request_schedule'])
        schedule = dict(self.request_schedule or {})
        wait = max(0, schedule.get(endpoint, 0) - time.time())
        if time.monotonic() + wait + 1 >= deadline:
            raise EtaRequestDeferred()
        if wait:
            time.sleep(wait)
        # ETA allows two calls/second per API. Keep a small safety margin.
        schedule[endpoint] = time.time() + 0.6
        self.write({'request_schedule': schedule})
        if self.env.context.get('cron_id'):
            if not self.env['ir.cron']._commit_progress(0, remaining=1):
                raise EtaRequestDeferred()

    def _defer_detail_requests(self, endpoint, delay):
        # The reservation commit releases the lock before the HTTP request.
        # Reacquire it so another endpoint's reservation is never overwritten.
        self.lock_for_update()
        self.invalidate_recordset(['request_schedule'])
        schedule = dict(self.request_schedule or {})
        schedule[endpoint] = max(schedule.get(endpoint, 0), time.time() + delay)
        self.write({'request_schedule': schedule})
        if self.env.context.get('cron_id'):
            self.env['ir.cron']._commit_progress(0, remaining=0)

    callback_url = fields.Char(string='Callback Base URL', compute='_compute_callback_url',
                               groups='ab_tax_eta_archive.group_eta_manager')

    def _compute_callback_url(self):
        for config in self:
            config.callback_url = (f'{config.get_base_url().rstrip("/")}/ab_tax_eta_archive/callback/{config.id}'
                                   if isinstance(config.id, int) else False)
    environment = fields.Selection([('production', 'Production'), ('preproduction', 'Preproduction')],
                                   required=True, default='production')
    start_date = fields.Date(required=True, default='2026-10-01')
    telegram_start_date = fields.Date(
        string='Telegram Delivery Start Date',
        help='Automatically send unsent files with issue dates on or after this date. '
             'Leave empty to use the archive start date. Automatic delivery waits four days.',
        default=lambda self: datetime.now(pytz.timezone('Africa/Cairo')).date() - timedelta(days=4))
    telegram_scan_date = fields.Date(string='Next Telegram Scan Date', copy=False, readonly=True,
                                    groups='ab_tax_eta_archive.group_eta_manager')
    invoice_client_id = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    invoice_client_secret = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    receipt_client_id = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    receipt_client_secret = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    receipt_auth_mode = fields.Selection(
        [('taxpayer', 'Taxpayer ERP'), ('pos', 'POS Device')],
        string='Receipt Authentication', required=True, default='taxpayer',
        help='Taxpayer ERP uses the Invoice API credentials for invoices and receipts across authorized POS devices. Select POS Device to use separate device credentials.',
        groups='ab_tax_eta_archive.group_eta_manager')
    pos_serial = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_os_version = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_model_framework = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    pos_preshared_key = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')
    telegram_chat_id = fields.Char(
        groups='ab_tax_eta_archive.group_eta_manager',
        help='Enter a negative numeric group chat ID or a public @username. Invite links and bot IDs cannot receive group files.')
    telegram_bot_token = fields.Char(groups='ab_tax_eta_archive.group_eta_manager')

    @api.constrains('start_date')
    def _check_start_date(self):
        for config in self:
            if config.start_date and config.start_date > date.today():
                raise ValidationError(_('The ETA start date cannot be in the future.'))

    def _base_urls(self):
        self.ensure_one()
        prefix = 'preprod.' if self.environment == 'preproduction' else ''
        return (f'https://id.{prefix}eta.gov.eg',
                f'https://api.{prefix}invoicing.eta.gov.eg')

    def action_find_telegram_group_ids(self):
        self.ensure_one()
        self.check_access('write')
        token = (self.telegram_bot_token or '').strip()
        if not token:
            raise UserError(_('Configure the Telegram bot token first.'))
        try:
            response = requests.get(
                f'https://api.telegram.org/bot{token}/getUpdates',
                params={'limit': 100}, timeout=15)
        except requests.RequestException as exc:
            raise UserError(_(
                'Could not read Telegram group updates (%(reason)s).',
                reason=type(exc).__name__)) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise UserError(_('Telegram returned an invalid group update response.')) from exc
        if not isinstance(payload, dict) or not payload.get('ok'):
            detail = payload.get('description') if isinstance(payload, dict) else None
            detail = ' '.join(str(detail or response.reason or response.status_code).split())[:300]
            detail = detail.replace(token, '***')
            raise UserError(_(
                'Telegram could not list group updates: %(detail)s', detail=detail))
        groups = {}
        for update in payload.get('result', []):
            if not isinstance(update, dict):
                continue
            for key in ('message', 'my_chat_member', 'chat_member', 'channel_post'):
                event = update.get(key)
                chat = event.get('chat') if isinstance(event, dict) else None
                if (isinstance(chat, dict) and
                        chat.get('type') in ('group', 'supergroup') and
                        isinstance(chat.get('id'), int)):
                    groups[chat['id']] = chat.get('title') or str(chat['id'])
        if not groups:
            raise UserError(_(
                'No Telegram group updates found. Add this bot to the intended group and send it a command there, then try again.'))
        message = '\n'.join(f'{title}: {chat_id}'
                            for chat_id, title in sorted(groups.items(), key=lambda item: item[1]))
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'title': _('Telegram Group Chat IDs'), 'message': message,
                       'type': 'info', 'sticky': True},
        }
