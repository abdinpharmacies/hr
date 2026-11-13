"""CSV replication exclusively in generated disposable PostgreSQL databases."""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch

from psycopg2 import sql
import test_prepared_postgres as fixtures
from common import connect, MigrationError, loads, save_json, settings
from csv_plan import export_plan, read_plan, discover, relation_scope, convert_plan, HEADERS, VERSION
from csv_copy import extract, verify_files, copy_table, table_fingerprint, restart_sequence
from csv_replicator import CSVRunner, initialize, read_state, run, FORMAT
from csv_relations import plan_operations


def relation_copy_only(*args, **kwargs):
    if kwargs.get('relation') is None:
        raise AssertionError('count-skipped model unexpectedly copied')
    return copy_table(*args, **kwargs)


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class CSVPostgresTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PreparedPostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.PreparedPostgresTests.tearDownClass.__func__)
    scalar = fixtures.PreparedPostgresTests.scalar

    def setUp(self):
        fixtures.PreparedPostgresTests.setUp(self)
        self.source_db = 'codex_migration_test_prepared_' + uuid.uuid4().hex[:12]
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.source_db)))
        self.source = connect(self.config, self.source_db, readonly=False)
        self.args = SimpleNamespace(source_config=self.config, target_config=self.config,
                                    source_db=self.source_db, target_db=self.database,
                                    export_table_plan=str(self.stage / 'plan.csv'), extra_actions=None)
        self.args.table_plan = self.args.export_table_plan
        for con, user, record, other in ((self.source, 13, 42, 21), (self.con, 7, 9, 8)):
            with con.cursor() as cr:
                cr.execute('CREATE TABLE ir_module_module(id serial PRIMARY KEY,name varchar,state varchar)')
                cr.execute('CREATE TABLE ir_model(id serial PRIMARY KEY,model varchar,transient boolean)')
                cr.execute('CREATE TABLE ir_model_fields(id serial PRIMARY KEY,model varchar,name varchar,ttype varchar,'
                           'relation_table varchar,column1 varchar,column2 varchar,related varchar,relation varchar,store boolean DEFAULT true)')
                cr.execute('CREATE TABLE ir_model_data(id serial PRIMARY KEY,module varchar,name varchar,model varchar,res_id integer,UNIQUE(module,name))')
                cr.execute('CREATE TABLE ir_model_fields_selection(id serial PRIMARY KEY,field_id integer REFERENCES ir_model_fields(id),value varchar,sequence integer)')
                cr.execute('CREATE TABLE res_users(id serial PRIMARY KEY,name varchar,password varchar)')
                cr.execute('CREATE TABLE ab_record(id serial PRIMARY KEY,name text,create_uid integer REFERENCES res_users(id))')
                cr.execute('CREATE TABLE ab_other(id serial PRIMARY KEY,name text)')
                cr.execute('CREATE TABLE ir_attachment(id serial PRIMARY KEY,name text)')
                cr.execute('CREATE TABLE a_b_rel(record_id integer REFERENCES ab_record(id),other_id integer REFERENCES ab_other(id),PRIMARY KEY(record_id,other_id))')
                cr.execute('CREATE TABLE ignored(id integer PRIMARY KEY,create_uid integer REFERENCES res_users(id) ON DELETE CASCADE,'
                           'write_uid integer REFERENCES res_users(id) ON DELETE SET NULL)')
                for model in ('res.users', 'ab_record', 'ab_other', 'ir.attachment', 'ir.model', 'ir.model.fields', 'ir.module.module'):
                    cr.execute('INSERT INTO ir_model(model,transient) VALUES(%s,false)', [model])
                cr.execute("INSERT INTO ir_model_fields(model,name,ttype,relation_table,column1,column2) VALUES"
                           "('ab_record','others','many2many','a_b_rel','record_id','other_id'),"
                           "('ab_other','records','many2many','a_b_rel','other_id','record_id')")
                cr.execute("UPDATE ir_model_fields SET relation=CASE model WHEN 'ab_record' THEN 'ab_other' ELSE 'ab_record' END")
                cr.execute("INSERT INTO ir_model_fields(model,name,ttype,relation) VALUES('ab_record','create_uid','many2one','res.users')")
                for model, name, rid in [('res.users', 'user', user), ('ab_other', 'other', other), ('ab_record', 'record', record)]:
                    cr.execute("INSERT INTO ir_model_data(module,name,model,res_id) VALUES('fixture',%s,%s,%s)", [name, model, rid])
                cr.execute('INSERT INTO res_users VALUES(%s,%s,%s)', [user, 'user', 'private-password'])
                cr.execute('INSERT INTO ab_record VALUES(%s,%s,%s)', [record, 'text\tline\n\\N', user])
                cr.execute('INSERT INTO ab_other VALUES(%s,%s)', [other, 'other'])
                cr.execute('INSERT INTO a_b_rel VALUES(%s,%s)', [record, other])
                cr.execute('INSERT INTO ignored VALUES(1,%s,%s)', [user, user])
            con.commit()
        # Count-only verification must copy these mismatched-count fixtures;
        # equal counts intentionally skip even when IDs or values differ.
        with self.con.cursor() as cr:
            cr.execute("INSERT INTO res_users VALUES(-99,'count fixture','test')")
            cr.execute("INSERT INTO ab_record VALUES(-99,'count fixture',7)")
            cr.execute("INSERT INTO ab_other VALUES(-99,'count fixture')")
        self.con.commit()

    def tearDown(self):
        self.source.close()
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(self.source_db)))
            cr.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s "
                       "AND usename=current_user AND backend_type='client backend'", [self.source_db])
            cr.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(self.source_db)))
        fixtures.PreparedPostgresTests.tearDown(self)

    def export(self, selections=None, constants=None, overrides=None):
        with contextlib.redirect_stdout(io.StringIO()):
            export_plan(self.args)
        self.edit(selections, constants, overrides)
        return read_plan(self.args.table_plan)

    def edit(self, selections=None, constants=None, overrides=None):
        path = Path(self.args.table_plan)
        with path.open(newline='') as file:
            reader = csv.DictReader(file)
            headers, rows = reader.fieldnames, list(reader)
        for row in rows:
            if selections is not None:
                row['replicate'] = '1' if row['table_name'] in selections else '0'
            if overrides is not None:
                row['replicate_override'] = '1' if row['table_name'] in overrides else '0'
            if constants and row['table_name'] in constants:
                row['column_default_value_json'] = json.dumps(constants[row['table_name']])
        with path.open('w', newline='') as file:
            writer = csv.DictWriter(file, headers)
            writer.writeheader()
            writer.writerows(rows)

    def runner(self, selections=None, constants=None, overrides=None):
        self.export(selections, constants, overrides)
        exclusions = []
        plan, selected = read_plan(self.args.table_plan, exclusions)
        operations = plan_operations(plan['source'], plan['target'], selected, exclusions, plan['force_tables'])
        self.source.set_session(readonly=True)
        manifest = extract(self.source, self.stage / 'tables', operations, plan['source'], plan['target'])
        self.source.rollback()
        state = dict(format=FORMAT, plan_id=plan['plan_id'], identities=plan['identities'], operations={}, constraints=[], actions={}, attempt=0)
        state = initialize(self.con, plan, state)
        return CSVRunner(self.con, self.stage, plan, manifest, operations, state, exclusions)

    def test_export_is_read_only_lists_registered_tables_and_has_no_samples(self):
        plan, selected = self.export()
        self.assertEqual(set(selected), {'ab_record', 'ab_other'})
        self.assertNotIn('ignored', plan['tables'])
        self.assertNotIn('a_b_rel', plan['tables'])
        text = Path(self.args.table_plan).read_text()
        self.assertNotIn('private-password', text)
        self.assertNotIn('source_columns_first_value_json', text)
        self.assertNotIn('target_columns_first_value_json', text)
        self.assertIn('available_target_selections_json', text)
        self.assertEqual(Path(self.args.table_plan).stat().st_mode & 0o777, 0o600)
        self.assertIsNone(self.scalar("SELECT to_regnamespace('csv_replication')"))
        self.assertEqual(self.scalar('SELECT id FROM res_users'), 7)

    def test_target_only_selection_metadata_order_null_and_empty_records(self):
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_record ADD COLUMN position varchar,ADD COLUMN dynamic varchar,ADD COLUMN note text')
            for name, kind in [('position', 'selection'), ('dynamic', 'selection'), ('name', 'selection'),
                               ('nonstored', 'selection'), ('note', 'text')]:
                cr.execute('INSERT INTO ir_model_fields(model,name,ttype) VALUES(%s,%s,%s)', ['ab_record', name, kind])
            cr.execute("INSERT INTO ir_model_fields_selection(field_id,value,sequence) "
                       "SELECT id,'bottom',30 FROM ir_model_fields WHERE name='position'")
            cr.execute("INSERT INTO ir_model_fields_selection(field_id,value,sequence) "
                       "SELECT id,'sided',10 FROM ir_model_fields WHERE name='position'")
            cr.execute("INSERT INTO ir_model_fields_selection(field_id,value,sequence) "
                       "SELECT id,'bottom',20 FROM ir_model_fields WHERE name='position'")
            cr.execute('DELETE FROM a_b_rel')
            cr.execute('DELETE FROM ab_record')
        self.con.commit()
        self.export({'ab_record'}, {'ab_record': {'position': 'operator-defined'}})
        with Path(self.args.table_plan).open(newline='') as file:
            row = next(row for row in csv.DictReader(file) if row['table_name'] == 'ab_record')
        self.assertEqual(loads(row['available_target_selections_json']),
                         {'available_target_selections': {'dynamic': None, 'position': ['sided', 'bottom']}})
        self.assertEqual(row['existance'], 'both')
        # Displayed keys are not an added ORM selection validation rule.
        self.assertEqual(read_plan(self.args.table_plan)[1]['ab_record']['position'], 'operator-defined')

    def test_existance_for_registered_source_only_and_target_only_tables(self):
        for connection, name in ((self.source, 'ab_source_only'), (self.con, 'ab_target_only')):
            with connection.cursor() as cr:
                cr.execute(sql.SQL('CREATE TABLE {} (id integer PRIMARY KEY)').format(sql.Identifier(name)))
                cr.execute('INSERT INTO ir_model(model,transient) VALUES(%s,false)', [name])
            connection.commit()
        # Export retains one-sided rows; import ignores them despite custom=1.
        with contextlib.redirect_stdout(io.StringIO()):
            export_plan(self.args)
        with Path(self.args.table_plan).open(newline='') as file:
            rows = {row['table_name']: row for row in csv.DictReader(file)}
        self.assertEqual(rows['ab_source_only']['existance'], 'source_only')
        self.assertEqual(rows['ab_target_only']['existance'], 'target_only')
        self.assertEqual(rows['ab_record']['existance'], 'both')
        self.assertEqual(loads(rows['ab_source_only']['available_target_selections_json']), {'available_target_selections': {}})
        exclusions = []
        _, selected = read_plan(self.args.table_plan, exclusions)
        self.assertEqual(set(selected), {'ab_record', 'ab_other'})
        self.assertEqual({item['table'] for item in exclusions}, {'ab_source_only', 'ab_target_only'})

    def test_diagnostic_refresh_preserves_new_controls_and_identity_and_refuses_overwrite(self):
        self.export({'ab_record'}, {'ab_record': {'name': 'reviewed'}}, overrides={'ab_record'})
        old_path = Path(self.args.table_plan)
        meta = loads(Path(str(old_path) + '.metadata.json').read_text())
        with old_path.open(newline='') as file:
            rows = list(csv.DictReader(file))
        original = old_path.read_bytes()
        old_plan, old_controls = read_plan(old_path)
        output = self.stage / 'selections.csv'
        convert_plan(old_path, output, self.config, self.database)
        new_plan, new_controls = read_plan(output)
        self.assertEqual(new_controls, old_controls)
        self.assertEqual(new_plan['plan_id'], old_plan['plan_id'])
        self.assertEqual(new_plan['identities'], old_plan['identities'])
        self.assertEqual(new_plan['source'], old_plan['source'])
        self.assertEqual(new_plan['target'], old_plan['target'])
        self.assertEqual(new_plan['version'], VERSION)
        self.assertEqual(new_plan['force_tables'], ['ab_record'])
        with output.open(newline='') as file:
            reader = csv.DictReader(file)
            self.assertEqual(tuple(reader.fieldnames), HEADERS)
            converted = list(reader)
        self.assertEqual([r['table_name'] for r in converted], [r['table_name'] for r in rows])
        self.assertTrue(all(len(value) < 32767 for row in converted for value in row.values()))
        self.assertEqual(old_path.read_bytes(), original)
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        with self.assertRaisesRegex(MigrationError, 'exists'):
            convert_plan(old_path, output, self.config, self.database)
        with self.assertRaisesRegex(MigrationError, 'identity differs'):
            convert_plan(old_path, self.stage / 'wrong.csv', self.config, self.source_db)
        self.assertFalse((self.stage / 'wrong.csv').exists())

    def test_conversion_does_not_change_committed_resume_specifications(self):
        runner = self.runner({'ab_other'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        output = self.stage / 'selections.csv'
        convert_plan(self.args.table_plan, output, self.config, self.database)
        meta, selected = read_plan(output)
        self.assertEqual(meta['plan_id'], runner.plan['plan_id'])
        runner.plan = meta
        runner.operations = plan_operations(meta['source'], meta['target'], selected)
        result = runner.run(meta['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertTrue(all(item['status'] in ('verified_existing', 'm2m_replaced') for item in result['operations']))

    def test_incoming_cascade_and_set_null_removed_ignored_rows_survive(self):
        runner = self.runner({'res_users', 'ab_record', 'ab_other'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['status'], 'complete_with_warnings')
        self.assertEqual(len(result['failed_foreign_keys']), 2)
        self.assertEqual(self.scalar('SELECT id FROM res_users'), 13)
        self.assertEqual(self.scalar('SELECT create_uid FROM ignored'), 7)
        self.assertEqual(self.scalar('SELECT write_uid FROM ignored'), 7)
        self.assertEqual(self.scalar('SELECT record_id FROM a_b_rel'), 42)
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'text\tline\n\\N')
        self.assertIsNone(self.scalar("SELECT to_regnamespace('prepared_migration_source')"))
        self.assertEqual(self.scalar("SELECT nextval(pg_get_serial_sequence('ab_record','id'))"), 43)
        self.con.rollback()
        with patch.object(runner, 'unit', wraps=runner.unit):
            second = runner.run(runner.plan['target']['fks'])
        self.assertEqual(second['failed_tables'], [])
        self.assertTrue(all(item['status'] in ('verified_existing', 'm2m_replaced') for item in second['operations'][-4:]))

    def test_constants_and_no_automatic_defaults(self):
        with self.con.cursor() as cr:
            cr.execute("ALTER TABLE ab_record ADD COLUMN nullable text DEFAULT 'SQL default', ADD COLUMN required text NOT NULL DEFAULT 'SQL required'")
        self.con.commit()
        runner = self.runner({'ab_record'}, {'ab_record': {'name': '', 'required': 'reviewed'}})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), '')
        self.assertEqual(self.scalar('SELECT required FROM ab_record'), 'reviewed')
        self.assertIsNone(self.scalar('SELECT nullable FROM ab_record'))
        self.assertEqual(self.scalar('SELECT id FROM res_users'), 7)

    def test_required_failure_preserves_previous_rows_then_pending_default_can_change(self):
        with self.con.cursor() as cr:
            cr.execute("ALTER TABLE ab_record ADD COLUMN required text NOT NULL DEFAULT 'old'")
        self.con.commit()
        runner = self.runner({'ab_record'})
        first = runner.run(runner.plan['target']['fks'])
        self.assertEqual(first['status'], 'finished_with_errors')
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        runner.operations['ab_record']['constants'] = {'required': 'fixed'}
        second = runner.run(runner.plan['target']['fks'])
        self.assertEqual(second['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 42)

    def test_shared_relations_are_additive_when_other_owner_is_ignored(self):
        runner = self.runner({'ab_record'})
        # Additive import keeps valid extras; the old link becomes an orphan
        # when its endpoint is replaced and must be removed before FK restore.
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [], result)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 8)

    def test_sequence_restart_rolls_back_and_committed_changes_are_rejected(self):
        runner = self.runner({'ab_other'})
        runner.capture_constraints(runner.plan['target']['fks'])
        self.assertEqual(runner.drop_constraints(), set())
        with self.con.cursor() as cr:
            cr.execute("SELECT last_value,is_called FROM ab_other_id_seq")
            before = cr.fetchone()
        original = runner.persist
        with patch.object(runner, 'persist', side_effect=[ValueError('injected'), None]):
            runner.unit('ab_other', set())
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 8)
        with self.con.cursor() as cr:
            cr.execute('SELECT last_value,is_called FROM ab_other_id_seq')
            self.assertEqual(cr.fetchone(), before)
        runner.persist = original
        runner.run(runner.plan['target']['fks'])
        with self.con.cursor() as cr:
            cr.execute("UPDATE ab_other SET name='outside change'")
        self.con.commit()
        runner.validate_resume()
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT name FROM ab_other'), 'outside change')

    def test_corrupt_retained_file_is_rejected(self):
        runner = self.runner({'ab_other'})
        path = self.stage / 'tables' / runner.manifest['tables']['ab_other']['file']
        path.write_bytes(path.read_bytes() + b'bad')
        with self.assertRaises(MigrationError):
            verify_files(self.stage, runner.manifest)

    def test_type_failure_isolated_empty_table_and_explicit_json_false_zero(self):
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_other ALTER COLUMN name TYPE integer USING 1')
            cr.execute('ALTER TABLE ab_record ADD COLUMN data jsonb, ADD COLUMN flag boolean, ADD COLUMN amount integer')
        self.con.commit()
        runner = self.runner({'ab_record', 'ab_other'}, {'ab_record': {'data': {'x': 'quoted\nvalue'}, 'flag': False, 'amount': 0}})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual({item['table'] for item in result['failed_tables']}, {'ab_other', 'a_b_rel'})
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 8)
        self.assertEqual(self.scalar('SELECT data FROM ab_record'), {'x': 'quoted\nvalue'})
        self.assertFalse(self.scalar('SELECT flag FROM ab_record'))
        self.assertEqual(self.scalar('SELECT amount FROM ab_record'), 0)
        runner.operations['ab_other']['constants'] = {'name': 0}
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_empty_source_replaces_rows_and_restarts_sequence(self):
        with self.source.cursor() as cr:
            cr.execute('DELETE FROM a_b_rel')
            cr.execute('DELETE FROM ab_record')
        self.source.commit()
        with self.con.cursor() as cr:
            cr.execute("ALTER TABLE ab_record ADD COLUMN required text NOT NULL DEFAULT 'old'")
        self.con.commit()
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_record'), 0)
        self.assertEqual(self.scalar("SELECT nextval(pg_get_serial_sequence('ab_record','id'))"), 1)

    def test_composite_fk_export_and_restore(self):
        for connection in (self.con, self.source):
            with connection.cursor() as cr:
                cr.execute('CREATE TABLE pair(a integer,b integer,PRIMARY KEY(a,b))')
                cr.execute('INSERT INTO pair VALUES(1,2)')
                cr.execute('ALTER TABLE ab_record ADD COLUMN a integer,ADD COLUMN b integer')
                cr.execute('UPDATE ab_record SET a=1,b=2')
                cr.execute('ALTER TABLE ab_record ADD CONSTRAINT pair_fk FOREIGN KEY(a,b) REFERENCES pair(a,b)')
            connection.commit()
        runner = self.runner({'ab_record'})
        exported = [fk for fk in runner.plan['target']['fks'] if fk['name'] == 'pair_fk']
        self.assertEqual([(fk['source_column'], fk['referenced_column']) for fk in exported], [('a', 'a'), ('b', 'b')])
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertTrue(any(item['name'] == 'pair_fk' and item['restored'] for item in result['constraints']))

    def test_failure_to_drop_fk_blocks_affected_replacement(self):
        runner = self.runner({'res_users'})
        original = runner.constraint

        def fail(item):
            if item['source_table'] == 'ignored':
                raise MigrationError('Injected unavailable FK lock')
            return original(item)

        with patch.object(runner, 'constraint', fail):
            result = runner.run(runner.plan['target']['fks'])
        self.assertTrue(result['failed_tables'])
        self.assertEqual(self.scalar('SELECT id FROM res_users'), 7)
        self.assertEqual(self.scalar('SELECT create_uid FROM ignored'), 7)

    def test_interrupt_after_copy_commit_and_before_commit_resume(self):
        runner = self.runner({'ab_record', 'ab_other'})
        original = runner.unit

        def stop(table, blocked):
            original(table, blocked)
            raise KeyboardInterrupt()

        with patch.object(runner, 'unit', stop):
            with self.assertRaises(KeyboardInterrupt):
                runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 21)
        runner.state = read_state(self.con)
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 42)
        # Current constants determine the expected contents even after a commit.
        runner.operations['ab_record']['constants']['name'] = 'not allowed'
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'text\tline\n\\N')

    def test_precommit_interrupt_preserves_old_rows(self):
        runner = self.runner({'ab_other'})
        runner.capture_constraints(runner.plan['target']['fks'])
        blocked = runner.drop_constraints()
        with patch.object(runner, 'persist', side_effect=KeyboardInterrupt()):
            with self.assertRaises(KeyboardInterrupt):
                runner.unit('ab_other', blocked)
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 8)
        runner.restore_constraints()
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_optional_action_failure_retries_without_recopying_tables(self):
        runner = self.runner({'ir_attachment'})
        calls = []

        def action(args, completed, save):
            calls.append(1)
            if len(calls) == 1:
                raise MigrationError('Injected file failure')
            return dict(copied=1)

        with patch.dict('csv_replicator.ACTIONS', {'copy-filestore': action}):
            first = runner.run(runner.plan['target']['fks'], actions=['copy-filestore'])
            self.assertEqual(first['status'], 'finished_with_errors')
            with patch('csv_replicator.copy_table', side_effect=relation_copy_only):
                second = runner.run(runner.plan['target']['fks'], actions=['copy-filestore'])
        self.assertEqual(second['status'], 'complete')
        self.assertTrue(second['actions']['copy-filestore']['success'])

    def test_changed_schema_fails_before_backup_or_target_gating(self):
        self.export({'ab_other'})
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_other ADD COLUMN changed integer')
        self.con.commit()
        with patch('csv_replicator.ensure_backup', side_effect=AssertionError('backup')), \
                patch('availability.DatabaseGate.exclude', side_effect=AssertionError('downtime')):
            with self.assertRaisesRegex(MigrationError, 'Target schema differs'):
                run(self.args, self.stage / 'runs')

    def test_fk_added_during_backup_is_captured_after_gate(self):
        self.export({'res_users', 'ab_record', 'ab_other'})
        self.con.close()
        from common import ensure_backup

        def backup(*args, **kwargs):
            ensure_backup(*args, **kwargs)
            other = connect(self.config, self.database, readonly=False)
            try:
                with other.cursor() as cr:
                    cr.execute('ALTER TABLE ignored ADD CONSTRAINT late_fk FOREIGN KEY(create_uid) REFERENCES res_users(id) ON DELETE CASCADE')
                other.commit()
            finally:
                other.close()

        try:
            with patch('prepared.confirm', return_value=True), patch('csv_replicator.ensure_backup', backup), \
                    contextlib.redirect_stdout(io.StringIO()):
                result = run(self.args, self.stage / 'runs')
            self.assertEqual(result['failed_tables'], [])
            self.assertTrue(any(item['name'] == 'late_fk' for item in result['failed_foreign_keys']))
        finally:
            self.con = connect(self.config, self.database, readonly=False)
        self.assertEqual(self.scalar('SELECT count(*) FROM ignored'), 1)
        self.assertEqual(self.scalar('SELECT create_uid FROM ignored'), 7)

    def test_zero_selections_do_not_backup_or_gate(self):
        self.export(set())
        with patch('csv_replicator.ensure_backup', side_effect=AssertionError('backup')), \
                patch('availability.DatabaseGate.exclude', side_effect=AssertionError('downtime')):
            result = run(self.args, self.stage / 'runs')
        self.assertEqual(result['committed_tables'], 0)
        self.assertIsNone(self.scalar("SELECT to_regnamespace('csv_replication')"))

    def test_full_controller_backups_and_reopens_without_registry_or_identity_checks(self):
        self.export({'ab_record', 'ab_other'})
        self.source.close()
        self.source = connect(self.config, self.source_db, readonly=False)
        self.con.close()
        root = self.stage / 'runs'
        try:
            with patch('prepared.confirm', return_value=True), \
                    patch('prepared.metadata', side_effect=AssertionError('registry invoked')), \
                    patch('prepared.identity_checkpoint', side_effect=AssertionError('identity check invoked')), \
                    contextlib.redirect_stdout(io.StringIO()):
                first = run(self.args, root)
                second = run(self.args, root)
            self.assertEqual(first['failed_tables'], [])
            self.assertEqual(second['failed_tables'], [])
            self.assertTrue(all(item['status'] in ('verified_existing', 'm2m_replaced') for item in second['operations']))
            stage = next(root.iterdir())
            self.assertTrue((stage / 'before_import.dump').is_file())
            self.assertFalse((stage / 'id-validation.json').exists())
            with self.admin.cursor() as cr:
                cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s', [self.database])
                self.assertTrue(cr.fetchone()[0])
        finally:
            self.con = connect(self.config, self.database, readonly=False)
