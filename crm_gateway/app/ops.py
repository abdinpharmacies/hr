import argparse
import json

from sqlalchemy import select

from .storage import Delivery, sessions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['status', 'retry'])
    parser.add_argument('--id')
    args = parser.parse_args()
    with sessions()() as session, session.begin():
        if args.action == 'retry':
            row = session.get(Delivery, args.id)
            if not row or row.state != 'review' or row.kind not in ('message', 'website', 'website_update'):
                raise SystemExit('Only reviewed idempotent inbound or sync deliveries can be retried; uncertain replies require provider reconciliation.')
            row.state = 'pending'
            row.attempts = 0
            row.error = None
        else:
            for row in session.scalars(select(Delivery).order_by(Delivery.created_at.desc()).limit(100)):
                print(json.dumps({'id': row.id, 'kind': row.kind, 'state': row.state, 'attempts': row.attempts,
                                  'last_success': str(row.last_success or ''), 'error': row.error}))


if __name__ == '__main__':
    main()
