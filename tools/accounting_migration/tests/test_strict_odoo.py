"""Opt-in acceptance of an already migrated disposable Odoo database.

Set MIGRATION_ODOO_TEST_CONFIG, MIGRATION_ODOO_TEST_DB (codex_migration_test_*)
and MIGRATION_ODOO_TEST_STAGE explicitly. Never installs/upgrades addons here.
"""
import os
from pathlib import Path
import subprocess
import sys
import unittest

ENABLED = all(os.environ.get(k) for k in ('MIGRATION_ODOO_TEST_CONFIG','MIGRATION_ODOO_TEST_DB','MIGRATION_ODOO_TEST_STAGE'))


@unittest.skipUnless(ENABLED, 'requires explicitly selected migrated disposable Odoo database')
class StrictOdooAcceptance(unittest.TestCase):
    def test_source_ids_groups_and_xmlids_in_fresh_registry(self):
        database = os.environ['MIGRATION_ODOO_TEST_DB']
        self.assertTrue(database.startswith('codex_migration_test_'))
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--probe'],
                                capture_output=True, text=True, timeout=300)
        # No row values or config secrets from a failing registry are echoed.
        self.assertEqual(result.returncode, 0, 'Disposable Odoo acceptance probe failed; inspect it in the isolated test environment')


def probe():
    here = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(here))
    from common import loads, LOOKUPS
    from worker import isolate
    from seeds import require_strict
    from resume import get_checkpoint
    from bulk_importer import verify_unassigned_accounting_permissions
    from psycopg2 import sql
    database, config_path = os.environ['MIGRATION_ODOO_TEST_DB'], os.environ['MIGRATION_ODOO_TEST_CONFIG']
    if not database.startswith('codex_migration_test_'):
        raise RuntimeError('Disposable database required')
    isolate(config_path, database)
    sys.path.insert(0, str(here.parents[2] / 'server'))
    import odoo
    from odoo.tools import config
    config.parse_config(['-c',config_path,'-d',database,'--no-http','--max-cron-threads=0','--logfile='])
    registry = odoo.modules.registry.Registry.new(database, update_module=False)
    manifest = loads((Path(os.environ['MIGRATION_ODOO_TEST_STAGE']) / 'bulk-manifest.json').read_text())
    with registry.cursor() as cr:
        cr.execute('SET TRANSACTION READ ONLY')
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {'active_test':False,'lang':'en_US'})
        require_strict(get_checkpoint(cr, 'business'), required=True)
        for model, metadata in manifest['models'].items():
            if model in LOOKUPS: continue
            cr.execute(sql.SQL('SELECT count(*) FROM {} s LEFT JOIN {} t ON s.id=t.id WHERE t.id IS NULL').format(
                sql.Identifier('accounting_migration_source',metadata['table']), sql.Identifier(env[model]._table)))
            assert cr.fetchone()[0] == 0, model
        cr.execute('SELECT count(*) FROM accounting_migration_work.business_xmlids s LEFT JOIN ir_model_data t USING(module,name) WHERE t.id IS NULL OR t.model<>s.model OR t.res_id<>s.res_id')
        assert cr.fetchone()[0] == 0
        verify_unassigned_accounting_permissions(env)
        for user in env['res.users'].search([]):
            user._check_disjoint_groups()
        assert env.ref('base.user_root').id == 1
        assert env.ref('base.user_admin').has_group('base.group_system')
        cr.rollback()


if __name__ == '__main__' and '--probe' in sys.argv:
    probe()
