"""Authoritative mapped M2M replacement in generated disposable databases."""
import os
import unittest
from unittest.mock import patch

import test_csv_postgres as fixtures
import test_csv_verify as counts
from csv_copy import copy_table
from csv_relations import M2M_POLICY, POLICY


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class M2MReplacePostgresTests(unittest.TestCase):
    base = fixtures.CSVPostgresTests
    setUpClass = classmethod(base.setUpClass.__func__)
    tearDownClass = classmethod(base.tearDownClass.__func__)
    setUp, tearDown = base.setUp, base.tearDown
    scalar, export, edit, runner = base.scalar, base.export, base.edit, base.runner
    execute, first = counts.CountPostgresTests.execute, counts.CountPostgresTests.first

    def test_equal_count_stale_roles_are_replaced_for_all_migrated_users(self):
        for con, ids, field in ((self.source, [1, 2, 3], 'groups_id'), (self.con, [10, 20, 30], 'group_ids')):
            self.execute(con, 'CREATE TABLE res_groups(id integer PRIMARY KEY)')
            self.execute(con, "INSERT INTO ir_model(model,transient) VALUES('res.groups',false)")
            for rid, name in zip(ids, ('group_user', 'group_portal', 'group_public')):
                self.execute(con, 'INSERT INTO res_groups VALUES(%s)', [rid])
                self.execute(con, "INSERT INTO ir_model_data(module,name,model,res_id) VALUES('base',%s,'res.groups',%s)", [name, rid])
            self.execute(con, 'CREATE TABLE res_groups_users_rel(uid integer REFERENCES res_users(id),'
                              'gid integer REFERENCES res_groups(id),PRIMARY KEY(uid,gid))')
            self.execute(con, "INSERT INTO ir_model_fields(model,name,ttype,relation,relation_table,column1,column2) "
                         "VALUES('res.users',%s,'many2many','res.groups','res_groups_users_rel','uid','gid')", [field])
            for uid in (3, 4, 9409):
                self.execute(con, "INSERT INTO res_users VALUES(%s,'role fixture','test')", [uid])
        self.execute(self.source, 'INSERT INTO res_groups_users_rel VALUES(13,1),(3,3),(4,2),(9409,1)')
        self.execute(self.con, 'INSERT INTO res_groups_users_rel VALUES(7,10),(3,10),(3,30),(4,20),(4,30),(9409,10),(9409,20)')
        runner = self.first({'res_users'})
        # Four target links, four source links, but wrong target roles.
        self.execute(self.con, 'DELETE FROM res_groups_users_rel')
        self.execute(self.con, 'INSERT INTO res_groups_users_rel VALUES(3,30),(4,20),(9409,10),(9409,20)')
        with patch('csv_replicator.copy_table', side_effect=fixtures.relation_copy_only):
            result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['operation_counts']['verified_existing'], 1)
        self.assertEqual(result['operation_counts']['m2m_replaced'], 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_groups_users_rel WHERE uid=9409 AND gid=20'), 0)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_groups_users_rel WHERE uid=13 AND gid=10'), 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_groups'), 3)
        self.assertEqual(self.scalar('SELECT count(*) FROM (SELECT uid FROM res_groups_users_rel GROUP BY uid HAVING count(*)>1) conflicts'), 0)

    def test_old_additive_checkpoint_and_extra_valid_links_cannot_skip_replacement(self):
        runner = self.first()
        self.execute(self.con, 'INSERT INTO a_b_rel VALUES(42,-99)')
        runner.state['operations']['a_b_rel'].update(status='additive_completed', mode='add')
        runner.persist()
        self.con.commit()
        snapshot = (self.stage / 'csv-extraction.json').read_bytes()
        for _ in range(2):
            with patch('csv_replicator.copy_table', side_effect=fixtures.relation_copy_only):
                result = runner.run(runner.plan['target']['fks'])
            self.assertEqual(result['operation_counts']['m2m_replaced'], 1)
            self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
            entry = runner.state['operations']['a_b_rel']
            self.assertEqual(entry['mode'], 'replace')
            self.assertEqual(entry['relation_policy'], M2M_POLICY)
            self.assertEqual(entry['relation_counts'], dict(source_rows=1, inserted_links=1, skipped_links=0, deduplicated_links=0))
        self.assertEqual((self.stage / 'csv-extraction.json').read_bytes(), snapshot)
        self.assertEqual(runner.manifest['mapping_policy'], POLICY)
        self.assertEqual(list((self.stage / 'relation-indexes').glob('*.sqlite')), [])

    def test_missing_xmlids_replace_with_zero_mapped_links_and_report_skip_counts(self):
        runner = self.first()
        self.execute(self.con, "DELETE FROM ir_model_data WHERE name='other'")
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['status'], 'complete_with_warnings')
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 0)
        entry = runner.state['operations']['a_b_rel']
        self.assertEqual(entry['relation_counts'], dict(source_rows=1, inserted_links=0, skipped_links=1, deduplicated_links=0))
        self.assertEqual(entry['verification']['expected']['rows'], 0)

    def collapsing_aliases(self, extra=False, conflict=False):
        self.execute(self.source, "INSERT INTO ab_other VALUES(22,'alias fixture')")
        self.execute(self.source, "INSERT INTO ir_model_data(module,name,model,res_id) VALUES('fixture','alias','ab_other',22)")
        self.execute(self.con, "INSERT INTO ir_model_data(module,name,model,res_id) VALUES('fixture','alias','ab_other',8)")
        if extra:
            for con in (self.source, self.con):
                self.execute(con, 'ALTER TABLE a_b_rel ADD COLUMN note text')
            self.execute(self.source, "UPDATE a_b_rel SET note='same'")
            self.execute(self.con, "UPDATE a_b_rel SET note='old target'")
            self.execute(self.source, 'INSERT INTO a_b_rel VALUES(42,22,%s)', ['different' if conflict else 'same'])
        else:
            self.execute(self.source, 'INSERT INTO a_b_rel VALUES(42,22)')

    def test_mapped_pair_alias_collisions_are_deduplicated(self):
        self.collapsing_aliases()
        runner = self.first()
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
        self.assertEqual(runner.state['operations']['a_b_rel']['relation_counts'],
                         dict(source_rows=2, inserted_links=1, skipped_links=0, deduplicated_links=1))

    def test_conflicting_extra_columns_for_a_collapsed_pair_roll_back(self):
        self.collapsing_aliases(extra=True, conflict=True)
        # Keep the selected endpoint count equal so its old ID survives; the
        # replacement failure must preserve its original valid target link.
        self.execute(self.con, 'DELETE FROM ab_record WHERE id=-99')
        runner = self.runner({'ab_record'})
        first = runner.run(runner.plan['target']['fks'])
        self.assertTrue(any(item['table'] == 'a_b_rel' for item in first['failed_tables']))
        self.assertEqual(self.scalar('SELECT note FROM a_b_rel'), 'old target')
        self.assertEqual(self.scalar('SELECT record_id FROM a_b_rel'), 9)
        self.assertEqual(list((self.stage / 'relation-indexes').glob('*.sqlite')), [])

    def test_identical_extra_columns_are_preserved_during_deduplication(self):
        self.collapsing_aliases(extra=True)
        runner = self.first()
        self.assertEqual(self.scalar('SELECT note FROM a_b_rel'), 'same')
        self.assertEqual(runner.state['operations']['a_b_rel']['relation_counts']['deduplicated_links'], 1)

    def test_both_selected_endpoints_keep_raw_ids_and_deduplicate_source_pairs(self):
        self.execute(self.source, 'ALTER TABLE a_b_rel DROP CONSTRAINT a_b_rel_pkey')
        self.execute(self.source, 'INSERT INTO a_b_rel SELECT * FROM a_b_rel')
        runner = self.first({'ab_record', 'ab_other'})
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id=21'), 1)
        self.assertEqual(runner.state['operations']['a_b_rel']['relation_counts']['deduplicated_links'], 1)

    def test_empty_source_clears_target_links_on_every_run(self):
        self.execute(self.source, 'DELETE FROM a_b_rel')
        runner = self.first()
        for _ in range(2):
            result = runner.run(runner.plan['target']['fks'])
            self.assertEqual(result['operation_counts']['m2m_replaced'], 1)
            self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 0)

    def test_self_relation_replaces_using_the_same_selected_endpoint(self):
        for con, rid in ((self.source, 21), (self.con, 8)):
            self.execute(con, 'CREATE TABLE other_links_rel(parent_id integer REFERENCES ab_other(id),'
                              'child_id integer REFERENCES ab_other(id),PRIMARY KEY(parent_id,child_id))')
            self.execute(con, 'INSERT INTO other_links_rel VALUES(%s,%s)', [rid, rid])
            self.execute(con, "INSERT INTO ir_model_fields(model,name,ttype,relation,relation_table,column1,column2) "
                         "VALUES('ab_other','links','many2many','ab_other','other_links_rel','parent_id','child_id')")
        runner = self.first({'ab_other'})
        self.assertEqual(self.scalar('SELECT parent_id FROM other_links_rel'), 21)
        self.assertEqual(self.scalar('SELECT child_id FROM other_links_rel'), 21)
        self.assertEqual(runner.state['operations']['other_links_rel']['relation_counts']['inserted_links'], 1)

    def test_interrupt_before_replacement_checkpoint_preserves_valid_old_links(self):
        runner = self.first()
        self.execute(self.con, 'DELETE FROM a_b_rel')
        self.execute(self.con, 'INSERT INTO a_b_rel VALUES(42,-99)')
        original = runner.persist
        copied = [False]

        def copy(*args, **kwargs):
            result = copy_table(*args, **kwargs)
            if args[2] == 'a_b_rel':
                copied[0] = True
            return result

        def interrupt():
            if copied[0]:
                copied[0] = False
                raise KeyboardInterrupt()
            original()

        with patch('csv_replicator.copy_table', copy), patch.object(runner, 'persist', interrupt), self.assertRaises(KeyboardInterrupt):
            runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.scalar('SELECT other_id FROM a_b_rel'), -99)
        self.assertEqual(list((self.stage / 'relation-indexes').glob('*.sqlite')), [])
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT other_id FROM a_b_rel'), 8)
