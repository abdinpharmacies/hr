"""Opt-in transaction tests. Never uses Odoo configs or existing migration DBs.

Set MIGRATION_RECOVERY_TEST_DSN explicitly to a disposable database whose name
starts with codex_migration_test_. Normal offline discovery skips these tests.
"""
import os
from pathlib import Path
import sys
import unittest
import uuid
import io
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resume import get_checkpoint, put_checkpoint


@unittest.skipUnless(os.environ.get('MIGRATION_RECOVERY_TEST_DSN'), 'requires explicitly selected disposable PostgreSQL database')
class PostgresRecoveryTests(unittest.TestCase):
    def test_copy_and_checkpoint_commit_or_rollback_together(self):
        import psycopg2
        from psycopg2.extensions import parse_dsn
        dsn = os.environ['MIGRATION_RECOVERY_TEST_DSN']
        if not parse_dsn(dsn).get('dbname', '').startswith('codex_migration_test_'):
            self.fail('Recovery test database name must start with codex_migration_test_')
        namespace = 'recovery_' + uuid.uuid4().hex
        connection = psycopg2.connect(dsn)
        connection.autocommit = True
        cursor = connection.cursor()
        cursor.execute('CREATE SCHEMA ' + namespace)
        cursor.execute('CREATE TABLE ' + namespace + '.checkpoint(name text PRIMARY KEY,value text)')
        class ScopedCursor:
            def execute(self, statement, params=None):
                cursor.execute(statement.replace('accounting_migration.', namespace + '.'), params)
            def fetchone(self): return cursor.fetchone()
        scoped = ScopedCursor()
        try:
            connection.autocommit = False
            cursor.execute('CREATE TABLE ' + namespace + '.copied(id integer PRIMARY KEY)')
            cursor.copy_expert('COPY ' + namespace + '.copied FROM STDIN', io.StringIO('1\n2\n'))
            put_checkpoint(scoped, 'copy:copied', {'identity': 'original', 'source_rows': 2})
            # Simulate interruption before commit: neither table nor checkpoint survives.
            connection.rollback()
            self.assertIsNone(get_checkpoint(scoped, 'copy:copied'))
            cursor.execute('SELECT to_regclass(%s)', [namespace + '.copied'])
            self.assertIsNone(cursor.fetchone()[0])
            cursor.execute('CREATE TABLE ' + namespace + '.copied(id integer PRIMARY KEY)')
            cursor.copy_expert('COPY ' + namespace + '.copied FROM STDIN', io.StringIO('1\n2\n'))
            put_checkpoint(scoped, 'copy:copied', {'identity': 'original', 'source_rows': 2})
            connection.commit()
            # A later partially copied table fails, without undoing the earlier commit.
            cursor.execute('CREATE TABLE ' + namespace + '.partial(id integer PRIMARY KEY)')
            with self.assertRaises(psycopg2.Error):
                cursor.copy_expert('COPY ' + namespace + '.partial FROM STDIN', io.StringIO('3\ninvalid\n'))
            connection.rollback()
            self.assertEqual(get_checkpoint(scoped, 'copy:copied')['source_rows'], 2)
            self.assertIsNone(get_checkpoint(scoped, 'copy:partial'))
            cursor.execute('SELECT count(*) FROM ' + namespace + '.copied')
            self.assertEqual(cursor.fetchone()[0], 2)
            # Commit durable business status, then lose the client before any JSON report.
            put_checkpoint(scoped, 'business', {'identity': 'mapped', 'report': {'passed': True}})
            connection.commit()
            connection.close()
            connection = psycopg2.connect(dsn)
            cursor = connection.cursor()
            self.assertTrue(get_checkpoint(scoped, 'business')['report']['passed'])
        finally:
            if connection.closed:
                connection = psycopg2.connect(dsn)
            connection.rollback()
            connection.autocommit = True
            with connection.cursor() as cleanup:
                cleanup.execute('DROP SCHEMA ' + namespace + ' CASCADE')
            connection.close()

    def test_identity_resolution_equivalence_and_synthetic_benchmark(self):
        """Compare both resolvers, write volume and a synthetic mapping/load path."""
        import json
        import time
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extensions import parse_dsn
        from mapping import MappingStrategies
        dsn = os.environ['MIGRATION_RECOVERY_TEST_DSN']
        if not parse_dsn(dsn).get('dbname', '').startswith('codex_migration_test_'):
            self.fail('Recovery test database name must start with codex_migration_test_')
        namespace = 'identity_' + uuid.uuid4().hex
        con = psycopg2.connect(dsn)
        cr = con.cursor()
        cr.execute('CREATE SCHEMA ' + namespace)
        try:
            cr.execute('CREATE TABLE ' + namespace + '.source_rows(id integer PRIMARY KEY)')
            cr.execute('INSERT INTO ' + namespace + '.source_rows SELECT generate_series(1,10000)')
            cr.execute('INSERT INTO ' + namespace + '.source_rows VALUES (-7),(0)')
            cr.execute('CREATE TABLE ' + namespace + '.record_map(model text,source_id integer,target_id integer, '
                       'PRIMARY KEY(model,source_id),UNIQUE(model,target_id))')
            cr.execute('INSERT INTO ' + namespace + ".record_map VALUES ('res.users',1,90001)")
            engine = MappingStrategies()
            model = 'abdin_eplus.example'
            engine.models = {model: {'table': 'source_rows'}}
            def execute(query):
                text = query.as_string(con) if not isinstance(query, str) else query
                cr.execute(text.replace('"accounting_migration_source"', '"' + namespace + '"')
                           .replace('accounting_migration.record_map', namespace + '.record_map'))
            results, samples, metrics = {}, {}, {}
            for mode in ('explicit', 'identity'):
                if mode == 'identity':
                    # Fixture setup is outside timing; never done to a production run.
                    cr.execute('DELETE FROM ' + namespace + '.record_map WHERE model=%s', [model])
                    con.commit()
                start = time.monotonic()
                if mode == 'explicit':
                    cr.execute('INSERT INTO ' + namespace + '.record_map SELECT %s,id,id FROM ' + namespace + '.source_rows', [model])
                else:
                    cr.execute('CREATE TABLE ' + namespace + '.model_plan(model text PRIMARY KEY,strategy text)')
                    cr.execute('INSERT INTO ' + namespace + '.model_plan VALUES (%s,%s)', [model, mode])
                con.commit()
                mapping_seconds = time.monotonic() - start
                engine.mapping_modes = {model: mode}
                own = sql.SQL('s.id') if mode == 'identity' else engine.mapped_expression(sql.Literal(model), sql.SQL('s.id'))
                parent = engine.mapped_expression(sql.Literal(model), sql.SQL('s.id-1'))
                query = sql.SQL('CREATE TABLE {} AS SELECT {} id,{} parent_id FROM {} s').format(
                    sql.Identifier(namespace, 'loaded_' + mode), own, parent, sql.Identifier(namespace, 'source_rows'))
                execute(query)
                con.commit()
                total_seconds = time.monotonic() - start
                cr.execute('SELECT * FROM ' + namespace + '.loaded_' + mode + ' ORDER BY id')
                results[mode] = cr.fetchall()
                dynamic = engine.mapped_expression(sql.SQL('v.model'), sql.SQL('v.ref'))
                execute(sql.SQL('SELECT v.model,v.ref,{} FROM (VALUES ({},-7),({},0),({},1),({},999999),({},NULL::integer),'
                                "('res.users',1),('res.users',2),('unknown',1)) v(model,ref) ORDER BY v.model,v.ref NULLS LAST").format(
                                    dynamic, *[sql.Literal(model)] * 5))
                samples[mode] = cr.fetchall()
                cr.execute('SELECT count(*) FROM ' + namespace + '.record_map WHERE model=%s', [model])
                entries = cr.fetchone()[0]
                cr.execute('SELECT pg_total_relation_size(%s)', [namespace + ('.record_map' if mode == 'explicit' else '.model_plan')])
                metrics[mode] = dict(mapping_seconds=mapping_seconds, mapping_and_load_seconds=total_seconds,
                                     mapping_storage_bytes=cr.fetchone()[0], mapping_rows=entries)
            self.assertEqual(results['explicit'], results['identity'])
            self.assertEqual(samples['explicit'], samples['identity'])
            self.assertEqual(metrics['identity']['mapping_rows'], 0)
            self.assertEqual(metrics['explicit']['mapping_rows'], 10002)
            print('Synthetic identity benchmark:', json.dumps(metrics, sort_keys=True))
        finally:
            con.rollback()
            cr.execute('DROP SCHEMA ' + namespace + ' CASCADE')
            con.commit()
            con.close()

    def test_seed_swap_references_constraints_and_rollback(self):
        import psycopg2
        from psycopg2 import sql
        from psycopg2.extensions import parse_dsn
        from unittest.mock import MagicMock
        from seeds import StrictSeeds, relocation_plan
        dsn = os.environ['MIGRATION_RECOVERY_TEST_DSN']
        if not parse_dsn(dsn).get('dbname', '').startswith('codex_migration_test_'):
            self.fail('Recovery test database name must start with codex_migration_test_')
        namespace = 'seeds_' + uuid.uuid4().hex
        con = psycopg2.connect(dsn)
        cr = con.cursor()
        cr.execute('CREATE SCHEMA ' + namespace)
        cr.execute('SET search_path TO ' + namespace + ',public')
        cr.execute('CREATE TABLE company(id integer PRIMARY KEY,name text)')
        cr.execute("INSERT INTO company VALUES (1,'seed A'),(2,'seed B')")
        cr.execute('CREATE TABLE child(id integer PRIMARY KEY,company_id integer REFERENCES company(id) DEFERRABLE INITIALLY DEFERRED, property jsonb)')
        cr.execute('INSERT INTO child VALUES (50,1,\'{"1":2,"2":null}\')')
        cr.execute('CREATE TABLE metadata(id integer PRIMARY KEY,model text,res_id integer)')
        cr.execute("INSERT INTO metadata VALUES (77,'res.company',1)")
        cr.execute('CREATE TABLE seed_move(model text,old_id bigint,temp_id bigint,new_id bigint,reason text)')
        moves = relocation_plan('res.company', {1,2}, 2, {1,2}, [(2,1),(1,2)])
        for move in moves:
            cr.execute('INSERT INTO seed_move VALUES (%s,%s,%s,%s,%s)', [move[k] for k in ('model','old_id','temp_id','new_id','reason')])
        con.commit()
        engine = StrictSeeds()
        engine.env = MagicMock()
        engine.seed_moves = moves
        engine.seed_references = [('scalar','child','company_id','res.company',''),
                                  ('company_json','child','property','res.company',''),
                                  ('polymorphic','metadata','res_id','','model')]
        engine.dst = lambda model: sql.Identifier('company')
        def execute(query, params=None):
            statement = query.as_string(con) if not isinstance(query,str) else query
            cr.execute(statement.replace('accounting_migration.seed_move', namespace+'.seed_move'), params)
        engine.execute = execute
        try:
            engine.relocate_seeds()
            cr.execute('SELECT name FROM company WHERE id=2')
            self.assertEqual(cr.fetchone()[0], 'seed A')
            cr.execute('SELECT company_id,property FROM child')
            self.assertEqual(cr.fetchone(), (2, {'2':1,'1':None}))
            cr.execute('SELECT id,res_id FROM metadata')
            self.assertEqual(cr.fetchone(), (77,2))
            # Inject a business-load failure after seed movement: all movement rolls back.
            with self.assertRaises(psycopg2.Error):
                cr.execute('INSERT INTO company VALUES (1,\'duplicate\')')
            con.rollback()
            cr.execute('SELECT name FROM company WHERE id=1')
            self.assertEqual(cr.fetchone()[0], 'seed A')
            cr.execute('SELECT company_id FROM child')
            self.assertEqual(cr.fetchone()[0], 1)
            engine.relocate_seeds()
            cr.execute('SET CONSTRAINTS ALL IMMEDIATE')
            con.commit()
            cr.execute('SELECT company_id FROM child')
            self.assertEqual(cr.fetchone()[0], 2)
        finally:
            con.rollback()
            cr.execute('DROP SCHEMA ' + namespace + ' CASCADE')
            con.commit()
            con.close()
