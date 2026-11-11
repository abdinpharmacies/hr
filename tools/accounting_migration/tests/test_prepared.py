"""Offline contract tests; no config files or databases are opened."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import MigrationError, save_json
from prepared import confirm, find_stage, identity_checkpoint, run, source_database_oid
from prepared_snapshot import select_models, verify
from migrate import main


class PreparedTests(unittest.TestCase):
    def test_only_shared_persistent_ab_models(self):
        def model(kind='r',transient=False):
            return dict(table_kind=kind,transient=transient)
        info={'models':{'ab_one':model(),'abdin.two':model(),'res.users':model(),
            'ab_wizard':model(transient=True),'ab_view':model('v'),'ab_omitted':model()}}
        selected,omitted=select_models(info,{'ab_one':{},'abdin.two':{},'res.users':{},'ab_wizard':{},'ab_view':{}})
        self.assertEqual(selected,['ab_one','abdin.two'])
        self.assertEqual(omitted,['ab_omitted'])

    def test_prompts_default_to_no_and_handle_eof(self):
        with contextlib.redirect_stdout(io.StringIO()):
            for answer in ('','n','YES PLEASE'):
                with patch('builtins.input',return_value=answer):
                    self.assertFalse(confirm('summary'))
            with patch('builtins.input',side_effect=EOFError):
                self.assertFalse(confirm('summary'))
            with patch('builtins.input',return_value='yes'):
                self.assertTrue(confirm('summary'))

    def test_run_identity_rejects_changed_rule_or_database(self):
        identity=dict(source_endpoint={},target_endpoint={},source_db='source',target_db='target',format=1,source_oid=11)
        with tempfile.TemporaryDirectory() as directory:
            path=find_stage(directory,identity)
            self.assertEqual(find_stage(directory,identity),path)
            with self.assertRaisesRegex(MigrationError,'incompatible'):
                find_stage(directory,{**identity,'source_oid':12})

    def test_run_identity_allows_mapping_revision_without_reset(self):
        identity=dict(source_endpoint={},target_endpoint={},source_db='source',target_db='target',format=2,
                      source_oid=11,target_oid=12,rules='original')
        with tempfile.TemporaryDirectory() as directory:
            path=find_stage(directory,identity)
            self.assertEqual(find_stage(directory,{**identity,'rules':'corrected'}),path)
            from common import loads
            self.assertEqual(loads((path/'prepared-run.json').read_text())['rules'],'original')

    def test_cli_uses_only_prepared_workflow(self):
        with patch('prepared.run',return_value={'passed':True}) as run,patch('legacy_migrate.legacy_main') as legacy:
            result=main(['--source-config','source','--source-db','a','--target-config','target','--target-db','b'])
        self.assertTrue(result['passed'])
        self.assertEqual(run.call_args.args[0].target_db,'b')
        legacy.assert_not_called()

    def test_invalid_snapshot_fails_before_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(MigrationError):
                verify(directory,{'format':1,'complete':False})

    def test_user_partner_check_has_no_reverse_difference(self):
        # A target-only ID is deliberately not a mismatch: only source LEFT JOIN.
        from test_bulk import render
        con=MagicMock()
        cr=con.cursor.return_value.__enter__.return_value
        cr.__iter__.return_value=iter([])
        from psycopg2 import sql
        with tempfile.TemporaryDirectory() as directory,patch('prepared.execute_values'), \
                patch.object(sql.Composed,'as_string',lambda query,connection:render(query)):
            report=identity_checkpoint(con,{'res_users':[1,5,6,7,13],'res_partner':[1,6,99]},directory)
        queries=[render(c.args[0]) for c in cr.execute.call_args_list]
        checks=[q for q in queries if 'LEFT JOIN' in q]
        self.assertEqual(len(checks),2)
        self.assertTrue(all('WHERE t.id IS NULL' in q for q in checks))
        self.assertTrue(all('s.id >= 7' in q for q in checks))
        self.assertEqual(report['report']['res_users']['missing_ids'],[])
        self.assertEqual(report['report']['res_users']['checked_count'],2)
        self.assertEqual(report['report']['res_users']['skipped_count'],3)

    def test_unavailable_source_never_has_an_availability_gate(self):
        import psycopg2
        target=MagicMock(oid=12)
        connection=MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchone.return_value=('19.0',)
        args=SimpleNamespace(source_db='source',target_db='target',source_config='source.conf',target_config='target.conf')
        with tempfile.TemporaryDirectory() as directory,contextlib.redirect_stdout(io.StringIO()), \
                patch('prepared.DatabaseGate',return_value=target) as gate,patch('prepared.recover_target'), \
                patch('prepared.settings',return_value={'data_dir':directory}),patch('prepared.endpoint',return_value={}), \
                patch('prepared.source_database_oid',return_value=11),patch('prepared.read_checkpoint',return_value=None), \
                patch('prepared.metadata',return_value={'res.users':{'table':'res_users','fields':{}}}), \
                patch('prepared.connect',side_effect=[connection,psycopg2.OperationalError('unavailable')]) as connect:
            with self.assertRaisesRegex(MigrationError,'Cannot read source'):
                run(args,Path(directory)/'runs')
        gate.assert_called_once_with('target.conf','target')
        connect.assert_called_with('source.conf','source',readonly=True)
        target.set_online.assert_not_called()

    def test_source_catalog_identity_is_read_only_without_owner_checks(self):
        connection=MagicMock()
        cr=connection.cursor.return_value.__enter__.return_value
        cr.fetchone.return_value=(123,)
        with patch('prepared.connect',return_value=connection) as connect:
            self.assertEqual(source_database_oid('source.conf','source'),123)
        connect.assert_called_once_with('source.conf','postgres',readonly=True)
        cr.execute.assert_called_once_with('SELECT oid FROM pg_database WHERE datname=%s',['source'])
        connection.close.assert_called_once()

    def test_users_cannot_use_stable_keys_or_extract_passwords(self):
        args=SimpleNamespace(source_db='source',target_db='target',source_config='unused',target_config='unused')
        with patch('prepared.loads',side_effect=[{'format':1,'stable_keys':{'res.users':'password'}},{}]), \
                patch('prepared.DatabaseGate') as gate:
            with self.assertRaisesRegex(MigrationError,'Stable-key override forbidden'):
                run(args,'unused')
        gate.assert_not_called()


if __name__=='__main__':
    unittest.main()
