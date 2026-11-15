import json

from unittest.mock import patch
from uuid import uuid4

from odoo import fields
from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, no_retry, tagged
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

    def test_group_link_all_orders_beyond_page_and_repeat_noop(self):
        first = self.website_order()
        second = self.website_order('WEB-TWO')
        token = _INTERNAL.set(True)
        try:
            (first | second).sudo().message_ids.write({
                'original_timestamp': fields.Datetime.subtract(fields.Datetime.now(), days=1)})
        finally:
            _INTERNAL.reset(token)
        for number in range(55):
            first.action_reply('Reply %s' % number)
        detail = first.workspace_detail()
        self.assertEqual(len(detail['messages']), 50)
        self.assertNotIn(second.message_ids.id, [message['id'] for message in detail['messages']])
        evidence = (first | second).message_ids.read(['body', 'conversation_id', 'provider_reference'])
        preview = self.link(first)
        self.assertEqual(set(preview['conversation_ids']), {first.id, second.id})
        self.assertEqual(preview['conversation_count'], 2)
        self.assertEqual((first | second).customer_id.id, self.contact['id'])
        self.assertEqual(first.customer_group_key, second.customer_group_key)
        self.assertEqual(first.workspace_detail()['name'], 'Canonical contact')
        self.assertEqual((first | second).message_ids.read(['body', 'conversation_id', 'provider_reference']), evidence)
        audits = self.env['ab_crm_workspace_audit'].search([
            ('conversation_id', 'in', [first.id, second.id]), ('action', '=', 'review_customer_link')])
        self.assertEqual(len(audits), 2)
        self.link(first)
        self.assertEqual(self.env['ab_crm_workspace_audit'].search_count([
            ('conversation_id', 'in', [first.id, second.id]), ('action', '=', 'review_customer_link')]), 2)
        self.assertEqual(len(first.workspace_customer_inbox()['items']), 1)

    def test_arrival_and_identity_changes_reject_stale_preview(self):
        first = self.website_order()
        preview = first.action_preview_customer_link(self.contact['id'])
        second = self.website_order('WEB-TWO')
        with self.assertRaises(UserError):
            first.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        self.assertFalse((first | second).customer_id)
        self.link(first)
        preview = first.action_preview_customer_link(self.contact['id'])
        from odoo.addons.ab_crm_sales_workspace.models.workspace import _WORKSPACE
        token = _WORKSPACE.set(True)
        try:
            identity = self.env['ab_crm_identity'].search([('external_key', '=', second.external_key)])
            identity.write({'active': False})
        finally:
            _WORKSPACE.reset(token)
        with self.assertRaises(UserError):
            first.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        self.assertFalse(identity.active)

    def test_group_access_and_atomic_rollback(self):
        first, second = self.website_order(), self.website_order('WEB-TWO')
        preview = first.action_preview_customer_link(self.contact['id'])
        for denied in (first.with_user(self.other), first.with_user(self.service),
                       first.with_context(ab_chatter_session_token='forged')):
            with self.assertRaises(AccessError):
                denied.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        with self.assertRaises(AccessError):
            first.write({'customer_id': self.contact['id']})
        foreign = self.env['ab_crm_branch'].create({'name': 'Foreign', 'code': 'group-foreign'})
        customer = self.env['ab_crm_customer'].create({'name': 'Foreign', 'branch_id': foreign.id})
        with self.assertRaises(AccessError):
            first.action_preview_customer_link(customer.id)
        company = self.env['res.company'].create({'name': 'Foreign group company'})
        with self.assertRaises(AccessError):
            first.with_context(allowed_company_ids=company.ids).action_preview_customer_link(self.contact['id'])
        foreign_channel = self.env['ab_crm_channel'].create({
            'name': 'Foreign', 'code': 'group-foreign', 'provider': 'website', 'branch_id': foreign.id})
        foreign_stream = self.env['ab_crm_conversation'].create({
            'name': 'Foreign', 'channel_id': foreign_channel.id, 'external_key': str(uuid4()), 'branch_id': foreign.id})
        with patch.object(type(first), '_customer_link_group', return_value=(first | foreign_stream.with_env(first.env))):
            with self.assertRaises(AccessError):
                first.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        original = type(first)._apply_customer_link
        def fail_second(record, *args):
            if record.id == second.id:
                raise UserError('Injected failure')
            return original(record, *args)
        with patch.object(type(first), '_apply_customer_link', fail_second):
            with self.assertRaises(UserError):
                first.action_confirm_customer_link(self.contact['id'], preview['fingerprint'])
        self.assertFalse((first | second).customer_id)
        self.assertFalse(self.env['ab_crm_identity'].search([('external_key', 'in', [first.external_key, second.external_key])]))
        self.assertFalse(self.env['ab_crm_workspace_audit'].search([
            ('conversation_id', 'in', [first.id, second.id]), ('action', '=', 'review_customer_link')]))

    def test_linked_and_unlinked_phone_groups_stay_separate(self):
        first = self.website_order()
        self.link(first)
        second = self.website_order('WEB-TWO')
        self.assertFalse(second.customer_id)
        self.assertNotEqual(first.customer_group_key, second.customer_group_key)
        self.assertEqual(second._customer_link_group().ids, second.ids)
        with self.assertRaises(AccessError):
            first.workspace_channel(second.id)
        self.link(second)
        self.assertEqual(first.customer_group_key, second.customer_group_key)
        for stream in (first, second):
            stream.action_reply('Reply to original order')
            operation = self.env['ab_crm_messaging_operation'].search([
                ('message_id.conversation_id', '=', stream.id)], order='id desc', limit=1)
            self.assertEqual(operation.destination, stream.external_key)
        detail = first.workspace_channel(second.id)
        self.assertEqual({message['website_order']['reference'] for message in detail['messages']
                          if message.get('website_order')}, {'WEB-ONE', 'WEB-TWO'})
        unlink = first.action_preview_customer_unlink(self.contact['id'])
        first.action_unlink_customer(self.contact['id'], unlink['fingerprint'])
        first.workspace_customer_inbox()
        self.assertFalse((first | second).customer_id)
        self.assertTrue(all(not identity.active for identity in self.env['ab_crm_identity'].with_context(
            active_test=False).search([('external_key', 'in', [first.external_key, second.external_key])])) )

    def test_cross_channel_navigation_and_website_timeline(self):
        first, second = self.website_order(), self.website_order('WEB-TWO')
        self.link(first)
        received = self.receive('Telegram content', owner='54321')
        telegram = self.env['ab_crm_message'].browse(received['message_id']).conversation_id.with_user(
            self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.link(telegram)
        extra = self.env['ab_crm_conversation']
        channel_field = self.env['ab_crm_channel']._fields['provider']
        account_field = self.env['ab_crm_messaging_account']._fields['provider']
        with patch.object(channel_field, '_selection', dict(channel_field._selection, future_test='Future test')), patch.object(
                account_field, '_selection', dict(account_field._selection, whatsapp='WhatsApp', future_test='Future test')):
            for provider in ('whatsapp', 'future_test'):
                channel = self.env['ab_crm_channel'].create({
                    'name': provider, 'code': 'group-' + provider, 'provider': provider,
                    'branch_id': self.branch.id})
                self.env['ab_crm_messaging_account'].create({
                    'name': provider, 'code': 'group-' + provider, 'provider': provider,
                    'provider_account': str(uuid4()), 'channel_id': channel.id,
                    'branch_id': self.branch.id, 'service_user_id': self.service.id,
                    'enabled': True, 'legacy_worker_disabled': True})
                stream = self.env['ab_crm_conversation'].create({
                    'name': provider, 'channel_id': channel.id, 'external_key': '201099998888',
                    'branch_id': self.branch.id}).with_user(self.staff).with_context(
                        ab_chatter_session_token=self.session_token)
                self.assertFalse(stream._auto_link_matching_customer())
                with self.assertRaises(AccessError):
                    stream.write({'customer_id': self.contact['id']})
                self.link(stream)
                extra |= stream.with_env(self.env)
            detail = first.workspace_detail()
            self.assertEqual({stream['id'] for stream in detail['streams']},
                             {first.id, second.id, telegram.id, *extra.ids})
            for stream in extra:
                switched = first.workspace_channel(stream.id)
                self.assertEqual(switched['id'], stream.id)
                self.assertEqual({entry['display_destination'] for entry in switched['streams']
                                  if entry['provider'] == 'website'}, {'WEB-ONE', 'WEB-TWO'})

        self.assertNotIn('Telegram content', [message['body'] for message in detail['messages']])
        self.assertEqual(first.workspace_channel(telegram.id)['id'], telegram.id)
        self.assertEqual(telegram.workspace_channel(first.id)['id'], first.id)
        self.assertEqual(len(first.workspace_customer_inbox()['items']), 1)
        self.assertEqual(self.env['ab_crm_website_order'].search([
            ('conversation_id', 'in', [first.id, second.id])]).mapped('snapshot')[0]['customer']['name'], 'Submitted name')

    def test_conflict_requires_manager_and_explicit_resolution(self):
        first = self.website_order()
        self.link(first)
        other = self.chatter_api.contact_save(self.session_token, {
            'name': 'Different contact', 'phone': '01199998888', 'address': '',
        }, branch_id=self.branch.id)
        with self.assertRaises(AccessError):
            first.action_preview_customer_link(other['id'])
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_crm_core.group_manager').id)]
        preview = first.action_preview_customer_link(other['id'])
        self.assertTrue(preview['conflict'])
        with self.assertRaises(UserError):
            first.action_confirm_customer_link(other['id'], preview['fingerprint'])
        first.action_confirm_customer_link(other['id'], preview['fingerprint'], resolve_conflict=True)
        self.assertEqual(first.customer_id.id, other['id'])
        identity = self.env['ab_crm_identity'].search([('external_key', '=', first.external_key)])
        self.assertEqual(identity.customer_id.id, other['id'])
        self.staff.group_ids = [fields.Command.link(self.env.ref('base.group_system').id)]
        preview = first.action_preview_customer_link(self.contact['id'])
        first.action_confirm_customer_link(self.contact['id'], preview['fingerprint'], resolve_conflict=True)
        self.assertEqual(first.customer_id.id, self.contact['id'])

    def test_rollout_is_bounded_and_admin_only(self):
        first, second = self.website_order(), self.website_order('WEB-TWO')
        self.link(first)
        with self.assertRaises(AccessError):
            first._recompute_website_customer_groups()
        before = first.customer_group_key
        ids = self.env['ab_crm_conversation']._recompute_website_customer_groups(limit=1, after_id=first.id - 1)
        self.assertEqual(ids, first.ids)
        self.assertEqual(first.customer_group_key, before)


@tagged('post_install', '-at_install', 'website_contact_groups_ui')
class TestWebsiteContactGroupUI(TestWebsiteContactGroups, HttpCase):
    def _browser_group_link(self, lang):
        self.staff.lang = lang
        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        first, second = self.website_order(), self.website_order('WEB-TWO')
        initial = first.workspace_detail()
        values = json.dumps({'first': first.id, 'second': second.id, 'contact': self.contact,
                             'token': self.session_token, 'initial': initial, 'arabic': lang == 'ar_001'})
        self.session = None
        self.browser_js('/odoo?debug=assets', '''
            (async () => {
                const data = DATA;
                const env = odoo.__WOWL_DEBUG__.root.env;
                const call = (model, method, args = [], kwargs = {}) => env.services.orm.call(model, method, args,
                    {...kwargs, context: {ab_chatter_session_token: data.token}});
                const {ChatterContacts} = odoo.loader.modules.get('@ab_crm_sales_workspace/contacts');
                const {SalesWorkspace} = odoo.loader.modules.get('@ab_crm_sales_workspace/workspace');
                const wait = async predicate => {
                    for (let i = 0; i < 100; i++) {
                        if (predicate()) return;
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    throw new Error('Timed out waiting for linking dialog');
                };
                const workspace = {
                    state: {token: data.token, detail: data.initial, reply: 'Keep this draft', attachments: [],
                            inboxQuery: '', firstUnread: false, phone: ''},
                    props: {}, navigationVersion: 1, call, refreshContacts: async () => {},
                    loadCustomerInbox: async () => call('ab_crm_conversation', 'workspace_customer_inbox'),
                };
                let saved = false;
                env.services.dialog.add(ChatterContacts, {
                    mode: 'link', channel: 'website', token: data.token, conversationId: data.first,
                    branchId: data.contact.branch_id, initial: data.contact, call,
                    onSaved: async () => {
                        await SalesWorkspace.prototype.refresh.call(workspace);
                        saved = true;
                    },
                });
                await wait(() => document.querySelector('.ab_chatter_contacts')?.textContent.includes(
                    data.arabic ? 'المحادثات المتأثرة' : 'Affected conversations'));
                const dialog = document.querySelector('.ab_chatter_contact_dialog');
                const labels = data.arabic ? ['المحادثات المتأثرة', 'جهة الاتصال الحالية', 'جهة اتصال الهوية'] :
                    ['Affected conversations', 'Current contact', 'Identity contact'];
                if (!labels.every(label => dialog.textContent.includes(label))) throw new Error('Link review labels missing');
                if (!dialog.textContent.includes('2') || !dialog.textContent.includes(data.initial.streams[0].destination) ||
                    !dialog.textContent.includes(data.initial.streams[1].destination)) throw new Error('Incomplete group preview');
                if (data.arabic && getComputedStyle(dialog.querySelector('.ab_chatter_contacts')).direction !== 'rtl')
                    throw new Error('Arabic dialog direction failed');
                const save = [...dialog.querySelectorAll('button')].find(button =>
                    button.textContent.trim() === (data.arabic ? 'حفظ' : 'Save'));
                if (!save) throw new Error('Save button missing');
                save.click();
                await wait(() => saved);
                if (workspace.state.reply !== 'Keep this draft' || workspace.state.detail.id !== data.first)
                    throw new Error('Refresh lost selection or draft');
                if (workspace.state.inbox.length !== 1 || workspace.state.inbox[0].name !== 'Canonical contact')
                    throw new Error('Canonical Inbox entry missing or duplicated');
                if (workspace.state.detail.name !== 'Canonical contact' || workspace.state.detail.streams.length !== 2)
                    throw new Error('Linked detail failed');
                const switched = await call('ab_crm_conversation', 'workspace_channel', [[data.first], data.second]);
                if (switched.id !== data.second || switched.messages.filter(message => message.website_order).length !== 2)
                    throw new Error('Website channel switching lost invoices');
                if (switched.unread_count !== data.initial.unread_count) throw new Error('Unread count changed on linking');
                console.log('test successful');
            })().catch(error => console.error(error));
        '''.replace('DATA', values), ready="!!odoo.__WOWL_DEBUG__?.root && !!document.querySelector('.o_ab_sales_dashboard_actions')", login=self.staff.login, timeout=90)

    @no_retry
    def test_group_link_browser_english(self):
        self._browser_group_link('en_US')

    @no_retry
    def test_group_link_browser_arabic(self):
        self.env['res.lang']._activate_lang('ar_001')
        self._browser_group_link('ar_001')

    @no_retry
    def test_website_header_opens_shared_timeline_and_restores_destinations(self):
        from lxml import etree
        from odoo.tools import file_path

        self.staff.group_ids = [fields.Command.link(self.env.ref('ab_store.ab_login_from_anywhere').id)]
        self.staff.lang = 'en_US'
        first, second = self.website_order(), self.website_order('WEB-TWO')
        self.link(first)
        received = self.receive('Telegram content', owner='54321')
        telegram = self.env['ab_crm_message'].browse(received['message_id']).conversation_id.with_user(
            self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.link(telegram)
        account_field = self.env['ab_crm_messaging_account']._fields['provider']
        channel = self.env['ab_crm_channel'].create({
            'name': 'WhatsApp', 'code': 'header-wa', 'provider': 'whatsapp', 'branch_id': self.branch.id})
        with patch.object(account_field, '_selection', dict(account_field._selection, whatsapp='WhatsApp')):
            self.env['ab_crm_messaging_account'].create({
                'name': 'WhatsApp', 'code': 'header-wa', 'provider': 'whatsapp',
                'provider_account': str(uuid4()), 'channel_id': channel.id, 'branch_id': self.branch.id,
                'service_user_id': self.service.id, 'enabled': True, 'legacy_worker_disabled': True})
        whatsapp = self.env['ab_crm_conversation'].create({
            'name': 'WhatsApp', 'channel_id': channel.id, 'external_key': '201099998888',
            'branch_id': self.branch.id}).with_user(self.staff).with_context(ab_chatter_session_token=self.session_token)
        self.link(whatsapp)
        document = etree.parse(file_path('ab_crm_sales_workspace/static/src/workspace.xml'))
        navigation = etree.tostring(document.xpath('//nav[@class="ab_channel_navigation"]')[0], encoding='unicode')
        values = json.dumps({'first': first.id, 'second': second.id, 'telegram': telegram.id,
                             'whatsapp': whatsapp.id, 'token': self.session_token,
                             'initial': telegram.workspace_detail(), 'inbox': first.workspace_customer_inbox()['items'],
                             'navigation': navigation})
        self.session = None
        self.browser_js('/odoo?debug=assets', '''
            (async () => {
                const data = DATA;
                const env = odoo.__WOWL_DEBUG__.root.env;
                const {useState, xml} = odoo.loader.modules.get('@odoo/owl');
                const {mountComponent} = odoo.loader.modules.get('@web/env');
                const {SalesWorkspace} = odoo.loader.modules.get('@ab_crm_sales_workspace/workspace');
                let view;
                class HeaderHarness extends SalesWorkspace {
                    static template = xml`<div class="ab_crm_sales_workspace">${data.navigation}
                        <div class="header_messages"><p t-foreach="state.detail.messages" t-as="message" t-key="message.id" t-esc="message.body"/></div>
                        <textarea t-model="state.reply"/></div>`;
                    setup() {
                        view = this;
                        this.state = useState({token: data.token, detail: data.initial, inbox: data.inbox,
                            reply: 'Telegram draft', attachments: [], replyTo: null, channelChooser: '', busy: false});
                        this.navigationVersion = 0;
                        this.drafts = new Map();
                        this.stopRecording = () => {};
                        this.clearSearch = () => {};
                        this.feedback = {report: error => {throw error;}};
                        this.call = (model, method, args = [], kwargs = {}) => env.services.orm.call(model, method, args,
                            {...kwargs, context: {ab_chatter_session_token: data.token}});
                    }
                }
                const target = document.createElement('div');
                document.body.append(target);
                const app = await mountComponent(HeaderHarness, target, {env});
                const wait = async predicate => {
                    for (let i = 0; i < 200; i++) {
                        if (predicate()) return;
                        await new Promise(resolve => setTimeout(resolve, 25));
                    }
                    throw new Error('Header navigation did not settle: ' + view.state.error);
                };
                const switchTo = async provider => {
                    target.querySelector(`[data-channel="${provider}"]`).click();
                    await wait(() => view.state.detail.provider === provider && !view.state.navigating);
                    await new Promise(resolve => requestAnimationFrame(resolve));
                };
                try {
                    await switchTo('website');
                    if (target.querySelector('.ab_channel_chooser')) throw new Error('Website icon only opened a chooser');
                    if (view.state.detail.id !== data.second) throw new Error('Website default destination changed');
                    if (view.state.detail.messages.filter(message => message.website_order).length !== 2 ||
                        view.state.detail.messages.some(message => message.body === 'Contact shared'))
                        throw new Error('Website timeline membership is incorrect');
                    view.state.reply = 'Second order draft';
                    await switchTo('whatsapp');
                    await switchTo('website');
                    if (view.state.reply !== 'Second order draft' || view.state.detail.id !== data.second)
                        throw new Error('Website draft or destination lost');
                    target.querySelector('[data-channel="website"]').click();
                    await wait(() => target.querySelectorAll('.ab_channel_chooser button').length === 2);
                    const choose = [...target.querySelectorAll('.ab_channel_chooser button')].find(button => button.textContent.includes('WEB-ONE'));
                    if (!choose) throw new Error('Original order reference missing');
                    choose.click();
                    await wait(() => view.state.detail.id === data.first && !view.state.navigating);
                    view.state.reply = 'First order draft';
                    view.lastChannelStreams = new Map();
                    await switchTo('telegram');
                    if (view.state.reply !== 'Telegram draft') throw new Error('Telegram draft lost');
                    await switchTo('website');
                    if (view.state.detail.id !== data.first || view.state.reply !== 'First order draft')
                        throw new Error('Explicit Website destination was not remembered');
                    console.log('test successful');
                } finally { app.destroy(); target.remove(); }
            })().catch(error => console.error(error));
        '''.replace('DATA', values),
            ready="!!odoo.__WOWL_DEBUG__?.root && !!document.querySelector('.o_ab_sales_dashboard_actions')",
            login=self.staff.login, timeout=90)
