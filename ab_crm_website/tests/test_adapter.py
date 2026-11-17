from copy import deepcopy
from uuid import uuid4
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged
from ..protocol import fingerprint


@tagged('post_install', '-at_install')
class TestWebsiteAdapter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.source = str(uuid4())
        cls.env.company.country_id = cls.env.ref('base.eg')
        cls.staff = cls.env['res.users'].create(
            {
                'name': 'Website staff',
                'login': 'website-staff',
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
                'name': 'Website service',
                'login': 'website-service',
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
        cls.other = cls.env['res.users'].create(
            {
                'name': 'Other staff',
                'login': 'website-other',
                'group_ids': [
                    fields.Command.set(
                        [
                            cls.env.ref('base.group_user').id,
                            cls.env.ref('ab_crm_core.group_user').id,
                        ]
                    )
                ],
            }
        )
        cls.branch = cls.env['ab_crm_branch'].create(
            {
                'name': 'Website branch',
                'code': 'website-test',
                'user_ids': [fields.Command.set((cls.staff | cls.service).ids)],
            }
        )
        cls.channel = cls.env['ab_crm_channel'].create(
            {
                'name': 'Website',
                'code': 'website-test',
                'provider': 'website',
                'branch_id': cls.branch.id,
            }
        )
        cls.account = cls.env['ab_crm_messaging_account'].create(
            {
                'name': 'Website',
                'code': 'website-test',
                'provider': 'website',
                'provider_account': cls.source,
                'channel_id': cls.channel.id,
                'branch_id': cls.branch.id,
                'service_user_id': cls.service.id,
                'enabled': True,
                'legacy_worker_disabled': True,
                'outgoing_enabled': True,
            }
        )
        cls.gateway = cls.env['ab_crm_messaging_api'].with_user(cls.service)

    def event(self, revision=1, kind='order', order_uuid=None):
        event = {
            'version': 1,
            'source': self.source,
            'order_uuid': order_uuid or str(uuid4()),
            'event_uuid': str(uuid4()),
            'revision': revision,
            'kind': kind,
            'payload': (
                {
                    'reference': 'WEB-TEST',
                    'customer': {
                        'name': 'Customer',
                        'phone': '01012345678',
                        'address': 'Cairo Street 1',
                    },
                    'lines': [
                        {
                            'serial': '111',
                            'unit': 'box',
                            'name': 'Product',
                            'quantity': 2,
                            'price': 25,
                            'discount': 0,
                            'subtotal': 50,
                            'total': 50,
                        }
                    ],
                    'currency': 'EGP',
                    'total': 50,
                    'notes': '',
                    'payments': [],
                    'fulfillment': {'state': 'sale'},
                }
                if kind == 'order'
                else {'body': 'Hello'}
            ),
        }
        event['fingerprint'] = fingerprint(event)
        return event

    def receive(self, event, gateway=None):
        return (self.gateway if gateway is None else gateway).receive_website_event(
            self.account.code, self.source, event
        )

    def test_duplicate_conflict_and_revision_order(self):
        event = self.event()
        self.receive(event)
        self.receive(event)
        order = self.env['ab_crm_website_order'].search(
            [('order_uuid', '=', event['order_uuid'])]
        )
        self.assertEqual(len(order), 1)
        self.assertEqual(len(order.conversation_id.message_ids), 1)
        changed = deepcopy(event)
        changed['payload']['total'] = 60
        changed['fingerprint'] = fingerprint(changed)
        with self.assertRaises(ValidationError):
            self.receive(changed)
        with self.assertRaises(ValidationError):
            self.receive(self.event(3, 'message', event['order_uuid']))
        chat = self.event(2, 'message', event['order_uuid'])
        self.receive(chat)
        self.assertEqual(order.revision, 2)
        self.assertEqual(len(order.conversation_id.message_ids), 2)
        with self.assertRaises(ValidationError):
            self.receive(self.event(2, 'message', event['order_uuid']))
        self.assertFalse(order.conversation_id.customer_id)
        self.assertEqual(order.phone, '+201012345678')

    def test_scope_and_immutable_evidence(self):
        event = self.event()
        with self.assertRaises(AccessError):
            self.receive(event, self.env['ab_crm_messaging_api'].with_user(self.staff))
        with self.assertRaises(AccessError):
            self.receive(event, self.env['ab_crm_messaging_api'].with_user(self.other))
        self.receive(event)
        order = self.env['ab_crm_website_order'].search(
            [('order_uuid', '=', event['order_uuid'])]
        )
        with self.assertRaises(AccessError):
            order.with_user(self.other).read(['snapshot'])
        with self.assertRaises(AccessError):
            order.with_user(self.staff).write({'snapshot': {}})
        with self.assertRaises(AccessError):
            order.write({'revision': 100})
        ledger = self.env['ab_crm_website_event'].search(
            [('event_uuid', '=', event['event_uuid'])]
        )
        with self.assertRaises(AccessError):
            ledger.write({'fingerprint': 'forged'})
        self.account.enabled = False
        with self.assertRaises(AccessError):
            self.receive(event)

    def test_unmapped_invoice_revision_remains_displayable(self):
        event = self.event()
        self.receive(event)
        order = self.env['ab_crm_website_order'].search(
            [('order_uuid', '=', event['order_uuid'])]
        )
        self.assertEqual(order._display_snapshot(order.snapshot)['lines'][0]['name'],
                         event['payload']['lines'][0]['name'])
        update = self.event(2, order_uuid=event['order_uuid'])
        update['payload']['total'] = 55
        update['fingerprint'] = fingerprint(update)
        self.receive(update)
        self.assertEqual(order.snapshot['total'], 55)
        self.assertEqual(order.progress, 'review')
        self.assertFalse(
            self.env['ab_sales_header'].search([('customer_id.name', '=', 'Customer')])
        )

    def test_source_and_company_scope_are_not_payload_controlled(self):
        event = self.event()
        wrong = deepcopy(event)
        wrong['source'] = str(uuid4())
        wrong['fingerprint'] = fingerprint(wrong)
        with self.assertRaises(AccessError):
            self.receive(wrong)
        with self.assertRaises(AccessError):
            self.gateway.receive_website_event('another-account', self.source, event)
        other_company = self.env['res.company'].create(
            {'name': 'Website other company'}
        )
        with self.assertRaises(AccessError):
            self.gateway.with_context(
                allowed_company_ids=other_company.ids
            ).receive_website_event(self.account.code, self.source, event)
        self.assertFalse(
            self.env['ab_crm_website_order'].search(
                [('order_uuid', '=', event['order_uuid'])]
            )
        )

    def test_unverified_orders_share_customer_screen_without_contact_merge(self):
        first, second = self.event(), self.event()
        self.receive(first)
        self.receive(second)
        orders = self.env['ab_crm_website_order'].search(
            [('account_id', '=', self.account.id)]
        )
        self.assertEqual(len(orders), 2)
        self.assertEqual(
            len(set(orders.conversation_id.mapped('customer_group_key'))), 1
        )
        self.assertFalse(orders.conversation_id.customer_id)
        self.assertEqual(len(orders.conversation_id), 1)

    def test_views_load_directly_from_source_in_xml_developer_mode(self):
        from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file
        from odoo.tools import file_path

        for name in ['orders_list', 'orders_form', 'mappings_list', 'mappings_form']:
            arch = get_view_arch_from_file(
                file_path('ab_crm_website/views/views.xml'), 'ab_crm_website.' + name
            )
            self.assertIn('<', arch)

    def test_free_and_paid_delivery_remain_invoice_evidence(self):
        event = self.event()
        event['payload']['lines'] = [
            {
                'serial': '',
                'unit': 'eplus_default',
                'name': 'Delivery',
                'quantity': 1,
                'price': 0,
                'discount': 0,
                'subtotal': 0,
                'total': 0,
                'is_delivery': True,
            }
        ]
        event['fingerprint'] = fingerprint(event)
        self.receive(event)
        order = self.env['ab_crm_website_order'].search(
            [('order_uuid', '=', event['order_uuid'])]
        )
        self.assertEqual(order._display_snapshot(order.snapshot)['lines'][0]['total'], 0)
        self.assertEqual(len(order.snapshot['lines']), 1)
        paid = self.event(2, order_uuid=event['order_uuid'])
        paid['payload']['lines'] = [
            dict(event['payload']['lines'][0], price=12, subtotal=12, total=12)
        ]
        paid['fingerprint'] = fingerprint(paid)
        self.receive(paid)
        self.assertEqual(order._display_snapshot(order.snapshot)['lines'][0]['total'], 12)

    def test_delivery_flag_must_be_boolean(self):
        event = self.event()
        event['payload']['lines'][0]['is_delivery'] = 'true'
        event['fingerprint'] = fingerprint(event)
        with self.assertRaises(ValidationError):
            self.receive(event)


    def test_invoice_presentation_keeps_evidence_and_removes_terms(self):
        event = self.event()
        event['payload']['notes'] = (
            '<p>Leave at reception</p><p>Terms: <a href="http://example.test/terms">terms</a></p>'
        )
        event['payload']['payments'] = [
            {'reference': 'COD-REF', 'provider': 'custom', 'method': 'cash_on_delivery',
             'state': 'pending', 'amount': event['payload']['total'], 'currency': 'EGP'}
        ]
        event['fingerprint'] = fingerprint(event)
        self.receive(event)
        order = self.env['ab_crm_website_order'].search([('order_uuid', '=', event['order_uuid'])])
        display = order.with_context(lang='en_US')._display_snapshot(order.snapshot)
        self.assertEqual(display['payment_method_label'], 'Cash on delivery')
        self.env['res.lang']._activate_lang('ar_001')
        self.assertEqual(order.with_context(lang='ar_001')._display_snapshot(order.snapshot)['payment_method_label'], 'الدفع عند الاستلام')
        self.assertEqual(display['display_notes'], 'Leave at reception')
        self.assertEqual(order.snapshot, event['payload'])
        unknown = dict(order.snapshot, payments=[{'reference': 'UNKNOWN', 'provider': 'custom'}])
        self.assertEqual(order.with_context(lang='en_US')._display_snapshot(unknown)['payment_method_label'], 'Not specified')

    def test_received_units_display_without_mapping_or_product_queries(self):
        for unit_name in (None, '', 'Source box', 'علبة'):
            event = self.event()
            if unit_name is not None:
                event['payload']['lines'][0]['unit_name'] = unit_name
            event['fingerprint'] = fingerprint(event)
            self.receive(event)
            self.receive(event)
            order = self.env['ab_crm_website_order'].search([
                ('order_uuid', '=', event['order_uuid']),
            ])
            with patch.object(type(self.env['ab_crm_website_mapping']), 'search',
                              side_effect=AssertionError('Mapping lookup')), patch.object(
                    type(self.env['ab_product']), 'search',
                    side_effect=AssertionError('Product lookup')):
                display = order._display_snapshot(order.snapshot)
            self.assertEqual(display['lines'], event['payload']['lines'])
            self.assertEqual(order.snapshot, event['payload'])
            self.assertEqual(len(order.conversation_id.message_ids.filtered(lambda m: m.website_order_id == order)), 1)

    def test_optional_unit_name_validation(self):
        for value in (None, False, 1, [], {}, 'x' * 10001):
            event = self.event()
            event['payload']['lines'][0]['unit_name'] = value
            event['fingerprint'] = fingerprint(event)
            with self.subTest(value=type(value).__name__), self.assertRaises(ValidationError):
                self.receive(event)

    def test_website_navigation_retains_read_only_orders(self):
        self.assertEqual(self.env.ref('ab_crm_website.orders_menu').parent_id,
                         self.env.ref('ab_crm_core.menu_root'))
        self.assertFalse(self.env.ref('ab_crm_website.mappings_menu').active)
        for name in ('orders_list', 'orders_form'):
            arch = self.env.ref('ab_crm_website.' + name)._get_combined_arch()
            for operation in ('create', 'edit', 'delete'):
                self.assertIn(arch.get(operation), ('0', 'false'))

    def test_invoice_delivery_address_and_snapshot_preservation(self):
        event = self.event()
        event['payload']['customer']['address'] = (
            '12 Main Street\nBuilding 3, floor 2\nAkhmim SHG 82511\nEgypt'
        )
        event['fingerprint'] = fingerprint(event)
        self.receive(event)
        order = self.env['ab_crm_website_order'].search([
            ('order_uuid', '=', event['order_uuid']),
        ])
        state = self.env['res.country.state'].search([
            ('country_id', '=', self.env.ref('base.eg').id), ('code', '=', 'SHG'),
        ])
        for language in ('en_US', 'ar_001'):
            display = order.with_context(lang=language)._display_snapshot(order.snapshot)
            self.assertEqual(display['display_delivery_address'],
                             state.name + ' | 12 Main Street Building 3, floor 2 Akhmim 82511')
        self.assertEqual(order.snapshot, event['payload'])
        for address, expected in [
            ('12 Main Street\nSHG\nEgypt', state.name + ' | 12 Main Street'),
            ('Unstructured\naddress', 'Unstructured address'),
            ('12 Main Street\nUNKNOWN\nEgypt', '12 Main Street UNKNOWN Egypt'),
            ('12 Main Street\nSHG\nUnknown country', '12 Main Street SHG Unknown country'),
            ('', ''),
        ]:
            with self.subTest(address=address):
                self.assertEqual(order._display_delivery_address(address), expected)

    def test_public_tracking_reference_is_separate_from_invoice_reference(self):
        event = self.event()
        event['payload']['public_reference'] = 'NO-151126-E4CRGK'
        event['fingerprint'] = fingerprint(event)
        self.receive(event)
        self.receive(event)
        order = self.env['ab_crm_website_order'].search([
            ('order_uuid', '=', event['order_uuid']),
        ])
        self.assertEqual(order.public_reference, 'NO-151126-E4CRGK')
        display = order._display_snapshot(order.snapshot)
        self.assertEqual(display['reference'], 'WEB-TEST')
        self.assertEqual(display['public_reference'], 'NO-151126-E4CRGK')
        legacy = dict(order.snapshot)
        legacy.pop('public_reference')
        self.assertEqual(order._display_snapshot(legacy)['public_reference'], order.public_reference)
        self.assertEqual(order.snapshot, event['payload'])
        self.assertEqual(len(order.conversation_id.message_ids), 1)
        with self.assertRaises(AccessError):
            order.with_user(self.staff).write({'public_reference': 'forged'})
        old_event = self.event()
        self.receive(old_event)
        old_order = self.env['ab_crm_website_order'].search([
            ('order_uuid', '=', old_event['order_uuid']),
        ])
        self.assertFalse(old_order._display_snapshot(old_order.snapshot)['public_reference'])
        for invalid in (None, False, 15, [], 'x' * 129):
            bad = self.event()
            bad['payload']['public_reference'] = invalid
            bad['fingerprint'] = fingerprint(bad)
            with self.assertRaises(ValidationError):
                self.receive(bad)
