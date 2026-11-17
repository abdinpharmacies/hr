from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.addons.ab_crm_sales_workspace.tests.test_pos_handoff import TestPosHandoff
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION
from ..protocol import fingerprint


@tagged('post_install', '-at_install', 'website_pos')
class TestWebsitePos(TestPosHandoff):
    def test_general_handoff_rejects_forged_sessions(self):
        super().test_handoff_rejects_forged_sessions_and_direct_writes()

    def test_general_handoff_preserves_draft_customer(self):
        super().test_handoff_sessions_scope_and_exact_draft_customer()

    def test_general_handoff_rejects_foreign_drafts(self):
        super().test_cross_company_archived_and_other_employee_drafts_are_rejected()

    def test_manual_pos_handoff_preserves_website_evidence_and_grouping(self):
        source = str(uuid4())
        channel = self.env['ab_crm_channel'].create(
            {
                'name': 'Website',
                'code': 'website-pos-test',
                'provider': 'website',
                'branch_id': self.branch.id,
            }
        )
        account = self.env['ab_crm_messaging_account'].create(
            {
                'name': 'Website',
                'code': 'website-pos-test',
                'provider': 'website',
                'provider_account': source,
                'channel_id': channel.id,
                'branch_id': self.branch.id,
                'service_user_id': self.service.id,
                'legacy_worker_disabled': True,
                'enabled': True,
                'outgoing_enabled': True,
            }
        )
        event = {
            'version': 1,
            'source': source,
            'order_uuid': str(uuid4()),
            'event_uuid': str(uuid4()),
            'revision': 1,
            'kind': 'order',
            'payload': {
                'reference': 'WEB-POS',
                'customer': {
                    'name': 'Website Customer',
                    'phone': '01012345678',
                    'address': 'Website address',
                },
                'lines': [
                    {
                        'serial': '111',
                        'unit': 'box',
                        'name': 'Website item',
                        'quantity': 2,
                        'price': 20,
                        'discount': 0,
                        'subtotal': 40,
                        'total': 40,
                    }
                ],
                'currency': 'EGP',
                'total': 40,
                'notes': '',
                'payments': [],
                'fulfillment': {'state': 'sale'},
            },
        }
        event['payload']['lines'].append(
            {
                'serial': '',
                'unit': 'eplus_default',
                'name': 'Free delivery',
                'quantity': 1,
                'price': 0,
                'discount': 0,
                'subtotal': 0,
                'total': 0,
                'is_delivery': True,
            }
        )
        event['fingerprint'] = fingerprint(event)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        gateway.receive_website_event(account.code, source, event)
        order = self.env['ab_crm_website_order'].search(
            [('order_uuid', '=', event['order_uuid'])]
        )
        conversation = order.conversation_id.with_user(self.staff).with_context(
            ab_chatter_session_token=self.session_token
        )
        detail = conversation.workspace_detail()
        self.assertEqual(detail['website_order']['total'], 40)
        quotation_messages = [
            message for message in detail['messages'] if message.get('website_order')
        ]
        self.assertEqual(len(quotation_messages), 1)
        self.assertEqual(quotation_messages[0]['direction'], 'in')
        self.assertEqual(quotation_messages[0]['website_order']['reference'], 'WEB-POS')
        self.assertEqual(quotation_messages[0]['website_order']['revision'], 1)
        self.assertEqual(quotation_messages[0]['website_order']['lines'][0]['quantity'], 2)
        self.assertFalse(conversation.customer_id)
        inbox = conversation.workspace_customer_inbox(query='01012345678')
        self.assertEqual(inbox['items'][0]['id'], conversation.id)
        with self.assertRaises(UserError):
            conversation.action_identify()
        identified = conversation.action_identify(confirmed=True)
        contact_id = identified['customer_id']
        self.chatter_api.contact_save(self.session_token, {'name': 'Website Customer', 'phone': '01012345678',
                                                        'address': 'Saved contact address'},
                                      contact_id=contact_id)
        metadata = order.read(['handoff_id', 'progress', 'snapshot'])[0]
        handoff = self.chatter_api.pos_handoff_start(
            self.session_token, contact_id, conversation.id
        )
        self.assertEqual(
            self.chatter_api.pos_handoff_start(
                self.session_token, contact_id, conversation.id
            ),
            handoff,
        )
        pos = self._pos_session()
        with patch.object(
            type(self.env['ab_sales_pos_api']),
            '_require_pos_operation_session',
            return_value=pos,
        ):
            result = self.chatter_api.pos_handoff_prepare(
                self.session_token, handoff, pos.session_token, self.store.id
            )
            self.assertEqual(result['address'], 'Saved contact address')
            self.assertNotIn('website_lines', result)
            self.assertNotIn('website_order', result)
            self.assertEqual(order.read(['handoff_id', 'progress', 'snapshot'])[0], metadata)
            mutation = _MUTATION.set(True)
            try:
                order.write({'handoff_id': handoff, 'progress': 'prepared'})
            finally:
                _MUTATION.reset(mutation)
            self.chatter_api.pos_handoff_claim(
                self.session_token,
                handoff,
                pos.session_token,
                'website-draft',
                self.store.id,
            )
            draft = self.env['ab_sales_pos_draft_cache'].create({
                'pos_client_token': 'website-draft', 'user_id': self.staff.id,
                'employee_id': self.employee.id, 'store_id': self.store.id,
                'bill_json': {'crm_handoff_id': handoff, 'website_quotation': event['payload'],
                              'header': {'store_id': self.store.id},
                              'lines': [{'product_id': self.product.id, 'qty': 2}]},
            })
            saved_draft = deepcopy(draft.bill_json)
            historical = order.read(['handoff_id', 'progress', 'snapshot'])[0]
            self.chatter_api.pos_handoff_start(self.session_token, contact_id, conversation.id)
            self.assertEqual(order.read(['handoff_id', 'progress', 'snapshot'])[0], historical)
            revised = deepcopy(event)
            revised.update(event_uuid=str(uuid4()), revision=2)
            revised['payload']['total'] = 60
            revised['fingerprint'] = fingerprint(revised)
            gateway.receive_website_event(account.code, source, revised)
            prepared = self.chatter_api.pos_handoff_prepare(
                self.session_token, handoff, pos.session_token, self.store.id
            )
            self.assertEqual(prepared['draft_token'], 'website-draft')
            self.assertNotIn('website_lines', prepared)
            self.assertNotIn('website_order', prepared)
            self.assertEqual(prepared['address'], 'Saved contact address')
            self.assertEqual(order.handoff_id.id, handoff)
            self.assertEqual(order.progress, 'review')
            self.assertEqual(draft.bill_json, saved_draft)
        detail = conversation.workspace_detail()
        quotations = [
            message['website_order']
            for message in detail['messages']
            if message.get('website_order')
        ]
        self.assertEqual([quotation['total'] for quotation in quotations], [40, 60])
        with self.assertRaises(UserError):
            conversation.action_reply('Agent reply')
        self.assertFalse(conversation.message_ids.filtered(lambda m: m.direction == 'out'))
        self.assertFalse(self.env['ab_crm_messaging_operation'].search([
            ('account_id', '=', account.id)]))
        self.assertFalse(
            self.env['ab_sales_header'].search(
                [('pos_client_token', '=', 'website-draft')]
            )
        )

        sibling = deepcopy(event)
        sibling.update(order_uuid=str(uuid4()), event_uuid=str(uuid4()))
        sibling['payload']['reference'] = 'WEB-SECOND'
        sibling['fingerprint'] = fingerprint(sibling)
        gateway.receive_website_event(account.code, source, sibling)
        sibling_order = self.env['ab_crm_website_order'].search(
            [('order_uuid', '=', sibling['order_uuid'])]
        )
        unrelated = deepcopy(sibling)
        unrelated.update(order_uuid=str(uuid4()), event_uuid=str(uuid4()))
        unrelated['payload']['customer']['phone'] = '01099998888'
        unrelated['payload']['reference'] = 'WEB-OTHER-PHONE'
        unrelated['fingerprint'] = fingerprint(unrelated)
        gateway.receive_website_event(account.code, source, unrelated)
        sibling_actor = sibling_order.conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.assertEqual(sibling_actor.customer_id.id, contact_id)
        preview = sibling_actor.action_preview_customer_link(contact_id)
        sibling_actor.action_confirm_customer_link(contact_id, preview['fingerprint'])
        detail = conversation.workspace_detail()
        self.assertEqual(detail['name'], 'Website Customer')
        self.assertEqual(len(detail['streams']), 1)
        self.assertEqual({stream['id'] for stream in detail['streams']}, {conversation.id, sibling_order.conversation_id.id})
        sibling_conversation = sibling_order.conversation_id.with_user(self.staff).with_context(
            ab_chatter_session_token=self.session_token
        )
        sibling_detail = sibling_conversation.workspace_detail()
        self.assertEqual(sibling_detail['website_order']['reference'], 'WEB-SECOND')
        self.assertEqual(len(sibling_detail['streams']), 1)
        self.assertEqual(sibling_detail['name'], 'Website Customer')
        inbox = conversation.workspace_customer_inbox(query='01012345678')
        self.assertEqual(
            {item['id'] for item in inbox['items']},
            {sibling_conversation.id},
        )
        combined = conversation.workspace_channel(sibling_conversation.id)
        self.assertEqual(
            {message['website_order']['reference'] for message in combined['messages']
             if message.get('website_order')}, {'WEB-POS', 'WEB-SECOND'},
        )
        self.assertEqual(len(combined['messages']), len(detail['messages']))
        conversation.workspace_acknowledge(combined['messages'][-1]['id'])
        self.assertEqual(conversation.workspace_detail()['unread_count'], 0)
        other = self.env['ab_crm_website_order'].search([('order_uuid', '=', unrelated['order_uuid'])])
        with self.assertRaises(AccessError):
            conversation.workspace_channel(other.conversation_id.id)
        with self.assertRaises(AccessError):
            conversation.workspace_acknowledge(other.conversation_id.message_ids.id)

        searched = conversation.workspace_detail(query='WEB-SECOND')
        self.assertEqual(len(searched['messages']), 1)
        self.assertEqual(searched['messages'][0]['conversation_id'], sibling_conversation.id)
        for original, start in [(event, 3), (sibling, 2)]:
            for offset in range(26):
                chat = deepcopy(original)
                chat.update(event_uuid=str(uuid4()), revision=start + offset, kind='message')
                chat['payload'] = {'body': 'Customer text %s' % offset}
                chat['fingerprint'] = fingerprint(chat)
                gateway.receive_website_event(account.code, source, chat)
        first_page = conversation.workspace_detail()
        self.assertEqual(len(first_page['messages']), 50)
        self.assertTrue(first_page['has_older'])
        older = conversation.workspace_detail(before_id=first_page['messages'][0]['id'])
        all_ids = {message['id'] for message in first_page['messages'] + older['messages']}
        self.assertEqual(
            len(all_ids),
            len((conversation | sibling_conversation).message_ids),
        )
        self.assertFalse({message['id'] for message in first_page['messages']}
                         & {message['id'] for message in older['messages']})
