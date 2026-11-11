#!/usr/bin/env python3
"""Observe an existing migration using read-only PostgreSQL statistics."""
import argparse
from pathlib import Path
import sys
import time
from common import MigrationError,loads
from resume import endpoint
from progress import monitor_factory
from prepared_progress import sample,format_status


def observe(config,stage):
    stage=Path(stage)
    run=loads((stage/'prepared-run.json').read_text())
    if endpoint(config)!=run['target_endpoint']:
        raise MigrationError('Target configuration does not match this run')
    connection=monitor_factory(config,'postgres')()
    try:
        with connection.cursor() as cr:
            cr.execute('SELECT oid FROM pg_database WHERE datname=%s',[run['target_db']])
            if cr.fetchone()!=(run['target_oid'],):
                raise MigrationError('Target database identity changed')
        state=stage/'availability.json'
        if not state.exists():
            return ['No registered target sessions yet; no completion status inferred.']
        availability=loads(state.read_text())
        if availability['oid']!=run['target_oid'] or availability['database']!=run['target_db']:
            raise MigrationError('Registered target identity mismatch')
        manifest_path=stage/'snapshot.json'
        manifest=loads(manifest_path.read_text()) if manifest_path.exists() else {}
        messages=[]
        for session in availability['sessions']:
            status=sample(connection,run['target_oid'],session['pid'],session['started'])
            event=dict(kind='progress',phase='observer',operation=f'backend {session["pid"]}',elapsed=0,database=status)
            # Only a known table identifier is exposed, never raw query text/values.
            if 'copy_rows' in status:
                with connection.cursor() as cr:
                    cr.execute("SELECT substring(query FROM '^COPY \"prepared_migration_source\"[.]\"([^\"]+)\"') "
                               'FROM pg_stat_activity WHERE datid=%s AND pid=%s AND backend_start=%s::timestamptz',
                               [run['target_oid'],session['pid'],session['started']])
                    row=cr.fetchone()
                table=row[0] if row else None
                meta=manifest.get('tables',{}).get(table)
                event.update(processed=status['copy_rows'],bytes=status['copy_bytes'])
                if meta:
                    event.update(table=table,total=meta['rows'],bytes_total=meta['bytes'],operation='COPY FROM')
            messages.append(format_status(event))
        backup=stage/'before_import.dump'
        if backup.exists():
            messages.append(f'Observed backup file size: {backup.stat().st_size:,} bytes')
        return messages
    finally:
        connection.close()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-config',required=True)
    parser.add_argument('--stage',type=Path,required=True)
    parser.add_argument('--once',action='store_true',help='Print one observation and exit')
    args=parser.parse_args(argv)
    while True:
        try:
            for message in observe(args.target_config,args.stage):
                print(message,flush=True)
        except MigrationError:
            raise
        except Exception as exc:
            print(f'Progress unavailable: {type(exc).__name__}; migration is unaffected.',flush=True)
        if args.once:
            return
        time.sleep(5)


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except MigrationError as exc:
        print(str(exc),file=sys.stderr)
        sys.exit(2)
