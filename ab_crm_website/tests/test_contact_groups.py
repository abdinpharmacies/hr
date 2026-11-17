
import json
from unittest.mock import patch

from uuid import uuid4

from odoo import fields
from odoo.exceptions import AccessError, UserError
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

    def website_order(self, reference='WEB-ONE', phone='01012345678'):
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

    def test_one_identity_and_no_website_reply(self):
        first = self.website_order()
        second = self.website_order('WEB-TWO', '+20 101 234 5678')
        self.assertEqual(first, second)
        orders = self.env['ab_crm_website_order'].search([('conversation_id', '=', first.id)], order='id')
        self.assertEqual(len(orders), 2)
        self.assertEqual(len(orders.website_customer_id), 1)
        detail = first.workspace_detail()
        self.assertEqual(len(detail['streams']), 1)
        self.assertEqual(len(first.workspace_customer_inbox()['items']), 1)
        self.assertFalse(detail['can_send'])
        self.assertNotIn('website_reply_order_id', detail)
        self.assertEqual({m['website_order']['reference'] for m in detail['messages']}, {'WEB-ONE', 'WEB-TWO'})
        self.assertTrue(all(not m['actions']['reply']['enabled'] for m in detail['messages']))
        for method, kwargs in [('action_reply', {}), ('website_action_reply', {'website_order_id': orders[0].id})]:
            with self.assertRaises(UserError):
                getattr(first, method)('No website reply', **kwargs)
        self.assertFalse(first.message_ids.filtered(lambda m: m.direction == 'out'))
        self.link(first)
        self.website_order('WEB-THREE')
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
        first = self.website_order()
        self.website_order('WEB-TWO')
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
        detail = first.workspace_detail()
        self.assertEqual(len(detail['messages']), 50)
        older = first.workspace_detail(before_id=detail['messages'][0]['id'])
        self.assertEqual(len({m['id'] for m in detail['messages'] + older['messages']}), 58)
        first.workspace_acknowledge(detail['messages'][-1]['id'])
        self.assertEqual(first.workspace_detail()['unread_count'], 0)

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
        first = self.website_order()
        self.website_order('WEB-TWO')
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
        self.website_order('WEB-THREE')
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
        self.assertEqual(len(first.workspace_detail()['messages']), 3)
        self.assertEqual(len(first.workspace_detail()['streams']), 1)
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


@tagged('post_install', '-at_install', 'website_customer_ui')
class TestWebsiteCustomerUI(TestWebsiteContactGroups, HttpCase):
    def _receive_only_browser(self, language):
        self.env['res.lang']._activate_lang(language)
        self.staff.lang = language
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        first = self.website_order()
        self.website_order('WEB-TWO')
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
                if (website.querySelector('.ab_composer, .ab_website_reply_destination, .ab_send'))
                    throw new Error('Website still exposes reply controls');
                if (website.querySelectorAll('.ab_website_order').length !== 2)
                    throw new Error('Grouped website invoices are missing');
                website.querySelector('.ab_message_menu').click();
                await new Promise(resolve => requestAnimationFrame(resolve));
                const replyLabel = odoo.loader.modules.get('@web/core/l10n/translation')._t('Reply');
                if ([...website.querySelectorAll('[role=menuitem]')].some(button => button.textContent.trim() === replyLabel))
                    throw new Error('Website message still offers Reply');
                const detail = await env.services.orm.call('ab_crm_conversation', 'workspace_detail', [[data.conversation]],
                    {context: {ab_chatter_session_token: data.token}});
                const expected = data.arabic ? 'الردود على الموقع معطلة.' : 'Website replies are disabled.';
                if (detail.can_send || detail.send_reason !== expected) throw new Error('Receive-only policy or translation failed');
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
