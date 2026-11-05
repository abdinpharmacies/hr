import json
from datetime import timedelta
from uuid import uuid4

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestTelegramCredentials(HttpCase):
    def test_controller_credentials_are_account_bound_and_not_cached(self):
        service = self.env.ref('ab_crm_sales_workspace.user_telegram_development')
        service.active = True
        branch = self.env['ab_crm_branch'].create(
            {
                'name': 'Credentials Intake',
                'code': 'credentials-test',
                'user_ids': [fields.Command.link(service.id)],
            }
        )
        channel = self.env['ab_crm_channel'].create(
            {
                'name': 'Credentials Telegram',
                'code': 'credentials-test',
                'provider': 'telegram',
                'branch_id': branch.id,
            }
        )
        self.env['ab_crm_messaging_account'].create(
            {
                'name': 'Credentials Bot',
                'code': 'credentials-test',
                'provider': 'telegram',
                'provider_account': '900000898',
                'channel_id': channel.id,
                'branch_id': branch.id,
                'service_user_id': service.id,
            }
        )
        token = '900000898:SYNTHETIC_TEST_TOKEN_ONLY_123456'
        self.env['ir.config_parameter'].sudo().set_param(
            'ab_crm_sales_workspace.telegram_token.%s.credentials-test'
            % branch.company_id.id,
            token,
        )
        key = (
            self.env['res.users.apikeys']
            .with_user(service)
            ._generate(
                'rpc',
                'Credentials controller test',
                fields.Datetime.now() + timedelta(hours=1),
            )
        )
        envelope = {
            'correlation_id': str(uuid4()),
            'payload': {
                'account_code': 'credentials-test',
                'provider_account': '900000898',
            },
        }
        headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}
        response = self.url_open(
            '/crm/messaging/v1/get_provider_credentials',
            data=json.dumps(envelope),
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
        self.assertEqual(response.json()['result']['token'], token)
        envelope['payload']['provider_account'] = '900000899'
        response = self.url_open(
            '/crm/messaging/v1/get_provider_credentials',
            data=json.dumps(envelope),
            headers=headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(token, response.text)
