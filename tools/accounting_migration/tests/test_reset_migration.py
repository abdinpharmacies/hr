import contextlib
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import MigrationError,save_json
from migrate import main
from reset_migration import matching_directories,validate_state


class ResetTests(unittest.TestCase):
    def args(self):
        return ['--source-config','source.conf','--source-db','source','--target-config','target.conf','--target-db','target','--no-backup']

    def test_optional_reset_and_startup_help(self):
        for reset in (False,True):
            with self.subTest(reset=reset),patch('prepared.run') as run,patch('reset_migration.reset') as clear, \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                main(self.args()+(['--reset'] if reset else []))
                self.assertIn('--reset',output.getvalue())
                self.assertEqual(clear.call_count,int(reset))
                self.assertEqual(run.call_count,int(not reset))

    def test_help_only_never_connects(self):
        with patch('common.connect') as connect,contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                main(['--help'])
            self.assertEqual(result.exception.code,0)
            connect.assert_not_called()

    def test_error_help_contains_complete_reset_command(self):
        with patch('prepared.run',side_effect=MigrationError('schema changed')), \
                contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()) as errors:
            with self.assertRaises(MigrationError):
                main(self.args())
        self.assertIn('--target-db target --reset',errors.getvalue())
        self.assertIn('refuses committed imports',errors.getvalue())

    def test_directory_matching_ignores_rules_but_rejects_identity_and_symlinks(self):
        args=SimpleNamespace(source_db='source',target_db='target',source_config='s',target_config='t')
        with tempfile.TemporaryDirectory() as d,patch('reset_migration.endpoint',return_value={}):
            root=Path(d)
            match=root/'match'
            match.mkdir()
            marker=dict(source_db='source',target_db='target',source_endpoint={},target_endpoint={},target_oid=12,rules='old')
            save_json(match/'prepared-run.json',marker)
            unrelated=root/'unrelated'
            unrelated.mkdir()
            save_json(unrelated/'prepared-run.json',{**marker,'target_db':'other'})
            self.assertEqual(matching_directories(root,args,12),[match])
            with self.assertRaisesRegex(MigrationError,'identity'):
                matching_directories(root,args,13)
            (root/'link').symlink_to(match,target_is_directory=True)
            with self.assertRaisesRegex(MigrationError,'Symlink'):
                matching_directories(root,args,12)

    def test_committed_or_unknown_checkpoints_refused(self):
        con=MagicMock()
        cr=con.cursor.return_value.__enter__.return_value
        cr.fetchone.return_value=(True,)
        for name in ('custom_and_xmlids','attachments','validation','unknown'):
            cr.fetchall.return_value=[(name,'{}')]
            with self.assertRaisesRegex(MigrationError,'checkpoints'):
                validate_state(con,SimpleNamespace(),12)
