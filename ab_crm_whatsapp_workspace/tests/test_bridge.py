import base64
from io import BytesIO

from PIL import Image
from datetime import timedelta
from unittest.mock import patch

from odoo import fields, models
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
                'whatsapp_extended_enabled': True,
            }
        )
        cls.template = cls.env['ab.whatsapp.template'].create(
            {
                'name': 'test_template',
                'template_uid': 'test-template',
                'business_account_id': 'test-waba',
                'language': 'en_US',
                'status': 'APPROVED',
                'body_preview': 'Hello {{1}}',
                'components_payload': [{'type': 'BODY', 'text': 'Hello {{1}}'}],
            }
        )
        with bridge_mutation():
            cls.wa_account.whatsapp_business_account = 'test-waba'
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
        self.assertIs(self.authorize(lease), True)
        self.template.status = 'REJECTED'
        self.assertEqual(
            self.authorize(lease),
            {'allowed': False, 'terminal': True, 'error': 'rejected'},
        )

    def test_permission_revoked_after_receipt(self):
        self.wa_staff.action_reply('Queued before revocation')
        lease = self.lease()
        self.assertIs(self.authorize(lease), True)
        self.branch.user_ids -= self.staff
        self.assertEqual(self.authorize(lease)['allowed'], False)

    def test_dispatch_uses_sender_branch_access(self):
        with self.assertRaises(AccessError):
            self.branch.with_user(self.service).check_access('read')
        self.wa_staff.action_reply('Queued by the chatter agent')
        payload = self.lease()
        self.env.invalidate_all()
        self.assertIs(self.authorize(payload), True)
        with self.assertRaises(AccessError):
            self.branch.with_user(self.service).check_access('read')

    def test_chatter_reaction_changes_authorize_as_sender(self):
        self.wa_account.whatsapp_webhook_enabled = True
        incoming = self.gateway.receive_event('test-wa', '98765', {
            'id': 'reaction-change-target',
            'sender': self.wa.external_key,
            'body': 'Reaction target',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False,
            'source_digest': 'b' * 64,
        })
        for emoji in ('👍', '❤'):
            with self.subTest(emoji=emoji):
                message_id = self.wa_staff.action_reply(
                    '', reply_id=incoming['message_id'], reaction=emoji
                )
                payload = self.lease()
                self.env.invalidate_all()
                self.assertIs(self.authorize(payload), True)
                self.assertEqual(payload['reaction'], emoji)
                message = self.env['ab_crm_message'].browse(message_id)
                self.assertEqual(message.whatsapp_session_id, self.session)

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
        self.assertIs(self.authorize(payload), True)
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

    def test_unsigned_ingestion_always_disabled(self):
        for actor in (self.staff, self.service, self.env.ref('base.user_admin'), self.env.ref('base.public_user')):
            with self.assertRaises(AccessError):
                self.env['ab.whatsapp.service'].with_user(actor).process_webhook_payload({})
        with self.assertRaises(UserError):
            self.dashboard.api_send_text('opaque.123', 'No guessing', phone_number_id='98765')
        with self.assertRaises(UserError):
            self.dashboard.api_send_text('201012345678', 'No fallback', phone_number_id='11111')

    def test_import_cursor_provenance_and_no_fresh_evidence(self):
        from datetime import datetime, timezone
        with bridge_mutation():
            skipped = self.env['ab.whatsapp.message'].create({
                'direction': 'incoming', 'wa_id': 'opaque:123', 'phone_number_id': '98765',
                'message_type': 'text', 'text_content': 'Review',
                'contact_id': self.env['ab.whatsapp.contact'].create({'wa_id': 'opaque:123', 'name': 'Review'}).id,
            })
            historical = self.env['ab.whatsapp.service']._create_message(
                direction='incoming', wa_id='201012345678', phone_number_id='98765',
                message_type='text', text_content='Old', meta_message_id='old-import',
                raw_payload={'timestamp': str(int(datetime.now(timezone.utc).timestamp()))},
            )
            self.wa.write({'messaging_last_inbound': False})
        first = self.wa_account.action_link_whatsapp_history(limit=1)
        self.assertEqual(first['skipped_ids'], skipped.ids)
        second = self.wa_account.action_link_whatsapp_history(limit=1, after_id=first['next_after_id'])
        self.assertEqual(second['linked_ids'], historical.ids)
        self.assertTrue(historical.crm_message_id.historical)
        self.assertFalse(self.wa.messaging_last_inbound)
        self.assertFalse(historical.crm_message_id.messaging_operation_ids)
        self.assertFalse(self.chatter_api.notifications(self.session_token)['items'])
        self.assertEqual(self.wa_staff.workspace_detail()['unread_count'], 0)
        self.assertEqual(self.wa_account.action_link_whatsapp_history(after_id=second['next_after_id'])['linked'], 0)

    def test_reviewed_customer_group_and_shared_orders(self):
        customer = self.env['ab_crm_customer'].create({'name': 'Shared', 'branch_id': self.branch.id})
        telegram = self.env['ab_crm_conversation'].create({
            'name': 'Telegram', 'external_key': '23456', 'branch_id': self.branch.id,
            'channel_id': self.channel.id,
        }).with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.assertFalse(self.wa_staff.action_preview_customer_link(customer.id)['requires_confirmation'])
        for stream in (self.wa_staff, telegram):
            preview = stream.action_preview_customer_link(customer.id)
            stream.action_confirm_customer_link(customer.id, preview['fingerprint'])
        self.assertFalse(self.wa.confirmed_phone)
        inbox = self.wa_staff.workspace_customer_inbox()
        self.assertEqual(len(inbox['items']), 1)
        self.assertEqual(set(r['id'] for r in inbox['items'][0]['streams']), {self.wa.id, telegram.id})
        order_id = self.archive_order(telegram).id
        detail = self.wa_staff.workspace_detail()
        self.assertEqual(detail['orders'][0]['id'], order_id)
        self.assertEqual(detail['orders'][0]['conversation_id'], telegram.id)
        other = self.env['ab_crm_customer'].create({'name': 'Another', 'branch_id': self.branch.id})
        with self.assertRaises(AccessError):
            self.wa_staff.action_preview_customer_link(other.id)
        self.staff.group_ids += self.env.ref('ab_crm_core.group_manager')
        preview = self.wa_staff.action_preview_customer_link(other.id)
        self.assertTrue(preview['conflict'])
        with self.assertRaises(UserError):
            self.wa_staff.action_confirm_customer_link(other.id, preview['fingerprint'], 'Reviewed conflict')
        self.wa_staff.action_confirm_customer_link(other.id, preview['fingerprint'], 'Reviewed conflict', True, customer_confirmed=True)
        with self.assertRaises(UserError):
            self.wa_staff.action_confirm_customer_link(other.id, preview['fingerprint'], 'Stale preview', True)
        self.assertEqual(len(self.wa_staff.workspace_customer_inbox()['items']), 2)
        with self.assertRaises(AccessError):
            self.wa.with_user(self.staff).action_preview_customer_link(customer.id)
        self.assertEqual(len(self.env['ab_crm_workspace_audit'].sudo().search([('action', '=', 'review_customer_link')])), 3)

    def test_extended_capabilities_require_explicit_validation(self):
        self.wa_account.whatsapp_extended_enabled = False
        detail = self.wa_staff.workspace_detail()
        self.assertFalse(detail['capabilities']['media'])
        self.assertFalse(detail['capabilities']['reactions'])
        with self.assertRaises(UserError):
            self.dashboard.api_send_media_base64('201012345678', 'test.pdf', 'application/pdf',
                base64.b64encode(b'%PDF-test').decode(), phone_number_id='98765')
        with self.assertRaises(AccessError):
            self.wa_account.with_user(self.staff).whatsapp_extended_enabled = True

    def test_customer_groups_paginate_before_expanding_streams(self):
        self.staff.group_ids += self.env.ref('ab_crm_core.group_manager')
        customer = self.env['ab_crm_customer'].create({'name': 'Two streams', 'branch_id': self.branch.id})
        other = self.wa_account._whatsapp_conversation('201055555555').with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        for stream in (self.wa_staff, other):
            preview = stream.action_preview_customer_link(customer.id)
            stream.action_confirm_customer_link(customer.id, preview['fingerprint'], 'Reviewed distinct account identities', customer_confirmed=True)
        unlinked = self.wa_account._whatsapp_conversation('201066666666')
        first = self.wa_staff.workspace_customer_inbox(limit=1)
        second = self.wa_staff.workspace_customer_inbox(offset=first['next_offset'], limit=1)
        self.assertTrue(first['has_more'])
        self.assertFalse(second['has_more'])
        self.assertEqual(first['items'][0]['id'], unlinked.id)
        self.assertEqual(len(second['items'][0]['streams']), 2)
        with self.assertRaises(AccessError):
            self.wa_staff.with_user(self.other).workspace_customer_inbox()
        company = self.env['res.company'].create({'name': 'Foreign linking company'})
        self.staff.company_ids += company
        with self.assertRaises(AccessError):
            self.wa_staff.with_context(allowed_company_ids=company.ids).action_preview_customer_link(customer.id)

    def test_import_chronology_and_duplicate_conflicts(self):
        imported = []
        with bridge_mutation():
            for reference, stamp in [('later', '1700001000'), ('earlier', '1700000000')]:
                imported.append(self.env['ab.whatsapp.service']._create_message(
                    direction='outgoing', wa_id='201012345678', phone_number_id='98765',
                    message_type='text', text_content=reference, meta_message_id=reference,
                    raw_payload={'timestamp': stamp}, status='sent',
                ))
        self.wa_account.action_link_whatsapp_history()
        detail = self.wa_staff.workspace_detail()
        self.assertEqual([m['body'] for m in detail['messages']], ['earlier', 'later'])
        older = self.wa_staff.workspace_detail(before_id=imported[0].crm_message_id.id)
        self.assertEqual([m['body'] for m in older['messages']], ['earlier'])
        self.assertFalse(older['has_older'])
        with bridge_mutation():
            for unused in range(2):
                self.env['ab.whatsapp.service']._create_message(
                    direction='outgoing', wa_id='201012345678', phone_number_id='98765',
                    message_type='text', text_content='Conflict', meta_message_id='duplicate',
                )
        result = self.wa_account.action_link_whatsapp_history()
        self.assertEqual(len(result['conflicting_ids']), 2)
        self.assertEqual(result['linked'], 0)

    def test_preparation_is_disabled_and_uses_dedicated_identity(self):
        service = self.env['ab.whatsapp.service']
        def config_value(record, key, default=''):
            return {'whatsapp_api_version': 'v26.0', 'whatsapp_phone_number_id': '55555'}.get(key, default)
        with patch.object(type(service), '_config_value', config_value):
            with self.assertRaises(AccessError):
                self.wa_account.with_user(self.staff).action_prepare_whatsapp_pilot()
            channel = self.channel.copy({'code': 'pilot-tg'})
            self.account.copy({'code': 'tg-callcenter', 'provider_account': '55554', 'channel_id': channel.id})
            result = self.wa_account.action_prepare_whatsapp_pilot()
            account = self.env['ab_crm_messaging_account'].browse(result['account_id'])
            self.assertEqual(account.branch_id, self.branch)
            self.assertFalse(account.enabled or account.outgoing_enabled or account.whatsapp_webhook_enabled)
            self.assertFalse(account.service_user_id.active)
            self.assertNotEqual(account.service_user_id, self.service)
            self.assertFalse(self.wa_account.action_prepare_whatsapp_pilot()['created'])

    def test_group_and_provenance_cannot_be_forged(self):
        with self.assertRaises(AccessError):
            self.wa_staff.write({'customer_group_key': 'forged'})
        with self.assertRaises(AccessError):
            self.env['ab_crm_message'].with_user(self.staff).create({
                'conversation_id': self.wa.id, 'branch_id': self.branch.id,
                'body': 'Forged', 'historical': True,
            })
        self.assertFalse(self.env['ab.whatsapp.message'].with_user(self.staff).search([('crm_account_id', '=', False)]))

    def test_import_cursor_is_independent_of_display_chronology(self):
        with bridge_mutation():
            for index in range(60):
                self.env['ab.whatsapp.service']._create_message(
                    direction='outgoing', wa_id='201012345678', phone_number_id='98765',
                    message_type='text', text_content=str(index), meta_message_id='cursor-%s' % index,
                    raw_payload={'timestamp': str(1700001000 - index)}, status='sent',
                )
        self.wa_account.action_link_whatsapp_history()
        first = self.wa_staff.workspace_detail()
        self.assertNotEqual(first['message_cursor'], first['messages'][-1]['id'])
        self.assertFalse(self.wa_staff.workspace_detail(after_id=first['message_cursor'])['messages'])
        self.wa_account.whatsapp_webhook_enabled = True
        result = self.gateway.receive_event('test-wa', '98765', {
            'id': 'new-after-history', 'sender': '201012345678', 'body': 'Fresh',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False, 'source_digest': 'f' * 64,
        })
        page = self.wa_staff.workspace_detail(after_id=first['message_cursor'])
        self.assertEqual([m['id'] for m in page['messages']], [result['message_id']])
        self.assertEqual(page['message_cursor'], result['message_id'])

    def test_approved_template_pickers_include_all_languages(self):
        arabic = self.template.copy({'name': 'arabic_greeting', 'template_uid': 'arabic-greeting', 'language': 'ar'})
        with bridge_mutation():
            self.wa_account.whatsapp_template_ids += arabic
        self.staff.lang = 'en_US'
        self.assertCountEqual([row['id'] for row in self.wa_staff.whatsapp_templates()], (self.template | arabic).ids)
        self.env['res.lang']._activate_lang('ar_001')
        self.staff.lang = 'ar_001'
        self.assertCountEqual([row['id'] for row in self.wa_staff.with_context(lang='en_US').whatsapp_templates()], (self.template | arabic).ids)
        self.dashboard.env.user.lang = 'ar_001'
        self.assertCountEqual([row['id'] for row in self.dashboard.api_list_templates()], (self.template | arabic).ids)
        self.dashboard.env.user.lang = 'en_US'
        self.assertCountEqual([row['id'] for row in self.dashboard.api_list_templates()], (self.template | arabic).ids)

    def incoming_whatsapp(self, event_id, **extra):
        self.wa_account.whatsapp_webhook_enabled = True
        event = {
            'id': event_id, 'sender': self.wa.external_key, 'body': 'Attachment',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False, 'source_digest': 'c' * 64,
            **extra,
        }
        result = self.gateway.receive_event('test-wa', '98765', event)
        return self.env['ab_crm_message'].browse(result['message_id'])

    def test_incoming_private_media_profile_and_history(self):
        image = BytesIO()
        Image.new('RGB', (8, 8), 'green').save(image, format='PNG')
        for index, (kind, mime, raw) in enumerate([
            ('image', 'image/png', image.getvalue()),
            ('image', 'image/webp', b'RIFF\x08\x00\x00\x00WEBPVP8 '),
            ('document', 'application/pdf', b'%PDF-test'),
            ('document', 'text/plain', b'Private document'),
            ('video', 'video/mp4', b'\x00\x00\x00\x18ftypmp42'),
        ]):
            message = self.incoming_whatsapp(f'media-{index}', whatsapp={'type': kind, 'profile_name': 'Human name'},
                media={'kind': kind, 'mimetype': mime, 'size': 0, 'duration': 0,
                       'file_id': str(index + 1), 'name': 'private', 'sha256': '', 'sticker': False, 'animated': False},
                reply_reference='original')
            media = message.media_ids
            self.assertEqual(media.state, 'pending')
            data = base64.b64encode(raw).decode()
            self.gateway.receive_media('test-wa', '98765', f'media-{index}', data)
            self.assertEqual(media.state, 'ready')
            self.assertEqual(media.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token).download()['data'], data)
            with self.assertRaises(AccessError):
                media.with_user(self.other).download()
            self.assertEqual(message.whatsapp_history_ids.message_type, kind)
            self.assertEqual(message.whatsapp_history_ids.reply_to_meta_message_id, 'original')
        self.assertEqual(self.wa_staff._customer_display_name(), 'Human name')

    def test_incoming_reactions_order_removal_and_deduplication(self):
        target = self.incoming_whatsapp('target', body='Hello')
        now = fields.Datetime.now()
        self.incoming_whatsapp('reaction-new', reaction='❤', reply_reference='target',
            timestamp=fields.Datetime.to_string(now), whatsapp={'type': 'reaction'})
        self.incoming_whatsapp('reaction-old', reaction='👍', reply_reference='target',
            timestamp=fields.Datetime.to_string(now - timedelta(seconds=3)), whatsapp={'type': 'reaction'})
        detail = self.wa_staff.workspace_detail()
        self.assertEqual([row['id'] for row in detail['messages']], target.ids)
        self.assertEqual(detail['messages'][0]['reactions'][0]['reaction'], '❤')
        for repeat in range(2):
            self.incoming_whatsapp('reaction-removed', reaction='', reply_reference='target',
                timestamp=fields.Datetime.to_string(now + timedelta(seconds=1)), whatsapp={'type': 'reaction'})
        self.assertFalse(self.wa_staff.workspace_detail()['messages'][0]['reactions'])
        self.assertEqual(self.env['ab_crm_message'].search_count([('conversation_id', '=', self.wa.id)]), 4)

    def test_contact_cards_do_not_identify_sender(self):
        cards = [{'name': {'formatted_name': 'Third party'}, 'phones': [{'phone': '+201011111111'}]},
                 {'name': {'formatted_name': 'Another'}, 'emails': [{'email': 'test@example.invalid'}]}]
        self.incoming_whatsapp('cards', whatsapp={'type': 'contacts', 'cards': cards})
        self.assertFalse(self.wa.customer_id)
        self.assertFalse(self.wa.confirmed_phone)
        self.assertEqual(self.wa_staff.workspace_detail()['messages'][0]['contact_cards'], cards)
        self.assertNotEqual(self.wa_staff._customer_display_name(), 'Third party')

    def test_agent_verified_link_and_name_persistence(self):
        self.incoming_whatsapp('verified', whatsapp={'type': 'text', 'profile_name': 'Provider name'})
        customer = self.env['ab_crm_customer'].create({'name': '767608631', 'phone': '+201012345678', 'branch_id': self.branch.id})
        preview = self.wa_staff.action_preview_customer_link(customer.id)
        self.wa_staff.action_confirm_customer_link(customer.id, preview['fingerprint'], 'Verified matching phone')
        self.assertEqual(self.wa.customer_id, customer)
        self.chatter_api.contact_save(self.session_token, {'name': 'Saved human', 'phone': '+201012345678', 'address': 'Saved address'}, contact_id=customer.id)
        self.incoming_whatsapp('later', whatsapp={'type': 'text', 'profile_name': 'Changed provider'})
        self.assertEqual(self.wa_staff.workspace_detail()['name'], 'Saved human')
        self.assertEqual(self.wa_staff.workspace_detail()['contact']['name'], 'Saved human')
        duplicate = customer.copy({'name': 'Duplicate'})
        with self.assertRaises(AccessError):
            self.wa_staff.action_preview_customer_link(duplicate.id)
        with self.assertRaises(AccessError):
            self.wa_staff.action_preview_customer_link(customer.id)

    def test_sync_templates_atomic_ownership_and_layout(self):
        service = type(self.env['ab.whatsapp.service'])
        inventory = [{'id': 'template-synced', 'name': 'greeting', 'language': 'ar', 'status': 'APPROVED',
                      'components': [{'type': 'BODY', 'text': 'Hello'}]}]
        settings = {'waba_id': '12345', 'api_version': 'v26.0'}
        with patch.object(service, '_settings', return_value=settings), patch.object(service, '_require_token', return_value='test'), patch.object(service, '_get_graph_json', side_effect=[{'data': [{'id': '98765'}]}, {'data': inventory}]):
            self.assertTrue(self.wa_account.action_refresh_whatsapp_templates()['ok'])
        synced = self.wa_account.whatsapp_template_ids
        self.assertEqual(synced.business_account_id, '12345')
        self.assertEqual(self.wa_staff.whatsapp_templates()[0]['language'], 'ar')
        with patch.object(service, '_settings', return_value=settings), patch.object(service, '_require_token', return_value='test'), patch.object(service, '_get_graph_json', side_effect=UserError('Network unavailable')):
            self.assertFalse(self.wa_account.action_refresh_whatsapp_templates()['ok'])
        self.assertEqual(self.wa_account.whatsapp_template_ids, synced)
        self.assertTrue(self.wa_account.whatsapp_templates_synced_at)
        synced.components_payload = [{'type': 'HEADER', 'format': 'IMAGE'}]
        self.assertTrue(self.wa_staff.whatsapp_templates()[0]['unsupported_reason'])
        with self.assertRaises(UserError):
            self.wa_staff.action_whatsapp_template(synced.id)
        with self.assertRaises(AccessError):
            self.wa_account.with_user(self.staff).action_refresh_whatsapp_templates()
        synced.business_account_id = 'another-business'
        self.assertFalse(self.wa_staff.whatsapp_templates())

    def test_unknown_and_opaque_inbound_remain_accessible(self):
        self.wa_account.whatsapp_webhook_enabled = True
        for index, sender in enumerate(('201099999999', '447700900123', 'opaque:customer-42')):
            event = {'id': 'unknown-%s' % index, 'sender': sender, 'body': 'Hello',
                     'timestamp': '2026-01-01 12:00:00', 'unsupported': False, 'source_digest': 'a' * 64}
            result = self.gateway.receive_event('test-wa', '98765', event)
            self.assertEqual(result, self.gateway.receive_event('test-wa', '98765', event))
            message = self.env['ab_crm_message'].browse(result['message_id'])
            conversation = message.conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
            self.assertFalse(conversation.customer_id)
            detail = conversation.workspace_detail()
            self.assertTrue(detail['link_review'])
            self.assertEqual(detail['destination'], sender)
            self.assertEqual(len(message.whatsapp_history_ids), 1)
            if sender.startswith('opaque'):
                self.assertFalse(detail['can_send'])
                self.assertFalse(conversation._verified_sender_phone())

    def test_multiple_phones_review_search_and_primary_destination(self):
        contact = self.chatter_api.contact_save(self.session_token,
            {'name': 'Hassan Hosny', 'phone': '+201014763233', 'address': ''}, branch_id=self.branch.id)
        original = self.wa.external_key
        result = self.chatter_api.contact_phone_add(self.session_token, contact['id'], '010 1234 5678',
            label='Work', reason='Customer confirmed another number', customer_confirmed=True)
        self.assertEqual(len(result['phones']), 2)
        result = self.chatter_api.contact_phone_add(self.session_token, contact['id'], '+20 10 1234 5678',
            label='Work', reason='Customer repeated confirmation', customer_confirmed=True)
        self.assertEqual(len(result['phones']), 2)
        second = next(p for p in result['phones'] if p['number'] == '+201012345678')
        self.assertEqual(self.chatter_api.contact_search(self.session_token, phone='01012345678')['contacts'][0]['id'], contact['id'])
        preview = self.wa_staff.action_preview_customer_link(contact['id'])
        self.assertFalse(preview['requires_confirmation'])
        self.wa_staff.action_confirm_customer_link(contact['id'], preview['fingerprint'], 'Customer confirmed identity', customer_confirmed=True)
        queued = self.env['ab_crm_message'].browse(self.wa_staff.action_reply('Queued before primary change')).messaging_operation_ids
        self.assertEqual(queued.destination, original)
        self.chatter_api.contact_phone_update(self.session_token, contact['id'], second['id'], 'primary', 'Customer chose primary')
        self.assertEqual(queued.destination, original)
        self.assertEqual(self.wa.external_key, original)
        self.assertEqual(self.wa_staff.workspace_detail()['contact']['phone'], second['number'])
        self.assertEqual(len(self.wa_staff.workspace_customer_inbox(query='201012345678')['items']), 1)
        with self.assertRaises(UserError):
            self.chatter_api.contact_phone_update(self.session_token, contact['id'], second['id'], 'archive', 'Archive primary number')
        with self.assertRaises(AccessError):
            self.env['ab_crm_contact_phone'].browse(second['id']).with_user(self.staff).write({'active': False})
        with self.assertRaises(AccessError):
            self.chatter_api.contact_phone_add('forged', contact['id'], '+447700900123', reason='Forged session', customer_confirmed=True)
        with self.assertRaises(AccessError):
            self.env['ab_crm_contact_phone'].browse(second['id']).with_user(self.other).read(['number'])

    def test_phone_changes_invalidate_preview_and_shared_numbers_require_manager(self):
        first = self.chatter_api.contact_save(self.session_token,
            {'name': 'First', 'phone': '+201014763233', 'address': ''}, branch_id=self.branch.id)
        second = self.chatter_api.contact_save(self.session_token,
            {'name': 'Second', 'phone': '+201012345678', 'address': ''}, branch_id=self.branch.id)
        preview = self.wa_staff.action_preview_customer_link(first['id'])
        with self.assertRaises(AccessError):
            self.chatter_api.contact_phone_add(self.session_token, first['id'], second['phone'],
                reason='Shared number requested', customer_confirmed=True)
        self.chatter_api.contact_phone_add(self.session_token, first['id'], '+442079460123',
            reason='Customer confirmed UK number', customer_confirmed=True)
        with self.assertRaises(UserError):
            self.wa_staff.action_confirm_customer_link(first['id'], preview['fingerprint'], 'Stale phone review', customer_confirmed=True)
        self.staff.group_ids += self.env.ref('ab_crm_core.group_manager')
        result = self.chatter_api.contact_phone_add(self.session_token, first['id'], second['phone'],
            reason='Manager reviewed shared household number', customer_confirmed=True, resolve_shared=True)
        self.assertEqual(len(result['phones']), 3)

    def test_initialization_and_consolidation_preserve_conversation_ids(self):
        self.staff.group_ids += self.env.ref('ab_crm_core.group_manager')
        first = self.chatter_api.contact_save(self.session_token,
            {'name': 'Canonical', 'phone': '+201014763233', 'address': ''}, branch_id=self.branch.id)
        duplicate = self.env['ab_crm_customer'].create({'name': 'Duplicate', 'phone': '+201012345678', 'branch_id': self.branch.id})
        for unused in range(2):
            self.chatter_api.contact_initialize_phones(self.session_token, duplicate.id)
        self.assertEqual(len(duplicate.phone_ids), 1)
        preview = self.wa_staff.action_preview_customer_link(duplicate.id)
        self.wa_staff.action_confirm_customer_link(duplicate.id, preview['fingerprint'], 'Reviewed duplicate identity', customer_confirmed=True)
        order = self.archive_order(self.wa_staff)
        snapshot = (order.customer_id.id, order.conversation_id.id, self.wa.external_key)
        preview = self.chatter_api.contact_consolidate(self.session_token, first['id'], duplicate.id)
        self.chatter_api.contact_consolidate(self.session_token, first['id'], duplicate.id,
            fingerprint=preview['fingerprint'], reason='Manager reviewed duplicate and all identities')
        self.assertFalse(duplicate.active)
        self.assertEqual(duplicate.canonical_customer_id.id, first['id'])
        self.assertEqual(self.wa.customer_id.id, first['id'])
        self.assertEqual((order.customer_id.id, order.conversation_id.id, self.wa.external_key), snapshot)

    def test_status_without_send_operation_has_exact_diagnostic(self):
        self.wa_account.whatsapp_webhook_enabled = True
        with self.assertRaisesRegex(UserError, 'Provider acceptance is not recorded yet'):
            self.gateway.receive_status('test-wa', '98765', 'untracked-provider-message', '201014763233', 'delivered')


    def test_phone_archive_scope_and_protected_defaults(self):
        contact = self.chatter_api.contact_save(self.session_token,
            {'name': 'Scoped contact', 'phone': '+201014763233', 'address': ''}, branch_id=self.branch.id)
        contact = self.chatter_api.contact_phone_add(self.session_token, contact['id'], '+201012345678',
            reason='Customer confirmed another number', customer_confirmed=True)
        phone = contact['phones'][1]
        self.chatter_api.contact_phone_update(self.session_token, contact['id'], phone['id'], 'archive', 'Number no longer used')
        self.assertFalse(self.chatter_api.contact_search(self.session_token, phone=phone['number'])['contacts'])
        with self.assertRaises(AccessError):
            self.env['ab_crm_customer'].with_user(self.staff).with_context(default_primary_phone_id=phone['id']).create(
                {'name': 'Forged primary', 'branch_id': self.branch.id})
        with self.assertRaises(AccessError):
            self.env['ab_crm_contact_phone'].browse(phone['id']).with_user(self.service).read(['number'])
        foreign = self.env['res.company'].create({'name': 'Phone foreign company'})
        self.staff.company_ids += foreign
        with self.assertRaises(AccessError):
            self.chatter_api.with_context(allowed_company_ids=foreign.ids).contact_phone_add(
                self.session_token, contact['id'], '+442079460123', reason='Cross company edit', customer_confirmed=True)
        self.assertEqual(self.env['ab_crm_contact_phone'].browse(phone['id']).number, '+201012345678')

    def test_telegram_links_saved_secondary_number_without_creating_contact(self):
        contact = self.chatter_api.contact_save(self.session_token,
            {'name': 'Saved customer', 'phone': '+201014763233', 'address': ''}, branch_id=self.branch.id)
        self.chatter_api.contact_phone_add(self.session_token, contact['id'], '+201012345678',
            reason='Customer confirmed secondary number', customer_confirmed=True)
        before = self.env['ab_crm_customer'].search_count([])
        event = {'id': 'tg-secondary', 'sender': '12345', 'body': 'Contact shared',
                 'timestamp': '2026-01-01 12:00:00', 'unsupported': False, 'source_digest': 'b' * 64,
                 'contact': {'phone': '01012345678', 'user_id': '12345', 'sender_id': '12345'}}
        result = self.gateway.receive_event(self.account.code, self.account.provider_account, event)
        conversation = self.env['ab_crm_message'].browse(result['message_id']).conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.assertFalse(conversation.customer_id)
        self.assertEqual(self.env['ab_crm_customer'].search_count([]), before)
        self.assertFalse(conversation.workspace_detail()['link_suggestions'])
        self.assertEqual(conversation.customer_id.id, contact['id'])
        self.assertEqual(self.env['ab_crm_workspace_audit'].search_count([('conversation_id', '=', conversation.id), ('action', '=', 'auto_link_customer')]), 1)
        self.gateway.receive_event(self.account.code, self.account.provider_account, dict(event, id='tg-later'))
        self.assertEqual(conversation.customer_id.id, contact['id'])
        self.assertEqual(self.env['ab_crm_customer'].search_count([]), before)

    def test_contact_phone_runtime_translations(self):
        from odoo.tools.translate import code_translations
        for lang in ('ar', 'ar_001'):
            self.env['res.lang']._activate_lang(lang)
            description = self.env['ab_crm_contact_phone'].with_context(lang=lang).fields_get(['number'])
            self.assertEqual(description['number']['string'], 'الرقم')
            translated = code_translations.get_python_translations('ab_crm_sales_workspace', lang)
            self.assertEqual(translated['Use the reviewed contact phone actions.'], 'استخدم إجراءات مراجعة هواتف جهة الاتصال.')
            web = {row['id']: row['string'] for row in code_translations.get_web_translations('ab_crm_sales_workspace', lang)['messages']}
            self.assertEqual(web['Consolidate duplicate contact'], 'توحيد جهة الاتصال المكررة')
        description = self.env['ab_crm_contact_phone'].with_context(lang='en_US').fields_get(['number'])
        self.assertEqual(description['number']['string'], 'Number')

    def test_same_phone_links_whatsapp_and_telegram_automatically_on_poll(self):
        contact = self.chatter_api.contact_save(self.session_token,
            {'name': 'One customer', 'phone': '01012345678', 'address': ''}, branch_id=self.branch.id)
        incoming = self.incoming_whatsapp('same-phone-wa')
        result = self.gateway.receive_event(self.account.code, self.account.provider_account,
            {'id': 'same-phone-tg', 'sender': '12345', 'body': 'Own phone',
             'timestamp': '2026-01-01 12:00:00', 'unsupported': False, 'source_digest': 'b' * 64,
             'contact': {'phone': '+20 1012345678', 'user_id': '12345', 'sender_id': '12345'}})
        telegram = self.env['ab_crm_message'].browse(result['message_id']).conversation_id
        before = (incoming.id, result['message_id'], self.wa.external_key, telegram.external_key)
        self.assertFalse(self.wa.customer_id)
        self.assertFalse(telegram.customer_id)
        items = self.chatter_api.notifications(self.session_token)['items']
        self.assertEqual(self.wa.customer_id.id, contact['id'])
        self.assertEqual(telegram.customer_id.id, contact['id'])
        self.assertEqual(len(items), 2)
        self.assertEqual(len({item['customer_group_key'] for item in items}), 1)
        inbox = self.wa_staff.workspace_customer_inbox()['items']
        self.assertEqual(len(inbox), 1)
        self.assertEqual(len(inbox[0]['streams']), 2)
        self.assertEqual((incoming.id, result['message_id'], self.wa.external_key, telegram.external_key), before)
        self.chatter_api.notifications(self.session_token)
        audits = self.env['ab_crm_workspace_audit'].search([('action', '=', 'auto_link_customer')])
        self.assertEqual(len(audits), 2)
        self.assertEqual(audits.customer_id.ids, [contact['id']])
        self.assertEqual(len(incoming.whatsapp_history_ids), 1)

    def test_unlink_separates_whatsapp_and_telegram(self):
        customer = self.env['ab_crm_customer'].create({'name': 'Grouped customer', 'branch_id': self.branch.id})
        telegram = self.env['ab_crm_conversation'].create({
            'name': 'Telegram', 'external_key': '23456', 'branch_id': self.branch.id,
            'channel_id': self.channel.id,
        }).with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        streams = self.wa_staff | telegram
        for stream in streams:
            preview = stream.action_preview_customer_link(customer.id)
            stream.action_confirm_customer_link(customer.id, preview['fingerprint'])
        self.assertEqual(len(self.wa_staff.workspace_customer_inbox()['items']), 1)
        messages = streams.message_ids.ids
        preview = self.wa_staff.action_preview_customer_unlink(customer.id)
        self.wa_staff.action_unlink_customer(customer.id, preview['fingerprint'])
        self.assertFalse(streams.customer_id)
        self.assertEqual(streams.message_ids.ids, messages)
        self.assertEqual(len(self.wa_staff.workspace_customer_inbox()['items']), 2)
        self.assertFalse(self.wa_staff._auto_link_matching_customer())
        self.assertFalse(telegram._auto_link_matching_customer())

    def archive_order(self, conversation):
        return models.Model.create(self.env['ab_crm_channel_order'].sudo(), {
            'name': 'Historical order', 'conversation_id': conversation.id,
            'channel_id': conversation.channel_id.id, 'customer_id': conversation.customer_id.id,
            'customer_name': conversation.customer_id.name, 'phone': conversation.confirmed_phone,
        })

    def historical_receipt(self, reference='old-receipt'):
        with bridge_mutation():
            history = self.env['ab.whatsapp.service']._create_message(
                direction='outgoing', wa_id='201012345678', phone_number_id='98765',
                message_type='text', text_content='Historical', meta_message_id=reference,
                status='sent',
            )
        self.wa_account.action_link_whatsapp_history()
        self.wa_account.whatsapp_webhook_enabled = True
        return history

    def test_historical_status_is_monotonic_without_sends_or_unread_changes(self):
        history = self.historical_receipt()
        message = history.crm_message_id
        before = message.conversation_id.read(['messaging_last_inbound', 'write_date'])
        operations = self.env['ab_crm_messaging_operation'].search_count([])
        unread = self.wa_staff._workspace_unread_messages(self.session).ids
        for state in ('delivered', 'accepted', 'failed', 'read', 'delivered', 'read'):
            self.assertTrue(self.gateway.receive_status('test-wa', '98765', 'old-receipt', '201012345678', state))
        self.assertEqual(history.status, 'read')
        self.assertEqual(message.delivery_state, 'sent')
        self.assertFalse(message.messaging_operation_ids)
        self.assertEqual(self.env['ab_crm_messaging_operation'].search_count([]), operations)
        self.assertEqual(message.conversation_id.read(list(before[0].keys() - {'id'})), before)
        self.assertEqual(self.wa_staff._workspace_unread_messages(self.session).ids, unread)

    def test_historical_status_preview_and_isolation(self):
        history = self.historical_receipt()
        preview = self.gateway.preview_status('test-wa', '98765', 'old-receipt', '201012345678', 'read')
        self.assertEqual(preview, {'match': 'historical'})
        self.assertEqual(history.status, 'sent')
        self.assertEqual(self.gateway.preview_status('test-wa', '98765', 'missing', '201012345678', 'read'), {'match': 'orphan'})
        for account, phone, destination in [('workspace-bot', '98765', '201012345678'), ('test-wa', 'other', '201012345678'), ('test-wa', '98765', 'wrong')]:
            with self.assertRaises(UserError if destination == 'wrong' else AccessError):
                self.gateway.receive_status(account, phone, 'old-receipt', destination, 'read')
        with self.assertRaises(AccessError):
            self.gateway.with_user(self.staff).preview_status('test-wa', '98765', 'old-receipt', '201012345678', 'read')
        with bridge_mutation():
            self.env['ab.whatsapp.service']._create_message(
                direction='outgoing', wa_id='201012345678', phone_number_id='98765',
                message_type='text', text_content='Duplicate reference', meta_message_id='old-receipt', status='sent',
            )
        self.assertEqual(self.gateway.preview_status('test-wa', '98765', 'old-receipt', '201012345678', 'read'), {'match': 'ambiguous'})
        with self.assertRaises(UserError):
            self.gateway.receive_status('test-wa', '98765', 'old-receipt', '201012345678', 'read')

    def test_historical_status_diagnostics_in_both_arabic_catalogs(self):
        self.wa_account.whatsapp_webhook_enabled = True
        for language in ('ar', 'ar_001'):
            gateway = self.gateway.with_context(lang=language)
            with self.assertRaisesRegex(UserError, 'لم يتم تسجيل قبول مزود الخدمة بعد'):
                gateway.receive_status('test-wa', '98765', 'missing', '201012345678', 'read')
            with self.assertRaisesRegex(UserError, 'دليل التسليم غير صالح'):
                gateway.receive_status('test-wa', '98765', '', '201012345678', 'read')
