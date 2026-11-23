from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, tagged, HttpCase, no_retry
from odoo.tools.safe_eval import safe_eval
from odoo.addons.ab_ecommerce_storefront.tests.test_checkout_reservation import (
    TestStorefrontReservations,
)
from odoo.addons.ab_ecommerce_storefront.controllers.checkout_submission import (
    checkout_submission,
)
from odoo.addons.website_sale.tests.common import MockRequest
from ..controllers.chat import Chat


@tagged('post_install', '-at_install', 'website_adapter')
class TestCapture(TestStorefrontReservations):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.worker = cls.env['res.users'].create(
            {
                'name': 'Adapter service',
                'login': 'adapter-service',
                'group_ids': [
                    fields.Command.set(
                        [
                            cls.env.ref('base.group_user').id,
                            cls.env.ref(
                                'ab_storefront_callcenter_adapter.group_service'
                            ).id,
                        ]
                    )
                ],
            }
        )
        values = {
            'service_user_id': cls.worker.id,
            'enabled': True,
            'cutoff': fields.Datetime.now() - timedelta(days=1),
        }
        cls.endpoint = cls.env['ab_storefront_callcenter_endpoint'].search(
            [('website_id', '=', cls.website.id)], limit=1
        )
        if cls.endpoint:
            cls.endpoint.write(values)
        else:
            cls.endpoint = cls.env['ab_storefront_callcenter_endpoint'].create(
                dict(values, name='Adapter', website_id=cls.website.id)
            )

    def _chat_configuration(self):
        operator = self.env.ref('ab_storefront_callcenter_adapter.user_callcenter_bridge')
        channel = self.env['im_livechat.channel'].create({
            'name': 'Callcenter test', 'user_ids': [fields.Command.set(operator.ids)]})
        self.website.channel_id = channel
        self.endpoint.write({'livechat_channel_id': channel.id, 'bridge_operator_id': operator.id,
                             'chat_enabled': True, 'outgoing_enabled': True})
        return channel

    def test_chat_acknowledgement_native_history_and_no_reflection(self):
        self._chat_configuration()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        key = str(uuid4())
        cart._ab_callcenter_customer_post('Customer question', key)
        self.assertTrue(cart.ab_callcenter_chat_ready)
        self.assertFalse(api.fetch_v2(self.endpoint.source))
        initial = api.fetch_v1(self.endpoint.source)[0]
        api.acknowledge_v1(self.endpoint.source, initial['event_uuid'], initial['fingerprint'])
        cart._ab_callcenter_customer_post('Customer question', key)
        events = api.fetch_v2(self.endpoint.source)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['destination'], {'kind': 'order', 'uuid': cart.ab_callcenter_uuid})
        self.assertEqual(len(cart.message_ids.filtered(lambda m: 'Customer question' in str(m.body))), 1)
        token = str(uuid4())
        api.receive_v2(self.endpoint.source, 'order', cart.ab_callcenter_uuid, token, '<safe reply>')
        api.receive_v2(self.endpoint.source, 'order', cart.ab_callcenter_uuid, token, '<safe reply>')
        self.assertEqual(len(api.fetch_v2(self.endpoint.source)), 1)
        replies = self.env['ab_storefront_callcenter_chat_reply'].search([('token', '=', token)])
        self.assertEqual(len(replies), 1)
        self.assertIn('&lt;safe reply&gt;', replies.message_id.body)
        with self.assertRaises(ValidationError):
            api.receive_v2(self.endpoint.source, 'order', cart.ab_callcenter_uuid, token, 'Changed')
        cart.action_ab_callcenter_publish_revision()
        cart.invalidate_recordset(['ab_callcenter_chat_ready'])
        self.assertTrue(cart.ab_callcenter_chat_ready)
        self.endpoint.outgoing_enabled = False
        with self.assertRaises(AccessError):
            api.receive_v2(self.endpoint.source, 'order', cart.ab_callcenter_uuid, str(uuid4()), 'Disabled')

    def test_dispatch_closes_one_order_and_preserves_acknowledgements(self):
        from ..models.chat import SessionEnded
        self._chat_configuration()
        self.endpoint.write({'lifecycle_enabled': True, 'dispatch_lifecycle_enabled': True})
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        orders = self.env['sale.order']
        for index in range(2):
            cart = self.cart()
            cart._cart_add(self.product.id, 1)
            cart.action_confirm()
            orders |= cart
        for event in api.fetch_v1(self.endpoint.source):
            api.acknowledge_v1(self.endpoint.source, event['event_uuid'], event['fingerprint'])
        first, second = orders
        token = str(uuid4())
        first._ab_callcenter_customer_post('Accepted before dispatch', token)
        reply = str(uuid4())
        api.receive_v2(self.endpoint.source, 'order', first.ab_callcenter_uuid, reply, 'Accepted reply')
        first.write({'ab_last_mile_status': 'out_for_delivery'})
        self.assertTrue(first.ab_callcenter_chat_closed)
        self.assertFalse(second.ab_callcenter_chat_closed)
        self.assertFalse([event for event in api.fetch_v3(self.endpoint.source) if event['kind'] == 'order_dispatched'])
        for event in api.fetch_v2(self.endpoint.source):
            api.acknowledge_v2(self.endpoint.source, event['event_uuid'], event['fingerprint'])
        dispatched = [event for event in api.fetch_v3(self.endpoint.source) if event['kind'] == 'order_dispatched']
        self.assertEqual(len(dispatched), 1)
        event = dispatched[0]
        self.assertEqual(event['kind'], 'order_dispatched')
        self.assertEqual(event['destination'], {'kind': 'order', 'uuid': first.ab_callcenter_uuid})
        first._ab_callcenter_customer_post('Accepted before dispatch', token)
        self.assertEqual(api.receive_v2(self.endpoint.source, 'order', first.ab_callcenter_uuid, reply, 'Accepted reply'), {'reference': reply})
        with self.assertRaises(SessionEnded):
            first._ab_callcenter_customer_post('Too late', str(uuid4()))
        with self.assertRaises(SessionEnded):
            api.receive_v2(self.endpoint.source, 'order', first.ab_callcenter_uuid, str(uuid4()), 'Too late')
        first.write({'ab_last_mile_status': 'not_started'})
        first.write({'ab_last_mile_status': 'out_for_delivery'})
        self.assertTrue(first.ab_callcenter_chat_closed)
        self.assertEqual(len([event for event in api.fetch_v3(self.endpoint.source) if event['kind'] == 'order_dispatched']), 1)
        second._ab_callcenter_customer_post('Other order remains open', str(uuid4()))

    def test_pending_order_media_is_saved_before_remote_acknowledgement(self):
        self._chat_configuration()
        self.endpoint.write({'media_enabled': True, 'lifecycle_enabled': True})
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        before = (cart.state, cart.amount_total, self.product.qty_available)
        attachment = self.env['ir.attachment'].create({'name': 'queued.pdf',
            'raw': b'%PDF-1.4 queued message', 'mimetype': 'application/pdf',
            'res_model': 'sale.order', 'res_id': cart.id})
        token = str(uuid4())
        cart._ab_callcenter_customer_post('', token, attachment.ids)
        cart._ab_callcenter_customer_post('', token, attachment.ids)
        pending = self.env['ab_storefront_callcenter_chat_event'].search([('event_uuid', '=', token)])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending.message_id.attachment_ids, attachment)
        self.assertFalse(pending.acknowledged)
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        self.assertFalse(api.fetch_v4(self.endpoint.source))
        self.assertFalse(api.fetch_v3(self.endpoint.source))
        initial = api.fetch_v1(self.endpoint.source)[0]
        api.acknowledge_v1(self.endpoint.source, initial['event_uuid'], initial['fingerprint'])
        self.assertEqual(api.fetch_v4(self.endpoint.source)[0]['event_uuid'], token)
        self.assertTrue(api.fetch_v3(self.endpoint.source))
        self.assertEqual((cart.state, cart.amount_total, self.product.qty_available), before)

    def test_warehouse_dispatch_closes_chat_with_native_stock_result(self):
        self._chat_configuration()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        before = self.product.with_context(warehouse_id=self.warehouse.id).qty_available
        picking = cart.picking_ids
        stock_user = self.env['res.users'].create({'name': 'Dispatch warehouse user', 'login': 'dispatch-warehouse-user',
            'group_ids': [fields.Command.set([self.env.ref('base.group_user').id, self.env.ref('stock.group_stock_user').id])]})
        picking.with_user(stock_user).move_ids.write({'quantity': 1, 'picked': True})
        picking.with_user(stock_user).button_validate()
        self.assertEqual(picking.state, 'done')
        self.assertTrue(cart.ab_callcenter_chat_closed)
        self.assertEqual(self.product.with_context(warehouse_id=self.warehouse.id).qty_available, before - 1)
        self.assertEqual(len(picking.move_ids.filtered(lambda move: move.state == 'done')), 1)

    def test_dispatch_evidence_cannot_be_forged(self):
        self._chat_configuration()
        cart = self.cart()
        with self.assertRaises(AccessError):
            cart.write({'ab_callcenter_chat_closed': True})

    def test_verified_customer_metadata_is_bounded_and_optional(self):
        from ..models.chat import customer_metadata
        self.env.user.partner_id.phone = '1' * 80
        self.assertEqual(customer_metadata(self.env.user)['phone'], '1' * 64)
        self.env.user.partner_id.phone = False
        self.assertEqual(customer_metadata(self.env.user)['phone'], '')

    def test_public_cod_confirmation_without_callcenter_receipt(self):
        self._chat_configuration()
        cart = self.cart()
        cart.partner_id = self.env.user.partner_id
        cart.carrier_id = self.env.ref('delivery.free_delivery_carrier')
        cart.carrier_id.website_published = True
        cart._cart_add(self.product.id, 1)
        cart._portal_ensure_token()
        provider = self.env['payment.provider'].search([
            ('code', '=', 'custom'), ('custom_mode', '=', 'cash_on_delivery'),
            ('company_id', '=', self.company.id),
        ], limit=1)
        method = self.env['payment.method'].search([('code', '=', 'cash_on_delivery')], limit=1)
        provider.payment_method_ids = method
        from odoo.addons.ab_ecommerce_storefront.controllers.checkout_submission import StorefrontPaymentPortal
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            StorefrontPaymentPortal().shop_payment_transaction(
                cart.id, cart.access_token, provider_id=provider.id, payment_method_id=method.id,
                token_id=None, amount=cart.amount_total, flow='redirect',
                tokenization_requested=False, landing_route='/shop/payment/validate')
        transaction = cart.transaction_ids.with_user(self.website.user_id).sudo()
        transaction._set_pending()
        transaction._post_process()
        self.assertEqual(cart.state, 'sale')
        self.assertTrue(transaction.is_post_processed)
        self.assertEqual(transaction.state, 'pending')
        initial = self.env['ab_storefront_callcenter_event'].search([('order_id', '=', cart.id)])
        self.assertTrue(initial)
        self.assertFalse(initial.acknowledged)
        self.assertEqual(len(cart.picking_ids), 1)
        transaction._post_process()
        self.assertEqual(len(cart.picking_ids), 1)

    def test_checkout_notifications_do_not_require_chat_receipt(self):
        self._chat_configuration()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        initial = self.env['ab_storefront_callcenter_event'].search([('order_id', '=', cart.id)])
        self.assertTrue(initial)
        self.assertFalse(initial.acknowledged)
        public_order = cart.with_user(self.website.user_id).sudo()
        message = public_order.message_post(body='Payment processing notification')
        self.assertEqual(message.message_type, 'notification')
        public_order._send_order_confirmation_mail()
        self.assertEqual(cart.state, 'sale')
        self.assertFalse(initial.acknowledged)
        self.assertFalse(self.env['ab_storefront_callcenter_chat_event'].search([
            ('endpoint_id', '=', self.endpoint.id)]))
        with self.assertRaises(AccessError):
            public_order.message_post(body='Customer question', message_type='comment',
                                      subtype_xmlid='mail.mt_comment')

    def test_v4_tracking_issues_guest_capability_only_to_owner(self):
        import hashlib
        from odoo.http import Response
        from ..models.adapter import _CAPTURE
        from ..controllers.portal import OrderPortal, AbStorefrontCustomerPortal
        self._chat_configuration()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        owner = 'tracking-guest-owner'
        guard = _CAPTURE.set(True)
        try:
            cart.write({'ab_callcenter_owner_hash': hashlib.sha256(('guest:' + owner).encode()).hexdigest()})
        finally:
            _CAPTURE.reset(guard)
        environment = self.env(user=self.website.user_id.id, su=False)
        with MockRequest(environment, website=self.website, url_root='https://shop.example/') as request:
            request.httprequest.scheme = 'https'
            request.session['ab_submission_owner'] = owner
            response = Response()
            response.qcontext = {'sale_order': cart}
            with patch.object(AbStorefrontCustomerPortal, 'portal_order_page', return_value=response):
                result = OrderPortal.portal_order_page.__wrapped__(OrderPortal(), cart.id)
            self.assertIn('HttpOnly', result.headers['Set-Cookie'])
            self.assertIn('Secure', result.headers['Set-Cookie'])
            self.assertTrue(cart.ab_callcenter_capability_hash)
            response = Response()
            response.qcontext = {'sale_order': cart}
            request.session['ab_submission_owner'] = 'other-guest'
            with patch.object(AbStorefrontCustomerPortal, 'portal_order_page', return_value=response):
                result = OrderPortal.portal_order_page.__wrapped__(OrderPortal(), cart.id)
            self.assertTrue(result.qcontext['disable_composer'])
            self.assertNotIn('Set-Cookie', result.headers)

    def test_v4_attachment_only_guest_ownership_and_replay(self):
        import hashlib
        self._chat_configuration()
        self.endpoint.media_enabled = True
        guest = self.env['mail.guest'].create({'name': 'Media visitor'})
        channel = self.endpoint.livechat_channel_id.with_user(self.website.user_id).with_context(guest=guest)
        values = channel._get_livechat_discuss_channel_vals(**channel._get_operator_info(lang='en_US', country_id=False))
        session = channel.env['discuss.channel'].sudo().create(values)
        raw = b'%PDF-1.4 test document'
        file = channel.env['ir.attachment'].sudo().create({'name': 'test.pdf', 'mimetype': 'application/pdf',
            'raw': raw, 'res_model': 'mail.compose.message', 'res_id': 0})
        token = str(uuid4())
        files = channel.env['ir.attachment']._ab_owned_files(session, [{'id': file.id, 'token': file._get_ownership_token()}])
        message = session.with_context(ab_message_uuid=token).message_post(body='', attachment_ids=files.ids,
            message_type='comment', subtype_xmlid='mail.mt_comment')
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        self.assertFalse(api.fetch_v2(self.endpoint.source))
        event = api.fetch_v4(self.endpoint.source)[0]
        self.assertEqual(event['attachments'][0]['digest'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(event['body'], '')
        self.assertEqual(session.with_context(ab_message_uuid=token).message_post(body='', attachment_ids=files.ids,
            message_type='comment', subtype_xmlid='mail.mt_comment'), message)
        with self.assertRaises(ValidationError):
            session.with_context(ab_message_uuid=token).message_post(body='Changed', attachment_ids=files.ids,
                message_type='comment', subtype_xmlid='mail.mt_comment')
        with self.assertRaises(AccessError):
            file.write({'raw': b'changed'})
        outsider = self.env['res.users'].create({'name': 'Media outsider', 'login': 'media-outsider',
            'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(AccessError):
            self.env['ir.attachment'].with_user(outsider)._ab_owned_files(session, [{'id': file.id, 'token': 'forged'}])
        with self.assertRaises(AccessError):
            api.with_user(outsider).fetch_v4(self.endpoint.source)

    def test_chat_floating_first_message_and_exact_session_reply(self):
        channel = self._chat_configuration()
        guest = self.env['mail.guest'].create({'name': 'Visitor test'})
        channel = channel.with_user(self.website.user_id).with_context(guest=guest, lang='en_US')
        values = channel._get_livechat_discuss_channel_vals(**channel._get_operator_info(lang='en_US', country_id=False))
        session = channel.env['discuss.channel'].sudo().create(values)
        session.message_post(body='First input', message_type='comment', subtype_xmlid='mail.mt_comment')
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        events = api.fetch_v2(self.endpoint.source)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['body'], 'First input')
        self.assertEqual(events[0]['identity']['kind'], 'visitor')
        self.assertEqual(events[0]['destination']['uuid'], session.ab_callcenter_session_uuid)
        self.assertIn('queued', str(session.message_ids[0].body))
        token = str(uuid4())
        api.receive_v2(self.endpoint.source, 'livechat', session.ab_callcenter_session_uuid, token, 'Agent response')
        api.receive_v2(self.endpoint.source, 'livechat', session.ab_callcenter_session_uuid, token, 'Agent response')
        self.assertEqual(len(session.message_ids.filtered(lambda m: 'Agent response' in str(m.body))), 1)
        self.assertEqual(len(api.fetch_v2(self.endpoint.source)), 1)
        self.assertIn(self.endpoint.bridge_operator_id, channel.sudo().available_operator_ids)
        next_values = channel._get_livechat_discuss_channel_vals(**channel._get_operator_info(lang='en_US', country_id=False))
        self.assertEqual(next_values['ab_callcenter_identity_uuid'], session.ab_callcenter_identity_uuid)
        self.assertNotEqual(next_values['ab_callcenter_session_uuid'], session.ab_callcenter_session_uuid)
        portal = self.env['res.users'].create({'name': 'Signed in customer', 'login': 'chat-login-boundary',
            'partner_id': self.partner.id, 'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(AccessError):
            session.with_user(portal).message_post(body='Do not merge', message_type='comment', subtype_xmlid='mail.mt_comment')
        with self.assertRaises(AccessError):
            api.receive_v2(self.endpoint.source, 'livechat', str(uuid4()), str(uuid4()), 'Forged')
        with self.assertRaises(AccessError):
            session.with_user(self.worker).write({'ab_callcenter_identity_uuid': str(uuid4())})

    def test_chat_storefront_upgrade_preserves_bridge_operator(self):
        from odoo.tools import convert_file

        channel = self.env.ref('ab_ecommerce_storefront.livechat_channel')
        operator = self.env.ref('ab_storefront_callcenter_adapter.user_callcenter_bridge')
        channel.write({'user_ids': [fields.Command.link(operator.id)]})
        self.website.channel_id = channel
        self.endpoint.write({'livechat_channel_id': channel.id, 'bridge_operator_id': operator.id,
                             'chat_enabled': True})
        convert_file(self.env, 'ab_ecommerce_storefront', 'data/livechat.xml', {}, mode='update')
        self.assertIn(operator, channel.user_ids)
        self.assertEqual(self.website.channel_id, channel)
        self.env['ab_storefront_callcenter_api'].with_user(self.worker).fetch_v1(self.endpoint.source)

    def test_chat_queue_acknowledgement_uses_session_language(self):
        channel = self._chat_configuration()
        self.env['res.lang']._activate_lang('ar_001')
        guest = self.env['mail.guest'].create({'name': 'Language test visitor'})
        public = channel.with_user(self.website.user_id).with_context(guest=guest, lang='en_US')
        for language, expected in [('en_US', 'Your message is queued'), ('ar_001', 'رسالتك في انتظار مركز الاتصال')]:
            values = public._get_livechat_discuss_channel_vals(**public._get_operator_info(lang=language, country_id=False))
            values['livechat_lang_id'] = self.env['res.lang']._get_data(code=language).id
            session = public.env['discuss.channel'].sudo().create(values)
            session.message_post(body='Local language test', message_type='comment', subtype_xmlid='mail.mt_comment')
            self.assertIn(expected, str(session.message_ids[0].body))

    def test_chat_native_portal_comments_and_notes(self):
        self._chat_configuration()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        portal = self.env['res.users'].create({'name': 'Portal chat customer', 'login': 'native-chat-portal',
            'partner_id': self.partner.id, 'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        import hashlib
        from ..models.adapter import _CAPTURE
        guard = _CAPTURE.set(True)
        try:
            cart.write({'ab_callcenter_owner_hash': hashlib.sha256(f'user:{portal.id}'.encode()).hexdigest()})
        finally:
            _CAPTURE.reset(guard)
        portal_env = self.env(user=portal.id, su=False)
        with MockRequest(portal_env, website=self.website):
            cart.with_user(portal).sudo().message_post(body='Pending', message_type='comment', subtype_xmlid='mail.mt_comment')
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        initial = api.fetch_v1(self.endpoint.source)[0]
        self.assertFalse(api.fetch_v2(self.endpoint.source))
        api.acknowledge_v1(self.endpoint.source, initial['event_uuid'], initial['fingerprint'])
        with MockRequest(portal_env, website=self.website) as request, patch.object(
                type(self.env['website']), 'get_current_website', return_value=self.website):
            del request.website
            cart.with_user(portal).sudo().message_post(body='Native customer comment', message_type='comment', subtype_xmlid='mail.mt_comment')
        cart.write({'ab_last_mile_status': 'out_for_delivery'})
        from ..models.chat import SessionEnded
        with MockRequest(portal_env, website=self.website):
            with self.assertRaises(SessionEnded):
                cart.with_user(portal).sudo().message_post(body='Late direct RPC comment', message_type='comment', subtype_xmlid='mail.mt_comment')
        cart.message_post(body='Internal note', message_type='comment', subtype_xmlid='mail.mt_note')
        cart.message_post(body='Employee comment', message_type='comment', subtype_xmlid='mail.mt_comment')
        events = api.fetch_v2(self.endpoint.source)
        self.assertEqual(len(events), 2)
        self.assertEqual({event['body'] for event in events}, {'Pending', 'Native customer comment'})

    def test_adapter_endpoint_selector_before_company_is_derived(self):
        endpoints = self.env['ab_storefront_callcenter_endpoint'].with_context(
            allowed_company_ids=self.company.ids
        )
        self.assertFalse(endpoints.new({}).company_id)
        view = endpoints.get_view(
            self.env.ref('ab_storefront_callcenter_adapter.endpoint_form').id,
            'form',
        )
        field = etree.fromstring(view['arch']).xpath("//field[@name='website_id']")[0]
        domain = safe_eval(
            field.get('domain'), {'allowed_company_ids': self.company.ids}
        )
        self.assertIn(self.website, self.env['website'].search(domain))
        self.assertTrue(safe_eval(field.get('options'))['no_create'])
        website = self.env['website'].create(
            {'name': self.website.name, 'company_id': self.company.id}
        )
        with Form(endpoints, view='ab_storefront_callcenter_adapter.endpoint_form') as form:
            form.name = 'New website endpoint'
            form.website_id = website
            self.assertEqual(form.company_id, self.company)
            form.service_user_id = self.worker
        self.assertEqual(form.record.website_id, website)
        self.assertEqual(form.record.company_id, self.company)
        with self.assertRaises(AccessError):
            form.record.write({'website_id': self.website.id})

    def test_adapter_endpoint_selector_company_scope(self):
        company = self.env['res.company'].create({'name': 'Other adapter company'})
        website = self.env['website'].create(
            {'name': self.website.name, 'company_id': company.id}
        )
        endpoints = self.env['ab_storefront_callcenter_endpoint'].with_context(
            allowed_company_ids=self.company.ids
        )
        view = endpoints.get_view(
            self.env.ref('ab_storefront_callcenter_adapter.endpoint_form').id,
            'form',
        )
        field = etree.fromstring(view['arch']).xpath("//field[@name='website_id']")[0]
        domain = safe_eval(
            field.get('domain'), {'allowed_company_ids': self.company.ids}
        )
        self.assertNotIn(website, self.env['website'].search(domain))
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            endpoints.create(
                {
                    'name': 'Unauthorized company endpoint',
                    'website_id': website.id,
                    'service_user_id': self.worker.id,
                }
            )

    def test_disabled_endpoint_can_be_detached_for_website_cleanup(self):
        website = self.env['website'].create(
            {'name': 'Retired test website', 'company_id': self.company.id}
        )
        endpoint = self.env['ab_storefront_callcenter_endpoint'].create({
            'name': 'Retired test endpoint',
            'website_id': website.id,
            'service_user_id': self.worker.id,
            'enabled': True,
        })
        source = endpoint.source
        with self.assertRaises(AccessError):
            endpoint.write({'website_id': False})
        endpoint.write({'enabled': False})
        with self.assertRaises(AccessError):
            endpoint.with_user(self.worker).write({'website_id': False})
        endpoint.write({'website_id': False})
        self.assertEqual(endpoint.company_id, self.company)
        self.assertEqual(endpoint.source, source)
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            endpoint.write({'enabled': True})
        website.unlink()
        self.assertTrue(endpoint.exists())
        self.assertEqual(endpoint.company_id, self.company)

    def test_adapter_browser_cod(self):
        self.test_cash_on_delivery_post_processing_confirms_and_reserves_once()
        events = self.env['ab_storefront_callcenter_event'].search([])
        self.assertEqual(len(events), 1)
        self.assertEqual(events.envelope['kind'], 'order')
        self.assertEqual(events.order_id.state, 'sale')
        self.assertEqual(events.envelope['payload']['payments'][0]['state'], 'pending')
        self.assertEqual(events.envelope['payload']['payments'][0]['method'], 'cash_on_delivery')
        self.assertEqual(
            events.envelope['payload']['customer']['address'],
            events.order_id.partner_shipping_id._display_address(),
        )
        self.assertEqual(events.order_id.ab_callcenter_revision, 1)

    def test_adapter_api_payment_capture(self):
        if 'ab_ecommerce_api_session' not in self.env:
            self.skipTest('Customer API is optional; install it for the API regression')
        from odoo.addons.ab_ecommerce_api.controllers.api import EcommerceApi

        cart = self.cart()
        cart.partner_id = self.env.user.partner_id
        cart.carrier_id = self.env.ref('delivery.free_delivery_carrier')
        cart.carrier_id.website_published = True
        cart._cart_add(self.product.id, 1)
        provider = self.env['payment.provider'].search(
            [('code', '=', 'custom'), ('custom_mode', '=', 'cash_on_delivery')], limit=1
        )
        method = self.env['payment.method'].search(
            [('code', '=', 'cash_on_delivery')], limit=1
        )
        provider.payment_method_ids = method
        api = EcommerceApi()
        with MockRequest(
            self.env, website=self.website, sale_order_id=cart.id
        ) as request:
            submission = checkout_submission(cart)
            request.ab_api_data = {
                'idempotency_key': submission.key,
                'provider_id': provider.id,
                'payment_method_id': method.id,
            }
            with patch.object(
                EcommerceApi, '_payment_options', return_value=(provider, method)
            ):
                __import__('inspect').unwrap(EcommerceApi.payment)(
                    api, order_id=cart.id
                )
        self.assertFalse(cart.ab_callcenter_uuid)
        cart.transaction_ids._set_pending()
        cart.transaction_ids._post_process()
        self.assertEqual(cart.state, 'sale')
        self.assertTrue(cart.ab_callcenter_uuid)
        self.assertEqual(
            len(
                self.env['ab_storefront_callcenter_event'].search(
                    [('order_id', '=', cart.id)]
                )
            ),
            1,
        )

    def test_adapter_disabled_cutoff_and_rollback(self):
        self.endpoint.enabled = False
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        self.assertFalse(cart.ab_callcenter_uuid)
        self.endpoint.enabled = True
        self.endpoint.cutoff = fields.Datetime.now() + timedelta(days=1)
        second = self.cart()
        second._cart_add(self.product.id, 1)
        second.action_confirm()
        self.assertFalse(second.ab_callcenter_uuid)
        self.endpoint.cutoff = fields.Datetime.now() - timedelta(days=1)
        third = self.cart()
        third._cart_add(self.product.id, 1)
        with self.assertRaisesRegex(ValueError, 'rollback'), self.env.cr.savepoint():
            third.action_confirm()
            raise ValueError('rollback')
        self.assertEqual(third.state, 'draft')
        self.assertFalse(third.ab_callcenter_uuid)

    def test_adapter_exchange_access_and_reply_dedup(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        events = api.fetch_v1(self.endpoint.source)
        self.assertEqual(len(events), 1)
        with self.assertRaises(AccessError):
            self.env['ab_storefront_callcenter_api'].fetch_v1(self.endpoint.source)
        with self.assertRaises(AccessError):
            api.fetch_v1(str(uuid4()))
        with self.assertRaises(AccessError):
            api.receive_v1(self.endpoint.source, cart.ab_callcenter_uuid, str(uuid4()), 'Hello')
        api.acknowledge_v1(
            self.endpoint.source, events[0]['event_uuid'], events[0]['fingerprint']
        )
        self.assertEqual(api.fetch_v1(self.endpoint.source), [])
        with self.assertRaises(AccessError):
            cart.write({'ab_callcenter_revision': 99})

    def test_adapter_guest_requires_origin_and_capability(self):
        from werkzeug.exceptions import Forbidden

        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        with MockRequest(self.env, website=self.website, sale_order_id=cart.id):
            checkout_submission(cart)
        cart.action_confirm()
        public_env = self.env(user=self.website.user_id.id, su=False)
        with MockRequest(public_env, website=self.website) as request:
            request.session['sale_last_order_id'] = cart.id
            with self.assertRaises(Forbidden):
                Chat()._order(cart.ab_callcenter_uuid)

    def test_adapter_browser_cod_disabled(self):
        self.endpoint.enabled = False
        self.test_cash_on_delivery_post_processing_confirms_and_reserves_once()
        self.assertFalse(self.env['ab_storefront_callcenter_event'].search([]))

    def test_adapter_preparation_failure_and_online_payment(self):
        cart = self.cart()
        cart.partner_id = self.env.user.partner_id
        cart._cart_add(self.product.id, 1)
        provider = self.env.ref('payment.payment_provider_transfer')
        method = self.env.ref('payment_custom.payment_method_wire_transfer')
        provider.write(
            {
                'state': 'test',
                'custom_mode': 'wire_transfer',
                'payment_method_ids': [fields.Command.set(method.ids)],
            }
        )
        method.active = True
        transaction = self.env['payment.transaction'].create(
            {
                'provider_id': provider.id,
                'payment_method_id': method.id,
                'reference': 'ADAPTER-ONLINE',
                'amount': cart.amount_total,
                'currency_id': cart.currency_id.id,
                'partner_id': cart.partner_id.id,
                'operation': 'online_redirect',
                'sale_order_ids': [fields.Command.set(cart.ids)],
            }
        )
        self.assertFalse(cart.ab_callcenter_uuid)
        transaction._set_error('Failed submission')
        transaction._post_process()
        self.assertFalse(cart.ab_callcenter_uuid)
        transaction.write({'state': 'done', 'is_post_processed': False})
        with patch.object(
            type(transaction),
            '_create_payment',
            return_value=self.env['account.payment'],
        ) as accounting:
            transaction._post_process()
        accounting.assert_called_once()
        self.assertEqual(cart.state, 'sale')
        self.assertTrue(cart.ab_callcenter_uuid)
        self.assertEqual(
            self.env['ab_storefront_callcenter_event']
            .search([('order_id', '=', cart.id)])
            .envelope['payload']['payments'][0]['state'],
            'done',
        )

    def test_adapter_chat_origin_capability_expiry_and_message_replay(self):
        import hashlib
        from werkzeug.exceptions import Forbidden
        from ..models.adapter import _CAPTURE

        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        public_env = self.env(user=self.website.user_id.id, su=False)
        owner = 'origin-session-secret'
        owner_hash = hashlib.sha256(('guest:' + owner).encode()).hexdigest()
        capability = 'private-order-capability'
        guard = _CAPTURE.set(True)
        try:
            cart.action_confirm()
            cart.write(
                {
                    'ab_callcenter_owner_hash': owner_hash,
                    'ab_callcenter_capability_hash': hashlib.sha256(
                        capability.encode()
                    ).hexdigest(),
                    'ab_callcenter_capability_expires': fields.Datetime.now()
                    + timedelta(hours=1),
                }
            )
        finally:
            _CAPTURE.reset(guard)
        with MockRequest(public_env, website=self.website) as request:
            request.session['ab_submission_owner'] = owner
            request.httprequest.cookies = {
                'ab_website_chat_' + cart.ab_callcenter_uuid: capability
            }
            self.assertEqual(Chat()._order(cart.ab_callcenter_uuid), cart)
            key = str(uuid4())
            guard = _CAPTURE.set(True)
            try:
                cart._ab_callcenter_event('message', {'body': 'Hello'}, key)
                cart._ab_callcenter_event('message', {'body': 'Hello'}, key)
                self.assertEqual(cart.ab_callcenter_revision, 2)
                with self.assertRaises(ValidationError):
                    cart._ab_callcenter_event('message', {'body': 'Changed'}, key)
                cart.write(
                    {
                        'ab_callcenter_capability_expires': fields.Datetime.now()
                        - timedelta(seconds=1)
                    }
                )
            finally:
                _CAPTURE.reset(guard)
            with self.assertRaises(Forbidden):
                Chat()._order(cart.ab_callcenter_uuid)
            request.session['ab_submission_owner'] = 'other-session'
            with self.assertRaises(Forbidden):
                Chat()._order(cart.ab_callcenter_uuid, capability=False)

    def test_adapter_manager_revision_preserves_native_state(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        state = cart.state
        cart.action_ab_callcenter_publish_revision()
        self.assertEqual(cart.state, state)
        self.assertEqual(cart.ab_callcenter_revision, 2)
        with self.assertRaises(AccessError):
            cart.with_user(self.worker).action_ab_callcenter_publish_revision()

    def test_adapter_chat_english_and_arabic_rendering(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        for language, expected in [('en_US', 'Order chat'), ('ar_001', 'محادثة الطلب')]:
            localized = self.env(context=dict(self.env.context, lang=language))
            with MockRequest(
                localized,
                website=self.website.with_env(localized),
                url_root='https://shop.example/',
            ):
                page = localized['ir.ui.view']._render_template(
                    'ab_storefront_callcenter_adapter.chat',
                    {'order': cart.with_env(localized)},
                )
            self.assertIn(expected, str(page))
            self.assertIn('Refresh' if language == 'en_US' else 'تحديث', str(page))

    def test_adapter_regular_sales_manager_confirmation(self):
        from odoo.tests import new_test_user

        manager = new_test_user(
            self.env,
            login='adapter-sales-manager',
            groups='base.group_user,sales_team.group_sale_manager',
        )
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        with MockRequest(self.env, website=self.website):
            checkout_submission(cart)
        cart.with_user(manager).action_confirm()
        self.assertTrue(cart.ab_callcenter_uuid)
        cart.with_user(manager).action_ab_callcenter_publish_revision()
        self.assertEqual(cart.ab_callcenter_revision, 2)

    def test_adapter_prescription_is_excluded(self):
        import base64

        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        self.env['ab.prescription.order'].create(
            {
                'partner_id': self.partner.id,
                'website_id': self.website.id,
                'company_id': self.company.id,
                'sale_order_id': cart.id,
                'prescription_image': base64.b64encode(b'review-test'),
            }
        )
        cart.action_confirm()
        self.assertEqual(cart.state, 'sale')
        self.assertFalse(cart.ab_callcenter_uuid)

    def test_adapter_views_load_in_xml_developer_mode(self):
        from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file
        from odoo.tools import file_path

        for name in ['endpoint_list', 'endpoint_form', 'unit_form', 'sale_order_form']:
            arch = get_view_arch_from_file(
                file_path('ab_storefront_callcenter_adapter/views/views.xml'),
                'ab_storefront_callcenter_adapter.' + name,
            )
            self.assertIn('<', arch)

    def test_adapter_snapshot_marks_native_delivery_lines(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        carrier = self.env.ref('delivery.free_delivery_carrier')
        cart._set_delivery_method(carrier)
        snapshot = cart._ab_callcenter_snapshot()
        delivery = [line for line in snapshot['lines'] if line['is_delivery']]
        products = [line for line in snapshot['lines'] if not line['is_delivery']]
        self.assertEqual(len(delivery), 1)
        self.assertEqual(delivery[0]['total'], 0)
        self.assertEqual(len(products), 1)

    def test_adapter_snapshot_preserves_readable_unit_name(self):
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        event = self.env['ab_storefront_callcenter_event'].search([
            ('order_id', '=', cart.id),
        ])
        self.assertEqual(len(event), 1)
        self.assertTrue(cart.ab_public_reference.startswith('NO-'))
        self.assertEqual(event.envelope['payload']['public_reference'], cart.ab_public_reference)
        self.assertEqual(event.envelope['payload']['reference'], cart.name)
        self.assertNotEqual(cart.ab_public_reference, cart.name)
        source = cart.order_line.filtered(lambda line: not line.display_type)
        self.assertEqual(event.envelope['payload']['lines'][0]['unit_name'],
                         source[0].product_uom_id.name)
        self.assertEqual(event.envelope['payload']['lines'][0]['unit'],
                         source[0].product_uom_id.ab_callcenter_code or '')
        from ..protocol import validate
        self.assertEqual(validate(event.envelope), event.envelope)

    def test_recovery_native_response_lost_same_uuid(self):
        channel = self._chat_configuration()
        guest = self.env['mail.guest'].create({'name': 'Recovery visitor'})
        public = channel.with_user(self.website.user_id).with_context(guest=guest)
        values = public._get_livechat_discuss_channel_vals(**public._get_operator_info(lang='en_US', country_id=False))
        session = public.env['discuss.channel'].sudo().create(values)
        token = str(uuid4())
        sender = session.with_context(ab_message_uuid=token)
        first = sender.message_post(body='Same deliberate text', message_type='comment', subtype_xmlid='mail.mt_comment')
        replay = sender.message_post(body='Same deliberate text', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertEqual(first.id, replay.id)
        distinct = session.with_context(ab_message_uuid=str(uuid4())).message_post(
            body='Same deliberate text', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertNotEqual(first.id, distinct.id)

    def recovery_guest_session(self):
        channel = self._chat_configuration()
        self.endpoint.lifecycle_enabled = True
        guest = self.env['mail.guest'].create({'name': 'Lifecycle guest'})
        public = channel.with_user(self.website.user_id).with_context(guest=guest)
        values = public._get_livechat_discuss_channel_vals(**public._get_operator_info(lang='en_US', country_id=False))
        session = public.env['discuss.channel'].sudo().create(values)
        session.message_post(body='Keep history', message_type='comment', subtype_xmlid='mail.mt_comment')
        return public, guest, session

    def test_recovery_guest_end_rotates_and_blocks_queued_reply(self):
        from ..models.chat import SessionEnded
        public, guest, session = self.recovery_guest_session()
        identity = session.ab_callcenter_identity_uuid
        session._close_livechat_session()
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        self.assertEqual(api.fetch_v3(self.endpoint.source), [])
        for event in api.fetch_v2(self.endpoint.source):
            api.acknowledge_v2(self.endpoint.source, event['event_uuid'], event['fingerprint'])
        self.assertEqual(len(api.fetch_v3(self.endpoint.source)), 1)
        with self.assertRaises(SessionEnded):
            api.receive_v2(self.endpoint.source, 'livechat', session.ab_callcenter_session_uuid, str(uuid4()), 'Too late')
        values = public._get_livechat_discuss_channel_vals(**public._get_operator_info(lang='en_US', country_id=False))
        self.assertNotEqual(values['ab_callcenter_identity_uuid'], identity)
        with self.assertRaises(SessionEnded):
            session.with_context(ab_message_uuid=str(uuid4())).message_post(
                body='After end', message_type='comment', subtype_xmlid='mail.mt_comment')

    def test_recovery_guest_handoff_requires_both_owners(self):
        public, guest, session = self.recovery_guest_session()
        portal = self.env['res.users'].create({'name': 'Verified handoff', 'login': 'verified-handoff',
            'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        other_guest = self.env['mail.guest'].create({'name': 'Other visitor'})
        with self.assertRaises(AccessError):
            session.with_user(portal).with_context(guest=other_guest)._ab_callcenter_bind_account()
        pending_uuid = str(uuid4())
        pending = session.with_context(ab_message_uuid=pending_uuid).message_post(body='Handoff pending message', message_type='comment', subtype_xmlid='mail.mt_comment')
        owner = session.with_user(portal).sudo().with_context(guest=guest)
        owner._ab_callcenter_bind_account()
        replay = owner.with_context(ab_message_uuid=pending_uuid).message_post(body='Handoff pending message', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.assertEqual(replay.id, pending.id)
        self.assertEqual(session.ab_callcenter_identity_kind, 'customer')
        self.assertFalse(session.channel_member_ids.filtered(lambda member: member.guest_id == guest))
        with self.assertRaises(AccessError):
            session.with_user(self.website.user_id).with_context(guest=guest)._ab_callcenter_authorize()
        with self.assertRaises(AccessError):
            session.with_user(portal).with_context(guest=guest)._ab_callcenter_bind_account()
        other = self.env['res.users'].create({'name': 'Same partner second account', 'login': 'same-partner-second-account',
            'partner_id': portal.partner_id.id, 'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        with self.assertRaises(AccessError):
            session.with_user(other).read(['name'])
        with self.assertRaises(AccessError):
            session.sudo().message_ids.with_user(other).read(['body'])
        owner.message_post(body='Verified continuation', message_type='comment', subtype_xmlid='mail.mt_comment')
        with self.assertRaises(AccessError):
            session.sudo().message_ids.with_user(other).read(['body'])
        self.assertFalse(self.env['mail.message'].with_user(other).search([('model', '=', 'discuss.channel'), ('res_id', '=', session.id)]))
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        self.assertEqual(api.fetch_v3(self.endpoint.source)[0]['kind'], 'identity_bound')

    def test_recovery_order_cursor_recovers_more_than_one_hundred(self):
        import json
        import hashlib
        from ..models.adapter import _CAPTURE
        self._chat_configuration()
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        portal = self.env['res.users'].create({'name': 'Paged owner', 'login': 'paged-owner',
            'partner_id': self.partner.id, 'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        guard = _CAPTURE.set(True)
        try:
            cart.write({'ab_callcenter_owner_hash': hashlib.sha256(f'user:{portal.id}'.encode()).hexdigest()})
            for index in range(105):
                cart.message_post(body='Page message %s' % index, message_type='comment', subtype_xmlid='mail.mt_comment')
        finally:
            _CAPTURE.reset(guard)
        environment = self.env(user=portal.id, su=False)
        with MockRequest(environment, website=self.website) as request:
            from odoo.http import Response
            request.make_json_response = lambda values, **kwargs: Response(json.dumps(values), content_type='application/json')
            first = json.loads(Chat().messages(cart.ab_callcenter_uuid).get_data())
            second = json.loads(Chat().messages(cart.ab_callcenter_uuid, after=first['cursor']).get_data())
        self.assertEqual(len(first['messages']), 100)
        self.assertTrue(first['has_more'])
        self.assertGreaterEqual(len(second['messages']), 5)
        self.assertFalse(set(row['key'] for row in first['messages']) & set(row['key'] for row in second['messages']))

    def test_recovery_order_handoff_revokes_guest_and_shared_partner(self):
        import hashlib
        from werkzeug.exceptions import Forbidden
        from ..models.adapter import _CAPTURE
        self._chat_configuration()
        self.endpoint.lifecycle_enabled = True
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        owner_secret, capability = 'verified-origin-secret', 'verified-order-capability'
        original = hashlib.sha256(('guest:' + owner_secret).encode()).hexdigest()
        guard = _CAPTURE.set(True)
        try:
            cart.write({'ab_callcenter_owner_hash': original,
                'ab_callcenter_capability_hash': hashlib.sha256(capability.encode()).hexdigest(),
                'ab_callcenter_capability_expires': fields.Datetime.now() + timedelta(hours=1)})
        finally:
            _CAPTURE.reset(guard)
        def customer(login):
            return self.env['res.users'].create({'name': login, 'login': login, 'partner_id': self.partner.id,
                'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        owner, other = customer('handoff-order-owner'), customer('shared-partner-not-owner')
        with MockRequest(self.env(user=other.id, su=False), website=self.website):
            with self.assertRaises(Forbidden):
                Chat()._order(cart.ab_callcenter_uuid)
        with MockRequest(self.env(user=owner.id, su=False), website=self.website) as request:
            request.session['ab_submission_owner'] = owner_secret
            request.httprequest.cookies = {'ab_website_chat_' + cart.ab_callcenter_uuid: capability}
            self.assertEqual(Chat()._order(cart.ab_callcenter_uuid), cart)
            self.assertEqual(Chat()._order(cart.ab_callcenter_uuid), cart)
        self.assertEqual(cart.ab_callcenter_owner_hash, original)
        self.assertTrue(cart.ab_callcenter_account_uuid)
        self.assertFalse(cart.ab_callcenter_capability_hash)
        with MockRequest(self.env(user=other.id, su=False), website=self.website):
            with self.assertRaises(Forbidden):
                Chat()._order(cart.ab_callcenter_uuid)
        with MockRequest(self.env(user=self.website.user_id.id, su=False), website=self.website) as request:
            request.session['ab_submission_owner'] = owner_secret
            request.httprequest.cookies = {'ab_website_chat_' + cart.ab_callcenter_uuid: capability}
            with self.assertRaises(Forbidden):
                Chat()._order(cart.ab_callcenter_uuid)


@tagged('post_install', '-at_install')
class TestRecoveryBrowser(HttpCase):
    @no_retry
    def test_submit_during_history_poll_preserves_intent_and_newer_draft(self):
        self.browser_js('/?debug=assets', r'''
            (async () => {
                const {startChat} = odoo.loader.modules.get('@ab_storefront_callcenter_adapter/chat');
                await odoo.loader.modules.get('@web/core/l10n/translation').translationIsReady;
                const originalFetch = window.fetch;
                const root = document.createElement('section');
                root.dataset.orderUuid = 'poll-race-' + crypto.randomUUID();
                root.innerHTML = '<div data-chat-history></div><div data-chat-status></div><div data-chat-uploads></div><form action="/poll-race-test"><input name="csrf_token" value="test"/><textarea name="body"></textarea><button type="submit">Send</button></form>';
                document.body.append(root);
                const form = root.querySelector('form');
                const input = form.elements.body;
                const pendingKey = 'ab.website.pending:' + location.origin + ':' + root.dataset.orderUuid;
                const draftKey = 'ab.website.draft:' + location.origin + ':' + root.dataset.orderUuid;
                let releaseRead;
                const sent = [];
                const wait = () => new Promise(resolve => setTimeout(resolve, 25));
                const response = acknowledged => ({ok: true, json: async () => ({ready: true, messages: [],
                    cursor: '0', has_more: false, acknowledged, account_identity: 'poll-race-owner'})});
                window.fetch = async (url, options) => {
                    if (!String(url).includes('/poll-race-test')) return originalFetch(url, options);
                    const body = options.body.get('body');
                    if (!body && !releaseRead) return new Promise(resolve => {releaseRead = resolve;});
                    if (body) sent.push({body, id: options.body.get('event_uuid')});
                    return response(options.body.get('event_uuid') || false);
                };
                try {
                    startChat(root);
                    for (let i = 0; i < 100 && !releaseRead; i++) await wait();
                    if (!releaseRead) throw new Error('Background poll did not begin');
                    input.value = 'Explicit send while polling';
                    input.dispatchEvent(new Event('input'));
                    form.dispatchEvent(new Event('submit', {cancelable: true}));
                    const staged = JSON.parse(sessionStorage.getItem(pendingKey) || 'null');
                    if (!staged || staged.body !== input.value) throw new Error('Busy poll discarded the explicit send intention');
                    input.value = 'Newer unsent draft';
                    input.dispatchEvent(new Event('input'));
                    releaseRead(response(false));
                    for (let i = 0; i < 100 && sessionStorage.getItem(pendingKey); i++) await wait();
                    await wait();
                    if (sent.length !== 1 || sent[0].body !== staged.body || sent[0].id !== staged.id) throw new Error('Queued intention was lost, changed or duplicated');
                    if (input.value !== 'Newer unsent draft' || sessionStorage.getItem(draftKey) !== input.value) throw new Error('Queued acknowledgement cleared the newer draft');
                    console.log('test successful');
                } finally {
                    window.fetch = originalFetch;
                    root.remove();
                    sessionStorage.removeItem(pendingKey);
                    sessionStorage.removeItem(draftKey);
                }
            })().catch(error => console.error(error));
        ''', ready="!!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/chat')", login='admin', timeout=90)

    @no_retry
    def test_order_draft_timeout_lifecycle_and_pagination(self):
        self.browser_js('/?debug=assets', r"""
            (async () => {
                const {startChat} = odoo.loader.modules.get('@ab_storefront_callcenter_adapter/chat');
                if (!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/native_history')) throw new Error('Native recovery assets missing');
                await odoo.loader.modules.get('@web/core/l10n/translation').translationIsReady;
                const originalFetch = window.fetch;
                const root = document.createElement('section');
                root.dataset.chatIdentity = 'browser-test';
                root.innerHTML = '<div data-chat-history></div><div data-chat-status></div><form action="/recovery-test"><input name="csrf_token" value="test"/><textarea name="body"></textarea><button type="submit">Send</button></form>';
                document.body.append(root);
                const form = root.querySelector('form');
                const input = form.elements.body;
                const sent = [];
                let phase = 'initial';
                const wait = () => new Promise(resolve => setTimeout(resolve, 50));
                window.fetch = async (url, options) => {
                    if (url !== form.action) return originalFetch(url, options);
                    const id = options.body.get('event_uuid');
                    if (id) {
                        sent.push(id);
                        if (phase === 'lost') throw new Error('Lost acknowledgement');
                        input.value = 'Newer draft'; input.dispatchEvent(new Event('input'));
                    }
                    const after = options.body.get('after');
                    return {ok: true, json: async () => ({ready: true, account_identity: 'owner',
                        messages: [{key: after === '0' ? '1' : '2', direction: 'agent', body: 'Recovered ' + after}],
                        cursor: after === '0' ? '1' : '2', has_more: after === '0', acknowledged: id || false})};
                };
                try {
                    input.value = 'Draft typed before initialization';
                    startChat(root);
                    await wait(); await wait();
                    if (input.value !== 'Draft typed before initialization') throw new Error('Initialization cleared the existing draft');
                    if (root.querySelector('[data-chat-history]').children.length !== 2) throw new Error('Cursor catch-up failed');
                    input.value = 'Pending body'; input.dispatchEvent(new Event('input'));
                    phase = 'lost'; form.dispatchEvent(new Event('submit', {cancelable: true}));
                    await wait();
                    if (input.value !== 'Pending body') throw new Error('Unacknowledged draft lost');
                    phase = 'recover'; form.dispatchEvent(new Event('submit', {cancelable: true}));
                    await wait();
                    if (sent.length !== 2 || sent[0] !== sent[1]) throw new Error('Retry changed message UUID');
                    if (input.value !== 'Newer draft') throw new Error('Acknowledgement cleared newer draft');
                    window.dispatchEvent(new Event('pagehide')); window.dispatchEvent(new Event('pageshow'));
                    document.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('online'));
                    await wait();
                    if (input.value !== 'Newer draft') throw new Error('Lifecycle recovery cleared draft');
                } finally {
                    window.fetch = originalFetch;
                    root.remove();
                    for (let index = sessionStorage.length - 1; index >= 0; index--) {
                        const key = sessionStorage.key(index);
                        if (key.startsWith('ab.website.') && key.includes('recovery-test')) sessionStorage.removeItem(key);
                    }
                }
                console.log('test successful');
            })().catch(error => console.error(error));
        """, ready="!!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/chat')", login='admin', timeout=90)

    @no_retry
    def test_recovery_native_arabic_labels(self):
        self.env['res.lang']._activate_lang('ar_001')
        language = self.env['res.lang']._lang_get('ar_001')
        self.env.ref('website.default_website').language_ids += language
        self.env.ref('base.user_admin').lang = 'ar_001'
        self.browser_js('/%s/?debug=assets' % language.url_code, r"""
            (async () => {
                const translation = odoo.loader.modules.get('@web/core/l10n/translation');
                await translation.translationIsReady;
                const expected = {'Previous conversations': 'المحادثات السابقة',
                    'Retry pending message': 'إعادة محاولة الرسالة المعلقة',
                    'Message pending acknowledgement.': 'الرسالة في انتظار تأكيد الاستلام.',
                    'This website chat has ended.': 'انتهت محادثة الموقع هذه.'};
                for (const [source, target] of Object.entries(expected)) {
                    const actual = String(translation.appTranslateFn(source, 'ab_storefront_callcenter_adapter'));
                    if (actual !== target) throw new Error('Native Arabic label missing: ' + source + ' = ' + actual);
                }
                if (!document.documentElement.lang.startsWith('ar')) throw new Error('Arabic website context missing');
                console.log('test successful');
            })().catch(error => console.error(error));
        """, ready="!!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/native_history')", login='admin', timeout=90)


@tagged('post_install', '-at_install')
class TestRecoveryHTTP(TestCapture, HttpCase):
    @no_retry
    def test_signed_customer_existing_session_reopens(self):
        channel = self._chat_configuration()
        self.endpoint.lifecycle_enabled = True
        portal = self.env['res.users'].create({
            'name': 'Existing Website Customer', 'login': 'floating-existing-owner',
            'password': 'floating-existing-owner', 'company_id': self.website.company_id.id,
            'company_ids': [fields.Command.set(self.website.company_id.ids)],
            'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)],
        })
        public_channel = channel.with_user(portal)
        with MockRequest(self.env(user=portal.id, su=False), website=self.website):
            values = public_channel._get_livechat_discuss_channel_vals(**public_channel._get_operator_info(lang='en_US', country_id=False))
        previous = self.env['discuss.channel'].sudo().create(values)
        previous.with_user(portal).message_post(body='Earlier customer conversation', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.env['ab_storefront_callcenter_api'].with_user(self.worker).receive_v2(
            self.endpoint.source, 'livechat', previous.ab_callcenter_session_uuid, 'earlier-session-answer', 'Earlier agent reply')
        previous._close_livechat_session()
        values = dict(values, ab_callcenter_session_uuid=str(uuid4()))
        session = self.env['discuss.channel'].sudo().create(values)
        session.with_user(portal).message_post(body='Existing website conversation', message_type='comment', subtype_xmlid='mail.mt_comment')
        self.env['ab_storefront_callcenter_api'].with_user(self.worker).receive_v2(
            self.endpoint.source, 'livechat', session.ab_callcenter_session_uuid, 'existing-session-answer', 'Existing agent reply')
        self.browser_js('/?debug=assets', r'''
            (async () => {
                const compactKey = 'mail.user_setting.chathub_compact';
                localStorage.setItem(compactKey, 'true');
                window.dispatchEvent(new StorageEvent('storage', {key: compactKey, newValue: 'true', storageArea: localStorage}));
                const waitForWindow = async () => {
                    for (let i = 0; i < 200; i++) {
                        const root = document.querySelector('.o-livechat-root')?.shadowRoot;
                        const window = root?.querySelector('.o-mail-ChatWindow');
                        if (window?.querySelector('.o-mail-Composer-input') && window.getBoundingClientRect().height > 100 && root.textContent.includes('Existing agent reply')) return root;
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    const {App} = odoo.loader.modules.get('@odoo/owl');
                    const store = [...App.apps].map(app => app.env.services?.['mail.store']).find(Boolean);
                    throw new Error('Existing signed-in session did not reopen: ' + JSON.stringify({
                        active: store?.activeLivechats.map(thread => ({id: thread.id, transient: thread.isTransient, ended: !!thread.livechat_end_dt})),
                        compact: store?.chatHub.compact,
                        opened: store?.chatHub.opened.map(window => ({id: window.thread?.id, canShow: window.canShow, bypass: window.bypassCompact})),
                    }));
                };
                window.dispatchEvent(new Event('ab-storefront:open-livechat'));
                const root = await waitForWindow();
                const history = root.querySelector('.ab_website_history details');
                if (!history || !history.textContent.includes('Earlier agent reply')) throw new Error('Earlier agent history missing');
                history.open = true;
                await new Promise(resolve => requestAnimationFrame(resolve));
                if (!root.querySelector('.o-mail-ChatWindow .o-mail-Composer-input')) throw new Error('Archived history destroyed the live chat window');
                const fold = root.querySelector('button[title="Fold"], button[data-tooltip="Fold"]');
                if (fold) {
                    fold.click();
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                window.dispatchEvent(new Event('ab-storefront:open-livechat'));
                await waitForWindow();
                localStorage.removeItem(compactKey);
                console.log('test successful');
            })().catch(error => console.error(error));
        ''', ready="!!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/native') && document.body.classList.contains('ab-livechat-integrated')", login=portal.login, timeout=90)
        self.assertEqual(self.env['discuss.channel'].search_count([('ab_callcenter_user_id', '=', portal.id), ('livechat_end_dt', '=', False)]), 1)

    @no_retry
    def test_signed_customer_floating_roundtrip(self):
        channel = self._chat_configuration()
        self.endpoint.lifecycle_enabled = True
        portal = self.env['res.users'].create({
            'name': 'Saved Website Customer', 'login': 'floating-roundtrip-owner',
            'password': 'floating-roundtrip-owner',
            'company_id': self.website.company_id.id,
            'company_ids': [fields.Command.set(self.website.company_id.ids)],
            'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)],
        })
        original = type(self.env['discuss.channel'])._message_post_after_hook
        worker_id = self.worker.id

        def reply_after_post(record, message, values):
            result = original(record, message, values)
            if record.ab_callcenter_endpoint_id and str(message.body) == '<p>Floating roundtrip question</p>':
                record.env['ab_storefront_callcenter_api'].with_user(worker_id).receive_v2(
                    record.ab_callcenter_endpoint_id.source, 'livechat', record.ab_callcenter_session_uuid,
                    'floating-roundtrip-answer', 'Floating roundtrip agent answer')
            return result

        with patch.object(type(self.env['discuss.channel']), '_message_post_after_hook', reply_after_post):
            self.browser_js('/?debug=assets', r'''
                (async () => {
                    const wait = async (selector, description) => {
                        for (let i = 0; i < 200; i++) {
                            const root = document.querySelector('.o-livechat-root')?.shadowRoot;
                            const element = root?.querySelector(selector);
                            if (element) return element;
                            await new Promise(resolve => setTimeout(resolve, 50));
                        }
                        throw new Error(description);
                    };
                    const compactKey = 'mail.user_setting.chathub_compact';
                    localStorage.setItem(compactKey, 'true');
                    window.dispatchEvent(new StorageEvent('storage', {key: compactKey, newValue: 'true', storageArea: localStorage}));
                    await new Promise(resolve => requestAnimationFrame(resolve));
                    window.dispatchEvent(new Event('ab-storefront:open-livechat'));
                    const input = await wait('.o-mail-Composer-input', 'Chat window did not open');
                    input.value = 'Floating roundtrip question';
                    input.dispatchEvent(new Event('input', {bubbles: true}));
                    input.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', bubbles: true, cancelable: true}));
                    for (let i = 0; i < 250; i++) {
                        const root = document.querySelector('.o-livechat-root')?.shadowRoot;
                        if (root?.textContent.includes('Floating roundtrip agent answer') && root.querySelector('.o-mail-ChatWindow .o-mail-Composer-input')) {
                            if (root.querySelector('.o-mail-ChatWindow').getBoundingClientRect().height < 100) throw new Error('Reply window is collapsed');
                            window.dispatchEvent(new Event('ab-storefront:open-livechat'));
                            await new Promise(resolve => setTimeout(resolve, 100));
                            if (!root.querySelector('.o-mail-ChatWindow .o-mail-Composer-input')) throw new Error('Existing conversation could not reopen');
                            localStorage.removeItem(compactKey);
                            console.log('test successful');
                            return;
                        }
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    throw new Error('Floating chat failed to remain open after sending and receiving a reply');
                })().catch(error => console.error(error));
            ''', ready="!!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/native') && document.body.classList.contains('ab-livechat-integrated')", login=portal.login, timeout=90)

        native_session = self.env['discuss.channel'].search([('ab_callcenter_user_id', '=', portal.id)])
        event = self.env['ab_storefront_callcenter_chat_event'].search([('message_id.res_id', '=', native_session.id)])
        self.assertEqual(event.envelope['identity']['name'], portal.partner_id.name)

    @no_retry
    def test_v4_native_javascript_voice_retry_and_decode(self):
        channel = self._chat_configuration()
        self.endpoint.media_enabled = True
        self.browser_js('/?debug=assets', r"""
            (async () => {
                const {Thread} = odoo.loader.modules.get('@mail/core/common/thread_model');
                const {nativeKey} = odoo.loader.modules.get('@ab_storefront_callcenter_adapter/native');
                const {rpc} = odoo.loader.modules.get('@web/core/network/rpc');
                const session = await rpc('/im_livechat/get_session', {channel_id: CHANNEL, persisted: true});
                const audioResponse = await fetch('/mail/static/src/audio/ting.ogg');
                const audioBytes = await audioResponse.arrayBuffer();
                const form = new FormData();
                form.set('csrf_token', odoo.csrf_token);
                form.set('thread_id', session.channel_id);
                form.set('thread_model', 'discuss.channel');
                form.set('is_pending', 'true');
                form.set('voice', 'true');
                form.set('ufile', new Blob([audioBytes], {type: 'audio/ogg'}), 'voice.ogg');
                const upload = await fetch('/mail/attachment/upload', {method: 'POST', body: form});
                const info = (await upload.json()).data;
                const file = info.store_data['ir.attachment'].find(file => file.id === info.attachment_id);
                if (!file.ownership_token) throw new Error('Attachment ownership token missing');
                form.delete('voice');
                form.set('ufile', new Blob([Uint8Array.from(atob('VIDEO_BYTES'), character => character.charCodeAt(0))], {type: 'video/mp4'}), 'video.mp4');
                const videoUpload = await fetch('/mail/attachment/upload', {method: 'POST', body: form});
                const videoInfo = (await videoUpload.json()).data;
                const videoFile = videoInfo.store_data['ir.attachment'].find(file => file.id === videoInfo.attachment_id);
                let received;
                const fake = {id: session.channel_id, channel_type: 'livechat', isTransient: false,
                    ab_callcenter_session_uuid: crypto.randomUUID(), ab_callcenter_identity_kind: 'visitor',
                    abEnsureWebsiteIdentity: async () => {}, addOrReplaceMessage() {}, onNewSelfMessage() {},
                    store: {env: {services: {'im_livechat.livechat': {options: {ab_callcenter: true}}}},
                        insert(data) {received = data;}, 'mail.message': {get(id) {return {id};}}}};
                const key = nativeKey(fake);
                const original = Storage.prototype.setItem;
                let submission;
                Storage.prototype.setItem = function(k, value) {if (k === key) submission = value; return original.call(this, k, value);};
                try {
                    const first = await Thread.prototype.post.call(fake, '', {attachments: [file, videoFile]});
                    if (!first || sessionStorage.getItem(key)) throw new Error('Native attachment-only message was not acknowledged');
                    original.call(sessionStorage, key, submission);
                    const retry = await Thread.prototype.post.call(fake, '', {attachments: [file, videoFile]});
                    if (retry.id !== first.id) throw new Error('Voice retry created a second message');
                    const attachment = received['ir.attachment'].find(row => row.id === file.id);
                    if (!attachment.voice_ids?.length) throw new Error('Voice metadata lost');
                    const response = await fetch('/web/content/' + file.id + '?access_token=' + encodeURIComponent(attachment.raw_access_token));
                    if (!response.ok) throw new Error('Voice download denied');
                    const audio = new AudioContext();
                    try {
                        const decoded = await audio.decodeAudioData(await response.arrayBuffer());
                        if (!decoded.duration) throw new Error('Voice cannot be played');
                    } finally { await audio.close(); }
                    const videoAttachment = received['ir.attachment'].find(row => row.id === videoFile.id);
                    const videoResponse = await fetch('/web/content/' + videoFile.id + '?access_token=' + encodeURIComponent(videoAttachment.raw_access_token));
                    if (!videoResponse.ok) throw new Error('Video download denied');
                    const video = document.createElement('video');
                    const url = URL.createObjectURL(await videoResponse.blob());
                    try {
                        await new Promise((resolve, reject) => {
                            const timeout = setTimeout(() => reject(new Error('Video cannot be played')), 5000);
                            video.onloadedmetadata = () => {clearTimeout(timeout); resolve();};
                            video.onerror = () => {clearTimeout(timeout); reject(new Error('Video decoding failed'));};
                            video.src = url;
                        });
                        if (!video.duration) throw new Error('Video duration missing');
                    } finally {URL.revokeObjectURL(url);}
                } finally {
                    Storage.prototype.setItem = original;
                    sessionStorage.removeItem(key);
                }
                console.log('test successful');
            })().catch(error => console.error(error));
        """.replace('CHANNEL', str(channel.id)).replace('VIDEO_BYTES', 'AAAAJGZ0eXBpc29tAAACAGlzb21pc282aXNvMmF2YzFtcDQxAAAC7m1vb3YAAABsbXZoZAAAAAAAAAAAAAAAAAAAA+gAAAAAAAEAAAEAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIAAAHwdHJhawAAAFx0a2hkAAAAAwAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAQAAAAABAAAAAQAAAAAABjG1kaWEAAAAgbWRoZAAAAAAAAAAAAAAAAAAAMgAAAAAAVcQAAAAAAC1oZGxyAAAAAAAAAAB2aWRlAAAAAAAAAAAAAAAAVmlkZW9IYW5kbGVyAAAAATdtaW5mAAAAFHZtaGQAAAABAAAAAAAAAAAAAAAkZGluZgAAABxkcmVmAAAAAAAAAAEAAAAMdXJsIAAAAAEAAAD3c3RibAAAAKtzdHNkAAAAAAAAAAEAAACbYXZjMQAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAABAAEAASAAAAEgAAAAAAAAAARVMYXZjNjAuMzEuMTAyIGxpYngyNjQAAAAAAAAAAAAAABj//wAAADVhdmNDAWQACv/hABhnZAAKrNlEJsBEAAADAAQAAAMAyDxIllgBAAZo6+PLIsD9+PgAAAAAEHBhc3AAAAABAAAAAQAAABBzdHRzAAAAAAAAAAAAAAAQc3RzYwAAAAAAAAAAAAAAFHN0c3oAAAAAAAAAAAAAAAAAAAAQc3RjbwAAAAAAAAAAAAAAKG12ZXgAAAAgdHJleAAAAAAAAAABAAAAAQAAAAAAAAAAAAAAAAAAAGJ1ZHRhAAAAWm1ldGEAAAAAAAAAIWhkbHIAAAAAAAAAAG1kaXJhcHBsAAAAAAAAAAAAAAAALWlsc3QAAAAlqXRvbwAAAB1kYXRhAAAAAQAAAABMYXZmNjAuMTYuMTAwAAAAsG1vb2YAAAAQbWZoZAAAAAAAAAABAAAAmHRyYWYAAAAkdGZoZAAAADkAAAABAAAAAAAAAxIAAAIAAAAC3AEBAAAAAAAUdGZkdAEAAAAAAAAAAAAAAAAAAFh0cnVuAAAKBQAAAAgAAAC4AgAAAAAAAtwAAAQAAAAADgAACgAAAAAMAAAEAAAAAAwAAAAAAAAADAAAAgAAAAAUAAAIAAAAAA4AAAIAAAAADAAAAgAAAANEbWRhdAAAAq4GBf//qtxF6b3m2Ui3lizYINkj7u94MjY0IC0gY29yZSAxNjQgcjMxMDggMzFlMTlmOSAtIEguMjY0L01QRUctNCBBVkMgY29kZWMgLSBDb3B5bGVmdCAyMDAzLTIwMjMgLSBodHRwOi8vd3d3LnZpZGVvbGFuLm9yZy94MjY0Lmh0bWwgLSBvcHRpb25zOiBjYWJhYz0xIHJlZj0zIGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDM6MHgxMTMgbWU9aGV4IHN1Ym1lPTcgcHN5PTEgcHN5X3JkPTEuMDA6MC4wMCBtaXhlZF9yZWY9MSBtZV9yYW5nZT0xNiBjaHJvbWFfbWU9MSB0cmVsbGlzPTEgOHg4ZGN0PTEgY3FtPTAgZGVhZHpvbmU9MjEsMTEgZmFzdF9wc2tpcD0xIGNocm9tYV9xcF9vZmZzZXQ9LTIgdGhyZWFkcz0yIGxvb2thaGVhZF90aHJlYWRzPTEgc2xpY2VkX3RocmVhZHM9MCBucj0wIGRlY2ltYXRlPTEgaW50ZXJsYWNlZD0wIGJsdXJheV9jb21wYXQ9MCBjb25zdHJhaW5lZF9pbnRyYT0wIGJmcmFtZXM9MyBiX3B5cmFtaWQ9MiBiX2FkYXB0PTEgYl9iaWFzPTAgZGlyZWN0PTEgd2VpZ2h0Yj0xIG9wZW5fZ29wPTAgd2VpZ2h0cD0yIGtleWludD0yNTAga2V5aW50X21pbj0yNSBzY2VuZWN1dD00MCBpbnRyYV9yZWZyZXNoPTAgcmNfbG9va2FoZWFkPTQwIHJjPWNyZiBtYnRyZWU9MSBjcmY9MjMuMCBxY29tcD0wLjYwIHFwbWluPTAgcXBtYXg9NjkgcXBzdGVwPTQgaXBfcmF0aW89MS40MCBhcT0xOjEuMDAAgAAAACZliIQAN//+4QP4FNdN/mOPQ9kBaFXLkbcSjp8gDW8Tm/+RMQM11wAAAApBmiRsQz/+ni3wAAAACEGeQniF/wm5AAAACAGeYXRCvww4AAAACAGeY2pCvww5AAAAEEGaZ0moQWiZTAhX//44jcEAAAAKQZ6FRREsK/8MOQAAAAgBnqZqQr8MOQAAAENtZnJhAAAAK3RmcmEBAAAAAAAAAQAAAAAAAAABAAAAAAAABAAAAAAAAAADEgEBAQAAABBtZnJvAAAAAAAAAEM='), ready="!!odoo.loader.modules.get('@ab_storefront_callcenter_adapter/native')", timeout=90)

    def test_v4_native_http_voice_and_files_guest_and_customer(self):
        import json
        from odoo.http import Request
        from odoo.tools import file_open
        channel = self._chat_configuration()
        self.endpoint.media_enabled = True
        portal = self.env['res.users'].create({'name': 'Media HTTP owner', 'login': 'media-http', 'password': 'media-http',
            'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        for login in (None, portal.login):
            self.authenticate(login, login)
            def rpc(route, **params):
                return self.url_open(route, data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params, 'id': 1}),
                    headers={'Content-Type': 'application/json'}).json()
            created = rpc('/im_livechat/get_session', channel_id=channel.id, persisted=True)
            self.assertNotIn('error', created)
            session_id = created['result']['channel_id']
            uploads = []
            for filename, voice in [('addons/mail/static/src/audio/ting.ogg', True),
                                     ('addons/mail/tests/play.png', False),
                                     ('addons/mail/tests/discuss/files/test_unicode.pdf', False)]:
                with file_open(filename, 'rb') as file:
                    response = self.url_open('/mail/attachment/upload', data={
                        'csrf_token': Request.csrf_token(self), 'is_pending': 'true',
                        'thread_model': 'discuss.channel', 'thread_id': session_id, 'voice': 'true' if voice else '',
                    }, files={'ufile': file})
                self.assertEqual(response.status_code, 200)
                result = response.json()['data']
                info = next(row for row in result['store_data']['ir.attachment'] if row['id'] == result['attachment_id'])
                uploads.append({'id': info['id'], 'token': info['ownership_token']})
            event_uuid = str(uuid4())
            first = rpc('/storefront-callcenter/native/send', channel_id=session_id, body='', event_uuid=event_uuid, attachments=uploads)
            self.assertNotIn('error', first, first)
            repeated = rpc('/storefront-callcenter/native/send', channel_id=session_id, body='', event_uuid=event_uuid, attachments=uploads)
            self.assertEqual(first['result']['message_id'], repeated['result']['message_id'])
            event = self.env['ab_storefront_callcenter_chat_event'].search([('event_uuid', '=', event_uuid)])
            self.assertEqual({item['kind'] for item in event.envelope['attachments']}, {'image', 'voice', 'document'})
            self.assertEqual(len(event.message_id.attachment_ids), 3)
            if login:
                self.authenticate(None, None)
            forged = rpc('/storefront-callcenter/native/send', channel_id=session_id, body='', event_uuid=str(uuid4()),
                attachments=[dict(uploads[0], token='forged')])
            self.assertIn('error', forged)

    @no_retry
    def test_v4_portal_refresh_preserves_draft_and_receives_reply(self):
        self._portal_refresh_without_callcenter(True)

    @no_retry
    def test_notification_only_portal_chatter_works_with_bridge_disabled(self):
        self._portal_refresh_without_callcenter(False)

    def _portal_refresh_without_callcenter(self, bridge_enabled):
        import json
        self._chat_configuration()
        portal = self.env['res.users'].create({'name': 'Portal refresh owner', 'login': 'portal-refresh', 'password': 'portal-refresh',
            'partner_id': self.partner.id, 'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        cart = self.cart()
        cart._cart_add(self.product.id, 1)
        cart.action_confirm()
        api = self.env['ab_storefront_callcenter_api'].with_user(self.worker)
        initial = api.fetch_v1(self.endpoint.source)[0]
        if not bridge_enabled:
            self.endpoint.write({'chat_enabled': False, 'enabled': False})
        import hashlib
        from ..models.adapter import _CAPTURE
        guard = _CAPTURE.set(True)
        try:
            cart.write({'ab_callcenter_owner_hash': hashlib.sha256(('user:' + str(portal.id)).encode()).hexdigest()})
        finally:
            _CAPTURE.reset(guard)
        self.browser_js('/my/orders/%s?access_token=%s&debug=assets' % (cart.id, cart._portal_ensure_token()), r"""
            (async () => {
                await odoo.portalChatterReady;
                let shadow;
                for (let i = 0; i < 100; i++) {
                    shadow = document.querySelector('#chatterRoot')?.shadowRoot;
                    if (shadow?.querySelector('.ab_order_chat_refresh')) break;
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                const refresh = shadow?.querySelector('.ab_order_chat_refresh button');
                if (!refresh) throw new Error('Scoped refresh button missing');
                const input = shadow.querySelector('textarea.o-mail-Composer-input');
                if (!input) throw new Error('Order composer missing');
                if (document.body.innerText.includes('Order chat is waiting for Callcenter acknowledgement.')) throw new Error('Internal acknowledgement notice exposed');
                input.value = 'Unsent portal draft';
                input.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: input.value}));
                const {rpc} = odoo.loader.modules.get('@web/core/network/rpc');
                await rpc('/mail/message/post', {thread_model: 'sale.order', thread_id: ORDER, token: new URL(location.href).searchParams.get('access_token'),
                    post_data: {body: 'Automatic portal response', message_type: 'comment', subtype_xmlid: 'mail.mt_comment'}});
                for (let i = 0; i < 70; i++) {
                    if (shadow.textContent.includes('Automatic portal response')) break;
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
                if (!shadow.textContent.includes('Automatic portal response')) throw new Error('Polling did not receive response');
                if (input.value !== 'Unsent portal draft') throw new Error('Polling cleared draft');
                refresh.click();
                await new Promise(resolve => setTimeout(resolve, 500));
                if (input.value !== 'Unsent portal draft') throw new Error('Manual refresh cleared draft');
                console.log('test successful');
            })().catch(error => console.error(error));
        """.replace('ORDER', str(cart.id)), ready="!!odoo.portalChatterReady", login=portal.login, timeout=90)
        cart.invalidate_recordset()
        self.assertEqual(cart.state, 'sale')
        initial_record = self.env['ab_storefront_callcenter_event'].search([
            ('event_uuid', '=', initial['event_uuid'])])
        self.assertFalse(initial_record.acknowledged)
        self.assertTrue(cart.ab_callcenter_chat_ready)
        events = self.env['ab_storefront_callcenter_chat_event'].search([
            ('message_id.model', '=', 'sale.order'), ('message_id.res_id', '=', cart.id)])
        if bridge_enabled:
            self.assertEqual(len(events), 1)
            self.assertFalse(api.fetch_v2(self.endpoint.source))
            api.acknowledge_v1(self.endpoint.source, initial['event_uuid'], initial['fingerprint'])
            self.assertEqual(api.fetch_v2(self.endpoint.source)[0]['body'], 'Automatic portal response')
        else:
            self.assertFalse(events)

    def test_recovery_native_http_retry_resume_and_history(self):
        import json
        channel = self._chat_configuration()
        self.endpoint.lifecycle_enabled = True
        portal = self.env['res.users'].create({'name': 'HTTP recovery owner', 'login': 'http-recovery-owner',
            'password': 'test-recovery-password',
            'group_ids': [fields.Command.set(self.env.ref('base.group_portal').ids)]})
        self.authenticate(portal.login, 'test-recovery-password')

        def call(route, **values):
            result = self.url_open(route, data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': values, 'id': 1}),
                headers={'Content-Type': 'application/json'}).json()
            self.assertNotIn('error', result, result.get('error', {}).get('message'))
            return result['result']

        session_id = call('/im_livechat/get_session', channel_id=channel.id, persisted=True)['channel_id']
        token = str(uuid4())
        first = call('/storefront-callcenter/native/send', channel_id=session_id, body='<p>Recovered native body</p>', event_uuid=token)
        replay = call('/storefront-callcenter/native/send', channel_id=session_id, body='<p>Recovered native body</p>', event_uuid=token)
        self.assertEqual(first['message_id'], replay['message_id'])
        self.assertEqual(first['acknowledged'], token)
        distinct = call('/storefront-callcenter/native/send', channel_id=session_id, body='<p>Recovered native body</p>', event_uuid=str(uuid4()))
        self.assertNotEqual(first['message_id'], distinct['message_id'])
        restored = call('/im_livechat/get_session', channel_id=channel.id, persisted=True)
        self.assertEqual(restored['channel_id'], session_id)
        opened = call('/im_livechat/get_session', channel_id=channel.id, persisted=False)
        self.assertEqual(opened['channel_id'], session_id)
        session = self.env['discuss.channel'].browse(session_id)
        session._close_livechat_session()
        transient = call('/im_livechat/get_session', channel_id=channel.id, persisted=False)
        self.assertLess(transient['channel_id'], 0)
        replacement = call('/im_livechat/get_session', channel_id=channel.id, persisted=True)['channel_id']
        self.assertNotEqual(replacement, session_id)
        history = call('/storefront-callcenter/native/history', channel_id=replacement)
        self.assertIn('Recovered native body', [message['body'] for message in history['previous']])
        self.opener.cookies.clear()
        denied = self.url_open('/storefront-callcenter/native/history', data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
            'params': {'channel_id': replacement}, 'id': 2}), headers={'Content-Type': 'application/json'}).json()
        self.assertIn('error', denied)
