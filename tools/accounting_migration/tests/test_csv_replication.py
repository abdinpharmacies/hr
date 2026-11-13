"""Offline contracts for CSV projection, selection, and CLI isolation."""
import csv
import copy
import hashlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError, save_json, loads
from csv_copy import ProjectionReader, unescape_copy
from csv_plan import HEADERS, LEGACY_HEADERS, VERSION, read_plan, relation_scope, target_selection_choices, selection_cell, table_existance
from migrate import parser, main
from csv_actions import choose_actions, copy_filestore
from csv_relations import record_batches, plan_m2m, plan_operations
from csv_verify import compare, verify_after


class CSVOfflineTests(unittest.TestCase):
    def test_count_verification_never_reads_or_projects_source_records(self):
        con, mapper = MagicMock(), MagicMock()
        con.cursor.return_value.__enter__.return_value.fetchone.return_value = (29463325,)
        mapper.rows.side_effect = AssertionError('source records scanned')
        result = compare(con, '/missing-stage', 'huge_table', {'rows': 29463325}, {},
                         dict(mode='replace', constants={'name': 'changed'}), mapper)
        self.assertTrue(result['matches'])
        self.assertEqual(result['policy'], 'csv_count_v1')
        self.assertNotIn('sha256', result['actual'])
        self.assertNotIn('artifact', result)
        mapper.rows.assert_not_called()
        con.cursor.return_value.__enter__.return_value.copy_expert.assert_not_called()
        self.assertIn('SELECT count(*)', str(con.cursor.return_value.__enter__.return_value.execute.call_args))

    def test_count_verification_distinguishes_replace_and_additive_rules(self):
        con = MagicMock()
        con.cursor.return_value.__enter__.return_value.fetchone.return_value = (5,)
        self.assertFalse(compare(con, None, 't', {'rows': 3}, {}, dict(mode='replace'))['matches'])
        self.assertTrue(compare(con, None, 't', {'rows': 3}, {}, dict(mode='add'))['matches'])
        previous = dict(actual=dict(rows=2), expected=dict(rows=100))
        self.assertTrue(verify_after(con, None, 't', {}, dict(mode='add'), previous, copied_rows=3)['matches'])

    def test_projection_preserves_escapes_and_explicit_nulls_in_small_reads(self):
        raw = b'1\ttext\\twith\\nnewlines\\\\and\\N\t\\N\n2\t\tfalse\n'
        file = io.BytesIO(raw)
        reader = ProjectionReader(file, ['id', 'name', 'flag'], ['name', 'id', 'target', 'flag'], {'flag': b'f'})
        chunks = []
        while True:
            part = reader.read(3)
            if not part:
                break
            self.assertLessEqual(len(part), 3)
            chunks.append(part)
        self.assertEqual(b''.join(chunks), b'text\\twith\\nnewlines\\\\and\\N\t1\t\\N\tf\n\t2\t\\N\tf\n')
        self.assertEqual(reader.hash.hexdigest(), hashlib.sha256(raw).hexdigest())
        self.assertEqual(unescape_copy(b'a\\tb\\\\c'), 'a\tb\\c')
        self.assertIsNone(unescape_copy(b'\\N'))

    def test_direct_reader_does_not_parse_or_reencode_payload(self):
        payload = b'42\t\\N\t\\\\N\t\n'
        reader = ProjectionReader(io.BytesIO(payload), ['id', 'a', 'b', 'c'], ['id', 'a', 'b', 'c'], {})
        self.assertTrue(reader.direct)
        self.assertEqual(reader.read(100), payload)
        self.assertEqual(reader.read(100), b'')

    def test_malformed_copy_width_or_truncation_fails(self):
        for payload in (b'1\n', b'1\tx'):
            with self.subTest(payload=payload), self.assertRaises(MigrationError):
                ProjectionReader(io.BytesIO(payload), ['id', 'x'], ['id', 'extra'], {}).read()

    def plan(self, path, action='1', constants='{}', version=VERSION):
        meta = dict(version=version, tables=['ab_record'], source={'columns': {'ab_record': {'id': {}, 'name': {}}}},
                    target={'columns': {'ab_record': {'id': {'generated': False}, 'name': {'generated': False}}}})
        save_json(str(path) + '.metadata.json', meta)
        with path.open('w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(LEGACY_HEADERS if version == 1 else HEADERS)
            cells = ['{"name":"quoted, sample"}', '{}'] if version == 1 else ['both', '{"available_target_selections":{}}']
            writer.writerow(['ab_record', 'custom', *cells, '[]', '[]', action, constants, '[]', '[]'])

    def test_selection_validation_and_constant_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.csv'
            for constants in ('{"id":1}', '[]', '{invalid', '{"unknown":1}'):
                self.plan(path, constants=constants)
                with self.assertRaises(MigrationError):
                    read_plan(path)
            self.plan(path, constants='{"name":false}')
            self.assertEqual(read_plan(path)[1], {'ab_record': {'name': False}})
            self.plan(path, action='')
            self.assertEqual(read_plan(path)[1], {})
            self.plan(path, action='yes')
            with self.assertRaises(MigrationError):
                read_plan(path)

    def test_cli_modes_are_exclusive_and_export_dispatch_isolated(self):
        args = ['--source-config', 'a', '--source-db', 's', '--target-config', 'b', '--target-db', 't']
        with patch('sys.stderr', io.StringIO()):
            with self.assertRaises(SystemExit):
                parser().parse_args(args + ['--reset', '--table-plan', 'x'])
        with patch('csv_plan.export_plan', return_value={'status': 'plan_exported'}) as export, \
                patch('prepared.run', side_effect=AssertionError('legacy importer invoked')), \
                patch('sys.stdout', io.StringIO()):
            self.assertEqual(main(args + ['--export-table-plan', 'x'])['status'], 'plan_exported')
            export.assert_called_once()

    def test_relation_mode_accounts_for_all_registered_owners(self):
        relation = dict(model='ab_a', field='links', table='a_b_rel', columns=['a_id', 'b_id'])
        other = dict(model='ab_b', field='links', table='a_b_rel', columns=['b_id', 'a_id'])
        side = dict(models={'ab_a': 'ab_a', 'ab_b': 'ab_b'}, relations=[relation, other],
                    columns={'a_b_rel': {'a_id': {}, 'b_id': {}}, 'ab_a': {'id': {}}, 'ab_b': {'id': {}}})
        self.assertEqual(relation_scope({'source': side, 'target': side}, {'ab_a': {}})['a_b_rel']['mode'], 'add')
        self.assertEqual(relation_scope({'source': side, 'target': side}, {'ab_a': {}, 'ab_b': {}})['a_b_rel']['mode'], 'replace')

    def test_physical_m2m_roles_match_renamed_fields_but_not_reversed_endpoints(self):
        source = dict(models={'a': 'a', 'b': 'b'}, columns={'rel': {'a_id': {}, 'b_id': {}}, 'a': {'id': {}}, 'b': {'id': {}}},
                      relations=[dict(model='a', field='old_name', table='rel', columns=['a_id', 'b_id'], related='b')])
        target = {**source, 'relations': [{**source['relations'][0], 'field': 'new_name'}]}
        result = plan_m2m(source, target, {'a': {}})
        self.assertEqual(result['rel']['references']['b_id']['source_model'], 'b')
        target['relations'][0]['columns'] = ['b_id', 'a_id']
        with self.assertRaisesRegex(MigrationError, 'binding differs'):
            plan_m2m(source, target, {'a': {}})

    def test_mapping_record_batches_are_bounded_by_bytes_as_well_as_count(self):
        rows = [[b'a' * 5], [b'b' * 5], [b'c' * 20], [b'd']]
        batches = list(record_batches(iter(rows), byte_limit=6))
        self.assertEqual([len(batch) for batch in batches], [1, 1, 1, 1])
        self.assertEqual([row for batch in batches for row in batch], rows)

    def relation_fixture(self):
        return dict(models={'a': 'a', 'b': 'b'}, columns={'a': {'id': {}}, 'b': {'id': {}},
                    'rel': {'a_id': {}, 'b_id': {}}},
                    relations=[dict(model='a', related='b', field='links', table='rel', columns=['a_id', 'b_id'])])

    def test_one_sided_m2m_tables_are_skipped_before_strict_binding(self):
        for missing in ('source', 'target'):
            with self.subTest(missing=missing):
                source = self.relation_fixture()
                target = copy.deepcopy(source)
                side = source if missing == 'source' else target
                del side['columns']['rel']
                # Missing physical tables must be excluded even with stale fields.
                side['relations'][0]['columns'] = ['b_id', 'a_id']
                if missing == 'source':
                    side['relations'] = []
                exclusions = []
                self.assertEqual(plan_m2m(source, target, {'a': {}}, exclusions), {})
                self.assertEqual(exclusions[0]['reason'], 'missing_' + missing + '_table')

    def test_common_m2m_with_one_sided_endpoint_is_excluded(self):
        source = self.relation_fixture()
        target = copy.deepcopy(source)
        del target['columns']['b']
        del target['models']['b']
        exclusions = []
        self.assertEqual(plan_m2m(source, target, {'a': {}}, exclusions), {})
        self.assertEqual(exclusions[0]['reason'], 'endpoint_table_not_both')
        self.assertEqual(exclusions[0]['endpoints'][0]['table'], 'b')

    def test_common_physical_relation_without_target_declaration_still_fails(self):
        source = self.relation_fixture()
        target = copy.deepcopy(source)
        target['relations'] = []
        with self.assertRaisesRegex(MigrationError, 'binding differs'):
            plan_m2m(source, target, {'a': {}})

    def test_operations_filter_one_sided_models_without_raw_id_selection(self):
        source = self.relation_fixture()
        target = copy.deepcopy(source)
        del target['columns']['b']
        exclusions = []
        self.assertEqual(set(plan_operations(source, target, {'a': {}, 'b': {}}, exclusions)), {'a'})
        self.assertEqual({item['kind'] for item in exclusions}, {'model', 'm2m'})

    def test_csv_existance_cell_does_not_override_physical_eligibility(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.csv'
            self.plan(path)
            metadata = Path(str(path) + '.metadata.json')
            meta = loads(metadata.read_text())
            del meta['target']['columns']['ab_record']
            save_json(metadata, meta)
            exclusions = []
            self.assertEqual(read_plan(path, exclusions)[1], {})
            self.assertEqual(exclusions[0]['reason'], 'missing_target_table')

    def test_optional_filestore_copy_reuses_files_and_never_overwrites_conflicts(self):
        from types import SimpleNamespace
        self.assertEqual(choose_actions(None, {}), [])
        with self.assertRaises(MigrationError):
            choose_actions('copy-filestore', {})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config.ini'
            config.write_text('[options]\ndata_dir = ' + str(root) + '\n')
            args = SimpleNamespace(source_config=str(config), target_config=str(config), source_db='s', target_db='t')
            source, target = root / 'filestore/s', root / 'filestore/t'
            (source / 'ab').mkdir(parents=True)
            (source / 'ab/file').write_bytes(b'first content')
            target.mkdir()
            (target / 'old').write_bytes(b'preserve')
            completed = {}
            first = copy_filestore(args, completed, lambda: None)
            self.assertEqual(first['copied'], 1)
            self.assertEqual(copy_filestore(args, completed, lambda: None)['reused'], 1)
            self.assertEqual((target / 'old').read_bytes(), b'preserve')
            (source / 'ab/file').write_bytes(b'conflicting content')
            with self.assertRaises(MigrationError):
                copy_filestore(args, completed, lambda: None)
            self.assertEqual((target / 'ab/file').read_bytes(), b'first content')

    def test_target_only_selection_keys_preserve_order_and_combine_owners(self):
        con = MagicMock()
        con.cursor.return_value.__enter__.return_value.__iter__.return_value = iter([
            ('ab_a', 'position', 'sided'), ('ab_a', 'position', 'bottom'),
            ('ab_a', 'dynamic', None), ('ab_a', 'shared', 'old'),
            ('ab_a', 'nonstored', 'skip'), ('ab_alias', 'position', 'bottom'),
            ('ab_alias', 'position', 'top'), ('transient', 'x', 'skip')])
        source = dict(columns={'ab_table': {'shared': {}}})
        target = dict(models={'ab_a': 'ab_table', 'ab_alias': 'ab_table'},
                      columns={'ab_table': {'position': {}, 'dynamic': {}, 'shared': {}}})
        result = target_selection_choices(con, source, target)
        self.assertEqual(result, {'ab_table': {'position': ['sided', 'bottom', 'top'], 'dynamic': None}})
        self.assertEqual(selection_cell(result, 'other'), '{"available_target_selections": {}}')

    def test_legacy_and_new_header_versions_remain_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'plan.csv'
            results = []
            for version in (1, VERSION):
                self.plan(path, constants='{"name":"bottom"}', version=version)
                results.append(read_plan(path)[1])
            self.assertEqual(results[0], results[1])

    def test_table_existance_uses_catalog_presence(self):
        source = {'columns': {'shared': {}, 'source': {}}}
        target = {'columns': {'shared': {}, 'target': {}}}
        self.assertEqual(table_existance('shared', source, target), 'both')
        self.assertEqual(table_existance('source', source, target), 'source_only')
        self.assertEqual(table_existance('target', source, target), 'target_only')
        with self.assertRaises(MigrationError):
            table_existance('missing', source, target)
