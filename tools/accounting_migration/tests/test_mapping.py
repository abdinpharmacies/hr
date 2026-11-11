"""Offline identity strategy, SQL consumer, and checkpoint compatibility tests."""
import copy
import tempfile
from unittest.mock import MagicMock, patch
import unittest
from psycopg2 import sql
from common import MigrationError
from resume import fingerprint
import test_bulk
import test_resume


class MappingTests(unittest.TestCase):
    def engine(self):
        engine = test_bulk.BulkTests().make_engine()
        name = 'abdin_eplus.example'
        engine.models[name] = engine.models.pop('ab_test')
        engine.schema[name] = engine.schema.pop('ab_test')
        engine.rules.update(xmlids={}, unidentified_groups={})
        engine.cr.fetchone.side_effect = [(0,), (True,), (True,), ('seed',)]
        engine.cr.fetchall.return_value = []
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        engine.stage = __import__('pathlib').Path(temporary.name)
        return engine, name

    def test_identity_map_creates_no_per_record_entries(self):
        engine, model = self.engine()
        engine.map_ids()
        queries = [q for q, _ in engine.queries]
        self.assertEqual(engine.mapping_modes[model], 'identity')
        self.assertFalse(any(q.startswith('INSERT INTO accounting_migration.record_map') for q in queries))
        self.assertTrue(any(q.startswith('INSERT INTO accounting_migration.model_plan') for q in queries))
        self.assertFalse(any('s.id+' in q for q in queries))
        self.assertEqual(engine.plan_records()[0]['source_rows'], 1)
        self.assertEqual(engine.plan_records()[0]['strategy'], 'identity')
        try:
            from pglast import parse_sql
        except ImportError:
            return
        for query in queries:
            parse_sql(query.replace('%s', 'NULL'))

    def test_seed_renumbering_moves_targets_not_source_records(self):
        from seeds import relocation_plan
        moves = relocation_plan('ab_test', {10, 20}, 20, {10, 20}, [(5, 10)])
        self.assertEqual({r['old_id']: r['new_id'] for r in moves}, {10: 5, 20: 21})

    def test_missing_primary_key_and_ambiguous_xml_rejected(self):
        engine, model = self.engine()
        engine.cr.fetchone.side_effect = [(0,), (False,)]
        with self.assertRaisesRegex(MigrationError, 'primary key'):
            engine.map_ids()
        engine, model = self.engine()
        engine.count = lambda query, params=None: int('HAVING count(*)>1' in test_bulk.render(query))
        with self.assertRaisesRegex(MigrationError, 'Ambiguous seeded XML identity'):
            engine.map_ids()

    def test_static_and_dynamic_resolution_preserve_source_membership(self):
        engine, model = self.engine()
        engine.mapping_modes = {model: 'identity'}
        expression = test_bulk.render(engine.mapped_expression(sql.Literal(model), sql.SQL('s.link_id')))
        self.assertIn('"accounting_migration_source"."ab_test"', expression)
        self.assertIn('m.id=s.link_id', expression)
        self.assertNotIn('record_map', expression)
        native = test_bulk.render(engine.mapped_expression(sql.Literal('res.users'), sql.SQL('s.user_id')))
        self.assertIn('record_map', native)
        dynamic = test_bulk.render(engine.mapped_expression(sql.SQL('s.res_model'), sql.SQL('s.res_id')))
        self.assertIn('CASE WHEN s.res_model=', dynamic)
        self.assertIn('ELSE (SELECT m.target_id', dynamic)
        for value in (None, 0, -5, 1000000):
            rendered = test_bulk.render(engine.mapped_expression(sql.Literal(model), sql.Literal(value)))
            self.assertIn('WHERE m.id=', rendered)
            self.assertNotIn('coalesce', rendered.lower())

    def test_identity_load_uses_own_id_and_only_updates_model_status(self):
        engine, model = self.engine()
        engine.mapping_modes = {model: 'identity'}
        engine.mapping_format = 3
        expressions = engine.prepare(model)
        self.assertEqual(test_bulk.render(expressions['id']), 's.id')
        engine.load_model(model, expressions)
        queries = '\n'.join(q for q, _ in engine.queries)
        self.assertNotIn('UPDATE accounting_migration.record_map', queries)
        self.assertIn("UPDATE accounting_migration.model_plan SET status='applied'", queries)
        engine.cr.commit.assert_not_called()

    def test_missing_identity_reference_is_not_silently_preserved(self):
        engine, model = self.engine()
        engine.mapping_modes = {model: 'identity'}
        engine.count = lambda *args: 1
        with self.assertRaisesRegex(MigrationError, 'Unmapped reference'):
            engine.check_link(model, 'parent_id', sql.Literal(model), sql.SQL('s.parent_id'))

    def test_many_to_many_both_directions_use_correct_relations(self):
        engine = test_bulk.BulkTests().make_engine()
        identity = 'abdin_eplus.example'
        engine.models[identity] = copy.deepcopy(engine.models['ab_test'])
        engine.models[identity]['table'] = 'eplus_example'
        engine.schema[identity] = copy.deepcopy(engine.schema['ab_test'])
        engine.schema[identity]['table'] = 'eplus_example'
        engine.mapping_modes = {identity: 'identity', 'ab_test': 'explicit'}
        engine.report['tests'] = []
        engine.manifest['relations'] = {}
        for i, (left, right) in enumerate([('ab_test', identity), (identity, 'ab_test')]):
            table = 'relation_' + str(i)
            engine.schema[left]['fields']['links'] = dict(relation_table=table, column1='left_id', column2='right_id')
            engine.manifest['relations'][table] = [dict(model=left, field='links', related=right, column1='left_id', column2='right_id')]
        engine.relations()
        queries = '\n'.join(q for q, _ in engine.queries)
        self.assertIn('SELECT id source_id,id target_id FROM "accounting_migration_source"."eplus_example"', queries)
        self.assertIn("WHERE model='ab_test'", queries)
        try:
            from pglast import parse_sql
        except ImportError:
            return
        for query, params in engine.queries:
            parse_sql(query.replace('%s', 'NULL'))

    def test_old_formats_cannot_be_used_for_strict_loading(self):
        engine, model = self.engine()
        for version in (1, 2, 99):
            with self.assertRaisesRegex(MigrationError, 'Unsupported mapping checkpoint'):
                engine.select_mapping_format({'format': version})
        engine.select_mapping_format(None)
        self.assertEqual(engine.mapping_format, 3)

    def test_mixed_checkpoint_plan_is_verified_and_restored(self):
        engine, model = self.engine()
        engine.mapping_modes = {model: 'identity'}
        records = engine.plan_records()
        engine.select_mapping_format({'format': 3})
        engine.cr.fetchall.return_value = [tuple(record[k] for k in ('model','strategy','source_table','target_table','source_rows','format')) for record in records]
        engine.restore_model_plan({'plans': records})
        self.assertTrue(engine.identity_model(model))
        with self.assertRaisesRegex(MigrationError, 'differs'):
            engine.restore_model_plan({'plans': []})

    def test_legacy_business_checkpoint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = test_resume.ResumeTests().engine(directory)
            with patch('bulk_importer.get_checkpoint', return_value={'identity': 'old', 'report': {'passed': True}}):
                with self.assertRaisesRegex(MigrationError, 'old ID policy'):
                    engine.run()
            engine.stage_tables.assert_not_called()
            engine.map_ids.assert_not_called()

    def test_membership_checks_keep_native_exists_and_identity_source_checks(self):
        engine, model = self.engine()
        engine.mapping_modes = {model: 'identity'}
        native = test_bulk.render(engine.mapping_exists(sql.Literal('res.users'), sql.SQL('s.user_id')))
        identity = test_bulk.render(engine.mapping_exists(sql.Literal(model), sql.SQL('s.parent_id')))
        self.assertTrue(native.startswith('EXISTS('))
        self.assertIn('record_map', native)
        self.assertTrue(identity.startswith('EXISTS('))
        self.assertIn('"accounting_migration_source"."ab_test"', identity)
        self.assertNotIn('record_map', identity)

    def test_empty_identity_model_uses_zero_mapping_rows(self):
        engine, model = self.engine()
        engine.manifest['tables']['ab_test']['rows'] = 0
        engine.map_ids()
        self.assertEqual(engine.plan_records()[0]['source_rows'], 0)
        self.assertFalse(any(q.startswith('INSERT INTO accounting_migration.record_map') for q, _ in engine.queries))

    def test_non_eplus_business_model_also_preserves_ids(self):
        engine, old = self.engine()
        engine.models['ab_test'] = engine.models.pop(old)
        engine.schema['ab_test'] = engine.schema.pop(old)
        engine.map_ids()
        self.assertEqual(engine.mapping_modes['ab_test'], 'identity')
        self.assertFalse(any(q.startswith('INSERT INTO accounting_migration.record_map') for q, _ in engine.queries))

    def test_old_mapping_is_archived_and_replanned(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = test_resume.ResumeTests().engine(directory)
            saved = {'identity': 'old', 'format': 1}
            engine.archive_old_mapping = MagicMock()
            with patch('bulk_importer.get_checkpoint', side_effect=lambda cr, name: saved if name == 'mapping' else None), \
                 patch('bulk_importer.put_checkpoint'), patch('bulk_importer.constraints', return_value=[]):
                engine.run()
            engine.archive_old_mapping.assert_called_once_with(saved)
            engine.map_ids.assert_called_once()
            self.assertEqual(engine.mapping_format, 3)

    def test_resume_model_plan_ignores_database_collation_order(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.models['abdin_eplus.example'] = copy.deepcopy(engine.models['ab_test'])
        engine.schema['abdin_eplus.example'] = copy.deepcopy(engine.schema['ab_test'])
        engine.mapping_format = 3
        engine.mapping_modes = {m:'identity' for m in engine.models}
        expected = engine.plan_records()
        columns = ('model','strategy','source_table','target_table','source_rows','format')
        engine.cr.fetchall.return_value = [tuple(r[k] for k in columns) for r in reversed(expected)]
        engine.restore_model_plan({'plans':expected})
        bad = list(engine.cr.fetchall.return_value)
        bad[0] = (*bad[0][:4], 999, bad[0][5])
        engine.cr.fetchall.return_value = bad
        with self.assertRaisesRegex(MigrationError, 'differs from its committed checkpoint'):
            engine.restore_model_plan({'plans':expected})
