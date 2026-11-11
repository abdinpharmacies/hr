"""Explicit reset of pre-import migration state; never touches source access."""
import os
from pathlib import Path
import shutil
from psycopg2 import sql
from availability import DatabaseGate
from common import MigrationError, connect, loads
from resume import endpoint, fingerprint
from prepared_staging import VERSION as STAGING_VERSION

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
        records={}
        if cr.fetchone()[0]:
            cr.execute('SELECT name,value FROM prepared_custom_migration.checkpoint')
            raw=dict(cr.fetchall())
            staging=loads(raw['staging_run']) if 'staging_run' in raw else None
            tables=staging.get('tables',[]) if isinstance(staging,dict) else []
            if not isinstance(tables,list) or not all(isinstance(t,str) for t in tables) or len(tables)!=len(set(tables)):
                raise MigrationError('Invalid staging ownership metadata; reset refused')
            def staging_key(name):
                if name in ('staging_run','staging_complete','staging_attempt'):
                    return staging is not None
                if name.startswith(('staging:','staging_failure:')):
                    return staging is not None and name.split(':',1)[1] in tables
                if name.startswith('staging_history:'):
                    parts=name.split(':',2)
                    return staging is not None and len(parts)==3 and parts[1].isdigit() and parts[2] in tables
                return False
            if any(name not in {'run','status','identities'} and not staging_key(name) for name in raw):
                raise MigrationError('Data-copy or unknown checkpoints exist; reset cannot undo imported data')
            records={name:loads(value) for name,value in raw.items()}
            if 'run' in records:
                run=records['run']
                if (run.get('source_db'),run.get('target_db'),run.get('target_oid'))!=(args.source_db,args.target_db,oid) or \
                        run.get('source_endpoint')!=endpoint(args.source_config) or run.get('target_endpoint')!=endpoint(args.target_config):
                    raise MigrationError('Target migration state belongs to another run')
            if records.get('status',{}).get('complete'):
                raise MigrationError('Completed migration cannot be reset by removing metadata')
            if staging:
                binding=staging.get('binding',{})
                if (binding.get('version')!=STAGING_VERSION or not isinstance(binding.get('snapshot'),str)
                        or binding.get('run')!=fingerprint(records.get('run'))):
                    raise MigrationError('Staging run ownership differs; reset refused')
                for name,value in records.items():
                    if name.startswith('staging:'):
                        source=value.get('source',{})
                        if source.get('binding')!=binding or source.get('table')!=name.split(':',1)[1] or not value.get('success'):
                            raise MigrationError('Invalid staging table checkpoint; reset refused')
                    elif name.startswith('staging_failure:') and value.get('binding')!=binding:
                        raise MigrationError('Invalid staging failure ownership; reset refused')
                if 'staging_complete' in records and records['staging_complete']!=staging:
                    raise MigrationError('Invalid staging completion ownership; reset refused')
        cr.execute("SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "WHERE c.relkind IN ('r','p','v','m','f') AND n.nspname IN ('prepared_migration_work','prepared_migration_source')")
        for schema,table in cr.fetchall():
            if schema=='prepared_migration_work':
                raise MigrationError('Committed staging/work tables exist; review prior import before resetting')
            if table in ('res_users','res_partner'):
                continue
            if not records.get('staging_run') or 'staging:'+table not in records:
                raise MigrationError('Unexplained staging table; review ownership before resetting: '+table)


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
