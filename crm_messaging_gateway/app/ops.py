import argparse
import getpass
import hashlib
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
    parser.add_argument('--account')
    parser.add_argument('--event-id', type=int)
    parser.add_argument('--note')
    parser.add_argument('--file')
    parser.add_argument('--quiesced', action='store_true')
    args = parser.parse_args()
    config = settings(load_provider_tokens=False)
    if args.account is not None:
        if args.command != 'status':
            parser.error('--account is only supported for status')
        if args.account not in config.accounts:
            parser.error('Unknown account')
    store = Store(config.database_url.get_secret_value())
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
            placeholder = '?' if sqlite else '%s'
            scope = f' AND account={placeholder}' if args.account is not None else ''
            parameters = (args.account,) if args.account is not None else ()
            polling_scope = f' WHERE provider_account={placeholder}' if args.account is not None else ''
            polling_parameters = (config.accounts[args.account].provider_account,) if args.account is not None else ()
            incoming = conn.execute(
                'SELECT account,state,count(*) AS count FROM incoming_event WHERE 1=1' + scope + ' GROUP BY account,state ORDER BY account,state', parameters
            ).fetchall()
            outgoing = conn.execute(
                'SELECT account,state,count(*) AS count FROM outgoing_operation WHERE 1=1' + scope + ' GROUP BY account,state ORDER BY account,state', parameters
            ).fetchall()
            polling = conn.execute(
                'SELECT provider_account,next_offset,updated_at FROM telegram_polling' + polling_scope + ' ORDER BY provider_account', polling_parameters
            ).fetchall()
            from .health import reception_health, website_queue_health

            backlog = conn.execute(
                "SELECT account,MIN(created_at) AS oldest FROM incoming_event WHERE state NOT IN ('done','ignored') " + scope + " GROUP BY account", parameters
            ).fetchall()
            health_config = config.model_copy(update={'accounts': {args.account: config.accounts[args.account]}}) if args.account is not None else config
            health = reception_health(health_config, polling, backlog)
            website_queue = conn.execute(
                "SELECT id,account,state,sends,created_at,payload->>'website_destination' AS destination,"
                "outcome->>'status' AS outcome_status,outcome->>'website_failure' AS failure "
                "FROM outgoing_operation WHERE payload->>'provider'='website' "
                "AND state!='superseded' AND (state!='done' OR outcome->>'status'='review')" + scope + ' ORDER BY created_at', parameters
            ).fetchall()
            metrics = {'website': website_queue_health(website_queue)}
            if not sqlite:
                for table in ('incoming_event', 'outgoing_operation'):
                    row = conn.execute(
                        f"SELECT EXTRACT(EPOCH FROM now()-MIN(created_at)) AS age FROM {table} WHERE state NOT IN ('done','ignored')" + scope, parameters
                    ).fetchone()
                    metrics[table + '_oldest_seconds'] = float(row['age'] or 0)
                metrics['polling_heartbeat_age_seconds'] = [float(row['age']) for row in conn.execute(
                    'SELECT EXTRACT(EPOCH FROM now()-updated_at) AS age FROM telegram_polling' + polling_scope, polling_parameters
                ).fetchall()]
                metrics['uncertain'] = conn.execute(
                    "SELECT count(*) AS count FROM outgoing_operation WHERE outcome->>'status'='review'" + scope, parameters
                ).fetchone()['count']
            if sqlite:
                import shutil
                import time

                for table in ('incoming_event', 'outgoing_operation'):
                    row = conn.execute(
                        f"SELECT MIN(created_at) AS oldest FROM {table} WHERE state NOT IN ('done','ignored')" + scope, parameters
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
                    "SELECT count(*) AS count FROM outgoing_operation WHERE outcome->>'status'='review'" + scope, parameters
                ).fetchone()['count']
        print(
            json.dumps(
                {
                    'incoming': incoming,
                    'outgoing': outgoing,
                    'polling': polling,
                    'metrics': metrics,
                    'reception_health': health,
                    'website_queue': website_queue,
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
            lock = '' if sqlite else ' FOR UPDATE'
            current = conn.execute(
                f"SELECT * FROM incoming_event WHERE id={placeholder} AND state='review'" + lock,
                (args.event_id,),
            ).fetchone()
            if not current:
                parser.error('Event is not awaiting review')
            payload = dict(current['payload'])
            if current['kind'] == 'incoming' and payload.get('review_reason') == 'unsupported_identity':
                payload.pop('review_reason')
            digest = hashlib.sha256(json.dumps([current['kind'], payload], sort_keys=True).encode()).hexdigest()
            conn.execute(
                f"UPDATE incoming_event SET state='pending',attempts=0,available_at=now(),lease_until=NULL,payload={placeholder},fingerprint={placeholder} WHERE id={placeholder}",
                (json.dumps(payload, sort_keys=True), digest, args.event_id),
            )
            conn.execute(
                f'INSERT INTO operator_audit(event_id,actor,note) VALUES ({placeholder},{placeholder},{placeholder})',
                (args.event_id, getpass.getuser(), args.note),
            )


if __name__ == '__main__':
    main()
