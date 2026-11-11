import base64
from decimal import Decimal
from pathlib import Path
import tempfile
import sqlite3
import hashlib
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError, downstream, dumps, loads, private_dir, safe_attachment_path, save_json, schema_digest
from importer import DependencyPending, Importer
from migrate import parser
from source import recover_files, staging_db
from worker import isolate
from adapters import transform, historical_validation_issues


class MigrationTests(unittest.TestCase):
    def test_dependency_closure_handles_cycles(self):
        graph = {'ab_accounting': ['catalog'], 'purchase': ['ab_accounting'],
                 'asset': ['purchase', 'cycle'], 'cycle': ['asset'], 'unrelated': ['catalog']}
        self.assertEqual(downstream(graph), ['ab_accounting', 'asset', 'cycle', 'purchase'])

    def test_exact_decimal_and_binary_roundtrip(self):
        record = {'amount': Decimal('1234567890123.4500'), 'binary': b'\x00\xff', 'arabic': 'حساب'}
        self.assertEqual(loads(dumps(record)), record)

    def test_artifacts_are_private_and_json_atomic(self):
        with tempfile.TemporaryDirectory() as d:
            private_dir(d)
            p = Path(d) / 'manifest.json'
            save_json(p, {'complete': False})
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            self.assertFalse(p.with_name('manifest.json.tmp').exists())
            self.assertFalse(loads(p.read_text())['complete'])

    def test_filestore_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(MigrationError): safe_attachment_path(d, '../../etc/passwd')
            self.assertEqual(safe_attachment_path(d, 'ab/hash'), Path(d) / 'ab/hash')

    def fixture_engine(self):
        engine = Importer.__new__(Importer)
        engine.rules = {'models': {}, 'fields': {}, 'ignore_fields': {}, 'selections': {},
                        'polymorphic': {'entry': {'res_id': 'res_model'}}, 'integer_links': {}}
        fields = {'account': {'type': 'many2one', 'required': True, 'compute': False, 'readonly': False, 'related': False},
                  'branch': {'type': 'many2one', 'required': False, 'compute': False, 'readonly': False, 'related': False},
                  'image': {'type': 'binary', 'required': False, 'compute': False, 'readonly': False, 'related': False},
                  'res_id': {'type': 'integer', 'required': False, 'compute': False, 'readonly': False, 'related': False},
                  'res_model': {'type': 'char', 'required': False, 'compute': False, 'readonly': False, 'related': False}}
        engine.schema = {'entry': {'fields': fields}}
        engine.manifest = {'models': {'entry': {'fields': {'account': {'relation': 'account'}, 'branch': {'relation': 'branch'}}}}}
        identities = {('account', 3): 103, ('branch', 7): 207, ('document', 12): 412}
        def mapped(model, source_id, pending=False):
            if (model, source_id) not in identities:
                raise DependencyPending() if pending else MigrationError('unresolved')
            return identities[model, source_id]
        engine.mapped = mapped
        return engine

    def test_relations_remap_and_binary_not_double_encoded(self):
        engine = self.fixture_engine()
        encoded = base64.b64encode(b'a picture')
        row = {'id': 10, 'account': 3, 'branch': 7, 'image': encoded, 'res_model': 'document', 'res_id': 12}
        vals = engine.values('entry', row)
        self.assertEqual(vals['account'], 103)
        self.assertEqual(vals['branch'], 207)
        self.assertEqual(vals['image'], encoded)
        self.assertNotIn('res_id', vals)
        self.assertEqual(engine.values('entry', row, final=True)['res_id'], 412)

    def test_required_dependency_waits_and_final_optional_fails(self):
        engine = self.fixture_engine()
        with self.assertRaises(DependencyPending): engine.values('entry', {'account': 999})
        self.assertFalse(engine.values('entry', {'account': 3, 'branch': 999})['branch'])
        with self.assertRaises(MigrationError): engine.values('entry', {'account': 3, 'branch': 999}, final=True)

    def test_source_connection_and_outbound_network_denied(self):
        import socket, psycopg2
        with tempfile.TemporaryDirectory() as d:
            config = Path(d) / 'odoo.conf'
            config.write_text('[options]\ndb_host=localhost\ndb_port=5432\n')
            # Patches are restored after exercising the isolated worker policy.
            with patch.object(socket.socket, 'connect'), patch.object(socket.socket, 'connect_ex'), \
                 patch.object(socket, 'create_connection'), patch.object(psycopg2, 'connect'):
                isolate(config, 'migration_target')
                with self.assertRaises(MigrationError): psycopg2.connect(dbname='abdinpharmacies')
                with self.assertRaises(MigrationError): socket.create_connection(('example.com', 443))

    def test_schema_fingerprint_ignores_dynamic_language_choices(self):
        import copy
        schema = {'res.users': {'table': 'res_users', 'fields': {'lang': {'type': 'selection', 'selection': ['en_US']}}}}
        expanded = copy.deepcopy(schema)
        expanded['res.users']['fields']['lang']['selection'].append('ar_001')
        self.assertEqual(schema_digest(schema), schema_digest(expanded))
        expanded['res.users']['fields']['lang']['type'] = 'char'
        self.assertNotEqual(schema_digest(schema), schema_digest(expanded))

    def test_phone_adapter_preserves_and_checks_conflicts(self):
        original = {'id': 8, 'mobile': '123', 'phone': False}
        self.assertEqual(transform('res.partner', original)['phone'], '123')
        self.assertEqual(original['mobile'], '123')
        self.assertEqual(transform('res.partner', {'phone': '123', 'mobile': '123'})['phone'], '123')
        with self.assertRaises(MigrationError):
            transform('res.partner', {'phone': '123', 'mobile': '456'})

    def test_zero_only_adapter_rejects_data_loss(self):
        self.assertNotIn('credit_limit', transform('res.partner', {'credit_limit': Decimal('0')}))
        with self.assertRaises(MigrationError):
            transform('res.partner', {'credit_limit': Decimal('0.01')})
        with self.assertRaises(MigrationError):
            transform('res.partner', {'partner_gid': 17})

    def test_idle_policy_is_not_discarded(self):
        self.assertEqual(transform('res.users', {'enable_idle': True, 'idle_time': 7, 'sidebar_type': 'large'}),
                         {'enable_idle': True, 'idle_time': 7})

    def test_file_recovery_preserves_snapshot_and_rejects_wrong_bytes(self):
        from common import digest
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as files:
            stage = Path(d)
            (stage / 'blobs').mkdir()
            db = sqlite3.connect(stage / 'records.sqlite')
            db.executescript('CREATE TABLE records(model TEXT,source_id INTEGER,payload TEXT); '
                             'CREATE TABLE attachments(source_id INTEGER PRIMARY KEY,sha256 TEXT,size INTEGER);')
            payload = dumps({'id': 3, 'type': 'binary', 'store_fname': 'file',
                             'checksum': hashlib.sha1(b'original').hexdigest()})
            db.execute('INSERT INTO records VALUES (?,?,?)', ('ir.attachment', 3, payload))
            db.commit(); db.close()
            save_json(stage / 'manifest.json', {'snapshot_id': 'same-snapshot', 'complete': False,
                'blockers': ['Missing attachment file: ir.attachment:3'],
                'records_sha256': digest(stage / 'records.sqlite')})
            (Path(files) / 'file').write_bytes(b'wrong')
            self.assertFalse(recover_files(stage, files)['complete'])
            self.assertFalse((stage / 'blobs' / '3').exists())
            (Path(files) / 'file').write_bytes(b'original')
            self.assertTrue(recover_files(stage, files)['complete'])
            self.assertEqual(loads((stage / 'manifest.json').read_text())['snapshot_id'], 'same-snapshot')
            self.assertEqual((stage / 'blobs' / '3').read_bytes(), b'original')
            with self.assertRaises(MigrationError): recover_files(stage, files)

    def test_stage_reader_does_not_block_export_commit(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'records.sqlite'
            writer = staging_db(path)
            writer.execute('CREATE TABLE records(id INTEGER PRIMARY KEY)')
            writer.execute('INSERT INTO records VALUES (1)')
            writer.commit()
            reader = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
            reader.execute('BEGIN')
            self.assertEqual(reader.execute('SELECT count(*) FROM records').fetchone()[0], 1)
            writer.execute('INSERT INTO records VALUES (2)')
            writer.commit()
            self.assertEqual(reader.execute('SELECT count(*) FROM records').fetchone()[0], 1)
            reader.close()
            self.assertEqual(writer.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0], 0)
            writer.close()

    def test_missing_attachment_keeps_metadata_without_fake_content(self):
        engine = self.fixture_engine()
        engine.schema['ir.attachment'] = engine.schema['entry']
        engine.manifest['models']['ir.attachment'] = {'fields': {}}
        engine.rules['polymorphic']['ir.attachment'] = {'res_id': 'res_model'}
        engine.missing_files = {99}
        engine.allow_missing_files = True
        row = {'id': 99, 'res_model': 'document', 'res_id': 12, 'type': 'binary',
               'store_fname': 'aa/missing', 'checksum': 'original', 'file_size': 123}
        result = engine.values('ir.attachment', row)
        self.assertFalse(result['raw'])
        self.assertTrue(result['migration_file_missing'])
        self.assertEqual(result['migration_source_checksum'], 'original')
        self.assertEqual(result['migration_source_size'], 123)
        engine.allow_missing_files = False
        with self.assertRaises(MigrationError): engine.values('ir.attachment', row)

    def test_orphan_inventory_keeps_quantity_and_cannot_link_to_unrelated_id(self):
        engine = self.fixture_engine()
        fields = {n: {'type': t, 'required': False, 'compute': False, 'readonly': False, 'related': False}
                  for n, t in [('qty','integer'), ('header_ref','char'), ('header_id','integer'), ('model_ref','char'), ('res_id','integer')]}
        engine.schema['ab_inventory'] = {'fields': fields}
        engine.manifest['models']['ab_inventory'] = {'fields': {}}
        engine.rules['polymorphic']['ab_inventory'] = {'res_id': 'model_ref'}
        engine.rules['integer_links']['ab_inventory'] = {'header_id': 'ab_inventory_header'}
        engine.orphan_refs = {('ab_inventory', 7, 'res_id'): ('ab_purchase_line', 404)}
        engine.orphan_targets = {('ab_purchase_header', 42)}
        engine.allow_source_defects = True
        engine.mapped = lambda model, rid, pending=False: 999
        row = {'id': 7, 'qty': 17, 'header_id': 888, 'header_ref': 'P42', 'model_ref': 'ab_purchase_line', 'res_id': 404}
        result = engine.values('ab_inventory', row)
        self.assertEqual(result['qty'], 17)
        self.assertEqual(result['res_id'], 0)
        self.assertEqual(result['header_id'], 999)
        self.assertEqual(result['header_ref'], 'LEGACY:P42')
        self.assertEqual(loads(result['migration_source_references'])['res_id'], 404)
        self.assertTrue(result['migration_reference_missing'])

    def test_only_bootstrap_administrator_remains_active_during_import(self):
        engine = self.fixture_engine()
        engine.schema['res.users'] = engine.schema['entry']
        engine.manifest['models']['res.users'] = {'fields': {}}
        engine.bootstrap_admin_source_id = 2
        self.assertTrue(engine.values('res.users', {'id': 2})['active'])
        self.assertFalse(engine.values('res.users', {'id': 3, 'active': True})['active'])

    def test_legacy_price_units_and_invoice_exceptions_are_reported(self):
        units = {1: {'unit_no': 1, 'type_id': 1}, 2: {'unit_no': 2, 'type_id': 1}, 3: {'unit_no': 3, 'type_id': 1}}
        self.assertTrue(historical_validation_issues('ab_product', {'unit_l_id': 1, 'unit_m_id': 2, 'unit_s_id': 3}, units, {}))
        self.assertFalse(historical_validation_issues('ab_product', {'unit_l_id': 1, 'unit_m_id': 1, 'unit_s_id': 1}, units, {}))
        row = {'price': 10, 'purchase_price': 9, '_m2m': {'taxes_ids': [1]}}
        self.assertTrue(historical_validation_issues('ab_product_source', row, {}, {1: {'percentage': 20}}))
        self.assertEqual(row['price'], 10)
        self.assertTrue(historical_validation_issues('ab_purchase_header', {'doc_code': 'ABC/123'}, {}, {}))
        self.assertFalse(historical_validation_issues('ab_purchase_header', {'doc_code': 'ABC-123'}, {}, {}))

    def test_unchanged_company_hierarchy_is_not_written(self):
        from types import SimpleNamespace
        engine = Importer.__new__(Importer)
        class Company:
            _fields = {'parent_id': SimpleNamespace(type='many2one'), 'name': SimpleNamespace(type='char')}
            def __getitem__(self, field):
                return SimpleNamespace(id=False) if field == 'parent_id' else 'Old name'
        self.assertEqual(engine.changed_values(Company(), {'parent_id': False, 'name': 'New name'}), {'name': 'New name'})

    def test_seed_limits_lookups_to_existing_target_identities(self):
        from unittest.mock import Mock
        engine = Importer.__new__(Importer)
        engine.db = sqlite3.connect(':memory:')
        engine.db.executescript('CREATE TABLE records(model TEXT,source_id INTEGER); CREATE TABLE xmlids(model TEXT,source_id INTEGER,xmlid TEXT UNIQUE);')
        engine.db.executemany('INSERT INTO xmlids VALUES (?,?,?)', [
            ('document', 1, '__export__.absent'), ('document', 2, '__export__.present'),
            ('res.company', 3, 'base.main_company'), ('res.groups', 4, 'old.group')])
        engine.db.execute("INSERT INTO records VALUES ('res.groups',5)")
        engine.rules = {'xmlids': {'old.group': 'new.group'}}
        engine.excluded_groups, engine.retired_fields = {}, {}
        engine.cr = Mock()
        engine.cr.fetchall.return_value = [('__export__','present'), ('base','main_company'), ('new','group')]
        engine.cr.fetchone.return_value = None
        engine.xml_matches = Mock(side_effect=lambda model, rid: rid + 100)
        engine.register = Mock()
        engine.seed()
        self.assertEqual({call.args[1] for call in engine.register.call_args_list}, {2, 3, 4, 5})
        self.assertEqual(engine.xml_matches.call_count, 4)
        engine.db.close()

    def test_retired_metadata_only_adapts_report_columns(self):
        engine = self.fixture_engine()
        engine.retired_fields = {42: {'name': '__last_update'}}
        self.assertEqual(engine.relation_ids('ab_accounting_account_statement', 'report_field_ids', 'ir.model.fields', [41, 42]), [41])
        self.assertEqual(engine.relation_ids('ab_accounting_recon_header', 'report_field_ids', 'ir.model.fields', [42]), [])
        with self.assertRaises(MigrationError):
            engine.relation_ids('ab_hr_report_model', 'target_field_id', 'ir.model.fields', [42])
        self.assertEqual(engine.relation_ids('other', 'links', 'business.record', [42]), [42])

    def test_cli_requires_only_four_explicit_arguments(self):
        args = parser().parse_args(['--source-config', '/source.conf', '--source-db', 'chosen_source',
                                    '--target-config', '/target.conf', '--target-db', 'chosen_target'])
        self.assertEqual(args.source_db, 'chosen_source')
        self.assertEqual(args.target_db, 'chosen_target')
        self.assertEqual(set(vars(args)), {'source_config', 'source_db', 'target_config', 'target_db', 'reset'})
        self.assertFalse(args.reset)



if __name__ == '__main__': unittest.main()
