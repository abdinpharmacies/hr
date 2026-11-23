
import json
from unittest.mock import patch

from uuid import uuid4

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import HttpCase, tagged, no_retry
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.addons.ab_crm_sales_workspace.tests.test_workspace import TestWorkspace
from ..protocol import fingerprint


@tagged('post_install', '-at_install', 'website_contact_groups')
class TestWebsiteContactGroups(TestWorkspace):
    def setUp(self):
        super().setUp()
        self.website_channel = self.env['ab_crm_channel'].create({
            'name': 'Website', 'code': 'group-website', 'provider': 'website',
            'branch_id': self.branch.id,
        })
        self.website_account = self.env['ab_crm_messaging_account'].create({
            'name': 'Website', 'code': 'group-website', 'provider': 'website',
            'provider_account': str(uuid4()), 'channel_id': self.website_channel.id,
            'branch_id': self.branch.id, 'service_user_id': self.service.id,
            'enabled': True, 'legacy_worker_disabled': True, 'outgoing_enabled': True,
        })
        self.contact = self.chatter_api.contact_save(self.session_token, {
            'name': 'Canonical contact', 'phone': '01012345678', 'address': '',
        }, branch_id=self.branch.id)

    def website_order(self, reference='WEB-ONE', phone='01012345678', account_identity=None):
        event = {
            'version': 1, 'source': self.website_account.provider_account,
            'order_uuid': str(uuid4()), 'event_uuid': str(uuid4()),
            'revision': 1, 'kind': 'order', 'payload': {
                'reference': reference,
                'customer': {'name': 'Submitted name', 'phone': phone, 'address': 'Cairo'},
                'lines': [{'serial': '111', 'unit': 'box', 'name': 'Product',
                           'quantity': 1, 'price': 20, 'discount': 0, 'subtotal': 20, 'total': 20}],
                'currency': 'EGP', 'total': 20, 'notes': '', 'payments': [],
                'fulfillment': {'state': 'sale'},
            },
        }
        if account_identity:
            event['payload']['account_identity'] = account_identity
        event['fingerprint'] = fingerprint(event)
        self.env['ab_crm_messaging_api'].with_user(self.service).receive_website_event(
            self.website_account.code, self.website_account.provider_account, event)
        order = self.env['ab_crm_website_order'].search([('order_uuid', '=', event['order_uuid'])])
        return order.conversation_id.with_user(self.staff).with_context(
            ab_chatter_session_token=self.session_token)

    def link(self, conversation):
        preview = conversation.action_preview_customer_link(self.contact['id'])
        conversation.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        return preview

    def legacy_reply(self, conversation, body='Historical reply'):
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)], limit=1)
        mutation, internal = _MUTATION.set(True), _INTERNAL.set(True)
        try:
            message = self.env['ab_crm_message'].create({
                'conversation_id': conversation.id, 'branch_id': conversation.branch_id.id,
                'company_id': conversation.company_id.id, 'direction': 'out', 'body': body,
                'website_order_id': order.id, 'delivery_state': 'approved',
                'approved_by': self.staff.id, 'approved_at': fields.Datetime.now(),
            })
            self.env['ab_crm_messaging_operation'].create({
                'account_id': self.website_account.id, 'message_id': message.id, 'body': body,
                'destination': order.order_uuid, 'branch_id': order.branch_id.id,
                'company_id': order.company_id.id, 'approved_by': self.staff.id,
                'approved_at': fields.Datetime.now(),
            })
            return message
        finally:
            _INTERNAL.reset(internal)
            _MUTATION.reset(mutation)

    def test_one_identity_and_order_card_replies(self):
        identity = str(uuid4())
        first = self.website_order(account_identity=identity)
        second = self.website_order('WEB-TWO', '+20 101 234 5678', account_identity=identity)
        self.assertEqual(first, second)
        orders = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)], order='id')
        self.assertEqual(len(orders), 2)
        self.assertEqual(len(orders.website_customer_id), 1)
        detail = first.workspace_detail(target={'kind': 'order', 'uuid': orders[-1].order_uuid}, combine=True)
        self.assertEqual(len(detail['streams']), 1)
        self.assertEqual(len(first.workspace_customer_inbox()['items']), 1)
        self.assertTrue(detail['can_send'])
        self.assertEqual(detail['send_reason'], '')
        self.assertEqual(detail['website_reply_order_id'], orders[-1].id)
        self.assertEqual({m['website_order']['reference'] for m in detail['messages']}, {'WEB-ONE', 'WEB-TWO'})
        self.assertTrue(all(m['actions']['reply']['enabled'] for m in detail['messages']))
        with self.assertRaises(ValidationError):
            first.action_reply('Ambiguous order reply')
        for method, kwargs in [('website_action_reply', {'website_order_id': orders[-1].id}), ('website_action_reply', {'website_order_id': orders[0].id})]:
            reply = self.env['ab_crm_message'].browse(getattr(first, method)('Order reply', **kwargs))
            self.assertIn(reply.website_order_id, orders)
        self.link(first)
        self.website_order('WEB-THREE', account_identity=identity)
        self.assertEqual(first.customer_id.id, self.contact['id'])
        self.assertEqual(len(first.workspace_detail()['streams']), 1)

    def test_website_link_candidates_do_not_lock_account(self):
        first = self.website_order()
        with patch.object(type(self.website_account), 'lock_for_update',
                          side_effect=AssertionError('A read-only candidate preview must not lock the account')):
            self.assertTrue(first.action_customer_link_candidates()['phone'])
            with self.assertRaises(AccessError):
                first.with_user(self.other).action_customer_link_candidates()

    def test_separate_phones_sources_and_missing_phones(self):
        first = self.website_order()
        different = self.website_order('WEB-OTHER', '01199998888')
        missing = self.website_order('WEB-MISSING', '')
        missing_again = self.website_order('WEB-MISSING-AGAIN', '')
        self.assertEqual(len(first | different | missing | missing_again), 4)
        self.assertEqual(first._website_timeline_streams(), first)
        other_channel = self.env['ab_crm_channel'].create({
            'name': 'Other website', 'code': 'other-website', 'provider': 'website', 'branch_id': self.branch.id})
        self.website_account = self.env['ab_crm_messaging_account'].create({
            'name': 'Other website', 'code': 'other-website', 'provider': 'website',
            'provider_account': str(uuid4()), 'channel_id': other_channel.id,
            'branch_id': self.branch.id, 'service_user_id': self.service.id,
            'enabled': True, 'legacy_worker_disabled': True, 'outgoing_enabled': True})
        other = self.website_order('OTHER-SOURCE')
        self.assertNotEqual(first, other)
        self.assertNotEqual(first.customer_group_key, other.customer_group_key)
        with self.assertRaises(UserError):
            first.website_action_reply('Forged order', website_order_id=self.env['ab_crm_website_order'].search([
                ('conversation_id', '=', other.id)]).id)

    def test_order_messages_retries_and_pagination(self):
        identity = str(uuid4())
        first = self.website_order(account_identity=identity)
        self.website_order('WEB-TWO', account_identity=identity)
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)], order='id', limit=1)
        event = {'version': 1, 'source': self.website_account.provider_account,
                 'order_uuid': order.order_uuid, 'event_uuid': str(uuid4()), 'revision': 2,
                 'kind': 'message', 'payload': {'body': 'Original order message'}}
        event['fingerprint'] = fingerprint(event)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        for unused in range(2):
            gateway.receive_website_event(self.website_account.code, self.website_account.provider_account, event)
        incoming = first.message_ids.filtered(lambda m: m.body == 'Original order message')
        self.assertEqual(len(incoming), 1)
        self.assertEqual(incoming.website_order_id, order)
        for number in range(55):
            event.update(event_uuid=str(uuid4()), revision=number + 3, payload={'body': 'Incoming %s' % number})
            event['fingerprint'] = fingerprint(event)
            gateway.receive_website_event(self.website_account.code, self.website_account.provider_account, event)
        detail = first.workspace_detail(combine=True)
        self.assertEqual(len(detail['messages']), 50)
        older = first.workspace_detail(before_id=detail['messages'][0]['id'], combine=True)
        self.assertEqual(len({m['id'] for m in detail['messages'] + older['messages']}), 58)
        first.workspace_acknowledge(detail['messages'][-1]['id'], target=detail['messages'][-1]['website_target'], combine=True)
        self.assertEqual(first.workspace_detail(combine=True)['unread_count'], 0)

    def test_destination_immutable_and_access_enforced(self):
        first = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)])
        for denied in (first.with_user(self.other), first.with_user(self.service),
                       first.with_context(ab_chatter_session_token='forged')):
            with self.assertRaises(AccessError):
                denied.website_action_reply('Denied', website_order_id=order.id)
        with self.assertRaises(AccessError):
            first.with_user(self.other).workspace_detail()
        with self.assertRaises(AccessError):
            order.with_user(self.other).read(['snapshot'])
        with self.assertRaises(AccessError):
            order.website_customer_id.with_user(self.other).read(['identity_key'])
        with self.assertRaises(AccessError):
            first.write({'website_canonical_id': first.id})
        message = first.message_ids[:1]
        with self.assertRaises(AccessError):
            message.with_user(self.staff).write({'website_order_id': order.id})
        self.website_order('Newer incoming order')
        self.assertEqual(message.website_order_id, order)
        with self.assertRaises(UserError):
            first.website_action_reply('Invalid', website_order_id=True)

    def test_website_and_telegram_keep_separate_timelines_and_unlink(self):
        identity = str(uuid4())
        first = self.website_order(account_identity=identity)
        self.website_order('WEB-TWO', account_identity=identity)
        self.link(first)
        received = self.receive('Telegram content', owner='54321')
        telegram = self.env['ab_crm_message'].browse(received['message_id']).conversation_id.with_user(
            self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.link(telegram)
        self.assertEqual(len(first.workspace_detail()['streams']), 2)
        self.assertEqual(len(self.chatter_api.contact_accounts(self.session_token, self.contact['id'])['accounts']), 2)
        self.assertNotIn('Telegram content', [m['body'] for m in first.workspace_detail()['messages']])
        self.assertEqual(first.workspace_channel(telegram.id)['id'], telegram.id)
        self.assertEqual(telegram.workspace_channel(first.id)['id'], first.id)
        unlink = first.action_preview_customer_unlink(self.contact['id'])
        first.action_unlink_customer(self.contact['id'], unlink['fingerprint'])
        self.website_order('WEB-THREE', account_identity=identity)
        self.assertFalse(first.customer_id)
        self.assertEqual(len(first.workspace_detail()['streams']), 1)
        self.assertEqual(len(self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)])), 3)

    def test_website_scope_in_other_branch_and_company(self):
        first = self.website_order()
        for index, company in enumerate((self.env.company, self.env['res.company'].create({
                'name': 'Website other company', 'country_id': self.env.ref('base.eg').id}))):
            self.service.company_ids = [fields.Command.link(company.id)]
            branch = self.env['ab_crm_branch'].create({
                'name': 'Scoped website', 'code': 'scoped-web-%s' % index,
                'company_id': company.id, 'user_ids': [fields.Command.set(self.service.ids)]})
            channel = self.env['ab_crm_channel'].create({
                'name': 'Scoped website', 'code': 'scoped-web-%s' % index,
                'provider': 'website', 'branch_id': branch.id, 'company_id': company.id})
            self.website_account = self.env['ab_crm_messaging_account'].create({
                'name': 'Scoped website', 'code': 'scoped-web-%s' % index, 'provider': 'website',
                'provider_account': str(uuid4()), 'channel_id': channel.id, 'branch_id': branch.id,
                'company_id': company.id, 'service_user_id': self.service.id,
                'enabled': True, 'legacy_worker_disabled': True, 'outgoing_enabled': True})
            original_env = self.env
            try:
                self.env = self.env(context=dict(self.env.context, allowed_company_ids=company.ids))
                other = self.website_order('SCOPED')
            finally:
                self.env = original_env
            self.assertNotEqual(first.id, other.id)
            self.assertEqual(other.branch_id, branch)
            self.assertEqual(other.company_id, company)
            with self.assertRaises(UserError):
                first.website_action_reply('Forged scope', website_order_id=self.env['ab_crm_website_order'].sudo().search([
                    ('conversation_id', '=', other.id)]).id)

    def test_approvals_and_gateway_dispatch_are_disabled(self):
        self.website_account.outgoing_enabled = False
        first = self.website_order()
        draft = first.env['ab_crm_message'].create({
            'conversation_id': first.id, 'branch_id': first.branch_id.id,
            'company_id': first.company_id.id, 'direction': 'out', 'body': 'Blocked draft',
        })
        with self.assertRaises(UserError):
            draft.action_approve()
        self.assertEqual(draft.delivery_state, 'draft')
        self.assertFalse(draft.messaging_operation_ids)
        legacy = self.legacy_reply(first)
        operation = legacy.messaging_operation_ids
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        self.assertFalse(gateway.lease_outgoing(self.website_account.code, self.website_account.provider_account))
        self.assertFalse(gateway.authorize_send(self.website_account.code,
            self.website_account.provider_account, operation.token, operation.attempt, 'legacy-receipt'))
        self.assertEqual(operation.state, 'queued')
        self.assertEqual(self.website_account._queue_eligibility(first)[0], 'outgoing_disabled')

    def test_reconciliation_preview_alias_history_and_queued_destinations(self):
        first = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)])
        second = self.website_order('WEB-TWO', '01111112222')
        other_order = self.env['ab_crm_website_order'].search([('conversation_id', '=', second.id)])
        queued = self.legacy_reply(second, 'Keep queued destination')
        mutation = _MUTATION.set(True)
        try:
            other_order.write({'phone': order.phone, 'snapshot': dict(other_order.snapshot, customer=dict(other_order.snapshot['customer'], phone=order.phone))})
            other_order.write({'website_customer_id': False})
            order.write({'website_customer_id': False})
        finally:
            _MUTATION.reset(mutation)
        model = self.env['ab_crm_website_order']
        with self.assertRaises(AccessError):
            model.with_user(self.staff).website_reconciliation_preview(self.website_account.id)
        preview = model.website_reconciliation_preview(self.website_account.id)
        with self.assertRaises(UserError):
            model.website_reconciliation_apply(self.website_account.id, 'stale')
        model.website_reconciliation_apply(self.website_account.id, preview['fingerprint'])
        self.assertEqual(other_order.conversation_id, order.conversation_id)
        self.assertEqual(second.website_canonical_id.id, first.id)
        self.assertEqual(queued.messaging_operation_ids.destination, other_order.order_uuid)
        self.assertEqual(len(first.workspace_detail(combine=True)['messages']), 3)
        self.assertEqual(len(first.workspace_detail(combine=True)['streams']), 1)
        self.assertEqual(len(first.workspace_customer_inbox()['items']), 1)
        self.assertEqual(len(first.workspace_customer_inbox(query='01012345678')['items'][0]['streams']), 1)
        event = {'version': 1, 'source': self.website_account.provider_account,
                 'order_uuid': other_order.order_uuid, 'event_uuid': str(uuid4()), 'revision': 2,
                 'kind': 'message', 'payload': {'body': 'Routed from alias'}}
        event['fingerprint'] = fingerprint(event)
        self.env['ab_crm_messaging_api'].with_user(self.service).receive_website_event(
            self.website_account.code, self.website_account.provider_account, event)
        self.assertEqual(first.message_ids.filtered(lambda m: m.body == 'Routed from alias').website_order_id, other_order)
        self.assertFalse(second.message_ids.filtered(lambda m: m.body == 'Routed from alias'))

    def test_conflicting_saved_contacts_require_review(self):
        first = self.website_order()
        self.link(first)
        second = self.website_order('OTHER', '01111112222')
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', second.id)])
        token = _MUTATION.set(True)
        try:
            order.write({'phone': '01012345678', 'snapshot': dict(order.snapshot, customer=dict(order.snapshot['customer'], phone='01012345678')),
                         'website_customer_id': False})
        finally:
            _MUTATION.reset(token)
        model = self.env['ab_crm_website_order']
        preview = model.website_reconciliation_preview(self.website_account.id)
        self.assertTrue(preview['groups'][0]['requires_review'])
        model.website_reconciliation_apply(self.website_account.id, preview['fingerprint'])
        self.assertNotEqual(order.conversation_id.id, first.id)


    def chat(self, conversation, order=False, identity=None, session=None, kind='customer'):
        event = {'version': 2, 'source': self.website_account.provider_account,
                 'event_uuid': str(uuid4()), 'body': 'Customer question',
                 'identity': {'kind': kind, 'uuid': identity or str(uuid4())},
                 'destination': {'kind': 'order' if order else 'livechat',
                                 'uuid': order.order_uuid if order else session or str(uuid4())}}
        event['fingerprint'] = fingerprint(event)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        return event

    def test_dispatch_terminal_per_order_and_queue_revalidation(self):
        conversation = self.website_order(account_identity=str(uuid4()))
        identity = conversation.website_account_identity
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        self.website_order('SECOND', account_identity=identity)
        second = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id), ('id', '!=', order.id)])
        conversation.action_claim()
        event = self.chat(conversation, order, identity=identity)
        outgoing = self.env['ab_crm_message'].browse(conversation.website_action_reply('Queued before dispatch', website_order_id=order.id))
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        lifecycle = {'version': 3, 'source': self.website_account.provider_account,
            'event_uuid': str(uuid4()), 'kind': 'order_dispatched',
            'destination': {'kind': 'order', 'uuid': order.order_uuid},
            'identity': {'kind': 'customer', 'uuid': identity}}
        lifecycle['fingerprint'] = fingerprint(lifecycle)
        conversation._internal_write({'assigned_id': self.staff.id, 'state': 'progress'})
        assigned_before = conversation.assigned_id
        for index in range(2):
            gateway.receive_website_lifecycle(self.website_account.code, self.website_account.provider_account, lifecycle)
        self.assertTrue(order.chat_closed)
        self.assertFalse(second.chat_closed)
        self.assertEqual(conversation.assigned_id, assigned_before)
        information = conversation.workspace_detail(target={'kind': 'order', 'uuid': order.order_uuid})['messages']
        self.assertEqual(len([item for item in information if item['item_type'] == 'information']), 1)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        with self.assertRaises(UserError):
            conversation.website_action_reply('Late explicit reply', website_order_id=order.id)
        with self.assertRaises(ValidationError):
            self.chat(conversation, order, identity=identity)
        gateway.lease_outgoing(self.website_account.code, self.website_account.provider_account)
        self.assertEqual(outgoing.messaging_operation_ids.state, 'review')
        self.assertEqual(outgoing.messaging_operation_ids.review_note, 'This chat has ended. Your order has been sent for delivery.')
        message = self.env['ab_crm_message'].browse(conversation.website_action_reply('Other order', website_order_id=second.id))
        self.assertEqual(message.website_order_id, second)
        support = self.chat(conversation, identity=identity)
        detail = conversation.workspace_detail(target=support['destination'])
        self.assertTrue(any(m.get('website_origin_kind') == 'livechat' for m in detail['messages']))
        detail = conversation.workspace_detail(target={'kind': 'order', 'uuid': order.order_uuid})
        self.assertFalse(next(m for m in detail['messages'] if m['id'] == outgoing.id)['actions']['reply']['enabled'])

    def test_order_chat_rejects_another_bound_account(self):
        identity = str(uuid4())
        conversation = self.website_order(account_identity=identity)
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        with self.assertRaises(AccessError):
            self.chat(conversation, order, identity=str(uuid4()))
        event = self.chat(conversation, order, identity=identity)
        self.assertEqual(event['identity']['uuid'], order.account_identity)

    def test_chat_input_boundaries_and_literal_markup(self):
        conversation = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        for body in ['x' * 4095, 'س' * 4096, '<script>unsafe()</script> & Arabic text']:
            message = self.env['ab_crm_message'].browse(conversation.website_action_reply(body, website_order_id=order.id))
            self.assertEqual(message.body, body)
        for body in [' ', 'x' * 4097]:
            with self.assertRaises(UserError), self.env.cr.savepoint():
                conversation.website_action_reply(body, website_order_id=order.id)

    def test_customer_phone_without_orders_and_legacy_metadata(self):
        event = {'version': 2, 'source': self.website_account.provider_account, 'event_uuid': str(uuid4()),
            'destination': {'kind': 'livechat', 'uuid': str(uuid4())},
            'identity': {'kind': 'customer', 'uuid': str(uuid4()), 'name': 'Verified account', 'phone': '01011112222'},
            'body': 'First contact'}
        event['fingerprint'] = fingerprint(event)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        session = self.env['ab_crm_website_session'].search([('session_uuid', '=', event['destination']['uuid'])])
        self.assertEqual(session.conversation_id.website_phone, '01011112222')
        self.assertEqual(session.conversation_id._provider_display_name(), 'Verified account · 01011112222')
        event['event_uuid'] = str(uuid4())
        del event['identity']['phone']
        event['fingerprint'] = fingerprint(event)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        self.assertEqual(session.conversation_id.website_phone, '01011112222')
        event['event_uuid'] = str(uuid4())
        event['identity']['phone'] = ''
        event['fingerprint'] = fingerprint(event)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        self.assertEqual(session.conversation_id._provider_display_name(), 'Verified account')

    def test_v4_reply_arrow_freezes_order_and_rejects_forgery(self):
        from odoo.exceptions import ValidationError
        identity = str(uuid4())
        conversation = self.website_order(account_identity=identity)
        conversation.action_claim()
        first = conversation.message_ids.filtered(lambda message: message.direction == 'in')[:1]
        first_order = first.website_order_id
        self.website_order('SECOND', account_identity=identity)
        token = str(uuid4())
        selected = self.env['ab_crm_message'].browse(conversation.website_action_reply('Selected', reply_id=first.id, submission_uuid=token))
        self.assertEqual(conversation.website_action_reply('Selected', reply_id=first.id, submission_uuid=token), selected.id)
        with self.assertRaises(ValidationError):
            conversation.website_action_reply('Changed', reply_id=first.id, submission_uuid=token)
        self.assertEqual(selected.website_order_id, first_order)
        second_order = self.env['ab_crm_website_order'].search([('reference', '=', 'SECOND')])
        with self.assertRaises(ValidationError):
            conversation.website_action_reply('Ambiguous')
        latest = self.env['ab_crm_message'].browse(conversation.website_action_reply('Latest', website_order_id=second_order.id))
        self.assertNotEqual(latest.website_order_id, first_order)
        with self.assertRaises(AccessError):
            conversation.website_action_reply('Forged', reply_id=first.id, website_order_id=latest.website_order_id.id)
        foreign = self.website_order('OTHER', phone='01099999999')
        with self.assertRaises(AccessError):
            conversation.website_action_reply('Foreign', reply_id=foreign.message_ids[:1].id)
        with self.assertRaises(ValidationError):
            conversation.website_action_reply('', reply_id=first.id)

    def test_v4_media_requires_durable_bytes_and_deduplicates(self):
        import base64
        import hashlib
        from odoo.exceptions import ValidationError
        conversation = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)], limit=1)
        event = self.chat(conversation, order)
        event.update(version=4, body='', event_uuid=str(uuid4()))
        raw = b'%PDF-1.4 website test'
        item = {'id': 'file1', 'name': 'test.pdf', 'mimetype': 'application/pdf', 'kind': 'document',
                'size': len(raw), 'digest': hashlib.sha256(raw).hexdigest(), 'duration': 0}
        second = dict(item, id='file2', name='copy.pdf')
        event['attachments'] = [item, second]
        event['fingerprint'] = fingerprint(event)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        for descriptor in event['attachments']:
            self.env['ir.attachment'].sudo().create({'name': descriptor['name'], 'raw': raw,
                'res_model': self.website_account._name, 'res_id': self.website_account.id,
                'description': gateway._website_media_key(self.website_account, event['event_uuid'], descriptor)})
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        message = self.env['ab_crm_message'].search([('provider_reference', '=', event['event_uuid'])])
        self.assertEqual(len(message), 1)
        self.assertEqual(len(message.media_ids), 2)
        self.assertEqual(base64.b64decode(message.media_ids[:1].data), raw)
        conversation.action_claim()
        outgoing = self.env['ab_crm_message'].browse(conversation.website_action_reply('', reply_id=message.id,
            attachments=[{'name': item['name'], 'mimetype': item['mimetype'], 'kind': 'document', 'size': len(raw),
                          'data': base64.b64encode(raw).decode()} for item in event['attachments']]))
        self.assertEqual(len(outgoing.media_ids), 2)
        self.assertEqual(outgoing.website_order_id, order)
        self.assertNotIn('data', outgoing.messaging_operation_ids.content['media'][0])
        self.assertEqual(outgoing.messaging_operation_ids.content['media'][0]['digest'], hashlib.sha256(raw).hexdigest())

    def test_chat_order_destination_freezes_and_switches(self):
        conversation = self.website_order()
        first = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        conversation.action_claim()
        self.assertEqual(conversation._website_reply_target()[0], first)
        event = self.chat(conversation, first)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        self.assertEqual(len(conversation.message_ids), 2)
        message = self.env['ab_crm_message'].browse(conversation.action_reply('First reply'))
        self.assertEqual(message.website_order_id, first)
        self.website_order('Second order')
        second = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id), ('id', '!=', first.id)])
        self.chat(conversation, second)
        revision = {'version': 1, 'source': self.website_account.provider_account,
                    'event_uuid': str(uuid4()), 'order_uuid': first.order_uuid,
                    'revision': first.revision + 1, 'kind': 'order', 'payload': first.snapshot}
        revision['fingerprint'] = fingerprint(revision)
        gateway.receive_website_event(self.website_account.code, self.website_account.provider_account, revision)
        next_message = self.env['ab_crm_message'].browse(conversation.action_reply('Second reply'))
        self.assertEqual(next_message.website_order_id, first)
        chosen = self.env['ab_crm_message'].browse(conversation.website_action_reply('Choose first', website_order_id=first.id))
        self.assertEqual(chosen.website_order_id, first)
        operation = message.messaging_operation_ids
        self.assertEqual(operation.content['website_destination'], {'kind': 'order', 'uuid': first.order_uuid})
        leased = gateway.lease_outgoing(self.website_account.code, self.website_account.provider_account)
        self.assertEqual(leased['website_destination']['uuid'], first.order_uuid)
        gateway.acknowledge_receipt(self.website_account.code, self.website_account.provider_account,
                                   leased['token'], leased['attempt'], leased['lease'], 'chat-receipt')
        self.assertTrue(gateway.authorize_send(self.website_account.code, self.website_account.provider_account,
                                              leased['token'], leased['attempt'], 'chat-receipt'))
        self.website_account.outgoing_enabled = False
        self.assertFalse(gateway.authorize_send(self.website_account.code, self.website_account.provider_account,
                                               leased['token'], leased['attempt'], 'chat-receipt'))

    def test_chat_livechat_identity_boundaries_and_latest_session(self):
        orders = self.website_order()
        identity, session = str(uuid4()), str(uuid4())
        self.chat(orders, identity=identity, session=session)
        stream = self.env['ab_crm_conversation'].search([('channel_id', '=', self.website_channel.id), ('external_key', '=', identity)])
        self.assertNotEqual(stream, orders)
        second_session = str(uuid4())
        self.chat(orders, identity=identity, session=second_session)
        stream = stream.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        stream.action_claim()
        with self.assertRaises(ValidationError):
            stream.action_reply('Ambiguous support')
        message = self.env['ab_crm_message'].browse(stream.website_action_reply('General support', target={'kind': 'livechat', 'uuid': second_session}))
        self.assertEqual(message.messaging_operation_ids.content['website_destination'], {'kind': 'livechat', 'uuid': second_session})
        with self.assertRaises(AccessError):
            self.chat(orders, identity=str(uuid4()), session=session, kind='visitor')
        visitor_identity = str(uuid4())
        self.chat(orders, identity=visitor_identity, kind='visitor')
        visitor = self.env['ab_crm_conversation'].search([('channel_id', '=', self.website_channel.id), ('external_key', '=', visitor_identity)])
        self.assertNotEqual(visitor.customer_group_key, stream.customer_group_key)
        self.assertNotEqual(visitor.customer_group_key, orders.customer_group_key)

    def test_chat_rejects_forgery_and_scope(self):
        conversation = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        event = self.chat(conversation, order)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        with self.assertRaises(AccessError):
            gateway.with_user(self.other).receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        session = self.env['ab_crm_website_chat_event'].search([('event_uuid', '=', event['event_uuid'])])
        with self.assertRaises(AccessError):
            session.with_user(self.other).read(['envelope'])
        with self.assertRaises(AccessError):
            session.with_user(self.staff).write({'envelope': {}})
        with self.assertRaises(AccessError):
            conversation.website_action_reply('Forged', website_order_id=True)
        unknown = dict(event, event_uuid=str(uuid4()), destination={'kind': 'order', 'uuid': str(uuid4())})
        unknown['fingerprint'] = fingerprint(unknown)
        with self.assertRaises(AccessError):
            gateway.receive_website_chat(self.website_account.code, self.website_account.provider_account, unknown)


    def test_chat_sources_do_not_merge_even_after_contact_linking(self):
        original = self.website_order()
        identity, native_session = str(uuid4()), str(uuid4())
        self.chat(original, identity=identity, session=native_session)
        first = self.env['ab_crm_website_session'].search([('account_id', '=', self.website_account.id)])
        channel = self.env['ab_crm_channel'].create({
            'name': 'Second source', 'code': 'second-chat-source', 'provider': 'website', 'branch_id': self.branch.id})
        self.website_account = self.env['ab_crm_messaging_account'].create({
            'name': 'Second source', 'code': 'second-chat-source', 'provider': 'website',
            'provider_account': str(uuid4()), 'channel_id': channel.id, 'branch_id': self.branch.id,
            'service_user_id': self.service.id, 'enabled': True, 'legacy_worker_disabled': True,
            'outgoing_enabled': True})
        self.chat(original, identity=identity, session=native_session)
        second = self.env['ab_crm_website_session'].search([('account_id', '=', self.website_account.id)])
        self.assertNotEqual(first.conversation_id, second.conversation_id)
        for record in first | second:
            conversation = record.conversation_id.with_user(self.staff).with_context(
                ab_chatter_session_token=self.session_token)
            self.link(conversation)
        self.assertNotEqual(first.conversation_id.customer_group_key, second.conversation_id.customer_group_key)
        with self.assertRaises(AccessError):
            first.conversation_id.message_ids.with_user(self.other).read(['body'])

    def lifecycle(self, chat, kind, identity=None):
        event = {key: value for key, value in chat.items() if key not in ('body', 'fingerprint')}
        event.update(version=3, kind=kind, event_uuid=str(uuid4()))
        if identity:
            event['identity'] = {'kind': 'customer', 'uuid': identity}
        event['fingerprint'] = fingerprint(event)
        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        result = api.receive_website_lifecycle(self.website_account.code, self.website_account.provider_account, event)
        self.assertEqual(result['event_uuid'], event['event_uuid'])
        return event

    def test_visitor_end_closes_only_last_guest_session(self):
        seed = self.website_order()
        visitor_identity = str(uuid4())
        first = self.chat(seed, identity=visitor_identity, kind='visitor')
        second = self.chat(seed, identity=visitor_identity, kind='visitor')
        sessions = self.env['ab_crm_website_session'].search([('identity_uuid', '=', visitor_identity)])
        conversation = sessions.conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        conversation.action_claim()
        previous_state = conversation.state
        self.lifecycle(first, 'session_ended')
        self.assertEqual(conversation.state, previous_state)
        self.lifecycle(second, 'session_ended')
        self.assertEqual(conversation.state, 'closed')
        self.assertFalse(conversation.assigned_id)
        detail = conversation.workspace_detail()
        self.assertTrue(detail['website_session_ended'])
        self.assertFalse(detail['can_send'])
        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        rejected = dict(second, event_uuid=str(uuid4()))
        rejected['fingerprint'] = fingerprint(rejected)
        with self.assertRaises(ValidationError):
            api.receive_website_chat(self.website_account.code, self.website_account.provider_account, rejected)
        self.chat(seed, identity=visitor_identity, kind='visitor')
        self.assertEqual(conversation.state, 'new')
        self.assertFalse(conversation.workspace_detail()['website_session_ended'])

    def test_verified_website_name_and_customer_session_end(self):
        seed = self.website_order()
        event = self.chat(seed, identity=str(uuid4()))
        event = dict(event, event_uuid=str(uuid4()), identity=dict(event['identity'], name='Saved Website Customer'))
        event['fingerprint'] = fingerprint(event)
        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        api.receive_website_chat(self.website_account.code, self.website_account.provider_account, event)
        session = self.env['ab_crm_website_session'].search([('session_uuid', '=', event['destination']['uuid'])])
        conversation = session.conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.assertEqual(conversation.name, 'Saved Website Customer')
        self.assertEqual(conversation.workspace_detail()['name'], 'Saved Website Customer')
        legacy = dict(event, event_uuid=str(uuid4()), identity={key: value for key, value in event['identity'].items() if key != 'name'})
        legacy['fingerprint'] = fingerprint(legacy)
        api.receive_website_chat(self.website_account.code, self.website_account.provider_account, legacy)
        self.assertEqual(conversation.workspace_detail()['name'], 'Saved Website Customer')
        conversation.action_claim()
        previous_state = conversation.state
        self.lifecycle(event, 'session_ended')
        self.assertEqual(conversation.state, previous_state)
        invalid = dict(event, event_uuid=str(uuid4()), identity=dict(event['identity'], kind='visitor'))
        invalid['fingerprint'] = fingerprint(invalid)
        with self.assertRaises(ValidationError):
            api.receive_website_chat(self.website_account.code, self.website_account.provider_account, invalid)

    def test_recovery_guest_handoff_end_and_frozen_reply(self):
        order_conversation = self.website_order()
        account_identity = str(uuid4())
        signed = self.chat(order_conversation, identity=account_identity)
        customer_session = self.env['ab_crm_website_session'].search([('session_uuid', '=', signed['destination']['uuid'])])
        guest = self.chat(order_conversation, identity=str(uuid4()), kind='visitor')
        guest_session = self.env['ab_crm_website_session'].search([('session_uuid', '=', guest['destination']['uuid'])])
        original_identity = guest_session.identity_uuid
        binding = self.lifecycle(guest, 'identity_bound', account_identity)
        api = self.env['ab_crm_messaging_api'].with_user(self.service)
        api.receive_website_lifecycle(self.website_account.code, self.website_account.provider_account, binding)
        self.assertEqual(guest_session.identity_uuid, original_identity)
        self.assertEqual(guest_session.account_identity, account_identity)
        self.assertEqual(guest_session.conversation_id.website_canonical_id, customer_session.conversation_id)
        conversation = customer_session.conversation_id.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        conversation.action_claim()
        message = self.env['ab_crm_message'].browse(conversation.website_action_reply('Frozen target', website_session_id=guest_session.id))
        operation = message.messaging_operation_ids
        self.assertEqual(operation.content['website_destination']['uuid'], guest_session.session_uuid)
        ended = dict(guest, identity={'kind': 'customer', 'uuid': account_identity})
        self.lifecycle(ended, 'session_ended')
        self.assertTrue(guest_session.ended)
        self.assertFalse(api._website_operation_allowed(self.website_account, operation))
        with self.assertRaises(AccessError):
            conversation.website_action_reply('Do not redirect', website_session_id=guest_session.id)
        self.assertEqual(operation.content['website_destination']['uuid'], guest_session.session_uuid)
        with self.assertRaises(AccessError):
            guest_session.with_user(self.staff).write({'ended': False})
        with self.assertRaises(AccessError):
            guest_session.with_user(self.other).read(['identity_uuid'])

    def test_recovery_verified_identity_precedes_shared_phone(self):
        first = self.website_order()
        other_identity = str(uuid4())
        own_identity = str(uuid4())
        first_order = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)])
        precursor = {'version': 2, 'source': self.website_account.provider_account, 'destination': {'kind': 'order', 'uuid': first_order.order_uuid},
                     'identity': {'kind': 'customer', 'uuid': own_identity}}
        self.lifecycle(precursor, 'identity_bound', own_identity)
        self.chat(first, first_order, identity=own_identity)
        canonical = self.env['ab_crm_website_customer'].search([('identity_key', '=', 'account:' + own_identity)]).conversation_id
        self.assertEqual(canonical, first)
        second = self.website_order('Same phone other account')
        other_order = self.env['ab_crm_website_order'].search([('reference', '=', 'Same phone other account')])
        precursor['destination'] = {'kind': 'order', 'uuid': other_order.order_uuid}
        self.lifecycle(precursor, 'identity_bound', other_identity)
        self.chat(second, other_order, identity=other_identity)
        foreign = self.env['ab_crm_website_customer'].search([('identity_key', '=', 'account:' + other_identity)]).conversation_id
        self.assertNotEqual(canonical, foreign)
        floating = self.chat(first, identity=own_identity)
        session = self.env['ab_crm_website_session'].search([('session_uuid', '=', floating['destination']['uuid'])])
        self.assertEqual(session.conversation_id, canonical)
        self.assertNotEqual(canonical.customer_group_key, foreign.customer_group_key)
        self.assertEqual(first_order.account_identity, own_identity)
        staff = canonical.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        staff.action_claim()
        message = self.env['ab_crm_message'].browse(staff.website_action_reply('Owned order', website_order_id=first_order.id))
        self.assertEqual(message._website_destination(self.website_account)['uuid'], first_order.order_uuid)
        with self.assertRaises(AccessError):
            staff.website_action_reply('Foreign order', website_order_id=other_order.id)

    def test_recovery_explicit_same_token_retry(self):
        conversation = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        self.chat(conversation, order, kind='visitor')
        conversation.action_claim()
        message = self.env['ab_crm_message'].browse(conversation.action_reply('Same token retry'))
        operation = message.messaging_operation_ids
        original = operation.token, operation.body, operation.content, operation.destination
        operation._change({'state': 'review', 'error_code': 'unavailable'})
        with self.assertRaises(AccessError):
            operation.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token).action_website_retry()
        self.staff.group_ids += self.env.ref('ab_crm_core.group_manager')
        operation.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token).action_website_retry()
        self.assertEqual(operation.attempt, 2)
        self.assertEqual((operation.token, operation.body, operation.content, operation.destination), original)
        self.assertEqual(operation.state, 'queued')
        operation._change({'state': 'review', 'error_code': 'media'})
        operation.with_user(self.staff).with_context(ab_chatter_session_token=self.session_token).action_website_retry()
        self.assertEqual(operation.attempt, 3)
        self.assertEqual((operation.token, operation.body, operation.content, operation.destination), original)
        with self.assertRaises(AccessError):
            operation.with_user(self.other).action_website_retry()

    def test_recovery_saved_reply_language_permission_and_length(self):
        conversation = self.website_order()
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', conversation.id)])
        self.chat(conversation, order, kind='visitor')
        conversation.action_claim()
        templates = self.env['ab_crm_saved_reply']
        english = templates.create({'name': 'English library reply', 'body': 'Hello {{required}}',
            'language_code': 'en', 'branch_id': self.branch.id, 'company_id': self.env.company.id})
        arabic = templates.create({'name': 'Arabic library reply', 'body': 'Arabic template content',
            'language_code': 'ar', 'branch_id': self.branch.id, 'company_id': self.env.company.id})
        self.staff.lang = 'en_US'
        ids = [item['id'] for item in conversation.workspace_templates()['items']]
        self.assertIn(english.id, ids)
        self.assertNotIn(arabic.id, ids)
        self.staff.lang = 'ar_001'
        ids = [item['id'] for item in conversation.workspace_templates()['items']]
        self.assertIn(arabic.id, ids)
        self.assertNotIn(english.id, ids)
        with self.assertRaises(AccessError):
            conversation.save_template('Unauthorized edit', 'Body', template_id=english.id)
        with self.assertRaises(AccessError):
            english.with_user(self.other).read(['body'])
        with self.assertRaises(UserError):
            conversation.website_action_reply('x' * 4097)

    def test_recovery_handoff_can_reply_to_latest_alias(self):
        account_identity = str(uuid4())
        canonical = self.website_order(account_identity=account_identity)
        guest = self.chat(canonical, identity=str(uuid4()), kind='visitor')
        self.lifecycle(guest, 'identity_bound', account_identity)
        canonical.action_claim()
        self.assertTrue(canonical.workspace_detail()['can_send'])
        message = self.env['ab_crm_message'].browse(canonical.website_action_reply('Latest guest question', target=guest['destination']))
        self.assertEqual(message.website_session_id.session_uuid, guest['destination']['uuid'])
        self.assertEqual(message.messaging_operation_ids.content['website_destination']['uuid'], guest['destination']['uuid'])


@tagged('post_install', '-at_install', 'website_customer_ui')
class TestWebsiteCustomerUI(TestWebsiteContactGroups, HttpCase):
    def test_v4_binary_upload_download_scope_and_replay(self):
        from datetime import timedelta
        from urllib.parse import urlencode
        from odoo.http import Request
        from odoo.exceptions import ValidationError
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        conversation = self.website_order()
        conversation.action_claim()
        incoming = conversation.message_ids.filtered(lambda message: message.direction == 'in')[:1]
        self.session = None
        self.authenticate(self.staff.login, self.staff.login)
        raw = b'%PDF-1.4 binary website fixture'
        metadata = {'name': 'binary.pdf', 'mimetype': 'application/pdf', 'size': len(raw), 'kind': 'document', 'duration': 0}
        token = str(uuid4())
        def upload(session_token=None):
            return self.url_open('/crm/website/media/upload', data={
                'csrf_token': Request.csrf_token(self), 'conversation_id': conversation.id, 'token': session_token or self.session_token,
                'submission_uuid': token, 'position': 0, 'metadata': json.dumps(metadata),
                'target': json.dumps({'kind': 'order', 'uuid': incoming.website_order_id.order_uuid}),
            }, files={'ufile': ('binary.pdf', raw, 'application/pdf')})
        domain = [('res_model', '=', conversation._name), ('res_id', '=', conversation.id)]
        before = self.env['ir.attachment'].sudo().search_count(domain)
        self.assertEqual(upload('forged-employee-session-token').status_code, 403)
        self.assertEqual(self.env['ir.attachment'].sudo().search_count(domain), before)
        response = upload()
        self.assertEqual(response.status_code, 200, response.content)
        reference = response.json()
        self.assertEqual(upload().json(), reference)
        message_id = conversation.website_action_reply('', attachments=[reference], reply_id=incoming.id, submission_uuid=token)
        self.assertEqual(conversation.website_action_reply('', attachments=[reference], reply_id=incoming.id, submission_uuid=token), message_id)
        other = self.website_order('Other owner', phone='01077777777')
        with self.assertRaises(AccessError):
            other.website_action_reply('', attachments=[reference], reply_id=other.message_ids[:1].id)
        gateway = self.env['ab_crm_messaging_api'].with_user(self.service)
        operation = gateway.lease_outgoing(self.website_account.code, self.website_account.provider_account)
        self.assertNotIn('data', operation['media'][0])
        gateway.acknowledge_receipt(self.website_account.code, self.website_account.provider_account,
            operation['token'], operation['attempt'], operation['lease'], 'media-receipt')
        key = self.env['res.users.apikeys'].with_user(self.service)._generate('rpc', 'Binary media test', fields.Datetime.now() + timedelta(days=1))
        headers = {'Authorization': 'Bearer ' + key, 'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'localhost', 'X-Odoo-Database': self.env.cr.dbname}
        path = '/crm/website/v4/media/' + self.website_account.code + '/' + operation['token'] + '/' + operation['media'][0]['id']
        query = {'provider_account': self.website_account.provider_account, 'attempt': operation['attempt'], 'receipt': 'media-receipt'}
        self.opener.cookies.clear()
        downloaded = self.url_open(path + '?' + urlencode(query), headers=headers)
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, raw)
        self.assertEqual(self.url_open(path + '?' + urlencode(dict(query, receipt='forged')), headers=headers).status_code, 403)
        self.website_account.enabled = False
        self.assertEqual(self.url_open(path + '?' + urlencode(query), headers=headers).status_code, 403)

    def _receive_only_browser(self, language):
        self.website_account.outgoing_enabled = False
        self.env['res.lang']._activate_lang(language)
        self.staff.lang = language
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        identity = str(uuid4())
        first = self.website_order(account_identity=identity)
        self.website_order('WEB-TWO', account_identity=identity)
        self.link(first)
        received = self.receive('Telegram still supports replies', owner='54321')
        telegram = self.env['ab_crm_message'].browse(received['message_id']).conversation_id
        data = json.dumps({'conversation': first.id, 'telegram': telegram.id, 'token': self.session_token,
                           'employee_id': self.employee.id, 'arabic': language == 'ar_001'})
        self.session = None
        self.browser_js('/odoo?debug=assets', '''
            (async () => {
                const data = DATA;
                const env = odoo.__WOWL_DEBUG__.root.env;
                env.services.ab_chatter_session.set({token: data.token, employee_id: data.employee_id});
                const open = async id => {
                    await env.services.action.doAction('ab_crm_sales_workspace.action_workspace',
                        {additionalContext: {chatter_conversation_id: id}});
                    for (let i = 0; i < 100; i++) {
                        if (document.querySelector('.ab_chat[data-channel="' + (id === data.conversation ? 'website' : 'telegram') + '"]')) return;
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    throw new Error('Conversation did not open');
                };
                await open(data.conversation);
                const website = document.querySelector('.ab_chat[data-channel="website"]');
                if (website.querySelector('.ab_send:not(:disabled)'))
                    throw new Error('Website still exposes reply controls');
                if (website.querySelectorAll('.ab_website_order').length < 1)
                    throw new Error('Grouped website invoices are missing');
                website.querySelector('.ab_message_menu').click();
                await new Promise(resolve => requestAnimationFrame(resolve));
                const replyLabel = odoo.loader.modules.get('@web/core/l10n/translation')._t('Reply');
                if ([...website.querySelectorAll('[role=menuitem]')].some(button => button.textContent.trim() === replyLabel && !button.disabled))
                    throw new Error('Website message still offers Reply');
                const detail = await env.services.orm.call('ab_crm_conversation', 'workspace_detail', [[data.conversation]],
                    {context: {ab_chatter_session_token: data.token}});
                if (detail.can_send || detail.send_reason) throw new Error('Notification-only conversation shows a reply warning');
                await open(data.telegram);
                if (!document.querySelector('.ab_chat[data-channel="telegram"] .ab_composer_input'))
                    throw new Error('Telegram composer was removed');
                console.log('test successful');
            })().catch(error => console.error(error));
        '''.replace('DATA', data), ready="!!odoo.__WOWL_DEBUG__?.root", login=self.staff.login, timeout=90)

    @no_retry
    def test_receive_only_browser_english(self):
        self._receive_only_browser('en_US')

    @no_retry
    def test_receive_only_browser_arabic(self):
        self._receive_only_browser('ar_001')

    def _chat_browser(self, language, mobile=False):
        self.env['res.lang']._activate_lang(language)
        self.staff.lang = language
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        identity = str(uuid4())
        first = self.website_order(account_identity=identity)
        order = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)])
        order_chat = self.chat(first, order, identity=identity)
        self.website_order('Second selectable order', account_identity=identity)
        other = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id), ('id', '!=', order.id)])
        self.chat(first, other, identity=identity)
        floating = self.chat(first, identity=order_chat['identity']['uuid'], kind='visitor')
        self.lifecycle(floating, 'session_ended')
        floating_session = self.env['ab_crm_website_session'].search([('session_uuid', '=', floating['destination']['uuid'])])
        self.env['ab_crm_saved_reply'].with_context(lang=language).create({'name': 'Recovery saved reply',
            'body': 'Saved {{required}}', 'language_code': language, 'branch_id': self.branch.id, 'company_id': self.env.company.id})
        data = json.dumps({'floating_conversation': floating_session.conversation_id.id, 'conversation': first.id, 'token': self.session_token,
                           'employee_id': self.employee.id, 'first_order': other.id, 'arabic': language == 'ar_001'})
        self.session = None
        if mobile:
            self.browser_size = '390x844'
        self.browser_js('/odoo?debug=assets', '''
            (async () => {
                const data = DATA;
                const env = odoo.__WOWL_DEBUG__.root.env;
                env.services.ab_chatter_session.set({token: data.token, employee_id: data.employee_id});
                await env.services.action.doAction('ab_crm_sales_workspace.action_workspace',
                    {additionalContext: {chatter_conversation_id: data.floating_conversation}});
                let floatingRoot;
                for (let i = 0; i < 100; i++) {
                    floatingRoot = document.querySelector('.ab_chat[data-channel="website"]');
                    if (floatingRoot?.querySelector('.ab_message.in')) break;
                    await new Promise(resolve => setTimeout(resolve, 50));
                }
                if (!floatingRoot?.querySelector('.ab_message.in')) throw new Error('Floating chat fixture missing');
                if (!floatingRoot.querySelector('.ab_chat_header img[src="/ab_crm_website/static/src/img/abdin_bot.jpg"]')) throw new Error('Floating chat bot icon is missing');
                const endedText = data.arabic ? 'غادر الزائر المحادثة.' : 'The guest has left the conversation.';
                const notices = [...floatingRoot.querySelectorAll('.ab_timeline_information')].filter(element => element.textContent.trim() === endedText);
                if (notices.length !== 1) throw new Error('Guest leave notice must appear once in the active language');
                if (floatingRoot.querySelector('.ab_send:not(:disabled)')) throw new Error('Ended visitor chat must not offer a composer');
                await env.services.action.doAction('ab_crm_sales_workspace.action_workspace',
                    {additionalContext: {chatter_conversation_id: data.conversation}});
                let root;
                for (let i = 0; i < 100; i++) {
                    root = document.querySelector('.ab_chat[data-channel="website"]');
                    if (root?.querySelector('.ab_composer_input')) break;
                    await new Promise(resolve => setTimeout(resolve, 50));
                }
                if (root.querySelector('.ab_website_reply_destination')) throw new Error('Destination dropdown remains');
                const botImage = '/ab_crm_website/static/src/img/abdin_bot.jpg';
                const inboxIcon = document.querySelector('.ab_conversation .ab_channels .fa-globe');
                for (const icon of [inboxIcon]) {
                    if (!icon || !getComputedStyle(icon).backgroundImage.includes(botImage)) throw new Error('Website bot icon missing');
                    if (getComputedStyle(icon, '::before').content !== 'none') throw new Error('Website globe still visible');
                    const bounds = icon.getBoundingClientRect();
                    if (!bounds.width || !bounds.height || Math.abs(bounds.width - bounds.height) > 1) throw new Error('Website bot icon must remain square');
                }
                const avatar = new Image();
                avatar.src = botImage;
                await avatar.decode();
                if (!avatar.naturalWidth) throw new Error('Website bot image failed to load');
                const detail = await env.services.orm.call('ab_crm_conversation', 'workspace_detail', [[data.conversation]],
                    {context: {ab_chatter_session_token: data.token}});
                await new Promise(resolve => setTimeout(resolve, 5500));
                if (!root.querySelector('.ab_chat_header img[src="/ab_crm_website/static/src/img/callcenter_support.png"]')) throw new Error('Order conversation header image is missing after polling');
                if (root.querySelector('.ab_website_origin, .ab_website_reply_origin, .ab_message .ab_website_header_icon')) throw new Error('Source icons must appear only in the header');
                const target = detail.messages.find(message => message.website_order_id === data.first_order && message.direction === 'in');
                const message = root.querySelector('[data-message-id="' + target.id + '"]');
                if (root.querySelector('.ab_website_reply_arrow')) throw new Error('Website must use the standard message reply menu');
                const toggle = message.querySelector('.ab_message_menu');
                toggle.click();
                for (let i = 0; i < 50 && !document.querySelector('.ab_chatter_message_menu'); i++) await new Promise(resolve => setTimeout(resolve, 20));
                const replyLabel = data.arabic ? 'الرد' : 'Reply';
                const reply = [...document.querySelectorAll('.ab_chatter_message_menu [role="menuitem"]')].find(button => button.textContent.trim() === replyLabel);
                if (!reply || reply.disabled) throw new Error('Standard message reply action missing');
                reply.click();
                await new Promise(resolve => requestAnimationFrame(resolve));
                for (let i = 0; i < 50 && !root.querySelector('.ab_composer .ab_message_quote'); i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (!root.querySelector('.ab_composer .ab_message_quote')) throw new Error('Reply quote missing');
                const cancel = root.querySelector('.ab_composer .ab_message_quote > button.btn');
                cancel.click();
                for (let i = 0; i < 50 && root.querySelector('.ab_composer .ab_message_quote'); i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (root.querySelector('.ab_composer .ab_message_quote')) throw new Error('Cancel reply did not clear the quote');
                let reselectedReply;
                for (let i = 0; i < 10; i++) {
                    const currentMessage = root.querySelector('[data-message-id="' + target.id + '"]');
                    currentMessage.dispatchEvent(new MouseEvent('contextmenu', {bubbles: true, clientX: 100, clientY: 200}));
                    await new Promise(resolve => setTimeout(resolve, 100));
                    reselectedReply = [...document.querySelectorAll('.ab_chatter_message_menu [role="menuitem"]')].find(button => button.textContent.trim() === replyLabel);
                    if (reselectedReply) break;
                }
                if (!reselectedReply || reselectedReply.disabled) throw new Error('Reply menu did not reopen');
                reselectedReply.click();
                for (let i = 0; i < 50 && !root.querySelector('.ab_composer .ab_message_quote'); i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (!root.querySelector('.ab_composer .ab_message_quote')) throw new Error('Reply could not be selected again');
                const input = root.querySelector('.ab_composer_input');
                if (input.placeholder !== (data.arabic ? 'اكتب رسالة...' : 'Write a message...')) throw new Error('Composer translation missing');
                const savedLabel = data.arabic ? 'الردود المحفوظة' : 'Saved replies';
                if ([...root.querySelectorAll('.ab_composer_tools button')].some(button => button.textContent.trim() === savedLabel)) throw new Error('Saved replies must not be a standalone composer tool');
                const emojiToggle = root.querySelector('.ab_emoji_toggle');
                const attachToggle = root.querySelector('.ab_attach_toggle');
                if (!emojiToggle || !attachToggle) throw new Error('Telegram-style composer controls missing');
                if (!root.querySelector('.ab_website_composer input[type="file"]') || !root.querySelector('.ab_website_composer .fa-microphone')) throw new Error('Website media controls missing');
                emojiToggle.click();
                for (let i = 0; i < 50 && !root.querySelector('.ab_emoji_panel button'); i++) await new Promise(resolve => setTimeout(resolve, 20));
                const emojiButton = root.querySelector('.ab_emoji_panel button');
                if (!emojiButton) throw new Error('Emoji picker did not open');
                const emoji = emojiButton.textContent;
                emojiButton.click();
                for (let i = 0; i < 50 && input.value !== emoji; i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (input.value !== emoji) throw new Error('Emoji was not inserted into the website draft');
                attachToggle.click();
                for (let i = 0; i < 50 && !root.querySelector('.ab_attachment_menu'); i++) await new Promise(resolve => setTimeout(resolve, 20));
                const menu = root.querySelector('.ab_attachment_menu');
                if (!menu || menu.querySelectorAll('button').length !== 4) throw new Error('Website attachment menu must contain media, documents, music and saved replies');
                const saved = [...menu.querySelectorAll('button')].find(button => button.textContent.trim() === savedLabel);
                if (!saved) throw new Error('Saved replies missing from attachment menu');
                saved.click();
                let modal;
                for (let i = 0; i < 100; i++) {
                    modal = document.querySelector('.ab_template_dialog');
                    if (modal?.querySelector('.ab_template_item')) break;
                    await new Promise(resolve => setTimeout(resolve, 50));
                }
                const item = [...modal.querySelectorAll('.ab_template_item')].find(button => button.textContent.includes('Recovery saved reply'));
                if (!item) throw new Error('Configured template missing');
                item.click();
                await new Promise(resolve => requestAnimationFrame(resolve));
                const insert = [...modal.querySelectorAll('button')].find(button => button.textContent.trim() === (data.arabic ? 'إدراج في محرر الرسالة' : 'Insert into composer'));
                if (!insert?.disabled) throw new Error('Missing placeholder must block insertion');
                const parameter = modal.querySelector('.ab_template_editor input[required]');
                parameter.value = 'parameter'; parameter.dispatchEvent(new Event('input', {bubbles: true}));
                await new Promise(resolve => requestAnimationFrame(resolve));
                for (let i = 0; i < 50 && insert.disabled; i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (insert.disabled) throw new Error('Completed placeholder still blocked: ' + modal.textContent);
                insert.click();
                await new Promise(resolve => requestAnimationFrame(resolve));
                for (let i = 0; i < 50 && input.value !== 'Saved parameter'; i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (input.value !== 'Saved parameter') throw new Error('Template was not inserted as editable draft');
                if (root.querySelector('.ab_message.out')?.textContent.includes('Saved parameter')) throw new Error('Template sent automatically');
                const {SalesWorkspace} = odoo.loader.modules.get('@ab_crm_sales_workspace/workspace');
                let delayed;
                const fake = {state: {detail: {id: 1, provider: 'website'}, reply: 'new draft'}, navigationVersion: 1,
                    call() {}, rememberDraft() {}, dialog: {add(component, props) {delayed = props.insert;}}};
                SalesWorkspace.prototype.templates.call(fake);
                fake.navigationVersion = 2; fake.state.detail = {id: 2, provider: 'website'};
                delayed('Wrong conversation');
                if (fake.state.reply !== 'new draft') throw new Error('Delayed template crossed navigation');
                SalesWorkspace.prototype.templates.call(fake);
                delayed('x'.repeat(4097));
                if (fake.state.reply !== 'new draft' || !fake.state.error) throw new Error('Overlong template expansion was accepted');
                const transfer = new DataTransfer();
                transfer.items.add(new File(['%PDF-1.4 browser media'], 'browser.pdf', {type: 'application/pdf'}));
                transfer.items.add(new File([Uint8Array.from(atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6tAAAAABJRU5ErkJggg=='), character => character.charCodeAt(0))], 'browser.png', {type: 'image/png'}));
                const upload = root.querySelector('.ab_website_composer input[type="file"]');
                upload.files = transfer.files;
                upload.dispatchEvent(new Event('change', {bubbles: true}));
                for (let i = 0; i < 100 && root.querySelectorAll('.ab_attachment_drafts > div').length !== 2; i++) await new Promise(resolve => setTimeout(resolve, 20));
                if (root.querySelectorAll('.ab_attachment_drafts > div').length !== 2) throw new Error('Multiple attachment drafts missing');
                input.value = 'Browser destination test';
                input.dispatchEvent(new Event('input', {bubbles: true}));
                await new Promise(resolve => requestAnimationFrame(resolve));
                let button;
                for (let i = 0; i < 100; i++) {
                    root = document.querySelector('.ab_chat[data-channel="website"]');
                    button = root.querySelector('.ab_send');
                    if (!button.disabled) break;
                    await new Promise(resolve => setTimeout(resolve, 50));
                }
                if (button.disabled) throw new Error('Send disabled: ' + button.title);
                button.click();
                for (let i = 0; i < 100; i++) {
                    root = document.querySelector('.ab_chat[data-channel="website"]');
                    if (root.textContent.includes('Browser destination test')) {
                        console.log('test successful');
                        return;
                    }
                    await new Promise(resolve => setTimeout(resolve, 50));
                }
                throw new Error('Reply was not queued');
            })().catch(error => console.error(error));
        '''.replace('DATA', data), ready="!!odoo.__WOWL_DEBUG__?.root", login=self.staff.login, timeout=90)
        reply = self.env['ab_crm_message'].search([('conversation_id', '=', first.id), ('body', '=', 'Browser destination test')])
        self.assertEqual(reply.website_order_id, other)
        self.assertEqual(len(reply.media_ids), 2)
        self.assertTrue(all('data' not in item for item in reply.messaging_operation_ids.content['media']))

    @no_retry
    def test_chat_browser_english(self):
        self._chat_browser('en_US')

    @no_retry
    def test_chat_browser_arabic_mobile(self):
        self._chat_browser('ar_001', mobile=True)
