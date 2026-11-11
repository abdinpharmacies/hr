"""Offline tests only: these must never create or connect to a database."""
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from psycopg2 import sql
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bulk import (BULK_FORMAT_VERSION, CopyWriter, choose_models, target_field,
                  copy_column_order, validate_bulk_manifest, export_snapshot)
from bulk_importer import BulkImporter
from common import MigrationError, loads
from legacy_migrate import legacy_main as main
from migrate import parser


def render(value):
    """Render composables offline for syntax tests; never execute this output."""
    if isinstance(value, sql.SQL):
        return value.string
    if isinstance(value, sql.Identifier):
        return '.'.join('"' + s.replace('"', '""') + '"' for s in value.strings)
    if isinstance(value, sql.Literal):
        obj = value.wrapped
        if obj is None:
            return 'NULL'
        if isinstance(obj, bool):
            return 'true' if obj else 'false'
        if isinstance(obj, (int, float)):
            return str(obj)
        return "'" + str(obj).replace("'", "''") + "'"
    if isinstance(value, sql.Composed):
        return ''.join(render(x) for x in value.seq)
    return str(value)


def metadata(name, fields=None, modules=None):
    return dict(table=name.replace('.', '_'), transient=False, table_kind='r', fields=fields or {},
                modules=modules or ['ab_accounting'])


class BulkTests(unittest.TestCase):
    def test_copy_order_survives_export_json_roundtrip_and_actual_loader(self):
        names = ['id', 'account_second_level_id', 'name', 'create_date']
        types = ['integer', 'integer', 'character varying', 'timestamp without time zone']
        columns = {name: {'type': typ} for name, typ in zip(names, types)}
        row = b'2\t7\tAccount\t2026-11-10 11:24:31\n'
        con = MagicMock()
        con.info.dbname = 'offline_source'
        cursor = con.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('2026-11-10', '1:1:')
        cursor.rowcount = 1
        exported = []
        def export(query, writer):
            exported.append(query)
            writer.write(row)
        cursor.copy_expert.side_effect = export
        info = {'source_version': '15.0', 'models': {'test': metadata('test')}}
        with tempfile.TemporaryDirectory() as directory, \
                patch('bulk.catalog', return_value={'test': columns}), \
                patch('bulk.constraints', return_value=[]), \
                patch('bulk.choose_models', return_value=['test']), \
                patch.object(sql.Composed, 'as_string', lambda query, connection: render(query)):
            stage = Path(directory)
            export_snapshot(con, stage, info, {'test': {'fields': {}}}, {})
            manifest = loads((stage / 'bulk-manifest.json').read_text())
            self.assertEqual(list(manifest['tables']['test']['columns']), sorted(names))
            self.assertEqual(manifest['tables']['test']['column_order'], names)
            self.assertEqual(copy_column_order('test', manifest['tables']['test']), names)
            engine = BulkImporter.__new__(BulkImporter)
            engine.stage, engine.manifest = stage, manifest
            engine.cr = MagicMock()
            engine.cr.fetchone.side_effect = [(None,), None, None, None]
            engine.report = {'tables': {}}
            engine.execute = MagicMock()
            engine.count = lambda query: 1
            imported = []
            def load(query, file):
                imported.append(query)
                self.assertEqual(file.read(), row)
            engine.cr._cnx.cursor.return_value.__enter__.return_value.copy_expert.side_effect = load
            engine.stage_tables()
            column_list = '(' + ','.join('"' + name + '"' for name in names) + ')'
            self.assertIn(column_list, exported[0])
            self.assertIn(column_list, imported[0])

    def test_invalid_column_orders_rejected(self):
        columns = {'id': {}, 'create_date': {}}
        for order in (None, [], ['id'], ['id', 'id'], ['id', 'other'],
                      ['id', 'create_date', 'other'], 'id,create_date', ['id', {}]):
            with self.subTest(order=order), self.assertRaisesRegex(MigrationError, 'column_order'):
                copy_column_order('test', {'columns': columns, 'column_order': order})

    def test_old_manifest_rejected_with_fresh_run_instruction(self):
        with self.assertRaisesRegex(MigrationError, 'fresh migration to a new target'):
            validate_bulk_manifest({'format_version': 2, 'complete': True})

    def test_later_invalid_table_rejected_before_any_staging_statement(self):
        engine = BulkImporter.__new__(BulkImporter)
        engine.manifest = {'format_version': BULK_FORMAT_VERSION, 'complete': True, 'tables': {
            'first': {'columns': {'id': {}}, 'column_order': ['id']},
            'second': {'columns': {'id': {}}, 'column_order': []}}}
        engine.execute = MagicMock()
        with self.assertRaisesRegex(MigrationError, 'second'):
            engine.stage_tables()
        engine.execute.assert_not_called()

    def test_explicit_database_names_and_old_options_rejected(self):
        args = ['--source-config', 'a', '--source-db', 'chosen', '--target-config', 'b', '--target-db', 'new']
        self.assertEqual(parser().parse_args(args).target_db, 'new')
        for extra in [['import'], ['--stage', '/tmp/old'], ['--source-frozen']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser().parse_args(args + extra)

    def test_same_database_rejected_before_connect(self):
        with patch('legacy_migrate.connect') as connect, self.assertRaises(MigrationError):
            main(['--source-config', 'a', '--source-db', 'same', '--target-config', 'b', '--target-db', 'same'])
        connect.assert_not_called()

    def test_existing_target_never_creates_stage_or_writes_database(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        with patch('legacy_migrate.connect', return_value=connection), patch('legacy_migrate.RUN_ROOT') as root:
            with self.assertRaisesRegex(MigrationError, 'already exists'):
                main(['--source-config', 'a', '--source-db', 'old', '--target-config', 'b', '--target-db', 'existing'])
            root.mkdir.assert_not_called()
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertTrue(cursor.execute.call_args.args[0].startswith('SELECT'))
        connection.close.assert_called_once()

    def test_full_eplus_scope_and_required_relations_without_dates(self):
        names = ['res.users', 'res.company', 'ab_document', 'abdin_eplus.r_sales_trans_h', 'abdin_eplus.vendor']
        models = {n: metadata(n, modules=['abdin_eplus'] if n.startswith('abdin_eplus') else ['ab_accounting']) for n in names}
        models['ab_document']['fields']['vendor'] = dict(ttype='many2one', relation='abdin_eplus.vendor')
        target = {n: {'fields': {'vendor': {}} if n == 'ab_document' else {}} for n in names}
        # A non-empty field metadata object mirrors the real registry.
        target['ab_document']['fields']['vendor'] = {'type': 'many2one'}
        result = choose_models({'models': models, 'roots': ['ab_document']}, target, {})
        self.assertEqual(set(result), set(names))

    def test_missing_business_model_fails_closed(self):
        info = {'models': {'ab_document': metadata('ab_document')}, 'roots': ['ab_document']}
        with self.assertRaises(MigrationError):
            choose_models(info, {}, {})

    def test_user_group_field_rename(self):
        field = {'relation_table': 'res_groups_users_rel'}
        self.assertIs(target_field({'res.users': {'fields': {'group_ids': field}}}, 'res.users', 'groups_id'), field)

    def test_copy_writer_hashes_bytes_without_decoding_or_reformatting(self):
        import hashlib
        out = io.BytesIO()
        data = b'1\t\\N\tArabic UTF8: \xd8\xa7\n'
        writer = CopyWriter(out, 'test')
        writer.write(data[:4]); writer.write(data[4:])
        self.assertEqual(out.getvalue(), data)
        self.assertEqual(writer.hash.hexdigest(), hashlib.sha256(data).hexdigest())
        self.assertEqual(writer.bytes, len(data))

    def make_engine(self):
        engine = BulkImporter.__new__(BulkImporter)
        engine.env = MagicMock()
        engine.env.__getitem__.return_value.default_get.return_value = {}
        engine.models = {'ab_test': metadata('ab_test', {
            'amount': {'ttype': 'float', 'store': True},
            'name': {'ttype': 'char', 'store': True},
            'user_id': {'ttype': 'many2one', 'relation': 'res.users', 'store': True}})}
        engine.schema = {'ab_test': {'table': 'ab_test', 'fields': {
            'amount': {'type': 'float'}, 'name': {'type': 'char', 'translate': True}, 'user_id': {'type': 'many2one'}}}}
        columns = {'id': {'type': 'integer'}, 'amount': {'type': 'double precision'},
                   'name': {'type': 'character varying'}, 'user_id': {'type': 'integer'}}
        engine.manifest = {'tables': {'ab_test': {'columns': columns, 'rows': 1}}}
        engine.physical = {'ab_test': {**columns, 'name': {'type': 'jsonb'}}}
        engine.rules = {'integer_links': {}, 'polymorphic': {}}
        engine.report = {'skipped_columns': [], 'unresolved_references': [], 'tables': {'ab_test': {}}}
        engine.prepared = {}
        engine.cr = MagicMock()
        engine.cr.rowcount = 1
        engine.batches = lambda table: iter([(None, 10, 1)])
        engine.queries = []
        engine.execute = lambda query, params=None: engine.queries.append((render(query), params))
        engine.count = lambda query, params=None: 0
        return engine

    def test_prepare_maps_links_and_translations_with_set_queries(self):
        engine = self.make_engine()
        values = engine.prepare('ab_test')
        self.assertIn('record_map', render(values['user_id']))
        self.assertIn('jsonb_build_object', render(values['name']))
        self.assertEqual(render(values['amount']), 's."amount"')
        self.assertFalse(engine.report['skipped_columns'])

    def test_unknown_populated_column_requires_adapter(self):
        engine = self.make_engine()
        engine.manifest['tables']['ab_test']['columns']['important'] = {'type': 'integer'}
        engine.models['ab_test']['fields']['important'] = {'ttype': 'integer', 'store': True}
        engine.count = lambda *args: 1
        # Make this check independent of the relation checker.
        engine.models['ab_test']['fields']['user_id'] = {'ttype': 'integer', 'store': True}
        with self.assertRaisesRegex(MigrationError, 'Populated source-only field'):
            engine.prepare('ab_test')

    def test_approved_eplus_column_is_skipped_without_dummy_field(self):
        engine = self.make_engine()
        model = 'abdin_eplus.customer'
        engine.models[model] = engine.models.pop('ab_test')
        engine.schema[model] = engine.schema.pop('ab_test')
        engine.manifest['tables']['ab_test']['columns']['claim_deliver_day'] = {'type': 'integer'}
        engine.models[model]['fields']['claim_deliver_day'] = {'ttype': 'integer', 'store': True}
        values = engine.prepare(model)
        self.assertNotIn('claim_deliver_day', values)
        self.assertIn({'model': model, 'field': 'claim_deliver_day'}, engine.report['skipped_columns'])

    def test_unsupported_type_conversion_fails_before_insert(self):
        engine = self.make_engine()
        engine.physical['ab_test']['amount'] = {'type': 'date'}
        with self.assertRaisesRegex(MigrationError, 'Unsupported SQL conversion'):
            engine.prepare('ab_test')
        self.assertFalse(any(q.startswith('INSERT') for q, _ in engine.queries))

    def test_generated_insert_has_explicit_columns_and_atomic_upsert(self):
        engine = self.make_engine()
        engine.load_model('ab_test', engine.prepare('ab_test'))
        queries = '\n'.join(q for q, _ in engine.queries)
        self.assertIn('ON CONFLICT (id) DO UPDATE', queries)
        self.assertIn('CREATE TABLE "accounting_migration_work"."prepared_0"', queries)
        self.assertNotIn('TRUNCATE', queries)
        self.assertNotIn('DISABLE TRIGGER', queries)

    def test_native_and_relation_sql_syntax(self):
        try:
            from pglast import parse_sql
        except ImportError:
            self.skipTest('Optional offline PostgreSQL parser is not installed')
        engine = self.make_engine()
        engine.cr = MagicMock()
        engine.cr.fetchall.return_value = []
        engine.cr.fetchone.side_effect = [(0,), (True,), (True,), ('seed',)]
        engine.rules.update(xmlids={}, unidentified_groups={})
        with tempfile.TemporaryDirectory() as directory:
            engine.stage = Path(directory)
            engine.map_ids()
        engine.schema['ab_test']['fields']['users'] = dict(relation_table='test_users_rel', column1='test_id', column2='user_id')
        engine.manifest['relations'] = {'test_users_rel': [dict(model='ab_test', field='users', related='res.users',
                                                             column1='test_id', column2='user_id')]}
        engine.report['tests'] = []
        engine.relations()
        for query, params in engine.queries:
            parse_sql(query.replace('%s', 'NULL'))

    def test_company_property_sql_syntax(self):
        try:
            from pglast import parse_sql
        except ImportError:
            self.skipTest('Optional offline PostgreSQL parser is not installed')
        engine = self.make_engine()
        engine.cr = MagicMock()
        engine.cr.fetchall.return_value = [('owner_id',)]
        engine.manifest['tables']['ir_property'] = {}
        engine.schema['ab_test']['fields']['owner_id'] = dict(type='many2one', company_dependent=True)
        engine.physical['ab_test']['owner_id'] = dict(type='jsonb')
        values = {}
        engine.property_expressions('ab_test', values)
        query = 'SELECT ' + render(values['owner_id']) + ' FROM source s'
        parse_sql(query)
        self.assertIn('LATERAL', query)
        self.assertIn('record_map', query)

    def test_sql_syntax_when_optional_parser_available(self):
        try:
            from pglast import parse_sql
        except ImportError:
            self.skipTest('Optional offline PostgreSQL parser is not installed')
        engine = self.make_engine()
        engine.load_model('ab_test', engine.prepare('ab_test'))
        engine.install_json_adapter()
        for query, params in engine.queries:
            parse_sql(query.replace('%s', 'NULL'))

    def test_historical_tax_query_parses_with_postgresql_keywords(self):
        try:
            from pglast import parse_sql
        except ImportError:
            self.skipTest('Optional PostgreSQL parser unavailable')
        engine = self.make_engine()
        engine.models = {'ab_product_source': {'table':'ab_product_source', 'fields': {
            'taxes_ids': {'relation_table':'ab_product_source_tax_rel','column1':'source_id','column2':'tax_id'}}},
            'ab_taxes': {'table':'ab_taxes'}}
        engine.manifest['tables']['ab_product_source_tax_rel'] = {}
        engine.cr.fetchall.return_value = []
        with tempfile.TemporaryDirectory() as directory:
            engine.stage = Path(directory)
            engine.historical_validation()
        self.assertEqual(len(engine.queries), 1)
        parse_sql(engine.queries[0][0])


if __name__ == '__main__':
    unittest.main()
