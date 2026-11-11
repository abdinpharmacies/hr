"""Durable staging tests; all database changes use generated disposable DBs."""
import hashlib
import os
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from psycopg2 import sql
import test_prepared_postgres as fixtures
from common import MigrationError, loads, save_json
from prepared import initialize, read_checkpoint, write_checkpoint
from prepared_snapshot import stage_tables, verify
from prepared_staging import StagingLoader, SCHEMA
from reset_migration import reset
from resume import endpoint, fingerprint


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class StagingPostgresTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PreparedPostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.PreparedPostgresTests.tearDownClass.__func__)
    setUp = fixtures.PreparedPostgresTests.setUp
    tearDown = fixtures.PreparedPostgresTests.tearDown
    scalar = fixtures.PreparedPostgresTests.scalar

    def prepare(self):
        self.run = self.stage / 'run'
        (self.run / 'tables').mkdir(parents=True)
        with self.admin.cursor() as cr:
            cr.execute('SELECT oid FROM pg_database WHERE datname=%s', [self.database])
            oid = cr.fetchone()[0]
        self.args = SimpleNamespace(source_db='unused_source', target_db=self.database,
                                    source_config=self.config, target_config=self.config)
        identity = dict(format=2, source_db=self.args.source_db, target_db=self.database,
                        source_endpoint=endpoint(self.config), target_endpoint=endpoint(self.config), target_oid=oid)
        initialize(self.con, identity)
        self.con.commit()
        save_json(self.run / 'prepared-run.json', identity)
        self.manifest = dict(format=1, complete=True, tables={})
        for table in ('ab_a', 'ab_b', 'ab_c'):
            self.add_table(table, b'1\tone\n')
        return self.manifest

    def add_table(self, table, data, columns=None):
        if columns is None:
            columns = [('id','integer'), ('value','text')]
        (self.run / 'tables' / (table + '.copy')).write_bytes(data)
        self.manifest['tables'][table] = dict(column_order=[c for c, _ in columns],
            columns={c: dict(type=t, required=False, default=None) for c,t in columns}, rows=len(data.splitlines()),
            bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        save_json(self.run / 'snapshot.json', self.manifest)

    def run_staging(self, **kwargs):
        return stage_tables(self.con, self.run, self.manifest, **kwargs)

    def test_failed_middle_table_does_not_lose_other_commits(self):
        self.prepare()
        original = StagingLoader.load
        def fail_middle(loader, table, index):
            if table == 'ab_b':
                raise OSError('injected staging failure')
            return original(loader, table, index)
        with patch.object(StagingLoader, 'load', fail_middle):
            with self.assertRaisesRegex(MigrationError, 'Staging incomplete'):
                self.run_staging()
        self.assertTrue(read_checkpoint(self.con, 'staging:ab_a')['success'])
        self.assertTrue(read_checkpoint(self.con, 'staging:ab_c')['success'])
        self.assertIsNone(read_checkpoint(self.con, 'staging_complete'))
        copied = []
        def record(loader, table, index):
            copied.append(table)
            return original(loader, table, index)
        with patch.object(StagingLoader, 'load', record):
            report = self.run_staging()
        self.assertEqual(copied, ['ab_b'])
        self.assertEqual(report['skipped'], ['ab_a', 'ab_c'])
        self.assertTrue(report['passed'])
        self.assertIsNone(read_checkpoint(self.con, 'staging_failure:ab_b'))
        self.assertFalse(read_checkpoint(self.con, 'staging_history:1:ab_b')['success'])
        self.assertTrue(read_checkpoint(self.con, 'staging_history:2:ab_b')['success'])

    def test_staging_survives_preflight_transaction_rollback(self):
        self.prepare()
        self.run_staging()
        with self.con.cursor() as cr:
            cr.execute('CREATE SCHEMA prepared_migration_work')
            cr.execute('CREATE TABLE prepared_migration_work.preflight_changes(id integer)')
        self.con.rollback()
        with patch.object(StagingLoader, 'load', side_effect=AssertionError('repeated COPY')):
            report = self.run_staging()
        self.assertEqual(report['skipped'], ['ab_a', 'ab_b', 'ab_c'])
        self.assertEqual(self.scalar('SELECT count(*) FROM prepared_migration_source.ab_a'), 1)

    def test_index_failure_rolls_back_only_its_table(self):
        self.prepare()
        original = StagingLoader.build_index
        def fail(loader, cr, table, columns):
            if table == 'ab_b':
                raise MigrationError('injected index failure')
            return original(loader, cr, table, columns)
        with patch.object(StagingLoader, 'build_index', fail):
            with self.assertRaisesRegex(MigrationError, 'Staging incomplete'):
                self.run_staging()
        self.assertIsNone(self.scalar("SELECT to_regclass('prepared_migration_source.ab_b')"))
        self.assertTrue(read_checkpoint(self.con, 'staging:ab_c')['success'])
        self.assertEqual(self.run_staging()['loaded'], ['ab_b'])

    def test_copy_failure_never_leaves_partial_staging_table(self):
        self.prepare()
        self.add_table('ab_b', b'invalid\tvalue\n')
        with self.assertRaisesRegex(MigrationError, 'Staging incomplete'):
            self.run_staging()
        failure = read_checkpoint(self.con, 'staging_failure:ab_b')
        self.assertEqual(failure['sqlstate'], '22P02')
        self.assertNotIn('invalid', str(failure))
        self.assertIsNone(self.scalar("SELECT to_regclass('prepared_migration_source.ab_b')"))
        self.assertTrue(read_checkpoint(self.con, 'staging:ab_c')['success'])

    def test_validation_failure_rolls_back_copied_table(self):
        self.prepare()
        original = StagingLoader.inspect
        def fail(loader, table):
            if table == 'ab_b':
                raise MigrationError('injected count mismatch')
            return original(loader, table)
        with patch.object(StagingLoader, 'inspect', fail):
            with self.assertRaisesRegex(MigrationError, 'Staging incomplete'):
                self.run_staging()
        self.assertIsNone(self.scalar("SELECT to_regclass('prepared_migration_source.ab_b')"))
        self.assertEqual(self.run_staging()['loaded'], ['ab_b'])

    def test_interruption_and_lost_json_use_database_marker(self):
        self.prepare()
        with patch.object(StagingLoader, 'report_progress', side_effect=OSError('lost JSON')):
            with self.assertRaises(OSError):
                self.run_staging()
        self.assertTrue(read_checkpoint(self.con, 'staging:ab_a')['success'])
        original = StagingLoader.load
        def interrupt(loader, table, index):
            if table == 'ab_b':
                raise KeyboardInterrupt()
            return original(loader, table, index)
        with patch.object(StagingLoader, 'load', interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_staging()
        self.con.rollback()
        report = self.run_staging()
        self.assertEqual(report['loaded'], ['ab_b', 'ab_c'])
        self.assertEqual(report['skipped'], ['ab_a'])

    def test_changed_committed_rows_are_not_replaced(self):
        self.prepare()
        self.run_staging()
        with self.con.cursor() as cr:
            cr.execute("UPDATE prepared_migration_source.ab_a SET value='changed'")
        self.con.commit()
        with patch.object(StagingLoader, 'load', side_effect=AssertionError('overwrite')):
            with self.assertRaisesRegex(MigrationError, 'Committed staging data changed'):
                self.run_staging()

    def test_missing_table_or_primary_key_stops_resume(self):
        self.prepare()
        self.run_staging()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE prepared_migration_source.ab_a DROP CONSTRAINT ab_a_pkey')
        self.con.commit()
        with self.assertRaisesRegex(MigrationError, 'primary key'):
            self.run_staging()
        self.con.rollback()
        with self.con.cursor() as cr:
            cr.execute('DROP TABLE prepared_migration_source.ab_a')
        self.con.commit()
        with self.assertRaisesRegex(MigrationError, 'schema missing'):
            self.run_staging()

    def test_snapshot_and_missing_source_file_rejected(self):
        self.prepare()
        self.run_staging()
        self.manifest['different_snapshot'] = True
        with self.assertRaisesRegex(MigrationError, 'snapshot/ownership'):
            self.run_staging()
        self.con.rollback()
        self.manifest.pop('different_snapshot')
        (self.run / 'tables' / 'ab_a.copy').unlink()
        with self.assertRaisesRegex(MigrationError, 'checksum mismatch'):
            verify(self.run, self.manifest)

    def test_identity_staging_is_replaced_once(self):
        self.prepare()
        self.add_table('res_users', b'1\n7\n', [('id','integer')])
        with self.con.cursor() as cr:
            cr.execute('CREATE SCHEMA prepared_migration_source')
            cr.execute('CREATE TABLE prepared_migration_source.res_users(id bigint PRIMARY KEY)')
            cr.execute('INSERT INTO prepared_migration_source.res_users VALUES(1),(7)')
        write_checkpoint(self.con, 'identities', dict(checked=True))
        self.con.commit()
        self.run_staging()
        with patch.object(StagingLoader, 'load', side_effect=AssertionError('identity restaging')):
            self.assertTrue(self.run_staging()['passed'])
        self.assertEqual(self.scalar('SELECT array_agg(id ORDER BY id) FROM prepared_migration_source.res_users'), [1,7])

    def test_legacy_setup_adopts_without_copying(self):
        self.prepare()
        with self.con.cursor() as cr:
            cr.execute('CREATE SCHEMA prepared_migration_source')
            for table in self.manifest['tables']:
                cr.execute(sql.SQL('CREATE TABLE {}(id integer PRIMARY KEY,value text)').format(sql.Identifier(SCHEMA,table)))
                cr.execute(sql.SQL("INSERT INTO {} VALUES(1,'one')").format(sql.Identifier(SCHEMA,table)))
        setup = dict(snapshot=fingerprint(self.manifest), started=True)
        write_checkpoint(self.con, 'table_setup', setup)
        self.con.commit()
        with patch.object(StagingLoader, 'load', side_effect=AssertionError('legacy recopy')):
            report = self.run_staging(legacy_setup=setup)
        self.assertEqual(report['adopted'], ['ab_a', 'ab_b', 'ab_c'])

    def test_unexplained_staging_cannot_be_adopted(self):
        self.prepare()
        with self.con.cursor() as cr:
            cr.execute('CREATE SCHEMA prepared_migration_source')
            cr.execute('CREATE TABLE prepared_migration_source.ab_a(id integer,value text)')
        self.con.commit()
        with self.assertRaisesRegex(MigrationError, 'no success marker'):
            self.run_staging()

    def test_reset_allows_staging_only_but_refuses_live_setup(self):
        self.prepare()
        self.run_staging()
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE public.preserved(id integer PRIMARY KEY)')
            cr.execute('INSERT INTO public.preserved VALUES(42)')
        self.con.commit()
        write_checkpoint(self.con, 'table_setup', dict(started=True))
        self.con.commit()
        with patch('builtins.input') as prompt:
            with self.assertRaisesRegex(MigrationError, 'checkpoints'):
                reset(self.args, self.stage)
            prompt.assert_not_called()
        with self.con.cursor() as cr:
            cr.execute("DELETE FROM prepared_custom_migration.checkpoint WHERE name='table_setup'")
        self.con.commit()
        with patch('builtins.input', return_value='yes'):
            self.assertTrue(reset(self.args, self.stage)['reset'])
        self.assertEqual(self.scalar('SELECT id FROM public.preserved'), 42)
        self.assertIsNone(self.scalar("SELECT to_regnamespace('prepared_migration_source')"))
        self.assertFalse(self.run.exists())
