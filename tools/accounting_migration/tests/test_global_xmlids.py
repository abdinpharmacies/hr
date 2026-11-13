"""Global alias repairs, only in generated disposable PostgreSQL fixtures."""
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

import test_database_repair as fixtures
from common import MigrationError
from csv_plan import database_identity
from database_repair import perform
from repair_fixes import apply_data
from repair_xmlids import build


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class GlobalXMLIDTests(unittest.TestCase):
    base = fixtures.DatabaseRepairTests
    setUpClass = classmethod(base.setUpClass.__func__)
    tearDownClass = classmethod(base.tearDownClass.__func__)
    tearDown = base.tearDown
    scalar = base.scalar

    def setUp(self):
        self.base.setUp(self)
        for connection in (self.source,self.con):
            with connection.cursor() as cr:
                for name,state in [('ab_accounting','installed'),('ab_accounting_base','installed'),
                                   ('feature_x','installed'),('unused_module','uninstalled'),('__export__','installed')]:
                    cr.execute('INSERT INTO ir_module_module VALUES(%s,%s)',[name,state])
                for model in ('ab_accounting_account_guide','other.seed','unreplicated.seed'):
                    cr.execute('INSERT INTO ir_model(model) VALUES(%s)',[model])
                cr.execute('CREATE TABLE ab_accounting_account_guide(id integer PRIMARY KEY,name text UNIQUE,parent_id integer)')
                cr.execute("INSERT INTO ab_accounting_account_guide VALUES(495,'Root',NULL),(1,'Assets',495),(257,'Liabilities',495)")
                cr.execute('CREATE TABLE other_seed(id integer PRIMARY KEY,name text UNIQUE)')
                cr.execute("INSERT INTO other_seed VALUES(42,'Feature seed')")
                cr.execute('CREATE TABLE unreplicated_seed(id integer PRIMARY KEY,name text)')
                cr.execute("INSERT INTO unreplicated_seed VALUES(9,'Correct target-local record'),(17,'Coincident numeric ID')")
                for module in ('ab_accounting','ab_accounting_base'):
                    for name,rid in [('root',495),('liability',257)]:
                        actual=rid if connection is self.source else dict(root=1,liability=3)[name]
                        cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,'ab_accounting_account_guide',%s,%s)",
                                   [module,name,actual,connection is self.source])
                for module,name,model,rid in [('feature_x','new_seed','other.seed',42),
                                               ('feature_x','unreplicated','unreplicated.seed',17),
                                               ('unused_module','ignored','other.seed',42),
                                               ('__export__','ignored','other.seed',42)]:
                    if connection is self.con and name=='new_seed':
                        continue
                    cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,true)',
                               [module,name,model,9 if connection is self.con and name=='unreplicated' else rid])
                if connection is self.con:
                    cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES('feature_x','target_only','other.seed',42,true)")
            connection.commit()
        discovery=self.stage/'discovery.conf'
        discovery.write_text('[options]\naddons_path=\n')
        self.context=dict(source_config=str(discovery),target_config=str(discovery),
                          identities=dict(source=database_identity(self.source,self.config),target=database_identity(self.con,self.config)))
        self.legacy=dict(format=3,identities=self.context['identities'],operations={
            'ab_accounting_account_guide':dict(success=True,mode='replace',rows=3,expected=3,target_count=3,fingerprint='a'*64)})
        self.current=dict(format=4,identities=self.context['identities'],previous_checkpoint='archive:old',operations={
            'ab_accounting_account_guide':dict(success=True,mode='replace',rows=0,expected=3,target_count=3,status='verified_existing'),
            'other_seed':dict(success=True,mode='replace',rows=1,expected=1,target_count=1,status='copied')},constraints=self.saved)
        with self.con.cursor() as cr:
            cr.execute("INSERT INTO csv_replication.checkpoint VALUES('archive:old',%s)",[json.dumps(self.legacy)])
        self.save_current()

    def save_current(self):
        with self.con.cursor() as cr:
            cr.execute("UPDATE csv_replication.checkpoint SET value=%s WHERE name='state'",[json.dumps(self.current)])
        self.con.commit()

    def plan(self):
        return build(self.source,self.con,self.context)

    def apply(self,plan=None):
        plan=plan or self.plan()
        self.con.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            return perform(self.con,self.source,self.stage,['identities'],{'identities':plan},
                           self.context['identities'],self.context)

    def test_multiple_namespaces_wrong_existing_and_missing_records_are_fixed(self):
        plan=self.plan()
        accounts=[c for c in plan['changes'] if c['group_model']=='ab_accounting_account_guide']
        self.assertEqual(len(accounts),4)
        self.assertTrue(all(c['evidence']['format']==3 for c in accounts))
        self.assertTrue(all(c['after']['noupdate'] is False for c in accounts))
        self.assertTrue(any(c['group_model']=='other.seed' and c['before'] is None for c in plan['changes']))
        result=self.apply(plan)
        self.assertTrue(all(r['status']=='committed' for r in result),result)
        self.assertEqual(self.scalar("SELECT count(*) FROM ir_model_data WHERE module IN ('ab_accounting','ab_accounting_base') AND name='liability' AND res_id=257"),2)
        self.assertEqual(self.scalar("SELECT count(*) FROM ir_model_data WHERE module IN ('ab_accounting','ab_accounting_base') AND name='root' AND res_id=495"),2)
        self.assertEqual(self.scalar("SELECT count(*) FROM ir_model_data WHERE module IN ('ab_accounting','ab_accounting_base') AND noupdate=false"),4)
        self.assertTrue(self.scalar("SELECT noupdate FROM ir_model_data WHERE module='feature_x' AND name='new_seed'"))
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_accounting_account_guide'),3)
        self.assertEqual(self.plan()['changes'],[])
        with self.con.cursor() as cr:
            cr.execute('SAVEPOINT duplicate_name')
            with self.assertRaises(Exception) as error:
                cr.execute("INSERT INTO ab_accounting_account_guide VALUES(999,'Liabilities',495)")
            self.assertEqual(error.exception.pgcode,'23505')
            cr.execute('ROLLBACK TO SAVEPOINT duplicate_name')

    def test_unreplicated_target_only_uninstalled_and_generated_aliases_preserved(self):
        plan=self.plan()
        self.assertTrue(any(r['reason']=='no_verified_source_id_copy' and r['name']=='unreplicated' for r in plan['unresolved']))
        self.assertTrue(any(r['reason']=='source_alias_missing_target_preserved' for r in plan['unresolved']))
        self.assertFalse(any(c['after'].get('module') in ('unused_module','__export__') for c in plan['changes']))
        self.apply(plan)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='unreplicated'"),9)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='target_only'"),42)

    def test_equal_counts_without_committed_copy_are_not_evidence(self):
        self.current.pop('previous_checkpoint')
        self.save_current()
        self.assertFalse(any(c['group_model']=='ab_accounting_account_guide' for c in self.plan()['changes']))

    def test_later_copy_from_another_source_invalidates_archived_proof(self):
        self.current['operations']['ab_accounting_account_guide']=dict(success=True,mode='replace',rows=3,expected=3,target_count=3,status='forced_copy')
        self.current['identities']=dict(self.context['identities'],source={'database':'different source'})
        self.save_current()
        self.assertFalse(any(c['group_model']=='ab_accounting_account_guide' for c in self.plan()['changes']))

    def test_bad_model_and_missing_destinations_do_not_block_other_aliases(self):
        with self.con.cursor() as cr:
            cr.execute("UPDATE ir_model_data SET model='other.seed',res_id=42 WHERE module='ab_accounting' AND name='liability'")
            cr.execute("DELETE FROM other_seed WHERE id=42")
        self.con.commit()
        plan=self.plan()
        self.assertTrue(any(r['reason']=='xmlid_model_conflict' for r in plan['unresolved']))
        self.assertTrue(any(r['reason']=='target_destination_missing' for r in plan['unresolved']))
        self.assertEqual(len([c for c in plan['changes'] if c['group_model']=='ab_accounting_account_guide']),3)
        self.apply(plan)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE module='ab_accounting_base' AND name='liability'"),257)
        self.assertEqual(self.scalar("SELECT model FROM ir_model_data WHERE module='ab_accounting' AND name='liability'"),'other.seed')

    def test_model_transaction_failure_rolls_back_both_namespaces_and_continues(self):
        plan=self.plan()
        def fail_one(connection,changes):
            apply_data(connection,changes)
            if changes[0]['group_model']=='ab_accounting_account_guide':
                raise MigrationError('injected accounting group failure')
        with patch('database_repair.apply_data',side_effect=fail_one):
            result=self.apply(plan)
        self.assertTrue(any(r['operation']=='xmlids:ab_accounting_account_guide' and r['status']=='failed' for r in result))
        self.assertTrue(any(r['operation']=='xmlids:other.seed' and r['status']=='committed' for r in result))
        self.assertEqual(self.scalar("SELECT count(*) FROM ir_model_data WHERE name='liability' AND res_id=3"),2)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='new_seed'"),42)
        self.assertEqual(self.scalar("SELECT count(*) FROM database_repairs.completed WHERE operation='xmlids:ab_accounting_account_guide'"),0)

    def test_changed_preview_rolls_back_only_its_model(self):
        plan=self.plan()
        with self.con.cursor() as cr:
            cr.execute("UPDATE ir_model_data SET res_id=1 WHERE module='ab_accounting' AND name='liability'")
        self.con.commit()
        result=self.apply(plan)
        self.assertTrue(any(r['operation']=='xmlids:ab_accounting_account_guide' and r['status']=='failed' for r in result))
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='new_seed'"),42)

    def test_archive_cycle_blocks_evidence_without_blocking_core_identities(self):
        self.current['previous_checkpoint']='state'
        self.save_current()
        plan=self.plan()
        self.assertTrue(any(r['reason']=='invalid_checkpoint_archive_chain' for r in plan['unresolved']))
        self.assertTrue(any(c['group_model']=='res.users' for c in plan['changes']))
        self.assertFalse(any(c['group_model']=='ab_accounting_account_guide' for c in plan['changes']))

    def test_model_table_override_uses_registry_free_discovery(self):
        for connection in (self.source,self.con):
            with connection.cursor() as cr:
                cr.execute("UPDATE ir_model SET model='custom.account.model' WHERE model='ab_accounting_account_guide'")
                cr.execute("UPDATE ir_model_data SET model='custom.account.model' WHERE model='ab_accounting_account_guide'")
            connection.commit()
        with patch('repair_xmlids.table_overrides',return_value={'custom.account.model':'ab_accounting_account_guide'}):
            self.assertEqual(len([c for c in self.plan()['changes'] if c['group_model']=='custom.account.model']),4)

    def test_id_checks_are_batched(self):
        with patch('repair_xmlids.BATCH',1):
            plan=self.plan()
        self.assertEqual(len([c for c in plan['changes'] if c['group_model']=='ab_accounting_account_guide']),4)

    def test_orphan_source_alias_is_reported_without_creating_a_record(self):
        with self.source.cursor() as cr:
            cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES('feature_x','orphan_source','other.seed',999,true)")
        self.source.commit()
        plan=self.plan()
        self.assertTrue(any(r['name']=='orphan_source' and r['reason']=='source_record_missing' for r in plan['unresolved']))
        self.apply(plan)
        self.assertEqual(self.scalar('SELECT count(*) FROM other_seed'),1)
        self.assertEqual(self.scalar("SELECT count(*) FROM ir_model_data WHERE name='orphan_source'"),0)

    def test_malformed_legacy_copy_receipt_is_not_evidence(self):
        self.legacy['operations']['ab_accounting_account_guide']['fingerprint']='invalid'
        with self.con.cursor() as cr:
            cr.execute("UPDATE csv_replication.checkpoint SET value=%s WHERE name='archive:old'",[json.dumps(self.legacy)])
        self.con.commit()
        self.assertFalse(any(c['group_model']=='ab_accounting_account_guide' for c in self.plan()['changes']))

    def test_malformed_checkpoint_does_not_block_verified_core_repairs(self):
        with self.con.cursor() as cr:
            cr.execute("UPDATE csv_replication.checkpoint SET value='invalid json' WHERE name='state'")
        self.con.commit()
        plan=self.plan()
        self.assertTrue(any(r['reason']=='malformed_checkpoint_json' for r in plan['unresolved']))
        self.assertTrue(any(c['group_model']=='res.users' for c in plan['changes']))
        self.assertFalse(any(c['group_model']=='ab_accounting_account_guide' for c in plan['changes']))


if __name__=='__main__':
    unittest.main()
