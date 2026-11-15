from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
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
        cls.endpoint = cls.env['ab_storefront_callcenter_endpoint'].create(
            {
                'name': 'Adapter',
                'website_id': cls.website.id,
                'service_user_id': cls.worker.id,
                'enabled': True,
                'cutoff': fields.Datetime.now() - timedelta(days=1),
            }
        )

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
        token = str(uuid4())
        api.receive_v1(self.endpoint.source, cart.ab_callcenter_uuid, token, 'Hello')
        api.receive_v1(self.endpoint.source, cart.ab_callcenter_uuid, token, 'Hello')
        with self.assertRaises(ValidationError):
            api.receive_v1(
                self.endpoint.source, cart.ab_callcenter_uuid, token, 'Changed'
            )
        self.assertEqual(
            self.env['ab_storefront_callcenter_reply'].search_count(
                [('order_id', '=', cart.id)]
            ),
            1,
        )
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
