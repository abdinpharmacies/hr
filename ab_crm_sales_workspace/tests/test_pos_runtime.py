import json
from unittest.mock import patch

from odoo.exceptions import UserError

from odoo.tests import HttpCase, tagged, no_retry


@tagged('post_install', '-at_install')
class TestPosRuntime(HttpCase):
    def _check_runtime(self, language, labels):
        self.env.ref('base.user_admin').write({'lang': language})
        with patch.object(type(self.env['ab_sales_branch_client']), '_call', side_effect=UserError('External service mocked')):
            self.browser_js('/odoo?debug=assets', '''
            (async () => {
            const env = odoo.__WOWL_DEBUG__.root.env;
            await env.services.action.doAction('ab_crm_sales_workspace.action_workspace');
            const expected = %s;
            const actual = [...document.querySelectorAll('.ab_workspace_navigation button')].map(button => button.textContent.trim());
            if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error('Navigation language mismatch: ' + JSON.stringify(actual));
            await env.services.action.doAction('ab_crm_sales_workspace.action_pos');
            await new Promise(resolve => setTimeout(resolve, 600));
            if (!document.querySelector('.ab_pos_hr_overlay')) throw new Error('Native employee login is missing from CRM POS');
            const actions = odoo.loader.modules.get('@web/core/registry').registry.category('actions');
            const Native = actions.get('ab_sales.pos');
            const Adapter = actions.get('ab_crm_sales_workspace.pos');
            if (Object.getPrototypeOf(Adapter.prototype) !== Native.prototype || Adapter.template !== Native.template) throw new Error('Native POS registration changed');
            await env.services.action.doAction('ab_sales.ab_sales_bill_wizard_action');
            if (!document.querySelector('.o_ab_sales_bill_wizard')) throw new Error('Bill Wizard did not open');
            console.log('test successful');
            })().catch(error => console.error(error));
        ''' % json.dumps(labels), ready='!!odoo.__WOWL_DEBUG__?.root', login='admin', timeout=90)

    @no_retry
    def test_english_navigation_and_native_pos_login(self):
        self._check_runtime('en_US', ['Inbox', 'Create order', 'Invoices'])

    @no_retry
    def test_arabic_navigation_and_native_pos_login(self):
        self._check_runtime('ar_001', ['الوارد', 'إنشاء طلب', 'الفواتير'])
