import json
from datetime import timedelta
from uuid import uuid4

from odoo import fields
from odoo.tests import HttpCase, tagged


@tagged('post_install', '-at_install')
class TestMessagingController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.service = cls.env['res.users'].create(
            {
                'name': 'Controller Service',
                'login': 'controller-test-service',
                'group_ids': [
                    fields.Command.set(
                        [
                            cls.env.ref('base.group_user').id,
                            cls.env.ref('ab_crm_messaging.group_service').id,
                        ]
                    )
                ],
            }
        )
        cls.key = (
            cls.env['res.users.apikeys']
            .with_user(cls.service)
            ._generate(
                'rpc',
                'Controller test',
                fields.Datetime.now() + timedelta(days=1),
            )
        )
        branch = cls.env['ab_crm_branch'].create(
            {
                'name': 'Controller Intake',
                'code': 'controller-intake',
                'user_ids': [fields.Command.set(cls.service.ids)],
            }
        )
        channel = cls.env['ab_crm_channel'].create(
            {
                'name': 'Controller Telegram',
                'code': 'controller-tg',
                'provider': 'telegram',
                'branch_id': branch.id,
            }
        )
        cls.env['ab_crm_messaging_account'].create(
            {
                'name': 'Controller Bot',
                'code': 'controller-bot',
                'provider': 'telegram',
                'provider_account': '900000789',
                'channel_id': channel.id,
                'branch_id': branch.id,
                'service_user_id': cls.service.id,
                'legacy_worker_disabled': True,
            }
        )

    def call_gateway(self, payload=None, key=None, operation='lease_outgoing'):
        correlation = str(uuid4())
        response = self.url_open(
            '/crm/messaging/v1/' + operation,
            data=json.dumps(
                {
                    'correlation_id': correlation,
                    'payload': payload
                    or {
                        'account_code': 'controller-bot',
                        'provider_account': '900000789',
                    },
                }
            ),
            headers={
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ' + (key or self.key),
            },
        )
        return response, correlation

    def test_bearer_and_account_scope(self):
        response, correlation = self.call_gateway()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {'correlation_id': correlation, 'result': False}
        )
        response, _ = self.call_gateway(key='invalid-key')
        self.assertEqual(response.status_code, 401)
        response, _ = self.call_gateway(
            payload={'account_code': 'foreign', 'provider_account': '900000789'}
        )
        self.assertEqual(response.status_code, 403)

    def test_envelope_cannot_inject_scope_or_methods(self):
        response, _ = self.call_gateway(
            payload={
                'account_code': 'controller-bot',
                'provider_account': '900000789',
                'context': {'sudo': True},
            }
        )
        self.assertEqual(response.status_code, 400)
        response, _ = self.call_gateway(operation='_account')
        self.assertEqual(response.status_code, 400)
        response = self.url_open(
            '/crm/messaging/v1/lease_outgoing',
            data='{}',
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 401)

    def test_staff_key_is_not_service_identity(self):
        staff = self.env['res.users'].create(
            {
                'name': 'Controller Staff',
                'login': 'controller-staff',
                'group_ids': [
                    fields.Command.set(
                        [
                            self.env.ref('base.group_user').id,
                            self.env.ref('ab_crm_core.group_user').id,
                        ]
                    )
                ],
            }
        )
        key = (
            self.env['res.users.apikeys']
            .with_user(staff)
            ._generate(
                'rpc',
                'Staff controller test',
                fields.Datetime.now() + timedelta(hours=1),
            )
        )
        response, _ = self.call_gateway(key=key)
        self.assertEqual(response.status_code, 403)
