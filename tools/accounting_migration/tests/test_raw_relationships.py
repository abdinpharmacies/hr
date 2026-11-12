"""Report-only references exercised only in generated disposable databases."""
import copy
import os
import unittest
from unittest.mock import patch

from psycopg2 import sql
import test_prepared_postgres as fixtures
from common import loads
from raw_importer import RawImporter
from prepared_importer import PreparedImporter
from prepared import read_checkpoint,write_checkpoint
from table_checkpoints import TableMigration
from prepared_snapshot import SCHEMA
from table_resume import ResumeState
from common import MigrationError


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'),'requires disposable PostgreSQL config')
class RawRelationshipTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.PreparedPostgresTests.setUpClass.__func__)
    tearDownClass=classmethod(fixtures.PreparedPostgresTests.tearDownClass.__func__)
    setUp=fixtures.PreparedPostgresTests.setUp
    tearDown=fixtures.PreparedPostgresTests.tearDown
    scalar=fixtures.PreparedPostgresTests.scalar
    def fixture(self):
        engine=fixtures.PreparedPostgresTests.fixture(self)
        # Ordinary raw-policy cases do not require replacing parents protected
        # by prepared standard/target-only rows. Protection cases seed them below.
        with self.con.cursor() as cr:
            cr.execute('UPDATE res_users SET accounting_auth_group_id=NULL')
            cr.execute('UPDATE ab_target_only SET group_id=NULL')
            cr.execute('DELETE FROM user_group_link')
        self.con.commit()
        return engine

    def run_raw(self, callback=None):
        engine=RawImporter(*self.arguments)
        engine.validate_ids()
        engine.preflight(replacing=not bool(read_checkpoint(self.con,'table_setup')))
        runner=TableMigration(engine,write_checkpoint)
        return runner.run(self.source_files,self.target_files,callback)

    def test_raw_ids_commit_despite_missing_foreign_keys_and_allocate_attachments(self):
        self.fixture()
        result=self.run_raw()
        self.assertEqual(result['status'],'complete_with_warnings',result)
        self.assertEqual(result['failed_tables'],[])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)

        self.assertEqual(self.scalar('SELECT currency_id FROM ab_record'),4)
        self.assertIsNone(self.scalar('SELECT accounting_auth_group_id FROM res_users WHERE id=1'))
        self.assertEqual(self.scalar('SELECT res_id FROM ir_attachment WHERE id=1'),9)
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)
        self.assertNotEqual(self.scalar('SELECT attachment_id FROM ab_record'),1)
        self.assertTrue(any(f['constraint']=='ab_record_currency_id_fkey' for f in result['failed_foreign_keys']))
        report=loads((self.stage/'relationship_report.json').read_text())
        self.assertGreater(report['counts'].get('missing_reference',0),0)
        details=[loads(line) for line in (self.stage/'relationship_issues.jsonl').read_text().splitlines()]
        self.assertTrue(any(x.get('field')=='currency_id' and x.get('reference_ids')==[4] for x in details))
        self.assertTrue((self.stage/'migration_report.md').exists())
        with patch.object(TableMigration,'copy_model',side_effect=AssertionError('recopy')):
            second=self.run_raw()
        self.assertEqual(second['status'],'complete_with_warnings',second)
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)

    def test_unchanged_phases_keep_hashes_and_actions_while_mutations_refresh(self):
        self.fixture()
        scans = []
        original = ResumeState.digest
        phase = [None]
        unit = TableMigration.unit

        def observe_unit(runner, table, operation, *args, **kwargs):
            phase[0] = operation
            return unit(runner, table, operation, *args, **kwargs)

        def digest(state, table, descriptor):
            scans.append((table, phase[0]))
            return original(state, table, descriptor)

        with patch.object(TableMigration, 'unit', observe_unit), patch.object(ResumeState, 'digest', digest):
            result = self.run_raw()
        self.assertEqual(result['failed_tables'], [], result)
        for table in ('ab_group', 'ab_record'):
            self.assertNotIn((table, 'xmlids'), scans)
            self.assertNotIn((table, 'external'), scans)
        self.assertNotIn(('ab_group', 'attachment_links'), scans)
        self.assertEqual(scans.count(('ab_record', 'attachment_links')), 1)
        for table in ('ab_group', 'ab_record'):
            for operation in ('xmlids', 'external', 'attachment_links'):
                self.assertTrue(read_checkpoint(self.con, 'table:' + operation + ':' + table)['success'])
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='new_alias'"), 42)
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_record_att_rel'), 2)
        self.assertNotEqual(self.scalar('SELECT attachment_id FROM ab_record'), 1)
        with patch.object(TableMigration, 'copy_model', side_effect=AssertionError('recopy')):
            self.assertEqual(self.run_raw()['failed_tables'], [])
        with self.con.cursor() as cr:
            cr.execute("UPDATE ab_group SET name='outside edit'")
        self.con.commit()
        with self.assertRaisesRegex(MigrationError, 'Committed table data changed'):
            self.run_raw()
        self.con.rollback()

    def test_no_refresh_falls_back_and_external_relation_action_still_commits(self):
        self.fixture()
        self.run_raw()
        engine = RawImporter(*self.arguments)
        engine.preflight(replacing=False)
        runner = TableMigration(engine, write_checkpoint)
        # Exercise an external relation action with no deferred custom columns.
        relation = next(p for p in engine.relations if p['table'] == 'ab_record_user_rel')
        relation['phase'] = 'external'
        engine.relations = [relation]
        with self.con.cursor() as cr:
            cr.execute('DELETE FROM ab_record_user_rel')
        self.con.commit()
        before = runner.resume.state['checks']['ab_record']['hash']
        with patch.object(runner.resume, 'digest', wraps=runner.resume.digest) as digest:
            self.assertTrue(runner.unit('ab_record', 'external', engine.external,
                                       force=True, refresh_fingerprint=False))
            digest.assert_not_called()
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_record_user_rel'), 1)
        self.assertEqual(runner.resume.state['checks']['ab_record']['hash'], before)
        del runner.resume.state['checks']['ab_group']
        with patch.object(runner.resume, 'digest', wraps=runner.resume.digest) as digest:
            self.assertTrue(runner.unit('ab_group', 'external', lambda: None,
                                       force=True, refresh_fingerprint=False))
            self.assertEqual(digest.call_count, 1)
        self.assertTrue(runner.resume.has_full_fingerprint('ab_group'))

    def test_failed_checkpoint_rolls_back_refreshed_hash_and_data(self):
        self.fixture()
        self.run_raw()
        engine = RawImporter(*self.arguments)
        engine.preflight(replacing=False)
        runner = TableMigration(engine, write_checkpoint)
        previous = read_checkpoint(self.con, 'resume_state')['checks']['ab_group']['hash']

        def mutate():
            engine.execute("UPDATE ab_group SET name='temporary change'")

        with patch.object(runner.resume, 'save', side_effect=ValueError('checkpoint failure')):
            self.assertFalse(runner.unit('ab_group', 'external', mutate, force=True))
        self.assertEqual(self.scalar('SELECT name FROM ab_group'), 'source group')
        self.assertEqual(runner.resume.state['checks']['ab_group']['hash'], previous)
        self.assertEqual(read_checkpoint(self.con, 'resume_state')['checks']['ab_group']['hash'], previous)
        with patch.object(TableMigration, 'copy_model', side_effect=AssertionError('recopy')):
            self.assertEqual(self.run_raw()['failed_tables'], [])

    def test_interrupt_after_unchanged_operation_commit_resumes_from_marker(self):
        self.fixture()
        unit = TableMigration.unit

        def interrupt(runner, table, operation, *args, **kwargs):
            result = unit(runner, table, operation, *args, **kwargs)
            if operation == 'xmlids':
                raise KeyboardInterrupt()
            return result

        with patch.object(TableMigration, 'unit', interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_raw()
        self.assertIsNone(read_checkpoint(self.con, 'table_result'))
        self.assertTrue(read_checkpoint(self.con, 'table:xmlids:ab_group')['success'])
        with patch.object(TableMigration, 'copy_model', side_effect=AssertionError('recopy')):
            result = self.run_raw()
        self.assertEqual(result['failed_tables'], [], result)
        self.assertTrue(any(item['operation'] == 'xmlids' and item['table'] == 'ab_group'
                            for item in result['skipped']))

    def test_future_integer_and_polymorphic_rules_do_not_enforce_relationships(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_record ADD COLUMN res_id integer')
            cr.execute('ALTER TABLE ab_record ADD COLUMN model_ref varchar')
            cr.execute('ALTER TABLE prepared_migration_source.ab_record ADD COLUMN res_id integer')
            cr.execute('ALTER TABLE prepared_migration_source.ab_record ADD COLUMN model_ref varchar')
            cr.execute("UPDATE prepared_migration_source.ab_record SET res_id=987654,model_ref='missing_model'")
        target=copy.deepcopy(self.arguments[3])
        target['ab_record']['fields'].update(res_id=dict(type='integer',store=True),model_ref=dict(type='char',store=True))
        manifest=self.arguments[2]
        manifest['models']['ab_record']['fields']=copy.deepcopy(target['ab_record']['fields'])
        from bulk import catalog
        manifest['tables']['ab_record']['columns']=catalog(self.con)['ab_record']
        rules={**self.arguments[4],'stable_keys':{'res.users':'password'},'external_ids':{'res.currency':{'4':900}}}
        conversions={'integer_links':{'ab_record':{'group_id':'future_missing_model'}},
                     'polymorphic':{'ab_record':{'res_id':'model_ref'}}}
        self.arguments=(*self.arguments[:3],target,rules,conversions)
        self.con.commit()
        result=self.run_raw()
        self.assertEqual(result['failed_tables'],[],result)
        self.assertEqual(self.scalar('SELECT res_id FROM ab_record'),987654)
        self.assertEqual(self.scalar('SELECT currency_id FROM ab_record'),4)
        self.assertEqual(self.scalar('SELECT group_id FROM ab_record'),13)
        details=[loads(line) for line in (self.stage/'relationship_issues.jsonl').read_text().splitlines()]
        self.assertTrue(any(x.get('referenced_model')=='missing_model' for x in details))

    def test_required_and_composite_foreign_keys_are_report_only(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_record ALTER COLUMN currency_id SET NOT NULL')
            cr.execute('CREATE TABLE external_pair(a integer,b integer,PRIMARY KEY(a,b))')
            cr.execute('INSERT INTO external_pair VALUES(1,1)')
            cr.execute('ALTER TABLE ab_record ADD COLUMN pair_a integer DEFAULT 1')
            cr.execute('ALTER TABLE ab_record ADD COLUMN pair_b integer DEFAULT 1')
            cr.execute('ALTER TABLE ab_record ADD CONSTRAINT pair_fk FOREIGN KEY(pair_a,pair_b) REFERENCES external_pair(a,b)')
            cr.execute('ALTER TABLE prepared_migration_source.ab_record ADD COLUMN pair_a integer')
            cr.execute('ALTER TABLE prepared_migration_source.ab_record ADD COLUMN pair_b integer')
            cr.execute('UPDATE prepared_migration_source.ab_record SET pair_a=999,pair_b=888')
        target=copy.deepcopy(self.arguments[3])
        for field in ('pair_a','pair_b'):
            target['ab_record']['fields'][field]=dict(type='integer',store=True)
        manifest=self.arguments[2]
        manifest['models']['ab_record']['fields']=copy.deepcopy(target['ab_record']['fields'])
        from bulk import catalog
        manifest['tables']['ab_record']['columns']=catalog(self.con)['ab_record']
        self.arguments=(*self.arguments[:3],target,*self.arguments[4:])
        self.con.commit()
        result=self.run_raw()
        self.assertEqual(result['failed_tables'],[],result)
        self.assertEqual(result['status'],'complete_with_warnings')
        self.assertTrue(any(f['constraint']=='pair_fk' for f in result['failed_foreign_keys']))
        self.assertEqual(self.scalar('SELECT pair_a FROM ab_record'),999)

    def test_user_partner_low_ids_are_excluded_but_missing_high_ids_are_warnings(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('INSERT INTO prepared_migration_source.res_users(id) VALUES(5),(777)')
            cr.execute('INSERT INTO prepared_migration_source.res_partner(id) VALUES(6),(888)')
            cr.execute('UPDATE prepared_migration_source.ab_record SET create_uid=5')
        self.con.commit()
        result=self.run_raw()
        self.assertEqual(result['failed_tables'],[],result)
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'),5)
        ids=loads((self.stage/'id-validation.json').read_text())
        self.assertEqual(ids['res_users']['missing_ids'],[777])
        self.assertEqual(ids['res_partner']['missing_ids'],[888])
        details=[loads(line) for line in (self.stage/'relationship_issues.jsonl').read_text().splitlines()]
        identities=[x['source_record_id'] for x in details if x['kind']=='missing_identity']
        self.assertEqual(sorted(identities),[777,888])

    def test_policy_change_preserves_old_completed_operations(self):
        engine=self.fixture()
        engine.validate_ids()
        engine.preflight()
        old=TableMigration(engine,write_checkpoint).run(self.source_files,self.target_files)
        self.assertEqual(old['status'],'complete')
        self.assertEqual(self.scalar('SELECT currency_id FROM ab_record'),900)
        with patch.object(TableMigration,'copy_model',side_effect=AssertionError('policy recopy')):
            result=self.run_raw()
        self.assertEqual(result['failed_tables'],[],result)
        self.assertEqual(self.scalar('SELECT currency_id FROM ab_record'),900)
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)

    def test_shared_links_and_xmlid_conflicts_preserve_prepared_records(self):
        self.fixture()
        target=copy.deepcopy(self.arguments[3])
        target['res.users']['fields']['record_ids']=dict(type='many2many',relation='ab_record',
            relation_table='ab_record_user_rel',column1='user_id',column2='record_id',module='ab_test')
        self.arguments=(*self.arguments[:3],target,*self.arguments[4:])
        with self.con.cursor() as cr:
            cr.execute("UPDATE ir_model_data SET model='res.users' WHERE module='custom' AND name='record'")
        self.con.commit()
        result=self.run_raw()
        self.assertEqual(result['failed_tables'],[],result)
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_record_user_rel'),2)
        self.assertEqual(self.scalar("SELECT model FROM ir_model_data WHERE module='custom' AND name='record'"),'res.users')
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)
        with patch.object(TableMigration,'copy_model',side_effect=AssertionError('conflict recopy')):
            second=self.run_raw()
        self.assertEqual(second['failed_tables'],[],second)

    def test_orm_audit_failure_does_not_undo_copy(self):
        self.fixture()
        def fail(models):
            raise RuntimeError('injected ORM reference read failure')
        result=self.run_raw(fail)
        self.assertEqual(result['status'],'complete_with_warnings',result)
        self.assertEqual(result['failed_tables'],[])
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)

    def test_company_properties_preserve_raw_ids_and_record_specific_values(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_record ADD COLUMN price jsonb')
            cr.execute('ALTER TABLE ab_record ADD COLUMN owner_partner jsonb')
            cr.execute('CREATE TABLE res_company(id integer PRIMARY KEY)')
            cr.execute('INSERT INTO res_company VALUES(900)')
            cr.execute('CREATE TABLE prepared_migration_source.res_company(id integer)')
            cr.execute('INSERT INTO prepared_migration_source.res_company VALUES(1)')
            cr.execute('CREATE TABLE prepared_migration_source.ir_property(id integer,fields_id integer,res_id varchar,'
                       'company_id integer,value_float double precision,value_reference varchar)')
            cr.execute("INSERT INTO prepared_migration_source.ir_model_fields VALUES"
                       "(101,'ab_record','price','float',NULL),(102,'ab_record','owner_partner','many2one','res.partner')")
            cr.execute("INSERT INTO prepared_migration_source.ir_property VALUES"
                       "(1,101,NULL,1,2.5,NULL),(2,101,'ab_record,42',1,3.5,NULL),"
                       "(3,102,'ab_record,42',1,NULL,'res.partner,777')")
        target=copy.deepcopy(self.arguments[3])
        manifest=self.arguments[2]
        for name,kind,related in [('price','float',None),('owner_partner','many2one','res.partner')]:
            target['ab_record']['fields'][name]=dict(type=kind,store=True,company_dependent=True,relation=related)
            manifest['models']['ab_record']['fields'][name]=dict(ttype=kind,company_dependent=True,relation=related)
        target['res.company']=dict(table='res_company',fields={})
        manifest['tables']['ir_property']={}
        manifest['tables']['res_company']={}
        self.arguments=(*self.arguments[:3],target,*self.arguments[4:])
        self.con.commit()
        result=self.run_raw()
        self.assertEqual(result['failed_tables'],[],result)
        self.assertEqual(self.scalar('SELECT price FROM ab_record'),{'1':3.5})
        self.assertEqual(self.scalar('SELECT owner_partner FROM ab_record'),{'1':777})
        self.assertEqual(self.scalar('SELECT id FROM res_company'),900)

    def test_not_null_failure_remains_isolated_and_does_not_stop_other_copies(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('UPDATE prepared_migration_source.ab_group SET name=NULL')
        self.con.commit()
        result=self.run_raw()
        self.assertEqual(result['status'],'finished_with_errors')
        self.assertEqual(self.scalar('SELECT id FROM ab_group'),7)
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)
        self.assertTrue(any(x.get('sqlstate')=='23502' for x in result['failed_tables']))
