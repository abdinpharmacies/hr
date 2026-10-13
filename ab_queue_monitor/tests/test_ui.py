from unittest.mock import patch
from datetime import timedelta

from odoo import fields
from odoo.tests import HttpCase, tagged
from odoo.tests.common import ChromeBrowser
from odoo.addons.integration_queue_job.job import Job


@tagged('post_install', '-at_install')
class TestQueueMonitorUI(HttpCase):
    def test_monitor_feedback(self):
        self.env['ab_queue_monitor_definition'].create({
            'name': 'res.partner.search_count', 'key': 'feedback|queue|res.partner|search_count',
            'module_name': 'feedback', 'module_label': 'Feedback', 'model_name': 'res.partner',
            'method_name': 'search_count', 'backend': 'queue', 'runtime_support': True,
            'static_found': True, 'discovery_type': 'static',
        })
        now = fields.Datetime.now()
        for state in ('started', 'failed', 'done'):
            job = Job(self.env['res.partner'].search_count, args=([],))
            job.state = state
            job.date_created = now - timedelta(hours=2)
            job.date_started = now - timedelta(hours=1)
            job.date_done = now if state == 'done' else None
            job.store()
        self._capture('''
            (async () => {
                const waitFor = async (check) => {
                    for (let i = 0; i < 600; i++) {
                        if (check()) return;
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    throw new Error('Monitor feedback did not arrive');
                };
                const ready = () => !document.querySelector('.abqm-loading');
                await waitFor(() => document.querySelector('.abqm-state-counts'));
                if (document.querySelector('.abqm-runner .completed')) throw new Error('Lease is presented as healthy execution');
                if (!document.querySelector('.abqm-freshness').textContent.includes('آخر تحديث:')) throw new Error('Freshness translation missing');
                if (!document.querySelector('.abqm-auto-refresh').checked) throw new Error('Auto refresh disabled by default');
                if (!document.querySelector('.abqm-review')?.textContent.includes('تحتاج إلى مراجعة')) throw new Error('Review alert missing');
                const initial = document.querySelector('.abqm-freshness b').textContent;
                await waitFor(() => ready() && document.querySelector('.abqm-freshness b').textContent !== initial);
                document.querySelectorAll('.abqm-tabs button')[1].click();
                await waitFor(() => ready() && document.querySelectorAll('.abqm-table tbody tr').length === 3);
                const failed = [...document.querySelectorAll('.abqm-table tbody tr')].find(row => row.querySelector('.failed'));
                if (!failed.querySelector('td:nth-child(5)').textContent.includes('غير معروف')) throw new Error('Failed duration is not unknown');
                const limit = document.querySelector('.abqm-review-minutes');
                limit.value = '120';
                limit.dispatchEvent(new Event('input', { bubbles: true }));
                limit.dispatchEvent(new Event('change', { bubbles: true }));
                await waitFor(() => ready() && !document.querySelector('.abqm-table .abqm-review'));
                document.querySelectorAll('.abqm-tabs button')[0].click();
                await waitFor(() => ready() && document.querySelector('.abqm-state-counts'));
                console.log('test successful');
            })().catch(error => console.error(error));
        ''', lang='ar_001')

    def test_definition_sorting(self):
        self.env['ab_queue_monitor_definition'].create([
            {'name': f'sort.work_{index:02d}', 'key': f'ui_sort|{index}', 'module_name': 'ui_sort',
             'model_name': 'sort', 'method_name': f'work_{index:02d}', 'backend': 'queue',
             'static_found': True, 'runtime_support': True, 'discovery_type': 'static'}
            for index in range(45)
        ])
        self._capture('''
            (async () => {
                const waitFor = async (check) => {
                    for (let i = 0; i < 300; i++) {
                        if (check()) return;
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    throw new Error('Sort result did not arrive');
                };
                const ready = () => !document.querySelector('.abqm-loading');
                const first = () => document.querySelector('.abqm-job-link code')?.textContent;
                await waitFor(() => document.querySelector('.abqm-sort'));
                [...document.querySelectorAll('.abqm-modules button')].find(button => button.textContent.includes('ui_sort')).click();
                await waitFor(() => ready() && first() === 'work_00');
                const header = document.querySelector('.abqm-sort');
                header.click();
                await waitFor(() => ready() && header.parentElement.getAttribute('aria-sort') === 'ascending');
                header.click();
                await waitFor(() => ready() && first() === 'work_44');
                document.querySelector('.abqm-pagination button:last-child').click();
                await waitFor(() => ready() && first() === 'work_04');
                header.click();
                await waitFor(() => ready() && first() === 'work_00' && document.querySelectorAll('.abqm-table tbody tr').length === 40);
                if (document.querySelectorAll('.abqm-sort').length !== 5) throw new Error('Missing sortable columns');
                console.log('test successful');
            })().catch(error => console.error(error));
        ''')

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
