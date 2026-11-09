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
