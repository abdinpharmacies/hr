"""Offline regressions for nullable legacy authorization groups and recovery."""
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from worker import accounting_upgrade_required, verify_optional_accounting_groups, AUTHORIZATION_MODELS
from bulk_importer import verify_unassigned_accounting_permissions
from common import MigrationError, loads
import test_bulk


class AccountingGroupTests(unittest.TestCase):
    def test_upgrade_detects_either_required_column(self):
        for values, expected in [((False, True), True), ((True, True), True),
                                 ((True, False), True), ((False, False), False)]:
            with self.subTest(values=values):
                cr = MagicMock()
                cr.fetchone.side_effect = [(value,) for value in values]
                self.assertEqual(accounting_upgrade_required(cr), expected)
                self.assertEqual([c.args[1] for c in cr.execute.call_args_list],
                                 [['public.' + model] for model in AUTHORIZATION_MODELS])

    def test_uninstalled_tables_do_not_request_upgrade(self):
        cr = MagicMock()
        cr.fetchone.side_effect = [None, None]
        self.assertFalse(accounting_upgrade_required(cr))

    def test_post_upgrade_checks_both_physical_and_orm_fields(self):
        env = MagicMock()
        models = {model: SimpleNamespace(_fields={'group_id': SimpleNamespace(required=False)})
                  for model in AUTHORIZATION_MODELS}
        env.__getitem__.side_effect = models.__getitem__
        env.cr.fetchone.side_effect = [(False,), (False,)]
        verify_optional_accounting_groups(env)
        for second in [(True,), None]:
            env.cr.fetchone.side_effect = [(False,), second]
            with self.assertRaisesRegex(MigrationError, 'ab_accounting_allowed_field_auth.group_id'):
                verify_optional_accounting_groups(env)
        env.cr.fetchone.side_effect = [(False,), (False,)]
        models[AUTHORIZATION_MODELS[1]]._fields['group_id'].required = True
        with self.assertRaisesRegex(MigrationError, 'must be optional'):
            verify_optional_accounting_groups(env)

    def test_unassigned_user_must_not_receive_either_authorization_type(self):
        env = MagicMock()
        for accounts, fields in [([], [1]), ([1], []), ([1], [2])]:
            env['res.users'].search.return_value = [SimpleNamespace(id=7, account_auth_ids=accounts, allowed_field_ids=fields)]
            with self.assertRaisesRegex(MigrationError, 'leaked to user 7'):
                verify_unassigned_accounting_permissions(env)
        env['res.users'].search.return_value = [SimpleNamespace(id=7, account_auth_ids=[], allowed_field_ids=[])]
        verify_unassigned_accounting_permissions(env)

    def engine(self, stage):
        engine = test_bulk.BulkTests().make_engine()
        model = 'ab_accounting_allowed_field_auth'
        fields = {'id': {'type': 'integer', 'required': True},
                  'group_id': {'type': 'integer', 'required': False},
                  'allowed_field_id': {'type': 'integer', 'required': False}}
        engine.models = {model: {'table': model, 'fields': {
            'group_id': {'ttype': 'many2one', 'relation': 'ab_accounting_auth_group', 'store': True},
            'allowed_field_id': {'ttype': 'many2one', 'relation': 'ab_accounting_allowed_field', 'store': True}}}}
        engine.schema = {model: {'table': model, 'fields': {
            'group_id': {'type': 'many2one', 'required': False},
            'allowed_field_id': {'type': 'many2one', 'required': True}}}}
        engine.manifest = {'tables': {model: {'columns': fields, 'rows': 261}}}
        engine.physical = {model: {k: dict(v) for k, v in fields.items()}}
        engine.physical[model]['allowed_field_id']['required'] = True
        engine.stage = Path(stage)
        return engine, model

    def test_nullable_group_passes_early_check_and_keeps_null_preserving_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, model = self.engine(directory)
            engine.cr.fetchone.return_value = (0,)
            engine.early_validation()
            self.assertEqual(loads((engine.stage / 'preflight-errors.json').read_text()), [])
            expressions = engine.prepare(model)
            group = test_bulk.render(expressions['group_id'])
            # Scalar lookup on a NULL source ID yields NULL, without a fallback group.
            self.assertIn('m.source_id=s."group_id"', group)
            self.assertNotIn('coalesce', group.lower())
            self.assertIn('allowed_field_id', expressions)

    def test_other_required_field_still_blocks_before_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            engine, model = self.engine(directory)
            engine.cr.fetchone.return_value = (3,)
            engine.cr.fetchall.return_value = [(1,), (2,), (3,)]
            with self.assertRaisesRegex(MigrationError, '1 schema/required-value issues'):
                engine.early_validation()
            problems = loads((engine.stage / 'preflight-errors.json').read_text())
            self.assertEqual(problems[0]['field'], 'allowed_field_id')
            self.assertEqual(problems[0]['count'], 3)
