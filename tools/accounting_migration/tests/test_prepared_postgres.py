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
from types import SimpleNamespace
from unittest.mock import patch
from psycopg2 import sql
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import connect,MigrationError,loads,save_json
from availability import DatabaseGate,target_offline
from prepared_importer import PreparedImporter,META,WORK
from prepared import initialize,identity_checkpoint,write_checkpoint,read_checkpoint
from prepared_snapshot import SCHEMA
from reset_migration import reset,SCHEMAS
from resume import endpoint


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

    def reset_fixture(self):
        args=SimpleNamespace(source_db='unused_source',target_db=self.database,
                             source_config=self.config,target_config=self.config)
        with self.admin.cursor() as cr:
            cr.execute('SELECT oid FROM pg_database WHERE datname=%s',[self.database])
            oid=cr.fetchone()[0]
        identity=dict(source_db=args.source_db,target_db=args.target_db,target_oid=oid,
                      source_endpoint=endpoint(self.config),target_endpoint=endpoint(self.config),rules='old')
        initialize(self.con,identity)
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE public.preserved(id integer PRIMARY KEY)')
            cr.execute('INSERT INTO public.preserved VALUES(42)')
            cr.execute('CREATE SCHEMA prepared_migration_source')
            cr.execute('CREATE TABLE prepared_migration_source.res_users(id integer)')
        self.con.commit()
        directory=self.stage/'matching'
        directory.mkdir()
        save_json(directory/'prepared-run.json',identity)
        (directory/'backup.dump').write_bytes(b'backup')
        unrelated=self.stage/'unrelated'
        unrelated.mkdir()
        save_json(unrelated/'prepared-run.json',{**identity,'target_db':'other'})
        return args,directory,unrelated

    def test_reset_cancel_cleanup_retry_and_idempotency(self):
        args,directory,unrelated=self.reset_fixture()
        with patch('builtins.input',return_value='n'):
            self.assertFalse(reset(args,self.stage)['reset'])
        self.assertTrue(directory.exists())
        self.assertEqual(self.scalar('SELECT count(*) FROM prepared_custom_migration.checkpoint'),1)
        self.con.commit()
        with patch('builtins.input',return_value='y'),patch('reset_migration.shutil.rmtree',side_effect=OSError('test')):
            with self.assertRaisesRegex(MigrationError,'cleanup incomplete'):
                reset(args,self.stage)
        self.assertTrue(directory.exists())
        for schema in SCHEMAS:
            self.assertIsNone(self.scalar("SELECT to_regnamespace('"+schema+"')"))
        self.assertEqual(self.scalar('SELECT id FROM public.preserved'),42)
        self.con.commit()
        for _ in range(2):
            with patch('builtins.input',return_value='yes'):
                self.assertTrue(reset(args,self.stage)['reset'])
        self.assertFalse(directory.exists())
        self.assertTrue(unrelated.exists())

    def test_reset_refuses_active_lock_and_committed_import(self):
        args,directory,_=self.reset_fixture()
        gate=DatabaseGate(self.config,self.database)
        try:
            with patch('builtins.input') as prompt:
                with self.assertRaisesRegex(MigrationError,'Another migration'):
                    reset(args,self.stage)
                prompt.assert_not_called()
        finally:
            gate.close()
        write_checkpoint(self.con,'custom_and_xmlids',{})
        self.con.commit()
        with patch('builtins.input') as prompt:
            with self.assertRaisesRegex(MigrationError,'checkpoints'):
                reset(args,self.stage)
            prompt.assert_not_called()
        self.assertTrue(directory.exists())
        self.assertEqual(self.scalar('SELECT count(*) FROM prepared_custom_migration.checkpoint'),2)

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
            'ir.attachment':dict(table='ir_attachment',fields={
                n:field(t,'res.users' if n=='create_uid' else None) for n,t in (
                    ('id','integer'),('name','char'),('type','selection'),('res_model','char'),('res_id','integer'),
                    ('store_fname','char'),('checksum','char'),('file_size','integer'),('db_datas','binary'),('create_uid','many2one'))})}
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

    def run_table_workflow(self, engine):
        from table_checkpoints import TableMigration
        engine.validate_ids()
        engine.preflight()
        runner=TableMigration(engine,write_checkpoint)
        return runner.run(self.source_files,self.target_files)

    def test_table_checkpoints_copy_links_and_constraints(self):
        result=self.run_table_workflow(self.fixture())
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual(self.scalar('SELECT accounting_auth_group_id FROM res_users WHERE id=1'),13)
        self.assertEqual(self.scalar('SELECT group_id FROM user_group_link WHERE user_id=1'),13)
        self.assertEqual(self.scalar('SELECT currency_id FROM ab_record WHERE id=42'),900)
        self.assertEqual(self.scalar('SELECT res_id FROM ir_attachment WHERE id=1'),42)
        self.assertEqual(self.scalar('SELECT count(*) FROM ab_record_att_rel'),2)
        self.assertTrue(read_checkpoint(self.con,'table:copy:ab_record')['success'])
        self.assertTrue(read_checkpoint(self.con,'table_setup')['constraints'])
        self.assertEqual(read_checkpoint(self.con,'table_result')['status'],'complete')
        self.assertEqual(loads((self.stage/'failed_foreign_keys.json').read_text()),[])

    def test_table_failure_preserves_old_rows_and_continues(self):
        engine=self.fixture()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_record ADD CONSTRAINT record_limit CHECK(id<20)')
            cr.execute('CREATE TABLE ab_z(id integer PRIMARY KEY,name varchar NOT NULL)')
            cr.execute("INSERT INTO ab_z VALUES(1,'old')")
            cr.execute('CREATE TABLE prepared_migration_source.ab_z AS SELECT * FROM ab_z WITH NO DATA')
            cr.execute("INSERT INTO prepared_migration_source.ab_z VALUES(2,'new')")
        from bulk import catalog
        physical=catalog(self.con)
        engine.manifest['selected'].append('ab_z')
        engine.manifest['models']['ab_z']=dict(table='ab_z',fields=engine.target['ab_group']['fields'])
        engine.target['ab_z']=dict(table='ab_z',fields=engine.target['ab_group']['fields'])
        engine.manifest['tables']['ab_z']=dict(columns=physical['ab_z'],rows=1)
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        result=self.run_table_workflow(engine)
        self.assertEqual(result['status'],'finished_with_errors')
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),9)
        self.assertEqual(self.scalar('SELECT id FROM ab_group'),13)
        self.assertEqual(self.scalar('SELECT id FROM ab_z'),2)
        self.assertEqual(self.scalar('SELECT record_id FROM ab_record_user_rel'),9)
        self.assertEqual(self.scalar("SELECT res_id FROM ir_model_data WHERE name='record'"),9)
        self.assertTrue(any(f['constraint']=='ab_record_group_id_fkey' for f in result['failed_foreign_keys']))
        failure=next(f for f in result['failed_tables'] if f['operation']=='copy')
        self.assertEqual(failure['sqlstate'],'23514')
        self.assertNotIn('old record',str(result['failed_tables']))

    def test_fk_exceptions_are_reported_and_other_constraints_restore(self):
        engine=self.fixture()
        original_fk_count=self.scalar("SELECT count(*) FROM pg_constraint WHERE contype='f'")
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE loose_reference(id integer PRIMARY KEY,group_id integer REFERENCES ab_group(id))')
            cr.execute('INSERT INTO loose_reference VALUES(1,7)')
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.validate_ids()
        engine.preflight()
        from table_checkpoints import TableMigration
        # Simulate a table update failure after preflight: the captured reference
        # cannot be remapped, so its FK restoration must fail independently.
        engine.rules['accepted_foreign_key_failures']=[dict(table='loose_reference',
            constraint='loose_reference_group_id_fkey',reason='Reviewed legacy exception')]
        runner=TableMigration(engine,write_checkpoint)
        restore=runner.restore_incoming
        def fail(item):
            if item['table']=='loose_reference':
                raise MigrationError('injected incoming update failure')
            return restore(item)
        runner.restore_incoming=fail
        with contextlib.redirect_stdout(__import__('io').StringIO()) as output:
            result=runner.run(self.source_files,self.target_files)
        self.assertEqual(result['status'],'finished_with_errors')
        self.assertNotIn('Foreign key not restored: loose_reference',output.getvalue())
        missing=result['failed_foreign_keys']
        self.assertEqual(len(missing),1)
        self.assertTrue(missing[0]['accepted'])
        self.assertIn('ALTER TABLE public.',missing[0]['restore_sql'])
        self.assertEqual(self.scalar("SELECT count(*) FROM pg_constraint WHERE contype='f'"),original_fk_count)

    def test_table_circular_and_self_foreign_keys_restore(self):
        engine=self.fixture()
        with self.con.cursor() as cr:
            cr.execute('ALTER TABLE ab_group ADD COLUMN record_id integer REFERENCES ab_record(id)')
            cr.execute('ALTER TABLE ab_group ADD COLUMN parent_id integer REFERENCES ab_group(id)')
            cr.execute('UPDATE ab_group SET record_id=9,parent_id=7')
            cr.execute('ALTER TABLE prepared_migration_source.ab_group ADD COLUMN record_id integer')
            cr.execute('ALTER TABLE prepared_migration_source.ab_group ADD COLUMN parent_id integer')
            cr.execute('UPDATE prepared_migration_source.ab_group SET record_id=42,parent_id=13')
        for name,relation in [('record_id','ab_record'),('parent_id','ab_group')]:
            engine.target['ab_group']['fields'][name]=dict(type='many2one',ttype='many2one',store=True,relation=relation)
        from bulk import catalog
        engine.manifest['tables']['ab_group']['columns']=catalog(self.con)['ab_group']
        self.con.commit()
        result=self.run_table_workflow(PreparedImporter(*self.arguments))
        self.assertEqual(result['status'],'complete',result)
        self.assertEqual(self.scalar('SELECT parent_id FROM ab_group'),13)
        self.assertEqual(self.scalar('SELECT record_id FROM ab_group'),42)

    def test_accepted_fk_only_finishes_with_exceptions_and_reopens_target(self):
        engine=self.fixture()
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE loose_reference(id integer PRIMARY KEY,group_id integer REFERENCES ab_group(id))')
            cr.execute('INSERT INTO loose_reference VALUES(1,7)')
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.rules['accepted_foreign_key_failures']=[dict(table='loose_reference',
            constraint='loose_reference_group_id_fkey',reason='Accepted in fixture')]
        engine.preflight()
        from table_checkpoints import TableMigration
        runner=TableMigration(engine,write_checkpoint)
        restore=runner.restore_incoming
        def add_orphan(item):
            rows=restore(item)
            if item['table']=='loose_reference':
                engine.execute('INSERT INTO loose_reference VALUES(2,999)')
            return rows
        runner.restore_incoming=add_orphan
        gate=DatabaseGate(self.config,self.database)
        try:
            with target_offline(gate,self.con,self.stage):
                result=runner.run(self.source_files,self.target_files)
            self.assertTrue(gate.online())
        finally:
            gate.close()
        self.assertEqual(result['status'],'finished_with_exceptions',result)
        self.assertTrue(result['passed'])
        self.assertEqual(result['failed_tables'],[])
        self.assertEqual(result['failed_foreign_keys'][0]['sqlstate'],'23503')

    def test_controlled_interrupt_retains_commits_and_attempts_constraints(self):
        engine=self.fixture()
        engine.preflight()
        from table_checkpoints import TableMigration
        runner=TableMigration(engine,write_checkpoint)
        copy=runner.copy_model
        def interrupt(model):
            if model=='ab_record':
                raise KeyboardInterrupt()
            return copy(model)
        runner.copy_model=interrupt
        with self.assertRaises(KeyboardInterrupt):
            runner.run(self.source_files,self.target_files)
        self.assertEqual(self.scalar('SELECT id FROM ab_group'),13)
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),9)
        self.assertTrue(read_checkpoint(self.con,'table:copy:ab_group')['success'])
        self.assertIsNone(read_checkpoint(self.con,'table_result'))
        attempts=self.scalar("SELECT count(*) FROM prepared_custom_migration.checkpoint WHERE name LIKE 'fk:%'")
        self.assertEqual(attempts,len(runner.constraints))

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

    def test_cached_source_only_fields_and_attachment_links_are_skipped(self):
        self.fixture()
        manifest,target=self.arguments[2:4]
        manifest['models']['ab_record']['fields']=copy.deepcopy(manifest['models']['ab_record']['fields'])
        sf=manifest['models']['ab_record']['fields']
        sf['vendor_id']=dict(ttype='many2one',relation='abdin_eplus.vendor',store=True)
        sf['legacy_attachment_id']=dict(ttype='many2one',relation='ir.attachment',store=True)
        sf['legacy_attachments']=dict(ttype='many2many',relation='ir.attachment',relation_table='legacy_attachment_rel',
                                      column1='record_id',column2='attachment_id')
        with self.con.cursor() as cr:
            cr.execute(sql.SQL('ALTER TABLE {} ADD vendor_id integer, ADD legacy_attachment_id integer').format(sql.Identifier(SCHEMA,'ab_record')))
            cr.execute(sql.SQL('UPDATE {} SET vendor_id=887,legacy_attachment_id=3').format(sql.Identifier(SCHEMA,'ab_record')))
            cr.execute(sql.SQL('ALTER TABLE {} ADD legacy_vendor_id integer').format(sql.Identifier(SCHEMA,'ir_attachment')))
            cr.execute(sql.SQL('UPDATE {} SET legacy_vendor_id=887').format(sql.Identifier(SCHEMA,'ir_attachment')))
            cr.execute(sql.SQL("INSERT INTO {}(id,name,type,res_model,res_id) VALUES(3,'source-only link','binary','res.users',999)").format(
                sql.Identifier(SCHEMA,'ir_attachment')))
            cr.execute(sql.SQL('CREATE TABLE {}(record_id integer,attachment_id integer)').format(sql.Identifier(SCHEMA,'legacy_attachment_rel')))
            cr.execute(sql.SQL('INSERT INTO {} VALUES(42,3)').format(sql.Identifier(SCHEMA,'legacy_attachment_rel')))
        for name in ('vendor_id','legacy_attachment_id'):
            manifest['tables']['ab_record']['columns'][name]=dict(type='integer',required=False,default=None)
        manifest['tables']['ir_attachment']['columns']['legacy_vendor_id']=dict(type='integer',required=False,default=None)
        manifest['relations'].append(dict(model='ab_record',field='legacy_attachments',related='ir.attachment',
            table='legacy_attachment_rel',column1='record_id',column2='attachment_id'))
        self.con.commit()
        engine=PreparedImporter(*self.arguments)
        engine.preflight()
        skipped={(f['model'],f['field']) for f in engine.report['skipped_fields']}
        self.assertIn(('ab_record','vendor_id'),skipped)
        self.assertIn(('ab_record','legacy_attachments'),skipped)
        self.assertIn(('ir.attachment','legacy_vendor_id'),skipped)
        self.assertNotIn('vendor_id',engine.plans['ab_record']['expressions'])
        self.assertEqual(engine.scalar(sql.SQL('SELECT count(*) FROM {}').format(engine.attachment_source())),2)
        engine.replace()
        engine.external()
        engine.attachments(self.source_files,self.target_files)
        self.con.commit()
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),42)
        self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)
        self.assertEqual(self.scalar('SELECT count(*) FROM prepared_custom_migration.attachment_map WHERE source_id=3'),0)
        self.assertEqual(self.scalar('SELECT vendor_id FROM prepared_migration_source.ab_record'),887)
        engine=PreparedImporter(*self.arguments)
        engine.preflight(replacing=False)
        engine.validate_values()

    def test_new_extraction_ignores_source_only_m2m(self):
        engine=self.fixture()
        info=dict(source_version='15.0',models=copy.deepcopy(engine.models))
        for m,meta in info['models'].items():
            meta.update(transient=False,table_kind='r')
            for field in meta['fields'].values():
                field.setdefault('ttype',field.get('type'))
        info['models']['ab_record']['fields']['legacy_vendor_ids']=dict(ttype='many2many',relation='missing_vendor',
            relation_table='legacy_vendor_rel',column1='record_id',column2='vendor_id')
        with self.con.cursor() as cr:
            cr.execute('CREATE TABLE legacy_vendor_rel(record_id integer,vendor_id integer)')
            cr.execute('INSERT INTO legacy_vendor_rel VALUES(9,887)')
            cr.execute('CREATE TABLE mail_activity(id integer,res_model varchar)')
        self.con.commit()
        directory=self.stage/'extract'
        directory.mkdir()
        from prepared_snapshot import export
        with patch('prepared_snapshot.inventory',return_value=info):
            exported=export(self.con,self.config,self.database,directory,engine.target,engine.rules)
        self.assertNotIn('legacy_vendor_rel',exported['tables'])
        self.assertFalse(any(r['field']=='legacy_vendor_ids' for r in exported['relations']))

    def test_required_target_only_field_still_blocks_shared_field_import(self):
        self.fixture()
        with self.con.cursor() as cr:
            cr.execute("ALTER TABLE ab_record ADD required_new varchar NOT NULL DEFAULT 'setup'")
            cr.execute('ALTER TABLE ab_record ALTER COLUMN required_new DROP DEFAULT')
        self.arguments[3]['ab_record']['fields']['required_new']=dict(type='char',store=True,required=True)
        engine=PreparedImporter(*self.arguments)
        with self.assertRaisesRegex(MigrationError,'Required target-only field'):
            engine.preflight()
        self.con.rollback()
        self.assertEqual(self.scalar('SELECT id FROM ab_record'),9)

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
                    from resume import endpoint
                    from watch_progress import observe
                    save_json(self.stage/'prepared-run.json',dict(target_endpoint=endpoint(self.config),
                        target_db=self.database,target_oid=gate.oid))
                    messages=observe(self.config,self.stage)
                    self.assertTrue(any('backend' in message for message in messages))
                    self.assertFalse(any('unavailable' in message for message in messages))
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

    def test_controller_keeps_source_read_only_and_returns_finished_table_result(self):
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
                if Path(path).name=='verification.json':
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
            answers=iter([True,False])
            with patch('prepared.metadata',side_effect=schema),patch('prepared_snapshot.inventory',side_effect=inventory), \
                    patch('prepared.confirm',side_effect=approve):
                cancelled=run(args,root)
            self.assertEqual(cancelled['status'],'cancelled')
            self.assertEqual((old_stage/'source-availability.json').read_bytes(),old_availability)
            self.assertEqual(loads((old_stage/'source-ids.json').read_text())['res_users'],[1,5,7,8])
            self.assertTrue(list(old_stage.glob('source-ids-before-refresh-*.json')))
            with patch('prepared.metadata',side_effect=schema),patch('prepared.confirm',return_value=False), \
                    patch('prepared.connect',side_effect=guarded_connect) as connections:
                first=run(args,root)
            self.assertEqual(first['status'],'cancelled')
            self.assertFalse(any(c.args[1]==source_db for c in connections.call_args_list))
            # Lose the report after the terminal result commits. Repeating the
            # command returns that result without replaying any table operation.
            with patch('prepared.metadata',side_effect=schema),patch('prepared.SmokeWorker',FakeSmoke), \
                    patch('prepared.confirm',return_value=True),patch('table_checkpoints.save_json',side_effect=lose_report):
                with self.assertRaisesRegex(MigrationError,'OSError'):
                    run(args,root)
            with patch('prepared.metadata',side_effect=schema),patch('prepared.confirm',side_effect=AssertionError('unexpected replay')):
                finished=run(args,root)
            self.assertTrue(finished['passed'])
            self.assertEqual(finished['status'],'complete')
            with self.admin.cursor() as cr:
                cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[source_db])
                self.assertTrue(cr.fetchone()[0])
                cr.execute('SELECT datallowconn FROM pg_database WHERE datname=%s',[self.database])
                self.assertTrue(cr.fetchone()[0])
            self.con=connect(self.config,self.database,readonly=False)
            self.assertEqual(self.scalar('SELECT count(*) FROM ir_attachment'),3)
            self.assertEqual(self.scalar('SELECT currency_id FROM ab_record'),900)
            self.assertEqual(self.scalar('SELECT name FROM ab_group'),'live update after snapshot 1')
            with self.con.cursor() as cr:
                cr.execute("DELETE FROM prepared_custom_migration.checkpoint WHERE name='table_result'")
            self.con.commit()
            with patch('prepared.metadata',side_effect=schema),patch('prepared.confirm') as prompt:
                with self.assertRaisesRegex(MigrationError,'automatic continuation is disabled'):
                    run(args,root)
                prompt.assert_not_called()
            with patch('builtins.input') as prompt:
                with self.assertRaisesRegex(MigrationError,'checkpoints'):
                    reset(args,root)
                prompt.assert_not_called()
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
