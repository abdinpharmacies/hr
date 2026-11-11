from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_workspace import TestWorkspace


@tagged('post_install', '-at_install', 'crm_pos_handoff')
class TestPosHandoff(TestWorkspace):
    def _contact(self):
        return self.chatter_api.contact_save(self.session_token, {
            'name': 'CRM Only Contact', 'phone': '01012345678', 'address': 'Contact address',
        }, branch_id=self.branch.id)

    def _pos_session(self, employee=None):
        return self.env['ab_employee_access_sales_pos_session'].create({
            'service_user_id': self.staff.id, 'employee_id': (employee or self.employee).id,
            'profile_id': self.profile.id, 'store_id': self.store.id, 'device_uid': 'crm-pos-test',
        })

    def test_crm_contact_never_registers_customer(self):
        with patch.object(type(self.env['ab_sales_branch_client']), '_call', side_effect=AssertionError('External call')):
            contact = self._contact()
        self.assertFalse(contact['is_ab_customer'])
        self.assertFalse(contact['catalog_customer_id'])
        self.assertEqual(contact['phone'], '+201012345678')

    def test_explicit_customer_selection_and_master_isolation(self):
        contact = self._contact()
        customer = self.env['ab_customer'].create({'code': 'CRM-CORE', 'name': 'Core Customer', 'mobile_phone': '01012345678'})
        self.assertFalse(self.env['ab_crm_customer'].browse(contact['id']).is_ab_customer)
        selected = self.chatter_api.contact_pos_select(self.session_token, customer.id, contact_id=contact['id'])
        self.assertEqual(selected['catalog_customer_id'], customer.id)
        self.assertTrue(selected['is_ab_customer'])
        self.chatter_api.contact_save(self.session_token, {'name': 'Edited CRM Contact', 'phone': '01012345678', 'address': 'Edited'}, contact_id=contact['id'])
        self.assertEqual(customer.name, 'Core Customer')
        self.assertFalse(customer.address)
        self.chatter_api.contact_archive(self.session_token, contact['id'])
        self.assertTrue(customer.active)
        audit = self.env['ab_crm_workspace_audit'].search([('customer_id', '=', contact['id']), ('action', '=', 'pos_customer_selected')])
        self.assertEqual(audit.employee_id, self.employee)
        self.assertEqual(audit.values['new']['catalog_customer_id'], customer.id)

    def test_handoff_sessions_scope_and_exact_draft_customer(self):
        contact = self._contact()
        handoff = self.chatter_api.pos_handoff_start(self.session_token, contact['id'])
        self.assertEqual(handoff, self.chatter_api.pos_handoff_start(self.session_token, contact['id']))
        pos = self._pos_session()
        api = self.env['ab_sales_pos_api']
        with patch.object(type(api), '_require_pos_operation_session', return_value=pos):
            data = self.chatter_api.pos_handoff_prepare(self.session_token, handoff, pos.session_token, self.store.id)
            self.assertEqual(data['phone'], '01012345678')
            self.assertFalse(data['catalog_customer_id'])
            with self.assertRaises(AccessError):
                self.chatter_api.pos_handoff_prepare(self.session_token, handoff, pos.session_token, self.foreign_store.id)
            self.chatter_api.pos_handoff_claim(self.session_token, handoff, pos.session_token, 'crm-draft-test', self.store.id)
            with self.assertRaises(AccessError):
                self.chatter_api.pos_handoff_claim(self.session_token, handoff, pos.session_token, 'another-draft', self.store.id)
            customer = self.env['ab_customer'].create({'code': 'CRM-ACTUAL', 'name': 'Actually Selected', 'mobile_phone': '01112345678'})
            self.env['ab_sales_pos_draft_cache'].create({
                'pos_client_token': 'crm-draft-test', 'user_id': self.staff.id, 'employee_id': self.employee.id,
                'store_id': self.store.id, 'bill_json': {'crm_handoff_id': handoff,
                    'header': {'pos_client_token': 'crm-draft-test', 'store_id': self.store.id, 'customer_id': customer.id}, 'lines': []},
            })
            result = self.chatter_api.pos_handoff_sync(self.session_token, handoff, pos.session_token, 'crm-draft-test')
            self.assertEqual(result['catalog_customer_id'], customer.id)
            self.chatter_api.pos_handoff_sync(self.session_token, handoff, pos.session_token, 'crm-draft-test')
            self.assertEqual(self.env['ab_crm_workspace_audit'].search_count([('customer_id', '=', contact['id']), ('action', '=', 'pos_customer_selected')]), 1)

    def test_handoff_rejects_forged_sessions_and_direct_writes(self):
        contact = self._contact()
        handoff_id = self.chatter_api.pos_handoff_start(self.session_token, contact['id'])
        with self.assertRaises(AccessError):
            self.chatter_api.pos_handoff_prepare('forged-session-token-value', handoff_id, 'forged-pos-token')
        with self.assertRaises(UserError):
            self.chatter_api.pos_handoff_prepare(self.session_token, handoff_id, 'forged-pos-token')
        with self.assertRaises(AccessError):
            self.env['ab_crm_pos_handoff'].with_user(self.other).browse(handoff_id).read(['contact_id'])
        with self.assertRaises(AccessError):
            self.env['ab_crm_pos_handoff'].with_user(self.staff).browse(handoff_id).write({'draft_token': 'forged'})
        with self.assertRaises(AccessError):
            self.env['ab_crm_customer'].with_user(self.staff).browse(contact['id']).write({'catalog_customer_id': False})
        with self.assertRaises(AccessError):
            self.env['ab_crm_chatter_api'].with_user(self.other).contact_pos_select(self.session_token, 1, contact_id=contact['id'])
        other_employee = self.env['ab_hr_employee'].create({'name': 'Different POS Employee', 'barcode': 'OTHERPOS'})
        pos = self._pos_session(other_employee)
        with patch.object(type(self.env['ab_sales_pos_api']), '_require_pos_operation_session', return_value=pos):
            with self.assertRaises(AccessError):
                self.chatter_api.pos_handoff_prepare(self.session_token, handoff_id, pos.session_token)

    def test_search_suggests_ambiguous_customers_and_branch_lookup_is_explicit(self):
        self._contact()
        customers = self.env['ab_customer'].create([
            {'name': 'First Suggestion', 'code': 'CRM-SUGGEST1', 'mobile_phone': '01012345678'},
            {'name': 'Second Suggestion', 'code': 'CRM-SUGGEST2', 'mobile_phone': '01012345678'},
        ])
        with patch.object(type(self.env['ab_sales_pos_api']), 'pos_customer_lookup') as lookup:
            result = self.chatter_api.contact_pos_search(self.session_token, '+201012345678', self.branch.id)
            self.assertEqual({customer['id'] for customer in result['customers']}, set(customers.ids))
            lookup.assert_not_called()
        with patch.object(type(self.env['ab_sales_pos_api']), 'pos_customer_lookup', return_value={'status': 'not_found'}) as lookup:
            self.chatter_api.contact_pos_search(self.session_token, '01199887766', self.branch.id, lookup=True, store_id=self.store.id)
            lookup.assert_called_once_with(phone='01199887766', store_id=self.store.id)
        with self.assertRaises(AccessError):
            self.chatter_api.contact_pos_search(self.session_token, '01199887766', self.branch.id, lookup=True, store_id=self.foreign_store.id)

    def test_cross_company_archived_and_other_employee_drafts_are_rejected(self):
        contact = self._contact()
        handoff = self.chatter_api.pos_handoff_start(self.session_token, contact['id'])
        company = self.env['res.company'].create({'name': 'Other CRM Company'})
        with self.assertRaises(AccessError):
            self.chatter_api.with_context(allowed_company_ids=[company.id]).pos_handoff_start(self.session_token, contact['id'])
        pos = self._pos_session()
        other_employee = self.env['ab_hr_employee'].create({'name': 'Other Draft Employee', 'barcode': 'OTHERDRAFT'})
        self.env['ab_sales_pos_draft_cache'].create({
            'pos_client_token': 'other-employee-draft', 'user_id': self.staff.id, 'employee_id': other_employee.id,
            'store_id': self.store.id, 'bill_json': {'crm_handoff_id': handoff, 'header': {
                'pos_client_token': 'other-employee-draft', 'store_id': self.store.id}, 'lines': []},
        })
        with patch.object(type(self.env['ab_sales_pos_api']), '_require_pos_operation_session', return_value=pos):
            with self.assertRaises(AccessError):
                self.chatter_api.pos_handoff_sync(self.session_token, handoff, pos.session_token, 'other-employee-draft')
        self.chatter_api.contact_archive(self.session_token, contact['id'])
        with self.assertRaises(AccessError):
            self.chatter_api.pos_handoff_prepare(self.session_token, handoff, pos.session_token)

    def test_selected_phone_and_location_prefill_without_changing_contact(self):
        conversation = self.conversation()
        conversation.action_claim()
        contact = self._contact()
        updated = self.chatter_api.contact_phone_add(self.session_token, contact['id'], '01112345678',
            label='Delivery', reason='Customer confirmed delivery phone', customer_confirmed=True)
        selected_phone = next(phone for phone in updated['phones'] if phone['number'] == '+201112345678')
        message = self.location_message(name='Delivery place', address='Selected delivery street')
        handoff = self.chatter_api.pos_handoff_start(self.session_token, contact['id'],
            conversation_id=conversation.id, message_id=message.id, phone_id=selected_phone['id'])
        pos = self._pos_session()
        with patch.object(type(self.env['ab_sales_pos_api']), '_require_pos_operation_session', return_value=pos):
            result = self.chatter_api.pos_handoff_prepare(self.session_token, handoff, pos.session_token, self.store.id)
        self.assertEqual(result['phone'], '01112345678')
        self.assertEqual(result['address'], 'Selected delivery street')
        self.assertEqual(self.env['ab_crm_customer'].browse(contact['id'])._directory_data()['address'], 'Contact address')
        self.assertFalse(self.env['ab_crm_customer'].browse(contact['id']).catalog_customer_id)

    def test_native_draft_normalization_preserves_handoff_and_missing_details(self):
        raw = {'id': 'native-draft', 'crm_handoff_id': 17, 'crm_prefilled': True,
               'header': {'pos_client_token': 'native-draft', 'store_id': self.store.id,
                          'new_customer_name': '', 'new_customer_phone': '', 'new_customer_address': ''},
               'lines': []}
        result = self.env['ab_sales_pos_api']._draft_payload(raw, {self.store.id})
        self.assertEqual(result['crm_handoff_id'], 17)
        self.assertTrue(result['crm_prefilled'])
        self.assertEqual(result['header']['new_customer_phone'], '')
        self.assertNotIn('customer_id', result['header'])
