import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock
from psycopg2 import sql
from common import MigrationError, save_json
from quarantine import validate_policy
from resume import fingerprint, BUSINESS_VERSION
import test_bulk


class QuarantineTests(unittest.TestCase):
    def policy(self):
        return dict(version=1,snapshot='snapshot',records={'abdin_eplus.pur_trans_d':[
            dict(source_id=7,missing_model='abdin_eplus.pur_trans_h',missing_id=9)]})

    def test_approval_is_bounded_and_snapshot_specific(self):
        policy=self.policy()
        self.assertEqual(validate_policy(policy,'snapshot'),policy)
        with self.assertRaisesRegex(MigrationError,'snapshot'):
            validate_policy(policy,'different')
        policy['records']['ab_product']=policy['records'].pop('abdin_eplus.pur_trans_d')
        with self.assertRaisesRegex(MigrationError,'scope'):
            validate_policy(policy,'snapshot')
        policy=self.policy();policy['records']['abdin_eplus.pur_trans_d']*=2
        with self.assertRaisesRegex(MigrationError,'duplicate'):
            validate_policy(policy,'snapshot')

    def test_no_policy_preserves_existing_business_identity(self):
        engine=test_bulk.BulkTests().make_engine()
        engine.mapping_identity=lambda:'mapping'
        with tempfile.TemporaryDirectory() as directory:
            engine.stage=Path(directory);engine.manifest_id='snapshot'
            engine.load_quarantine_policy()
            self.assertEqual(engine.business_identity(),fingerprint(dict(version=BUSINESS_VERSION,mapping='mapping')))
            save_json(engine.stage/'quarantine-policy.json',self.policy())
            engine.load_quarantine_policy()
            self.assertNotEqual(engine.business_identity(),fingerprint(dict(version=BUSINESS_VERSION,mapping='mapping')))

    def test_all_identity_resolvers_exclude_quarantined_records(self):
        engine=test_bulk.BulkTests().make_engine()
        engine.mapping_modes={'ab_test':'identity'}
        engine.quarantine_models={'ab_test'};engine.working_models={'ab_test'}
        for query in [engine.mapping_relation('ab_test'),
                      engine.mapping_exists(sql.Literal('ab_test'),sql.SQL('s.id')),
                      engine.mapped_expression(sql.Literal('ab_test'),sql.SQL('s.id'))]:
            self.assertIn('accounting_migration_work',test_bulk.render(query))

    def test_prepare_quarantine_preserves_payload_and_raw_rows(self):
        engine=test_bulk.BulkTests().make_engine()
        engine.quarantine_policy=self.policy();engine.manifest_id='snapshot'
        model='abdin_eplus.pur_trans_d'
        engine.models={model:{'table':'detail'},'abdin_eplus.pur_trans_h':{'table':'header'}}
        engine.working_models=set();engine.quarantine_models=set()
        engine.cr.fetchall.return_value=[(7,'abdin_eplus.pur_trans_h',9)]
        engine.copy_quarantined_files=MagicMock()
        with tempfile.TemporaryDirectory() as directory:
            engine.stage=Path(directory);engine.prepare_quarantine()
        queries='\n'.join(q for q,p in engine.queries)
        self.assertIn('to_jsonb(s)',queries)
        self.assertIn('REVOKE ALL ON SCHEMA',queries)
        self.assertIn('CREATE VIEW',queries)
        self.assertNotIn('DELETE',queries)
        self.assertNotIn('UPDATE',queries)
        self.assertEqual(engine.quarantine_models,{model})
        engine.cr.commit.assert_not_called()

    def test_quarantine_refuses_changed_original_reference(self):
        engine=test_bulk.BulkTests().make_engine();engine.quarantine_policy=self.policy()
        engine.models={'abdin_eplus.pur_trans_d':{'table':'detail'}}
        engine.cr.fetchall.return_value=[(7,'abdin_eplus.pur_trans_h',10)]
        with self.assertRaisesRegex(MigrationError,'differ from approval'):
            engine.prepare_quarantine()
        self.assertFalse(any(q.startswith('INSERT') for q,p in engine.queries))

    def test_attachment_bytes_are_preserved_or_explicitly_reported_missing(self):
        import hashlib
        engine=test_bulk.BulkTests().make_engine()
        engine.quarantine_models={'ir.attachment'}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);engine.stage=root/'stage';engine.stage.mkdir()
            source=root/'source';(source/'ab').mkdir(parents=True)
            body=b'quarantined attachment\x00\xff';(source/'ab'/'file').write_bytes(body)
            checksum=hashlib.sha1(body).hexdigest()
            save_json(engine.stage/'bulk-settings.json',{'source_filestore':str(source)})
            engine.report={'quarantine':{'files':[]}}
            engine.cr.fetchall.return_value=[(7,'ab/file',checksum,str(len(body))), (8,'ab/missing',checksum,'1')]
            engine.copy_quarantined_files()
            target=engine.stage/'quarantine-filestore'/'ab'/'file'
            self.assertEqual(target.read_bytes(),body)
            self.assertEqual(target.stat().st_mode & 0o777,0o600)
            self.assertEqual([r['status'] for r in engine.report['quarantine']['files']],['preserved','missing_in_source'])
            self.assertEqual((source/'ab'/'file').read_bytes(),body)
            engine.cr.fetchall.return_value=[(7,'ab/file','bad-checksum',str(len(body)))]
            with self.assertRaisesRegex(MigrationError,'checksum/size'):
                engine.copy_quarantined_files()
