"""Opt-in fresh-registry acceptance on a disposable pg_dump clone.

MIGRATION_PREPARED_TEST_CONFIG selects maintenance credentials/config.
MIGRATION_PREPARED_ODOO_TEMPLATE_DB explicitly selects a read-only dump source.
All replacement/availability operations affect only a generated test database.
This is Odoo 19 acceptance, not a complete production Odoo 15 migration rehearsal.
"""
import configparser
import copy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from psycopg2 import sql
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from availability import DatabaseGate,target_offline
from bulk import catalog
from common import connect,settings,save_json
from prepared import initialize,metadata,SmokeWorker
from prepared_importer import PreparedImporter,WORK
from prepared_snapshot import SCHEMA


ENABLED=os.environ.get('MIGRATION_PREPARED_TEST_CONFIG') and os.environ.get('MIGRATION_PREPARED_ODOO_TEMPLATE_DB')


@unittest.skipUnless(ENABLED,'requires explicitly selected read-only Odoo 19 template and disposable clone')
class PreparedOdooAcceptance(unittest.TestCase):
    def test_replaced_custom_ids_are_readable_by_fresh_offline_registry(self):
        config=os.environ['MIGRATION_PREPARED_TEST_CONFIG']
        template=os.environ['MIGRATION_PREPARED_ODOO_TEMPLATE_DB']
        database='codex_migration_test_prepared_odoo_'+uuid.uuid4().hex[:10]
        opts=settings(config)
        env=os.environ.copy()
        for key in ('db_host','db_port','db_user','db_password'):
            if opts.get(key) not in (None,'','False','false'):
                env['PG'+key[3:].upper()]=opts[key]
        admin=connect(config,'postgres',readonly=False)
        admin.autocommit=True
        connection,gate,worker=None,None,None
        with tempfile.TemporaryDirectory() as directory:
            stage=Path(directory)
            try:
                dump=stage/'template.dump'
                result=subprocess.run(['pg_dump','-Fc','--no-owner','-d',template,'-f',str(dump)],env=env,capture_output=True)
                self.assertEqual(result.returncode,0,'read-only template dump failed')
                dump.chmod(0o600)
                with admin.cursor() as cr:
                    cr.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database)))
                result=subprocess.run(['pg_restore','--no-owner','--no-privileges','-d',database,str(dump)],env=env,capture_output=True)
                self.assertEqual(result.returncode,0,'disposable clone restore failed')
                cfg=configparser.ConfigParser(interpolation=None)
                cfg['options']=opts
                cfg['options']['data_dir']=str(stage/'data')
                test_config=stage/'target.conf'
                with open(test_config,'w') as out:
                    cfg.write(out)
                test_config.chmod(0o600)
                from types import SimpleNamespace
                args=SimpleNamespace(target_config=str(test_config),target_db=database)
                target=metadata(args,stage)
                selected=['ab_customer_contact_way']
                self.assertIn(selected[0],target)
                connection=connect(str(test_config),database,readonly=False)
                physical=catalog(connection)
                models={m:dict(table=v['table'],fields={n:{**f,'ttype':f['type']} for n,f in v['fields'].items()}) for m,v in target.items()}
                table=target[selected[0]]['table']
                with connection.cursor() as cr:
                    # The template may already contain a real migration's private
                    # staging/checkpoints. Reset them only inside this disposable clone.
                    for namespace in (WORK,SCHEMA,'prepared_custom_migration'):
                        cr.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(namespace)))
                    cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
                    cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(WORK)))
                    for name in (table,'ir_model_data','ir_model_fields','ir_model','res_currency'):
                        cr.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM public.{}').format(sql.Identifier(SCHEMA,name),sql.Identifier(name)))
                    for name in ('res_users','res_partner'):
                        cr.execute(sql.SQL('CREATE TABLE {} AS SELECT id FROM public.{}').format(sql.Identifier(SCHEMA,name),sql.Identifier(name)))
                    cr.execute(sql.SQL('CREATE TABLE {} AS SELECT * FROM public.ir_attachment WHERE false').format(sql.Identifier(SCHEMA,'ir_attachment')))
                    cr.execute(sql.SQL('SELECT id FROM {} ORDER BY id').format(sql.Identifier(SCHEMA,table)))
                    old_ids=[r[0] for r in cr]
                    self.assertTrue(old_ids,'selected template model has no seed data')
                    for old in old_ids:
                        new=old+10000
                        cr.execute(sql.SQL('UPDATE {} SET id=%s WHERE id=%s').format(sql.Identifier(SCHEMA,table)),[new,old])
                        cr.execute(sql.SQL('UPDATE {} SET res_id=%s WHERE model=%s AND res_id=%s').format(sql.Identifier(SCHEMA,'ir_model_data')),
                                   [new,selected[0],old])
                    manifest=dict(format=1,complete=True,selected=selected,omitted=[],models=models,relations=[],tables={},activities=0)
                    for name in (table,'ir_model_data','ir_model_fields','ir_model','res_currency','ir_attachment'):
                        cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(SCHEMA,name)))
                        manifest['tables'][name]=dict(columns=physical[name],rows=cr.fetchone()[0])
                initialize(connection,{'acceptance':True})
                rules=dict(stable_keys={'res.currency':'name'},external_ids={},incoming_ids={},ignore_fields={})
                engine=PreparedImporter(connection,stage,manifest,target,rules,{})
                engine.validate_ids()
                engine.preflight()
                engine.replace()
                connection.commit()
                engine=PreparedImporter(connection,stage,manifest,target,rules,{})
                engine.preflight(replacing=False)
                engine.external()
                engine.attachments(stage/'source-files',stage/'data'/'filestore'/database)
                engine.validate_values()
                connection.commit()
                save_json(stage/'snapshot.json',manifest)
                worker=SmokeWorker(args,stage)
                gate=DatabaseGate(str(test_config),database)
                with target_offline(gate,connection,stage,workers=[worker.pid]):
                    result=worker.run()
                    self.assertTrue(result['passed'])
                with connection.cursor() as cr:
                    cr.execute(sql.SQL('SELECT id FROM public.{} ORDER BY id').format(sql.Identifier(table)))
                    self.assertEqual([r[0] for r in cr],[n+10000 for n in old_ids])
            except BaseException:
                import shutil
                diagnostics=Path(tempfile.mkdtemp(prefix='prepared-odoo-diagnostics-'))
                for log in stage.glob('*.log'):
                    shutil.copyfile(log,diagnostics/log.name)
                print('Private Odoo acceptance logs: '+str(diagnostics),flush=True)
                raise
            finally:
                if worker:
                    worker.close()
                if gate:
                    gate.close()
                if connection:
                    connection.close()
                with admin.cursor() as cr:
                    cr.execute('SELECT 1 FROM pg_database WHERE datname=%s',[database])
                    if cr.fetchone():
                        cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(database)))
                    cr.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s "
                               "AND usename=current_user AND backend_type='client backend'",[database])
                    cr.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(database)))
                admin.close()


if __name__=='__main__':
    unittest.main()
