from uuid import uuid4

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import HttpCase, tagged
from .test_contact_groups import TestWebsiteContactGroups
from ..protocol import fingerprint
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION


@tagged('post_install', '-at_install', 'chat_ux')
class TestChatUX(TestWebsiteContactGroups):
    def target(self, order):
        return {'kind': 'order', 'uuid': order.order_uuid}

    def pair(self):
        identity = str(uuid4())
        conversation = self.website_order(account_identity=identity)
        self.website_order('SECOND', account_identity=identity)
        orders = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)], order='id')
        return conversation, orders, identity

    def close(self, conversation, destination, identity, kind='order_dispatched', identity_kind='customer'):
        event = {'version': 3, 'source': self.website_account.provider_account,
            'event_uuid': str(uuid4()), 'kind': kind, 'destination': destination,
            'identity': {'kind': identity_kind, 'uuid': identity}}
        event['fingerprint'] = fingerprint(event)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        gateway.receive_website_lifecycle(self.website_account.code, self.website_account.provider_account, event)
        return event

    def test_target_isolation_and_reads(self):
        conversation, orders, identity = self.pair()
        one, two = [self.target(order) for order in orders]
        self.chat(conversation, orders[0], identity=identity)
        self.chat(conversation, orders[1], identity=identity)
        first = conversation.workspace_detail(target=one)
        second = conversation.workspace_detail(target=two)
        self.assertTrue(first['messages'])
        self.assertFalse(set(item['id'] for item in first['messages']) & set(item['id'] for item in second['messages']))
        conversation.workspace_acknowledge(first['messages'][-1]['id'], target=one)
        self.assertEqual(conversation.workspace_detail(target=one)['unread_count'], 0)
        self.assertGreater(conversation.workspace_detail(target=two)['unread_count'], 0)
        with self.assertRaises(AccessError):
            conversation.workspace_acknowledge(second['messages'][-1]['id'], target=one)
        with self.assertRaises(ValidationError):
            conversation.website_action_reply('Ambiguous reply')
        sent = self.env['ab_crm_message'].browse(conversation.website_action_reply('First order', target=one))
        self.assertEqual(sent.website_order_id, orders[0])
        with self.assertRaises(AccessError):
            conversation.website_action_reply('Wrong quote', target=two, reply_id=first['messages'][0]['id'])

    def test_combined_orders_preserve_support_and_reply_destinations(self):
        conversation, orders, identity = self.pair()
        self.chat(conversation, orders[0], identity=identity)
        self.chat(conversation, orders[1], identity=identity)
        support = self.chat(conversation, identity=identity)
        detail = conversation.workspace_detail(target=self.target(orders[0]), combine=True)
        self.assertTrue(detail['website_combined'])
        self.assertEqual({item['website_target']['uuid'] for item in detail['messages']}, set(orders.mapped('order_uuid')))
        self.assertTrue(all(item['website_target']['kind'] == 'order' for item in detail['messages']))
        self.assertTrue(all(item.get('website_order_reference') for item in detail['messages']))
        support_detail = conversation.workspace_detail(target=support['destination'], combine=True)
        self.assertTrue(all(item['website_target'] == support['destination'] for item in support_detail['messages']))
        for order in orders:
            incoming = next(item for item in detail['messages'] if item['direction'] == 'in'
                and item['website_target'] == self.target(order) and item['actions']['reply']['enabled'])
            sent = self.env['ab_crm_message'].browse(conversation.website_action_reply('Reply to this order',
                target=incoming['website_target'], reply_id=incoming['id']))
            self.assertEqual(sent.website_order_id, order)
        with self.assertRaises(AccessError):
            conversation.workspace_detail(target={'kind': 'order', 'uuid': str(uuid4())}, combine=True)

    def test_combined_orders_follow_verified_canonical_conversation(self):
        conversation, orders, identity = self.pair()
        alias = self.website_order('ALIAS')
        order = self.env['ab_crm_website_order'].search([('reference', '=', 'ALIAS')])
        self.close(alias, self.target(order), identity, kind='identity_bound')
        self.assertEqual(alias.website_canonical_id, conversation)
        detail = alias.workspace_detail(target=self.target(orders[0]), combine=True)
        references = {item['website_target']['uuid'] for item in detail['messages']}
        self.assertEqual(references, set((orders | order).mapped('order_uuid')))

    def test_linked_contact_with_website_and_telegram_channels(self):
        conversation, orders, identity = self.pair()
        self.chat(conversation, orders[0], identity=identity)
        telegram = self.conversation()
        self.link(conversation)
        self.link(telegram)
        streams = conversation._workspace_streams()
        self.assertEqual(set(streams.channel_id.mapped('provider')), {'website', 'telegram'})
        for combine in (False, True):
            detail = conversation.workspace_detail(target=self.target(orders[0]), combine=combine)
            self.assertEqual({item['provider'] for item in detail['streams']}, {'website', 'telegram'})
            self.assertTrue(all(item.get('website_target') for item in detail['messages']))
            self.assertTrue(any(item['provider'] == 'telegram' and item['unread'] for item in detail['streams']))
        detail = telegram.workspace_detail()
        self.assertTrue(detail['messages'])
        self.assertTrue(all(not item.get('website_target') for item in detail['messages']))
        rows = streams._workspace_inbox_rows(conversation._workspace_actor())
        self.assertEqual({item['id'] for item in rows}, set(streams.ids))

    def test_linked_distinct_website_targets_do_not_scope_inbox_summaries(self):
        first = self.website_order('FIRST-IDENTITY', account_identity=str(uuid4()))
        second = self.website_order('SECOND-IDENTITY', account_identity=str(uuid4()))
        self.link(first)
        self.link(second)
        telegram = self.conversation()
        self.link(telegram)
        snapshots = {stream.id: stream.message_ids.ids for stream in first | second | telegram}
        for stream in first | second:
            order = self.env['ab_crm_website_order'].search([('conversation_id', '=', stream.id)])
            self.chat(stream, order, identity=stream.website_account_identity)
            for combined in (False, True):
                detail = stream.workspace_detail(target=self.target(order), combine=combined)
                self.assertEqual({item['id'] for item in detail['streams']}, set((first | second | telegram).ids))
                self.assertEqual({item['website_target']['uuid'] for item in detail['messages']}, {order.order_uuid})
            with self.assertRaises(AccessError):
                stream.workspace_detail(target={'kind': 'order', 'uuid': str(uuid4())}, combine=True)
        preview = first.action_preview_customer_unlink(self.contact['id'])
        with self.assertRaises(AccessError):
            first.with_user(self.other).action_unlink_customer(self.contact['id'], preview['fingerprint'])
        first.action_unlink_customer(self.contact['id'], preview['fingerprint'])
        self.assertFalse((first | second | telegram).customer_id)
        with self.assertRaises(AccessError):
            first.workspace_channel(second.id)
        for stream in first | second | telegram:
            self.assertTrue(set(snapshots[stream.id]).issubset(stream.message_ids.ids))
            self.link(stream)
        self.assertEqual(set(first._workspace_streams().ids), set((first | second | telegram).ids))

    def test_unlink_includes_hidden_canonical_aliases(self):
        canonical, orders, identity = self.pair()
        alias = self.website_order('HIDDEN-ALIAS')
        order = self.env['ab_crm_website_order'].search([('reference', '=', 'HIDDEN-ALIAS')])
        self.close(alias, self.target(order), identity, kind='identity_bound')
        self.assertEqual(alias.website_canonical_id, canonical)
        self.link(canonical)
        telegram = self.conversation()
        self.link(telegram)
        streams = canonical | alias | telegram
        snapshots = streams.message_ids.ids
        preview = canonical.action_preview_customer_unlink(self.contact['id'])
        self.assertEqual(set(preview['conversation_ids']), set(streams.ids))
        canonical.action_unlink_customer(self.contact['id'], preview['fingerprint'])
        self.assertFalse(streams.customer_id)
        self.assertEqual(streams.message_ids.ids, snapshots)
        self.assertEqual(alias.website_canonical_id, canonical)
        self.link(canonical)
        self.assertEqual((canonical | alias).customer_id.id, self.contact['id'])

    def test_combined_reads_cover_orders_without_reading_support(self):
        conversation, orders, identity = self.pair()
        self.chat(conversation, orders[0], identity=identity)
        self.chat(conversation, orders[1], identity=identity)
        support = self.chat(conversation, identity=identity)
        detail = conversation.workspace_detail(target=self.target(orders[1]), combine=True)
        last = max((item for item in detail['messages'] if item['direction'] == 'in'), key=lambda item: item['id'])
        conversation.workspace_acknowledge(last['id'], target=last['website_target'], combine=True)
        self.assertEqual(conversation.workspace_detail(target=self.target(orders[0]), combine=True)['unread_count'], 0)
        self.assertGreater(conversation.workspace_detail(target=support['destination'])['unread_count'], 0)
        with self.assertRaises(AccessError):
            conversation.workspace_acknowledge(last['id'], target=support['destination'], combine=True)

    def test_combined_channel_pagination_and_closed_order(self):
        conversation, orders, identity = self.pair()
        for index in range(52):
            self.chat(conversation, orders[index % 2], identity=identity)
        self.close(conversation, self.target(orders[1]), identity)
        detail = conversation.workspace_detail(target=self.target(orders[1]), combine=True)
        self.assertEqual(detail['website_target'], self.target(orders[0]))
        self.assertTrue(detail['can_send'])
        messages = [item for item in detail['messages'] if item['item_type'] == 'message']
        self.assertEqual(len(messages), 50)
        self.assertTrue(detail['has_older'])
        older = conversation.workspace_detail(target=self.target(orders[0]), combine=True, before_id=messages[0]['id'])
        self.assertFalse({item['id'] for item in messages} & {item['id'] for item in older['messages']})
        closed = [item for item in messages if item['website_target'] == self.target(orders[1])]
        self.assertTrue(closed)
        self.assertTrue(all(not item['actions']['reply']['enabled'] for item in closed))

    def test_same_phone_is_not_identity(self):
        first = self.website_order()
        second = self.website_order('ANOTHER')
        self.assertNotEqual(first, second)
        self.assertNotEqual(first.customer_group_key, second.customer_group_key)

    def test_lifecycle_information_is_deduplicated(self):
        conversation, orders, identity = self.pair()
        target = self.target(orders[0])
        before = conversation._workspace_activity()
        event = self.close(conversation, target, identity)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        gateway.receive_website_lifecycle(self.website_account.code, self.website_account.provider_account, event)
        detail = conversation.workspace_detail(target=target)
        info = [item for item in detail['messages'] if item['item_type'] == 'information']
        self.assertEqual(len(info), 1)
        self.assertLess(info[0]['id'], 0)
        self.assertEqual(conversation._workspace_activity(), before)
        self.assertFalse(conversation.message_ids.filtered('website_closure_notice'))

    def test_all_order_targets_remain_visible_and_preferences_private(self):
        conversation, orders, identity = self.pair()
        for order in orders:
            self.chat(conversation, order, identity=identity)
            self.close(conversation, self.target(order), identity)
        detail = conversation.workspace_detail(target=self.target(orders[0]), combine=True)
        self.assertEqual({item['uuid'] for item in detail['website_targets']}, set(orders.mapped('order_uuid')))
        self.assertEqual({item['website_target']['uuid'] for item in detail['messages']}, set(orders.mapped('order_uuid')))
        self.assertIn(conversation.id, [row['id'] for row in conversation.workspace_customer_inbox()['items']])
        self.assertFalse(hasattr(conversation, 'workspace_archive_chats'))
        self.assertFalse(hasattr(conversation, 'website_archive_targets'))
        preference = self.env['ab_crm_website_target_preference']
        self.assertNotIn('archived', preference._fields)
        self.assertNotIn('archived_through', preference._fields)
        with self.assertRaises(AccessError):
            preference.with_user(self.staff).search([]).read()
        with self.assertRaises(AccessError):
            preference.with_user(self.staff).create({})
        self.assertFalse(self.env.ref('ab_crm_sales_workspace.menu_archived_chats').active)
        self.assertEqual(self.env.ref('ab_crm_sales_workspace.action_archived_chats').context, '{}')

    def test_no_claim_or_tab_protocol_is_required(self):
        conversation, orders, identity = self.pair()
        detail = conversation.workspace_detail(target=self.target(orders[0]))
        self.assertTrue(detail['owned'])
        self.assertNotIn('reservation', detail)
        self.assertNotIn('reservation_employee_id', conversation._fields)
        self.assertFalse(hasattr(conversation, 'workspace_reservation'))
        self.assertFalse(hasattr(conversation, 'workspace_transfer'))
        message = conversation.website_action_reply('Direct reply without a claim', target=self.target(orders[0]))
        operation = self.env['ab_crm_messaging_operation'].search([('message_id', '=', message)])
        self.assertTrue(self.env['ab_crm_messaging_api']._website_operation_allowed(self.website_account, operation))

    def test_activity_cursor_before_pagination(self):
        conversation, orders, identity = self.pair()
        others = [self.website_order('ROW-%s' % index, account_identity=str(uuid4())) for index in range(52)]
        inbox = conversation.workspace_customer_inbox()
        self.assertEqual(len(inbox['items']), 50)
        self.assertNotIn(conversation.id, [row['id'] for row in inbox['items']])
        conversation.website_action_reply('Recent response', target=self.target(orders[0]))
        replied = conversation.workspace_customer_inbox()
        self.assertEqual([row['id'] for row in replied['items']], [row['id'] for row in inbox['items']])
        self.chat(conversation, orders[0], identity=identity)
        newest = conversation.workspace_customer_inbox()
        self.assertEqual(newest['items'][0]['id'], conversation.id)
        page2 = conversation.workspace_customer_inbox(cursor=newest['next_cursor'])
        self.assertFalse(set(row['group_key'] for row in newest['items']) & set(row['group_key'] for row in page2['items']))

    def test_all_authorized_agents_can_reply_with_employee_audit(self):
        conversation, orders, identity = self.pair()
        support = self.chat(conversation, identity=identity)
        targets = [self.target(order) for order in orders] + [support['destination']]
        self.branch.user_ids = [fields.Command.link(self.other.id)]
        tokens = {}
        for index, user in enumerate([self.other, self.staff]):
            employee = self.env['ab_hr_employee'].create({
                'name': 'Shared chat employee %s' % index, 'barcode': 'UX-OPEN-%s' % index, 'user_id': user.id})
            profile = self.profile.copy({'employee_id': employee.id, 'pos_pin': '1234'})
            token = self.env['ab_crm_chatter_api'].with_user(user).employee_login(profile.id, '1234', 'ux-open-%s' % index)['token']
            tokens[user.id] = token
            other = conversation.with_user(user).with_context(ab_chatter_session_token=token)
            for target in targets:
                conversation.website_action_reply('First employee response', target=target)
                self.assertTrue(other.workspace_detail(target=target)['can_send'])
                message = other.website_action_reply('Another employee response', target=target)
                audit = self.env['ab_crm_workspace_audit'].search([('message_id', '=', message), ('action', '=', 'reply')])
                self.assertEqual(audit.employee_id, employee)
                self.assertEqual(audit.user_id, user)
            with self.assertRaises(AccessError):
                other.with_context(ab_chatter_session_token='forged').website_action_reply('Forged session', target=targets[0])
        self.branch.user_ids = [fields.Command.unlink(self.other.id)]
        with self.assertRaises(AccessError):
            conversation.with_user(self.other).with_context(ab_chatter_session_token=tokens[self.other.id]).workspace_detail(target=targets[0])

    def test_trusted_guest_group_preserves_ended_history(self):
        from copy import deepcopy
        visitor = str(uuid4())
        legacy = self.website_order('LEGACY-BASE')
        support = self.chat(legacy, identity=visitor, kind='visitor')
        template = self.env['ab_crm_website_event'].search([('order_uuid', '!=', False)], order='id desc', limit=1).envelope
        for reference in ['GUEST-ONE', 'GUEST-TWO']:
            event = deepcopy(template)
            event.update(order_uuid=str(uuid4()), event_uuid=str(uuid4()))
            event['payload'].update(reference=reference, origin_kind='guest', visitor_identity=visitor)
            event['fingerprint'] = fingerprint(event)
            self.env['ab_crm_messaging_api'].with_user(self.service).receive_website_event(
                self.website_account.code, self.website_account.provider_account, event)
        orders = self.env['ab_crm_website_order'].search([('visitor_identity', '=', visitor)], order='id')
        self.assertEqual(len(orders.conversation_id), 1)
        session = self.env['ab_crm_website_session'].search([('session_uuid', '=', support['destination']['uuid'])])
        self.assertEqual(orders.conversation_id, session.conversation_id)
        conversation = session.conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.close(conversation, support['destination'], visitor, kind='session_ended', identity_kind='visitor')
        detail = conversation.workspace_detail(target=support['destination'])
        self.assertEqual(len([item for item in detail['messages'] if item['item_type'] == 'information']), 1)
        self.assertIn(conversation.id, [row['id'] for row in conversation.workspace_customer_inbox()['items']])
        fresh = self.chat(conversation, identity=visitor, kind='visitor')
        self.assertNotEqual(fresh['destination'], support['destination'])
        combined = conversation.workspace_detail(target=fresh['destination'], combine=True)
        uuids = {item['website_target']['uuid'] for item in combined['messages']}
        self.assertIn(support['destination']['uuid'], uuids)
        self.assertIn(fresh['destination']['uuid'], uuids)

    def test_legacy_shared_phone_history_cannot_bind_other_orders(self):
        conversation = self.website_order('LEGACY-OWNER')
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        mutation = _MUTATION.set(True)
        try:
            sibling = self.env['ab_crm_website_order'].create({
                'account_id': self.website_account.id, 'order_uuid': str(uuid4()), 'reference': 'LEGACY-OTHER',
                'conversation_id': conversation.id, 'revision': 1, 'snapshot': order.snapshot,
                'branch_id': self.branch.id, 'company_id': self.branch.company_id.id})
        finally:
            _MUTATION.reset(mutation)
        with self.assertRaises(AccessError):
            self.close(conversation, self.target(order), str(uuid4()), kind='identity_bound')
        self.assertFalse(order.account_identity)
        self.assertFalse(sibling.account_identity)
        self.assertFalse(conversation.website_account_identity)

    def test_inbox_received_order_across_channels_and_lifecycle(self):
        first, orders, identity = self.pair()
        telegram = self.conversation()
        self.link(first)
        self.link(telegram)
        website = self.website_order('LATEST-RECEIVED', phone='01199998888', account_identity=str(uuid4()))
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', website.id)])
        self.chat(website, order, identity=website.website_account_identity)
        api = first
        before = api.workspace_customer_inbox()['items']
        self.assertEqual(before[0]['id'], website.id)
        first.website_action_reply('Reply does not move a row', target=self.target(orders[0]))
        self.assertEqual(api.workspace_customer_inbox()['items'][0]['id'], website.id)
        self.receive('latest-telegram-received')
        incoming = api.workspace_customer_inbox()['items']
        self.assertEqual(incoming[0]['id'], telegram.id)
        self.assertIn(telegram.id, {row['id'] for row in incoming[0]['streams']})
        self.assertIn(first.id, {row['id'] for row in incoming})
        rank = first._workspace_activity()
        self.close(first, self.target(orders[0]), identity)
        self.assertEqual(first._workspace_activity(), rank)
        self.assertEqual(api.workspace_customer_inbox()['items'][0]['id'], telegram.id)


class TestChatUXBrowser(TestChatUX, HttpCase):
    def browser(self, language, mobile=False):
        import json
        import os
        import subprocess
        from pathlib import Path
        self.env['res.lang']._activate_lang(language)
        self.staff.lang = language
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        conversation, orders, identity = self.pair()
        for order in orders:
            self.chat(conversation, order, identity=identity)
        support = self.chat(conversation, identity=identity)
        from copy import deepcopy
        support_message = deepcopy(support)
        support_message.update(event_uuid=str(uuid4()), body='Support-only message')
        support_message['fingerprint'] = fingerprint(support_message)
        self.env['ab_crm_messaging_api'].with_user(self.service).receive_website_chat(
            self.website_account.code, self.website_account.provider_account, support_message)
        employee = self.env['ab_hr_employee'].create({'name': 'Browser colleague', 'barcode': 'UX-BROWSER', 'user_id': self.staff.id})
        profile = self.profile.copy({'employee_id': employee.id, 'pos_pin': '1234'})
        colleague_token = self.chatter_api.employee_login(profile.id, '1234', 'ux-browser-colleague')['token']
        visitor = str(uuid4())
        guest = self.chat(conversation, identity=visitor, kind='visitor')
        guest_session = self.env['ab_crm_website_session'].search([('session_uuid', '=', guest['destination']['uuid'])])
        self.close(conversation, guest['destination'], visitor, kind='session_ended', identity_kind='visitor')
        self.session = None
        self.authenticate(self.staff.login, self.staff.login)
        self.cr.flush()
        self.cr.clear()
        with self.allow_requests(all_requests=True):
            data = {'url': self.base_url(), 'cookies': self.opener.cookies.get_dict(),
                'token': self.session_token, 'employee': self.employee.id, 'conversation': conversation.id,
                'orders': [self.target(order) for order in orders], 'support': support['destination'],
                'colleague_token': colleague_token, 'colleague': employee.id,
                'guest_conversation': guest_session.conversation_id.id, 'guest_target': guest['destination'],
                'mobile': mobile, 'language': language, 'screenshot': '/tmp/chatter-ux/' + language + '.png'}
            result = subprocess.run(['node', '/opt/odoo19/worktrees/e_commerce/qa/chatter_ux/browser.cjs'],
                input=json.dumps(data), text=True, capture_output=True, timeout=120,
                env=dict(os.environ, NODE_PATH='/tmp/chat-lifecycle-validation/browser-deps/node_modules'))
            self._wait_remaining_requests()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_english_desktop(self):
        self.browser('en_US')

    def test_arabic_mobile(self):
        self.browser('ar_001', mobile=True)
