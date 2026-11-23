"""Local peer authentication, privilege boundaries, and secret-free failures."""
import contextlib
import io
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError, connect, settings, ensure_backup
import local_peer
from migrate import main
from migration_menu import DEFAULTS, run_menu


class LocalPeerTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.account = SimpleNamespace(pw_name='postgres', pw_uid=123, pw_gid=456, pw_dir='/var/lib/postgresql')

    def config(self, root, **options):
        path = Path(root) / 'odoo.conf'
        values = dict(db_host='False', db_port='False', db_user='odoo15', db_password='secret', data_dir='/srv/odoo15')
        values.update(options)
        path.write_text('[options]\n' + ''.join(f'{key} = {value}\n' for key, value in values.items()))
        return path

    def test_normal_settings_and_read_only_connections_are_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.config(root)
            before = path.read_bytes()
            with patch('common.psycopg2.connect') as pg:
                con = connect(path, 'source')
                pg.assert_called_once_with(dbname='source', connect_timeout=10, user='odoo15', password='secret')
                con.set_session.assert_called_once_with(readonly=True, isolation_level='REPEATABLE READ')
            self.assertEqual(path.read_bytes(), before)

    def test_peer_settings_for_both_configs_and_target_maintenance(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {local_peer.ENV: '1'}), \
                patch('local_peer.pwd.getpwuid', return_value=self.account):
            path = self.config(root)
            before = path.read_bytes()
            for role in ('odoo15', 'odoo19'):
                self.config(root, db_user=role, db_port='5433', db_host='/var/run/postgresql')
                with patch('common.psycopg2.connect') as pg:
                    con = connect(path, 'postgres', readonly=False)
                    pg.assert_called_once_with(dbname='postgres', connect_timeout=10, host='/var/run/postgresql', port='5433', user='postgres')
                    con.set_session.assert_called_once_with(readonly=False, isolation_level='READ COMMITTED')
                self.assertEqual(settings(path)['data_dir'], '/srv/odoo15')
            # Settings are in-memory overrides, not changes to either service file.
            self.config(root)
            settings(path)
            self.assertEqual(path.read_bytes(), before)

    def test_peer_mode_refuses_wrong_os_user_and_tcp_hosts(self):
        with patch.dict(os.environ, {local_peer.ENV: '1'}), \
                patch('local_peer.pwd.getpwuid', return_value=SimpleNamespace(pw_name='root')):
            with self.assertRaisesRegex(MigrationError, 'Linux postgres'):
                local_peer.enabled()
        with patch('local_peer.enabled', return_value=True):
            for host in ('127.0.0.1', 'localhost', 'database.example'):
                with self.assertRaisesRegex(MigrationError, 'TCP hosts are refused'):
                    local_peer.connection_settings({'db_host': host})

    def test_safe_actionable_connection_errors_do_not_leak_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            path = self.config(root)
            for error, expected in [('Peer authentication failed for user secret', '--local-peer'),
                                    ('password=secret server details', 'check the database name')]:
                with patch('common.psycopg2.connect', side_effect=psycopg2.OperationalError(error)):
                    with self.assertRaisesRegex(MigrationError, expected) as caught:
                        connect(path, 'source')
                    self.assertNotIn('secret', str(caught.exception))
                    self.assertNotIn('server details', str(caught.exception))

    def test_launcher_drops_privileges_and_preserves_arguments(self):
        argv = ['--source-config', '/source.conf', '--target-config', '/target.conf',
                '--source-db', 'source', '--target-db', 'target', '--table-plan', '/plan.csv', '--backup']
        with patch('local_peer.pwd.getpwnam', return_value=self.account), \
                patch('local_peer.os.geteuid', return_value=0), \
                patch('local_peer.prepare_workspace', return_value=Path('/runs/local-peer')) as workspace, \
                patch('local_peer.runtime_groups', return_value=[456, 789]), \
                patch('local_peer.os.setgroups') as groups, patch('local_peer.os.setgid') as gid, \
                patch('local_peer.os.setuid') as uid, patch('local_peer.os.chdir'), \
                patch('local_peer.os.access', return_value=True), \
                patch('local_peer.os.umask'), patch('local_peer.os.execve') as execute, \
                patch.dict(os.environ, {'PGHOST': 'remote', 'PGPASSWORD': 'secret'}), \
                contextlib.redirect_stdout(io.StringIO()):
            local_peer.launch(argv, Path('/runs'))
            workspace.assert_called_once_with(Path('/runs/local-peer'), self.account)
            groups.assert_called_once_with([456, 789])
            gid.assert_called_once_with(456)
            uid.assert_called_once_with(123)
            executable, command, env = execute.call_args.args
            self.assertEqual(command, [sys.executable, '-B', str(local_peer.HERE / 'migrate.py'), *argv])
            self.assertEqual(env[local_peer.ENV], '1')
            self.assertNotIn('PGHOST', env)
            self.assertNotIn('PGPASSWORD', env)

    def test_launcher_refuses_unprivileged_user_and_legacy_workflow(self):
        with patch('local_peer.pwd.getpwnam', return_value=self.account), \
                patch('local_peer.os.geteuid', return_value=999), patch('local_peer.os.execve') as execute:
            with self.assertRaisesRegex(MigrationError, 'with sudo'):
                local_peer.launch([], Path('/runs'))
            execute.assert_not_called()
        for argv in (['--reset'], ['--source-db', 'source']):
            with self.assertRaisesRegex(MigrationError, 'CSV menu'):
                local_peer.launch(argv, Path('/runs'))
        for extra in (['--extra-actions', 'copy-filestore'], ['--extra-actions=menu']):
            with self.assertRaisesRegex(MigrationError, 'filestore actions'):
                local_peer.launch(['--table-plan=/plan.csv', *extra], Path('/runs'))

    def test_runtime_adds_only_group_needed_for_restricted_ancestor(self):
        with tempfile.TemporaryDirectory() as root, patch('local_peer.os.getgrouplist', return_value=[456]):
            root = Path(root)
            root.chmod(0o755)
            restricted = root / 'odoo19'
            restricted.mkdir(mode=0o750)
            restricted.chmod(0o750)
            runtime = restricted / 'tools'
            runtime.mkdir(mode=0o755)
            runtime.chmod(0o755)
            groups = local_peer.runtime_groups([runtime], self.account)
            self.assertEqual(set(groups), {456, restricted.stat().st_gid})
            self.assertEqual(restricted.stat().st_mode & 0o777, 0o750)
            restricted.chmod(0o700)
            with self.assertRaisesRegex(MigrationError, 'not traversable'):
                local_peer.runtime_groups([runtime], self.account)

    def test_runtime_does_not_inherit_unnecessary_parent_groups(self):
        with tempfile.TemporaryDirectory() as root, patch('local_peer.os.getgrouplist', return_value=[456]):
            root = Path(root)
            root.chmod(0o755)
            self.assertEqual(local_peer.runtime_groups([root], self.account), [456])

    def test_workspace_refuses_symlink_and_does_not_chown_existing_artifacts(self):
        account = SimpleNamespace(pw_uid=os.getuid(), pw_gid=os.getgid())
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'private'
            path.mkdir(mode=0o700)
            with patch('local_peer.os.chown') as chown:
                self.assertEqual(local_peer.prepare_workspace(path, account), path)
                chown.assert_not_called()
                link = Path(root) / 'link'
                link.symlink_to(path, target_is_directory=True)
                with self.assertRaisesRegex(MigrationError, 'real directory'):
                    local_peer.prepare_workspace(link, account)
                path.chmod(0o755)
                with self.assertRaisesRegex(MigrationError, '0700'):
                    local_peer.prepare_workspace(path, account)

    def test_local_peer_help_does_not_launch_or_create_workspace(self):
        with patch('local_peer.launch') as launch, contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--local-peer', '--help']), 0)
        launch.assert_not_called()
        self.assertIn('--local-peer', output.getvalue())

    def test_local_menu_uses_private_csv_default(self):
        with tempfile.TemporaryDirectory() as root, patch('local_peer.enabled', return_value=True), \
                patch('builtins.input', side_effect=['1', '0']), \
                patch('migration_menu.collect', return_value=DEFAULTS) as collect, \
                contextlib.redirect_stdout(io.StringIO()):
            run_menu(Mock(), root)
            self.assertEqual(collect.call_args.args[0]['csv_path'], str(Path(root) / 'table-plan.csv'))

    def test_backup_uses_same_peer_role_as_connections(self):
        with tempfile.TemporaryDirectory() as root, patch('local_peer.enabled', return_value=True), \
                patch('subprocess.run') as run:
            path = self.config(root)
            run.return_value = SimpleNamespace(returncode=0)
            ensure_backup(path, 'target', Path(root))
            self.assertEqual(run.call_args.kwargs['env']['PGUSER'], 'postgres')
            self.assertNotIn('PGPASSWORD', run.call_args.kwargs['env'])


if __name__ == '__main__':
    unittest.main()
