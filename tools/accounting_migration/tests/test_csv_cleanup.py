"""Generic orphan cleanup, exclusively in generated disposable databases."""
import json
import contextlib
import os
import unittest
from unittest.mock import patch

import test_csv_postgres as fixtures
import test_csv_verify as count_fixtures
from common import MigrationError
from csv_replicator import read_state


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class M2MCleanupPostgresTests(unittest.TestCase):
    base = fixtures.CSVPostgresTests
    setUpClass = classmethod(base.setUpClass.__func__)
    tearDownClass = classmethod(base.tearDownClass.__func__)
    setUp, tearDown = base.setUp, base.tearDown
    scalar, export, edit, runner = base.scalar, base.export, base.edit, base.runner
    execute, first = count_fixtures.CountPostgresTests.execute, count_fixtures.CountPostgresTests.first

    def audit(self, runner, table):
        entry = runner.state['m2m_cleanup'][table]
        path = self.stage / entry['deleted_ids_file']
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        return [json.loads(line) for line in path.read_text().splitlines()]

    def drop_link_fks(self):
        self.execute(self.con, 'ALTER TABLE a_b_rel DROP CONSTRAINT a_b_rel_record_id_fkey')
        self.execute(self.con, 'ALTER TABLE a_b_rel DROP CONSTRAINT a_b_rel_other_id_fkey')

    @contextlib.contextmanager
    def after_relation(self, runner, callback, table='a_b_rel'):
        """Exercise defensive cleanup of defects introduced after replacement."""
        original = runner.unit

        def unit(name, blocked):
            original(name, blocked)
            if name == table and runner.state['operations'].get(name, {}).get('success'):
                callback()

        with patch.object(runner, 'unit', unit):
            yield

    def test_endpoint_replacement_removes_old_link_and_preserves_valid_records(self):
        runner = self.runner({'ab_record'})
        with self.after_relation(runner, lambda: self.execute(self.con, 'INSERT INTO a_b_rel VALUES(9,8)')):
            runner.run(runner.plan['target']['fks'])
        result = runner.state['m2m_cleanup']['a_b_rel']
        self.assertEqual(result['deleted_links'], 1)
        self.assertEqual(self.audit(runner, 'a_b_rel'), [dict(record_id=9, other_id=8)])
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
        self.assertEqual(self.scalar('SELECT record_id FROM a_b_rel'), 42)
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_other'), 2)
        self.assertTrue(all(fk.get('restored') for fk in runner.state['constraints']))

    def test_count_skipped_endpoints_repair_either_missing_endpoint_and_keep_extras(self):
        runner = self.first()
        with patch('csv_replicator.copy_table', side_effect=fixtures.relation_copy_only), self.after_relation(
                runner, lambda: self.execute(self.con, 'INSERT INTO a_b_rel VALUES(999,8),(42,999),(999,999),(42,-99)')):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['failed_foreign_keys'], [])
        self.assertEqual(result['deleted_m2m_links'], 3)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 2)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE other_id=-99'), 1)
        self.assertEqual(len(self.audit(runner, 'a_b_rel')), 3)
        self.assertEqual(runner.state['operations']['a_b_rel']['target_count'], 2)
        self.assertEqual(result['operations'][-1]['target_count'], 2)
        again = runner.run(runner.plan['target']['fks'])
        self.assertEqual(again['deleted_m2m_links'], 0)
        self.assertEqual(again['m2m_cleanup']['a_b_rel']['status'], 'no_orphans')
        self.assertEqual(len(again['m2m_cleanup_history']), 1)
        self.assertTrue(all((self.stage / item['deleted_ids_file']).exists() for item in again['m2m_cleanup_history']))

    def test_company_users_example_is_repaired_without_copying_company(self):
        for con, uid in ((self.source, 13), (self.con, 7)):
            self.execute(con, 'CREATE TABLE res_company(id integer PRIMARY KEY)')
            self.execute(con, 'INSERT INTO res_company VALUES(1)')
            self.execute(con, "INSERT INTO ir_model(model,transient) VALUES('res.company',false)")
            self.execute(con, 'CREATE TABLE res_company_users_rel(user_id integer REFERENCES res_users(id), '
                              'cid integer REFERENCES res_company(id),PRIMARY KEY(user_id,cid))')
            self.execute(con, 'INSERT INTO res_company_users_rel VALUES(%s,1)', [uid])
            self.execute(con, "INSERT INTO ir_model_fields(model,name,ttype,relation_table,column1,column2,relation) "
                         "VALUES('res.users','company_ids','many2many','res_company_users_rel','user_id','cid','res.company')")
            self.execute(con, "INSERT INTO ir_model_data(module,name,model,res_id) VALUES('base','main_company','res.company',1)")
        runner = self.first({'res_users'})
        with patch('csv_replicator.copy_table', side_effect=fixtures.relation_copy_only), self.after_relation(
                runner, lambda: self.execute(self.con, 'INSERT INTO res_company_users_rel VALUES(2951,1),(9426,1)'),
                table='res_company_users_rel'):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['deleted_m2m_links'], 2)
        self.assertEqual(result['failed_m2m_cleanup'], [])
        self.assertEqual(self.scalar('SELECT user_id FROM res_company_users_rel'), 13)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_company'), 1)
        self.assertEqual({row['user_id'] for row in self.audit(runner, 'res_company_users_rel')}, {2951, 9426})
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_constraint WHERE conname='res_company_users_rel_user_id_fkey'"), 1)

    def test_unrelated_m2m_and_ordinary_m2o_rows_are_untouched(self):
        for con in (self.source, self.con):
            self.execute(con, 'CREATE TABLE other_users_rel(other_id integer,user_id integer)')
            self.execute(con, "INSERT INTO ir_model_fields(model,name,ttype,relation_table,column1,column2,relation) "
                         "VALUES('ab_other','users','many2many','other_users_rel','other_id','user_id','res.users')")
        self.execute(self.con, 'INSERT INTO other_users_rel VALUES(999,999)')
        runner = self.first()
        self.assertNotIn('other_users_rel', runner.state['m2m_cleanup'])
        self.assertEqual(self.scalar('SELECT count(*) FROM other_users_rel'), 1)
        self.assertEqual(self.scalar('SELECT create_uid FROM ignored'), 7)

    def test_failed_selected_endpoint_blocks_cleanup(self):
        self.drop_link_fks()
        self.execute(self.con, 'INSERT INTO a_b_rel VALUES(999,8)')
        self.execute(self.con, "DELETE FROM ir_model_data WHERE name='user'")
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertTrue(any(item['table'] == 'ab_record' for item in result['failed_tables']))
        self.assertEqual(result['m2m_cleanup']['a_b_rel']['status'], 'skipped')
        self.assertEqual(result['deleted_m2m_links'], 0)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=999'), 1)

    def test_cleanup_checkpoint_failure_rolls_back_and_can_retry_without_copy(self):
        runner = self.runner({'ab_record'})
        original = runner.persist

        def fail():
            entry = runner.state.get('m2m_cleanup', {}).get('a_b_rel', {})
            if entry.get('success') and entry.get('deleted_links'):
                raise MigrationError('Injected cleanup checkpoint failure')
            original()

        with patch.object(runner, 'persist', fail), self.after_relation(
                runner, lambda: self.execute(self.con, 'INSERT INTO a_b_rel VALUES(9,8)')):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['status'], 'finished_with_errors')
        self.assertEqual(result['deleted_m2m_links'], 0)
        self.assertEqual(len(result['failed_m2m_cleanup']), 1)
        self.assertEqual(result['m2m_cleanup_history'], [])
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=9'), 1)
        self.assertEqual(list((self.stage / 'm2m_cleanup').glob('*.jsonl')), [])
        with patch('csv_replicator.copy_table', side_effect=fixtures.relation_copy_only):
            second = runner.run(runner.plan['target']['fks'])
        self.assertEqual(second['failed_m2m_cleanup'], [])
        self.assertEqual(second['deleted_m2m_links'], 0)
        self.assertEqual(second['failed_foreign_keys'], [])

    def test_cleanup_interruption_rolls_back_ids_and_rows(self):
        runner = self.runner({'ab_record'})
        original = runner.persist

        def interrupt():
            if runner.state.get('m2m_cleanup', {}).get('a_b_rel', {}).get('deleted_links'):
                raise KeyboardInterrupt()
            original()

        with patch.object(runner, 'persist', interrupt), self.after_relation(
                runner, lambda: self.execute(self.con, 'INSERT INTO a_b_rel VALUES(9,8)')), self.assertRaises(KeyboardInterrupt):
            runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=9'), 1)
        self.assertFalse(read_state(self.con).get('m2m_cleanup'))
        self.assertEqual(list((self.stage / 'm2m_cleanup').glob('*.jsonl')), [])
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_m2m_cleanup'], [])

    def test_more_than_one_delete_batch_is_streamed_and_reported(self):
        runner = self.first()
        with self.after_relation(runner, lambda: self.execute(
                self.con, 'INSERT INTO a_b_rel SELECT 5000+g,8 FROM generate_series(1,1201) g')):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['deleted_m2m_links'], 1201)
        self.assertEqual(len(self.audit(runner, 'a_b_rel')), 1201)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)

    def test_partition_row_identity_does_not_delete_valid_link_in_another_partition(self):
        self.execute(self.con, 'DROP TABLE a_b_rel')
        self.execute(self.con, 'CREATE TABLE a_b_rel(record_id integer,other_id integer) PARTITION BY RANGE(other_id)')
        self.execute(self.con, 'CREATE TABLE a_b_rel_low PARTITION OF a_b_rel FOR VALUES FROM (MINVALUE) TO (10)')
        self.execute(self.con, 'CREATE TABLE a_b_rel_high PARTITION OF a_b_rel FOR VALUES FROM (10) TO (MAXVALUE)')
        self.execute(self.con, 'INSERT INTO a_b_rel VALUES(42,8),(999,999)')
        runner = self.runner({'ab_record'})
        with self.after_relation(runner, lambda: self.execute(self.con, 'INSERT INTO a_b_rel VALUES(999,999)')):
            runner.run(runner.plan['target']['fks'])
        self.assertEqual(runner.state['m2m_cleanup']['a_b_rel']['deleted_links'], 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
        self.assertEqual(self.scalar('SELECT record_id FROM a_b_rel'), 42)

    def test_cleanup_cannot_cascade_into_business_records(self):
        runner = self.first()

        def create_child():
            self.execute(self.con, 'INSERT INTO a_b_rel VALUES(999,8)')
            self.execute(self.con, 'CREATE TABLE business_child(id integer PRIMARY KEY,record_id integer,other_id integer,'
                                  'FOREIGN KEY(record_id,other_id) REFERENCES a_b_rel(record_id,other_id) ON DELETE CASCADE)')
            self.execute(self.con, 'INSERT INTO business_child VALUES(1,999,8)')

        with self.after_relation(runner, create_child):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['deleted_m2m_links'], 0)
        self.assertEqual(len(result['failed_m2m_cleanup']), 1)
        self.assertIn('cascading FK', result['failed_m2m_cleanup'][0]['reason'])
        self.assertEqual(self.scalar('SELECT count(*) FROM business_child'), 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=999'), 1)
