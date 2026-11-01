import base64
from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user


@tagged('post_install', '-at_install')
class TestClaimHttp(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if hasattr(type(cls.env['res.users']), '_client_ip'):
            cls.enterClassContext(patch.object(type(cls.env['res.users']), '_client_ip', return_value='127.0.0.1'))
        cls.roles = ('user', 'inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts', 'reviewer', 'admin')
        cls.users = {role: new_test_user(cls.env(context=dict(cls.env.context, no_reset_password=True)),
            login='scc_http_' + role, password='claim-test-password',
            groups='ab_supplier_claim_cycle.supplier_claim_group_' + role) for role in cls.roles}
        supplier = cls.env['ab_costcenter'].create({'name': 'HTTP supplier', 'code': '1-http'})
        cls.claim = cls.env['ab_supplier_claim_cycle'].with_user(cls.users['user']).create({
            'supplier_id': supplier.id, 'num_of_invoice': 1, 'area': 'north', 'claim_amount': 100,
            'type_of_invoice': 'original', 'payment_nature': 'check', 'tax_classification': 'tax_payment'})
        cls.claim.action_submit()
        for department in ('inventory', 'purchasing'):
            cls.claim.with_user(cls.users[department]).action_decide(department, 'approved')
        cls.content = base64.b64encode(b'%PDF-1.4 claim test evidence')
        cls.claim.with_user(cls.users['tax']).write({'tax_review_attachment': cls.content,
            'tax_review_filename': 'tax.pdf', 'tax_discount_decision': 'apply'})
        cls.claim.with_user(cls.users['tax']).action_decide('tax', 'approved')
        cls.claim.with_user(cls.users['supplier_accounts']).write({'supplier_cheque_attachment': cls.content,
            'supplier_cheque_filename': 'supplier.pdf'})
        cls.claim.with_user(cls.users['supplier_accounts']).action_decide('supplier_accounts', 'approved')
        cls.claim.write({'payment_request_attachment': cls.content, 'payment_request_filename': 'request.pdf'})
        cls.claim.action_prepare_payment()
        cls.claim.with_user(cls.users['bank_accounts']).write({'bank_cheque_attachment': cls.content,
            'bank_cheque_filename': 'bank.pdf'})
        cls.claim.with_user(cls.users['bank_accounts']).action_decide('bank_accounts', 'approved')
        cls.claim.action_close()
        cls.claim.with_user(cls.users['admin']).write({'active': False})

    def test_all_roles_download_closed_archived_documents(self):
        for role in self.roles:
            self.authenticate(self.users[role].login, 'claim-test-password')
            for kind in ('supplier_cheque', 'tax_review', 'payment_request', 'bank_cheque'):
                response = self.url_open(f'/web/content/ab_supplier_claim_cycle/{self.claim.id}/{kind}_attachment?download=true')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, base64.b64decode(self.content))

    def test_unified_form_renders(self):
        self.browser_js(f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.claim.id}', """
            const deadline = Date.now() + 30000;
            const timer = setInterval(() => {
                const timeline = document.querySelector('.o_scc_top_timeline');
                const entry = document.querySelector('.o_scc_entry_grid');
                const details = document.querySelector('.o_scc_workflow_box');
                const documents = document.querySelector('.o_scc_documents');
                const departments = ['inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts'];
                if (timeline && entry && details && documents &&
                    document.querySelector('.o_field_widget[name="net_claim_amount"]') &&
                    timeline.querySelectorAll(':scope > .o_scc_route_step').length === 6 &&
                    timeline.querySelectorAll('.o_scc_parallel_stage').length === 2 &&
                    departments.every(department => Array.from(timeline.querySelectorAll(`.o_field_widget[name="${department}_decision"]`)).filter(node => node.getClientRects().length).length === 1) &&
                    !timeline.querySelector('.o_kanban_record') &&
                    !details.closest('.o_scc_top_tracking') &&
                    (timeline.compareDocumentPosition(entry) & Node.DOCUMENT_POSITION_FOLLOWING) &&
                    (documents.compareDocumentPosition(details) & Node.DOCUMENT_POSITION_FOLLOWING)) {
                    clearInterval(timer);
                    console.log('test successful');
                } else if (Date.now() > deadline) {
                    clearInterval(timer);
                    console.error('Claim form did not render');
                }
            }, 200);
        """, login=self.users['reviewer'].login, timeout=60)

    def test_arabic_form_renders(self):
        self.env['res.lang']._activate_lang('ar_001')
        self.env['ir.module.module'].search([('name', '=', 'ab_supplier_claim_cycle')])._update_translations(filter_lang=['ar_001'])
        self.users['reviewer'].lang = 'ar_001'
        self.browser_js(f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.claim.id}', """
            const deadline = Date.now() + 30000;
            const timer = setInterval(() => {
                if (document.querySelector('.o_field_widget[name="net_claim_amount"]') &&
                    document.body.textContent.includes('صافي مبلغ المطالبة') &&
                    Array.from(document.querySelectorAll('.o_scc_top_tracking summary')).some(node => node.textContent.trim() === 'تجهيز السكرتارية')) {
                    clearInterval(timer);
                    console.log('test successful');
                } else if (Date.now() > deadline) {
                    clearInterval(timer);
                    console.error('Arabic claim form did not render');
                }
            }, 200);
        """, login=self.users['reviewer'].login, timeout=60)
