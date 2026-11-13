"""Generic relational IDs tested only in generated disposable databases."""
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

import test_csv_postgres as fixtures
from common import MigrationError, connect
from csv_copy import verify_files
from csv_relations import plan_operations, verified_path


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class XMLIDPostgresTests(unittest.TestCase):
    base = fixtures.CSVPostgresTests
    setUpClass = classmethod(base.setUpClass.__func__)
    tearDownClass = classmethod(base.tearDownClass.__func__)
    setUp = base.setUp
    tearDown = base.tearDown
    scalar = base.scalar
    export = base.export
    edit = base.edit
    runner = base.runner

    def execute(self, connection, query, params=None):
        with connection.cursor() as cr:
            cr.execute(query, params)
        connection.commit()

    def issue_kinds(self, runner, table):
        artifact = runner.state['operations'][table]['mapping']['artifact']
        path = verified_path(self.stage, artifact)
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            return {row[0] for row in db.execute('SELECT kind FROM issues')}
        finally:
            db.close()

    def test_generic_m2o_and_m2m_map_ignored_endpoint_ids(self):
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 42)
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id=8'), 1)
        self.assertEqual(self.scalar('SELECT id FROM ab_other'), 8)
        self.assertEqual(self.scalar('SELECT id FROM res_users'), 7)
        self.assertEqual(runner.state['operations']['ab_record']['mapping']['stats']['resolved_references'], 1)

    def test_missing_m2o_does_not_fall_back_to_valid_numeric_id(self):
        self.execute(self.con, "DELETE FROM ir_model_data WHERE name='user'")
        self.execute(self.con, "INSERT INTO res_users VALUES(13,'unrelated record','test')")
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertTrue(any(item['table'] == 'ab_record' for item in result['failed_tables']))
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 1)
        self.assertEqual(self.issue_kinds(runner, 'ab_record'), {'missing_target_xmlid'})

    def test_missing_source_xmlid_and_wrong_model_and_dangling_target_fail(self):
        # Missing source aliases are distinguishable from missing target aliases.
        self.execute(self.source, "DELETE FROM ir_model_data WHERE name='user'")
        runner = self.runner({'ab_record'})
        runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.issue_kinds(runner, 'ab_record'), {'missing_source_xmlid'})
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)

    def test_wrong_target_model_is_not_a_match(self):
        self.execute(self.con, "UPDATE ir_model_data SET model='ab_other' WHERE name='user'")
        runner = self.runner({'ab_record'})
        runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.issue_kinds(runner, 'ab_record'), {'model_mismatch'})

    def test_dangling_target_xmlid_is_not_a_match(self):
        self.execute(self.con, "UPDATE ir_model_data SET res_id=999 WHERE name='user'")
        runner = self.runner({'ab_record'})
        runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.issue_kinds(runner, 'ab_record'), {'missing_target_record'})

    def test_null_m2o_and_explicit_constants_bypass_mapping(self):
        self.execute(self.source, 'UPDATE ab_record SET create_uid=NULL')
        runner = self.runner({'ab_record'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertIsNone(self.scalar('SELECT create_uid FROM ab_record'))
        self.assertEqual(runner.state['operations']['ab_record']['mapping']['stats']['missing_references'], 0)

    def test_constant_bypasses_missing_alias(self):
        self.execute(self.source, "DELETE FROM ir_model_data WHERE name='user'")
        runner = self.runner({'ab_record'}, {'ab_record': {'create_uid': 7}})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)
        self.assertNotIn('mapping', runner.state['operations']['ab_record'])

    def test_both_selected_keep_source_ids(self):
        runner = self.runner({'ab_record', 'ab_other', 'res_users'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 13)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id=21'), 1)

    def test_unknown_m2o_comodel_fails_planning_without_numeric_fallback(self):
        self.execute(self.source, "UPDATE ir_model_fields SET relation='missing.model' WHERE name='create_uid'")
        with self.assertRaisesRegex(MigrationError, 'endpoint model/table unavailable'):
            self.runner({'ab_record'})
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)

    def test_constant_bypasses_unavailable_m2o_metadata(self):
        self.execute(self.source, "UPDATE ir_model_fields SET relation='missing.model' WHERE name='create_uid'")
        runner = self.runner({'ab_record'}, {'ab_record': {'create_uid': 7}})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)

    def test_interrupt_before_mapped_checkpoint_commit_rolls_back_then_resumes(self):
        runner = self.runner({'ab_record'})
        original = runner.persist

        def interrupt():
            if runner.state['operations'].get('ab_record', {}).get('success'):
                raise KeyboardInterrupt()
            original()

        with patch.object(runner, 'persist', interrupt), self.assertRaises(KeyboardInterrupt):
            runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        self.assertFalse(runner.state['operations'].get('ab_record', {}).get('success'))
        verify_files(self.stage, runner.manifest)
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)

    def test_m2m_missing_skips_link_with_warning(self):
        self.execute(self.con, "DELETE FROM ir_model_data WHERE name='other'")
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(result['skipped_links'], 1)
        self.assertEqual(result['status'], 'complete_with_warnings')
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 0)
        self.assertEqual(self.issue_kinds(runner, 'a_b_rel'), {'missing_target_xmlid'})

    def add_alias(self, model, name, source_id, target_id):
        for connection, rid in ((self.source, source_id), (self.con, target_id)):
            self.execute(connection, "INSERT INTO ir_model_data(module,name,model,res_id) VALUES('fixture',%s,%s,%s)",
                         [name, model, rid])

    def test_ambiguous_m2o_fails_table_same_target_aliases_are_allowed(self):
        self.add_alias('res.users', 'user_alias', 13, 7)
        runner = self.runner({'ab_record'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)

    def test_conflicting_m2o_aliases_fail(self):
        self.execute(self.con, "INSERT INTO res_users VALUES(17,'other identity','test')")
        self.add_alias('res.users', 'user_alias', 13, 17)
        runner = self.runner({'ab_record'})
        runner.run(runner.plan['target']['fks'])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        self.assertEqual(self.issue_kinds(runner, 'ab_record'), {'ambiguous'})

    def test_conflicting_m2m_aliases_fail_instead_of_skip(self):
        self.execute(self.con, "INSERT INTO ab_other VALUES(18,'other identity')")
        self.add_alias('ab_other', 'other_alias', 21, 18)
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertTrue(any(item['table'] == 'a_b_rel' for item in result['failed_tables']))
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel'), 0)
        self.assertEqual(self.issue_kinds(runner, 'a_b_rel'), {'ambiguous'})

    def test_unidirectional_m2m_maps_either_nonselected_endpoint(self):
        for connection in (self.source, self.con):
            self.execute(connection, "DELETE FROM ir_model_fields WHERE model='ab_other'")
        runner = self.runner({'ab_other'})
        self.assertEqual(runner.operations['a_b_rel']['mode'], 'replace')
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'), 9)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=9 AND other_id=21'), 1)

    def test_renamed_m2m_fields_match_physical_roles(self):
        self.execute(self.con, "UPDATE ir_model_fields SET name=name||'_v19' WHERE ttype='many2many'")
        runner = self.runner({'ab_record'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id=8'), 1)

    def test_standard_user_group_names_and_different_group_ids(self):
        for connection, gid, uid, field in ((self.source, 3, 13, 'groups_id'), (self.con, 4, 7, 'group_ids')):
            with connection.cursor() as cr:
                cr.execute('CREATE TABLE res_groups(id integer PRIMARY KEY)')
                cr.execute('INSERT INTO res_groups VALUES(%s)', [gid])
                cr.execute("INSERT INTO ir_model(model,transient) VALUES('res.groups',false)")
                cr.execute('CREATE TABLE res_groups_users_rel(uid integer REFERENCES res_users(id),gid integer REFERENCES res_groups(id),PRIMARY KEY(uid,gid))')
                cr.execute('INSERT INTO res_groups_users_rel VALUES(%s,%s)', [uid, gid])
                cr.execute("INSERT INTO ir_model_fields(model,name,ttype,relation_table,column1,column2,relation) "
                           "VALUES('res.users',%s,'many2many','res_groups_users_rel','uid','gid','res.groups')", [field])
                cr.execute("INSERT INTO ir_model_data(module,name,model,res_id) VALUES('base','group_system','res.groups',%s)", [gid])
            connection.commit()
        runner = self.runner({'res_users'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT count(*) FROM res_groups_users_rel WHERE uid=13 AND gid=4'), 1)
        self.assertEqual(self.scalar('SELECT count(*) FROM res_groups_users_rel WHERE uid=13 AND gid=3'), 0)
        self.assertEqual(self.scalar('SELECT id FROM res_groups'), 4)

    def test_prepared_target_map_survives_selected_xmlid_table_replacement(self):
        for connection in (self.source, self.con):
            self.execute(connection, "INSERT INTO ir_model(model,transient) VALUES('ir.model.data',false)")
        runner = self.runner({'ab_record', 'ir_model_data'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='other'"), 8)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id=8'), 1)
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_pending_retry_after_xmlid_replacement_uses_original_prepared_map(self):
        for connection in (self.source, self.con):
            self.execute(connection, "INSERT INTO ir_model(model,transient) VALUES('ir.model.data',false)")
        self.execute(self.con, "ALTER TABLE ab_record ADD COLUMN required text NOT NULL DEFAULT 'old'")
        runner = self.runner({'ab_record', 'ir_model_data'})
        self.assertTrue(runner.run(runner.plan['target']['fks'])['failed_tables'])
        self.assertTrue(runner.state['operations']['ir_model_data']['success'])
        runner.operations['ab_record']['constants']['required'] = 'fixed'
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id=8'), 1)

    def test_changed_target_xmlid_rechecks_and_recopies_current_expected_values(self):
        self.execute(self.con, "DELETE FROM ir_model_data WHERE name='user'")
        runner = self.runner({'ab_record'})
        self.assertTrue(runner.run(runner.plan['target']['fks'])['failed_tables'])
        self.execute(self.con, "INSERT INTO ir_model_data(module,name,model,res_id) VALUES('fixture','user','res.users',7)")
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.execute(self.con, "INSERT INTO res_users VALUES(17,'other identity','test')")
        self.execute(self.con, "UPDATE ir_model_data SET res_id=17 WHERE name='user'")
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)
        self.assertEqual(runner.state['operations']['ab_record']['status'], 'verified_existing')

    def test_source_snapshot_is_used_not_current_source_xmlids(self):
        runner = self.runner({'ab_record'})
        self.source.set_session(readonly=False)
        self.execute(self.source, "UPDATE ir_model_data SET name='later_change' WHERE name='user'")
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 7)

    def test_mapping_artifact_corruption_blocks_resume(self):
        runner = self.runner({'ab_record'})
        runner.run(runner.plan['target']['fks'])
        info = runner.state['operations']['ab_record']['mapping']['artifact']
        path = Path(self.stage) / info['file']
        with path.open('ab') as file:
            file.write(b'changed')
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])

    def test_plain_integer_column_is_not_mapped(self):
        for connection in (self.source, self.con):
            self.execute(connection, 'ALTER TABLE ab_record ADD COLUMN external_integer integer')
        self.execute(self.source, 'UPDATE ab_record SET external_integer=13')
        runner = self.runner({'ab_record'})
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT external_integer FROM ab_record'), 13)

    def test_nonstored_many2one_metadata_does_not_remap_retained_physical_column(self):
        for connection in (self.source, self.con):
            self.execute(connection, "UPDATE ir_model_fields SET store=false WHERE name='create_uid'")
        runner = self.runner({'ab_record'})
        self.assertNotIn('references', runner.operations['ab_record'])
        self.assertEqual(runner.run(runner.plan['target']['fks'])['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'), 13)

    def test_more_than_one_mapping_batch_and_only_metadata_not_business_payloads(self):
        with self.source.cursor() as cr:
            cr.execute("INSERT INTO ab_other SELECT 100+g,'source' FROM generate_series(1,1200) g")
            cr.execute("INSERT INTO ir_model_data(module,name,model,res_id) SELECT 'batch','other_'||g,'ab_other',100+g FROM generate_series(1,1200) g")
            cr.execute('INSERT INTO a_b_rel SELECT 42,100+g FROM generate_series(1,1200) g')
        self.source.commit()
        with self.con.cursor() as cr:
            cr.execute("INSERT INTO ab_other SELECT 2000+g,'target' FROM generate_series(1,1200) g")
            cr.execute("INSERT INTO ir_model_data(module,name,model,res_id) SELECT 'batch','other_'||g,'ab_other',2000+g FROM generate_series(1,1200) g")
        self.con.commit()
        runner = self.runner({'ab_record'})
        result = runner.run(runner.plan['target']['fks'])
        self.assertEqual(result['failed_tables'], [])
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42'), 1201)
        self.assertEqual(self.scalar('SELECT count(*) FROM a_b_rel WHERE record_id=42 AND other_id>2000'), 1200)
        self.assertEqual(result['mapping']['a_b_rel']['stats']['resolved_references'], 1201)

    def test_both_ignored_do_not_derive_association_copy(self):
        runner = self.runner(set())
        self.assertEqual(runner.operations, {})

    def test_source_xmlid_artifact_corruption_is_detected(self):
        runner = self.runner({'ab_record'})
        descriptor = runner.manifest['xmlids']
        with (Path(self.stage) / descriptor['file']).open('ab') as file:
            file.write(b'changed')
        with self.assertRaisesRegex(MigrationError, 'artifact'):
            verify_files(self.stage, runner.manifest)

    def test_old_retained_extraction_is_not_reinterpreted(self):
        from csv_replicator import run
        from common import save_json
        runner = self.runner({'ab_record'})
        runner.manifest.pop('mapping_policy')
        save_json(self.stage / 'csv-extraction.json', runner.manifest)
        # Exercise the public preflight using the run directory it expects.
        root = self.stage / 'root'
        destination = root / ('csv_' + runner.plan['plan_id'])
        destination.mkdir(parents=True, mode=0o700)
        save_json(destination / 'csv-extraction.json', runner.manifest)
        original = (destination / 'csv-extraction.json').read_bytes()
        with patch('csv_replicator.ensure_backup', side_effect=MigrationError('preflight_complete')):
            with self.assertRaisesRegex(MigrationError, 'preflight_complete'):
                run(self.args, root)
        self.assertEqual((destination / 'csv-extraction.json').read_bytes(), original)
        self.assertTrue(list(destination.glob('generation_*/csv-extraction.json')))
