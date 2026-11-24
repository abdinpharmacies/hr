from uuid import uuid4

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged

from .test_chat_ux import TestChatUX


@tagged('post_install', '-at_install', 'independent_chats')
class TestIndependentChats(TestChatUX):
    def test_independent_inbox_and_pagination(self):
        conversation, orders, identity = self.pair()
        support = self.chat(conversation, identity=identity)
        again = self.chat(conversation, identity=identity, session=str(uuid4()))
        targets = [self.target(order) for order in orders] + [support['destination'], again['destination']]
        inbox = conversation.workspace_customer_inbox(limit=2)
        more = conversation.workspace_customer_inbox(limit=2, cursor=inbox['next_cursor'])
        items = inbox['items'] + more['items']
        self.assertTrue(inbox['has_more'])
        self.assertFalse(more['has_more'])
        self.assertEqual(len(items), 4)
        self.assertEqual(len({item['group_key'] for item in items}), 4)
        self.assertEqual({item['website_target']['uuid'] for item in items}, {target['uuid'] for target in targets})
        self.assertTrue(all(len(item['streams']) == 1 for item in items))
        for target in targets:
            detail = conversation.workspace_detail(target=target, combine=True)
            self.assertFalse(detail['website_combined'])
            self.assertTrue(all(message['website_target'] == target for message in detail['messages']))

    def test_independent_reads_and_notifications(self):
        conversation, orders, identity = self.pair()
        for order in orders:
            self.chat(conversation, order, identity=identity)
        support = self.chat(conversation, identity=identity)
        items = [item for item in self.chatter_api.notifications(self.session_token)['items']
                 if item['conversation_id'] == conversation.id]
        self.assertEqual(len(items), 3)
        self.assertEqual(len({item['alert_key'] for item in items}), 3)
        first = next(item for item in items if item['website_target'] == self.target(orders[0]))
        other = next(item for item in items if item['website_target'] == self.target(orders[1]))
        with self.assertRaises(AccessError):
            self.chatter_api.acknowledge_alert(self.session_token, conversation.id,
                first['message_ids'] + other['message_ids'], target=first['website_target'])
        with self.assertRaises(AccessError):
            self.chatter_api.acknowledge_alert(self.session_token, conversation.id,
                first['message_ids'], target=other['website_target'])
        detail = conversation.workspace_focus(first['latest_message_id'], target=first['website_target'])
        self.assertEqual(detail['website_target'], first['website_target'])
        conversation.workspace_acknowledge(first['latest_message_id'], target=first['website_target'], combine=True)
        self.chatter_api.acknowledge_alert(self.session_token, conversation.id,
            first['message_ids'], target=first['website_target'])
        self.assertEqual(conversation.workspace_detail(target=first['website_target'])['unread_count'], 0)
        self.assertGreater(conversation.workspace_detail(target=other['website_target'])['unread_count'], 0)
        self.assertGreater(conversation.workspace_detail(target=support['destination'])['unread_count'], 0)
        with self.assertRaises(AccessError):
            conversation.workspace_focus(first['latest_message_id'], target=other['website_target'])
        pending = self.chatter_api.notifications(self.session_token)['items']
        self.assertEqual({item['website_target']['uuid'] for item in pending},
                         {other['website_target']['uuid'], support['destination']['uuid']})

    def test_independent_manual_linking_disabled(self):
        conversation, orders, identity = self.pair()
        for actor in (conversation, conversation.sudo()):
            for method, args in [('action_customer_link_candidates', []),
                    ('action_preview_customer_link', [self.contact['id']]),
                    ('action_confirm_customer_link', [self.contact['id'], 'forged']),
                    ('action_preview_customer_unlink', [self.contact['id']]),
                    ('action_unlink_customer', [self.contact['id'], 'forged']),
                    ('action_identify', [])]:
                with self.assertRaises(AccessError):
                    getattr(actor, method)(*args)
        for method, args in [('website_reconciliation_preview', [self.website_account.id]),
                             ('website_reconciliation_apply', [self.website_account.id, 'forged'])]:
            with self.assertRaises(AccessError):
                getattr(orders.sudo(), method)(*args)
        before = (orders.mapped('conversation_id').ids, orders.mapped('website_customer_id').ids)
        conversation.workspace_customer_inbox()
        conversation.workspace_detail(target=self.target(orders[0]))
        self.assertFalse(conversation.customer_id)
        self.assertEqual(before, (orders.mapped('conversation_id').ids, orders.mapped('website_customer_id').ids))

    def test_independent_target_access(self):
        conversation, orders, identity = self.pair()
        target = self.target(orders[0])
        for denied in (conversation.with_user(self.other), conversation.with_user(self.service),
                       conversation.with_context(ab_chatter_session_token='forged')):
            with self.assertRaises(AccessError):
                denied.workspace_detail(target=target)
            with self.assertRaises(AccessError):
                denied.website_action_reply('Denied', target=target)
        unrelated = self.website_order('OTHER')
        alien = self.env['ab_crm_website_order'].search([('conversation_id', '=', unrelated.id)])
        with self.assertRaises(AccessError):
            conversation.workspace_detail(target=self.target(alien))
        with self.assertRaises(AccessError):
            conversation.workspace_acknowledge(unrelated.message_ids[-1].id, target=target)

    def test_independent_legacy_alias_notifications(self):
        conversation, orders, identity = self.pair()
        alias = self.website_order('ALIAS')
        order = self.env['ab_crm_website_order'].search([('reference', '=', 'ALIAS')])
        original = alias.message_ids
        self.close(alias, self.target(order), identity, kind='identity_bound')
        self.chat(conversation, order, identity=identity)
        items = [item for item in self.chatter_api.notifications(self.session_token)['items']
                 if item.get('website_target') == self.target(order)]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['conversation_id'], conversation.id)
        self.assertTrue(set(original.ids) <= set(items[0]['message_ids']))
        self.chatter_api.acknowledge_alert(self.session_token, conversation.id,
            items[0]['message_ids'], target=self.target(order))
        pending = self.chatter_api.notifications(self.session_token)['items']
        self.assertFalse(any(item.get('website_target') == self.target(order) for item in pending))


class TestIndependentChatsBrowser(TestIndependentChats, HttpCase):
    def browser(self, language, mobile=False):
        import json
        import os
        import subprocess
        self.env['res.lang']._activate_lang(language)
        self.staff.lang = language
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        conversation, orders, identity = self.pair()
        for order in orders:
            self.chat(conversation, order, identity=identity)
        support = self.chat(conversation, identity=identity)
        visitor = str(uuid4())
        guest = self.chat(conversation, identity=visitor, kind='visitor')
        self.close(conversation, guest['destination'], visitor, kind='session_ended', identity_kind='visitor')
        self.session = None
        self.authenticate(self.staff.login, self.staff.login)
        self.cr.flush()
        self.cr.clear()
        with self.allow_requests(all_requests=True):
            data = {'url': self.base_url(), 'cookies': self.opener.cookies.get_dict(),
                'token': self.session_token, 'employee': self.employee.id,
                'orders': [self.target(order) for order in orders], 'support': support['destination'],
                'order_alert': next(item for item in self.chatter_api.notifications(self.session_token)['items'] if item.get('website_target') == self.target(orders[0])),
                'guest_target': guest['destination'], 'mobile': mobile, 'language': language,
                'screenshot': '/tmp/independent-chats/' + language + ('-mobile' if mobile else '-desktop') + '.png'}
            result = subprocess.run(['node', '/opt/odoo19/worktrees/e_commerce/qa/independent_chats/browser.cjs'],
                input=json.dumps(data), text=True, capture_output=True, timeout=240,
                env=dict(os.environ, NODE_PATH='/tmp/chat-lifecycle-validation/browser-deps/node_modules'))
            self._wait_remaining_requests()
        if 'notification_components' in self._testMethodName:
            from pathlib import Path
            Path('/tmp/independent-chats/hoot-console.log').write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_independent_english_desktop(self):
        self.browser('en_US')

    def test_independent_english_mobile(self):
        self.browser('en_US', mobile=True)

    def test_independent_arabic_desktop(self):
        self.browser('ar_001')

    def test_independent_arabic_mobile(self):
        self.browser('ar_001', mobile=True)

    def test_independent_notification_components(self):
        import json
        import os
        import subprocess
        self.env['ir.asset'].create([
            {'name': 'Isolate unrelated POS scripts', 'bundle': 'web.assets_backend',
             'directive': 'remove', 'path': path}
            for path in (
                'ab_sales/static/src/pos/zz_pos_settings_extension_patch.js',
                'ab_sales/static/src/pos/zz_pos_replication_manual_patch.js',
                'ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js',
                'ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js',
                'ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js',
            )])
        self.session = None
        self.authenticate('admin', 'admin')
        self.cr.flush()
        self.cr.clear()
        with self.allow_requests(all_requests=True):
            result = subprocess.run(['node', '/opt/odoo19/worktrees/e_commerce/qa/independent_chats/hoot.cjs'],
                input=json.dumps({'url': self.base_url(), 'cookies': self.opener.cookies.get_dict()}),
                text=True, capture_output=True, timeout=200,
                env=dict(os.environ, NODE_PATH='/tmp/chat-lifecycle-validation/browser-deps/node_modules'))
            self._wait_remaining_requests()
        if 'notification_components' in self._testMethodName:
            from pathlib import Path
            Path('/tmp/independent-chats/hoot-console.log').write_text(result.stdout + result.stderr)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
