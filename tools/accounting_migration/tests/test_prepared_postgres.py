"""Opt-in real PostgreSQL tests, exclusively in generated disposable databases.

MIGRATION_PREPARED_TEST_CONFIG supplies maintenance credentials with CREATEDB.
The configured application DB is never opened; only postgres and generated
codex_migration_test_prepared_* databases are used. No existing DB is dropped.
"""
import contextlib
import copy
import configparser
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from psycopg2 import sql
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import connect,MigrationError,loads,save_json
from availability import DatabaseGate,target_offline
from prepared_importer import PreparedImporter,META,WORK
from prepared import initialize,identity_checkpoint,write_checkpoint,read_checkpoint
from prepared_snapshot import SCHEMA


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG'),'requires disposable-database maintenance config')
class PreparedPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config=os.environ['MIGRATION_PREPARED_TEST_CONFIG']
        cls.admin=connect(cls.config,'postgres',readonly=False)
        cls.admin.autocommit=True

    @classmethod
    def tearDownClass(cls):
        cls.admin.close()

    def setUp(self):
        self.database='codex_migration_test_prepared_'+uuid.uuid4().hex[:12]
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(self.database)))
        self.con=connect(self.config,self.database,readonly=False)
        self.temp=tempfile.TemporaryDirectory()
        self.stage=Path(self.temp.name)

    def tearDown(self):
        self.con.close()
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(self.database)))
            cr.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s "
                       "AND usename=current_user AND backend_type='client backend'",[self.database])
            cr.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(self.database)))
        self.temp.cleanup()

    def scalar(self,query):
        with self.con.cursor() as cr:
            cr.execute(query)
            return cr.fetchone()[0]

    def fixture(self):
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE ab_group(id integer PRIMARY KEY,name varchar NOT NULL)')
            cr.execute('CREATE TABLE res_currency(id integer PRIMARY KEY,name varchar UNIQUE)')
            cr.execute('CREATE TABLE res_partner(id integer PRIMARY KEY)')
            cr.execute('CREATE TABLE res_users(id integer PRIMARY KEY,accounting_auth_group_id integer REFERENCES ab_group(id) ON DELETE SET NULL)')
            cr.execute('CREATE TABLE ab_record(id integer PRIMARY KEY,name varchar NOT NULL,group_id integer REFERENCES ab_group(id),'
                       'currency_id integer REFERENCES res_currency(id),attachment_id integer,create_uid integer REFERENCES res_users(id))')
            cr.execute('CREATE TABLE ab_target_only(id integer PRIMARY KEY,group_id integer REFERENCES ab_group(id))')
            cr.execute('CREATE TABLE user_group_link(user_id integer REFERENCES res_users(id),group_id integer REFERENCES ab_group(id) ON DELETE CASCADE,PRIMARY KEY(user_id,group_id))')
            cr.execute('CREATE TABLE ir_model(id integer PRIMARY KEY,model varchar)')
            cr.execute('CREATE TABLE ir_model_fields(id integer PRIMARY KEY,model varchar,name varchar,ttype varchar,relation varchar)')
            cr.execute('CREATE TABLE ir_model_data(id serial PRIMARY KEY,module varchar,name varchar,model varchar,res_id integer,noupdate boolean,UNIQUE(module,name))')
            cr.execute('CREATE TABLE ir_attachment(id serial PRIMARY KEY,name varchar NOT NULL,type varchar,res_model varchar,res_id integer,'
                       'store_fname varchar,checksum varchar,file_size integer,db_datas bytea,create_uid integer REFERENCES res_users(id))')
            cr.execute('CREATE TABLE ab_record_user_rel(record_id integer REFERENCES ab_record(id) ON DELETE CASCADE,user_id integer REFERENCES res_users(id),PRIMARY KEY(record_id,user_id))')
            cr.execute('CREATE TABLE ab_record_att_rel(record_id integer REFERENCES ab_record(id) ON DELETE CASCADE,attachment_id integer REFERENCES ir_attachment(id),PRIMARY KEY(record_id,attachment_id))')
            cr.execute("INSERT INTO ab_group VALUES (7,'old group')")
            cr.execute("INSERT INTO res_currency VALUES (900,'EGP')")
            cr.execute('INSERT INTO res_users VALUES(1,7),(999,NULL)')
            cr.execute('INSERT INTO res_partner VALUES(1),(999)')
            cr.execute("INSERT INTO ab_record VALUES(9,'old record',7,900,NULL,1)")
            cr.execute('INSERT INTO ab_target_only VALUES(80,7)')
            cr.execute('INSERT INTO user_group_link VALUES(1,7)')
            cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES "
                       "('custom','group','ab_group',7,false),('custom','record','ab_record',9,false),"
                       "('base','EGP','res.currency',900,false),('unrelated','record','ab_target_only',80,false)")
            cr.execute("INSERT INTO ir_attachment(name,type,res_model,res_id) VALUES('existing','binary','ab_record',9)")
            cr.execute('INSERT INTO ab_record_user_rel VALUES(9,1)')
            cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
            for table in ('ab_group','ab_record','res_users','res_partner','ir_model','ir_model_fields','ir_model_data','ir_attachment','ab_record_user_rel','ab_record_att_rel','res_currency'):
                cr.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM public.{} WITH NO DATA').format(sql.Identifier(SCHEMA,table),sql.Identifier(table)))
            cr.execute(sql.SQL("INSERT INTO {} VALUES(13,'source group')").format(sql.Identifier(SCHEMA,'ab_group')))
            cr.execute(sql.SQL("INSERT INTO {} VALUES(42,'source record',13,4,1,1)").format(sql.Identifier(SCHEMA,'ab_record')))
            cr.execute(sql.SQL('INSERT INTO {}(id) VALUES(1)').format(sql.Identifier(SCHEMA,'res_users')))
            cr.execute(sql.SQL('INSERT INTO {} VALUES(1)').format(sql.Identifier(SCHEMA,'res_partner')))
            cr.execute(sql.SQL("INSERT INTO {} VALUES(4,'EGP')").format(sql.Identifier(SCHEMA,'res_currency')))
            cr.execute(sql.SQL("INSERT INTO {}(module,name,model,res_id,noupdate) VALUES "
                "('custom','group','ab_group',13,false),('custom','record','ab_record',42,false),"
                "('custom','new_alias','ab_record',42,false),('base','EGP','res.currency',4,false)").format(sql.Identifier(SCHEMA,'ir_model_data')))
            self.source_files=self.stage/'source-filestore'
            self.target_files=self.stage/'target-filestore'
            content=b'old attachment file'
            checksum=hashlib.sha1(content).hexdigest()
            (self.source_files/'aa').mkdir(parents=True)
            (self.source_files/'aa'/checksum).write_bytes(content)
            cr.execute(sql.SQL('INSERT INTO {}(id,name,type,res_model,res_id,store_fname,checksum,file_size,create_uid) '
                "VALUES(1,'present','binary','ab_record',42,%s,%s,%s,1),(2,'missing','binary','ab_record',42,'bb/missing',NULL,12,1)").format(
                    sql.Identifier(SCHEMA,'ir_attachment')),['aa/'+checksum,checksum,len(content)])
            cr.execute(sql.SQL('INSERT INTO {} VALUES(42,1)').format(sql.Identifier(SCHEMA,'ab_record_user_rel')))
            cr.execute(sql.SQL('INSERT INTO {} VALUES(42,1),(42,2)').format(sql.Identifier(SCHEMA,'ab_record_att_rel')))
            cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(WORK)))
        initialize(self.con,{'fixture':True})
        def field(typ,related=None):
            return dict(type=typ,ttype=typ,store=True,relation=related,required=False)
        group={'id':field('integer'),'name':field('char')}
        record={'id':field('integer'),'name':field('char'),'group_id':field('many2one','ab_group'),
            'currency_id':field('many2one','res.currency'),'attachment_id':field('many2one','ir.attachment'),
            'create_uid':field('many2one','res.users')}
        target={'ab_group':dict(table='ab_group',fields=group),'ab_record':dict(table='ab_record',fields=record),
            'res.users':dict(table='res_users',fields={'accounting_auth_group_id':field('many2one','ab_group'),
                'ab_groups':dict(type='many2many',relation='ab_group',relation_table='user_group_link',column1='user_id',column2='group_id')}),
            'res.partner':dict(table='res_partner',fields={}),
            'res.currency':dict(table='res_currency',fields={'name':field('char')}),
            'ab_target_only':dict(table='ab_target_only',fields={'group_id':field('many2one','ab_group')}),
            'ir.attachment':dict(table='ir_attachment',fields={})}
        source_models={m:dict(table=v['table'],fields=v['fields']) for m,v in target.items()}
        relations=[]
        for fieldname,table,column2,related in [('users','ab_record_user_rel','user_id','res.users'),('attachments','ab_record_att_rel','attachment_id','ir.attachment')]:
            target['ab_record']['fields'][fieldname]=dict(type='many2many',relation=related,relation_table=table,column1='record_id',column2=column2)
            relations.append(dict(model='ab_record',field=fieldname,related=related,table=table,column1='record_id',column2=column2))
        from bulk import catalog
        physical=catalog(self.con)
        manifest=dict(selected=['ab_group','ab_record'],omitted=['ab_missing'],models=source_models,relations=relations,tables={},activities=0)
        for table in ('ab_group','ab_record','ir_model_data','ir_model_fields','ir_model','res_currency','ir_attachment'):
            with self.con.cursor() as cr:
                cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(SCHEMA,table)))
                manifest['tables'][table]=dict(columns=physical[table],rows=cr.fetchone()[0])
        rules=dict(stable_keys={'res.currency':'name'},external_ids={},incoming_ids={},ignore_fields={})
        self.con.commit()
        self.arguments=(self.con,self.stage,manifest,target,rules,{})
        return PreparedImporter(*self.arguments)

    def test_full_copy_external_attachment_pipeline_preserves_references(self):
        engine=self.fixture()
        engine.validate_ids()  # IDs 999 in target are allowed.
        engine.preflight()
        engine.replace()
        write_checkpoint(self.con,'custom',{'complete':True})
        self.con.commit()
        self.assertEqual(self.scalar('SELECT accounting_auth_group_id FROM res_users WHERE id=1'),13)
        self.assertEqual(self.scalar('SELECT group_id FROM ab_target_only WHERE id=80'),13)
        self.assertEqual(self.scalar('SELECT group_id FROM user_group_link WHERE user_id=1'),13)
        self.assertEqual(self.scalar('SELECT res_id FROM ir_attachment WHERE id=1'),42)
        self.assertIsNone(self.scalar('SELECT currency_id FROM ab_record WHERE id=42'))
        self.assertFalse(self.scalar("SELECT noupdate FROM ir_model_data WHERE module='custom' AND name='group'"))
        self.assertTrue(self.scalar("SELECT noupdate FROM ir_model_data WHERE module='custom' AND name='new_alias'"))
        baseline=engine.fingerprints()
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.verify_fingerprints(baseline)
        engine.external()
        self.con.commit()
        self.assertEqual(self.scalar('SELECT currency_id FROM ab_record WHERE id=42'),900)
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.attachments(self.source_files,self.target_files)
        self.con.commit()
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)
        self.assertNotEqual(self.scalar('SELECT attachment_id FROM ab_record WHERE id=42'),1)
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_record_att_rel'),2)
        self.assertEqual(self.scalar("SELECT count(*) FROM ir_attachment WHERE store_fname='bb/missing'"),1)
        self.assertEqual(len(loads((self.stage/'attachments.json').read_text())['missing_files']),1)
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.validate_values()
        self.con.rollback()

    def test_failure_rolls_back_delete_copy_xmlids_and_reference_updates(self):
        engine=self.fixture()
        engine.preflight()
        with patch.object(engine,'repair_xmlids',side_effect=MigrationError('injected failure')):
            with self.assertRaises(MigrationError):
                engine.replace()
        self.con.rollback()
        self.assertEqual(self.scalar('SELECT id FROM ab_group'),7)
        self.assertEqual(self.scalar('SELECT accounting_auth_group_id FROM res_users WHERE id=1'),7)
        self.assertEqual(self.scalar('SELECT group_id FROM user_group_link'),7)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE module='custom' AND name='group'"),7)
        self.assertIsNone(read_checkpoint(self.con,'custom'))

    def test_incoming_scalar_capture_does_not_duplicate_target_credentials(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE res_users ADD password varchar')
            cr.execute("UPDATE res_users SET password='fixture secret' WHERE id=1")
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight()
        engine.replace()
        self.assertEqual(self.scalar('SELECT password FROM res_users WHERE id=1'),'fixture secret')
        self.assertEqual(self.scalar("SELECT count(*) FROM information_schema.columns WHERE table_schema='prepared_migration_work' "
                                    "AND table_name LIKE 'incoming_%' AND column_name='password'"),0)
        self.con.rollback()

    def test_missing_source_ids_and_required_deferred_fields_stop(self):
        engine=self.fixture()
        with self.con.cursor() as cr:
            cr.execute(sql.SQL('INSERT INTO {}(id) VALUES(123)').format(sql.Identifier(SCHEMA,'res_partner')))
        with self.assertRaisesRegex(MigrationError,'IDs.*missing'):
            engine.validate_ids()
        self.con.rollback()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_record ALTER COLUMN currency_id SET NOT NULL')
        engine=PreparedImporter(*self.arguments)
        with self.assertRaisesRegex(MigrationError,'cannot be deferred'):
            engine.preflight()
        self.con.rollback()
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),9)

    def test_online_edit_is_detected_before_next_checkpoint(self):
        engine=self.fixture()
        engine.preflight()
        engine.replace()
        baseline=engine.fingerprints()
        self.con.commit()
        with self.con.cursor() as cr:
            cr.execute("UPDATE ab_record SET name='online edit' WHERE id=42")
        self.con.commit()
        with self.assertRaisesRegex(MigrationError,'changed between checkpoints'):
            engine.verify_fingerprints(baseline)

    def test_shared_standard_relation_cannot_erase_extra_target_user_links(self):
        engine=self.fixture()
        self.arguments[3]['res.users']['fields']['records']=dict(type='many2many',relation='ab_record',
            relation_table='ab_record_user_rel',column1='user_id',column2='record_id')
        with self.con.cursor() as cr:
            cr.execute('INSERT INTO ab_record_user_rel VALUES(9,999)')
        engine=PreparedImporter(*self.arguments)
        with self.assertRaisesRegex(MigrationError,'erase prepared'):
            engine.preflight()
        self.con.rollback()
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),9)

    def test_arabic_translation_and_required_null_are_preserved(self):
        engine=self.fixture()
        with self.con.cursor() as cr:
            cr.execute("ALTER TABLE ab_group ALTER COLUMN name TYPE jsonb USING jsonb_build_object('en_US',name)")
            cr.execute(sql.SQL('CREATE TABLE {}(id integer,type varchar,name varchar,lang varchar,res_id integer,value varchar)').format(
                sql.Identifier(SCHEMA,'ir_translation')))
            cr.execute(sql.SQL("INSERT INTO {} VALUES(1,'model','ab_group,name','ar_001',13,%s)").format(
                sql.Identifier(SCHEMA,'ir_translation')),['مجموعة'])
        self.arguments[2]['tables']['ir_translation']={'rows':1}
        self.arguments[3]['ab_group']['fields']['name']['translate']=True
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight()
        engine.replace()
        self.con.commit()
        self.assertEqual(self.scalar('SELECT name FROM ab_group'),{'en_US':'source group','ar_001':'مجموعة'})
        with self.con.cursor() as cr:
            cr.execute(sql.SQL('UPDATE {} SET name=NULL').format(sql.Identifier(SCHEMA,'ab_group')))
        engine=PreparedImporter(*self.arguments)
        with self.assertRaisesRegex(MigrationError,'Invalid required value'):
            engine.preflight(replacing=False)
        self.con.rollback()

    def test_company_dependent_defaults_use_mapped_company_keys(self):
        engine=self.fixture()
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE res_company(id integer PRIMARY KEY)')
            cr.execute('INSERT INTO res_company VALUES(800)')
            cr.execute(sql.SQL('CREATE TABLE {}(id integer)').format(sql.Identifier(SCHEMA,'res_company')))
            cr.execute(sql.SQL('INSERT INTO {} VALUES(2)').format(sql.Identifier(SCHEMA,'res_company')))
            cr.execute('ALTER TABLE ab_record ADD company_amount jsonb')
            cr.execute("INSERT INTO ir_model_fields VALUES(500,'ab_record','company_amount','float',NULL)")
            cr.execute(sql.SQL("INSERT INTO {} VALUES(50,'ab_record','company_amount','float',NULL)").format(sql.Identifier(SCHEMA,'ir_model_fields')))
            cr.execute(sql.SQL('CREATE TABLE {}(id integer,fields_id integer,company_id integer,res_id varchar,value_float double precision)').format(
                sql.Identifier(SCHEMA,'ir_property')))
            cr.execute(sql.SQL("INSERT INTO {} VALUES(1,50,2,NULL,5),(2,50,2,'ab_record,42',7.5)").format(sql.Identifier(SCHEMA,'ir_property')))
            cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES('base','main_company','res.company',800,true)")
            cr.execute(sql.SQL("INSERT INTO {}(module,name,model,res_id,noupdate) VALUES('base','main_company','res.company',2,true)").format(
                sql.Identifier(SCHEMA,'ir_model_data')))
        self.arguments[2]['tables']['ir_property']={'rows':2}
        self.arguments[2]['tables']['res_company']={'rows':1}
        self.arguments[3]['ab_record']['fields']['company_amount']=dict(type='float',store=True,company_dependent=True)
        self.arguments[3]['res.company']=dict(table='res_company',fields={})
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight()
        engine.replace()
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.external()
        self.assertEqual(self.scalar('SELECT company_amount FROM ab_record'),{'800':7.5})
        self.con.rollback()

    def test_reviewed_field_and_selection_aliases_map_technical_field_ids(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute(sql.SQL('ALTER TABLE {} RENAME COLUMN name TO legacy_name').format(sql.Identifier(SCHEMA,'ab_group')))
            cr.execute('ALTER TABLE ab_record ADD status varchar, ADD field_id integer REFERENCES ir_model_fields(id)')
            cr.execute(sql.SQL('ALTER TABLE {} ADD status varchar, ADD field_id integer').format(sql.Identifier(SCHEMA,'ab_record')))
            cr.execute(sql.SQL("UPDATE {} SET status='old',field_id=11").format(sql.Identifier(SCHEMA,'ab_record')))
            cr.execute("INSERT INTO ir_model_fields VALUES(111,'ab_group','name','char',NULL)")
            cr.execute(sql.SQL("INSERT INTO {} VALUES(11,'ab_group','legacy_name','char',NULL)").format(sql.Identifier(SCHEMA,'ir_model_fields')))
        manifest,target=self.arguments[2:4]
        fields=copy.deepcopy(manifest['models']['ab_group']['fields'])
        fields['legacy_name']=fields.pop('name')
        manifest['models']['ab_group']['fields']=fields
        columns=manifest['tables']['ab_group']['columns']
        columns['legacy_name']=columns.pop('name')
        for name in ('status','field_id'):
            manifest['tables']['ab_record']['columns'][name]=dict(type='character varying' if name=='status' else 'integer',required=False,default=None)
        target['ab_record']['fields'].update(status=dict(type='selection',ttype='selection',selection=['new'],store=True),
            field_id=dict(type='many2one',ttype='many2one',relation='ir.model.fields',store=True))
        target['ir.model.fields']=dict(table='ir_model_fields',fields={})
        self.arguments[5].update(fields={'ab_group':{'legacy_name':'name'}},selections={'ab_record':{'status':{'old':'new'}}})
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight()
        engine.replace()
        engine.external()
        self.assertEqual(self.scalar('SELECT status FROM ab_record'),'new')
        self.assertEqual(self.scalar('SELECT field_id FROM ab_record'),111)
        self.assertEqual(self.scalar('SELECT name FROM ab_group'),'source group')
        self.con.rollback()

    def test_attachment_file_publication_survives_rollback_and_retry(self):
        engine=self.fixture()
        engine.preflight()
        engine.replace()
        engine.external()
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        with patch.object(engine,'load_relations',side_effect=MigrationError('late attachment failure')):
            with self.assertRaisesRegex(MigrationError,'late attachment failure'):
                engine.attachments(self.source_files,self.target_files)
        self.con.rollback()
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),1)
        self.assertEqual(len(list(self.target_files.rglob('*'))),2)  # Directory + published file.
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.attachments(self.source_files,self.target_files)
        self.con.commit()
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.validate_values()

    def test_target_is_reopened_on_exception(self):
        gate=DatabaseGate(self.config,self.database)
        try:
            with self.assertRaisesRegex(RuntimeError,'failure'):
                with target_offline(gate,self.con,self.stage):
                    self.assertFalse(gate.online())
                    raise RuntimeError('failure')
            self.assertTrue(gate.online())
        finally:
            gate.close()
        with self.admin.cursor() as cr:
            cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[self.database])
            self.assertTrue(cr.fetchone()[0])

    def test_both_identity_checks_skip_5_6_but_require_7(self):
        engine=self.fixture()
        ids={'res_users':[1,5],'res_partner':[1,6]}
        report=identity_checkpoint(self.con,ids,self.stage)
        self.assertEqual(report['report']['res_users']['skipped_count'],2)
        self.assertEqual(report['report']['res_partner']['checked_count'],0)
        engine.validate_ids()
        engine.preflight()
        engine.replace()
        self.assertEqual(self.scalar('SELECT create_uid FROM ab_record'),1)
        self.con.rollback()
        for table in ('res_users','res_partner'):
            with self.subTest(table=table):
                missing={k:[*v,7] if k==table else v for k,v in ids.items()}
                with self.assertRaisesRegex(MigrationError,'IDs >= 7 missing'):
                    identity_checkpoint(self.con,missing,self.stage)
                self.con.rollback()
                with self.con.cursor() as cr:
                    cr.execute(sql.SQL('INSERT INTO {}(id) VALUES(7)').format(sql.Identifier(SCHEMA,table)))
                with self.assertRaisesRegex(MigrationError,'IDs >= 7 missing'):
                    PreparedImporter(*self.arguments).validate_ids()
                self.con.rollback()

    def test_watchdog_recovers_after_controller_sigkill(self):
        # The worker and watchdog use only this generated disposable database.
        script="""
import sys,time
sys.path.insert(0,sys.argv[1])
from availability import DatabaseGate,target_offline
from common import connect
gate=DatabaseGate(sys.argv[2],sys.argv[3])
con=connect(sys.argv[2],sys.argv[3],readonly=False)
with target_offline(gate,con,sys.argv[4]):
 print('OFFLINE_READY',flush=True)
 time.sleep(30)
"""
        self.con.close()
        proc=subprocess.Popen([sys.executable,'-u','-c',script,str(Path(__file__).resolve().parents[1]),
            self.config,self.database,str(self.stage)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            import select
            self.assertTrue(select.select([proc.stdout],[],[],15)[0])
            self.assertEqual(proc.stdout.readline().strip(),'OFFLINE_READY')
            os.kill(proc.pid,signal.SIGKILL)
            proc.wait(timeout=5)
            online=False
            for _ in range(100):
                with self.admin.cursor() as cr:
                    cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[self.database])
                    online=cr.fetchone()[0]
                if online:
                    break
                time.sleep(.1)
            self.assertTrue(online,'watchdog did not reopen disposable target')
            self.con=connect(self.config,self.database,readonly=False)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()

    def test_controller_keeps_live_source_read_only_and_resumes_failed_run(self):
        engine=self.fixture()
        target=copy.deepcopy(engine.target)
        info=dict(source_version='15.0',models=copy.deepcopy(engine.models))
        source_db='codex_migration_test_prepared_'+uuid.uuid4().hex[:12]
        live_source=None
        # Only generated disposable DBs are created or dropped by this test.
        with self.admin.cursor() as cr:
            cr.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(source_db)))
        try:
            source=connect(self.config,source_db,readonly=False)
            with self.con.cursor() as cr:
                cr.execute('CREATE TABLE ir_module_module(name varchar,latest_version varchar)')
                cr.execute("INSERT INTO ir_module_module VALUES('base','19.0')")
                cr.execute('INSERT INTO res_users(id) VALUES(7)')
                cr.execute('INSERT INTO res_partner(id) VALUES(7)')
                cr.execute('SELECT tablename FROM pg_tables WHERE schemaname=%s',[SCHEMA])
                tables=[r[0] for r in cr]
                for table in tables:
                    cr.execute('SELECT column_name,data_type FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',[SCHEMA,table])
                    cols=cr.fetchall()
                    with source.cursor() as sc:
                        sc.execute(sql.SQL('CREATE TABLE public.{} ({})').format(sql.Identifier(table),sql.SQL(',').join(
                            sql.SQL('{} {}').format(sql.Identifier(n),sql.SQL(t)) for n,t in cols)))
                    import io
                    buf=io.BytesIO()
                    cr.copy_expert(sql.SQL('COPY {} TO STDOUT').format(sql.Identifier(SCHEMA,table)).as_string(self.con),buf)
                    buf.seek(0)
                    with source.cursor() as sc:
                        sc.copy_expert(sql.SQL('COPY public.{} FROM STDIN').format(sql.Identifier(table)).as_string(source),buf)
                cr.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(SCHEMA)))
                cr.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(WORK)))
                cr.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(META)))
            with source.cursor() as sc:
                sc.execute('CREATE TABLE ir_module_module(name varchar,latest_version varchar)')
                sc.execute("INSERT INTO ir_module_module VALUES('base','15.0')")
                sc.execute('CREATE TABLE mail_activity(id integer,res_model varchar)')
                sc.execute('INSERT INTO res_users(id) VALUES(5),(7)')
                sc.execute('INSERT INTO res_partner(id) VALUES(6),(7)')
                sc.execute('WITH numbered AS (SELECT ctid,row_number() OVER() n FROM ir_model_data) '
                           'UPDATE ir_model_data d SET id=n.n FROM numbered n WHERE d.ctid=n.ctid')
            source.commit()
            source.close()
            self.con.commit()
            self.con.close()  # Otherwise the controller correctly terminates this test connection.
            info['models']={m:v for m,v in info['models'].items() if v['table'] in tables}
            for m,v in info['models'].items():
                v.update(transient=False,table_kind='r')
                for f in v['fields'].values():
                    f['ttype']=f.get('type')
            from common import settings
            from types import SimpleNamespace
            from prepared import run,find_stage,source_database_oid,FORMAT,HERE
            from resume import endpoint,fingerprint
            configs=[]
            for side,database in [('source',source_db),('target',self.database)]:
                cfg=configparser.ConfigParser(interpolation=None)
                opts=settings(self.config)
                data=self.stage/(side+'-data')
                cfg['options']={k:v for k,v in opts.items() if k in ('db_host','db_port','db_user','db_password')}
                cfg['options']['data_dir']=str(data)
                file=self.stage/(side+'.conf')
                with open(file,'w') as out:
                    cfg.write(out)
                file.chmod(0o600)
                configs.append(str(file))
                if side=='source':
                    import shutil
                    shutil.copytree(self.source_files,data/'filestore'/database)
            args=SimpleNamespace(source_config=configs[0],source_db=source_db,target_config=configs[1],target_db=self.database)
            root=self.stage/'runs'
            rules=loads((HERE/'prepared_rules.json').read_text())
            conversions=loads((HERE/'mappings.json').read_text())
            identity=dict(format=FORMAT,source_db=source_db,target_db=self.database,
                source_endpoint=endpoint(configs[0]),target_endpoint=endpoint(configs[1]),
                source_oid=source_database_oid(configs[0],source_db),
                target_oid=source_database_oid(configs[1],self.database),rules=fingerprint([rules,conversions]))
            old_stage=find_stage(root,identity)
            save_json(old_stage/'source-ids.json',{'res_users':[1,5],'res_partner':[1,6]})
            save_json(old_stage/'id-validation.json',{'res_users':{'missing_ids':[5]},'res_partner':{'missing_ids':[6]}})
            save_json(old_stage/'source-availability.json',{'offline':True,'manual_reopen_required':True})
            old_availability=(old_stage/'source-availability.json').read_bytes()
            live_source=connect(configs[0],source_db,readonly=False)
            live_source.autocommit=True
            def schema(args,stage,smoke=False):
                return {'passed':True} if smoke else target
            answers=iter([True,True])
            source_updates=0
            def approve(summary):
                nonlocal source_updates
                with live_source.cursor() as cr:
                    if summary.startswith('Checkpoint 1:'):
                        source_updates+=1
                        cr.execute('UPDATE ab_group SET name=%s',[f'live update after snapshot {source_updates}'])
                    cr.execute('SELECT 1')
                    self.assertEqual(cr.fetchone()[0],1)
                return next(answers)
            def inventory(connection,*a,**kw):
                with connection.cursor() as cr:
                    cr.execute('SHOW transaction_read_only')
                    self.assertEqual(cr.fetchone()[0],'on')
                return info
            def guarded_connect(config,database,readonly=True):
                if config==configs[0]:
                    self.assertTrue(readonly)
                return connect(config,database,readonly=readonly)
            case=self
            class FakeSmoke:
                def __init__(self,args,stage):
                    self.connection=connect(args.target_config,args.target_db)
                    self.pid=self.connection.get_backend_pid()
                def run(self):
                    with live_source.cursor() as cr:
                        cr.execute('SELECT 1')
                        case.assertEqual(cr.fetchone()[0],1)
                    with case.admin.cursor() as cr:
                        cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[case.database])
                        case.assertFalse(cr.fetchone()[0])
                    return {'passed':True}
                def close(self):
                    self.connection.close()
            def lose_report(path,value):
                if Path(path).name=='custom_and_xmlids.json':
                    raise OSError('injected loss of post-commit report')
                return save_json(path,value)
            # First fail after checkpoint 1, before any extraction, with source still usable.
            with patch('prepared.metadata',side_effect=schema),patch('prepared.confirm',side_effect=approve), \
                    patch('prepared_snapshot.export',side_effect=MigrationError('injected extraction failure')), \
                    patch('prepared.connect',side_effect=guarded_connect):
                with self.assertRaisesRegex(MigrationError,'injected extraction failure'):
                    run(args,root)
            with live_source.cursor() as cr:
                cr.execute('INSERT INTO res_users(id) VALUES(8)')
                cr.execute('INSERT INTO res_partner(id) VALUES(8)')
            prep=connect(configs[1],self.database,readonly=False)
            with prep,prep.cursor() as cr:
                cr.execute('INSERT INTO res_users(id) VALUES(8)')
                cr.execute('INSERT INTO res_partner(id) VALUES(8)')
            prep.close()
            answers=iter([True,True])
            with patch('prepared.metadata',side_effect=schema),patch('prepared_snapshot.inventory',side_effect=inventory), \
                    patch('prepared.confirm',side_effect=approve),patch('prepared.save_json',side_effect=lose_report), \
                    patch('prepared.connect',side_effect=guarded_connect):
                with self.assertRaisesRegex(MigrationError,'OSError'):
                    run(args,root)
            # Database checkpoint is authoritative even when its JSON report was lost.
            self.assertFalse(any(root.glob('*/custom_and_xmlids.json')))
            self.assertEqual((old_stage/'source-availability.json').read_bytes(),old_availability)
            self.assertEqual(loads((old_stage/'source-ids.json').read_text())['res_users'],[1,5,7,8])
            self.assertTrue(list(old_stage.glob('source-ids-before-refresh-*.json')))
            with patch('prepared.metadata',side_effect=schema),patch('prepared.confirm',return_value=False), \
                    patch('prepared.connect',side_effect=guarded_connect) as connections:
                first=run(args,root)
            self.assertEqual(first['status'],'cancelled')
            self.assertFalse(any(c.args[1]==source_db for c in connections.call_args_list))
            with self.admin.cursor() as cr:
                cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[source_db])
                self.assertTrue(cr.fetchone()[0])
                cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[self.database])
                self.assertTrue(cr.fetchone()[0])
            with patch('prepared.metadata',side_effect=schema),patch('prepared.SmokeWorker',FakeSmoke), \
                    patch('prepared.confirm',side_effect=[True,True,True]):
                second=run(args,root)
            self.assertTrue(second['passed'])
            with patch('prepared.metadata',side_effect=schema),patch('prepared.confirm',side_effect=AssertionError('unexpected checkpoint replay')):
                third=run(args,root)
            self.assertTrue(third['passed'])
            with self.admin.cursor() as cr:
                cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[source_db])
                self.assertTrue(cr.fetchone()[0])
            self.con=connect(self.config,self.database,readonly=False)
            self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)
            self.assertEqual(self.scalar('SELECT currency_id FROM ab_record'),900)
            self.assertEqual(self.scalar('SELECT name FROM ab_group'),'live update after snapshot 1')
            with live_source.cursor() as cr:
                cr.execute('SELECT name FROM ab_group')
                self.assertEqual(cr.fetchone()[0],'live update after snapshot 2')
        finally:
            if live_source is not None:
                live_source.close()
            with self.admin.cursor() as cr:
                cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(source_db)))
                cr.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s "
                           "AND usename=current_user AND backend_type='client backend'",[source_db])
                cr.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(source_db)))


if __name__=='__main__':
    unittest.main()
