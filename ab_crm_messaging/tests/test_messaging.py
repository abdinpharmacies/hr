from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestMessaging(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def user(name, group):
            return cls.env['res.users'].create(
                {
                    'name': name,
                    'login': name,
                    'group_ids': [
                        fields.Command.set(
                            [cls.env.ref('base.group_user').id, cls.env.ref(group).id]
                        )
                    ],
                }
            )

        cls.staff = user('messaging-staff', 'ab_crm_core.group_user')
        cls.other = user('messaging-other', 'ab_crm_core.group_user')
        cls.service = user('messaging-service', 'ab_crm_messaging.group_service')
        cls.manager = user('messaging-manager', 'ab_crm_core.group_manager')
        cls.branch = cls.env['ab_crm_branch'].create(
            {
                'name': 'Messaging A',
                'code': 'messaging-a',
                'user_ids': [fields.Command.set((cls.staff | cls.service).ids)],
            }
        )
        cls.channel = cls.env['ab_crm_channel'].create(
            {
                'name': 'Messaging Telegram',
                'code': 'messaging-tg',
                'provider': 'telegram',
                'branch_id': cls.branch.id,
            }
        )
        cls.account = cls.env['ab_crm_messaging_account'].create(
            {
                'name': 'Messaging Telegram',
                'code': 'tg',
                'provider': 'telegram',
                'provider_account': '900000123',
                'branch_id': cls.branch.id,
                'channel_id': cls.channel.id,
                'service_user_id': cls.service.id,
                'legacy_worker_disabled': True,
                'enabled': True,
                'outgoing_enabled': True,
            }
        )
        cls.gateway = cls.env['ab_crm_messaging_api'].with_user(cls.service)

    def receive(self, event_id='1', **values):
        event = dict(
            id=event_id,
            sender='12345',
            body='Hello',
            timestamp=fields.Datetime.to_string(fields.Datetime.now()),
            unsupported=False,
            source_digest='a' * 64,
        )
        event.update(values)
        return self.gateway.receive_event('tg', '900000123', event)

    def reply(self):
        result = self.receive()
        conversation = (
            self.env['ab_crm_message'].browse(result['message_id']).conversation_id
        )
        return (
            self.env['ab_crm_message']
            .with_user(self.staff)
            .create(
                {
                    'conversation_id': conversation.id,
                    'branch_id': self.branch.id,
                    'direction': 'out',
                    'body': 'Approved response',
                }
            )
        )

    def lease(self):
        message = self.reply()
        message.action_approve()
        payload = self.gateway.lease_outgoing('tg', '900000123')
        self.gateway.acknowledge_receipt(
            'tg',
            '900000123',
            payload['token'],
            payload['attempt'],
            payload['lease'],
            'receipt',
        )
        return message.messaging_operation_ids, payload

    def test_receive_dedup_and_conflict(self):
        date = fields.Datetime.to_string(fields.Datetime.now())
        first = self.receive(timestamp=date)
        self.assertEqual(first, self.receive(timestamp=date))
        with self.assertRaises(ValidationError):
            self.receive(body='Different', timestamp=date)
        self.assertEqual(
            self.env['ab_crm_messaging_event'].search_count(
                [('account_id', '=', self.account.id)]
            ),
            1,
        )

    def test_no_cross_channel_customer_merge(self):
        result = self.receive()
        self.assertFalse(
            self.env['ab_crm_message']
            .browse(result['message_id'])
            .conversation_id.customer_id
        )

    def test_unsupported_notice(self):
        result = self.receive(body='', unsupported=True)
        self.assertIn(
            'Unsupported attachment',
            self.env['ab_crm_message'].browse(result['message_id']).body,
        )

    def test_account_and_role_mismatch(self):
        with self.assertRaises(AccessError):
            self.gateway.lease_outgoing('tg', 'other')
        with self.assertRaises(AccessError):
            self.gateway.with_user(self.staff).lease_outgoing('tg', '900000123')
        with self.assertRaises(AccessError):
            self.env['ab_crm_message'].with_user(self.service).search([])
        with self.assertRaises(AccessError):
            self.account.with_user(self.other).read(['provider_account'])

    def test_service_cannot_approve(self):
        with self.assertRaises(AccessError):
            self.reply().with_user(self.service).action_approve()

    def test_atomic_approval_and_immutable_operation(self):
        message = self.reply()
        message.with_context(default_state='read', default_attempt=99).action_approve()
        operation = message.messaging_operation_ids
        self.assertEqual(operation.state, 'queued')
        self.assertEqual(operation.attempt, 1)
        self.assertEqual(operation.approved_by, self.staff)
        self.assertEqual(message.delivery_state, 'unknown')
        with self.assertRaises(UserError):
            message.action_approve()
        with self.assertRaises(AccessError):
            operation.write({'body': 'Forged'})
        with self.assertRaises(AccessError):
            operation.with_user(self.other).read(['body'])
        self.assertEqual(operation.with_user(self.manager).body, 'Approved response')

    def test_expired_lease_recovery(self):
        message = self.reply()
        message.action_approve()
        first = self.gateway.lease_outgoing('tg', '900000123')
        self.assertFalse(self.gateway.lease_outgoing('tg', '900000123'))
        operation = message.messaging_operation_ids
        operation._change({'lease_until': fields.Datetime.now() - timedelta(seconds=1)})
        second = self.gateway.lease_outgoing('tg', '900000123')
        self.assertEqual(first['token'], second['token'])
        self.assertNotEqual(first['lease'], second['lease'])
        with self.assertRaises(UserError):
            self.gateway.acknowledge_receipt(
                'tg', '900000123', first['token'], 1, first['lease'], 'receipt'
            )

    def test_durable_receipt_and_evidence_replay(self):
        operation, payload = self.lease()
        self.assertTrue(
            self.gateway.acknowledge_receipt(
                'tg', '900000123', payload['token'], 1, '', 'receipt'
            )
        )
        self.assertFalse(self.gateway.lease_outgoing('tg', '900000123'))
        for unused in range(2):
            self.gateway.report_delivery(
                'tg', '900000123', payload['token'], 1, 'receipt', 'accepted', 'tg-1'
            )
        self.assertEqual(operation.state, 'accepted')
        for reference in ('', 'tg-1'):
            self.gateway.report_delivery(
                'tg', '900000123', payload['token'], 1, 'receipt',
                'failed', reference, 'unavailable',
            )
        self.assertEqual(operation.state, 'accepted')
        self.assertEqual(len(operation.history), 1)
        with self.assertRaises(ValidationError):
            self.gateway.receive_status('tg', '900000123', 'tg-1', '12345', 'read')

    def test_ambiguous_cannot_retry(self):
        operation, payload = self.lease()
        self.gateway.report_delivery(
            'tg',
            '900000123',
            payload['token'],
            1,
            'receipt',
            'review',
            error='ambiguous',
        )
        with self.assertRaises(UserError):
            operation.action_retry()
        operation.action_close_review('Provider console checked; no automatic resend')
        self.assertEqual(operation.state, 'resolved')
        self.assertEqual(operation.reviewed_by, self.staff)
        with self.assertRaises(UserError):
            operation.write({'review_note': 'Overwrite audit'})

    def test_definitive_retry_keeps_approval_and_payload(self):
        operation, payload = self.lease()
        self.gateway.report_delivery(
            'tg',
            '900000123',
            payload['token'],
            1,
            'receipt',
            'failed',
            error='rate_limit',
        )
        operation.action_retry()
        second = self.gateway.lease_outgoing('tg', '900000123')
        self.assertEqual(
            (second['token'], second['body']), (payload['token'], payload['body'])
        )
        self.assertEqual(second['attempt'], 2)
        self.assertEqual(operation.approved_by, self.staff)

    def test_pause_prevents_send(self):
        operation, payload = self.lease()
        self.account.enabled = False
        self.assertFalse(
            self.gateway.authorize_send(
                'tg', '900000123', payload['token'], 1, 'receipt'
            )
        )

    def test_whatsapp_window_and_status_order(self):
        channel = self.env['ab_crm_channel'].create(
            {
                'name': 'WA',
                'code': 'messaging-wa',
                'provider': 'whatsapp',
                'branch_id': self.branch.id,
            }
        )
        account = self.env['ab_crm_messaging_account'].create(
            {
                'name': 'WA',
                'code': 'wa',
                'provider': 'whatsapp',
                'provider_account': '456',
                'channel_id': channel.id,
                'branch_id': self.branch.id,
                'service_user_id': self.service.id,
                'legacy_worker_disabled': True,
                'enabled': True,
                'outgoing_enabled': True,
            }
        )
        old = fields.Datetime.now() - timedelta(hours=25)
        event = dict(
            id='old',
            sender='201234',
            body='Hi',
            timestamp=fields.Datetime.to_string(old),
            unsupported=False,
            source_digest='a' * 64,
        )
        result = self.gateway.receive_event('wa', '456', event)
        conversation = (
            self.env['ab_crm_message'].browse(result['message_id']).conversation_id
        )
        message = (
            self.env['ab_crm_message']
            .with_user(self.staff)
            .create(
                {
                    'conversation_id': conversation.id,
                    'branch_id': self.branch.id,
                    'direction': 'out',
                    'body': 'Reply',
                }
            )
        )
        with self.assertRaises(UserError):
            message.action_approve()
        event.update(
            id='new', timestamp=fields.Datetime.to_string(fields.Datetime.now())
        )
        self.gateway.receive_event('wa', '456', event)
        message.action_approve()
        payload = self.gateway.lease_outgoing('wa', '456')
        self.gateway.acknowledge_receipt(
            'wa', '456', payload['token'], 1, payload['lease'], 'receipt'
        )
        self.gateway.report_delivery(
            'wa', '456', payload['token'], 1, 'receipt', 'accepted', 'wa-1'
        )
        self.gateway.receive_status('wa', '456', 'wa-1', '201234', 'failed')
        self.assertEqual(message.messaging_operation_ids.state, 'failed')
        self.assertFalse(message.messaging_operation_ids.retryable)
        for status in ('read', 'delivered', 'accepted', 'failed'):
            self.gateway.receive_status('wa', '456', 'wa-1', '201234', status)
        self.assertEqual(message.messaging_operation_ids.state, 'read')
        with self.assertRaises(UserError):
            self.gateway.receive_status('wa', '456', 'unmatched', '201234', 'delivered')
        self.assertTrue(account.enabled)

    def test_company_scope(self):
        company = self.env['res.company'].create({'name': 'Messaging other company'})
        with self.assertRaises(AccessError):
            self.gateway.with_context(allowed_company_ids=company.ids).lease_outgoing(
                'tg', '900000123'
            )

    def test_evidence_cannot_be_forged(self):
        conversation = self.reply().conversation_id
        with self.assertRaises(AccessError):
            conversation.write({'messaging_last_inbound': fields.Datetime.now()})
        with self.assertRaises(UserError):
            conversation.write({'external_key': 'another'})

    def test_account_cannot_enable_with_previous_worker(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.account.write({'legacy_worker_disabled': False})

    def test_incoming_context_cannot_create_staff_messages(self):
        event = dict(
            id='context-test',
            sender='6789',
            body='Hello',
            timestamp=fields.Datetime.to_string(fields.Datetime.now()),
            unsupported=False,
            source_digest='a' * 64,
        )
        result = self.gateway.with_context(
            default_message_ids=[
                fields.Command.create({'body': 'Forged', 'direction': 'out'})
            ],
            default_approved_by=self.staff.id,
        ).receive_event('tg', '900000123', event)
        message = self.env['ab_crm_message'].browse(result['message_id'])
        self.assertFalse(message.approved_by)
        self.assertEqual(len(message.conversation_id.message_ids), 1)

    def test_foreign_service_cannot_access_account(self):
        service = self.env['res.users'].create(
            {
                'name': 'Other messaging service',
                'login': 'other-messaging-service',
                'group_ids': [
                    fields.Command.set(
                        [
                            self.env.ref('base.group_user').id,
                            self.env.ref('ab_crm_messaging.group_service').id,
                        ]
                    )
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.gateway.with_user(service).lease_outgoing('tg', '900000123')

    def test_service_with_accidental_staff_role_still_cannot_read_crm(self):
        message = self.reply()
        self.service.write(
            {
                'group_ids': [
                    fields.Command.link(self.env.ref('ab_crm_core.group_manager').id)
                ]
            }
        )
        with self.assertRaises(AccessError):
            message.with_user(self.service).read(['body'])
        with self.assertRaises(AccessError):
            self.gateway.lease_outgoing('tg', '900000123')

    def test_telegram_late_failure_does_not_downgrade_sent(self):
        operation, payload = self.lease()
        self.gateway.report_delivery(
            'tg', '900000123', payload['token'], 1, 'receipt', 'accepted', 'reference'
        )
        self.gateway.report_delivery(
            'tg',
            '900000123',
            payload['token'],
            1,
            'receipt',
            'failed',
            'reference',
            'rejected',
        )
        self.assertEqual(operation.state, 'accepted')
        self.assertFalse(operation.retryable)
        self.gateway.report_delivery(
            'tg', '900000123', payload['token'], 1, 'receipt', 'accepted', 'reference'
        )
        self.assertEqual(operation.state, 'accepted')

    def test_archival_stops_sending_but_accepts_existing_evidence(self):
        operation, payload = self.lease()
        self.account.active = False
        self.assertFalse(
            self.gateway.authorize_send(
                'tg', '900000123', payload['token'], 1, 'receipt'
            )
        )
        self.assertFalse(self.gateway.lease_outgoing('tg', '900000123'))
        with self.assertRaises(UserError):
            self.receive('archived')
        self.gateway.report_delivery(
            'tg', '900000123', payload['token'], 1, 'receipt', 'accepted', 'reference'
        )
        self.assertEqual(operation.state, 'accepted')
