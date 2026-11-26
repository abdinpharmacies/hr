from unittest.mock import patch

from psycopg2.errors import SerializationFailure

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_chat_ux import TestChatUX


@tagged('post_install', '-at_install', 'website_reply_concurrency')
class TestWebsiteReplyConcurrency(TestChatUX):
    def test_polling_does_not_lock_reply_targets(self):
        conversation, orders, identity = self.pair()
        self.chat(conversation, orders[0], identity=identity)
        support = self.chat(conversation, identity=identity)
        targets = [self.target(orders[0]), support['destination']]
        conversation.workspace_detail(target=targets[0])
        conversation.workspace_detail(target=targets[1])
        with patch.object(type(orders), 'lock_for_update', side_effect=SerializationFailure()), \
                patch.object(type(self.env['ab_crm_website_session']), 'lock_for_update',
                             side_effect=SerializationFailure()):
            for target in targets:
                detail = conversation.workspace_detail(target=target)
                incoming = [item for item in detail['messages'] if item['direction'] == 'in']
                self.assertTrue(incoming)
                self.assertTrue(any(item['actions']['reply']['enabled'] for item in incoming))
                conversation.workspace_updates(target=target, visible_ids=[item['id'] for item in detail['messages']])
                with self.assertRaises(SerializationFailure):
                    conversation.website_action_reply('Still requires a lock', target=target)

    def test_preview_and_send_reject_closed_targets(self):
        conversation, orders, identity = self.pair()
        self.chat(conversation, orders[0], identity=identity)
        support = self.chat(conversation, identity=identity)
        for target in [self.target(orders[0]), support['destination']]:
            self.close(conversation, target, identity,
                       kind='order_dispatched' if target['kind'] == 'order' else 'session_ended')
            detail = conversation.workspace_detail(target=target)
            self.assertFalse(detail['can_send'])
            self.assertFalse(any(item['actions'].get('reply', {}).get('enabled') for item in detail['messages']))
            with self.assertRaises(UserError):
                conversation.website_action_reply('Cannot send', target=target)
