import ast
import json
import unittest
from unittest.mock import MagicMock
from action_seeds import action_references
from common import MigrationError
from seeds import StrictSeeds

SCHEMA = {
    'ir.cron': {'fields': {}},
    'entry': {'fields': {
        'account_id': {'type':'many2one','relation':'account'},
        'doctype_id': {'type':'many2one','relation':'doctype'},
        'costcenter_id': {'type':'many2one','relation':'costcenter'},
        'amount': {'type':'integer'},
    }},
    'account': {'fields':{}}, 'doctype': {'fields':{}}, 'costcenter': {'fields':{}},
}
MOVES = [dict(model='account',old_id=22,temp_id=1000,new_id=267),
         dict(model='doctype',old_id=1,temp_id=1001,new_id=10),
         dict(model='other',old_id=5,temp_id=1002,new_id=500),
         dict(model='other',old_id=7,temp_id=1003,new_id=700)]


class ActionSeedsTests(unittest.TestCase):
    def test_salary_defaults_two_steps_preserve_other_entries(self):
        original = "{'default_account_id':22,'default_doctype_id':7,'default_costcenter_id':629,'flag':True}"
        temporary, errors = action_references(original,'context','entry',SCHEMA,MOVES)
        self.assertEqual(errors, [])
        self.assertEqual(ast.literal_eval(temporary)['default_account_id'],1000)
        final, errors = action_references(temporary,'context','entry',SCHEMA,MOVES,'temp_id','new_id')
        self.assertEqual(errors, [])
        self.assertEqual(ast.literal_eval(final), {**ast.literal_eval(original),'default_account_id':267})

    def test_cron_domain_cross_model_collision_is_unchanged(self):
        original = "[('id','!=',5)]"
        self.assertEqual(action_references(original,'domain','ir.cron',SCHEMA,MOVES),(original,[]))

    def test_affected_domain_and_unknown_field_block(self):
        for domain in ["[('account_id','=',22)]", "[('missing_id','=',22)]"]:
            self.assertTrue(action_references(domain,'domain','entry',SCHEMA,MOVES)[1])
        self.assertTrue(action_references("[('id','=',22)]",'domain','missing.model',SCHEMA,MOVES)[1])

    def test_unsupported_or_duplicate_default_blocks_without_evaluation(self):
        for context in ["{'default_account_id':22+0}","{'default_account_id':[22]}",
                        "{'default_account_id':22,'default_account_id':7}",
                        "{'default_unknown_id':22}","{'default_account_id':env['account'].browse(22).id}"]:
            replacement, errors = action_references(context,'context','entry',SCHEMA,MOVES)
            self.assertEqual(replacement,context)
            self.assertTrue(errors,context)

    def test_nonrelational_default_and_dynamic_unrelated_entry_preserved(self):
        original="{'default_amount':22, 'uid':uid, 'default_doctype_id':7}"
        self.assertEqual(action_references(original,'context','entry',SCHEMA,MOVES),(original,[]))

    def test_context_guard_and_no_commit(self):
        engine=StrictSeeds(); engine.cr=MagicMock(); engine.execute=MagicMock()
        plan=[dict(id=289,model='entry',original='old',temporary='temp',final='final')]
        descriptor=('action_context','ir_act_window','context','',json.dumps(plan))
        engine.cr.rowcount=1
        engine.rewrite_seed_reference(descriptor,'old_id','temp_id')
        self.assertEqual(engine.execute.call_args.args[1],['temp',289,'entry','old'])
        engine.rewrite_seed_reference(descriptor,'temp_id','new_id')
        self.assertEqual(engine.execute.call_args.args[1],['final',289,'entry','temp'])
        engine.cr.rowcount=0
        with self.assertRaisesRegex(MigrationError,'changed after seed planning'):
            engine.rewrite_seed_reference(descriptor,'old_id','temp_id')
        engine.cr.commit.assert_not_called()
