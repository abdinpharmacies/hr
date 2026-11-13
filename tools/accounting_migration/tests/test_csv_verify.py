"""Cross-run adoption and count-only verification in disposable databases."""
import contextlib
import copy
import csv
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

import test_csv_postgres as fixtures
from common import connect, MigrationError, save_json, loads
from csv_copy import copy_table
from csv_replicator import initialize, read_state, save_state, run, recover_csv_target, FORMAT
from csv_relations import verified_path
from availability import DatabaseGate


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class CountPostgresTests(unittest.TestCase):
    base = fixtures.CSVPostgresTests
    setUpClass = classmethod(base.setUpClass.__func__)
    tearDownClass = classmethod(base.tearDownClass.__func__)
    setUp, tearDown = base.setUp, base.tearDown
    scalar, export, edit, runner = base.scalar, base.export, base.edit, base.runner

    def execute(self, con, query, params=None):
        if con is self.source:
            con.set_session(readonly=False)
        with con.cursor() as cr:
            cr.execute(query, params)
        con.commit()

    def first(self, selections=None, constants=None):
        runner = self.runner(selections or {'ab_record'}, constants)
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        return runner

    def controller(self, root):
        self.con.close()
        try:
            with patch('builtins.input', side_effect=AssertionError('unexpected confirmation')), contextlib.redirect_stdout(io.StringIO()):
                return run(self.args, root)
        finally:
            self.con = connect(self.config, self.database, readonly=False)

    def new_plan(self, selections=None, constants=None):
        self.args.table_plan = str(self.stage / 'new.csv')
        self.args.export_table_plan = self.args.table_plan
        return self.export(selections or {'ab_record'}, constants)

    def test_different_plan_archives_checkpoint_and_skips_matching_contents(self):
        first = self.first()
        old_id = first.plan['plan_id']
        self.new_plan()
        with patch('csv_replicator.copy_table', side_effect=AssertionError('matching table recopied')):
            result = self.controller(self.stage / 'runs')
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['operation_counts']['verified_existing'], 2)
        state = read_state(self.con)
        self.assertNotEqual(state['plan_id'], old_id)
        self.assertEqual(state['format'], FORMAT)
        self.assertEqual(self.scalar("SELECT count(*) FROM csv_replication.checkpoint WHERE name LIKE 'archive:%'"), 1)
        self.assertIn(old_id, self.scalar("SELECT value FROM csv_replication.checkpoint WHERE name LIKE 'archive:%'"))

    def test_equal_counts_skip_even_with_changed_values(self):
        runner = self.first()
        self.execute(self.con, "UPDATE ab_record SET name='changed'")
        with patch('csv_replicator.copy_table', side_effect=AssertionError('equal count recopied')):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'changed')
        self.assertEqual(runner.state['operations']['ab_record']['verification']['reason'], 'count_matches')

    def test_equal_counts_skip_even_with_different_ids(self):
        runner = self.first({'ab_other'})
        self.execute(self.con, 'DELETE FROM a_b_rel')
        self.execute(self.con, 'UPDATE ab_other SET id=999')
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 999)
        self.assertEqual(runner.state['operations']['ab_other']['status'], 'verified_existing')

    def test_changed_constant_does_not_force_recopy_when_counts_match(self):
        runner = self.first()
        runner.operations['ab_record']['constants']['name'] = 'new choice'
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'text\tline\n\\N')

    def test_new_run_different_defaults_still_uses_count_only(self):
        self.first()
        self.new_plan(constants={'ab_record': {'name': 'reviewed'}})
        result = self.controller(self.stage / 'runs')
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'text\tline\n\\N')
        self.assertEqual(result['operation_counts']['copied'], 0)

    def test_adoption_does_not_drop_constraints_or_rewind_sequence(self):
        runner = self.first()
        self.execute(self.con, 'ALTER SEQUENCE ab_record_id_seq RESTART WITH 1000')
        with patch('csv_replicator.copy_table', side_effect=AssertionError('recopy')):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(runner.write_tables, set())
        self.assertEqual(self.scalar('SELECT nextval(\'ab_record_id_seq\')'), 1000)

    def test_adoption_advances_stale_sequence(self):
        runner = self.first()
        self.execute(self.con, 'ALTER SEQUENCE ab_record_id_seq RESTART WITH 1')
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(runner.state['operations']['ab_record']['status'], 'verified_existing')
        self.assertEqual(self.scalar("SELECT nextval('ab_record_id_seq')"), 43)

    def test_additive_relation_checks_subset_and_only_inserts_missing_links(self):
        runner = self.first()
        self.execute(self.con, 'DELETE FROM a_b_rel')
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['operation_counts']['verified_existing'], 1)
        self.assertEqual(result['operation_counts']['additive_completed'], 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)

    def test_target_numeric_type_input_normalizes_expected_values(self):
        self.execute(self.source, 'ALTER TABLE ab_record ADD COLUMN amount integer')
        self.execute(self.source, 'UPDATE ab_record SET amount=5')
        self.execute(self.con, 'ALTER TABLE ab_record ADD COLUMN amount numeric(10,2)')
        runner = self.first()
        with patch('csv_replicator.copy_table', side_effect=AssertionError('normalization mismatch')):
            self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_varchar_typmod_error_does_not_truncate_or_delete_target(self):
        self.execute(self.con, 'ALTER TABLE ab_record ALTER COLUMN name TYPE varchar(20)')
        self.execute(self.source, "UPDATE ab_record SET name=repeat('x',21)")
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertTrue(result['failed_tables'])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        self.assertIn('ab_record', runner.write_tables)

    def test_generated_fields_are_excluded_from_expected_inputs(self):
        self.execute(self.con, 'ALTER TABLE ab_record ADD COLUMN doubled integer GENERATED ALWAYS AS (id*2) STORED')
        runner = self.first()
        self.assertEqual(self.scalar('SELECT doubled FROM ab_record'), 84)
        with patch('csv_replicator.copy_table', side_effect=AssertionError('generated column mismatch')):
            self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_binary_json_arrays_and_escaped_record_values_roundtrip(self):
        for con in (self.source, self.con):
            self.execute(con, 'ALTER TABLE ab_record ADD COLUMN payload bytea, ADD COLUMN document jsonb, '
                              'ADD COLUMN labels text[], ADD COLUMN moment timestamptz')
        self.execute(self.source, "UPDATE ab_record SET payload=decode('00ff095c','hex'), "
                                 "document=%s::jsonb,labels=%s,moment='2026-11-12 12:00:00+02'",
                     ['{"x":"quote\\\"\\\\newline\\n","y":null}', ['"', '\\', 'line\ntext', '']])
        runner = self.first()
        with patch('csv_replicator.copy_table', side_effect=AssertionError('escaped type mismatch')):
            self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertNotIn('artifact', runner.state['operations']['ab_record']['verification'])
        self.assertFalse((self.stage / 'verification').exists())

    def test_equal_counts_do_not_scan_source_for_duplicate_ids(self):
        self.execute(self.source, 'ALTER TABLE a_b_rel DROP CONSTRAINT a_b_rel_record_id_fkey')
        self.execute(self.source, 'ALTER TABLE ab_record DROP CONSTRAINT ab_record_pkey')
        self.execute(self.source, 'INSERT INTO ab_record SELECT * FROM ab_record')
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        self.assertEqual(runner.state['operations']['ab_record']['status'], 'verified_existing')

    def test_postcopy_verification_only_checks_row_count(self):
        self.execute(self.con, "CREATE FUNCTION change_import() RETURNS trigger LANGUAGE plpgsql AS $$ "
                               "BEGIN NEW.name := 'changed by trigger'; RETURN NEW; END $$")
        self.execute(self.con, 'CREATE TRIGGER mutate_copy BEFORE INSERT ON ab_record FOR EACH ROW EXECUTE FUNCTION change_import()')
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 42)
        self.assertEqual(self.scalar('SELECT name FROM ab_record'), 'changed by trigger')

    def test_empty_expected_and_target_are_adopted(self):
        for con in (self.source, self.con):
            self.execute(con, 'DELETE FROM a_b_rel')
            self.execute(con, 'DELETE FROM ab_other')
        runner = self.runner({'ab_other'})
        with patch('csv_replicator.copy_table', side_effect=AssertionError('empty table recopied')):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertTrue(all(item['status'] == 'verified_existing' for item in result['operations']))

    def test_historical_missing_fk_definitions_survive_run_transfer(self):
        runner = self.first({'res_users', 'ab_record', 'ab_other'})
        self.assertTrue(any(not fk.get('restored') for fk in runner.state['constraints']))
        self.new_plan({'ab_other'})
        result = self.controller(self.stage / 'runs')
        self.assertEqual(len(result['failed_foreign_keys']), 2)
        self.assertEqual(self.scalar('SELECT create_uid FROM ignored'), 7)

    def test_malformed_history_rejects_ownership_transfer(self):
        runner = self.first()
        bad = copy.deepcopy(runner.state)
        bad['constraints'] = [{'removed': True}]
        save_state(self.con, bad)
        self.con.commit()
        self.new_plan()
        with self.assertRaisesRegex(MigrationError, 'recovery metadata'):
            self.controller(self.stage / 'runs')

    def test_interrupt_adoption_keeps_existing_data_and_retries(self):
        runner = self.first()
        original = runner.persist

        def interrupt():
            if runner.state['operations'].get('ab_record', {}).get('status') == 'verified_existing':
                raise KeyboardInterrupt()
            original()

        with patch.object(runner, 'persist', interrupt), self.assertRaises(KeyboardInterrupt):
            runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 42)
        with patch('csv_replicator.copy_table', side_effect=AssertionError('recopy after adoption interruption')):
            self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_legacy_format_and_extraction_get_new_generation_and_archive(self):
        runner = self.first()
        old = copy.deepcopy(runner.state)
        old['format'] = 3
        old.pop('stage', None)
        save_state(self.con, old)
        self.con.commit()
        root = self.stage / 'runs'
        base = root / ('csv_' + runner.plan['plan_id'])
        base.mkdir(parents=True)
        legacy = dict(runner.manifest)
        legacy.pop('mapping_policy')
        save_json(base / 'csv-extraction.json', legacy)
        original = (base / 'csv-extraction.json').read_bytes()
        with patch('csv_replicator.copy_table', side_effect=AssertionError('legacy matching table recopied')):
            result = self.controller(root)
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual((base / 'csv-extraction.json').read_bytes(), original)
        self.assertTrue(list(base.glob('generation_*/csv-extraction.json')))
        self.assertTrue(read_state(self.con).get('previous_checkpoint'))
        with patch('csv_replicator.copy_table', side_effect=AssertionError('legacy repeat recopied')):
            self.assertEqual(self.controller(root)['failed_tables'], [])

    def test_interrupted_archive_transaction_preserves_previous_owner(self):
        runner = self.first()
        plan, _ = self.new_plan()
        state = dict(format=FORMAT, plan_id=plan['plan_id'], identities=plan['identities'],
                     operations={}, constraints=[], actions={}, attempt=0)
        with patch('csv_replicator.save_state', side_effect=KeyboardInterrupt()), self.assertRaises(KeyboardInterrupt):
            initialize(self.con, plan, state)
        self.con.rollback()
        self.assertEqual(read_state(self.con)['plan_id'], runner.plan['plan_id'])
        self.assertEqual(self.scalar("SELECT count(*) FROM csv_replication.checkpoint WHERE name LIKE 'archive:%'"), 0)

    def test_equal_count_skips_relationship_revalidation(self):
        runner = self.first()
        self.execute(self.con, 'ALTER TABLE ab_record DROP CONSTRAINT ab_record_create_uid_fkey')
        self.execute(self.con, 'DELETE FROM ignored')
        self.execute(self.con, 'DELETE FROM res_users')
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(runner.state['operations']['ab_record']['status'], 'verified_existing')

    def test_incomplete_extraction_is_preserved_in_new_generation(self):
        plan, _ = self.export({'ab_other'})
        root = self.stage / 'runs'
        base = root / ('csv_' + plan['plan_id'])
        base.mkdir(parents=True)
        save_json(base / 'csv-extraction.json', dict(complete=False, tables={}))
        original = (base / 'csv-extraction.json').read_bytes()
        result = self.controller(root)
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual((base / 'csv-extraction.json').read_bytes(), original)
        self.assertTrue(list(base.glob('generation_*/csv-extraction.json')))

    def test_legacy_content_artifacts_are_not_required_for_count_resume(self):
        runner = self.first()
        runner.state['operations']['ab_record']['verification'] = dict(
            policy='csv_content_v1', artifact=dict(file='missing-old.sqlite', sha256='invalid'))
        with patch('csv_replicator.copy_table', side_effect=AssertionError('equal count recopied')):
            self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(runner.state['operations']['ab_record']['verification']['policy'], 'csv_count_v1')

    def test_recovery_finds_previous_csv_generation_for_same_database(self):
        root = self.stage / 'runs'
        previous = root / ('csv_' + 'a' * 32) / 'generation_test'
        current = root / ('csv_' + 'b' * 32)
        previous.mkdir(parents=True)
        current.mkdir()
        gate = DatabaseGate(self.config, self.database)
        try:
            save_json(previous / 'availability.json', dict(database=self.database, oid=gate.oid, offline=True, sessions=[]))
            gate.set_online(False)
            recover_csv_target(gate, current, root)
            self.assertTrue(gate.online())
            self.assertFalse(loads((previous / 'availability.json').read_text())['offline'])
        finally:
            gate.set_online(True)
            gate.close()

    def test_unidentified_offline_target_is_not_taken_over(self):
        gate = DatabaseGate(self.config, self.database)
        try:
            gate.set_online(False)
            with self.assertRaisesRegex(MigrationError, 'recovery marker'):
                recover_csv_target(gate, self.stage, self.stage)
            self.assertFalse(gate.online())
        finally:
            gate.set_online(True)
            gate.close()

    def test_wrong_target_identity_still_rejects_before_copy(self):
        self.export({'ab_record'})
        self.args.target_db = self.source_db
        with self.assertRaisesRegex(MigrationError, 'target database identity'):
            self.controller(self.stage / 'runs')
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)

    def test_reported_source_only_relation_is_skipped_on_fresh_and_retained_runs(self):
        relation = 'ab_hr_job_ab_visit_report_report_rel'
        for con, rid in ((self.source, 3), (self.con, 9)):
            self.execute(con, 'CREATE TABLE ab_hr_job(id integer PRIMARY KEY)')
            self.execute(con, "INSERT INTO ir_model(model,transient) VALUES('ab_hr_job',false)")
            self.execute(con, 'INSERT INTO ab_hr_job VALUES(%s)', [rid])
        self.execute(self.source, 'CREATE TABLE ab_visit_report_report(id integer PRIMARY KEY)')
        self.execute(self.source, "INSERT INTO ir_model(model,transient) VALUES('ab_visit_report_report',false)")
        self.execute(self.source, 'CREATE TABLE ' + relation + '(ab_hr_job_id integer REFERENCES ab_hr_job(id),'
                                 'ab_visit_report_report_id integer REFERENCES ab_visit_report_report(id))')
        self.execute(self.source, "INSERT INTO ir_model_fields(model,name,ttype,relation_table,column1,column2,relation) "
                     "VALUES('ab_visit_report_report','missing_job_ids','many2many',%s,'ab_visit_report_report_id','ab_hr_job_id','ab_hr_job')", [relation])
        self.export({'ab_hr_job'})
        path = Path(self.args.table_plan)
        with path.open(newline='') as file:
            reader = csv.DictReader(file)
            headers, rows = reader.fieldnames, [row for row in reader if row['existance'] == 'both']
        with path.open('w', newline='') as file:
            writer = csv.DictWriter(file, headers)
            writer.writeheader()
            writer.writerows(rows)
        root = self.stage / 'runs'
        first = self.controller(root)
        self.assertEqual(first['status'], 'complete_with_warnings')
        self.assertEqual(first['failed_tables'], [])
        self.assertEqual(first['committed_tables'], 1)
        self.assertEqual(self.scalar('SELECT id FROM ab_hr_job'), 9)
        self.assertEqual(first['excluded_tables'][0]['table'], relation)
        with patch('csv_replicator.copy_table', side_effect=AssertionError('matching table recopied')):
            second = self.controller(root)
        self.assertEqual(second['excluded_tables'], first['excluded_tables'])
        self.assertEqual(second['operation_counts']['verified_existing'], 1)
        stage = Path(read_state(self.con)['stage'])
        self.assertIn(relation, (stage / 'excluded_tables.json').read_text())
        self.assertIn('missing target table', (stage / 'migration_report.md').read_text())

    def test_all_one_sided_selection_reports_warnings_without_backup_or_downtime(self):
        for con, table in ((self.source, 'ab_source_only'), (self.con, 'ab_target_only')):
            self.execute(con, 'CREATE TABLE ' + table + '(id integer PRIMARY KEY)')
            self.execute(con, 'INSERT INTO ir_model(model,transient) VALUES(%s,false)', [table])
        self.export({'ab_source_only', 'ab_target_only'})
        with patch('csv_replicator.ensure_backup', side_effect=AssertionError('backup')), \
                patch('availability.DatabaseGate.exclude', side_effect=AssertionError('downtime')):
            result = self.controller(self.stage / 'runs')
        self.assertEqual(result['status'], 'complete_with_warnings')
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['committed_tables'], 0)
        self.assertEqual(len(result['excluded_tables']), 2)
        self.assertIsNone(self.scalar("SELECT to_regnamespace('csv_replication')"))

    def test_relation_with_missing_endpoint_is_excluded_and_existing_links_preserved(self):
        self.execute(self.con, 'DROP TABLE ab_other CASCADE')
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['committed_tables'], 1)
        self.assertEqual(result['excluded_tables'][0]['reason'], 'endpoint_table_not_both')
        self.assertEqual(self.scalar('SELECT record_id FROM a_b_rel'), 9)

    def test_genuine_common_relation_column_mismatch_remains_an_error(self):
        self.execute(self.con, 'ALTER TABLE a_b_rel RENAME COLUMN other_id TO different_id')
        with self.assertRaisesRegex(MigrationError, 'binding differs'):
            self.runner({'ab_record'})

    def test_historical_operations_outside_current_selection_are_not_counted(self):
        runner = self.first()
        runner.state['operations']['historical_table'] = dict(success=True, rows=100)
        runner.persist()
        self.con.commit()
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['committed_tables'], 2)
        self.assertEqual(len(result['operations']), 2)
