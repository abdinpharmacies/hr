import copy
import unittest
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestCRMOMS(TransactionCase):
    test_tags = {"standard"}
    test_module = "ab_oms_core"
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        group = cls.env.ref('ab_crm_core.group_user')
        cls.staff = cls.env['res.users'].create({'name': 'CRM Test Staff', 'login': 'crm-test-staff',
            'group_ids': [fields.Command.set([cls.env.ref('base.group_user').id, group.id])],
            'company_id': cls.company.id, 'company_ids': [fields.Command.set(cls.company.ids)]})
        cls.other = cls.env['res.users'].create({'name': 'CRM Other Staff', 'login': 'crm-test-other',
            'group_ids': [fields.Command.set([cls.env.ref('base.group_user').id, group.id])],
            'company_id': cls.company.id, 'company_ids': [fields.Command.set(cls.company.ids)]})
        cls.branch = cls.env['ab_crm_branch'].create({'name': 'Test A', 'code': 'test-a', 'user_ids': [fields.Command.set(cls.staff.ids)]})
        cls.branch_b = cls.env['ab_crm_branch'].create({'name': 'Test B', 'code': 'test-b', 'user_ids': [fields.Command.set(cls.other.ids)]})
        cls.channel = cls.env['ab_crm_channel'].create({'name': 'Test Phone', 'code': 'test-phone', 'provider': 'phone', 'branch_id': cls.branch.id})
        cls.connection = cls.env['ab_oms_connection'].create({'name': 'Mock Branch', 'branch_id': cls.branch.id,
            'endpoint': 'https://branch.invalid', 'database': 'branch', 'db_serial': 10, 'store_serial': 20, 'api_key': 'test-only'})
        cls.connection._internal_write({'verified': True})

    def request(self):
        return self.env['ab_oms_request'].with_user(self.staff).create({'branch_id': self.branch.id,
            'customer_name': 'Test Customer', 'customer_phone': '01000000000', 'customer_reference': 123,
            'employee_reference': 234, 'approval_note': 'Confirmed by phone',
            'line_ids': [fields.Command.create({'name': 'Test Item', 'quantity': 2, 'price_unit': 12,
                'branch_product_reference': 345, 'unit_factor': 1})]})

    def submitted(self):
        request = self.request()
        request.action_claim()
        request.action_approve()
        request.action_submit()
        return request

    def test_standalone(self):
        for name in ('ab_sales', 'ab_sales_channel', 'ab_sales_lead', 'ab_hr'):
            module = self.env['ir.module.module'].search([('name', '=', name)])
            self.assertNotEqual(module.state, 'installed')

    def test_branch_header_line_isolation(self):
        request = self.request()
        with self.assertRaises(AccessError):
            request.with_user(self.other).read(['customer_name'])
        with self.assertRaises(AccessError):
            request.line_ids.with_user(self.other).read(['price_unit'])
        with self.assertRaises(AccessError):
            request.with_user(self.other).action_approve()
        self.assertFalse(self.env['ab_oms_request'].with_user(self.other).search([]))

    def test_reject_scope_reassignment(self):
        request = self.request()
        with self.assertRaises(AccessError):
            request.write({'branch_id': self.branch_b.id})
        with self.assertRaises(AccessError):
            request.line_ids.write({'request_id': request.id})

    def test_freeze_and_duplicate_submit(self):
        request = self.submitted()
        payload = copy.deepcopy(request.attempt_ids.payload)
        request.action_submit()
        self.assertEqual(len(request.attempt_ids), 1)
        with self.assertRaises(UserError):
            request.line_ids.write({'quantity': 3})
        with self.assertRaises(AccessError):
            request.attempt_ids.write({'payload': {}})
        self.assertEqual(request.attempt_ids.payload, payload)

    def test_approval_required(self):
        request = self.request()
        with self.assertRaises(UserError):
            request.action_submit()
        with self.assertRaises(AccessError):
            request.write({'state': 'approved'})

    def test_price_audit(self):
        request = self.request()
        request.line_ids.write({'price_unit': 14})
        audit = self.env['ab_oms_price_history'].search([('line_id', '=', request.line_ids.id)])
        self.assertEqual((audit.old_price, audit.new_price, audit.changed_by.id), (12, 14, self.staff.id))
        with self.assertRaises(AccessError):
            audit.with_user(self.staff).write({'old_price': 0})

    def test_note_does_not_assert_payment(self):
        request = self.submitted()
        note = self.env['ab_oms_note'].with_user(self.staff).create({'request_id': request.id, 'body': 'Branch contacted by phone'})
        self.assertEqual(request.paid_amount, 0)
        self.assertEqual(request.attempt_ids.state, 'prepending')
        with self.assertRaises(UserError):
            note.write({'body': 'changed'})

    def test_rejection_correction_restricts_identity(self):
        request = self.submitted()
        attempt = request.attempt_ids
        attempt._internal_write({'state': 'rejected', 'can_edit': True, 'queued': False})
        original = copy.deepcopy(attempt.payload)
        token = attempt.token
        attempt.correct_rejection([3], approval_note='Customer reconfirmed')
        self.assertEqual(attempt.token, token)
        self.assertEqual(attempt.revision, 2)
        self.assertEqual(attempt.payload['header'], original['header'])
        self.assertEqual(attempt.payload['lines'][0]['product_id'], original['lines'][0]['product_id'])
        self.assertEqual(attempt.payload['lines'][0]['qty_str'], '3')
        self.assertEqual(len(attempt.history), 1)

    def test_unknown_cannot_replace(self):
        request = self.submitted()
        request.attempt_ids._internal_write({'state': 'unknown'})
        with self.assertRaises(UserError):
            request.action_replacement()
        with self.assertRaises(UserError):
            request.attempt_ids.correct_rejection([3], approval_note='No confirmation')

    def test_response_validation(self):
        attempt = self.submitted().attempt_ids
        valid = {'token': attempt.token, 'request_revision': 1, 'submission_guard_version': 1,
                 'status': 'pending', 'branch_header_id': 12, 'eplus_serial': 234}
        with self.assertRaises(UserError):
            attempt._apply_result(dict(valid, token='other'))
        attempt._apply_result(valid)
        with self.assertRaises(UserError):
            attempt._apply_result(dict(valid, status='rejected', eplus_serial=0))
        self.assertEqual(attempt.state, 'pending')

    def test_manager_bypass_without_branch_membership(self):
        manager = self.env['res.users'].create({'name': 'CRM Manager Test', 'login': 'crm-manager-test',
            'group_ids': [fields.Command.set([self.env.ref('base.group_user').id, self.env.ref('ab_crm_core.group_manager').id])],
            'company_id': self.company.id, 'company_ids': [fields.Command.set(self.company.ids)]})
        request = self.request().with_user(manager)
        self.assertFalse(request.env.su)
        self.assertEqual(request.customer_name, 'Test Customer')
        self.assertNotIn(manager, self.branch.user_ids)

    def test_credentials_not_readable_by_staff(self):
        with self.assertRaises(AccessError):
            self.connection.with_user(self.staff).read(['api_key'])

    def test_gateway_role_required(self):
        with self.assertRaises(AccessError):
            self.env['ab_crm_gateway_api'].with_user(self.staff).receive_message('test-phone', '1', 'phone', 'Hello')

    def test_context_cannot_forge_approval(self):
        request = self.env['ab_oms_request'].with_user(self.staff).with_context(default_state='approved', default_paid_amount=100).create({
            'branch_id': self.branch.id, 'customer_name': 'Test', 'customer_phone': '123'})
        self.assertEqual(request.state, 'draft')
        self.assertEqual(request.paid_amount, 0)


    def service(self):
        return self.env['res.users'].create({'name': 'Test Integration', 'login': 'crm-integration',
            'group_ids': [fields.Command.set([self.env.ref('base.group_user').id,
                self.env.ref('ab_crm_core.group_manager').id, self.env.ref('ab_crm_gateway.group_gateway').id,
                self.env.ref('ab_oms_branch_adapter.group_worker').id, self.env.ref('ab_oms_sync.group_sync').id,
                self.env.ref('ab_oms_website_adapter.group_sync').id])],
            'company_id': self.company.id, 'company_ids': [fields.Command.set(self.company.ids)]})

    def website_event(self, revision=1, paid=0):
        return {'source': 'test-site', 'event_id': 'event-%s' % revision, 'reference': 'order-1', 'revision': revision,
                'snapshot': {'currency': self.company.currency_id.name, 'paid_amount': paid, 'payments': [],
                'customer': {'name': 'Website Customer', 'phone': '123'}, 'lines': [
                    {'name': 'Website Item', 'product': 'site-1', 'unit': 'unit-1', 'quantity': 2, 'price_unit': 12}]}}

    def website_channel(self):
        return self.env['ab_crm_channel'].create({'name': 'Test Website', 'code': 'test-site', 'provider': 'website', 'branch_id': self.branch.id})

    def test_gateway_deduplication(self):
        service = self.service()
        api = self.env['ab_crm_gateway_api'].with_user(service)
        first = api.receive_message('test-phone', 'event-1', 'sender', 'Hello')
        second = api.receive_message('test-phone', 'event-1', 'sender', 'Hello')
        self.assertEqual(first, second)
        with self.assertRaises(ValidationError):
            api.receive_message('test-phone', 'event-1', 'sender', 'Different')

    def test_web_event_duplicate_and_out_of_order(self):
        self.website_channel()
        api = self.env['ab_oms_sync_event'].with_user(self.service())
        first = api.receive_event('test-site', self.website_event(3))
        self.assertEqual(first, api.receive_event('test-site', self.website_event(3)))
        old = api.receive_event('test-site', self.website_event(2))
        self.assertEqual(api.browse(old['id']).state, 'obsolete')
        request = api.browse(first['id']).request_id
        self.assertEqual(request.source_revision, 3)
        self.assertEqual(len(request.line_ids), 1)

    def test_newer_web_revision_preserves_staff_work(self):
        self.website_channel()
        api = self.env['ab_oms_sync_event'].with_user(self.service())
        first = api.receive_event('test-site', self.website_event())
        request = api.browse(first['id']).request_id
        request.line_ids.write({'quantity': 5})
        new = api.receive_event('test-site', self.website_event(2, paid=12))
        self.assertEqual(api.browse(new['id']).state, 'review')
        self.assertEqual(request.line_ids.quantity, 5)
        self.assertEqual(request.paid_amount, 12)

    def test_prepaid_cannot_submit(self):
        request = self.request()
        request._internal_write({'paid_amount': 10})
        request.action_claim()
        with self.assertRaises(UserError):
            request.action_approve()

    def test_lost_branch_response_preserves_original(self):
        import requests
        request = self.submitted()
        attempt = request.attempt_ids.with_user(self.service())
        original = copy.deepcopy(attempt.payload)
        lease = self.env['ab_oms_attempt'].with_user(attempt.env.user).lease_submission()
        self.assertEqual(lease['id'], attempt.id)
        with patch.object(type(self.connection), '_call', side_effect=requests.Timeout()):
            attempt.deliver_submission(1)
        self.assertEqual(attempt.state, 'unknown')
        self.assertFalse(attempt.queued)
        self.assertEqual(attempt.payload, original)
        attempt.with_user(self.staff).action_retry()
        self.assertTrue(attempt.queued)
        self.assertEqual(attempt.revision, 1)

    def test_company_isolation(self):
        company = self.env['res.company'].create({'name': 'CRM Other Company'})
        branch = self.env['ab_crm_branch'].with_company(company).create({'name': 'Other Company Branch', 'code': 'other'})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.env['ab_oms_request'].with_user(self.staff).create({'branch_id': branch.id,
                'company_id': company.id, 'customer_name': 'Other Company', 'customer_phone': '123'})

    def test_website_checkout_does_not_execute_stock(self):
        from datetime import timedelta
        website = self.env['website'].search([], limit=1)
        website.write({'oms_enabled': True, 'oms_cutoff': fields.Datetime.now() - timedelta(hours=1), 'oms_source': 'test-site'})
        partner = self.env['res.partner'].create({'name': 'Website Test Customer', 'phone': '123'})
        product = self.env['product.product'].create({'name': 'Test Website Product', 'type': 'consu', 'list_price': 12})
        order = self.env['sale.order'].create({'partner_id': partner.id, 'website_id': website.id,
            'order_line': [fields.Command.create({'product_id': product.id, 'product_uom_qty': 2})]})
        order.action_confirm()
        self.assertEqual(order.state, 'sent')
        self.assertTrue(order.oms_request_reference)
        first_revision = order.oms_revision
        order.action_confirm()
        self.assertEqual(order.oms_revision, first_revision)
        if 'picking_ids' in order._fields:
            self.assertFalse(order.picking_ids)
        order.action_cancel()
        self.assertEqual(order.state, 'sent')
        self.assertTrue(order.oms_cancellation_requested)
        self.assertEqual(order.oms_revision, first_revision + 1)


    def test_replacement_retires_original_and_clears_mappings(self):
        request = self.submitted()
        request.attempt_ids._internal_write({'state': 'rejected', 'can_edit': True, 'queued': False})
        result = request.action_replacement()
        replacement = self.env['ab_oms_request'].browse(result['res_id'])
        self.assertEqual(replacement.replacement_of, request)
        self.assertEqual(replacement.state, 'draft')
        self.assertFalse(replacement.line_ids.branch_product_reference)
        self.assertTrue(request.attempt_ids.retired)
        with self.assertRaises(UserError):
            request.attempt_ids.action_retry()

    def test_mapping_scope_and_source(self):
        request = self.request()
        mapping = self.env['ab_oms_reference_map'].create({'name': 'Test Mapping', 'branch_id': self.branch.id,
            'source': 'test-site', 'product_reference': 'p1', 'unit_reference': 'u1', 'branch_product_reference': 876, 'unit_factor': 2})
        request.line_ids.write({'mapping_id': mapping.id})
        request.line_ids.action_apply_mapping()
        self.assertEqual(request.line_ids.branch_product_reference, 876)
        self.assertEqual(request.line_ids.unit_factor, 2)
        with self.assertRaises(AccessError):
            mapping.with_user(self.other).read(['name'])


    def test_service_cannot_approve_customer_decision(self):
        request = self.request()
        request.action_claim()
        with self.assertRaises(AccessError):
            request.with_user(self.service()).action_approve()

    def test_website_service_receipt_and_status_ordering(self):
        from datetime import timedelta
        website = self.env['website'].search([], limit=1)
        website.write({'oms_enabled': True, 'oms_cutoff': fields.Datetime.now() - timedelta(hours=1), 'oms_source': 'test-site'})
        partner = self.env['res.partner'].create({'name': 'Status Test Customer', 'phone': '123'})
        product = self.env['product.product'].create({'name': 'Status Test Product', 'type': 'consu', 'list_price': 12})
        order = self.env['sale.order'].create({'partner_id': partner.id, 'website_id': website.id,
            'order_line': [fields.Command.create({'product_id': product.id, 'product_uom_qty': 1})]})
        order.action_confirm()
        service = self.service()
        api = self.env['ab_oms_website_event'].with_user(service)
        newer = {'event_id': 'newer-status', 'source': 'test-site', 'reference': order.oms_request_reference,
                 'oms_reference': 'oms-order', 'revision': 2, 'status': 'accepted', 'invoice_reference': 123}
        self.assertTrue(api.receive_update(newer)['received'])
        self.assertTrue(api.receive_update(newer)['received'])
        api.receive_update(dict(newer, event_id='older-status', revision=1, status='review'))
        self.assertEqual(order.oms_status, 'accepted')
        self.assertEqual(order.oms_status_revision, 2)
        self.assertEqual(order.state, 'sent')
        with self.assertRaises(AccessError):
            order.with_user(service).write({'note': 'Unauthorized business edit'})


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCRMOMS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise RuntimeError('CRM/OMS acceptance tests failed')
