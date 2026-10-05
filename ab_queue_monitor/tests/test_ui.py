from unittest.mock import patch

from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser


@tagged('post_install', '-at_install')
class TestQueueMonitorUI(HttpCase):
    def _capture(self, code, lang='en_US', size='1366x900'):
        self.env.ref('base.user_admin').lang = lang
        self.browser_size = size
        original = ChromeBrowser._wait_code_ok

        def capture(browser, *args, **kwargs):
            result = original(browser, *args, **kwargs)
            browser.take_screenshot('queue_monitor_' + lang + '_').result(timeout=15)
            return result

        with patch.object(ChromeBrowser, '_wait_code_ok', capture):
            self.browser_js('/odoo/queue-monitor', code, login='admin', timeout=180)

    def test_discover_and_runtime(self):
        before = self.env['queue.job'].search_count([])
        self._capture('''
            (async () => {
                const waitFor = async (fn) => {
                    for (let i = 0; i < 1600; i++) {
                        const result = fn(); if (result) return result;
                        await new Promise(r => setTimeout(r, 100));
                    }
                    throw new Error('Monitor UI did not reach expected state');
                };
                await waitFor(() => document.querySelector('.abqm-primary'));
                document.querySelector('.abqm-primary').click();
                await waitFor(() => document.querySelector('.abqm-progress h2')?.textContent === 'Discovery Complete');
                await waitFor(() => document.querySelector('.abqm-table tbody tr'));
                const rows = [...document.querySelectorAll('.abqm-modules button')];
                const classification = rows.find(el => el.textContent.includes('ab_website_sale_product'));
                if (!classification) throw new Error('Classification module missing');
                classification.click();
                await waitFor(() => document.querySelector('.abqm-table')?.textContent.includes('_apply_control'));
                const control = [...document.querySelectorAll('.abqm-table tbody tr')].find(el => el.textContent.includes('_apply_control'));
                if (!control.textContent.includes('Declared / Idle')) throw new Error('Idle control job missing');
                document.querySelectorAll('.abqm-tabs button')[1].click();
                await waitFor(() => !document.querySelector('.abqm-loading') && document.querySelector('.abqm-table th:nth-child(4)')?.textContent === 'Created' && document.querySelector('.abqm-table')?.textContent.includes('_process_checkpoint'));
                document.querySelector('.abqm-job-link').click();
                await waitFor(() => document.querySelector('.abqm-context'));
                if (!document.querySelector('.abqm-context').textContent.includes('Processed')) throw new Error('Classification counters missing');
                document.querySelector('.modal-footer button').click();
                await waitFor(() => !document.querySelector('.abqm-detail'));
                console.log('test successful');
            })().catch(error => console.error(error));
        ''')
        self.env.invalidate_all()
        self.assertEqual(self.env['queue.job'].search_count([]), before)
        session = self.env['ab_queue_monitor_session'].search([], limit=1)
        self.assertEqual(session.state, 'done')
        self._logger.info('DISCOVERY RESULT: modules=%s files=%s definitions=%s job_modules=%s runtime=%s warnings=%s',
                          session.modules_scanned, session.files_scanned, session.definitions_count,
                          session.modules_count, session.runtime_count, session.warnings)

    def test_arabic_mobile(self):
        self._capture('''
            (async () => {
                for (let i = 0; i < 500; i++) {
                    if (document.querySelector('.abqm-runner')) break;
                    await new Promise(r => setTimeout(r, 100));
                }
                const root = document.querySelector('.abqm');
                if (!root || !root.textContent.includes('مراقبة المهام الخلفية')) throw new Error('Arabic dashboard missing');
                if (getComputedStyle(root).direction !== 'rtl') throw new Error('RTL missing');
                if (root.scrollWidth > root.clientWidth + 2) throw new Error('Mobile layout overflows');
                console.log('test successful');
            })().catch(error => console.error(error));
        ''', lang='ar_001', size='390x844')
