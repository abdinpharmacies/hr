"""Explicit reset of pre-import migration state; never touches source access."""
import os
from pathlib import Path
import shutil
from psycopg2 import sql
from availability import DatabaseGate
from common import MigrationError, connect, loads
from resume import endpoint

SCHEMAS=('prepared_migration_work','prepared_migration_source','prepared_custom_migration')


def matching_directories(root,args,oid):
    root=Path(root)
    if root.is_symlink():
        raise MigrationError('Reset run root must not be a symlink')
    result=[]
    for marker in root.glob('*/prepared-run.json'):
        if marker.is_symlink() or marker.parent.is_symlink():
            raise MigrationError('Symlink run markers/directories cannot be reset')
        try:
            data=loads(marker.read_text())
        except Exception:
            raise MigrationError(f'Cannot verify run marker: {marker}') from None
        if data.get('source_db')!=args.source_db or data.get('target_db')!=args.target_db:
            continue
        if data.get('source_endpoint')!=endpoint(args.source_config) or data.get('target_endpoint')!=endpoint(args.target_config):
            continue
        directory=marker.parent
        if marker.is_symlink() or directory.is_symlink() or directory.resolve().parent!=root.resolve():
            raise MigrationError('Unsafe reset directory: '+str(directory))
        if data.get('target_oid')!=oid:
            raise MigrationError('Saved target database identity changed; refusing reset')
        result.append(directory)
    return sorted(result)


def validate_state(connection,args,oid):
    with connection.cursor() as cr:
        cr.execute("SELECT to_regclass('prepared_custom_migration.checkpoint')")
        if cr.fetchone()[0]:
            cr.execute('SELECT name,value FROM prepared_custom_migration.checkpoint')
            records=dict(cr.fetchall())
            if set(records)-{'run','status','identities'}:
                raise MigrationError('Data-copy or unknown checkpoints exist; reset cannot undo imported data')
            if 'run' in records:
                run=loads(records['run'])
                if (run.get('source_db'),run.get('target_db'),run.get('target_oid'))!=(args.source_db,args.target_db,oid) or \
                        run.get('source_endpoint')!=endpoint(args.source_config) or run.get('target_endpoint')!=endpoint(args.target_config):
                    raise MigrationError('Target migration state belongs to another run')
            if 'status' in records and loads(records['status']).get('complete'):
                raise MigrationError('Completed migration cannot be reset by removing metadata')
        cr.execute("SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "WHERE c.relkind IN ('r','p') AND (n.nspname='prepared_migration_work' OR "
                   "(n.nspname='prepared_migration_source' AND c.relname NOT IN ('res_users','res_partner'))))")
        if cr.fetchone()[0]:
            raise MigrationError('Committed staging/work tables exist; review prior import before resetting')


def reset(args,root):
    os.umask(0o077)
    if args.source_db==args.target_db:
        raise MigrationError('Source and target database names must differ')
    gate=DatabaseGate(args.target_config,args.target_db)
    connection=None
    try:
        directories=matching_directories(root,args,gate.oid)
        if not gate.online():
            raise MigrationError('Target is offline; use normal target recovery before resetting. No availability change was attempted.')
        connection=connect(args.target_config,args.target_db,readonly=False)
        validate_state(connection,args,gate.oid)
        connection.rollback()
        print('Reset target: '+args.target_db,flush=True)
        print('Drop private schemas: '+', '.join(SCHEMAS),flush=True)
        for directory in directories:
            print('Permanently delete run directory: '+str(directory),flush=True)
        print('Extraction files, logs, and backups inside these directories will be deleted. Public records and installed modules are preserved.',flush=True)
        try:
            approved=input('Reset migration state? [y/N] ').strip().lower() in ('y','yes')
        except EOFError:
            approved=False
        if not approved:
            print('Reset cancelled; migration state retained.',flush=True)
            return dict(reset=False)
        # Recheck after confirmation, while the migration lock is still held.
        if matching_directories(root,args,gate.oid)!=directories:
            raise MigrationError('Run directories changed during reset confirmation')
        validate_state(connection,args,gate.oid)
        with connection.cursor() as cr:
            for schema in SCHEMAS:
                cr.execute(sql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(sql.Identifier(schema)))
        connection.commit()
        failures=[]
        for directory in directories:
            try:
                if directory.is_symlink() or directory.resolve().parent!=Path(root).resolve():
                    raise MigrationError('Directory identity changed')
                shutil.rmtree(directory)
            except FileNotFoundError:
                pass
            except Exception:
                failures.append(str(directory))
        if failures:
            raise MigrationError('Schemas reset; directory cleanup incomplete. Retry --reset. Remaining: '+', '.join(failures))
        print('Reset complete. Rerun without --reset to start fresh.',flush=True)
        return dict(reset=True)
    finally:
        if connection is not None:
            connection.close()
        gate.close()
