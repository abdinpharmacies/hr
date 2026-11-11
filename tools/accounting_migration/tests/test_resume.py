"""Recovery tests use temporary files and fake cursors, never an implicit DB."""
import contextlib
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from psycopg2 import sql
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import MigrationError, save_json
from resume import (find_run, fingerprint, require_compatible, verify_staged,
                    legacy_evidence, get_checkpoint, put_checkpoint, assert_exclusive)
from bulk_importer import BulkImporter
from legacy_migrate import resume_run
import test_bulk


class ResumeTests(unittest.TestCase):
    def test_run_requires_unique_source_target_and_matching_token(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / 'one'
            stage.mkdir()
            marker = dict(source='old', database='new', ownership_token='token')
            save_json(stage / 'target.json', marker)
            self.assertEqual(find_run(root, 'old', 'new', 'accounting_migration:token')[0], stage)
            with self.assertRaisesRegex(MigrationError, 'ownership'):
                find_run(root, 'old', 'new', 'unowned')
            other = root / 'two'
            other.mkdir()
            save_json(other / 'target.json', marker)
            with self.assertRaisesRegex(MigrationError, 'exactly one'):
                find_run(root, 'old', 'new', 'accounting_migration:token')

    def test_checkpoint_fingerprint_is_order_independent_and_strict(self):
        self.assertEqual(fingerprint(dict(a=1, b=2)), fingerprint(dict(b=2, a=1)))
        self.assertTrue(require_compatible({'identity': 'v1'}, 'v1', 'mapping'))
        self.assertFalse(require_compatible(None, 'v1', 'mapping'))
        with self.assertRaisesRegex(MigrationError, 'Incompatible mapping'):
            require_compatible({'identity': 'v1'}, 'v2', 'mapping')

    def test_checkpoint_write_never_commits_on_its_own(self):
        cr = MagicMock()
        put_checkpoint(cr, 'copy:table', {'identity': 'x'})
        cr.commit.assert_not_called()
        cr.fetchone.return_value = ('{"identity":"x"}',)
        self.assertEqual(get_checkpoint(cr, 'copy:table'), {'identity': 'x'})

    def test_active_target_session_blocks_without_termination(self):
        cr = MagicMock()
        cr.fetchall.return_value = [(123,)]
        with self.assertRaisesRegex(MigrationError, 'Other sessions'):
            assert_exclusive(cr, 'test')
        self.assertNotIn('terminate', cr.execute.call_args.args[0])

    def test_staging_validation_checks_schema_count_and_primary_index(self):
        meta = dict(column_order=['id'], columns={'id': {'type': 'integer'}}, rows=2)
        cr = MagicMock()
        cr.fetchall.return_value = [('id', 'integer')]
        cr.fetchone.side_effect = [(2,), (True,)]
        verify_staged(cr, 'test', meta)
        cr.fetchone.side_effect = [(1,)]
        with self.assertRaisesRegex(MigrationError, 'row count'):
            verify_staged(cr, 'test', meta)
        cr.fetchone.side_effect = [(False,)]
        with self.assertRaisesRegex(MigrationError, 'index'):
            verify_staged(cr, 'test', meta, count_rows=False)
        cr.fetchall.return_value = [('other', 'integer')]
        with self.assertRaisesRegex(MigrationError, 'schema'):
            verify_staged(cr, 'test', meta)

    def test_legacy_adoption_requires_original_complete_evidence_and_empty_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            archived = stage / 'attempts' / 'old'
            archived.mkdir(parents=True)
            save_json(archived / 'bulk-error.json', {'phase': 'schema adaptation'})
            save_json(archived / 'verification.json', {'passed': False, 'tables': {'test': {'source_rows': 2}}})
            save_json(stage / 'bulk-error.json', {'phase': 'staging validation'})
            save_json(stage / 'verification.json', {'passed': False})
            manifest = {'tables': {'test': {'rows': 2}}}
            cr = MagicMock()
            cr.fetchone.return_value = (0,)
            self.assertEqual(legacy_evidence(stage, manifest, cr)['tables']['test']['source_rows'], 2)
            cr.fetchone.return_value = (1,)
            with self.assertRaisesRegex(MigrationError, 'committed identity'):
                legacy_evidence(stage, manifest, cr)
            cr.fetchone.return_value = (0,)
            manifest['tables']['test']['rows'] = 3
            with self.assertRaisesRegex(MigrationError, 'failure evidence'):
                legacy_evidence(stage, manifest, cr)

    def engine(self, directory):
        engine = test_bulk.BulkTests().make_engine()
        engine.stage = Path(directory)
        engine.rules = {'xmlids': {}}
        engine.report = dict(tables={}, tests=[], excluded_roles=[])
        engine.manifest['complete'] = True
        engine.manifest['relations'] = {}
        engine.validate_language_setup = MagicMock()
        engine.stage_tables = MagicMock(side_effect=lambda: setattr(engine, 'manifest_id', fingerprint(engine.manifest)))
        engine.early_validation = MagicMock()
        def mapping():
            engine.excluded_group_ids, engine.retired_field_ids = [], []
            engine.mapping_modes = {model: 'identity' for model in engine.models}
            engine.seed_moves, engine.seed_fingerprints, engine.seed_references, engine.seed_surplus = [], {}, [], {}
            engine.cr.fetchall.return_value = [tuple(r[k] for k in ('model','strategy','source_table','target_table','source_rows','format')) for r in engine.plan_records()]
        engine.map_ids = MagicMock(side_effect=mapping)
        engine.prepare_working_tables = MagicMock()
        engine.check_seed_state = MagicMock()
        engine.relocate_seeds = MagicMock()
        engine.restore_business_xmlids = MagicMock()
        engine.prepare = MagicMock(return_value={'id': sql.SQL('s.id')})
        engine.load_model = MagicMock()
        for method in ('historical_validation', 'defer_constraints', 'replace_calendar_seed_schedules',
                       'relations', 'files', 'verify'):
            setattr(engine, method, MagicMock())
        return engine

    def test_mapping_commit_survives_business_failure_and_is_skipped_next_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            saved, pending = {}, {}
            def put(cr, name, value): pending[name] = copy.deepcopy(value)
            def commit(): saved.update(copy.deepcopy(pending)); pending.clear()
            engine.cr.commit.side_effect = commit
            engine.cr.rollback.side_effect = pending.clear
            engine.load_model.side_effect = MigrationError('business failed')
            with patch('bulk_importer.get_checkpoint', side_effect=lambda cr, name: saved.get(name)), \
                 patch('bulk_importer.put_checkpoint', side_effect=put), patch('bulk_importer.constraints', return_value=[]):
                with self.assertRaisesRegex(MigrationError, 'business failed'):
                    engine.run()
                self.assertIn('mapping', saved)
                self.assertNotIn('business', saved)
                engine.cr.rollback.assert_called_once()
                engine.load_model.side_effect = None
                engine.run()
                self.assertEqual(engine.map_ids.call_count, 1)
                self.assertIn('business', saved)
                engine.stage_tables.reset_mock()
                engine.run()
                engine.stage_tables.assert_not_called()

    def test_validation_aggregates_models_and_does_not_write_business_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.models['another'] = copy.deepcopy(engine.models['ab_test'])
            engine.prepare.side_effect = MigrationError('bad reference')
            with patch('bulk_importer.get_checkpoint', return_value=None), \
                 patch('bulk_importer.put_checkpoint'), patch('bulk_importer.constraints', return_value=[]):
                with self.assertRaisesRegex(MigrationError, '2 model validation failures'):
                    engine.run()
                engine.load_model.assert_not_called()
                self.assertEqual(len(json.loads((Path(directory) / 'validation-errors.json').read_text())), 2)

    def test_mapping_failure_does_not_commit_mapping_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = self.engine(directory)
            engine.map_ids.side_effect = MigrationError('mapping failed')
            with patch('bulk_importer.get_checkpoint', return_value=None), patch('bulk_importer.put_checkpoint') as put:
                with self.assertRaisesRegex(MigrationError, 'mapping failed'):
                    engine.run()
                put.assert_not_called()
                engine.cr.commit.assert_not_called()
                engine.cr.rollback.assert_called_once()

    def test_complete_database_uses_database_report_instead_of_stale_file(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            manifest = {'complete': True, 'tables': {}}
            save_json(stage / 'bulk-manifest.json', manifest)
            save_json(stage / 'verification.json', {'passed': False})
            con = MagicMock()
            cr = con.cursor.return_value.__enter__.return_value
            cr.fetchone.side_effect = [('accounting_migration.run',), ('old', 'new')]
            args = MagicMock(source_db='old', target_db='new')
            with patch('legacy_migrate.connect', return_value=con), patch('legacy_migrate.assert_exclusive'), \
                 patch('legacy_migrate.get_checkpoint', side_effect=[None, {'identity': fingerprint(manifest), 'id_policy': 'preserve_business_ids_v1', 'report': {'passed': True}}]), \
                 patch('legacy_migrate.worker') as worker:
                self.assertTrue(resume_run(args, stage, {})['passed'])
                worker.assert_not_called()
                self.assertTrue(json.loads((stage / 'verification.json').read_text())['passed'])

    def test_committed_copy_is_skipped_without_reading_source_file(self):
        engine = test_bulk.BulkTests().make_engine()
        meta = engine.manifest['tables']['ab_test']
        meta.update(column_order=list(meta['columns']), rows=1, bytes=1, sha256='unused')
        engine.manifest.update(complete=True, format_version=3)
        engine.cr.fetchone.return_value = ('accounting_migration_source',)
        engine.stage = Path('/intentionally/nonexistent')
        checkpoints = {'manifest': {'identity': fingerprint(engine.manifest)},
                       'copy:ab_test': {'identity': fingerprint(meta)}}
        with patch('bulk_importer.get_checkpoint', side_effect=lambda cr, name: checkpoints.get(name)), \
             patch('bulk_importer.bind_manifest', return_value='snapshot'), patch('bulk_importer.verify_staged') as verify:
            engine.stage_tables()
            engine.cr._cnx.cursor.assert_not_called()
            verify.assert_called_once_with(engine.cr, 'ab_test', meta, count_rows=False)
            self.assertTrue(engine.report['tables']['ab_test']['reused'])

    def test_failed_copy_has_no_table_checkpoint_or_table_commit(self):
        engine = test_bulk.BulkTests().make_engine()
        meta = engine.manifest['tables']['ab_test']
        meta.update(column_order=list(meta['columns']), rows=1, bytes=1, sha256='hash')
        engine.manifest.update(complete=True, format_version=3)
        engine.cr.fetchone.return_value = (None,)
        with tempfile.TemporaryDirectory() as directory:
            engine.stage = Path(directory)
            (engine.stage / 'tables').mkdir()
            (engine.stage / 'tables' / 'ab_test.copy').write_bytes(b'x')
            engine.cr._cnx.cursor.return_value.__enter__.return_value.copy_expert.side_effect = RuntimeError('interrupted COPY')
            with patch('bulk_importer.get_checkpoint', return_value=None), \
                 patch('bulk_importer.bind_manifest', return_value='snapshot'), \
                 patch('bulk_importer.digest', return_value='hash'), patch('bulk_importer.put_checkpoint') as put, \
                 patch.object(__import__('psycopg2').sql.Composed, 'as_string', lambda q, con: test_bulk.render(q)):
                with self.assertRaisesRegex(RuntimeError, 'interrupted COPY'):
                    engine.stage_tables()
                put.assert_not_called()
                # Only schema/manifest preparation commits; failed table does not.
                self.assertEqual(engine.cr.commit.call_count, 1)

    def test_resume_complete_extraction_does_not_connect_to_source(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            manifest = {'complete': True}
            save_json(stage / 'bulk-manifest.json', manifest)
            con = MagicMock()
            cr = con.cursor.return_value.__enter__.return_value
            cr.fetchone.side_effect = [('accounting_migration.run',), ('old', 'new')]
            args = MagicMock(source_db='old', target_db='new')
            order = []
            def run_worker(args, stage, command, modules=()):
                order.append(command)
                if command == 'bulk-smoke':
                    save_json(stage / 'verification.json', {'passed': True})
            with patch('legacy_migrate.connect', return_value=con) as connect, patch('legacy_migrate.assert_exclusive'), \
                 patch('legacy_migrate.get_checkpoint', side_effect=[{'identity': fingerprint(manifest)}, None, None]), \
                 patch('legacy_migrate.worker', side_effect=run_worker):
                self.assertTrue(resume_run(args, stage, {'modules': ['ab_accounting']})['passed'])
                connect.assert_called_once_with(args.target_config, 'new')
                self.assertEqual(order, ['init-target', 'bulk-import', 'bulk-smoke'])

    def test_bound_manifest_change_is_rejected_before_worker_upgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            save_json(stage / 'bulk-manifest.json', {'complete': False})
            con = MagicMock()
            cr = con.cursor.return_value.__enter__.return_value
            cr.fetchone.side_effect = [('accounting_migration.run',), ('old', 'new')]
            args = MagicMock(source_db='old', target_db='new')
            with patch('legacy_migrate.connect', return_value=con), patch('legacy_migrate.assert_exclusive'), \
                 patch('legacy_migrate.get_checkpoint', side_effect=[{'identity': 'original'}, None, None]), \
                 patch('legacy_migrate.worker') as worker:
                with self.assertRaisesRegex(MigrationError, 'manifest missing or changed'):
                    resume_run(args, stage, {'modules': []})
                worker.assert_not_called()

    def test_interrupted_extraction_restarts_all_files_in_one_new_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            save_json(stage / 'bulk-manifest.json', {'complete': False})
            save_json(stage / 'target-schema.json', {})
            (stage / 'tables').mkdir()
            (stage / 'tables' / 'partial.copy').write_text('old snapshot')
            target, source = MagicMock(), MagicMock()
            source.__enter__.return_value = source
            cr = target.cursor.return_value.__enter__.return_value
            cr.fetchone.side_effect = [('accounting_migration.run',), ('old', 'new')]
            args = MagicMock(source_db='old', target_db='new')
            from adapters import SUPPORT_MODULES
            marker = dict(modules=sorted(set(SUPPORT_MODULES) | {'abdin_eplus'}), required_languages=['en_US', 'ar_001'])
            def export(con, directory, *unused):
                self.assertIs(con, source)
                self.assertFalse((directory / 'tables').exists())
                save_json(directory / 'verification.json', {'passed': True})
            with patch('legacy_migrate.connect', side_effect=[target, source]), patch('legacy_migrate.assert_exclusive'), \
                 patch('legacy_migrate.get_checkpoint', return_value=None), patch('legacy_migrate.worker'), \
                 patch('legacy_migrate.monitor_factory'), patch('legacy_migrate.settings', return_value={}), \
                 patch('legacy_migrate.source.inventory', return_value={'modules': []}), \
                 patch('legacy_migrate.discover_languages', return_value=marker['required_languages']), \
                 patch('legacy_migrate.export_snapshot', side_effect=export) as exporter:
                self.assertTrue(resume_run(args, stage, marker)['passed'])
                exporter.assert_called_once()
                self.assertEqual(len(list(stage.glob('incomplete-extraction-*/tables/partial.copy'))), 1)

    def test_early_required_field_failures_aggregate_before_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = test_bulk.BulkTests().make_engine()
            engine.stage = Path(directory)
            engine.physical = copy.deepcopy(engine.physical)
            engine.physical['ab_test']['name']['required'] = True
            engine.physical['ab_test']['amount']['required'] = True
            engine.cr.fetchone.return_value = (2,)
            engine.cr.fetchall.return_value = [(11,), (12,)]
            with self.assertRaisesRegex(MigrationError, '2 schema/required-value issues'):
                engine.early_validation()
            report = json.loads((engine.stage / 'preflight-errors.json').read_text())
            self.assertEqual({p['field'] for p in report}, {'name', 'amount'})
            self.assertTrue(all(p['count'] == 2 and p['ids'] == [11, 12] for p in report))
