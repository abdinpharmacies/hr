"""Isolated Odoo 19 process. Never loads an Odoo 15 registry."""
import argparse
import os
from pathlib import Path
import sys
from common import MigrationError, loads, save_json, settings
from adapters import SUPPORT_MODULES
from progress import current, session, monitor_factory
from seeds import require_strict
from resume import get_checkpoint, put_checkpoint, assert_exclusive, fingerprint


AUTHORIZATION_MODELS = ('ab_accounting_account_auth', 'ab_accounting_allowed_field_auth')


def accounting_group_columns(cursor):
    """Read both physical columns; None means the model is not installed yet."""
    columns = {}
    for model in AUTHORIZATION_MODELS:
        cursor.execute("SELECT attnotnull FROM pg_attribute WHERE attrelid=to_regclass(%s) "
                       "AND attname='group_id' AND NOT attisdropped", ['public.' + model])
        row = cursor.fetchone()
        columns[model] = bool(row[0]) if row else None
    return columns


def accounting_upgrade_required(cursor):
    return any(value is True for value in accounting_group_columns(cursor).values())


def verify_optional_accounting_groups(env):
    columns = accounting_group_columns(env.cr)
    for model in AUTHORIZATION_MODELS:
        if env[model]._fields['group_id'].required:
            raise MigrationError(f'{model}.group_id must be optional in this migration checkout')
        if columns[model] is not False:
            raise MigrationError(f'{model}.group_id is missing or still NOT NULL after targeted upgrade')


def isolate(config, database):
    """Allow PostgreSQL only to this destination; deny network side effects."""
    import socket
    import psycopg2
    from psycopg2.extensions import parse_dsn
    opts = settings(config)
    host, port = opts.get('db_host', 'localhost'), int(opts.get('db_port', 5432))
    original_connect = psycopg2.connect
    def target_connect(dsn=None, *a, **kw):
        params = parse_dsn(dsn or '')
        params.update({k: v for k, v in kw.items() if k not in ('connection_factory', 'cursor_factory')})
        if params.get('dbname', params.get('database')) != database:
            raise MigrationError('Migration worker attempted connection to another database')
        if params.get('host', '') not in ('', host) or int(params.get('port', 5432)) != port:
            raise MigrationError('Migration worker attempted connection to another server')
        return original_connect(dsn, *a, **kw)
    psycopg2.connect = target_connect
    def denied(*a, **kw):
        raise MigrationError('Outbound networking is disabled in the migration worker')
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    try:
        import pymssql
        pymssql.connect = denied
    except ImportError:
        pass
    try:
        import pyodbc
        pyodbc.connect = denied
    except ImportError:
        pass


def registry_metadata(env):
    result = {}
    for name in env.registry:
        model = env[name]
        if model._abstract or model._transient or not model._auto:
            continue
        fields = {}
        for fn, f in model._fields.items():
            fields[fn] = {'type': f.type, 'store': bool(f.store), 'required': bool(f.required),
                          'module': getattr(f, '_module', None),
                          'readonly': bool(f.readonly), 'compute': bool(f.compute), 'related': bool(f.related),
                          'model_field': getattr(f, 'model_field', None), 'relation': getattr(f, 'comodel_name', None), 'translate': bool(f.translate), 'company_dependent': bool(f.company_dependent),
                          'relation_table': getattr(f, 'relation', None) if f.type == 'many2many' else None,
                          'column1': getattr(f, 'column1', None), 'column2': getattr(f, 'column2', None)}
            if f.type == 'selection':
                try: fields[fn]['selection'] = [v for v, _ in f._description_selection(env)]
                except Exception: fields[fn]['selection'] = None
        result[name] = {'table': model._table, 'inherits': model._inherits, 'fields': fields}
    return result


def main():
    p = argparse.ArgumentParser()
    for name in ('config', 'database', 'source-db', 'server', 'stage', 'command'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--modules')
    p.add_argument('--batch-size', type=int, default=100)
    p.add_argument('--allow-source-defects', action='store_true')
    p.add_argument('--refresh-engine-before-records', action='store_true')
    p.add_argument('--allow-missing-files', action='store_true')
    p.add_argument('--rehearsal', action='store_true')
    args = p.parse_args()
    current().begin(args.command, operation='load Odoo configuration')
    os.umask(0o077)
    stage = Path(args.stage)
    if args.database == args.source_db:
        raise MigrationError('Source and destination must differ')
    marker = loads((stage / 'target.json').read_text())
    if marker['database'] != args.database or marker['source'] != args.source_db:
        raise MigrationError('Destination marker does not match this run')
    from common import connect
    connection = connect(args.config, args.database)
    upgrade_accounting = False
    missing_modules = list(marker['modules'])
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [args.database])
            if cursor.fetchone()[0] != 'accounting_migration:' + marker['ownership_token']:
                raise MigrationError('Destination ownership token mismatch')
            assert_exclusive(cursor, args.database)
            cursor.execute("SELECT to_regclass('accounting_migration.run'),to_regclass('public.ir_module_module')")
            run_table, module_table = cursor.fetchone()
            if run_table:
                cursor.execute('SELECT source_db,target_db,status FROM accounting_migration.run WHERE id')
                run = cursor.fetchone()
                if not run or run[:2] != (args.source_db, args.database):
                    raise MigrationError('Destination run marker mismatch')
            elif marker.get('initialized'):
                raise MigrationError('Initialized target has lost its database run marker')
            if module_table:
                cursor.execute("SELECT name FROM ir_module_module WHERE state='installed'")
                installed = {r[0] for r in cursor.fetchall()}
                missing_modules = sorted(set(marker['modules']) - installed)
                upgrade_accounting = accounting_upgrade_required(cursor)
            if run_table and upgrade_accounting and get_checkpoint(cursor, 'business'):
                raise MigrationError('Cannot upgrade schema after business commit during resume')
    finally:
        connection.close()
    isolate(args.config, args.database)
    sys.path.insert(0, args.server)
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.tools import config
    opts = ['-c', args.config, '-d', args.database, '--no-http', '--max-cron-threads=0',
            '--stop-after-init', '--without-demo', '--logfile=']
    if args.command == 'init-target':
        if missing_modules:
            opts += ['-i', ','.join(missing_modules)]
        if upgrade_accounting:
            opts += ['-u', 'ab_accounting']
    config.parse_config(opts)
    import logging
    logging.getLogger('odoo.sql_db').disabled = True  # never log SQL parameters/password hashes
    odoo.modules.module.initialize_sys_path()
    from odoo.addons.bus.models.bus import BusBus
    BusBus._sendone = lambda *a, **kw: None
    # Registry creation runs synchronously: no service, cron or queue runner is started.
    current().operation('install modules' if args.command == 'init-target' else 'reload registry')
    registry = odoo.modules.registry.Registry.new(args.database, update_module=args.command == 'init-target' and bool(missing_modules or upgrade_accounting),
                  install_modules=config['init'] if args.command == 'init-target' else (),
                  upgrade_modules=config['update'] if args.command == 'init-target' else (), new_db_demo=False)
    with registry.cursor() as cr:
        current().bind(monitor_factory(args.config, args.database), cr._cnx.get_backend_pid())
        env = api.Environment(cr, SUPERUSER_ID, {'active_test': False, 'tracking_disable': True,
                              'mail_create_nolog': True, 'mail_create_nosubscribe': True,
                              'mail_notrack': True, 'no_reset_password': True, 'allow_recon': True,
                              'from_header': True, 'no_calc_balance': True, 'lang': 'en_US'})
        if args.command == 'init-target':
            installed = env['ir.module.module'].search([('name', 'in', marker['modules']), ('state', '=', 'installed')]).mapped('name')
            missing = sorted(set(marker['modules']) - set(installed))
            if missing:
                raise MigrationError(f'Required modules were not installed: {missing}')
            cr.execute('CREATE SCHEMA IF NOT EXISTS accounting_migration')
            cr.execute('CREATE TABLE IF NOT EXISTS accounting_migration.run (id boolean PRIMARY KEY DEFAULT true CHECK(id), '
                       'source_db text NOT NULL, target_db text NOT NULL, snapshot_id text, status text NOT NULL)')
            cr.execute("INSERT INTO accounting_migration.run(source_db,target_db,status) VALUES (%s,%s,'initialized') ON CONFLICT (id) DO NOTHING", [args.source_db, args.database])
            cr.execute('CREATE TABLE IF NOT EXISTS accounting_migration.record_map (model text, source_id bigint, '
                       'target_model text NOT NULL, target_id bigint NOT NULL, phase text NOT NULL, '
                       'PRIMARY KEY(model,source_id), UNIQUE(target_model,target_id))')
            cr.execute('CREATE TABLE IF NOT EXISTS accounting_migration.checkpoint (name text PRIMARY KEY, value text)')
            env['ir.cron'].search([]).write({'active': False})
            put_checkpoint(cr, 'modules', {'identity': fingerprint(sorted(marker['modules']))})
            cr.commit()
            language_checkpoint = get_checkpoint(cr, 'languages')
            requested = marker.get('required_languages')
            if language_checkpoint and language_checkpoint['identity'] != fingerprint(requested):
                raise MigrationError('Required language set changed since initialization')
            if language_checkpoint and not upgrade_accounting:
                report = language_checkpoint['report']
                active = set(env['res.lang'].with_context(active_test=False).search([
                    ('code', 'in', report['required']), ('active', '=', True)]).mapped('code'))
                if active != set(report['required']):
                    raise MigrationError('Committed target languages are no longer active')
                save_json(stage / 'languages.json', report)
                current().finish('skipped: committed language checkpoint')
            else:
                from languages import install_languages
                # Legacy runs have no language checkpoint: revalidate the recorded setup.
                legacy_path = stage / 'languages.json'
                legacy = loads(legacy_path.read_text()) if legacy_path.exists() else {}
                active = set(env['res.lang'].with_context(active_test=False).search([
                    ('code', 'in', requested), ('active', '=', True)]).mapped('code'))
                if (marker.get('initialized') and not upgrade_accounting and legacy.get('complete')
                        and legacy.get('translations_loaded') and set(legacy.get('required', [])) == set(requested)
                        and active == set(requested)):
                    report = legacy
                else:
                    report = install_languages(env, stage, requested)
                put_checkpoint(cr, 'languages', {'identity': fingerprint(requested), 'report': report})
                cr.commit()
            verify_optional_accounting_groups(env)
            current().transaction('committed', 'initialization and languages')
            save_json(stage / 'target-schema.json', registry_metadata(env))
            marker['initialized'] = True
            save_json(stage / 'target.json', marker)
            print('Fresh target initialized with scheduled jobs disabled')
        else:
            if args.command == 'bulk-smoke':
                from bulk_importer import smoke_test
                done = get_checkpoint(cr, 'runtime')
                if done:
                    require_strict(done)
                    manifest = loads((stage / 'bulk-manifest.json').read_text())
                    if done['identity'] != fingerprint(manifest):
                        raise MigrationError('Runtime checkpoint belongs to another extraction')
                    save_json(stage / 'verification.json', done['report'])
                    current().finish('skipped: committed runtime checkpoint; migration complete')
                else:
                    smoke_test(env, stage)
                return
            if args.command == 'bulk-import':
                from bulk_importer import BulkImporter
                engine = None
                try:
                    engine = BulkImporter(env, stage, registry_metadata(env))
                    engine.run()
                except Exception as exc:
                    import traceback
                    save_json(stage / 'bulk-error.json', {'error_type': type(exc).__name__,
                        'phase': getattr(engine, 'current_phase', 'initialization'),
                        'table': getattr(engine, 'current_table', None),
                        'message': str(exc) if isinstance(exc, MigrationError) else 'Database/adapter failure; values redacted',
                        'constraint': getattr(getattr(exc, 'diag', None), 'constraint_name', None),
                        'frames': [f'{f.filename}:{f.lineno}:{f.name}' for f in traceback.extract_tb(exc.__traceback__)]})
                    raise MigrationError('Bulk migration failed; see bulk-error.json and verification.json') from None
                return
            from importer import Importer
            engine = Importer(env, stage, args, registry_metadata(env))
            if args.command == 'import': engine.run()
            elif args.command == 'verify': engine.verify()
            elif args.command == 'validate-export':
                engine.check_schema()
            elif args.command == 'activate-dev': engine.activate_dev()


if __name__ == '__main__':
    with session(transport=True):
        try:
            main()
        except BaseException:
            current().finish('failed')
            raise
