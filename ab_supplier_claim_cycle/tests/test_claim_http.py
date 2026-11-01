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
                const documents = document.querySelector('.o_scc_workflow_details .nav-link[name="claim_documents"]');
                const chatter = document.querySelector('.o-mail-Chatter');
                const departments = ['inventory', 'purchasing', 'tax', 'supplier_accounts', 'bank_accounts'];
                if (timeline && entry && details && documents && chatter &&
                    document.querySelector('.o_field_widget[name="net_claim_amount"]') &&
                    timeline.querySelectorAll(':scope > .o_scc_route_step').length === 6 &&
                    timeline.querySelectorAll('.o_scc_parallel_stage').length === 2 &&
                    departments.every(department => Array.from(timeline.querySelectorAll(`.o_field_widget[name="${department}_decision"]`)).filter(node => node.getClientRects().length).length === 1) &&
                    !timeline.querySelector('.o_kanban_record') &&
                    !details.closest('.o_scc_top_tracking') &&
                    (timeline.compareDocumentPosition(entry) & Node.DOCUMENT_POSITION_FOLLOWING) &&
                    details.contains(documents) &&
                    !document.querySelector('.o_scc_documents')) {
                    clearInterval(timer);
                    documents.click();
                    const documentTimer = setInterval(() => {
                        const table = document.querySelector('.o_field_widget[name="document_ids"]');
                        if (table && table.querySelectorAll('.o_data_row').length >= 4 &&
                            table.textContent.includes('supplier.pdf') && table.textContent.includes('tax.pdf')) {
                            clearInterval(documentTimer);
                            console.log('test successful');
                        } else if (Date.now() > deadline) {
                            clearInterval(documentTimer);
                            console.error('Historical claim documents did not render');
                        }
                    }, 200);
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
                    document.querySelector('.o-mail-Chatter') &&
                    document.body.textContent.includes('صافي مبلغ المطالبة') &&
                    Array.from(document.querySelectorAll('.nav-link[name="claim_documents"]')).some(node => node.textContent.trim() === 'المستندات') &&
                    Array.from(document.querySelectorAll('.o_scc_top_tracking summary')).some(node => node.textContent.trim() === 'تجهيز السكرتارية')) {
                    clearInterval(timer);
                    console.log('test successful');
                } else if (Date.now() > deadline) {
                    clearInterval(timer);
                    console.error('Arabic claim form did not render');
                }
            }, 200);
        """, login=self.users['reviewer'].login, timeout=60)

    def _check_document_column_resizing(self, language, size):
        self.browser_size = size
        self.users['reviewer'].lang = language
        self.browser_js(f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.claim.id}', """
            (async () => {
                const waitFor = async (predicate) => {
                    const deadline = Date.now() + 30000;
                    while (!predicate()) {
                        if (Date.now() > deadline) throw new Error('Timed out waiting for document table');
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                };
                await waitFor(() => document.querySelector('.nav-link[name="claim_documents"]'));
                document.querySelector('.nav-link[name="claim_documents"]').click();
                await waitFor(() => document.querySelector('.o_field_widget[name="document_ids"] th[data-name="filename"] .o_resize'));
                const widget = document.querySelector('.o_field_widget[name="document_ids"]');
                const renderer = widget.querySelector('.o_list_renderer');
                const table = renderer.querySelector('table');
                const header = table.querySelector('th[data-name="filename"]');
                const handle = header.querySelector('.o_resize');
                const initialWidth = header.getBoundingClientRect().width;
                const sheet = widget.closest('.o_form_sheet');
                const originalSheetWidth = sheet.getBoundingClientRect().width;
                const x = handle.getBoundingClientRect().x;
                const y = header.getBoundingClientRect().y + 10;
                const direction = getComputedStyle(table).direction === 'rtl' ? -1 : 1;
                handle.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, button: 0, buttons: 1, clientX: x, clientY: y}));
                window.dispatchEvent(new PointerEvent('pointermove', {bubbles: true, buttons: 1, clientX: x + direction * 900, clientY: y}));
                await new Promise(resolve => requestAnimationFrame(resolve));
                window.dispatchEvent(new PointerEvent('pointerup', {bubbles: true, button: 0, clientX: x + direction * 900, clientY: y}));
                await new Promise(resolve => setTimeout(resolve, 200));
                if (header.getBoundingClientRect().width < initialWidth + 800) throw new Error('Column did not widen');
                if (renderer.scrollWidth <= renderer.clientWidth) throw new Error('Document renderer did not provide horizontal scrolling');
                if (renderer.getBoundingClientRect().width > widget.getBoundingClientRect().width + 2) throw new Error('Renderer escaped document widget');
                if (sheet.getBoundingClientRect().width > originalSheetWidth + 2) throw new Error('Column resize expanded the form');
                if (widget.getBoundingClientRect().right > sheet.getBoundingClientRect().right + 2) throw new Error('Document widget escaped the form');
                if (document.documentElement.scrollWidth > innerWidth + 2) throw new Error('Column resize introduced page overflow');
                console.log('test successful');
            })().catch(error => console.error(error.message));
        """, login=self.users['reviewer'].login, timeout=60)

    def test_document_column_resize_is_contained_desktop(self):
        self._check_document_column_resizing('en_US', '1366x900')

    def test_document_column_resize_is_contained_arabic(self):
        self.env['res.lang']._activate_lang('ar_001')
        self._check_document_column_resizing('ar_001', '1366x900')

    def test_document_column_resize_is_contained_mobile(self):
        self._check_document_column_resizing('en_US', '390x844')

    def test_admin_and_secretarial_chatter_shows_their_own_work(self):
        for role in ('user', 'admin'):
            actor = self.users[role]
            claim = self.env['ab_supplier_claim_cycle'].with_user(actor).with_context(tracking_disable=True).create({
                'supplier_id': self.claim.supplier_id.id, 'num_of_invoice': 1, 'area': 'north', 'claim_amount': 100,
                'type_of_invoice': 'original', 'payment_nature': 'cash', 'tax_classification': 'non_tax_payment'})
            claim.write({'claim_amount': 150, 'area': 'south'})
            claim.action_submit()
            claim.with_user(self.users['supplier_accounts']).action_decide('supplier_accounts', 'approved')
            claim.write({'payment_request_attachment': self.content, 'payment_request_filename': 'own-work-evidence.pdf'})
            claim.action_prepare_payment()
            claim.action_close()
            self.browser_js(f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{claim.id}', """
                const deadline = Date.now() + 30000;
                const timer = setInterval(() => {
                    const text = document.querySelector('.o-mail-Chatter')?.textContent || '';
                    if (text.includes('own-work-evidence.pdf') && text.includes('100.0 → 150.0') && text.includes('Closed')) {
                        clearInterval(timer);
                        console.log('test successful');
                    } else if (Date.now() > deadline) {
                        clearInterval(timer);
                        console.error('Actor could not see their own upload, field change and workflow history');
                    }
                }, 200);
            """, login=actor.login, timeout=60)

    def test_claim_history_visible_when_muk_notifications_are_hidden(self):
        if not self.env['ir.module.module'].search_count([
            ('name', '=', 'muk_web_chatter'), ('state', '=', 'installed')]):
            self.skipTest('MuK Chatter is not installed')
        for role in ('user', 'admin', 'tax', 'reviewer'):
            self.browser_js(f'/odoo/action-ab_supplier_claim_cycle.invoice_action/{self.claim.id}', """
                (async () => {
                    const deadline = Date.now() + 30000;
                    while (!document.querySelector('.o-mail-Chatter')?.textContent.includes('request.pdf')) {
                        if (Date.now() > deadline) throw new Error('Claim history did not load');
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    const chatter = document.querySelector('.o-mail-Chatter');
                    const toggle = chatter.querySelector('button[aria-label="Show/Hide Notifications"]');
                    if (!toggle) throw new Error('MuK notification filter is missing');
                    if (!toggle.querySelector('.fa-eye-slash')) toggle.click();
                    await new Promise(resolve => setTimeout(resolve, 250));
                    if (!toggle.querySelector('.fa-eye-slash')) throw new Error('Notification hiding was not enabled');
                    if (localStorage.getItem('muk_web_chatter.notifications') !== 'false') throw new Error('Preference was not persisted');
                    const text = chatter.textContent;
                    if (!text.includes('request.pdf') || !text.includes('Closed')) {
                        throw new Error('Claim audit history disappeared when MuK notifications were hidden');
                    }
                    console.log('test successful');
                })().catch(error => console.error(error.message));
            """, login=self.users[role].login, timeout=60)
