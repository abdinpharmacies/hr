import tempfile
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file

from ..services import runtime, static_discovery


@tagged('post_install', '-at_install')
class TestQueueMonitor(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.monitor = cls.env['ab_queue_monitor']
        cls.definitions = cls.env['ab_queue_monitor_definition']
        cls.sessions = cls.env['ab_queue_monitor_session']
        cls.reader = cls.env['res.users'].create({
            'name': 'Monitor test reader', 'login': 'ab_queue_monitor_test_reader',
            'group_ids': [fields.Command.set([cls.env.ref('base.group_user').id, cls.env.ref('ab_queue_monitor.group_user').id])],
        })
        cls.outsider = cls.env['res.users'].create({
            'name': 'Monitor test outsider', 'login': 'ab_queue_monitor_test_outsider',
            'group_ids': [fields.Command.set([cls.env.ref('base.group_user').id])],
        })

    def definition(self, **kwargs):
        values = {'name': 'test_model.work', 'key': 'test|queue|test_model|work',
                  'module_name': 'test_module', 'model_name': 'test_model', 'method_name': 'work',
                  'backend': 'queue', 'static_found': True, 'runtime_support': True, 'discovery_type': 'static'}
        values.update(kwargs)
        return self.definitions.create(values)

    def test_views_load_from_source(self):
        source = Path(__file__).resolve().parents[1] / 'views' / 'monitor_views.xml'
        for name, view_type in (('definition_list', 'list'), ('definition_form', 'form'),
                                ('definition_search', 'search'), ('session_list', 'list'),
                                ('session_form', 'form')):
            xmlid = 'ab_queue_monitor.' + name
            with self.subTest(view=xmlid):
                arch = get_view_arch_from_file(str(source), xmlid)
                self.assertEqual(etree.fromstring(arch).tag, view_type)
                for language in ('en_US', 'ar_001'):
                    view = self.env.ref(xmlid).with_context(read_arch_from_file=True, lang=language)
                    self.assertEqual(etree.fromstring(view.arch).tag, view_type)
                    result = self.env[view.model].with_context(read_arch_from_file=True, lang=language).get_views(
                        [(view.id, view_type)])
                    self.assertTrue(result)

    def test_static_idle_and_module_filter(self):
        self.definition()
        with patch.object(static_discovery, 'scan_file', side_effect=AssertionError('dashboard scanned source')):
            data = self.monitor.dashboard({'module': 'test_module'})
        self.assertEqual(data['rows'][0]['status'], 'idle')
        self.assertIn('test_module', [m['name'] for m in data['modules']])
        self.assertNotIn('base', [m['name'] for m in data['modules']])

    def test_static_methods_and_deduplication(self):
        source = '''
class Work:
    _name = 'work'
    def enqueue(self):
        self.with_user(1).with_delay().run()
        self.with_delay().run()
        delayed = self.delayable()
        delayed.control()
    def run(self): pass
    def control(self): pass
'''
        found = static_discovery.scan_text(source, 'example', 'models/work.py')
        self.assertEqual({r['method_name'] for r in found}, {'run', 'control'})
        self.assertEqual(len(found), 2)
        self.assertTrue(all(r['model_name'] == 'work' for r in found))

    def test_empty_module(self):
        self.assertEqual(static_discovery.scan_text('class Empty: pass', 'empty', 'empty.py'), [])

    def test_malformed_file_is_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'broken.py').write_text('def broken(')
            with self.assertRaises(SyntaxError):
                static_discovery.scan_file(directory, 'broken.py', 'example')
            Path(directory, 'large.py').write_text(' ' * (static_discovery.MAX_FILE_BYTES + 1))
            with self.assertRaises(ValueError):
                static_discovery.scan_file(directory, 'large.py', 'example')

    def test_inventory_excludes_tests_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'models').mkdir()
            (root / 'tests').mkdir()
            (root / 'models' / 'work.py').touch()
            (root / 'tests' / 'test_work.py').touch()
            (root / 'outside.py').symlink_to('/etc/passwd')
            self.assertEqual(static_discovery.inventory(directory), ['models/work.py'])

    def test_large_tree_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            for index in range(4):
                Path(directory, f'{index}.py').touch()
            with patch.object(static_discovery, 'MAX_FILES', 3), self.assertRaises(ValueError):
                static_discovery.inventory(directory)

    def test_runtime_states(self):
        self.assertEqual(runtime.state_category('started'), 'running')
        self.assertEqual(runtime.state_category('pending', 2), 'retrying')
        self.assertEqual(runtime.state_category('wait_dependencies'), 'pending')
        self.assertEqual(runtime.state_category('new_framework_state'), 'unknown')
        actual = runtime.adapters(self.env)['queue'].states()
        self.assertIn(('started', 'Started'), self.env['queue.job'].with_context(lang='en_US')._fields['state']._description_selection(self.env(context=dict(self.env.context, lang='en_US'))))
        self.assertTrue(actual)

    def test_permissions(self):
        with self.assertRaises(AccessError):
            self.monitor.with_user(self.outsider).dashboard()
        with self.assertRaises(AccessError):
            self.sessions.with_user(self.reader).start_scan()
        with self.assertRaises(AccessError):
            self.definition().with_user(self.reader).write({'name': 'changed'})
        self.monitor.with_user(self.reader).dashboard()

    def test_details_are_sanitized(self):
        text = 'Traceback:\n  File "/secret/path/worker.py", line 15, in run\n    password = "TOP_SECRET"\nValueError: bearer TOP_SECRET'
        result = runtime.safe_traceback(text)
        self.assertEqual(result, 'worker.py:15 in run')
        self.assertNotIn('TOP_SECRET', result)

    def test_optional_runtime_fields(self):
        class MinimalJob:
            id = 1
            _fields = {'state': True, 'model_name': True, 'method_name': True}

            def __getitem__(self, name):
                return {'state': 'pending', 'model_name': 'example', 'method_name': 'work'}[name]

        data = runtime.QueueAdapter(self.env).details(MinimalJob())
        self.assertEqual(data['status'], 'pending')
        self.assertFalse(data['context'])
        self.assertEqual(data['duration'], 0)

    def test_no_cron_or_startup_scan(self):
        self.assertFalse(self.env['ir.model.data'].search_count([
            ('module', '=', 'ab_queue_monitor'), ('model', '=', 'ir.cron')]))
        count = self.sessions.search_count([])
        with patch.object(static_discovery, 'inventory', side_effect=AssertionError('unexpected scan')):
            self.monitor.dashboard()
        self.assertEqual(count, self.sessions.search_count([]))

    def test_runtime_without_discovery(self):
        data = self.monitor.dashboard(tab='executions')
        expected = sum(adapter.jobs.search_count(adapter.domain()) for adapter in runtime.adapters(self.env).values())
        self.assertEqual(data['total'], expected)
        self.assertLessEqual(len(data['rows']), 40)

    def test_today_uses_viewer_timezone(self):
        utc = self.monitor.with_context(tz='UTC')._utc_day_start(fields.Date.to_date('2026-01-10'))
        cairo = self.monitor.with_context(tz='Africa/Cairo')._utc_day_start(fields.Date.to_date('2026-01-10'))
        self.assertEqual((utc - cairo).total_seconds(), 7200)

    def test_difference(self):
        self.assertEqual(static_discovery.difference(['a', 'b'], ['b', 'c']), (['c'], ['a'], ['b']))

    def test_runner_requires_lease(self):
        with patch.object(self.env.cr, 'execute'), patch.object(self.env.cr, 'fetchone', return_value=None), patch.object(type(self.env['queue.job']), 'search', return_value=self.env['queue.job']):
            self.assertEqual(runtime.runner_health(self.env)['status'], 'unknown')

    def test_registered_idle_control(self):
        if runtime.CLASSIFICATION_MODEL not in self.env:
            self.skipTest('Classification is optional')
        self.assertEqual(runtime.owner(self.env, runtime.CLASSIFICATION_MODEL, '_apply_control'), 'ab_website_sale_product')
        functions = self.env['queue.job.function'].search([('model_id.model', '=', runtime.CLASSIFICATION_MODEL)])
        self.assertIn('_apply_control', functions.mapped('method'))

    def test_real_classification_context(self):
        job = self.env['queue.job'].search([('model_name', '=', runtime.CLASSIFICATION_MODEL)], limit=1)
        if not job:
            self.skipTest('No retained classification execution')
        context = runtime.QueueAdapter(self.env).context(job)
        self.assertEqual(context['model'], runtime.CLASSIFICATION_MODEL)
        self.assertIn('processed_products', context['metrics'])
        self.assertFalse(runtime.QueueAdapter(self.env(user=self.reader)).context(job))

    def test_runtime_and_static_merge(self):
        item = {'module': 'integration_queue_job', 'model_name': 'queue.job', 'method_name': 'testing_method', 'backend': 'queue', 'static_found': True}
        session = self.sessions.create({'work': {'modules': ['integration_queue_job']}, 'candidates': {self.definitions._key(item): item}})
        with patch.object(runtime.QueueAdapter, 'pairs', return_value=[('queue.job', 'testing_method')]), patch.object(runtime, 'owner', return_value='integration_queue_job'):
            session._finish()
        definition = self.definitions.search([('method_name', '=', 'testing_method')])
        self.assertTrue(definition.runtime_found)
        self.assertEqual(definition.discovery_type, 'both')
        self.assertEqual(len(definition), 1)

    def test_removed_and_incomplete_modules(self):
        removed = self.definition()
        preserved = self.definition(key='incomplete|queue|work', module_name='incomplete')
        session = self.sessions.create({'work': {'modules': []}, 'incomplete_modules': ['incomplete'], 'candidates': {}})
        session._finish()
        self.assertFalse(removed.active)
        self.assertTrue(preserved.active)
        self.assertGreaterEqual(session.removed_count, 1)

    def test_scan_continues_after_malformed_source(self):
        session = self.sessions.create({'modules_total': 1, 'work': {'modules': ['example'], 'module_index': 0, 'files': [], 'file_index': 0}, 'candidates': {}})
        with patch('odoo.addons.ab_queue_monitor.models.discovery.get_module_path', return_value='/tmp'), patch.object(static_discovery, 'inventory', return_value=['bad.py', 'good.py']), patch.object(static_discovery, 'scan_file', side_effect=[SyntaxError(), []]):
            progress = session.scan_step()
        self.assertEqual(progress['state'], 'done')
        self.assertEqual(progress['files_scanned'], 2)
        self.assertIn('bad.py', progress['warnings'])
