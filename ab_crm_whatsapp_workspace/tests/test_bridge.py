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
                'whatsapp_extended_enabled': True,
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
        with self.assertRaises(AccessError):
            self.wa_staff.action_preview_customer_link(customer.id)
        self.staff.group_ids += self.env.ref('ab_crm_core.group_manager')
        for stream in (self.wa_staff, telegram):
            preview = stream.action_preview_customer_link(customer.id)
            stream.action_confirm_customer_link(customer.id, preview['fingerprint'], 'Reviewed account evidence')
        self.assertFalse(self.wa.confirmed_phone)
        inbox = self.wa_staff.workspace_customer_inbox()
        self.assertEqual(len(inbox['items']), 1)
        self.assertEqual(set(r['id'] for r in inbox['items'][0]['streams']), {self.wa.id, telegram.id})
        order_id = telegram.action_new_order()
        detail = self.wa_staff.workspace_detail()
        self.assertEqual(detail['orders'][0]['id'], order_id)
        self.assertEqual(detail['orders'][0]['conversation_id'], telegram.id)
        other = self.env['ab_crm_customer'].create({'name': 'Another', 'branch_id': self.branch.id})
        preview = self.wa_staff.action_preview_customer_link(other.id)
        self.assertTrue(preview['conflict'])
        with self.assertRaises(UserError):
            self.wa_staff.action_confirm_customer_link(other.id, preview['fingerprint'], 'Reviewed conflict')
        self.wa_staff.action_confirm_customer_link(other.id, preview['fingerprint'], 'Reviewed conflict', True)
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
            stream.action_confirm_customer_link(customer.id, preview['fingerprint'], 'Reviewed distinct account identities')
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

    def test_approved_template_pickers_follow_preference_language(self):
        arabic = self.template.copy({'name': 'arabic_greeting', 'template_uid': 'arabic-greeting', 'language': 'ar'})
        self.wa_account.whatsapp_template_ids += arabic
        self.staff.lang = 'en_US'
        self.assertEqual([row['id'] for row in self.wa_staff.whatsapp_templates()], self.template.ids)
        self.env['res.lang']._activate_lang('ar_001')
        self.staff.lang = 'ar_001'
        self.assertEqual([row['id'] for row in self.wa_staff.with_context(lang='en_US').whatsapp_templates()], arabic.ids)
        self.dashboard.env.user.lang = 'ar_001'
        self.assertEqual([row['id'] for row in self.dashboard.api_list_templates()], arabic.ids)
        self.dashboard.env.user.lang = 'en_US'
        self.assertEqual([row['id'] for row in self.dashboard.api_list_templates()], self.template.ids)
