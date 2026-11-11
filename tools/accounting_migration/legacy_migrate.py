#!/usr/bin/env python3
"""Retired owned-target initializer, retained exclusively for regression tests."""
import argparse
import datetime
import os
from pathlib import Path
import subprocess
import shlex
import sys
import uuid
import threading
from seeds import require_strict
from resume import find_run, endpoint, assert_exclusive, get_checkpoint, fingerprint
from psycopg2 import sql
from common import MigrationError, connect, loads, save_json, settings
from adapters import SUPPORT_MODULES
from bulk import export_snapshot, heartbeat
from languages import discover_languages
from progress import current, session, monitor_factory
import source

HERE = Path(__file__).resolve().parent
RUN_ROOT = HERE.parents[2] / 'migration-runs'


def parser():
    p = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for name in ('source-config', 'source-db', 'target-config', 'target-db'):
        p.add_argument('--' + name, required=True)
    return p


def worker(args, stage, command, modules=()):
    server = HERE.parents[2] / 'server'
    if not (server / 'odoo').is_dir():
        raise MigrationError(f'Odoo server not found beside checkout: {server}')
    argv = [sys.executable, '-u', str(HERE / 'worker.py'), '--config', args.target_config,
            '--database', args.target_db, '--source-db', args.source_db, '--server', str(server),
            '--stage', str(stage), '--command', command]
    if modules:
        argv += ['--modules', ','.join(modules)]
    reporter = current()
    reporter.bind(None, None)
    reporter.begin(command, operation='start isolated Odoo worker')
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    def drain():
        try:
            for line in proc.stdout:
                reporter.accept(line.rstrip('\n'), command)
        except Exception as exc:
            reporter.log(f'[LOGGING] worker pipe reader failed: {type(exc).__name__}', important=True)
    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        code = proc.wait()
        reader.join(timeout=2)
        if code:
            raise MigrationError(f'{command} failed; see {stage / (command + ".log")}')
    except BaseException:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        reader.join(timeout=2)
        raise


def archive_attempt(stage):
    attempt = datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:8]
    archive = stage / 'attempts' / attempt
    archive.mkdir(parents=True)
    for name in ('failure.json', 'bulk-error.json', 'preflight-errors.json', 'validation-errors.json'):
        path = stage / name
        if path.exists():
            # Keep originals until successful recovery has inspected legacy evidence.
            (archive / name).write_bytes(path.read_bytes())
    if (stage / 'verification.json').exists():
        (archive / 'verification.json').write_bytes((stage / 'verification.json').read_bytes())
    print(f'Attempt {attempt}; retained earlier diagnostics in {archive}')
    return archive


def resume_run(args, stage, marker):
    for name, config in (('source_endpoint', args.source_config), ('target_endpoint', args.target_config)):
        if marker.get(name) is not None and marker[name] != endpoint(config):
            raise MigrationError(f'{name} changed; refusing to reuse another server snapshot')
    con = connect(args.target_config, args.target_db)
    bound_snapshot = None
    business_committed = False
    try:
        with con.cursor() as cr:
            assert_exclusive(cr, args.target_db)
            cr.execute("SELECT to_regclass('accounting_migration.run')")
            if cr.fetchone()[0]:
                cr.execute('SELECT source_db,target_db FROM accounting_migration.run WHERE id')
                if cr.fetchone() != (args.source_db, args.target_db):
                    raise MigrationError('Database run identity mismatch')
                bound_snapshot = get_checkpoint(cr, 'manifest')
                done = get_checkpoint(cr, 'runtime')
                if done:
                    require_strict(done)
                    manifest = loads((stage / 'bulk-manifest.json').read_text())
                    if done['identity'] != fingerprint(manifest):
                        raise MigrationError('Completed database manifest mismatch')
                    save_json(stage / 'verification.json', done['report'])
                    print('Migration already complete; skipped all committed phases')
                    return done['report']
                business = get_checkpoint(cr, 'business')
                require_strict(business)
                business_committed = business is not None
            elif marker.get('initialized'):
                raise MigrationError('Initialized database has no migration run marker')
    finally:
        con.close()
    path = stage / 'bulk-manifest.json'
    manifest = loads(path.read_text()) if path.exists() else {}
    if bound_snapshot and bound_snapshot['identity'] != fingerprint(manifest):
        raise MigrationError('Committed staging manifest missing or changed; original extraction is required')
    if not business_committed:
        worker(args, stage, 'init-target', marker['modules'])
    else:
        print('Initialization skipped: business transaction already committed')
    if manifest.get('complete'):
        print('Extraction skipped: complete original snapshot retained')
    else:
        # An interrupted repeatable-read source snapshot cannot be reopened.
        archive = stage / ('incomplete-extraction-' + uuid.uuid4().hex)
        archive.mkdir()
        for name in ('bulk-manifest.json', 'tables'):
            item = stage / name
            if item.exists():
                item.rename(archive / name)
        with connect(args.source_config, args.source_db) as source_con:
            current().bind(monitor_factory(args.source_config, args.source_db), source_con.get_backend_pid())
            info = source.inventory(source_con, settings(args.source_config).get('addons_path', '').split(','))
            required = set(info['modules']) | set(SUPPORT_MODULES) | {'abdin_eplus'}
            if required != set(marker['modules']) or discover_languages(source_con, info) != marker['required_languages']:
                raise MigrationError('Source module/language scope changed after interrupted extraction; use a new target')
            save_json(stage / 'inventory.json', info)
            export_snapshot(source_con, stage, info, loads((stage / 'target-schema.json').read_text()),
                            loads((HERE / 'mappings.json').read_text()))
    worker(args, stage, 'bulk-import')
    worker(args, stage, 'bulk-smoke')
    report = loads((stage / 'verification.json').read_text())
    if not report['passed']:
        raise MigrationError('Runtime verification incomplete; see verification.json')
    print(f'Migration resumed and validated for isolated development. Report: {stage / "verification.json"}')
    return report


def legacy_main(argv=None):
    args = parser().parse_args(argv)
    os.umask(0o077)
    if args.source_db == args.target_db:
        raise MigrationError('Source and target database names must differ')
    # Existence is checked before source extraction or target initialization.
    maintenance = connect(args.target_config, 'postgres', readonly=False)
    maintenance.autocommit = True
    try:
        with maintenance.cursor() as cr:
            cr.execute('SELECT pg_try_advisory_lock(hashtext(%s))', ['accounting_migration:' + args.target_db])
            if not cr.fetchone()[0]:
                raise MigrationError('Another migration is working on this target')
            cr.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s", [args.target_db])
            existing = cr.fetchone()
        if existing:
            stage, marker = find_run(RUN_ROOT, args.source_db, args.target_db, existing[0])
            with session(stage) as reporter:
                archive_attempt(stage)
                try:
                    return resume_run(args, stage, marker)
                except BaseException as exc:
                    save_json(stage / 'failure.json', dict(error_type=type(exc).__name__, complete=False, connection_policy='always_enabled'))
                    reporter.finish('failed; committed checkpoints retained')
                    raise
        RUN_ROOT.mkdir(exist_ok=True)
        stage = RUN_ROOT / (datetime.datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:12])
        stage.mkdir(mode=0o700)
        with session(stage) as reporter:
            try:
                archive_attempt(stage)
                print(f'Fresh migration: {args.source_db} -> {args.target_db}\nLogs: {stage}', flush=True)
                print('Database connections stay enabled, including after failures. An incomplete target is not a completed migration.', flush=True)
                with connect(args.source_config, args.source_db) as con:
                    reporter.bind(monitor_factory(args.source_config, args.source_db), con.get_backend_pid())
                    with heartbeat('Discover source'):
                        info = source.inventory(con, settings(args.source_config).get('addons_path', '').split(','))
                    languages = discover_languages(con, info)
                    print('Required languages: ' + ', '.join(languages), flush=True)
                    modules = sorted(set(info['modules']) | set(SUPPORT_MODULES) | {'abdin_eplus'})
                    marker = dict(database=args.target_db, source=args.source_db, modules=modules,
                                  initialized=False, ownership_token=str(uuid.uuid4()),
                                  source_endpoint=endpoint(args.source_config), target_endpoint=endpoint(args.target_config),
                                  required_languages=languages, connection_policy='always_enabled')
                    save_json(stage / 'target.json', marker)
                    save_json(stage / 'inventory.json', info)
                    opts = settings(args.source_config)
                    if not opts.get('data_dir'):
                        raise MigrationError('Source config must specify data_dir for unambiguous filestore discovery')
                    save_json(stage / 'bulk-settings.json', dict(source_filestore=str(
                        Path(opts['data_dir']).expanduser().resolve() / 'filestore' / args.source_db)))
                    with maintenance.cursor() as cr:
                        cr.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' ALLOW_CONNECTIONS true").format(sql.Identifier(args.target_db)))
                        cr.execute(sql.SQL('COMMENT ON DATABASE {} IS %s').format(sql.Identifier(args.target_db)),
                                   ['accounting_migration:' + marker['ownership_token']])
                    worker(args, stage, 'init-target', modules)
                    target = loads((stage / 'target-schema.json').read_text())
                    rules = loads((HERE / 'mappings.json').read_text())
                    reporter.bind(monitor_factory(args.source_config, args.source_db), con.get_backend_pid())
                    export_snapshot(con, stage, info, target, rules)
                worker(args, stage, 'bulk-import')
                worker(args, stage, 'bulk-smoke')
                report = loads((stage / 'verification.json').read_text())
                if not report['passed']:
                    raise MigrationError(f'Verification failed: {stage / "verification.json"}')
                print(f'Migration validated for isolated development. Report: {stage / "verification.json"}')
                launch = [sys.executable, str(HERE / 'dev_server.py'), '--config', args.target_config, '--stage', str(stage)]
                print('Scheduled jobs remain disabled. Use the isolated development server for manual testing:')
                print(shlex.join(launch))
                return report
            except BaseException as exc:
                # No exception parameters/SQL values (potential credentials) are logged.
                save_json(stage / 'failure.json', {'error_type': type(exc).__name__, 'complete': False,
                    'connection_policy': 'always_enabled'})
                if isinstance(exc, MigrationError):
                    print(f'ERROR: {exc}', flush=True)
                else:
                    print(f'ERROR: {type(exc).__name__}; destination remains incomplete and connections stay enabled. See worker log.', flush=True)
                print('Run incomplete. The script has not disabled database connections.', flush=True)
                reporter.finish('failed; see failure.json')
                raise
    finally:
        maintenance.close()


if __name__ == "__main__":
    raise SystemExit("Retired workflow. Use migrate.py for prepared custom-model migration.")
