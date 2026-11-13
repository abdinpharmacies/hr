"""Version-3 forced copy controls tested only in disposable databases."""
import csv
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_csv_postgres as fixtures
import test_csv_verify as counts
from common import MigrationError
from csv_plan import read_plan, HEADERS, VERSION
from csv_relations import plan_operations
from csv_copy import copy_table
from csv_replicator import read_state


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class OverridePostgresTests(unittest.TestCase):
    base = fixtures.CSVPostgresTests
    setUpClass = classmethod(base.setUpClass.__func__)
    tearDownClass = classmethod(base.tearDownClass.__func__)
    setUp, tearDown = base.setUp, base.tearDown
    scalar, export, edit, runner = base.scalar, base.export, base.edit, base.runner
    execute, first, controller = counts.CountPostgresTests.execute, counts.CountPostgresTests.first, counts.CountPostgresTests.controller

    def controls(self, runner, selections=None, overrides=None):
        self.edit(selections=selections, overrides=overrides)
        meta, selected = read_plan(self.args.table_plan)
        runner.operations = plan_operations(meta['source'], meta['target'], selected, force_tables=meta['force_tables'])

    def test_new_exports_have_only_new_flags_and_safe_defaults(self):
        plan, _ = self.export()
        with Path(self.args.table_plan).open(newline='') as file:
            reader = csv.DictReader(file)
            self.assertEqual(tuple(reader.fieldnames), HEADERS)
            self.assertNotIn('replicate_source_id', reader.fieldnames)
            for row in reader:
                self.assertEqual(row['replicate_override'], '0')
                self.assertEqual(row['replicate'], '1' if row['model_type'] == 'custom' else '0')
        self.assertEqual(plan['version'], VERSION)

    def test_override_alone_forces_equal_count_copy_and_new_run_archival(self):
        self.first({'ab_other'})
        self.execute(self.con, "UPDATE ab_other SET name='target differs'")
        self.args.table_plan = str(self.stage / 'forced.csv')
        self.args.export_table_plan = self.args.table_plan
        self.export(set(), overrides={'ab_other'})
        result = self.controller(self.stage / 'runs')
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['operation_counts']['forced_copy'], 1)
        self.assertEqual(self.scalar('SELECT name FROM ab_other'), 'other')
        state = read_state(self.con)
        self.assertEqual(state['operations']['ab_other']['status'], 'forced_copy')
        self.assertEqual(state['operations']['ab_other']['copy_reason'], 'replicate_override')
        self.assertTrue(state['previous_checkpoint'])

    def test_override_repeats_on_resume_until_cleared_and_replays_m2m(self):
        self.export({'ab_record'}, overrides={'ab_record'})
        root = self.stage / 'runs'
        self.assertEqual(self.controller(root)['operation_counts']['forced_copy'], 1)
        stage = Path(read_state(self.con)['stage'])
        snapshot = (stage / 'csv-extraction.json').read_bytes()
        with patch('csv_replicator.copy_table', wraps=copy_table) as copier:
            result = self.controller(root)
        self.assertEqual(result['operation_counts']['forced_copy'], 1)
        self.assertEqual([call.args[2] for call in copier.call_args_list], ['ab_record', 'a_b_rel'])
        self.assertEqual((stage / 'csv-extraction.json').read_bytes(), snapshot)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
        self.edit(overrides=set())
        with patch('csv_replicator.copy_table', side_effect=fixtures.relation_copy_only):
            result = self.controller(root)
        self.assertEqual(result['operation_counts']['forced_copy'], 0)
        self.assertEqual(result['operation_counts']['verified_existing'], 1)

    def test_force_copy_failure_rolls_back_rows_sequence_and_checkpoint(self):
        runner = self.first()
        self.execute(self.con, "UPDATE ab_record SET name='keep on rollback'")
        self.execute(self.con, 'ALTER SEQUENCE ab_record_id_seq RESTART WITH 200')
        self.controls(runner, overrides={'ab_record'})
        original = runner.persist

        def fail():
            if runner.state['operations'].get('ab_record', {}).get('status') == 'forced_copy':
                raise MigrationError('Injected forced-copy checkpoint failure')
            original()

        with patch.object(runner, 'persist', fail):
            result = runner.run(runner.plan['target']['fks'])
        self.assertTrue(result['failed_tables'])
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'keep on rollback')
        self.assertEqual(self.scalar("SELECT nextval('ab_record_id_seq')"), 200)
        self.con.rollback()
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['operation_counts']['forced_copy'], 1)
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'text\tline\n\\N')
        self.assertEqual(self.scalar("SELECT nextval('ab_record_id_seq')"), 43)

    def test_equal_count_missing_partner_is_repaired_by_forced_copy(self):
        for con, uid in ((self.source, 13), (self.con, 7)):
            self.execute(con, 'CREATE TABLE res_partner(id integer PRIMARY KEY,name text)')
            self.execute(con, "INSERT INTO res_partner VALUES(2,'existing'),(6,'required partner')")
            self.execute(con, "INSERT INTO ir_model(model,transient) VALUES('res.partner',false)")
            self.execute(con, 'ALTER TABLE res_users ADD COLUMN partner_id integer REFERENCES res_partner(id) ON DELETE RESTRICT')
            self.execute(con, 'UPDATE res_users SET partner_id=2')
            self.execute(con, 'UPDATE res_users SET partner_id=6 WHERE id=%s', [uid])
        runner = self.runner({'res_partner'})
        runner.capture_constraints(runner.plan['target']['fks'])
        runner.drop_constraints()
        self.execute(self.con, 'DELETE FROM res_partner WHERE id=6')
        self.execute(self.con, "INSERT INTO res_partner VALUES(99,'extra target')")
        first = runner.run(runner.plan['target']['fks'])
        self.assertEqual(first['operation_counts']['verified_existing'], 1)
        self.assertEqual(len(first['failed_foreign_keys']), 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_partner WHERE id=6'), 0)
        self.controls(runner, selections=set(), overrides={'res_partner'})
        second = runner.run(runner.plan['target']['fks'])
        self.assertEqual(second['failed_tables'], [])
        self.assertEqual(second['failed_foreign_keys'], [])
        self.assertEqual(second['operation_counts']['forced_copy'], 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_partner WHERE id=6'), 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_partner WHERE id=99'), 0)
        self.assertEqual(self.scalar('SELECT partner_id FROM res_users WHERE id=7'), 6)

    def test_override_does_not_select_one_sided_table(self):
        self.execute(self.source, 'CREATE TABLE ab_source_only(id integer PRIMARY KEY)')
        self.execute(self.source, "INSERT INTO ir_model(model,transient) VALUES('ab_source_only',false)")
        self.export(set(), overrides={'ab_source_only'})
        with patch('csv_replicator.ensure_backup', side_effect=AssertionError('one-sided forced backup')):
            result = self.controller(self.stage / 'runs')
        self.assertEqual(result['committed_tables'], 0)
        self.assertEqual(result['excluded_tables'][0]['table'], 'ab_source_only')
