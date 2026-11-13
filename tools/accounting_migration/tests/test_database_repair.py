"""Repair regressions exclusively in generated disposable PostgreSQL databases."""
import contextlib
import io
import json
import os
import unittest
import uuid
from unittest.mock import patch

from psycopg2 import sql
from psycopg2.extras import Json
import test_prepared_postgres as fixtures
from common import MigrationError, connect
from repair_audit import audit, audit_fk, constraints, rows
from repair_fixes import plan_fixes, apply_data, payments, reports, discuss, restore_fk
from database_repair import perform, validate_binding, run
from csv_plan import database_identity


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'), 'requires disposable PostgreSQL config')
class DatabaseRepairTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PreparedPostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.PreparedPostgresTests.tearDownClass.__func__)
    scalar = fixtures.PreparedPostgresTests.scalar

    def setUp(self):
        fixtures.PreparedPostgresTests.setUp(self)
        self.source_db = 'codex_migration_test_prepared_' + uuid.uuid4().hex[:12]
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.source_db)))
        self.source = connect(self.config, self.source_db, readonly=False)
        for connection, source in ((self.source, True), (self.con, False)):
            with connection.cursor() as cr:
                cr.execute('CREATE TABLE ir_module_module(name varchar PRIMARY KEY,state varchar)')
                cr.execute("INSERT INTO ir_module_module VALUES('base','installed')")
                cr.execute('CREATE TABLE ir_model(model varchar PRIMARY KEY,transient boolean DEFAULT false)')
                for model in ('res.users','res.partner','res.company','ir.model.fields','res.groups'):
                    cr.execute('INSERT INTO ir_model(model) VALUES(%s)',[model])
                cr.execute('CREATE TABLE res_partner(id serial PRIMARY KEY)')
                cr.execute('INSERT INTO res_partner(id) SELECT generate_series(1,6)')
                cr.execute('CREATE TABLE res_users(id integer PRIMARY KEY,login varchar UNIQUE,partner_id integer REFERENCES res_partner(id),active boolean)')
                cr.execute("INSERT INTO res_users VALUES (1,'__system__',2,false),(2,'admin',3,true),"
                           "(3,'default',5,false),(4,'public',4,false),(5,'portaltemplate',6,false)")
                cr.execute('CREATE TABLE res_company(id integer PRIMARY KEY,partner_id integer REFERENCES res_partner(id))')
                cr.execute('INSERT INTO res_company VALUES(1,1)')
                cr.execute('CREATE TABLE ir_model_data(id serial PRIMARY KEY,module varchar,name varchar,model varchar,res_id integer,noupdate boolean, UNIQUE(module,name))')
                for name, model, rid in [('user_root','res.users',1),('user_admin','res.users',2),
                                          ('default_user','res.users',3),('public_user','res.users',4),
                                          ('template_portal_user_id','res.users',5),('public_partner','res.partner',4),
                                          ('template_portal_user_id_res_partner','res.partner',6),('main_partner','res.partner',1)]:
                    if not source and name == 'default_user':
                        continue
                    actual = {'public_user': 3, 'template_portal_user_id': 4,
                              'template_portal_user_id_res_partner': 5}.get(name, rid) if not source else rid
                    cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES('base',%s,%s,%s,true)", [name,model,actual])
                cr.execute('CREATE TABLE ir_config_parameter(id serial PRIMARY KEY,key varchar UNIQUE,value varchar)')
                cr.execute("INSERT INTO ir_config_parameter(key,value) VALUES('base.template_portal_user_id','4')")
                cr.execute('CREATE TABLE res_groups_users_rel(uid integer,gid integer)')
                for rid,name in enumerate(('group_user','group_portal','group_public'),1):
                    cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES('base',%s,'res.groups',%s,true)",[name,rid])
                cr.execute('CREATE TABLE ab_hr_payment_type(id serial PRIMARY KEY,name ' + ('text' if source else 'jsonb') + ')')
                for rid, name in [(1,'Salary'),(2,'Payback'),(3,'Firing'),(4,'صندوق الزمالة')]:
                    if source or rid < 4:
                        cr.execute('INSERT INTO ab_hr_payment_type(id,name) VALUES(%s,%s)', [rid, name if source else Json(dict(en_US=name, ar_001='preserved'))])
                cr.execute('CREATE TABLE ir_model_fields(id integer PRIMARY KEY,model varchar,name varchar)')
                for rid,name in [(3389 if source else 9669,'action_date'),(3392 if source else 9672,'notes')]:
                    cr.execute("INSERT INTO ir_model_fields VALUES(%s,'ab_hr_emp_history',%s)", [rid,name])
                    cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES('ab_hr',%s,'ir.model.fields',%s,true)", ['field_' + name, rid])
                cr.execute('CREATE TABLE ab_hr_report_model(id integer PRIMARY KEY,target_field_id integer)')
                cr.execute('INSERT INTO ab_hr_report_model SELECT n,CASE WHEN n=1 THEN 3392 ELSE 3389 END FROM generate_series(1,13) n')
                cr.execute('CREATE TABLE ab_hr_payroll(id integer PRIMARY KEY,payment_type_id integer)')
                cr.execute('INSERT INTO ab_hr_payroll SELECT n,4 FROM generate_series(1,140) n')
                cr.execute('CREATE TABLE ab_hr_action_wizard(id integer PRIMARY KEY,payment_type_id integer,set_payment_type_id integer)')
                cr.execute('INSERT INTO ab_hr_action_wizard SELECT n,CASE WHEN n<=9 THEN 4 ELSE NULL END,4 FROM generate_series(1,183) n')
                cr.execute('CREATE TABLE discuss_channel_member(id integer PRIMARY KEY,channel_id integer,partner_id integer,custom_channel_name text)')
                cr.execute("INSERT INTO discuss_channel_member VALUES(1538,1,9429,'full before image'),(1539,1,4,'preserved')")
            connection.commit()
        self.saved = []
        for table, column, parent in [('ab_hr_payroll','payment_type_id','ab_hr_payment_type'),
                                      ('ab_hr_action_wizard','payment_type_id','ab_hr_payment_type'),
                                      ('ab_hr_action_wizard','set_payment_type_id','ab_hr_payment_type'),
                                      ('ab_hr_report_model','target_field_id','ir_model_fields'),
                                      ('discuss_channel_member','partner_id','res_partner')]:
            self.saved.append(dict(source_schema='public',source_table=table,name=table+'_'+column+'_fkey',
                                   referenced_schema='public',referenced_table=parent,
                                   definition=f'FOREIGN KEY ({column}) REFERENCES {parent}(id) ON DELETE SET NULL'))
        with self.con.cursor() as cr:
            cr.execute('CREATE SCHEMA csv_replication')
            cr.execute('CREATE TABLE csv_replication.checkpoint(name text PRIMARY KEY,value text)')
            cr.execute("INSERT INTO csv_replication.checkpoint VALUES('state',%s)", [json.dumps(dict(format=4,operations={},constraints=self.saved))])
        self.con.commit()

    def tearDown(self):
        self.source.close()
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(self.source_db)))
        fixtures.PreparedPostgresTests.tearDown(self)

    def preview(self):
        checked = audit(self.con)
        return checked, plan_fixes(self.source, self.con, checked)

    def test_all_repairs_restore_five_constraints_and_repeat_without_changes(self):
        before, fixes = self.preview()
        with self.con.cursor() as cr:
            cr.execute('SAVEPOINT upgrade_conflict')
            with self.assertRaises(Exception) as error:
                cr.execute("UPDATE res_users SET login='portaltemplate' WHERE id=(SELECT res_id FROM ir_model_data "
                           "WHERE module='base' AND name='template_portal_user_id')")
            self.assertEqual(error.exception.pgcode,'23505')
            cr.execute('ROLLBACK TO SAVEPOINT upgrade_conflict')
        self.assertEqual(sorted(i['orphan_rows'] for i in before['constraints'] if i['missing']), [1,9,13,140,183])
        self.assertFalse(any('error' in f for f in fixes.values()), fixes)
        self.con.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            result = perform(self.con, self.source, self.stage, list(fixes), fixes, {})
        self.assertTrue(all(r['status']=='committed' for r in result),result)
        after, fixes = self.preview()
        self.assertTrue(after['complete'])
        self.assertTrue(all(not i['missing'] and i['orphan_rows']==0 for i in after['constraints']))
        self.assertTrue(all(f['changes']==[] for f in fixes.values()),fixes)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='template_portal_user_id'"),5)
        self.assertEqual(self.scalar("SELECT value FROM ir_config_parameter WHERE key='base.template_portal_user_id'"),'5')
        self.assertTrue(self.scalar("SELECT noupdate FROM ir_model_data WHERE name='template_portal_user_id'"))
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_hr_payroll'),140)
        self.assertEqual(self.scalar("SELECT name->>'ar_001' FROM ab_hr_payment_type WHERE id=1"),'preserved')
        self.assertEqual(self.scalar('SELECT count(*) FROM discuss_channel_member'),1)
        with self.con.cursor() as cr:
            cr.execute("UPDATE res_users SET login='portaltemplate' WHERE id=(SELECT res_id FROM ir_model_data "
                       "WHERE module='base' AND name='template_portal_user_id')")
            self.assertEqual(cr.rowcount,1)
        self.assertEqual(self.scalar("SELECT count(*) FROM database_repairs.completed WHERE record::text LIKE '%full before image%'"),1)
        with self.con.cursor() as cr:
            cr.execute("INSERT INTO ab_hr_payment_type(name) VALUES ('{}') RETURNING id")
            self.assertGreater(cr.fetchone()[0],4)

    def test_full_workflow_creates_backup_audits_receipts_and_reopens_target(self):
        identities=dict(source=database_identity(self.source,self.config),target=database_identity(self.con,self.config))
        values=dict(source_config=self.config,target_config=self.config,source_db=self.source_db,
                    target_db=self.database,csv_path='bound-test-plan.csv')
        self.con.close()
        try:
            with patch('database_repair.read_plan',return_value=({'identities':identities},{})), \
                    patch('builtins.input',side_effect=['a','y']),contextlib.redirect_stdout(io.StringIO()):
                result=run(values,self.stage,backup=True)
        finally:
            self.con=connect(self.config,self.database,readonly=False)
        self.assertEqual(result['status'],'complete',result)
        from pathlib import Path
        stage=Path(result['reports'])
        self.assertTrue((stage/'before_import.dump').is_file())
        self.assertTrue((stage/'preview.json').is_file())
        self.assertTrue((stage/'after.json').is_file())
        self.assertFalse(json.loads((stage/'availability.json').read_text())['offline'])
        self.assertGreater(self.scalar('SELECT count(*) FROM database_repairs.completed'),0)

    def test_cancelled_workflow_creates_no_backup_or_database_changes(self):
        identities=dict(source=database_identity(self.source,self.config),target=database_identity(self.con,self.config))
        values=dict(source_config=self.config,target_config=self.config,source_db=self.source_db,
                    target_db=self.database,csv_path='bound-test-plan.csv')
        with patch('database_repair.read_plan',return_value=({'identities':identities},{})), \
                patch('builtins.input',side_effect=['a','n']),contextlib.redirect_stdout(io.StringIO()):
            result=run(values,self.stage,backup=True)
        self.assertEqual(result['status'],'cancelled')
        self.assertEqual(list(self.stage.rglob('before_import.dump')),[])
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_hr_payment_type'),3)
        self.assertIsNone(self.scalar("SELECT to_regnamespace('database_repairs')"))

    def test_explicit_skip_repairs_without_any_backup_or_verification(self):
        identities=dict(source=database_identity(self.source,self.config),target=database_identity(self.con,self.config))
        values=dict(source_config=self.config,target_config=self.config,source_db=self.source_db,
                    target_db=self.database,csv_path='bound-test-plan.csv')
        self.con.close()
        try:
            with patch('database_repair.read_plan',return_value=({'identities':identities},{})), \
                    patch('sys.stdin.isatty',return_value=True),patch('builtins.input',side_effect=['a','2','y']), \
                    patch('database_repair.ensure_backup',side_effect=AssertionError('backup')), \
                    patch('backup_policy.digest',side_effect=AssertionError('checksum')), \
                    patch('backup_policy.subprocess.run',side_effect=AssertionError('archive')), \
                    contextlib.redirect_stdout(io.StringIO()):
                result=run(values,self.stage)
        finally:
            self.con=connect(self.config,self.database,readonly=False)
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual(result['backup']['status'],'skipped')
        self.assertEqual(list(self.stage.rglob('before_import.dump')),[])
        self.assertEqual(list(self.stage.rglob('backup.json')),[])
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_hr_payment_type'),4)

    def test_requested_backup_failure_stops_before_repairs_or_offline(self):
        identities=dict(source=database_identity(self.source,self.config),target=database_identity(self.con,self.config))
        values=dict(source_config=self.config,target_config=self.config,source_db=self.source_db,
                    target_db=self.database,csv_path='bound-test-plan.csv')
        with patch('database_repair.read_plan',return_value=({'identities':identities},{})), \
                patch('builtins.input',side_effect=['a','y']), \
                patch('database_repair.ensure_backup',side_effect=MigrationError('fixture backup failure')), \
                patch('database_repair.target_offline') as offline,contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(MigrationError,'fixture backup failure'):
            run(values,self.stage,backup=True)
        offline.assert_not_called()
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_hr_payment_type'),3)
        self.assertIsNone(self.scalar("SELECT to_regnamespace('database_repairs')"))

    def test_interruption_rolls_back_and_reopens_target(self):
        self.assert_interruption_recovery(backup=True)

    def test_interruption_without_backup_rolls_back_and_reopens_target(self):
        self.assert_interruption_recovery(backup=False)

    def assert_interruption_recovery(self,backup):
        identities=dict(source=database_identity(self.source,self.config),target=database_identity(self.con,self.config))
        values=dict(source_config=self.config,target_config=self.config,source_db=self.source_db,
                    target_db=self.database,csv_path='bound-test-plan.csv')
        self.con.close()
        def interrupt(connection,changes):
            apply_data(connection,changes)
            raise KeyboardInterrupt()
        try:
            with patch('database_repair.read_plan',return_value=({'identities':identities},{})), \
                    patch('builtins.input',side_effect=['2','y']),patch('database_repair.apply_data',side_effect=interrupt), \
                    contextlib.redirect_stdout(io.StringIO()),self.assertRaises(KeyboardInterrupt):
                run(values,self.stage,backup=backup)
        finally:
            self.con=connect(self.config,self.database,readonly=False)
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_hr_payment_type'),3)
        failure=json.loads(next(self.stage.rglob('failure.json')).read_text())
        self.assertEqual(failure['status'],'interrupted')
        self.assertFalse(json.loads(next(self.stage.rglob('availability.json')).read_text())['offline'])

    def test_failed_repair_rolls_back_data_and_receipt_then_retries(self):
        before,fixes=self.preview()
        self.con.rollback()
        def fail(connection, changes):
            apply_data(connection, changes)
            raise MigrationError('injected failure')
        with patch('database_repair.apply_data',side_effect=fail),contextlib.redirect_stdout(io.StringIO()):
            result=perform(self.con,self.source,self.stage,['payments'],fixes,{})
        self.assertEqual(result[0]['status'],'failed')
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_hr_payment_type'),3)
        self.assertEqual(self.scalar('SELECT count(*) FROM database_repairs.completed'),0)
        self.con.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            result=perform(self.con,self.source,self.stage,['payments'],fixes,{})
        self.assertEqual(result[0]['status'],'committed')

    def test_changed_preview_and_alias_conflicts_are_rejected(self):
        before,fixes=self.preview()
        with self.con.cursor() as cr:
            cr.execute('UPDATE ab_hr_report_model SET target_field_id=NULL WHERE id=1')
        self.con.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            result=perform(self.con,self.source,self.stage,['reports'],fixes,{})
        self.assertEqual(result[0]['status'],'failed')
        self.assertIsNone(self.scalar('SELECT target_field_id FROM ab_hr_report_model WHERE id=1'))
        with self.con.cursor() as cr:
            cr.execute("UPDATE ir_model_data SET model='res.partner' WHERE name='template_portal_user_id'")
        _,fixes=self.preview()
        self.assertTrue(any(i['reason']=='xmlid_model_conflict' for i in fixes['identities']['unresolved']))

    def test_missing_or_wrong_shared_field_mapping_is_blocked(self):
        with self.con.cursor() as cr:
            cr.execute("DELETE FROM ir_model_data WHERE name='field_action_date'")
        with self.assertRaisesRegex(MigrationError,'XML-ID'):
            reports(self.source,self.con)

    def test_orphan_removal_and_payment_identity_guards(self):
        with self.con.cursor() as cr:
            cr.execute('INSERT INTO res_partner(id) VALUES(9429)')
        with self.assertRaisesRegex(MigrationError,'now exists'):
            discuss(self.source,self.con)
        with self.con.cursor() as cr:
            cr.execute("UPDATE ab_hr_payment_type SET name='null' WHERE id=1")
        with self.assertRaisesRegex(MigrationError,'conflicting name'):
            payments(self.source,self.con)

    def test_discuss_incoming_cascade_never_changes_another_record(self):
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE rtc(id integer PRIMARY KEY,member_id integer REFERENCES discuss_channel_member(id) ON DELETE CASCADE)')
        self.assertEqual(len(discuss(self.source,self.con)),1)
        with self.con.cursor() as cr:
            cr.execute('INSERT INTO rtc VALUES(1,1538)')
        with self.assertRaisesRegex(MigrationError,'cascading changes'):
            discuss(self.source,self.con)
        self.assertEqual(self.scalar('SELECT count(*) FROM rtc'),1)

    def test_fk_restore_refuses_orphans_and_definition_changes(self):
        with self.assertRaisesRegex(MigrationError,'orphan'):
            restore_fk(self.con,self.saved[0])
        with self.assertRaisesRegex(MigrationError,'changed'):
            restore_fk(self.con,dict(self.saved[0],definition=self.saved[0]['definition'].replace('SET NULL','CASCADE')))

    def test_composite_match_full_counts_partial_nulls(self):
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE parent(a integer,b integer,PRIMARY KEY(a,b))')
            cr.execute('CREATE TABLE child(a integer,b integer)')
            cr.execute('INSERT INTO parent VALUES(1,2)')
            cr.execute('INSERT INTO child VALUES(1,2),(NULL,NULL),(1,NULL),(9,9)')
        item=dict(source_schema='public',source_table='child',referenced_schema='public',referenced_table='parent',
                  columns=['a','b'],parent_columns=['a','b'],match='f')
        self.assertEqual(audit_fk(self.con,item)['orphan_rows'],2)
        self.assertEqual(audit_fk(self.con,dict(item,match='s'))['orphan_rows'],1)

    def test_timeout_is_incomplete_and_transaction_recovers(self):
        original=audit_fk
        def slow(connection,item):
            with connection.cursor() as cr:
                cr.execute('SELECT pg_sleep(0.02)')
            return original(connection,item)
        with patch('repair_audit.audit_fk',side_effect=slow):
            result=audit(self.con,timeout_ms=1)
        self.assertFalse(result['complete'])
        self.assertTrue(all(i['error_type']=='QueryCanceled' for i in result['constraints']))
        self.assertEqual(self.scalar('SELECT 1'),1)


if __name__=='__main__':
    unittest.main()
