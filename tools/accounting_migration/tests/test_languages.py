"""Offline language and orchestrator tests; no real database connections."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError, loads, save_json
from languages import discover_languages, install_languages
from bulk_importer import BulkImporter
from migrate import main
from test_bulk import render


class LanguageTests(unittest.TestCase):
    def test_discover_delegated_languages_without_user_lang_column(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.__iter__.return_value = iter([('ar_001',), ('en_US',), ('fr_FR',), (None,), ('',), ('ar_001',)])
        inventory = {'models': {
            'res.partner': {'table': 'res_partner', 'table_kind': 'r', 'columns': {'id': {}, 'lang': {}}},
            'res.users': {'table': 'res_users', 'columns': {'id': {}, 'partner_id': {}}}}}
        self.assertEqual(discover_languages(connection, inventory), ['en_US', 'ar_001', 'fr_FR'])
        query = render(cursor.execute.call_args.args[0])
        self.assertIn('"public"."res_partner"', query)
        self.assertNotIn('res_users', query)

    def test_missing_partner_language_schema_stops_before_query(self):
        connection = MagicMock()
        with self.assertRaisesRegex(MigrationError, 'stored res.partner.lang'):
            discover_languages(connection, {'models': {}})
        connection.cursor.assert_not_called()

    def make_env(self, codes=('en_US', 'ar_001')):
        env = MagicMock()
        lang, modules = MagicMock(), MagicMock()
        env.__getitem__.side_effect = {'res.lang': lang, 'ir.module.module': modules}.__getitem__
        lang._activate_lang.return_value = SimpleNamespace(active=True)
        lang.with_context.return_value.search.return_value.mapped.return_value = list(codes)
        return env, lang, modules

    def test_activate_then_load_translations_and_preserve_preferences(self):
        env, lang, modules = self.make_env(('en_US', 'ar_001', 'fr_FR'))
        order = []
        lang._activate_lang.side_effect = lambda code: order.append(code) or SimpleNamespace(active=True)
        modules.search.return_value._update_translations.side_effect = lambda **kw: order.append('translations')
        with tempfile.TemporaryDirectory() as d:
            report = install_languages(env, Path(d), ['ar_001', 'fr_FR', 'ar_001'])
        self.assertEqual(order, ['en_US', 'ar_001', 'fr_FR', 'translations'])
        self.assertTrue(report['complete'])
        self.assertTrue(report['translations_loaded'])
        modules.search.assert_called_once_with([('state', '=', 'installed')])
        self.assertNotIn('res.users', [call.args[0] for call in env.__getitem__.call_args_list])
        self.assertNotIn('res.partner', [call.args[0] for call in env.__getitem__.call_args_list])

    def test_unsupported_language_does_not_load_translations(self):
        env, lang, modules = self.make_env()
        lang._activate_lang.side_effect = lambda code: None if code == 'xx_XX' else SimpleNamespace(active=True)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(MigrationError, 'xx_XX'):
                install_languages(env, Path(d), ['xx_XX'])
            report = loads((Path(d) / 'languages.json').read_text())
        self.assertFalse(report['complete'])
        modules.search.assert_not_called()

    def test_translation_failure_is_reported_without_sensitive_exception(self):
        env, lang, modules = self.make_env()
        modules.search.return_value._update_translations.side_effect = RuntimeError('sensitive data')
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(MigrationError, 'module translations') as raised:
                install_languages(env, Path(d), ['en_US'])
            text = (Path(d) / 'languages.json').read_text()
            self.assertNotIn('sensitive data', text + str(raised.exception))
            self.assertFalse(loads(text)['complete'])

    def test_language_readiness_is_checked_before_any_copy(self):
        with tempfile.TemporaryDirectory() as d:
            engine = BulkImporter.__new__(BulkImporter)
            engine.stage, engine.report, engine.cr = Path(d), {}, MagicMock()
            engine.stage_tables = MagicMock()
            with self.assertRaisesRegex(MigrationError, 'COPY cannot start'):
                engine.run()
            engine.stage_tables.assert_not_called()

    def test_activation_verification_rejects_missing_arabic(self):
        env, lang, modules = self.make_env(('en_US',))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(MigrationError, 'ar_001'):
                install_languages(env, Path(d), ['en_US', 'ar_001'])
            self.assertFalse(loads((Path(d) / 'languages.json').read_text())['complete'])


class LifecycleTests(unittest.TestCase):
    def run_mocked(self, failure=None, failed_phase='bulk-import'):
        maintenance, source = MagicMock(), MagicMock()
        source.__enter__.return_value = source
        cursor = maintenance.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(True,), None]
        order = []
        def worker(args, stage, command, modules=()):
            order.append(command)
            if failure is not None and command == failed_phase:
                raise failure
            if command == 'init-target':
                save_json(stage / 'target-schema.json', {})
                order.append('languages complete')
            if command == 'bulk-smoke':
                save_json(stage / 'verification.json', {'passed': True})
        def discovery(*args):
            order.append('discover languages')
            return ['en_US', 'ar_001']
        with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()), \
                patch('migrate.RUN_ROOT', Path(d)), \
                patch('migrate.monitor_factory', return_value=lambda: None), \
                patch('migrate.connect', side_effect=[maintenance, source]), \
                patch('migrate.settings', return_value={'data_dir': '/unused'}), \
                patch('migrate.endpoint', return_value={}), \
                patch('migrate.source.inventory', return_value={'modules': []}), \
                patch('migrate.discover_languages', side_effect=discovery), \
                patch('migrate.worker', side_effect=worker), \
                patch('migrate.export_snapshot', side_effect=lambda *a: order.append('extract')) as export:
            argv = ['--source-config', 'source.conf', '--source-db', 'old',
                    '--target-config', 'target.conf', '--target-db', 'new']
            if failure is None:
                self.assertTrue(main(argv)['passed'])
            else:
                with self.assertRaises(type(failure)):
                    main(argv)
                stage = next(Path(d).iterdir())
                self.assertEqual(loads((stage / 'failure.json').read_text())['connection_policy'], 'always_enabled')
                if failed_phase == 'init-target':
                    export.assert_not_called()
            queries = '\n'.join(render(call.args[0]) for call in cursor.execute.call_args_list)
            self.assertIn('ALLOW_CONNECTIONS true', queries)
            self.assertNotIn('ALTER DATABASE', queries)
            self.assertNotIn('pg_terminate_backend', queries)
            self.assertNotIn('ALLOW_CONNECTIONS false', queries)
            maintenance.close.assert_called_once()
        return order

    def test_success_keeps_connections_enabled_and_orders_languages_before_copy(self):
        order = self.run_mocked()
        self.assertEqual(order, ['discover languages', 'init-target', 'languages complete', 'extract', 'bulk-import', 'bulk-smoke'])

    def test_load_failure_keeps_connections_enabled(self):
        self.run_mocked(MigrationError('test failure'))

    def test_interruption_keeps_connections_enabled(self):
        self.run_mocked(KeyboardInterrupt())

    def test_initialization_language_failure_prevents_extraction(self):
        self.run_mocked(MigrationError('Language setup failed'), 'init-target')


if __name__ == '__main__':
    unittest.main()
