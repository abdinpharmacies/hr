"""Offline reporting contracts; database behavior is covered by disposable fixtures."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import runpy
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError, loads
from table_checkpoints import TableMigration, safe_error, validate_exceptions


class TableCheckpointTests(unittest.TestCase):
    def test_exception_rules_require_exact_names_and_reason(self):
        for entry in ({}, {'table': 'x', 'constraint': 'fk', 'reason': ''}, 'fk'):
            with self.assertRaises(MigrationError):
                validate_exceptions({'accepted_foreign_key_failures': [entry]})
        self.assertEqual(validate_exceptions({}), {})
        self.assertEqual(validate_exceptions({'accepted_foreign_key_failures': [
            dict(table='x', constraint='fk', reason='reviewed')]}), {('x', 'fk'): 'reviewed'})

    def test_error_report_does_not_copy_values(self):
        error = Exception('secret row value')
        self.assertNotIn('secret', str(safe_error(error)))

    def test_cli_exit_status_distinguishes_errors_and_accepted_exceptions(self):
        script=Path(__file__).resolve().parents[1]/'migrate.py'
        argv=[str(script),'--source-config','source','--source-db','a',
              '--target-config','target','--target-db','b','--no-backup']
        with patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
            with patch('prepared.run',return_value={'status':'finished_with_errors'}):
                with self.assertRaises(SystemExit) as error:
                    runpy.run_path(str(script),run_name='__main__')
                self.assertEqual(error.exception.code,2)
            with patch('prepared.run',return_value={'status':'finished_with_exceptions'}):
                runpy.run_path(str(script),run_name='__main__')

    def test_unit_commits_marker_and_continues_after_rollback(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = SimpleNamespace(con=MagicMock(), selected={'ab_test'}, relations=[],
                                     rules={}, conversions={}, target={'ab_test': {'table': 'ab_test'}}, physical={}, stage=Path(directory))
            checkpoint = MagicMock()
            worker = TableMigration(engine, checkpoint)
            def fail():
                raise ValueError('private data')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertFalse(worker.unit('ab_test', 'copy', fail))
                self.assertTrue(worker.unit('ab_other', 'copy', lambda: 3))
            engine.con.rollback.assert_called_once()
            self.assertEqual(engine.con.commit.call_count, 2)
            self.assertEqual(checkpoint.call_args.args[1], 'table:copy:ab_other')
            self.assertEqual(checkpoint.call_args.args[2]['rows'], 3)
            self.assertNotIn('private data', (Path(directory) / 'failed_tables.json').read_text())
            self.assertEqual(len(loads((Path(directory) / 'failed_tables.json').read_text())), 1)
