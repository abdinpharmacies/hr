import argparse
import getpass
import json

from .config import settings
from .storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'command', choices=('migrate', 'status', 'review', 'retry-incoming')
    )
    parser.add_argument('--event-id', type=int)
    parser.add_argument('--note')
    args = parser.parse_args()
    store = Store(settings().database_url.get_secret_value())
    if args.command == 'migrate':
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
                'SELECT provider_account,next_offset,updated_at::text FROM telegram_polling ORDER BY provider_account'
            ).fetchall()
        print(
            json.dumps({'incoming': incoming, 'outgoing': outgoing, 'polling': polling})
        )
    elif args.command == 'review':
        with store.connect() as conn:
            rows = conn.execute(
                "SELECT id,account,kind,state,attempts,error FROM incoming_event WHERE state='review' ORDER BY id"
            ).fetchall()
            outgoing = conn.execute(
                "SELECT id,account,state,outcome->>'error' AS error FROM outgoing_operation WHERE outcome->>'status'='review' ORDER BY id"
            ).fetchall()
        print(json.dumps({'incoming': rows, 'outgoing': outgoing}))
    else:
        if not args.event_id or not args.note or len(args.note) > 2000:
            parser.error('A reviewed event ID and note are required')
        with store.connect() as conn:
            row = conn.execute(
                "UPDATE incoming_event SET state='pending',attempts=0,available_at=now() WHERE id=%s AND state='review' RETURNING id",
                (args.event_id,),
            ).fetchone()
            if not row:
                parser.error('Event is not awaiting review')
            conn.execute(
                'INSERT INTO operator_audit(event_id,actor,note) VALUES (%s,%s,%s)',
                (args.event_id, getpass.getuser(), args.note),
            )


if __name__ == '__main__':
    main()
