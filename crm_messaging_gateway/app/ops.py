import argparse
import getpass
import json

from .config import settings
from .storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command',
        choices=(
            'migrate',
            'status',
            'review',
            'retry-incoming',
            'export',
            'import',
            'backup',
        ),
    )
    parser.add_argument('--event-id', type=int)
    parser.add_argument('--note')
    parser.add_argument('--file')
    parser.add_argument('--quiesced', action='store_true')
    args = parser.parse_args()
    store = Store(settings(load_provider_tokens=False).database_url.get_secret_value())
    sqlite = store.database_url.startswith('sqlite:')
    if args.command in ('export', 'import', 'backup'):
        from .queue_transfer import export_queue, import_queue, backup_queue

        if not args.file:
            parser.error('--file is required')
        if args.command == 'export':
            result = export_queue(store, args.file, quiesced=args.quiesced)
        elif args.command == 'import':
            result = import_queue(store, args.file)
        else:
            if sqlite:
                result = backup_queue(store, args.file)
            else:
                from .postgres_backup import backup_postgres
                result = backup_postgres(store, args.file)
        print(json.dumps(result))
    elif args.command == 'migrate':
        store.migrate()
    elif args.command == 'status':
        with store.connect() as conn:
            incoming = conn.execute(
                'SELECT account,state,count(*) AS count FROM incoming_event GROUP BY account,state ORDER BY account,state'
            ).fetchall()
            outgoing = conn.execute(
                'SELECT account,state,count(*) AS count FROM outgoing_operation GROUP BY account,state ORDER BY account,state'
            ).fetchall()
            polling = conn.execute(
                'SELECT provider_account,next_offset,updated_at FROM telegram_polling ORDER BY provider_account'
            ).fetchall()
            metrics = {}
            if not sqlite:
                for table in ('incoming_event', 'outgoing_operation'):
                    row = conn.execute(
                        f"SELECT EXTRACT(EPOCH FROM now()-MIN(created_at)) AS age FROM {table} WHERE state NOT IN ('done','ignored')"
                    ).fetchone()
                    metrics[table + '_oldest_seconds'] = float(row['age'] or 0)
                metrics['polling_heartbeat_age_seconds'] = [float(row['age']) for row in conn.execute(
                    'SELECT EXTRACT(EPOCH FROM now()-updated_at) AS age FROM telegram_polling'
                ).fetchall()]
                metrics['uncertain'] = conn.execute(
                    "SELECT count(*) AS count FROM outgoing_operation WHERE outcome->>'status'='review'"
                ).fetchone()['count']
            if sqlite:
                import shutil
                import time

                for table in ('incoming_event', 'outgoing_operation'):
                    row = conn.execute(
                        f"SELECT MIN(created_at) AS oldest FROM {table} WHERE state NOT IN ('done','ignored')"
                    ).fetchone()
                    metrics[table + '_oldest_seconds'] = (
                        max(0, time.time() - row['oldest']) if row['oldest'] else 0
                    )
                metrics['disk_free_bytes'] = shutil.disk_usage(store.path.parent).free
                metrics['database_bytes'] = store.path.stat().st_size
                wal = store.path.with_name(store.path.name + '-wal')
                metrics['wal_bytes'] = wal.stat().st_size if wal.exists() else 0
                metrics['polling_heartbeat_age_seconds'] = [
                    max(0, time.time() - r['updated_at']) for r in polling
                ]
                metrics['uncertain'] = conn.execute(
                    "SELECT count(*) AS count FROM outgoing_operation WHERE outcome->>'status'='review'"
                ).fetchone()['count']
        print(
            json.dumps(
                {
                    'incoming': incoming,
                    'outgoing': outgoing,
                    'polling': polling,
                    'metrics': metrics,
                },
                default=str,
            )
        )
    elif args.command == 'review':
        with store.connect() as conn:
            rows = conn.execute(
                "SELECT id,account,kind,state,attempts,COALESCE(error,payload->>'review_reason') AS error FROM incoming_event WHERE state='review' ORDER BY id"
            ).fetchall()
            outgoing = conn.execute(
                "SELECT id,account,state,outcome->>'error' AS error FROM outgoing_operation WHERE outcome->>'status'='review' ORDER BY id"
            ).fetchall()
        print(json.dumps({'incoming': rows, 'outgoing': outgoing}))
    else:
        placeholder = '?' if sqlite else '%s'
        if not args.event_id or not args.note or len(args.note) > 2000:
            parser.error('A reviewed event ID and note are required')
        with store.connect() as conn:
            row = conn.execute(
                f"UPDATE incoming_event SET state='pending',attempts=0,available_at=now() WHERE id={placeholder} AND state='review' RETURNING id",
                (args.event_id,),
            ).fetchone()
            if not row:
                parser.error('Event is not awaiting review')
            conn.execute(
                f'INSERT INTO operator_audit(event_id,actor,note) VALUES ({placeholder},{placeholder},{placeholder})',
                (args.event_id, getpass.getuser(), args.note),
            )


if __name__ == '__main__':
    main()
