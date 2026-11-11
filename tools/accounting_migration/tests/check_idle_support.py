"""Runtime checks on an owned synthetic target; all ORM test changes roll back."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import connect, loads, save_json
from worker import isolate
from psycopg2 import sql, IntegrityError
import fcntl

p = argparse.ArgumentParser()
p.add_argument('stage', type=Path)
p.add_argument('--config', default='/opt/odoo19/config/migrate19.conf')
p.add_argument('--translations', action='store_true')
p.add_argument('--views', action='store_true')
a = p.parse_args()
lock = open(a.stage / 'worker.lock', 'a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
m = loads((a.stage / 'target.json').read_text())
assert 'fixture' in m['database']
maintenance = connect(a.config, 'postgres', readonly=False)
maintenance.autocommit = True
with maintenance.cursor() as c:
    c.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [m['database']])
    assert c.fetchone()[0] == 'accounting_migration:' + m['ownership_token']
    c.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS true').format(sql.Identifier(m['database'])))
try:
    isolate(a.config, m['database'])
    sys.path.insert(0, '/opt/odoo19/server')
    import odoo
    import logging
    logging.getLogger('odoo.sql_db').disabled = True
    from odoo import api
    from odoo.tools import config
    from odoo.tools.translate import trans_export
    from odoo.exceptions import AccessError
    config.parse_config(['-c', a.config, '-d', m['database'], '--no-http', '--max-cron-threads=0', '--logfile='])
    odoo.modules.module.initialize_sys_path()
    reg = odoo.modules.registry.Registry.new(m['database'])
    with reg.cursor() as cr:
        env = api.Environment(cr, 1, {'no_reset_password': True, 'mail_create_nolog': True})
        cr.execute("SELECT module||'.'||name FROM ir_model_data WHERE model='res.groups'")
        save_json(a.stage / 'target-role-xmlids.json', [r[0] for r in cr.fetchall()])
        if a.views:
            modules = m['modules'] + ['ab_migration_compat', 'auto_logout_idle_user_odoo']
            view_ids = env['ir.model.data'].search([('module', 'in', modules), ('model', '=', 'ir.ui.view')]).mapped('res_id')
            views = env['ir.ui.view'].browse(view_ids).exists().filtered(lambda v: v.active and v.model in env and v.type in ('form', 'list', 'search', 'kanban', 'pivot', 'graph'))
            checked, failures = 0, []
            for view in views:
                try:
                    with cr.savepoint():
                        env[view.model].get_view(view.id, view.type)
                    checked += 1
                except Exception as exc:
                    failures.append({'view': view.id, 'model': view.model, 'type': view.type, 'exception': type(exc).__name__, 'message': str(exc)[:500]})
            save_json(a.stage / 'view-checks.json', {'checked': checked, 'failures': failures})
            print(f'Compiled {checked} installed views; failures: {len(failures)}', flush=True)
            assert not failures, 'See view-checks.json'
        # Exercise the batched log-access restoration against an owned fixture.
        if (a.stage / 'manifest.json').exists():
            import sqlite3
            from types import SimpleNamespace
            from importer import Importer
            from worker import registry_metadata
            engine = Importer.__new__(Importer)
            engine.env, engine.cr = env, cr
            engine.args = SimpleNamespace(batch_size=100)
            engine.schema = registry_metadata(env)
            engine.manifest = loads((a.stage / 'manifest.json').read_text())
            engine.rules = loads(Path(__file__).resolve().parents[1].joinpath('mappings.json').read_text())
            engine.db = sqlite3.connect(f'file:{a.stage / "records.sqlite"}?mode=ro', uri=True)
            engine.cache = {}
            engine.restore_audit()
            engine.db.close()
        missing = env['ir.attachment'].search([('migration_file_missing', '=', True)], limit=1)
        if missing:
            from werkzeug.exceptions import NotFound
            assert not missing.raw and missing.migration_source_size == 123
            try: missing._to_http_stream()
            except NotFound: pass
            else: raise AssertionError('Unavailable attachment returned fake content')
        inventory = env['ab_inventory'].search([('migration_reference_missing', '=', True)], limit=1)
        if inventory:
            from odoo.exceptions import UserError
            assert inventory.qty == 17 and inventory.res_id == 0
            try: inventory.with_user(2).write({'qty': 999})
            except UserError: pass
            else: raise AssertionError('Orphan inventory was editable')
            assert inventory.qty == 17
            print('Missing-file download and unresolved-inventory edit guards verified')
        with (a.stage / 'idle.pot').open('wb') as f:
            trans_export(None, ['auto_logout_idle_user_odoo'], f, 'po', env)
        with (a.stage / 'private-contacts.pot').open('wb') as f:
            trans_export(None, ['ab_migration_compat'], f, 'po', env)
        user = env['res.users'].create({'name': 'Idle policy check', 'login': 'idle_policy_check', 'idle_time': 7})
        assert user.idle_time == 7 and user.enable_idle
        assert user.with_user(user).idle_time == 7
        private = env['res.partner'].create({'name': 'Confidential fixture contact', 'type': 'private'})
        assert not env['res.partner'].with_user(user).search([('id', '=', private.id)])
        assert env['res.partner'].with_user(2).search([('id', '=', private.id)])
        mapped_user = env['res.users'].with_context(active_test=False).search([('login', '=', 'synthetic_migration_fixture')], limit=1)
        if mapped_user:
            assert mapped_user.has_group('ab_migration_compat.group_private_addresses')
            assert env['res.partner'].with_user(mapped_user).search([('id', '=', private.id)])
        from odoo.exceptions import UserError
        from odoo.addons.ab_migration_compat.models.res_partner import preserve_private_addresses
        try:
            preserve_private_addresses(private)
        except UserError:
            pass
        else:
            raise AssertionError('Private address removal was not blocked')
        print('Private contacts hidden from ordinary users; administrator access and removal guard verified')
        try:
            user.with_user(user).write({'idle_time': 100})
        except AccessError:
            pass
        else:
            raise AssertionError('Ordinary user changed idle policy')
        try:
            with cr.savepoint():
                user.write({'idle_time': 0})
                env.flush_all()
        except IntegrityError:
            pass
        else:
            raise AssertionError('Nonpositive timeout accepted')
        cr.rollback()
        if a.translations:
            for lang in ('ar_001',):
                env['res.lang']._activate_lang(lang)
            env['ir.module.module'].search([('name', 'in', ['auto_logout_idle_user_odoo', 'ab_migration_compat'])])._update_translations(['ar_001'], overwrite=True)
            view = env['ir.model.data']._xmlid_to_res_id('auto_logout_idle_user_odoo.view_users_form_idle')
            record = env['ir.ui.view'].browse(view)
            for lang in ('ar_001',):
                assert record.with_context(lang=lang).arch_db != record.with_context(lang='en_US').arch_db
            for xmlid in ('ab_migration_compat.attachment_missing_file_form', 'ab_migration_compat.ab_inventory_header_legacy_reference_form', 'ab_migration_compat.ab_accounting_tracking_legacy_reference_form'):
                view_id = env['ir.model.data']._xmlid_to_res_id(xmlid)
                view = env['ir.ui.view'].browse(view_id)
                assert view.with_context(lang='ar_001').arch_db != view.with_context(lang='en_US').arch_db, xmlid
            print('Arabic idle, attachment and legacy-reference views verified in ar_001 (both PO files shipped)')
        cr.rollback()
        print('POT exported; administrator-only policy and positive timeout checked')
finally:
    with maintenance.cursor() as c:
        c.execute(sql.SQL('ALTER DATABASE {} ALLOW_CONNECTIONS false').format(sql.Identifier(m['database'])))
    maintenance.close()
