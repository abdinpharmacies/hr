from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from ..models.workspace import normalized_phone


@tagged('post_install', '-at_install')
class TestWorkspace(TransactionCase):
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
        category = cls.env['ab_product_uom_category'].create(
            {'name': 'Workspace Units', 'active': True}
        )
        cls.uom = cls.env['ab_product_uom'].create(
            {'name': 'Box', 'category_id': category.id}
        )
        cls.product = cls.env['ab_product'].create(
            {
                'product_card_id': cls.env['ab_product_card']
                .create({'name': 'Workspace Product'})
                .id,
                'uom_category_id': category.id,
                'uom_id': cls.uom.id,
                'default_price': 25,
            }
        )

    def receive(self, event_id='1', phone='01012345678', owner='12345'):
        event = {
            'id': event_id,
            'sender': '12345',
            'body': 'Contact shared',
            'timestamp': '2026-01-01 12:00:00',
            'unsupported': False,
            'source_digest': 'b' * 64,
            'contact': {'phone': phone, 'user_id': owner, 'sender_id': '12345'},
        }
        return (
            self.env['ab_crm_messaging_api']
            .with_user(self.service)
            .receive_event('workspace-bot', '900000234', event)
        )

    def conversation(self):
        result = self.receive()
        return (
            self.env['ab_crm_message']
            .browse(result['message_id'])
            .conversation_id.with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )

    def order(self):
        conversation = self.conversation()
        conversation.action_claim()
        conversation.action_identify()
        order = (
            self.env['ab_crm_channel_order']
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
            .browse(conversation.action_new_order())
        )
        order.write(
            {
                'store_id': self.store.id,
                'confirmation': 'Customer confirmed the quoted order in Telegram.',
            }
        )
        order.action_add_product(self.product.id)
        return order

    def test_phone_normalization(self):
        self.assertEqual(normalized_phone('010 1234 5678', 'EG'), '+201012345678')
        self.assertEqual(normalized_phone('+20 10 1234 5678', 'EG'), '+201012345678')
        self.assertFalse(normalized_phone('invalid', 'EG'))
        self.assertFalse(normalized_phone('01012345678', False))

    def test_owned_contact_and_dedup(self):
        conversation = self.conversation()
        self.assertTrue(conversation.message_ids.telegram_contact_owned)
        self.receive()
        self.assertEqual(len(conversation.message_ids), 1)
        conversation.action_claim()
        result = conversation.action_identify()
        self.assertEqual(result['phone'], '+201012345678')
        self.assertFalse(conversation.customer_id.catalog_customer_id)
        self.assertEqual(
            self.env['ab_crm_identity'].search_count(
                [('customer_id', '=', conversation.customer_id.id)]
            ),
            1,
        )
        self.assertFalse(conversation.order_ids)

    def test_third_party_and_typed_require_confirmation(self):
        self.receive(owner='67890')
        conversation = (
            self.env['ab_crm_conversation']
            .search([('channel_id', '=', self.channel.id)])
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )
        conversation.action_claim()
        with self.assertRaises(UserError):
            conversation.action_identify()
        conversation.action_identify(confirmed=True)
        self.assertFalse(
            self.env['ab_crm_identity'].search([('channel_id', '=', self.channel.id)])
        )
        with self.assertRaises(UserError):
            conversation.action_identify(phone='01112345678')

    def test_unique_duplicate_and_scoped_catalog(self):
        customer = (
            self.env['ab_customer']
            .sudo()
            .create(
                {
                    'name': 'Existing Customer',
                    'code': 'WORKSPACE-A',
                    'mobile_phone': '010 1234 5678',
                    'default_store_id': self.store.id,
                }
            )
        )
        conversation = self.conversation()
        conversation.action_claim()
        conversation.action_identify()
        self.assertEqual(conversation.customer_id.catalog_customer_id, customer)
        duplicate = (
            self.env['ab_customer']
            .sudo()
            .create(
                {
                    'name': 'Duplicate Customer',
                    'code': 'WORKSPACE-B',
                    'delivery_phone': '+201012345678',
                    'default_store_id': self.store.id,
                }
            )
        )
        result = conversation.action_identify()
        self.assertEqual(
            {r['id'] for r in result['candidates']}, {customer.id, duplicate.id}
        )
        with self.assertRaises(AccessError):
            conversation.action_identify(customer_id=99999999)
        duplicate.default_store_id = self.foreign_store
        self.assertEqual(conversation._phone_candidates('+201012345678'), customer)

    def test_accept_has_no_sales_or_stock_side_effects(self):
        order = self.order()
        names = [
            'ab_sales_header',
            'ab_sales_callcenter_rpc_log',
            'ab_oms_attempt',
            'account.payment',
            'stock.move',
        ]
        models = [name for name in names if name in self.env.registry]
        before = {name: self.env[name].sudo().search_count([]) for name in models}
        order.action_accept()
        self.assertEqual(order.state, 'accepted')
        self.assertEqual(order.accepted_by, self.staff)
        self.assertEqual(order.accepted_employee_id, self.employee)
        self.assertEqual(order.channel_id, self.channel)
        self.assertEqual(
            before, {name: self.env[name].sudo().search_count([]) for name in models}
        )
        self.assertTrue(
            order.audit_ids.filtered(lambda a: a.action == 'accepted').values['lines']
        )

    def test_frozen_revision_cancellation_and_price_audit(self):
        order = self.order()
        order.line_ids.write({'price': 30})
        audit = order.audit_ids.filtered(lambda a: a.action == 'line_changed')[-1]
        self.assertEqual(audit.values['old']['price'], 25)
        self.assertEqual(audit.values['new']['price'], 30)
        previous_version = order.edit_version
        order.action_accept()
        with self.assertRaises(UserError):
            order.line_ids.write({'price': 20})
        with self.assertRaises(AccessError):
            order.with_context(default_state='accepted').write({'state': 'draft'})
        order.action_close()
        order.action_reopen('Customer changed quantity')
        self.assertEqual(order.revision, 2)
        with self.assertRaises(UserError):
            order.action_save_draft({}, [], previous_version)
        self.assertFalse(order.confirmation)
        order.action_cancel('Customer cancelled')
        self.assertEqual(order.state, 'cancelled')
        self.assertTrue(order.line_ids)
        with self.assertRaises(UserError):
            order.unlink()
        with self.assertRaises(AccessError):
            audit.sudo().write({'values': {}})

    def test_branch_company_and_agent_isolation(self):
        order = self.order()
        with self.assertRaises(AccessError):
            order.with_user(self.other).read(['phone'])
        with self.assertRaises(AccessError):
            order.line_ids.with_user(self.other).read(['price'])
        with self.assertRaises(AccessError):
            order.write({'store_id': self.foreign_store.id})
        with self.assertRaises(AccessError):
            order.with_user(self.service).action_accept()
        with self.assertRaises(UserError):
            order.with_context(ab_chatter_session_token='forged').action_accept()
        other_company = self.env['res.company'].create(
            {'name': 'Foreign Workspace Company'}
        )
        with self.assertRaises(AccessError):
            order.with_context(allowed_company_ids=other_company.ids).read(['phone'])

    def test_shared_agents_and_locked_session(self):
        conversation = self.conversation()
        conversation.action_claim()
        self.branch.user_ids |= self.other
        other_token = self.chatter_api.with_user(self.other).employee_login(
            self.profile.id, '1234', 'other-session'
        )['token']
        shared = conversation.with_user(self.other).with_context(
            ab_chatter_session_token=other_token
        )
        self.assertTrue(shared.workspace_detail()['can_send'])
        shared.action_reply('Reply from another authorized agent')
        self.assertFalse(conversation.assigned_id)
        self.session.state = 'closed'
        with self.assertRaises(UserError):
            conversation.action_new_order()

    def test_direct_evidence_spoofing(self):
        conversation = self.conversation()
        with self.assertRaises(AccessError):
            conversation.write({'assigned_employee_id': self.employee.id})
        with self.assertRaises(AccessError):
            conversation.write({'confirmed_phone': '+201012345678'})
        with self.assertRaises(AccessError):
            conversation.message_ids.write({'telegram_contact_owned': True})
        conversation.action_claim()
        with self.assertRaises(AccessError):
            self.env['ab_crm_channel_order'].with_user(self.staff).create(
                {'conversation_id': conversation.id, 'state': 'accepted'}
            )

    def test_contact_request_uses_durable_approval(self):
        conversation = self.conversation()
        conversation.action_claim()
        message_id = conversation.action_request_contact()
        message = self.env['ab_crm_message'].browse(message_id)
        self.assertTrue(message.telegram_request_contact)
        self.assertEqual(message.approved_by, self.staff)
        payload = (
            self.env['ab_crm_messaging_api']
            .with_user(self.service)
            .lease_outgoing('workspace-bot', '900000234')
        )
        self.assertEqual(payload['contact_button'], 'Share contact')

    def test_unmapped_activation_and_invalid_lines(self):
        self.account.enabled = False
        self.branch.replica_id = False
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.account.enabled = True
        self.branch.replica_id = self.replica
        self.account.enabled = True
        order = self.order()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.line_ids.write({'quantity': 0})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            order.line_ids.write({'price': -1})

    def test_acceptance_preconditions_and_multiple_orders(self):
        conversation = self.conversation()
        conversation.action_claim()
        order = (
            self.env['ab_crm_channel_order']
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
            .browse(conversation.action_new_order())
        )
        with self.assertRaises(UserError):
            order.action_accept()
        conversation.action_identify()
        order.write({'store_id': self.store.id, 'confirmation': 'Confirmed in chat'})
        with self.assertRaises(UserError):
            order.action_accept()
        order.action_add_product(self.product.id)
        order.action_accept()
        second = conversation.action_new_order()
        self.assertNotEqual(second, order.id)
        self.assertEqual(len(conversation.order_ids), 2)
        self.assertEqual(order.state, 'accepted')

    def test_returning_identity_and_read_position(self):
        conversation = self.conversation()
        conversation.action_claim()
        conversation.action_identify()
        customer = conversation.customer_id
        self.receive(event_id='2')
        self.assertEqual(conversation.customer_id, customer)
        before = conversation.workspace_inbox()
        self.assertEqual(
            next(row for row in before if row['id'] == conversation.id)['unread'], 2
        )
        conversation.workspace_detail()
        after = conversation.workspace_inbox()
        self.assertEqual(
            next(row for row in after if row['id'] == conversation.id)['unread'], 0
        )
        with self.assertRaises(AccessError):
            self.env['ab_crm_identity'].with_user(self.staff).create(
                {
                    'customer_id': customer.id,
                    'channel_id': self.channel.id,
                    'branch_id': self.branch.id,
                    'external_key': 'forged',
                }
            )

    def test_second_employee_can_edit_shared_order(self):
        order = self.order()
        other_employee = self.env['ab_hr_employee'].create(
            {
                'name': 'Other Employee',
                'barcode': 'WORKSPACE2',
                'user_id': self.staff.id,
            }
        )
        other_profile = self.profile.copy(
            {'employee_id': other_employee.id, 'pos_pin': '1234'}
        )
        other_token = self.chatter_api.employee_login(
            other_profile.id, '1234', 'other-device'
        )['token']
        order.with_context(ab_chatter_session_token=other_token).action_accept()
        self.assertEqual(order.accepted_employee_id, other_employee)
        self.assertTrue(
            order.conversation_id.with_context(
                ab_chatter_session_token=other_token
            ).workspace_detail()['owned']
        )

    def test_paginated_history_search_and_read_position(self):
        conversation = self.conversation()
        for number in range(2, 56):
            self.receive(event_id=str(number))
        detail = conversation.workspace_detail()
        self.assertEqual(len(detail['messages']), 50)
        self.assertTrue(detail['has_older'])
        older = conversation.workspace_detail(before_id=detail['messages'][0]['id'])
        self.assertEqual(len(older['messages']), 5)
        self.assertFalse(older['has_older'])
        self.assertTrue(
            all(
                message['timestamp'] == '2026-01-01 12:00:00'
                for message in detail['messages']
            )
        )
        self.assertFalse(
            conversation.workspace_detail(after_id=detail['messages'][-1]['id'])[
                'messages'
            ]
        )
        self.assertEqual(conversation.workspace_inbox(query='does-not-exist'), [])
        self.assertEqual(conversation.workspace_inbox()[0]['unread'], 0)
        self.assertEqual(conversation.workspace_inbox(before_id=conversation.id), [])
        with self.assertRaises(AccessError):
            conversation.with_user(self.other).workspace_detail(
                before_id=detail['messages'][0]['id']
            )

    def test_menu_immediately_after_pos(self):
        root = self.env.ref('ab_sales.sales_menu_root')
        menus = self.env['ir.ui.menu'].search([('parent_id', '=', root.id)])
        pos = menus.ids.index(self.env.ref('ab_sales.ab_sales_pos_menu').id)
        self.assertEqual(
            menus[pos + 1], self.env.ref('ab_crm_sales_workspace.menu_workspace')
        )

    def test_direct_message_rpc_requires_employee_session(self):
        conversation = self.conversation()
        conversation.action_claim()
        values = {
            'conversation_id': conversation.id,
            'branch_id': self.branch.id,
            'direction': 'out',
            'body': 'Explicit reply',
        }
        messages = self.env['ab_crm_message'].with_user(self.staff)
        with self.assertRaises(AccessError):
            messages.create(values.copy())
        message = messages.with_context(
            ab_chatter_session_token=self.session_token
        ).create(values.copy())
        with self.assertRaises(AccessError):
            message.with_context(ab_chatter_session_token=False).action_approve()
        with self.assertRaises(AccessError):
            message.with_context(ab_chatter_session_token=False).write(
                {'body': 'Changed without employee'}
            )
        message.action_approve()
        self.assertEqual(message.messaging_operation_ids.state, 'queued')
        with self.assertRaises(AccessError):
            conversation.write({'customer_id': False})

    def test_chatter_session_is_separate_and_revocable(self):
        before = self.env['ab_employee_access_sales_pos_session'].search_count([])
        token = self.chatter_api.employee_login(
            self.profile.id, '1234', 'chatter-only'
        )['token']
        self.assertEqual(
            self.env['ab_employee_access_sales_pos_session'].search_count([]), before
        )
        self.assertFalse(
            self.env['ab_employee_access_sales_pos_api']
            .with_user(self.staff)
            ._get_session(token, required=False)
        )
        with self.assertRaises(AccessError):
            self.env['ab_crm_chatter_session'].with_user(self.staff).create(
                {'token_hash': 'forged'}
            )
        with self.assertRaises(AccessError):
            self.chatter_api.with_user(self.other)._session(token)
        self.chatter_api.logout(token)
        with self.assertRaises(AccessError):
            self.chatter_api._session(token)

    def test_chatter_login_throttle_and_role_recheck(self):
        for unused in range(5):
            self.assertIn(
                'error',
                self.chatter_api.employee_login(self.profile.id, 'wrong', 'attempt'),
            )
        self.assertIn(
            'error', self.chatter_api.employee_login(self.profile.id, '1234', 'attempt')
        )
        self.staff.sudo().write(
            {'chatter_failed_attempts': 0, 'chatter_blocked_until': False}
        )
        token = self.chatter_api.employee_login(self.profile.id, '1234', 'attempt')[
            'token'
        ]
        self.profile.pos_allow_login = False
        with self.assertRaises(AccessError):
            self.chatter_api._session(token)

    def test_admin_legacy_service_role_can_work_after_employee_login(self):
        manager = self.env['res.users'].create(
            {
                'name': 'Chatter Admin',
                'login': 'chatter-admin',
                'group_ids': [
                    fields.Command.set(
                        [
                            self.env.ref('base.group_user').id,
                            self.env.ref('base.group_system').id,
                            self.env.ref('ab_sales.group_call_center').id,
                            self.env.ref('ab_crm_core.group_service').id,
                        ]
                    )
                ],
            }
        )
        api = self.chatter_api.with_user(manager)
        token = api.employee_login(self.profile.id, '1234', 'admin-device')['token']
        conversation = (
            self.conversation()
            .with_user(manager)
            .with_context(ab_chatter_session_token=token)
        )
        conversation.action_claim()
        conversation.action_identify()
        self.assertTrue(conversation.action_new_order())
        conversation.action_reply('Approved employee reply')
        with self.assertRaises(AccessError):
            self.chatter_api.with_user(self.service).bootstrap()

    def test_channel_notifications_are_scoped_and_cursor_based(self):
        conversation = self.conversation()
        result = self.chatter_api.notifications(self.session_token, 0)
        self.assertEqual(result['items'][0]['conversation_id'], conversation.id)
        self.assertEqual(result['items'][0]['provider'], 'telegram')
        self.assertNotIn('body', result['items'][0])
        self.assertFalse(
            self.chatter_api.notifications(self.session_token, result['cursor'])[
                'items'
            ]
        )
        token = self.chatter_api.with_user(self.other).employee_login(
            self.profile.id, '1234', 'other'
        )['token']
        self.assertFalse(
            self.chatter_api.with_user(self.other).notifications(token, 0)['items']
        )

    def test_employee_selection_excludes_non_call_center_roles(self):
        employee = self.employee.copy(
            {
                'name': 'Non Call Center',
                'user_id': self.service.id,
                'barcode': 'NONCALLCENTER',
            }
        )
        profile = self.profile.copy({'employee_id': employee.id, 'pos_pin': '1234'})
        employees = self.chatter_api.bootstrap()['employees']
        self.assertIn(self.profile.id, [value['id'] for value in employees])
        self.assertNotIn(profile.id, [value['id'] for value in employees])
        result = self.chatter_api.employee_login(profile.id, '1234', 'role-test')
        self.assertIn('error', result)

    def test_telegram_parameter_is_admin_only_and_account_bound(self):
        wizard = self.env['ab_crm_chatter_telegram_setup'].create(
            {
                'account_code': 'setup-bot',
                'bot_username': 'test_bot',
            }
        )
        with self.assertRaises(UserError):
            wizard.action_save()
        self.env['ir.config_parameter'].sudo().set_param(
            wizard._key(), '999000:' + 'x' * 32
        )
        wizard.action_save()
        self.assertNotIn('bot_token', wizard._fields)
        self.assertNotIn('branch_id', wizard._fields)
        account = self.env['ab_crm_messaging_account'].search(
            [('code', '=', 'setup-bot')]
        )
        self.assertFalse(account.enabled)
        service = self.env.ref('ab_crm_sales_workspace.user_telegram_development')
        values = (
            self.env['ab_crm_messaging_api']
            .with_user(service)
            .get_provider_credentials('setup-bot', '999000')
        )
        self.assertEqual(values['token'], '999000:' + 'x' * 32)
        with self.assertRaises(AccessError):
            self.env['ab_crm_messaging_api'].with_user(
                self.staff
            ).get_provider_credentials('setup-bot', '999000')
        with self.assertRaises(AccessError):
            self.env['ab_crm_messaging_api'].with_user(
                self.service
            ).get_provider_credentials('setup-bot', '999000')
        with self.assertRaises(AccessError):
            self.env['ab_crm_chatter_telegram_setup'].with_user(self.staff).create(
                {'account_code': 'forbidden'}
            )
        with self.assertRaises(AccessError):
            self.env['ir.config_parameter'].with_user(service).search([])

    def test_order_identity_is_derived_and_delivery_is_private(self):
        order = self.order()
        with self.assertRaises(AccessError):
            order.write({'customer_name': 'Spoofed'})
        with self.assertRaises(AccessError):
            self.env['ab_crm_channel_order'].with_user(self.staff).with_context(
                ab_chatter_session_token=self.session_token
            ).create(
                {
                    'conversation_id': order.conversation_id.id,
                    'customer_name': 'Spoofed',
                }
            )
        address = order.customer_id.address
        order.write({'delivery_address': 'Order only'})
        self.assertEqual(order.customer_id.address, address)
        order.workspace_data()
        self.assertEqual(order.customer_name, order.conversation_id.confirmed_phone)
        order.action_accept()
        snapshot = order._snapshot()
        order.conversation_id.customer_id.sudo().write({'name': 'Changed CRM name'})
        self.assertEqual(
            order.workspace_data()['customer_name'], snapshot['customer_name']
        )

    def test_atomic_save_repricing_and_stale_editor(self):
        order = self.order()
        self.replica.allowed_sales_store_ids |= self.foreign_store
        self.profile.pos_allowed_store_ids |= self.foreign_store
        data = order.workspace_data()
        lines = [
            {k: line[k] for k in ('id', 'product_id', 'uom_id', 'quantity', 'price')}
            for line in data['lines']
        ]
        lines[0]['quantity'] = -1
        with self.assertRaises(ValidationError):
            order.action_save_draft(
                {'store_id': self.foreign_store.id},
                lines,
                data['edit_version'],
                reprice=True,
            )
        self.assertEqual(order.store_id, self.store)
        self.assertEqual(order.line_ids.quantity, 1)
        lines[0]['quantity'] = 2
        lines[0]['price'] = 999
        result = order.action_save_draft(
            {'store_id': self.foreign_store.id},
            lines,
            data['edit_version'],
            reprice=True,
        )
        self.assertEqual(order.line_ids.price, 25)
        self.assertEqual(result['total'], 50)
        self.assertTrue(
            order.audit_ids.filtered(lambda row: row.action == 'branch_changed')
        )
        with self.assertRaises(UserError):
            order.action_save_draft({}, lines, data['edit_version'])

    def test_branch_preview_scope_and_barcode(self):
        order = self.order()
        with self.assertRaises(AccessError):
            order.preview_branch(self.foreign_store.id, self.product.ids)
        with self.assertRaises(UserError):
            order.write({'store_id': False})
        barcode = self.env['ab_product_barcode'].create({'name': 'TESTPOPUP123'})
        self.product.barcode_ids |= barcode
        rows = order.search_products('TESTPOPUP123')
        self.assertEqual(rows[0]['id'], self.product.id)
        self.assertEqual(rows[0]['balance_state'], 'unavailable')

    def test_contact_request_once_and_cancel_unsent(self):
        conversation = self.conversation()
        conversation.action_claim()
        first = conversation.action_request_contact()
        self.assertEqual(first, conversation.action_request_contact())
        operation = (
            self.env['ab_crm_message']
            .browse(first)
            .messaging_operation_ids.with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )
        operation.action_cancel_unsent('Replace old unsent request')
        self.assertEqual(operation.state, 'cancelled')
        second = conversation.action_request_contact()
        self.assertNotEqual(first, second)
        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        api.lease_outgoing(self.account.code, self.account.provider_account)
        with self.assertRaises(UserError):
            self.env['ab_crm_message'].browse(second).messaging_operation_ids.with_user(
                self.staff
            ).with_context(
                ab_chatter_session_token=self.session_token
            ).action_cancel_unsent(
                'Must refuse leased'
            )
        self.account.outgoing_enabled = False
        with self.assertRaises(UserError):
            conversation.action_request_contact()

    def test_auto_prompt_profile_and_contact_after_claim(self):
        self.account.contact_automation = True
        event = {
            'id': 'profile:1',
            'sender': '12345',
            'body': 'Hi',
            'timestamp': '2026-01-01 12:00:00',
            'unsupported': False,
            'source_digest': 'c' * 64,
            'profile': {'name': 'Telegram Name', 'username': 'test'},
        }
        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        result = api.receive_event(
            self.account.code, self.account.provider_account, event
        )
        conversation = (
            self.env['ab_crm_message']
            .browse(result['message_id'])
            .conversation_id.with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )
        self.assertEqual(conversation._customer_display_name(), 'Telegram Name')
        api.receive_event(self.account.code, self.account.provider_account, event)
        self.assertEqual(
            len(conversation.message_ids.filtered('telegram_request_contact')), 1
        )
        conversation.action_claim()
        self.receive('profile:2')
        conversation.workspace_detail()
        self.assertEqual(conversation.confirmed_phone, '+201012345678')
        self.assertEqual(conversation._customer_display_name(), 'Telegram Name')

    def test_media_private_and_immutable_snapshot(self):
        import base64

        conversation = self.conversation()
        conversation.action_claim()
        raw = b'%PDF-1.4\nSynthetic document'
        media = {
            'kind': 'document',
            'name': 'test.pdf',
            'mimetype': 'application/pdf',
            'size': len(raw),
            'data': base64.b64encode(raw).decode(),
        }
        message_id = conversation.action_reply(
            'Document', attachments=[media], reply_id=conversation.message_ids[0].id
        )
        message = self.env['ab_crm_message'].browse(message_id)
        self.assertEqual(
            message.messaging_operation_ids.content['media'][0]['data'], media['data']
        )
        with self.assertRaises(AccessError):
            message.media_ids.with_user(self.other).download()
        with self.assertRaises(AccessError):
            message.media_ids.with_user(self.staff).write({'name': 'changed.pdf'})
        with self.assertRaises(ValidationError):
            conversation.action_reply(
                'Too large', attachments=[dict(media, size=21 * 1024 * 1024)]
            )
        with self.assertRaises(ValidationError):
            conversation.action_reply(
                'Mismatch',
                attachments=[dict(media, mimetype='image/jpeg', kind='image')],
            )
        with self.assertRaises(ValidationError):
            conversation.action_reply(
                'Too long', attachments=[dict(media, duration=301)]
            )

    def test_saved_reply_scope_and_manager_guard(self):
        conversation = self.conversation()
        conversation.action_claim()
        with self.assertRaises(AccessError):
            conversation.save_template('Hello', 'Hello {{customer}}')
        template = self.env['ab_crm_saved_reply'].create(
            {
                'name': 'Greeting',
                'body': 'Hello {{customer}}',
                'branch_id': self.branch.id,
                'company_id': self.env.company.id,
            }
        )
        result = conversation.workspace_templates()
        self.assertIn(template.id, [row['id'] for row in result['items']])
        self.assertFalse(result['can_manage'])
        with self.assertRaises(AccessError):
            template.with_user(self.other).read(['body'])

    def test_incoming_media_is_account_scoped_and_cannot_be_replaced(self):
        import base64

        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        raw = b'%PDF-1.4\nIncoming test'
        event = {
            'id': '12345:media',
            'sender': '12345',
            'body': 'File',
            'timestamp': '2026-01-01 12:00:00',
            'unsupported': False,
            'source_digest': 'd' * 64,
            'media': {
                'kind': 'document',
                'name': 'file.pdf',
                'size': len(raw),
                'mimetype': 'application/pdf',
                'file_id': 'private-file',
            },
        }
        result = api.receive_event(
            self.account.code, self.account.provider_account, event
        )
        media = self.env['ab_crm_message'].browse(result['message_id']).media_ids
        self.assertEqual(media.state, 'pending')
        encoded = base64.b64encode(raw).decode()
        api.receive_media(
            self.account.code, self.account.provider_account, event['id'], encoded
        )
        self.assertEqual(media.state, 'ready')
        self.assertEqual(
            media.with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
            .download()['data'],
            encoded,
        )
        with self.assertRaises(AccessError):
            api.receive_media(self.account.code, 'wrong-account', event['id'], encoded)
        with self.assertRaises(ValidationError):
            api.receive_media(
                self.account.code,
                self.account.provider_account,
                event['id'],
                base64.b64encode(b'%PDF-changed').decode(),
            )
        with self.assertRaises(AccessError):
            media.with_user(self.service).read(['data'])

    def test_dialog_polling_does_not_mark_hidden_messages_read(self):
        conversation = self.conversation()
        conversation.workspace_detail(mark_read=False)
        self.assertFalse(
            self.env['ab_crm_workspace_read'].search(
                [('conversation_id', '=', conversation.id)]
            )
        )
        conversation.workspace_detail()
        self.assertTrue(
            self.env['ab_crm_workspace_read'].search(
                [('conversation_id', '=', conversation.id)]
            )
        )

    def test_invalid_shared_contact_never_blocks_reception_or_viewing(self):
        self.receive(phone='bad-phone')
        conversation = (
            self.env['ab_crm_conversation']
            .search([('channel_id', '=', self.channel.id)])
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )
        conversation.action_claim()
        detail = conversation.workspace_detail()
        self.assertTrue(detail['messages'])
        self.assertFalse(conversation.confirmed_phone)

    def test_ingestion_resolves_before_claim_and_with_expired_session(self):
        self.session.sudo().write({'expires_at': fields.Datetime.now()})
        result = self.receive()
        conversation = (
            self.env['ab_crm_message'].browse(result['message_id']).conversation_id
        )
        self.assertFalse(conversation.assigned_id)
        self.assertEqual(conversation.confirmed_phone, '+201012345678')
        self.assertEqual(conversation.catalog_match_state, 'unmatched')
        contact = conversation.customer_id
        identity = contact.identity_ids
        self.receive(event_id='second-contact')
        self.assertEqual(conversation.customer_id, contact)
        self.assertEqual(contact.identity_ids, identity)
        self.assertEqual(len(identity), 1)

    def test_ambiguous_ingestion_retains_crm_contact_and_evidence(self):
        for code in ('MATCH-A', 'MATCH-B'):
            self.env['ab_customer'].create(
                {
                    'name': code,
                    'code': code,
                    'mobile_phone': '01012345678',
                    'default_store_id': self.store.id,
                }
            )
        conversation = self.conversation()
        self.assertEqual(conversation.catalog_match_state, 'ambiguous')
        self.assertTrue(conversation.customer_id)
        self.assertFalse(conversation.customer_id.catalog_customer_id)
        self.assertTrue(conversation.contact_evidence_id.telegram_contact_owned)
        conversation.action_claim()
        order = (
            self.env['ab_crm_channel_order']
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
            .browse(conversation.action_new_order())
        )
        order.write({'store_id': self.store.id, 'confirmation': 'Customer approved'})
        order.action_add_product(self.product.id)
        order.action_accept()
        self.assertEqual(order.state, 'accepted')

    def test_third_party_order_acceptance_does_not_verify_contact(self):
        self.receive(owner='another-person')
        conversation = (
            self.env['ab_crm_conversation']
            .search(
                [
                    ('channel_id', '=', self.channel.id),
                ]
            )
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )
        self.assertFalse(conversation.customer_id)
        self.assertFalse(conversation.confirmed_phone)
        conversation.action_claim()
        order = (
            self.env['ab_crm_channel_order']
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
            .browse(conversation.action_new_order())
        )
        order.write({'store_id': self.store.id, 'confirmation': 'Customer approved'})
        order.action_add_product(self.product.id)
        order.action_accept()
        self.assertFalse(order.phone)
        self.assertFalse(order.customer_id)
        self.assertFalse(conversation.confirmed_phone)
        self.assertFalse(
            self.env['ab_crm_identity'].search([('channel_id', '=', self.channel.id)])
        )

    def test_workspace_read_does_not_resolve_contact(self):
        from unittest.mock import patch

        conversation = self.conversation()
        conversation.action_claim()
        with patch.object(
            type(conversation),
            '_link_contact',
            side_effect=AssertionError('Read linked a contact'),
        ):
            detail = conversation.workspace_detail(mark_read=False)
        self.assertEqual(detail['candidates'], [])

    def test_send_eligibility_matches_reply_and_preserves_queue(self):
        conversation = self.conversation()
        self.assertTrue(conversation.workspace_detail()['can_send'])
        conversation.action_claim()
        self.assertTrue(conversation.workspace_detail()['can_send'])
        for values, expected in [
            ({'outgoing_enabled': False}, 'outgoing_disabled'),
            ({'enabled': False}, 'account_disabled'),
            ({'active': False}, 'account_disabled'),
        ]:
            original = {key: self.account[key] for key in values}
            self.account.write(values)
            before = self.env['ab_crm_messaging_operation'].search_count([])
            detail = conversation.workspace_detail()
            self.assertFalse(detail['can_send'])
            self.assertEqual(detail['send_reason_code'], expected)
            self.assertEqual(detail['gateway_status'], 'unknown')
            with self.assertRaises(UserError):
                conversation.action_reply('Must not queue')
            self.assertEqual(
                self.env['ab_crm_messaging_operation'].search_count([]), before
            )
            self.account.write(original)

    def test_catalog_review_requires_manager_and_scoped_candidate(self):
        conversation = self.conversation()
        customer = self.env['ab_customer'].create(
            {
                'name': 'Candidate',
                'code': 'REVIEW-A',
                'mobile_phone': '01012345678',
                'default_store_id': self.store.id,
            }
        )
        with self.assertRaises(AccessError):
            conversation.action_review_catalog()
        admin_conversation = conversation.with_env(self.env)
        admin_conversation.review_catalog_customer_id = customer
        admin_conversation.action_review_catalog()
        self.assertEqual(conversation.customer_id.catalog_customer_id, customer)
        customer.default_store_id = self.foreign_store
        with self.assertRaises(AccessError):
            admin_conversation.action_review_catalog()

    def test_late_contact_fills_empty_draft_and_preserves_accepted_snapshot(self):
        self.receive(owner='third-party')
        conversation = (
            self.env['ab_crm_conversation']
            .search(
                [
                    ('channel_id', '=', self.channel.id),
                ]
            )
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
        )
        conversation.action_claim()
        order = (
            self.env['ab_crm_channel_order']
            .with_user(self.staff)
            .with_context(ab_chatter_session_token=self.session_token)
            .browse(conversation.action_new_order())
        )
        order.write(
            {
                'store_id': self.store.id,
                'delivery_address': 'Agent address',
                'confirmation': 'Customer approved',
            }
        )
        order.action_add_product(self.product.id)
        self.receive(event_id='self-contact')
        data = order.workspace_data()
        self.assertEqual(data['phone'], '+201012345678')
        self.assertEqual(data['delivery_address'], 'Agent address')
        order.action_accept()
        snapshot = order._snapshot()
        self.receive(event_id='different-phone', phone='01112345678')
        self.assertEqual(conversation.catalog_match_state, 'conflict')
        self.assertEqual(order._snapshot(), snapshot)
        self.assertEqual(conversation.confirmed_phone, '+201012345678')

    def test_ingestion_scope_and_evidence_cannot_be_forged(self):
        conversation = self.conversation()
        for values in [
            {'contact_evidence_id': conversation.message_ids.id},
            {'catalog_match_state': 'matched'},
        ]:
            with self.assertRaises(AccessError):
                conversation.write(values)
        with self.assertRaises(AccessError):
            conversation._resolve_ingested_contact(
                self.account, conversation.message_ids
            )
        with self.assertRaises(AccessError):
            self.env['ab_crm_messaging_api'].with_user(self.other).receive_event(
                self.account.code, self.account.provider_account, {}
            )

    def test_customer_label_excludes_legacy_destination_and_employee(self):
        conversation = self.conversation()
        conversation.action_claim()
        conversation.customer_id.name = conversation.external_key
        self.assertEqual(
            conversation._customer_display_name(), conversation.confirmed_phone
        )
        row = next(
            item
            for item in conversation.workspace_inbox()
            if item['id'] == conversation.id
        )
        self.assertNotEqual(row['name'], conversation.external_key)
        self.assertNotIn('assigned', row)
        self.assertEqual(row['preview'], conversation.message_ids.sorted('id')[-1].body)
        conversation._internal_write({'telegram_profile_name': 'Customer Profile'})
        self.assertEqual(conversation.workspace_detail()['name'], 'Customer Profile')
        with self.assertRaises(AccessError):
            conversation.with_user(self.other).workspace_detail()

    def test_orders_menu_is_separate_from_conversations(self):
        root = self.env.ref('ab_crm_sales_workspace.menu_workspace')
        orders = self.env.ref('ab_crm_sales_workspace.menu_orders')
        conversations = self.env.ref('ab_crm_sales_workspace.menu_conversations')
        self.assertEqual(orders.parent_id, root)
        self.assertEqual(conversations.parent_id, root)
        self.assertEqual(orders.action.tag, 'ab_crm_sales_workspace.orders')
        self.assertEqual(conversations.action.tag, 'ab_crm_sales_workspace.workspace')

    def test_alert_persistence_read_independence_and_arrival_race(self):
        conversation = self.conversation()
        first = self.chatter_api.notifications(self.session_token)['items'][0]
        conversation.workspace_detail()
        self.assertEqual(
            self.chatter_api.notifications(self.session_token)['items'][0], first
        )
        self.receive('alert-second')
        self.chatter_api.acknowledge_alert(
            self.session_token, conversation.id, first['message_ids']
        )
        pending = self.chatter_api.notifications(self.session_token)['items'][0]
        self.assertEqual(pending['count'], 1)
        self.assertNotEqual(pending['latest_message_id'], first['latest_message_id'])
        self.chatter_api.logout(self.session_token)
        token = self.chatter_api.employee_login(
            self.profile.id, '1234', 'alert-relogin'
        )['token']
        self.assertEqual(
            self.chatter_api.notifications(token)['items'][0]['message_ids'],
            pending['message_ids'],
        )
        self.chatter_api.acknowledge_alert(
            token, conversation.id, pending['message_ids']
        )
        self.assertFalse(self.chatter_api.notifications(token)['items'])

    def test_alert_employee_isolation_and_forgery(self):
        conversation = self.conversation()
        item = self.chatter_api.notifications(self.session_token)['items'][0]
        other_employee = self.employee.copy(
            {'name': 'Second alert employee', 'barcode': 'ALERT2'}
        )
        profile = self.profile.copy(
            {'employee_id': other_employee.id, 'pos_pin': '1234'}
        )
        token = self.chatter_api.employee_login(
            profile.id, '1234', 'second-alert-device'
        )['token']
        other_item = self.chatter_api.notifications(token)['items'][0]
        self.assertNotEqual(item['alert_key'], other_item['alert_key'])
        self.chatter_api.acknowledge_alert(
            self.session_token, conversation.id, item['message_ids']
        )
        self.assertTrue(self.chatter_api.notifications(token)['items'])
        with self.assertRaises(AccessError):
            self.chatter_api.acknowledge_alert(
                'forged', conversation.id, item['message_ids']
            )
        outgoing = conversation.action_reply('Outgoing cannot acknowledge an alert')
        with self.assertRaises(AccessError):
            self.chatter_api.acknowledge_alert(token, conversation.id, [outgoing])
        with self.assertRaises(AccessError):
            self.env['ab_crm_workspace_alert'].with_user(self.staff).search([])

    def test_focus_long_history_and_private_payload(self):
        conversation = self.conversation()
        first = conversation.message_ids.id
        for number in range(65):
            self.receive('focus-%s' % number)
        detail = conversation.workspace_focus(first)
        self.assertEqual(detail['messages'][-1]['id'], first)
        self.assertEqual(detail['focus_message_id'], first)
        self.assertNotIn('staff_reads', detail)
        for message in detail['messages']:
            self.assertEqual(message['status'], 'received')
            self.assertNotIn('evidence', message)
            self.assertNotIn('reference', message)
        outgoing = conversation.action_reply('Focus validation')
        with self.assertRaises(AccessError):
            conversation.workspace_focus(outgoing)

    def test_friendly_status_mapping_and_bounded_retry(self):
        conversation = self.conversation()
        message = self.env['ab_crm_message'].browse(
            conversation.action_reply('Status test')
        )
        operation = message.messaging_operation_ids
        for raw, expected in [
            ('queued', 'waiting'),
            ('leased', 'sending'),
            ('received', 'sending'),
            ('accepted', 'sent'),
            ('delivered', 'sent'),
            ('read', 'sent'),
            ('review', 'uncertain'),
            ('resolved', 'uncertain'),
            ('failed', 'failed'),
        ]:
            operation._change({'state': raw})
            data = (
                message.with_user(self.staff)
                .with_context(ab_chatter_session_token=self.session_token)
                ._display_status()
            )
            self.assertEqual(data['status'], expected)
        operation._change(
            {'state': 'failed', 'error_code': 'media', 'retryable': False}
        )
        self.assertFalse(message._display_status()['retry_operation_id'])
        self.assertIn('Choose another file', message._display_status()['explanation'])
        operation._change(
            {'state': 'failed', 'error_code': 'unavailable', 'retryable': True}
        )
        acting = operation.with_user(self.staff).with_context(
            ab_chatter_session_token=self.session_token
        )
        acting.action_retry()
        self.assertEqual(message._display_status()['status'], 'retrying')
        operation._change(
            {'state': 'failed', 'error_code': 'unavailable', 'retryable': True}
        )
        self.assertEqual(message._display_status()['status'], 'retry_failed')
        acting.action_retry()
        operation._change(
            {'state': 'failed', 'error_code': 'unavailable', 'retryable': True}
        )
        self.assertFalse(message._display_status()['retry_operation_id'])
        with self.assertRaises(UserError):
            acting.action_retry()
        operation._change({'state': 'review', 'error_code': 'ambiguous'})
        with self.assertRaises(UserError):
            acting.action_retry()

    def test_contact_directory_overrides_archive_and_audit(self):
        conversation = self.conversation()
        conversation.action_identify()
        customer = conversation.customer_id
        original = (
            customer.name,
            customer.phone,
            conversation.confirmed_phone,
            conversation.external_key,
            customer.catalog_customer_id.id,
        )
        values = {
            'name': 'Local display',
            'phone': '01098765432',
            'address': 'Local address',
        }
        saved = self.chatter_api.contact_save(
            self.session_token, values, contact_id=customer.id
        )
        self.assertEqual(saved['phone'], '+201098765432')
        self.assertEqual(conversation._customer_display_name(), 'Local display')
        self.assertEqual(
            original,
            (
                customer.name,
                customer.phone,
                conversation.confirmed_phone,
                conversation.external_key,
                customer.catalog_customer_id.id,
            ),
        )
        self.assertEqual(
            self.chatter_api.contact_search(self.session_token, query='Local')[
                'contacts'
            ][0]['id'],
            customer.id,
        )
        self.chatter_api.contact_archive(self.session_token, customer.id)
        self.assertFalse(customer.active)
        self.receive('after-archive')
        self.assertTrue(self.chatter_api.notifications(self.session_token)['items'])
        self.assertEqual(conversation.customer_id, customer)
        self.assertTrue(customer.identity_ids)
        logs = self.env['ab_crm_workspace_audit'].search(
            [('customer_id', '=', customer.id)]
        )
        self.assertEqual(
            set(logs.mapped('action')), {'edit_contact', 'archive_contact'}
        )
        self.assertEqual(logs.employee_id, self.employee)
        with self.assertRaises(AccessError):
            logs.with_user(self.staff).read(['employee_id'])

    def test_contact_without_conversation_and_scope(self):
        values = {
            'name': 'Directory only',
            'phone': '01012345678',
            'address': 'Address',
        }
        saved = self.chatter_api.contact_save(
            self.session_token, values, branch_id=self.branch.id
        )
        self.assertFalse(
            self.chatter_api.contact_open(self.session_token, saved['id'])[
                'conversation_id'
            ]
        )
        self.assertTrue(
            self.chatter_api.contact_search(self.session_token, phone='01012345678')[
                'contacts'
            ]
        )
        contact = self.env['ab_crm_customer'].browse(saved['id'])
        self.assertFalse(contact.identity_ids)
        with self.assertRaises(AccessError):
            self.chatter_api.contact_save('forged', values, contact_id=contact.id)
        self.branch.user_ids -= self.staff
        with self.assertRaises(AccessError):
            self.chatter_api.contact_save(
                self.session_token, values, contact_id=contact.id
            )
        with self.assertRaises(AccessError):
            self.chatter_api.contact_archive(self.session_token, contact.id)
        with self.assertRaises(AccessError):
            self.chatter_api.contact_save(
                self.session_token, values, branch_id=self.branch.id
            )

    def test_installed_crm_oms_menu_views(self):
        entries = (
            self.env['ir.model.data']
            .search(
                [
                    ('module', '=like', 'ab_%'),
                    ('model', '=', 'ir.ui.menu'),
                ]
            )
            .filtered(lambda entry: entry.module.startswith(('ab_crm_', 'ab_oms_')))
        )
        checked = set()
        for entry in entries:
            menu = self.env['ir.ui.menu'].browse(entry.res_id).exists()
            action = menu.action
            if (
                not action
                or action._name != 'ir.actions.act_window'
                or action.id in checked
            ):
                continue
            checked.add(action.id)
            model = self.env[action.res_model]
            views = [(False, kind) for kind in ('list', 'form', 'search')]
            result = model.get_views(views, {'action_id': action.id, 'toolbar': True})
            self.assertEqual(
                set(result['views']), {'list', 'form', 'search'}, menu.complete_name
            )
        self.assertTrue(checked)

    def test_alert_backlog_paginates_conversations_without_loss(self):
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        expected = set()
        for index in range(56):
            result = gateway.receive_event(
                'workspace-bot',
                '900000234',
                {
                    'id': 'backlog-%s' % index,
                    'sender': str(30000 + index),
                    'body': 'Offline backlog',
                    'timestamp': '2026-01-01 12:00:00',
                    'unsupported': False,
                    'source_digest': 'b' * 64,
                },
            )
            expected.add(result['message_id'])
        first = self.chatter_api.notifications(self.session_token)
        self.assertTrue(first['has_more'])
        self.assertEqual(len(first['items']), 50)
        second = self.chatter_api.notifications(self.session_token, first['cursor'])
        self.assertFalse(second['has_more'])
        actual = {
            mid
            for item in first['items'] + second['items']
            for mid in item['message_ids']
        }
        self.assertEqual(actual, expected)

    def test_retry_rejects_older_attempt_and_telegram_receipts(self):
        conversation = self.conversation()
        operation = (
            self.env['ab_crm_message']
            .browse(conversation.action_reply('Attempt test'))
            .messaging_operation_ids
        )
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        operation._change(
            {'state': 'failed', 'retryable': True, 'error_code': 'unavailable'}
        )
        operation.with_user(self.staff).with_context(
            ab_chatter_session_token=self.session_token
        ).action_retry()
        with self.assertRaises(AccessError):
            gateway._operation(self.account, operation.token, 1)
        with self.assertRaises(ValidationError):
            gateway._apply_status(
                self.account, operation, 'read', 'tg-reference', 'none'
            )
        gateway._apply_status(
            self.account, operation, 'accepted', 'tg-reference', 'none'
        )
        gateway._apply_status(self.account, operation, 'review', '', 'ambiguous')
        self.assertEqual(operation.state, 'accepted')
        self.assertEqual(operation.attempt, 2)
        audits = self.env['ab_crm_workspace_audit'].search(
            [('message_id', '=', operation.message_id.id)]
        )
        self.assertEqual(set(audits.mapped('action')), {'reply', 'retry_message'})
        self.assertEqual(audits.employee_id, self.employee)
        self.assertEqual(audits.user_id, self.staff)

    def test_diagnostic_history_and_staff_reads_are_protected(self):
        conversation = self.conversation()
        conversation.workspace_detail()
        with self.assertRaises(AccessError):
            self.env['ab_crm_workspace_read'].with_user(self.staff).search([])
        operation = (
            self.env['ab_crm_message']
            .browse(conversation.action_reply('Private diagnostics'))
            .messaging_operation_ids
        )
        with self.assertRaises(AccessError):
            operation.with_user(self.staff).read(
                ['history', 'error_code', 'provider_reference']
            )
        with self.assertRaises(AccessError):
            operation.with_user(self.staff).action_close_review('Forged review')

    def test_contact_pagination_and_formatted_phone_duplicates(self):
        for index in range(35):
            self.chatter_api.contact_save(
                self.session_token,
                {'name': 'Paged contact %s' % index, 'phone': '01098765432', 'address': ''},
                branch_id=self.branch.id,
            )
        first = self.chatter_api.contact_search(self.session_token, query='Paged contact')
        second = self.chatter_api.contact_search(self.session_token, query='Paged contact', offset=30)
        self.assertEqual(len(first['contacts']), 30)
        self.assertTrue(first['has_more'])
        self.assertEqual(len(second['contacts']), 5)
        self.assertFalse(second['has_more'])
        self.assertFalse({row['id'] for row in first['contacts']} & {row['id'] for row in second['contacts']})
        contact = self.env['ab_crm_customer'].create({
            'name': 'Formatted existing contact', 'phone': '010 1234 5678',
            'branch_id': self.branch.id,
        })
        candidates = self.chatter_api.contact_search(self.session_token, phone='+201012345678')
        self.assertIn(contact.id, [row['id'] for row in candidates['contacts']])
        self.assertEqual(contact.phone, '010 1234 5678')
