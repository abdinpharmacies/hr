from datetime import date, datetime, timedelta
import secrets
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
        default=lambda self: datetime.now(pytz.timezone('Africa/Cairo')).date() - timedelta(days=4))
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
