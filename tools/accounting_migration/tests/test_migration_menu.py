"""Interactive dispatch and shared private defaults; no application DB access."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError
from migration_menu import DEFAULTS, load_defaults, save_defaults, collect, run_menu
from migrate import main
from database_repair import choose
from repair_audit import saved_definition


class MenuTests(unittest.TestCase):
    def test_private_atomic_shared_settings_and_invalid_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'menu-defaults.json'
            self.assertEqual(load_defaults(path), DEFAULTS)
            save_defaults(path, DEFAULTS)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o644)
            changed = dict(DEFAULTS, csv_path='/other.csv')
            save_defaults(path, changed)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(load_defaults(path), changed)
            path.write_text('{invalid')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(load_defaults(path), DEFAULTS)
            self.assertEqual(list(Path(root).glob('.menu-defaults-*')), [])

    def test_dispatch_uses_shared_values_and_zero_exits_without_importing(self):
        with tempfile.TemporaryDirectory() as root:
            dispatch = Mock(return_value={'status': 'complete'})
            with patch('builtins.input', side_effect=['1', '2', '0']), patch('migration_menu.collect', return_value=DEFAULTS), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(run_menu(dispatch, root), 0)
            export, imp = [call.args[0] for call in dispatch.call_args_list]
            self.assertEqual(export[:-2], imp[:-2])
            self.assertEqual(export[-2:], ['--export-table-plan', DEFAULTS['csv_path']])
            self.assertEqual(imp[-2:], ['--table-plan', DEFAULTS['csv_path']])
            self.assertEqual(load_defaults(Path(root) / 'menu-defaults.json'), DEFAULTS)

    def test_failure_preserves_defaults_and_returns_to_menu(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('builtins.input', side_effect=['2', '0']), patch('migration_menu.collect', return_value=DEFAULTS), \
                    contextlib.redirect_stdout(io.StringIO()):
                run_menu(Mock(side_effect=MigrationError('fixture failure')), root)
            self.assertEqual(load_defaults(Path(root) / 'menu-defaults.json'), DEFAULTS)

    def test_zero_and_eof_do_not_collect_or_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            for answer in ('0', EOFError()):
                with patch('builtins.input', side_effect=[answer]), patch('migration_menu.collect') as collect_mock, \
                        contextlib.redirect_stdout(io.StringIO()):
                    dispatch = Mock()
                    self.assertEqual(run_menu(dispatch, root), 0)
                    dispatch.assert_not_called()
                    collect_mock.assert_not_called()

    def test_fix_dispatch_never_calls_importer(self):
        with tempfile.TemporaryDirectory() as root:
            with patch('builtins.input', side_effect=['3', '0']), patch('migration_menu.collect', return_value=DEFAULTS), \
                    patch('database_repair.run') as repair, contextlib.redirect_stdout(io.StringIO()):
                dispatch = Mock()
                run_menu(dispatch, root)
                repair.assert_called_once_with(DEFAULTS, root)
                dispatch.assert_not_called()

    def test_collect_enter_accepts_defaults_and_rejects_existing_export(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / 'odoo.conf'
            config.write_text('[options]\ndb_host=localhost\n')
            existing = Path(root) / 'exists.csv'
            existing.touch()
            values = dict(DEFAULTS, source_config=str(config), target_config=str(config), csv_path=str(existing))
            fresh = str(Path(root) / 'fresh.csv')
            with patch('builtins.input', side_effect=['', '', '', '', '', fresh]), contextlib.redirect_stdout(io.StringIO()):
                result = collect(values, '1')
            self.assertEqual(result['source_db'], DEFAULTS['source_db'])
            self.assertEqual(result['csv_path'], fresh)
            with patch('migration_menu.read_plan') as reader, patch('builtins.input', return_value=''):
                self.assertEqual(collect(values, '2'), values)
                reader.assert_called_once_with(str(existing))

    def test_no_arguments_noninteractive_does_not_connect(self):
        with patch('sys.stdin.isatty', return_value=False), patch('common.connect') as connect, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main([]), 2)
            connect.assert_not_called()

    def test_fix_selection_orders_dependencies_and_excludes_blocked(self):
        fixes = {key: {'changes': [1]} for key in ('identities', 'payments', 'reports', 'discuss', 'foreign_keys')}
        with patch('builtins.input', return_value='5,2,2,1'):
            self.assertEqual(choose(fixes), ['identities', 'payments', 'foreign_keys'])
        fixes['payments'] = {'error': 'blocked'}
        with patch('builtins.input', return_value='a'):
            self.assertEqual(choose(fixes), ['identities', 'reports', 'discuss', 'foreign_keys'])

    def test_saved_composite_constraint_definition_is_bounded(self):
        item = dict(referenced_schema='public', referenced_table='parent',
                    definition='FOREIGN KEY (a, b) REFERENCES parent(a, b) MATCH FULL ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED')
        parsed = saved_definition(item)
        self.assertEqual(parsed['columns'], ['a', 'b'])
        self.assertEqual(parsed['match'], 'f')
        with self.assertRaises(MigrationError):
            saved_definition(dict(item, definition=item['definition'] + '; DELETE FROM parent'))


if __name__ == '__main__':
    unittest.main()
