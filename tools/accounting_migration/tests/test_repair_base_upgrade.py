"""Opt-in base-upgrade rehearsal in a fresh, disposable Odoo clone only."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from psycopg2 import sql
import test_prepared_postgres as fixtures
from common import connect, ensure_backup, settings
from csv_plan import export_plan, database_identity
from database_repair import run


@unittest.skipUnless(os.environ.get('MIGRATION_PREPARED_TEST_CONFIG') and os.environ.get('MIGRATION_ODOO_SERVER'),
                     'requires disposable PostgreSQL config and Odoo server for base-upgrade rehearsal')
class BaseUpgradeRepairTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PreparedPostgresTests.setUpClass.__func__)
    tearDownClass = classmethod(fixtures.PreparedPostgresTests.tearDownClass.__func__)
    setUp = fixtures.PreparedPostgresTests.setUp
    tearDown = fixtures.PreparedPostgresTests.tearDown

    def test_core_identity_repair_allows_base_upgrade_in_disposable_clone(self):
        server=Path(os.environ['MIGRATION_ODOO_SERVER'])
        addons=self.stage/'addons'
        alpha=addons/'repair_seed_alpha'
        beta=addons/'repair_seed_beta'
        alpha.mkdir(parents=True)
        beta.mkdir()
        (alpha/'__manifest__.py').write_text(repr(dict(name='Repair seed fixture',version='19.0.1.0.0',
            author='Migration test fixtures',developer='Migration test fixtures',license='LGPL-3',
            depends=['base'],data=['security/ir.model.access.csv','seed.xml'])))
        (alpha/'__init__.py').write_text('from . import model\n')
        (alpha/'model.py').write_text("from odoo import models, fields\n"
            "class RepairSeed(models.Model):\n"
            "    _name = 'repair_test_seed'\n"
            "    _description = 'Repair seed fixture'\n"
            "    name = fields.Char(required=True)\n"
            "    _unique_name = models.Constraint('UNIQUE(name)', 'Seed name must be unique.')\n")
        (alpha/'security').mkdir()
        (alpha/'security'/'ir.model.access.csv').write_text('id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink\n'
            'access_seed,Repair seed,model_repair_test_seed,base.group_system,1,1,1,0\n')
        (alpha/'seed.xml').write_text('<odoo><data noupdate="1">'
            '<record id="root" model="repair_test_seed"><field name="name">Root</field></record>'
            '<record id="liability" model="repair_test_seed"><field name="name">Liabilities</field></record>'
            '</data></odoo>')
        (beta/'__manifest__.py').write_text(repr(dict(name='Second seed namespace',version='19.0.1.0.0',
            author='Migration test fixtures',developer='Migration test fixtures',license='LGPL-3',
            depends=['repair_seed_alpha'],data=['seed.xml'])))
        (beta/'__init__.py').write_text('')
        (beta/'seed.xml').write_text('<odoo/>')
        logfile=self.stage/'odoo.log'
        command=[sys.executable,str(server/'odoo-bin'),'-c',self.config,'-d',self.database,
                 '--addons-path='+str(server/'odoo/addons')+','+str(server/'addons')+','+str(addons),
                 '--data-dir='+str(self.stage/'odoo-data'),'--stop-after-init','--no-http',
                 '--max-cron-threads=0','--without-demo=all','--logfile='+str(logfile)]
        self.con.close()
        source_db=None
        try:
            initialized=subprocess.run(command+['-i','repair_seed_alpha,repair_seed_beta'],capture_output=True,timeout=180)
            self.assertEqual(initialized.returncode,0,logfile.read_text()[-2500:])
            self.con=connect(self.config,self.database,readonly=False)
            with self.con.cursor() as cr:
                cr.execute('UPDATE ir_cron SET active=false')
            self.con.commit()
            self.con.close()
            clone=self.stage/'clone'
            clone.mkdir(mode=0o700)
            ensure_backup(self.config,self.database,clone)
            source_name='codex_migration_test_prepared_'+uuid.uuid4().hex[:12]
            with self.admin.cursor() as cr:
                cr.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(source_name)))
            source_db=source_name
            environ=os.environ.copy()
            options=settings(self.config)
            for variable,key in [('PGHOST','db_host'),('PGPORT','db_port'),('PGUSER','db_user'),('PGPASSWORD','db_password')]:
                if options.get(key) not in (None,'','False'):
                    environ[variable]=options[key]
            restored=subprocess.run(['pg_restore','--no-owner','--no-privileges','-d',source_db,str(clone/'before_import.dump')],
                                    env=environ,capture_output=True,timeout=120)
            self.assertEqual(restored.returncode,0,'Could not restore disposable Odoo source clone')
            self.con=connect(self.config,self.database,readonly=False)
            with self.con.cursor() as cr:
                cr.execute("UPDATE ir_model_data SET res_id=(SELECT id FROM res_users WHERE login='public') "
                           "WHERE module='base' AND name='template_portal_user_id'")
                cr.execute("UPDATE ir_config_parameter SET value=(SELECT id::text FROM res_users WHERE login='public') "
                           "WHERE key='base.template_portal_user_id'")
            self.con.commit()
            self.con.close()
            # Simulate committed source-ID replacement in both fixtures while
            # leaving only target aliases at their pre-copy IDs.
            for database,is_source in ((source_db,True),(self.database,False)):
                connection=connect(self.config,database,readonly=False)
                try:
                    with connection.cursor() as cr:
                        cr.execute("SELECT id,name FROM repair_test_seed")
                        old=dict((name,rid) for rid,name in cr.fetchall())
                        for name,rid in [('Root',495),('Liabilities',257)]:
                            cr.execute('UPDATE repair_test_seed SET id=%s WHERE id=%s',[rid,old[name]])
                            if is_source:
                                cr.execute("UPDATE ir_model_data SET res_id=%s WHERE model='repair_test_seed' AND res_id=%s",[rid,old[name]])
                        cr.execute("INSERT INTO repair_test_seed(id,name) VALUES(%s,'Assets')",[old['Root']])
                        cr.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) "
                                   "VALUES('repair_seed_beta','liability','repair_test_seed',%s,true)",
                                   [257 if is_source else old['Liabilities']])
                    connection.commit()
                finally:
                    connection.close()
            (beta/'seed.xml').write_text('<odoo><data noupdate="1">'
                '<record id="liability" model="repair_test_seed"><field name="name">Liabilities</field></record>'
                '</data></odoo>')
            broken_seed=subprocess.run(command+['-u','repair_seed_alpha,repair_seed_beta'],capture_output=True,timeout=180)
            self.assertNotEqual(broken_seed.returncode,0)
            self.assertIn('Key (name)=(Liabilities) already exists',logfile.read_text())
            broken=subprocess.run(command+['-u','base'],capture_output=True,timeout=180)
            self.assertNotEqual(broken.returncode,0)
            self.assertIn('res_users_login_key',logfile.read_text())
            source=connect(self.config,source_db)
            self.con=connect(self.config,self.database,readonly=False)
            try:
                identities=dict(source=database_identity(source,self.config),target=database_identity(self.con,self.config))
                with self.con.cursor() as cr:
                    cr.execute('CREATE SCHEMA csv_replication')
                    cr.execute('CREATE TABLE csv_replication.checkpoint(name text PRIMARY KEY,value text)')
                    state=dict(format=4,identities=identities,constraints=[],operations={'repair_test_seed':dict(
                        success=True,mode='replace',status='copied',rows=3,expected=3,target_count=3)})
                    cr.execute("INSERT INTO csv_replication.checkpoint VALUES('state',%s)",[json.dumps(state)])
                self.con.commit()
            finally:
                source.close()
                self.con.close()
            csv=self.stage/'bound.csv'
            args=SimpleNamespace(source_config=self.config,source_db=source_db,target_config=self.config,
                                 target_db=self.database,export_table_plan=str(csv))
            with contextlib.redirect_stdout(io.StringIO()):
                export_plan(args)
            values=dict(source_config=self.config,source_db=source_db,target_config=self.config,
                        target_db=self.database,csv_path=str(csv))
            with patch('builtins.input',side_effect=['1','y']),contextlib.redirect_stdout(io.StringIO()):
                result=run(values,self.stage,backup=True)
            self.assertTrue(all(r['status']=='committed' for r in result['results']),result)
            fixed=subprocess.run(command+['-u','base,repair_seed_alpha,repair_seed_beta'],capture_output=True,timeout=180)
            self.assertEqual(fixed.returncode,0,logfile.read_text()[-2500:])
            self.con=connect(self.config,self.database,readonly=False)
            with self.con.cursor() as cr:
                cr.execute("SELECT module,name,res_id FROM ir_model_data WHERE model='repair_test_seed' ORDER BY module,name")
                self.assertEqual(cr.fetchall(),[('repair_seed_alpha','liability',257),('repair_seed_alpha','root',495),('repair_seed_beta','liability',257)])
                cr.execute('SELECT count(*) FROM repair_test_seed')
                self.assertEqual(cr.fetchone()[0],3)
        finally:
            self.con.close()
            if source_db:
                with self.admin.cursor() as cr:
                    cr.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(source_db)))
                    cr.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s "
                               "AND usename=current_user AND backend_type='client backend'",[source_db])
                    cr.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(source_db)))
            self.con=connect(self.config,self.database,readonly=False)


if __name__=='__main__':
    unittest.main()
