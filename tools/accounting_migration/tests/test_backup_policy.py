"""Explicit backup choices without connecting to application databases."""
import contextlib
import hashlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backup_policy import require_choice, select_backup, perform_backup
from common import MigrationError, loads, save_json
from migrate import main, parser


class BackupPolicyTests(unittest.TestCase):
    argv = ['--source-config','s.conf','--source-db','s','--target-config','t.conf','--target-db','t']

    def test_no_default_and_flags_are_mutually_exclusive(self):
        self.assertIsNone(parser().parse_args(self.argv).backup)
        self.assertTrue(parser().parse_args(self.argv+['--backup']).backup)
        self.assertFalse(parser().parse_args(self.argv+['--no-backup']).backup)
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            parser().parse_args(self.argv+['--backup','--no-backup'])

    def test_noninteractive_missing_choice_refuses_before_dispatch_or_connect(self):
        for mode in ([], ['--table-plan','plan.csv']):
            with patch('sys.stdin.isatty',return_value=False),patch('common.connect') as connect, \
                    patch('prepared.run') as prepared,patch('csv_replicator.run') as csv, \
                    contextlib.redirect_stderr(io.StringIO()) as error,self.assertRaises(SystemExit) as exit:
                main(self.argv+mode)
            self.assertEqual(exit.exception.code,2)
            self.assertIn('--backup or --no-backup',error.getvalue())
            connect.assert_not_called();prepared.assert_not_called();csv.assert_not_called()

    def test_flags_dispatch_without_prompt_and_export_does_not_require_choice(self):
        for flag,expected in (('--backup',True),('--no-backup',False)):
            with patch('prepared.run',return_value={}) as run,patch('builtins.input') as prompt, \
                    contextlib.redirect_stdout(io.StringIO()):
                main(self.argv+[flag])
            self.assertIs(run.call_args.args[0].backup,expected)
            prompt.assert_not_called()
        with patch('csv_plan.export_plan',return_value={}) as export,patch('backup_policy.require_choice') as choice, \
                contextlib.redirect_stdout(io.StringIO()):
            main(self.argv+['--export-table-plan','out.csv'])
            export.assert_called_once();choice.assert_not_called()

    def test_blank_and_invalid_input_never_authorize_backup(self):
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['','yes','x','2']) as prompt, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertIs(select_backup(None,'target','/private/run'),False)
        self.assertEqual(prompt.call_count,4)
        self.assertIn('/private/run/before_import.dump',output.getvalue())

    def test_cancel_and_every_rerun_requires_new_consent(self):
        with patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['1','0','2']) as prompt, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(select_backup(None,'target','/private/run'))
            self.assertIsNone(select_backup(None,'target','/private/run'))
            self.assertFalse(select_backup(None,'target','/private/run'))
        self.assertEqual(prompt.call_count,3)

    def test_skip_never_creates_or_verifies_even_an_existing_corrupt_backup(self):
        with tempfile.TemporaryDirectory() as root:
            stage=Path(root)
            (stage/'before_import.dump').write_bytes(b'untouched corrupt archive')
            (stage/'backup.json').write_text('invalid metadata')
            ensure=Mock(side_effect=AssertionError('backup called'))
            with patch('backup_policy.digest',side_effect=AssertionError('checksum called')), \
                    patch('backup_policy.subprocess.run',side_effect=AssertionError('archive called')):
                result=perform_backup('unused','target',stage,False,ensure=ensure)
            self.assertEqual(result['status'],'skipped')
            self.assertNotIn('path',result)
            self.assertEqual((stage/'before_import.dump').read_bytes(),b'untouched corrupt archive')
            self.assertEqual(loads((stage/'backup-report.json').read_text())['status'],'skipped')
            ensure.assert_not_called()

    def test_created_and_reused_are_reported_per_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            stage=Path(root)
            def ensure(*args):
                (stage/'before_import.dump').write_bytes(b'fixture')
                save_json(stage/'backup.json',dict(database='target',sha256=hashlib.sha256(b'fixture').hexdigest()))
            with patch('backup_policy.subprocess.run',return_value=SimpleNamespace(returncode=0)) as archive:
                first=perform_backup('config','target',stage,True,ensure=ensure)
                second=perform_backup('config','target',stage,True,ensure=ensure)
            self.assertEqual(first['status'],'created');self.assertEqual(second['status'],'reused')
            self.assertEqual(archive.call_count,2)
            self.assertEqual(len(list(stage.glob('backup-decision-*.json'))),2)

    def test_requested_backup_failure_is_recorded_and_raised(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(MigrationError,'fixture failure'):
                perform_backup('config','target',root,True,ensure=Mock(side_effect=MigrationError('fixture failure')))
            report=loads((Path(root)/'backup-report.json').read_text())
            self.assertEqual(report['status'],'failed')
            self.assertTrue(report['requested'])

    def test_failed_checksum_stops_before_archive_validation(self):
        with tempfile.TemporaryDirectory() as root:
            stage=Path(root)
            (stage/'before_import.dump').write_bytes(b'fixture')
            save_json(stage/'backup.json',dict(database='target',sha256='incorrect'))
            with patch('backup_policy.subprocess.run') as archive,self.assertRaisesRegex(MigrationError,'checksum'):
                perform_backup('config','target',stage,True,ensure=Mock())
            archive.assert_not_called()

    def test_missing_or_invalid_programmatic_consent_cannot_backup(self):
        with tempfile.TemporaryDirectory() as root:
            for value in (None,1,'yes'):
                ensure=Mock()
                with self.assertRaises(MigrationError):
                    perform_backup('config','target',root,value,ensure=ensure)
                ensure.assert_not_called()
            self.assertEqual(list(Path(root).iterdir()),[])


if __name__=='__main__':
    unittest.main()
