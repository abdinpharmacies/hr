"""Real PostgreSQL lock lifecycle and immutable standard-table regression cases."""
import io
import os
import threading
import unittest
from unittest.mock import patch

from psycopg2 import sql
import test_prepared_postgres as fixtures
from common import connect,MigrationError
from prepared import SmokeWorker,read_checkpoint,write_checkpoint
from prepared_metadata import wait_for_import
from raw_importer import RawImporter
from table_checkpoints import TableMigration
from standard_protection import StandardProtection


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'),'requires disposable PostgreSQL config')
class StandardProtectionTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PreparedPostgresTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PreparedPostgresTests.tearDownClass.__func__)
    setUp=fixtures.PreparedPostgresTests.setUp
    tearDown=fixtures.PreparedPostgresTests.tearDown
    scalar=fixtures.PreparedPostgresTests.scalar
    fixture=fixtures.PreparedPostgresTests.fixture

    def raw_engine(self):
        engine=RawImporter(*self.arguments)
        engine.validate_ids()
        engine.preflight(replacing=not bool(read_checkpoint(self.con,'table_setup')))
        return engine

    def run_raw(self):
        return TableMigration(self.raw_engine(),write_checkpoint).run(self.source_files,self.target_files)

    def definitions(self):
        with self.con.cursor() as cr:
            cr.execute("SELECT s.relname,k.conname,pg_get_constraintdef(k.oid) FROM pg_constraint k "
                       "JOIN pg_class s ON s.oid=k.conrelid JOIN pg_namespace n ON n.oid=s.relnamespace "
                       "WHERE n.nspname='public' AND s.relname IN ('res_users','res_partner','res_company',"
                       "'user_group_link','ir_attachment') ORDER BY 1,2")
            return cr.fetchall()

    def test_standard_rows_and_definitions_remain_identical(self):
        self.fixture()
        before=self.definitions()
        users=self.scalar('SELECT jsonb_agg(t ORDER BY id) FROM res_users t')
        target=self.scalar('SELECT group_id FROM ab_target_only')
        result=self.run_raw()
        self.assertEqual(self.definitions(),before)
        self.assertEqual(self.scalar('SELECT jsonb_agg(t ORDER BY id) FROM res_users t'),users)
        self.assertEqual(self.scalar('SELECT group_id FROM ab_target_only'),target)
        self.assertEqual(self.scalar('SELECT id FROM ab_group'),7)
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)
        self.assertTrue(any(x['table']=='ab_group' and x['operation']=='copy' for x in result['failed_tables']))
        self.assertTrue(all(c.get('protected') for c in result['constraints'] if c['table']=='res_users'))

    def test_protected_cascade_set_null_no_action_and_composite(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE res_company(id integer PRIMARY KEY,group_id integer REFERENCES ab_group(id) ON DELETE CASCADE)')
            cr.execute('INSERT INTO res_company VALUES(1,7)')
            cr.execute('ALTER TABLE res_partner ADD COLUMN group_id integer REFERENCES ab_group(id) ON DELETE NO ACTION')
            cr.execute('UPDATE res_partner SET group_id=7 WHERE id=1')
            cr.execute('ALTER TABLE ab_group ADD CONSTRAINT group_pair UNIQUE(id,name)')
            cr.execute('ALTER TABLE res_users ADD COLUMN group_name varchar')
            cr.execute("UPDATE res_users SET group_name='old group' WHERE id=1")
            cr.execute('ALTER TABLE res_users ADD CONSTRAINT group_pair_fk '
                       'FOREIGN KEY(accounting_auth_group_id,group_name) REFERENCES ab_group(id,name) ON DELETE CASCADE')
        self.con.commit()
        before=self.definitions()
        result=self.run_raw()
        self.assertEqual(self.definitions(),before)
        self.assertEqual(self.scalar('SELECT group_id FROM res_company'),7)
        self.assertEqual(self.scalar('SELECT group_id FROM res_partner WHERE id=1'),7)
        self.assertEqual(self.scalar('SELECT accounting_auth_group_id FROM res_users WHERE id=1'),7)
        self.assertEqual(self.scalar('SELECT id FROM ab_group'),7)
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)

    def test_alias_and_native_relation_cannot_bypass_write_guard(self):
        self.fixture()
        engine=self.raw_engine()
        engine.target['ab_alias']=dict(table='res_users',fields={})
        engine.selected.add('ab_alias')
        engine.target['res.users']['fields']['group_ids']=dict(type='many2many',module='base',
            relation_table='ab_fake_rel',relation='res.groups')
        engine.relations.append(dict(table='ab_fake_rel'))
        guard=StandardProtection(engine)
        for table in ('res_users','res_partner','res_company','ab_fake_rel'):
            with self.assertRaisesRegex(MigrationError,'Protected'):
                guard.require_write(table,'copy')
            self.assertFalse(guard.can_alter(table))
        guard.require_write('ir_attachment','attachments')
        guard.require_write('ir_model_data','xmlids')
        self.assertFalse(guard.can_alter('ir_attachment'))

    def test_old_saved_standard_constraint_is_never_recreated(self):
        self.fixture()
        result=self.run_raw()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE res_users DROP CONSTRAINT res_users_accounting_auth_group_id_fkey')
        self.con.commit()
        second=self.run_raw()
        self.assertFalse(self.scalar("SELECT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='res_users_accounting_auth_group_id_fkey')"))
        self.assertTrue(any(c['table']=='res_users' and c.get('protected') and not c.get('restored') for c in second['constraints']))

    def test_worker_releases_read_locks_and_observes_new_commits_after_go(self):
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE ab_lock_parent(id integer PRIMARY KEY,name text)')
            cr.execute("INSERT INTO ab_lock_parent VALUES(1,'before')")
            cr.execute('CREATE TABLE ab_lock_child(id integer REFERENCES ab_lock_parent(id))')
        self.con.commit()
        ready=threading.Event()
        go=threading.Event()
        errors=[]
        observed=[]
        cache={'name':'before'}
        pids=[]
        class Output(io.StringIO):
            def write(self,value):
                result=super().write(value)
                if '@PREPARED_READY@' in value:
                    ready.set()
                return result
        class Input:
            def readline(self):
                return 'GO\n' if go.wait(10) else ''
        def worker():
            connection=connect(self.config,self.database,readonly=True)
            try:
                pids.append(connection.get_backend_pid())
                with connection.cursor() as cr:
                    cr.execute('SELECT * FROM ab_lock_child')
                    wait_for_import(connection.rollback,cache.clear,connection.get_backend_pid,Input(),Output())
                    self.assertFalse(cache)
                    cr.execute('SELECT name FROM ab_lock_parent WHERE id=1')
                    observed.append(cr.fetchone()[0])
            except Exception as exc:
                errors.append(exc)
            finally:
                connection.close()
        thread=threading.Thread(target=worker)
        thread.start()
        try:
            self.assertTrue(ready.wait(5),'worker did not announce readiness')
            smoke=SmokeWorker.__new__(SmokeWorker)
            smoke.config,smoke.database,smoke.pid=self.config,self.database,pids[0]
            smoke.verify_idle()
            with self.con.cursor() as cr:
                cr.execute("SET LOCAL lock_timeout='1s'")
                cr.execute('ALTER TABLE ab_lock_child DROP CONSTRAINT ab_lock_child_id_fkey')
                cr.execute("UPDATE ab_lock_parent SET name='after' WHERE id=1")
            self.con.commit()
        finally:
            go.set()
            thread.join(5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(errors,[])
        self.assertEqual(observed,['after'])

    def test_parent_rejects_worker_with_open_read_transaction(self):
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE ab_lock(id integer)')
        self.con.commit()
        worker=connect(self.config,self.database,readonly=True)
        try:
            with worker.cursor() as cr:
                cr.execute('SELECT * FROM ab_lock')
            smoke=SmokeWorker.__new__(SmokeWorker)
            smoke.config,smoke.database,smoke.pid=self.config,self.database,worker.get_backend_pid()
            with self.assertRaisesRegex(MigrationError,'retained a transaction'):
                smoke.verify_idle()
            worker.rollback()
            smoke.verify_idle()
        finally:
            worker.close()
