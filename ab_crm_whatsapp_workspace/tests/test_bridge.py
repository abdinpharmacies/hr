import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from ..models.common import bridge_mutation


@tagged('post_install', '-at_install')
class TestWhatsAppBridge(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.country_id = cls.env.ref('base.eg')
        cls.staff = cls.env['res.users'].create(
            {
                'name': 'Workspace Agent',
                'login': 'workspace-agent',
                'group_ids': [
                    fields.Command.set(
                        [
                            cls.env.ref('base.group_user').id,
                            cls.env.ref('ab_sales.group_call_center').id,
                        ]
                    )
                ],
            }
        )
        cls.other = cls.env['res.users'].create(
            {
                'name': 'Other Agent',
                'login': 'workspace-other',
                'group_ids': [
                    fields.Command.set(
                        [
                            cls.env.ref('base.group_user').id,
                            cls.env.ref('ab_sales.group_call_center').id,
                        ]
                    )
                ],
            }
        )
        cls.service = cls.env['res.users'].create(
            {
                'name': 'Workspace Service',
                'login': 'workspace-service',
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
        cls.store = cls.env['ab_store'].create(
            {'name': 'Workspace Store', 'code': 'workspace'}
        )
        cls.foreign_store = cls.env['ab_store'].create(
            {'name': 'Foreign Store', 'code': 'foreign'}
        )
        cls.replica = cls.env['ab_replica_db'].create(
            {
                'name': 'Workspace Replica',
                'allowed_sales_store_ids': [fields.Command.set(cls.store.ids)],
                'default_sales_store_id': cls.store.id,
            }
        )
        cls.branch = cls.env['ab_crm_branch'].create(
            {
                'name': 'Workspace Intake',
                'code': 'workspace-intake',
                'replica_id': cls.replica.id,
                'user_ids': [fields.Command.set((cls.staff | cls.service).ids)],
            }
        )
        cls.channel = cls.env['ab_crm_channel'].create(
            {
                'name': 'Workspace Telegram',
                'code': 'workspace-tg',
                'provider': 'telegram',
                'branch_id': cls.branch.id,
            }
        )
        cls.account = cls.env['ab_crm_messaging_account'].create(
            {
                'name': 'Workspace Bot',
                'code': 'workspace-bot',
                'provider': 'telegram',
                'provider_account': '900000234',
                'channel_id': cls.channel.id,
                'branch_id': cls.branch.id,
                'service_user_id': cls.service.id,
                'legacy_worker_disabled': True,
                'enabled': True,
                'outgoing_enabled': True,
            }
        )
        cls.employee = cls.env['ab_hr_employee'].create(
            {
                'name': 'Workspace Employee',
                'barcode': 'WORKSPACE1',
                'user_id': cls.staff.id,
            }
        )
        cls.profile = cls.env['ab_employee_access'].create(
            {
                'employee_id': cls.employee.id,
                'pos_pin': '1234',
                'pos_use_custom_permissions': True,
                'pos_allow_pos_screen': True,
                'pos_allowed_store_ids': [fields.Command.set(cls.store.ids)],
            }
        )
        cls.chatter_api = cls.env['ab_crm_chatter_api'].with_user(cls.staff)
        cls.session_token = cls.chatter_api.employee_login(
            cls.profile.id, '1234', 'workspace-test'
        )['token']
        cls.session = cls.chatter_api._session(cls.session_token)
        cls.wa_channel = cls.env['ab_crm_channel'].create(
            {
                'name': 'WhatsApp',
                'code': 'test-wa',
                'provider': 'whatsapp',
                'branch_id': cls.branch.id,
            }
        )
        cls.wa_account = cls.env['ab_crm_messaging_account'].create(
            {
                'name': 'WhatsApp',
                'code': 'test-wa',
                'provider': 'whatsapp',
                'provider_account': '98765',
                'branch_id': cls.branch.id,
                'channel_id': cls.wa_channel.id,
                'service_user_id': cls.service.id,
                'legacy_worker_disabled': True,
                'enabled': True,
                'outgoing_enabled': True,
                'whatsapp_migrated': True,
            }
        )
        cls.template = cls.env['ab.whatsapp.template'].create(
            {
                'name': 'test_template',
                'template_uid': 'test-template',
                'language': 'en_US',
                'status': 'APPROVED',
                'body_preview': 'Hello {{1}}',
                'components_payload': [{'type': 'BODY', 'text': 'Hello {{1}}'}],
            }
        )
        cls.wa_account.whatsapp_template_ids = cls.template
        cls.wa = cls.wa_account._whatsapp_conversation('201012345678')
        with bridge_mutation():
            cls.wa.write({'messaging_last_inbound': fields.Datetime.now()})
        cls.wa_staff = cls.wa.with_user(cls.staff).with_context(
            ab_chatter_session_token=cls.session_token
        )
        cls.gateway = cls.env['ab_crm_messaging_api'].with_user(cls.service)
        cls.dashboard = cls.env['ab.whatsapp.service'].with_user(
            cls.env.ref('base.user_admin')
        )

    def lease(self):
        result = self.gateway.lease_outgoing('test-wa', '98765')
        self.gateway.acknowledge_receipt(
            'test-wa',
            '98765',
            result['token'],
            result['attempt'],
            result['lease'],
            'receipt',
        )
        return result

    def authorize(self, payload):
        return self.gateway.authorize_send(
            'test-wa', '98765', payload['token'], payload['attempt'], 'receipt'
        )

    def test_chatter_and_dashboard_use_one_operation(self):
        first = self.env['ab_crm_message'].browse(self.wa_staff.action_reply('Chatter'))
        with patch.object(
            type(self.dashboard),
            '_post_graph_json',
            side_effect=AssertionError('Direct send'),
        ):
            result = self.dashboard.api_send_text(
                '201012345678', 'Dashboard', phone_number_id='98765'
            )
        second = (
            self.env['ab.whatsapp.message']
            .browse(result['message']['id'])
            .crm_message_id
        )
        self.assertEqual(first.messaging_operation_ids.state, 'queued')
        self.assertEqual(second.messaging_operation_ids.state, 'queued')
        self.assertEqual(len(first.whatsapp_history_ids), 1)
        self.assertEqual(result['message']['status'], 'queued')
        with self.assertRaises(UserError):
            first.with_user(self.staff).with_context(
                ab_chatter_session_token=self.session_token
            ).action_approve()

    def test_template_outside_window_and_revocation(self):
        with bridge_mutation():
            self.wa.write(
                {'messaging_last_inbound': fields.Datetime.now() - timedelta(days=2)}
            )
        with self.assertRaises(UserError):
            self.wa_staff.action_reply('Too late')
        message = self.env['ab_crm_message'].browse(
            self.wa_staff.action_whatsapp_template(self.template.id, ['Customer'])
        )
        self.assertEqual(
            message.messaging_operation_ids.content['template']['name'],
            self.template.name,
        )
        lease = self.lease()
        self.assertTrue(self.authorize(lease))
        self.template.status = 'REJECTED'
        self.assertEqual(
            self.authorize(lease),
            {'allowed': False, 'terminal': True, 'error': 'rejected'},
        )

    def test_permission_revoked_after_receipt(self):
        self.wa_staff.action_reply('Queued before revocation')
        lease = self.lease()
        self.assertTrue(self.authorize(lease))
        self.branch.user_ids -= self.staff
        self.assertEqual(self.authorize(lease)['allowed'], False)

    def test_scoped_history_and_immutable_rpc(self):
        message = self.env['ab_crm_message'].browse(
            self.wa_staff.action_reply('Private')
        )
        history = message.whatsapp_history_ids
        self.assertEqual(
            history.with_user(self.staff).read(['text_content'])[0]['text_content'],
            'Private',
        )
        with self.assertRaises(AccessError):
            history.with_user(self.other).read(['text_content'])
        with self.assertRaises(AccessError):
            history.with_user(self.service).read(['text_content'])
        with self.assertRaises(AccessError):
            history.with_user(self.env.ref('base.user_admin')).write(
                {'text_content': 'Tampered'}
            )
        with self.assertRaises(AccessError):
            self.dashboard.api_delete_message_local(history.id)
        with self.assertRaises(AccessError):
            self.wa_account.with_user(self.staff).write({'whatsapp_migrated': False})
        with self.assertRaises(AccessError):
            self.wa.with_user(self.staff).with_context(
                ab_chatter_session_token=False
            ).action_reply('No session')

    def test_history_linking_never_enqueues(self):
        with bridge_mutation():
            historical = self.env['ab.whatsapp.service']._create_message(
                direction='outgoing',
                wa_id='201012345678',
                phone_number_id='98765',
                message_type='text',
                text_content='Historical',
                meta_message_id='old-id',
                status='sent',
            )
            ambiguous = self.env['ab.whatsapp.service']._create_message(
                direction='incoming',
                wa_id='201012345678',
                message_type='text',
                text_content='Ambiguous',
            )
        self.assertEqual(self.wa_account.action_link_whatsapp_history()['linked'], 1)
        self.assertEqual(self.wa_account.action_link_whatsapp_history()['linked'], 0)
        self.assertFalse(historical.crm_message_id.messaging_operation_ids)
        self.assertFalse(ambiguous.crm_message_id)
        self.assertFalse(
            self.env['ab.whatsapp.message']
            .with_user(self.staff)
            .search([('id', '=', ambiguous.id)])
        )

    def test_signed_reception_disabled_and_canonical_dedup(self):
        event = {
            'id': 'wamid-in',
            'sender': '201012345678',
            'body': 'Incoming',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False,
            'source_digest': 'a' * 64,
        }
        with self.assertRaises(UserError):
            self.gateway.receive_event('test-wa', '98765', event)
        self.wa_account.whatsapp_webhook_enabled = True
        first = self.gateway.receive_event('test-wa', '98765', event)
        self.assertEqual(first, self.gateway.receive_event('test-wa', '98765', event))
        self.wa_account.enabled = False
        with self.assertRaises(UserError):
            self.gateway.receive_event('test-wa', '98765', event)
        self.wa_account.enabled = True
        self.assertEqual(
            len(
                self.env['ab_crm_message']
                .browse(first['message_id'])
                .whatsapp_history_ids
            ),
            1,
        )
        with self.assertRaises(AccessError):
            self.dashboard.process_webhook_payload(
                {
                    'entry': [
                        {
                            'changes': [
                                {'value': {'metadata': {'phone_number_id': '98765'}}}
                            ]
                        }
                    ]
                }
            )

    def test_media_reactions_and_delivery_projection(self):
        data = base64.b64encode(b'%PDF-test').decode()
        result = self.dashboard.api_send_media_base64(
            '201012345678', 'test.pdf', 'application/pdf', data, phone_number_id='98765'
        )
        history = self.env['ab.whatsapp.message'].browse(result['message']['id'])
        self.assertEqual(history.crm_message_id.media_ids.state, 'ready')
        lease = self.lease()
        self.gateway.report_delivery(
            'test-wa',
            '98765',
            lease['token'],
            lease['attempt'],
            'receipt',
            'accepted',
            'wamid-1',
        )
        self.assertEqual(history.status, 'accepted')
        self.assertEqual(history.meta_message_id, 'wamid-1')
        reaction = self.dashboard.api_send_reaction(
            '201012345678', 'wamid-1', '👍', phone_number_id='98765'
        )
        self.assertEqual(reaction['message']['status'], 'queued')
        self.assertEqual(reaction['message']['message_type'], 'reaction')

    def test_disabled_account_has_no_direct_fallback(self):
        self.wa_account.outgoing_enabled = False
        with patch.object(
            type(self.dashboard),
            '_post_graph_json',
            side_effect=AssertionError('Direct send'),
        ):
            with self.assertRaises(UserError):
                self.dashboard.api_send_text(
                    '201012345678', 'Blocked', phone_number_id='98765'
                )
        self.assertFalse(
            self.env['ab_crm_messaging_operation'].search(
                [('account_id', '=', self.wa_account.id)]
            )
        )

    def test_company_switch_does_not_expose_history(self):
        message = self.env['ab_crm_message'].browse(
            self.wa_staff.action_reply('Company private')
        )
        second = self.env['res.company'].create({'name': 'Other WhatsApp Company'})
        self.staff.company_ids += second
        with self.assertRaises(AccessError):
            message.whatsapp_history_ids.with_user(self.staff).with_context(
                allowed_company_ids=second.ids
            ).read(['text_content'])
        with self.assertRaises(AccessError):
            self.wa.with_user(self.other).with_context(
                ab_chatter_session_token=self.session_token
            ).action_reply('Cross user')

    def test_uncertain_history_and_archived_mapping_never_direct_send(self):
        self.wa_staff.action_reply('Uncertain')
        payload = self.lease()
        self.gateway.report_delivery(
            'test-wa',
            '98765',
            payload['token'],
            payload['attempt'],
            'receipt',
            'review',
            error='ambiguous',
        )
        operation = self.env['ab_crm_messaging_operation'].search(
            [('token', '=', payload['token'])]
        )
        self.assertEqual(operation.message_id.whatsapp_history_ids.status, 'uncertain')
        with self.assertRaises(UserError):
            operation.with_user(self.staff).with_context(
                ab_chatter_session_token=self.session_token
            ).action_retry()
        self.wa_account.active = False
        with patch.object(
            type(self.dashboard),
            '_post_graph_json',
            side_effect=AssertionError('Direct send'),
        ):
            with self.assertRaises(UserError):
                self.dashboard.api_send_text(
                    '201012345678', 'Archived', phone_number_id='98765'
                )

    def test_employee_revocation_after_queue_prevents_dispatch(self):
        self.wa_staff.action_reply('Employee authorization')
        payload = self.lease()
        self.assertTrue(self.authorize(payload))
        self.profile.pos_allow_login = False
        self.assertEqual(self.authorize(payload)['allowed'], False)

    def test_legacy_incoming_replay_reuses_projection(self):
        import hashlib
        import json
        from datetime import datetime, timezone

        self.wa_account.whatsapp_webhook_enabled = True
        raw = {
            'id': 'historical-in',
            'from': '201012345678',
            'type': 'text',
            'text': {'body': 'Historical incoming'},
            'timestamp': str(int(datetime.now(timezone.utc).timestamp())),
        }
        with bridge_mutation():
            history = self.env['ab.whatsapp.service']._create_message(
                direction='incoming',
                wa_id='201012345678',
                phone_number_id='98765',
                message_type='text',
                text_content='Historical incoming',
                meta_message_id='historical-in',
                raw_payload=raw,
            )
        self.wa_account.action_link_whatsapp_history()
        event = {
            'id': 'historical-in',
            'sender': '201012345678',
            'body': 'Historical incoming',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False,
            'source_digest': hashlib.sha256(
                json.dumps(raw, sort_keys=True).encode()
            ).hexdigest(),
        }
        self.assertEqual(
            self.gateway.receive_event('test-wa', '98765', event)['message_id'],
            history.crm_message_id.id,
        )
        self.assertEqual(len(self.wa.message_ids), 1)
        with self.assertRaises(UserError):
            self.gateway.receive_event('test-wa', '98765', dict(event, body='Conflict'))

    def test_dashboard_document_and_unicode_reaction(self):
        result = self.dashboard.api_send_media_base64(
            '201012345678',
            'note.txt',
            'text/plain',
            base64.b64encode(b'Hello').decode(),
            phone_number_id='98765',
        )
        history = self.env['ab.whatsapp.message'].browse(result['message']['id'])
        self.assertTrue(result['message']['media_id'])
        lease = self.lease()
        self.gateway.report_delivery(
            'test-wa',
            '98765',
            lease['token'],
            lease['attempt'],
            'receipt',
            'accepted',
            'doc-id',
        )
        result = self.dashboard.api_send_reaction(
            '201012345678', 'doc-id', '🎉', phone_number_id='98765'
        )
        self.assertEqual(result['message']['status'], 'queued')
        self.assertEqual(history.message_type, 'document')

    def test_dashboard_contact_and_media_scope(self):
        result = self.dashboard.api_send_media_base64(
            '201012345678',
            'note.txt',
            'text/plain',
            base64.b64encode(b'Hello').decode(),
            phone_number_id='98765',
            contact_name='Named contact',
        )
        self.assertTrue(self.dashboard.api_list_contacts()[0]['integrated'])
        self.assertEqual(self.dashboard.api_list_contacts()[0]['name'], 'Named contact')
        self.assertEqual(
            self.dashboard.get_message_media_content(result['message']['id'])[0],
            b'Hello',
        )
        company = self.env['res.company'].create({'name': 'Other Media Company'})
        admin = self.env.ref('base.user_admin')
        admin.company_ids += company
        with self.assertRaises(AccessError):
            self.dashboard.with_context(
                allowed_company_ids=company.ids
            ).sudo().get_message_media_content(result['message']['id'])

    def test_location_canonical_snapshot_and_reception_guard(self):
        event = {
            'id': 'wamid-location', 'sender': '201012345678', 'body': 'Location',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False, 'source_digest': 'd' * 64,
            'location': {'latitude': 0, 'longitude': 0, 'name': 'Customer location'},
        }
        with self.assertRaises(UserError):
            self.gateway.receive_event('test-wa', '98765', event)
        self.wa_account.whatsapp_webhook_enabled = True
        result = self.gateway.receive_event('test-wa', '98765', event)
        self.assertEqual(result, self.gateway.receive_event('test-wa', '98765', event))
        message = self.env['ab_crm_message'].browse(result['message_id'])
        history = message.whatsapp_history_ids
        self.assertEqual(len(history), 1)
        self.assertEqual(history.message_type, 'location')
        self.assertEqual(history.meta_message_id, event['id'])
        self.assertEqual(history.crm_location_snapshot, message.location_snapshot)
        for actor in (self.staff, self.service, self.env.user):
            with self.assertRaises(AccessError):
                history.with_user(actor).write({'crm_location_snapshot': False})
        self.assertEqual(history.raw_payload['source_digest'], event['source_digest'])
