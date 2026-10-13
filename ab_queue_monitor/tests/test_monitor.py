import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.addons.base.models.ir_ui_view import get_view_arch_from_file
from odoo.addons.integration_queue_job.job import Job

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

    def queue_execution(self, **values):
        job = Job(self.env['res.partner'].search_count, args=([],))
        for name, value in values.items():
            setattr(job, name, value)
        job.store()
        return job.db_record()

    def test_failed_duration_is_unknown_without_end_time(self):
        now = fields.Datetime.now()
        job = self.queue_execution(state='failed', date_started=now - timedelta(days=1))
        for instant in (now, now + timedelta(hours=1)):
            summary = runtime.QueueAdapter(self.env, instant).summary(job)
            self.assertIsNone(summary['duration'])
            self.assertFalse(summary['delayed'])

    def test_running_and_completed_duration(self):
        now = fields.Datetime.now()
        running = self.queue_execution(state='started', date_started=now - timedelta(minutes=5))
        completed = self.queue_execution(state='done', date_started=now - timedelta(minutes=5),
                                         date_done=now - timedelta(minutes=2))
        cancelled = self.queue_execution(state='cancelled', date_started=now - timedelta(minutes=5),
                                         date_cancelled=now - timedelta(minutes=1))
        later = runtime.QueueAdapter(self.env, now + timedelta(minutes=1))
        self.assertEqual(later.summary(running)['duration'], 360)
        self.assertEqual(later.summary(completed)['duration'], 180)
        self.assertEqual(later.summary(cancelled)['duration'], 240)

    def test_delayed_domain_matches_display_and_respects_eta(self):
        now = fields.Datetime.now()
        old = now - timedelta(hours=2)
        jobs = self.env['queue.job']
        cases = [
            ({'state': 'started', 'date_started': old}, True),
            ({'state': 'started', 'date_started': now - timedelta(minutes=2)}, False),
            ({'state': 'pending'}, True),
            ({'state': 'pending', 'eta': now + timedelta(hours=1)}, False),
            ({'state': 'pending', 'eta': now - timedelta(minutes=5), 'retry': 2}, False),
            ({'state': 'pending', 'eta': now - timedelta(minutes=45), 'retry': 2}, True),
            ({'state': 'enqueued', 'date_enqueued': now - timedelta(minutes=5)}, False),
            ({'state': 'wait_dependencies'}, True),
            ({'state': 'done', 'date_started': old, 'date_done': now}, False),
        ]
        adapter = runtime.QueueAdapter(self.env, now, 30)
        expected = set()
        for values, delayed in cases:
            job = self.queue_execution(date_created=old, **values)
            jobs |= job
            if delayed:
                expected.add(job.id)
            self.assertEqual(adapter.summary(job)['delayed'], delayed, values)
        found = adapter.jobs.search(adapter.delayed_domain() & fields.Domain('id', 'in', jobs.ids))
        self.assertEqual(set(found.ids), expected)

    def test_old_running_execution_remains_visible(self):
        now = fields.Datetime.now()
        definition = self.definition(model_name='res.partner', method_name='search_count')
        running = self.queue_execution(state='started', date_created=now - timedelta(hours=2),
                                       date_started=now - timedelta(hours=1))
        failed = self.queue_execution(state='failed', date_started=now - timedelta(minutes=10))
        pending = self.queue_execution(state='pending', retry=2, eta=now + timedelta(hours=1))
        completed = self.queue_execution(state='done', date_started=now - timedelta(minutes=2), date_done=now)
        jobs = running | failed | pending | completed
        before = jobs.read(['state', 'date_started', 'date_done', 'retry', 'eta'])
        reader = self.monitor.with_user(self.reader)
        for status in ('running', 'retrying', 'failed', 'completed'):
            result = reader.dashboard({'definition_id': definition.id, 'status': status})
            self.assertEqual(result['total'], 1)
            row = result['rows'][0]
            self.assertEqual(row['status'], 'running')
            self.assertEqual(row['latest']['id'], completed.id)
            self.assertEqual(row['states'], {'running': 1, 'failed': 1, 'retrying': 1, 'completed': 1})
            self.assertEqual(row['delayed'], 1)
        result = reader.dashboard({'definition_id': definition.id, 'delayed': True}, tab='executions')
        self.assertEqual([row['id'] for row in result['rows']], [running.id])
        self.assertEqual(definition.with_user(self.reader).running_count, 1)
        self.assertEqual(definition.with_user(self.reader).retrying_count, 1)
        self.assertEqual(definition.with_user(self.reader).failure_count, 1)
        self.assertIsNone(reader.execution_details('queue', failed.id)['duration'])
        self.assertEqual(jobs.read(['state', 'date_started', 'date_done', 'retry', 'eta']), before)
        with self.assertRaises(AccessError):
            self.monitor.with_user(self.outsider).execution_details('queue', running.id)

    def test_review_threshold_validation(self):
        with self.assertRaises(UserError):
            self.monitor.dashboard({'delay_minutes': 'invalid'})
        self.assertEqual(self.monitor._delay_minutes(0), 1)
        self.assertEqual(self.monitor._delay_minutes(999999), 1440)

    def test_monitor_field_translation(self):
        english = self.definitions.with_context(lang='en_US').fields_get(['running_count'])
        arabic = self.definitions.with_context(lang='ar_001').fields_get(['running_count'])
        self.assertEqual(english['running_count']['string'], 'Running Executions')
        self.assertNotEqual(english['running_count']['string'], arabic['running_count']['string'])

    def test_lease_is_not_progress_evidence(self):
        with patch.object(self.env.cr, 'execute'), patch.object(self.env.cr, 'fetchone', return_value=(123,)), patch.object(type(self.env['queue.job']), 'search', return_value=self.env['queue.job']):
            data = runtime.runner_health(self.env)
            self.assertEqual(data['status'], 'lease_held')
            self.assertEqual(data['progress'], 'unverified')

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

    def test_definition_sorting_before_pagination(self):
        for index in range(45):
            self.definition(key=f'sort|{index}', module_name='sort_test', method_name=f'work_{44 - index:02d}')
        monitor = self.monitor.with_user(self.reader)
        for direction in ('asc', 'desc'):
            pages = [monitor.dashboard({'module': 'sort_test'}, offset=offset,
                                       sort_by='method_name', sort_direction=direction)
                     for offset in (0, 40)]
            names = [row['method_name'] for page in pages for row in page['rows']]
            expected = [f'work_{index:02d}' for index in range(45)]
            self.assertEqual(names, expected if direction == 'asc' else list(reversed(expected)))
            self.assertEqual(pages[0]['total'], 45)
        with self.assertRaises(AccessError):
            self.monitor.with_user(self.outsider).dashboard(sort_by='count')

    def test_definition_sort_columns(self):
        rows = [
            {'id': 1, 'module_name': 'test', 'method_name': 'z', 'count': 2,
             'status': 'running', 'channel': 'z', 'discovery_type': 'static'},
            {'id': 2, 'module_name': 'test', 'method_name': 'a', 'count': 11,
             'status': 'completed', 'channel': '', 'discovery_type': 'both'},
        ]
        monitor = self.monitor.with_context(lang='en_US')
        for column in ('method_name', 'status', 'channel', 'discovery_type', 'count'):
            with self.subTest(column=column):
                monitor._sort_definitions(rows, column, 'asc')
                self.assertEqual(rows[0]['id'], 1 if column == 'count' else 2)
                monitor._sort_definitions(rows, column, 'desc')
                self.assertEqual(rows[0]['id'], 2 if column == 'count' else 1)
        original = list(rows)
        monitor._sort_definitions(rows, 'unsupported', 'desc')
        self.assertEqual(rows, original)

    def test_empty_module(self):
        self.assertEqual(static_discovery.scan_text('class Empty: pass', 'empty', 'empty.py'), [])

    def test_discovery_function_scope_and_reassignment(self):
        source = '''
class Work:
    _name = 'work'
    def first(self):
        task = self.env['first.model'].with_delay()
        task.run_first()
        task = self.env['third.model'].with_delay()
        task.run_third()
        task = object()
        task.unrelated()
    def second(self):
        task = self.env['second.model'].with_delay()
        task.run_second()
        def nested(task):
            task.should_not_be_a_job()
        task.after_nested()
'''
        found = static_discovery.scan_text(source, 'example', 'models/work.py')
        self.assertEqual({(row['model_name'], row['method_name']) for row in found}, {
            ('first.model', 'run_first'), ('third.model', 'run_third'),
            ('second.model', 'run_second'), ('second.model', 'after_nested'),
        })

    def test_discovery_branch_aliases_are_not_guessed(self):
        source = '''
class Work:
    _name = 'work'
    def schedule(self, flag):
        if flag:
            task = self.env['first.model'].with_delay()
            task.first()
        else:
            task = self.env['second.model'].with_delay()
            task.second()
        task.ambiguous()
'''
        found = static_discovery.scan_text(source, 'example', 'work.py')
        self.assertEqual({(row['model_name'], row['method_name']) for row in found}, {
            ('first.model', 'first'), ('second.model', 'second'),
        })

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
