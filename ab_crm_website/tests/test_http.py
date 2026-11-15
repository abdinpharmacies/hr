import json
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged
from .test_adapter import TestWebsiteAdapter


@tagged('post_install', '-at_install')
class TestWebsiteHTTP(TestWebsiteAdapter, HttpCase):
    def test_http_bearer_scope_dedup_and_revocation(self):
        key = (
            self.env['res.users.apikeys']
            .with_user(self.service)
            ._generate(
                'rpc', 'Website HTTP test', fields.Datetime.now() + timedelta(days=1)
            )
        )
        event = self.event()
        payload = {
            'account_code': self.account.code,
            'provider_account': self.source,
            'event': event,
        }

        def receive(credential=key, values=payload):
            return self.url_open(
                '/crm/website/v1/receive',
                data=json.dumps(values),
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + credential,
                    'X-Forwarded-Proto': 'https',
                    'X-Forwarded-Host': 'localhost',
                    'X-Odoo-Database': self.env.cr.dbname,
                },
            )

        self.assertEqual(receive('invalid-key').status_code, 401)
        self.assertEqual(
            receive(values=dict(payload, account_code='foreign')).status_code, 403
        )
        self.assertEqual(receive().status_code, 200)
        self.assertEqual(receive().status_code, 200)
        self.assertEqual(
            self.env['ab_crm_website_event'].search_count(
                [('event_uuid', '=', event['event_uuid'])]
            ),
            1,
        )
        self.env['res.users.apikeys'].search(
            [('name', '=', 'Website HTTP test')]
        ).unlink()
        self.assertEqual(receive().status_code, 401)
