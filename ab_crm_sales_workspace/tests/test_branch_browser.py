from odoo.tests import HttpCase, tagged, no_retry
from odoo.addons.web.tests.test_js import unit_test_error_checker


@tagged('post_install', '-at_install')
class TestBranchBrowser(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.asset'].create(
            [
                {
                    'name': 'Isolate unrelated POS scripts',
                    'bundle': 'web.assets_backend',
                    'directive': 'remove',
                    'path': path,
                }
                for path in (
                    'ab_sales/static/src/pos/zz_pos_settings_extension_patch.js',
                    'ab_sales/static/src/pos/zz_pos_replication_manual_patch.js',
                    'ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js',
                    'ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js',
                    'ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js',
                )
            ]
        )

    @no_retry
    def test_branch_components(self):
        value = 0
        for char in '@ab_crm_sales_workspace':
            value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
        self.browser_js(
            f'/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id={value:08x}',
            '',
            '',
            login='admin',
            timeout=180,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=unit_test_error_checker,
        )

    @no_retry
    def test_header_navigation(self):
        value = 0
        for char in '@ab_crm_sales_workspace/navigation':
            value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
        self.browser_js(
            f'/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id={value:08x}',
            '', '', login='admin', timeout=120,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=unit_test_error_checker,
        )

    @no_retry
    def test_performance_notification_components(self):
        value = 0
        for char in '@ab_crm_sales_workspace/notifications':
            value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
        self.browser_js(
            f'/web/tests?headless&loglevel=2&preset=desktop&timeout=15000&id={value:08x}',
            '', '', login='admin', timeout=180,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=unit_test_error_checker)

    @no_retry
    def test_performance_english_arabic_workspace(self):
        import json
        self.env['res.lang']._activate_lang('ar_001')
        self.env['ir.module.module'].search([
            ('name', 'in', ['ab_crm_sales_workspace', 'ab_crm_website']),
            ('state', '=', 'installed')])._update_translations(['ar_001'])
        for language, heading, login, direction, name, phone in [
            ('en_US', 'Sales Chatter', 'Employee Login', 'ltr', 'Name', 'Phone'),
            ('ar_001', 'محادثات المبيعات', 'دخول الموظف', 'rtl', 'الاسم', 'الهاتف')]:
            self.env.ref('base.user_admin').lang = language
            labels = self.env['ab_crm_customer'].with_context(lang=language).fields_get(
                ['directory_name_key', 'directory_phone_key'])
            self.assertEqual(labels['directory_name_key']['string'], name)
            self.assertEqual(labels['directory_phone_key']['string'], phone)
            expected = json.dumps({'heading': heading, 'login': login, 'direction': direction})
            self.browser_js('/odoo?debug=assets', '''
                (async () => {
                    const expected = ''' + expected + ''';
                    const env = odoo.__WOWL_DEBUG__.root.env;
                    await env.services.action.doAction('ab_crm_sales_workspace.action_workspace');
                    for (let count = 0; count < 100 && !document.querySelector('.ab_chatter_login h3'); count++) {
                        await new Promise(resolve => setTimeout(resolve, 50));
                    }
                    const root = document.querySelector('.ab_crm_sales_workspace');
                    if (root?.querySelector('header h2')?.textContent !== expected.heading) throw new Error('Workspace heading language mismatch');
                    if (root.getAttribute('dir') !== expected.direction) throw new Error('Workspace direction mismatch');
                    if (document.querySelector('.ab_chatter_login h3')?.textContent !== expected.login) throw new Error('Login language mismatch');
                    console.log('test successful');
                })();
            ''', ready='!!(odoo.__WOWL_DEBUG__ && odoo.__WOWL_DEBUG__.root)', login='admin', timeout=90)
