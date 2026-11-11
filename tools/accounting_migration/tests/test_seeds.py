"""Offline strict-ID planning, reference SQL, and XML-ID policy regressions."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import unittest
from psycopg2 import sql
from seeds import relocation_plan, require_strict, STRICT_POLICY
from common import MigrationError
import test_bulk


class SeedTests(unittest.TestCase):
    def test_swap_uses_disjoint_temporary_ids(self):
        moves = relocation_plan('res.partner', {1, 2}, 2, {1, 2}, [(2, 1), (1, 2)])
        self.assertEqual([(m['old_id'], m['new_id']) for m in moves], [(1, 2), (2, 1)])
        self.assertTrue(all(m['temp_id'] > 2 for m in moves))
        self.assertEqual(len({m['temp_id'] for m in moves}), 2)

    def test_unrelated_seed_moves_above_source_maximum(self):
        moves = relocation_plan('ab_product', {1, 99}, 500, {1}, [])
        self.assertEqual([(m['old_id'],m['new_id']) for m in moves], [(1,501)])
        self.assertGreater(moves[0]['temp_id'], 501)
        self.assertEqual(relocation_plan('ab_product', set(), 500, set(), []), [])
        self.assertEqual(relocation_plan('ab_product', {7}, 10, {7}, [(7,7)]), [])

    def test_ambiguous_and_contradictory_identity_rejected(self):
        for pairs in ([(1,1),(1,2)], [(1,1),(2,1)]):
            with self.assertRaises(MigrationError):
                relocation_plan('res.country', {1,2}, 10, {1,2}, pairs)

    def test_superuser_and_integer_range_protected(self):
        self.assertEqual(relocation_plan('res.users', {1}, 1, {1}, [(1,1)]), [])
        for pairs in ([], [(2,1)]):
            with self.assertRaisesRegex(MigrationError, 'superuser'):
                relocation_plan('res.users', {1}, 2, {1}, pairs)
        with self.assertRaisesRegex(MigrationError, 'integer ID space'):
            relocation_plan('ab_test', {1}, 2147483647, {1}, [])

    def test_old_completed_data_is_never_accepted(self):
        for checkpoint in ({'format':1}, {'format':2}, {'report':{'passed':True}}):
            with self.assertRaisesRegex(MigrationError, 'old ID policy'):
                require_strict(checkpoint)
        require_strict({'id_policy':STRICT_POLICY})
        with self.assertRaisesRegex(MigrationError, 'missing'):
            require_strict(None, required=True)

    def test_every_seed_reference_adapter_generates_valid_sql(self):
        try:
            from pglast import parse_sql
        except ImportError:
            self.skipTest('Optional PostgreSQL parser unavailable')
        engine = test_bulk.BulkTests().make_engine()
        descriptors = [
            ('scalar','example','company_id','res.company',''),
            ('polymorphic','example','res_id','','res_model'),
            ('model_reference','example','res_id','','res_model_id'),
            ('reference','example','ref','',''),
            ('parent_path','example','parent_path','res.partner',''),
            ('company_json','example','property','res.partner',''),
            ('defaults','ir_default','json_value','',''),
            ('config','ir_config_parameter','value','','')]
        for descriptor in descriptors:
            for before, after in [('old_id','temp_id'),('temp_id','new_id')]:
                engine.rewrite_seed_reference(descriptor,before,after)
        for query, params in engine.queries:
            parse_sql(query.replace('%s', 'NULL'))
        engine.cr.commit.assert_not_called()

    def test_seed_relocation_has_two_steps_and_no_internal_commit(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.seed_moves = relocation_plan('ab_test', {1,2}, 2, {1,2}, [(2,1),(1,2)])
        engine.seed_references = [('scalar','related','parent_id','ab_test','')]
        engine.relocate_seeds()
        queries = [q for q,_ in engine.queries]
        self.assertEqual(len(queries), 4)
        self.assertIn('SET id=m."temp_id"', queries[0])
        self.assertIn('SET "parent_id"=m."temp_id"', queries[1])
        self.assertIn('SET id=m."new_id"', queries[2])
        self.assertIn('SET "parent_id"=m."new_id"', queries[3])
        engine.cr.commit.assert_not_called()

    def test_xmlid_restoration_is_scoped_and_preserves_target_flags(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.restore_business_xmlids()
        queries = '\n'.join(q for q,_ in engine.queries)
        self.assertIn('JOIN "accounting_migration_source"."ab_test" s ON s.id=x.res_id', queries)
        self.assertIn('INSERT INTO ir_model_data(module,name,model,res_id,noupdate)', queries)
        self.assertNotIn('UPDATE ir_model_data', queries)
        self.assertIn('s.res_id,true', queries)
        self.assertIn('source_noupdate', queries)
        self.assertNotIn('INSERT INTO ir_model_data(id', queries)
        engine.cr.commit.assert_not_called()
        try:
            from pglast import parse_sql
        except ImportError:
            return
        for query, params in engine.queries:
            parse_sql(query.replace('%s', 'NULL'))

    def test_xmlid_conflict_blocks_before_insert(self):
        engine = test_bulk.BulkTests().make_engine()
        def check(query, params, message):
            if 'conflicts with installed' in message:
                raise MigrationError(message)
        engine.fail_if = check
        with self.assertRaisesRegex(MigrationError, 'conflicts with installed'):
            engine.restore_business_xmlids()
        self.assertFalse(any(q.startswith('INSERT INTO ir_model_data(') for q,_ in engine.queries))

    def test_unsupported_foreign_key_stops_planning(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.seed_moves = [{'model':'ab_test', 'old_id':1}]
        engine.cr.fetchall.side_effect = [[('dependent','parent_id','ab_test','id','r',1,'restrict_fk')], []]
        with tempfile.TemporaryDirectory() as directory:
            engine.stage = Path(directory)
            with self.assertRaisesRegex(MigrationError, 'unsupported seed reference'):
                engine.discover_seed_references()
        engine.cr.commit.assert_not_called()

    def test_old_mapping_archive_cannot_run_after_old_business_commit(self):
        engine = test_bulk.BulkTests().make_engine()
        with patch('seeds.get_checkpoint', return_value={'format': 1}):
            with self.assertRaisesRegex(MigrationError, 'old ID policy'):
                engine.archive_old_mapping({'format': 1})
        self.assertEqual(engine.queries, [])

    def test_fk_to_unmoved_model_is_not_mistaken_for_unknown_integer(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.seed_moves = [{'model':'ab_test', 'old_id':1}]
        engine.physical['dependent'] = {'technical_id': {'type':'integer'}}
        engine.cr.fetchall.side_effect = [[('dependent','technical_id','ir_model','id','a',1,'technical_fk')], []]
        engine.cr.fetchone.return_value = (0,)
        with tempfile.TemporaryDirectory() as directory:
            engine.stage = Path(directory)
            engine.discover_seed_references()
        self.assertFalse(any('"technical_id"=m.old_id' in q for q,_ in engine.queries))
        self.assertFalse(any(r[1:3] == ('dependent','technical_id') for r in engine.seed_references))

    def test_unknown_numeric_config_names_key_without_value(self):
        engine = test_bulk.BulkTests().make_engine()
        engine.cr.fetchall.return_value = [('custom.owner_id',)]
        with self.assertRaisesRegex(MigrationError, 'adapter: custom.owner_id$'):
            engine.check_config_seed_references('old_id')

    def test_config_policy_covers_reviewed_scalars_and_portal_user(self):
        from seeds import CONFIG_SCALARS
        engine = test_bulk.BulkTests().make_engine()
        engine.cr.fetchall.return_value = []
        for before, after in [('old_id', 'temp_id'), ('temp_id', 'new_id')]:
            engine.rewrite_seed_reference(('config', 'ir_config_parameter', 'value', '', ''), before, after)
        updates = [(q, p) for q, p in engine.queries if q.startswith('UPDATE')]
        self.assertEqual(sum(p == ['base.template_portal_user_id', 'res.users'] for q, p in updates), 2)
        self.assertTrue(all(p[0] not in CONFIG_SCALARS for q, p in updates))
        checks = [(q, p) for q, p in engine.queries if q.startswith('SELECT DISTINCT')]
        self.assertEqual(len(checks), 2)
        for q, p in checks:
            self.assertTrue(CONFIG_SCALARS.issubset(p[0]))
            self.assertIn('base.template_portal_user_id', p[0])

    def test_metadata_blocker_identifies_record_and_xmlid(self):
        import json
        engine = test_bulk.BulkTests().make_engine()
        engine.seed_moves = [{'model':'ab_test', 'old_id':4}]
        engine.cr.fetchall.side_effect = [[], [(7, 'payload')], [('base.example',)]]
        engine.cr.fetchone.return_value = (0,)
        finding = {'location':'/form/@context', 'expression':"{'default_partner_id':4}"}
        with tempfile.TemporaryDirectory() as directory:
            engine.stage = Path(directory)
            with patch('seeds.inspect_metadata', return_value=[finding]):
                with self.assertRaisesRegex(MigrationError, 'unsupported seed reference'):
                    engine.discover_seed_references()
            report = json.loads((engine.stage / 'seed-reference-blockers.json').read_text())
        self.assertEqual(report[0]['record_id'], 7)
        self.assertEqual(report[0]['xmlids'], ['base.example'])
        self.assertEqual(report[0]['findings'], [finding])

    def test_seed_resume_ignores_collation_but_rejects_changed_ids(self):
        from resume import fingerprint
        engine = test_bulk.BulkTests().make_engine()
        moves = [dict(model=m,old_id=1,temp_id=10,new_id=2,reason='test')
                 for m in ('ab_test','abdin_eplus.example')]
        saved = dict(seed_moves=moves,seed_fingerprints={},seed_surplus={},seed_references=[])
        engine.seed_moves=moves;engine.seed_fingerprints={};engine.seed_surplus={};engine.seed_references=[]
        saved['seed_plan_identity']=engine.seed_plan_identity()
        engine.discover_seed_references=lambda: None
        columns=('model','old_id','temp_id','new_id','reason')
        engine.cr.fetchall.return_value=[tuple(r[k] for k in columns) for r in reversed(moves)]
        engine.check_seed_state(saved)
        engine.cr.fetchall.return_value=[('ab_test',1,10,999,'test')]
        with self.assertRaisesRegex(MigrationError,'differs from committed plan'):
            engine.check_seed_state(saved)
