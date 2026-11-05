import re

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class TelegramSetup(models.TransientModel):
    _name = 'ab_crm_chatter_telegram_setup'
    _description = 'Sales Chatter Telegram Setup'

    account_code = fields.Char(default='tg-callcenter', required=True)
    bot_username = fields.Char(default='abdin_callcenter_bot', required=True)
    token_configured = fields.Boolean(compute='_compute_connection')
    parameter_key = fields.Char(compute='_compute_connection')
    provider_account = fields.Char(string='Bot ID', compute='_compute_connection')

    def _key(self):
        self.ensure_one()
        return 'ab_crm_sales_workspace.telegram_token.%s.%s' % (
            self.env.company.id,
            self.account_code,
        )

    @api.depends('account_code')
    def _compute_connection(self):
        for wizard in self:
            if not self.env.user.has_group('base.group_system'):
                raise AccessError(_('Only administrators can configure Telegram.'))
            wizard.parameter_key = wizard._key()
            token = self.env['ir.config_parameter'].sudo().get_param(wizard._key(), '')
            wizard.token_configured = bool(token)
            wizard.provider_account = token.partition(':')[0] if token else ''

    def action_save(self):
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only administrators can configure Telegram.'))
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', self.account_code or ''):
            raise UserError(
                _('Use letters, numbers, underscores or hyphens for the account code.')
            )
        parameters = self.env['ir.config_parameter'].sudo()
        token = parameters.get_param(self._key(), '')
        if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]{20,}', token):
            raise UserError(
                _(
                    'Add a valid BotFather token in System Parameters using the displayed key.'
                )
            )
        bot_id = token.partition(':')[0]
        service = self.env.ref('ab_crm_sales_workspace.user_telegram_development')
        accounts = self.env['ab_crm_messaging_account']
        account = accounts.with_context(active_test=False).search(
            [('code', '=', self.account_code)], limit=1
        )
        branches = (
            account.branch_id
            if account
            else self.env['ab_crm_branch'].search(
                [
                    ('company_id', '=', self.env.company.id),
                    ('replica_id', '!=', False),
                ],
                limit=2,
            )
        )
        if len(branches) != 1:
            raise UserError(
                _(
                    'The company must have one configured messaging branch before preparing the connection.'
                )
            )
        branch = branches
        branch.check_access('write')
        if (
            branch.company_id != self.env.company
            or not branch.active
            or service.company_id != branch.company_id
        ):
            raise AccessError(_('The selected company or branch is not allowed.'))
        if account and (
            account.company_id != branch.company_id
            or account.branch_id != branch
            or account.provider != 'telegram'
            or account.provider_account != bot_id
            or account.service_user_id != service
        ):
            raise UserError(
                _('This account code is already mapped to another connection.')
            )
        service.write({'active': True})
        branch.write({'user_ids': [fields.Command.link(service.id)]})
        if not account:
            channel = self.env['ab_crm_channel'].create(
                {
                    'name': self.bot_username,
                    'code': self.account_code,
                    'provider': 'telegram',
                    'branch_id': branch.id,
                    'company_id': branch.company_id.id,
                }
            )
            account = accounts.create(
                {
                    'name': self.bot_username,
                    'code': self.account_code,
                    'provider': 'telegram',
                    'provider_account': bot_id,
                    'channel_id': channel.id,
                    'branch_id': branch.id,
                    'company_id': branch.company_id.id,
                    'service_user_id': service.id,
                    'enabled': False,
                }
            )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Telegram Connection'),
                'message': _(
                    'Connection prepared. Verify the bot with the gateway before enabling reception or sending.'
                ),
                'type': 'success',
                'sticky': True,
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }


class MessagingAPI(models.AbstractModel):
    _inherit = 'ab_crm_messaging_api'

    @api.model
    def get_provider_credentials(self, account_code, provider_account):
        account = self._account(account_code, provider_account)
        if account.provider != 'telegram' or not account.active:
            raise AccessError(_('The messaging account is not authorized.'))
        key = 'ab_crm_sales_workspace.telegram_token.%s.%s' % (
            account.company_id.id,
            account.code,
        )
        token = self.env['ir.config_parameter'].sudo().get_param(key, '')
        if not token or token.partition(':')[0] != account.provider_account:
            raise UserError(
                _('Configure the BotFather token in System Parameters first.')
            )
        return {
            'provider': 'telegram',
            'provider_account': account.provider_account,
            'token': token,
        }
