from odoo.tests import HttpCase, tagged, no_retry
from odoo.addons.web.tests.test_js import unit_test_error_checker


@tagged('post_install', '-at_install')
class TestWhatsAppBrowser(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.asset'].create(
            [
                {
                    'name': 'Isolated existing POS test patch',
                    'bundle': 'web.assets_unit_tests_setup',
                    'directive': 'remove',
                    'path': path,
                }
                for path in (
                    'ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js',
                    'ab_sales/static/src/pos/zz_pos_replication_manual_patch.js',
                    'ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js',
                    'ab_sales/static/src/pos/zz_pos_settings_extension_patch.js',
                    'ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js',
                )
            ]
        )

    @no_retry
    def test_channel_composition(self):
        filters = []
        for name in ('@ab_crm_whatsapp_workspace', '@ab_crm_sales_workspace'):
            value = 0
            for char in name:
                value = ((value << 5) - value + ord(char)) & 0xFFFFFFFF
            filters.append(f'&id={value:08x}')
        self.browser_js(
            '/web/tests?headless&loglevel=2&preset=desktop&timeout=15000'
            + ''.join(filters),
            '',
            '',
            login='admin',
            timeout=180,
            success_signal='[HOOT] Test suite succeeded',
            error_checker=unit_test_error_checker,
        )
