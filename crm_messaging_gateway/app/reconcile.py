import argparse
import getpass
import hashlib
import json

import httpx

from .config import settings
from .odoo import Odoo
from .storage import Store


def selected_rows(conn, store, account, event_ids):
    if not event_ids or len(event_ids) > 500 or any(type(value) is not int or value < 1 for value in event_ids):
        raise ValueError('Select between one and 500 explicit event IDs')
    placeholder = '?' if store.database_url.startswith('sqlite:') else '%s'
    rows = []
    for event_id in sorted(set(event_ids)):
        row = conn.execute(f'SELECT * FROM incoming_event WHERE id={placeholder}', (event_id,)).fetchone()
        if not row or row['account'] != account or row['kind'] != 'status' or row['state'] not in ('pending', 'review'):
            raise ValueError('Selection must contain only pending/review status events for this account')
        if set(row['payload']) != {'reference', 'destination', 'status'}:
            raise ValueError('Invalid status event payload')
        rows.append(row)
    return rows


def preview(store, odoo, account, event_ids):
    with store.connect() as conn:
        rows = selected_rows(conn, store, account, event_ids)
    result = []
    for row in rows:
        match = odoo.call('preview_status', account, **row['payload'])['match']
        if match not in ('operation', 'historical', 'orphan', 'unverified', 'ambiguous'):
            raise ValueError('Invalid status preview')
        result.append({'id': row['id'], 'account': account, 'fingerprint': row['fingerprint'], 'state': row['state'], 'match': match})
    digest = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return {'events': result, 'digest': digest}


def apply(store, odoo, account, event_ids, digest, action, note):
    if action not in ('retry', 'ignore') or not isinstance(note, str) or not note.strip() or len(note) > 2000:
        raise ValueError('An action and mandatory reason (1-2000 characters) are required')
    report = preview(store, odoo, account, event_ids)
    if report['digest'] != digest:
        raise ValueError('Preview changed; review a new preview before applying')
    allowed = ('operation', 'historical') if action == 'retry' else ('orphan',)
    if any(row['match'] not in allowed for row in report['events']):
        raise ValueError('Only verified matches can be retried; only confirmed orphans can be ignored')
    placeholder = '?' if store.database_url.startswith('sqlite:') else '%s'
    lock = '' if placeholder == '?' else ' FOR UPDATE'
    with store.connect() as conn:
        for expected in report['events']:
            row = conn.execute(f'SELECT state,fingerprint FROM incoming_event WHERE id={placeholder}' + lock, (expected['id'],)).fetchone()
            if not row or row['state'] != expected['state'] or row['fingerprint'] != expected['fingerprint']:
                raise ValueError('Event changed after preview; nothing was applied')
            conn.execute(
                f"UPDATE incoming_event SET state={placeholder},attempts=0,available_at=now(),lease_until=NULL,error=NULL WHERE id={placeholder}",
                ('pending' if action == 'retry' else 'ignored', expected['id']),
            )
            conn.execute(
                f'INSERT INTO operator_audit(event_id,actor,note) VALUES ({placeholder},{placeholder},{placeholder})',
                (expected['id'], getpass.getuser(), json.dumps({'action': action, 'match': expected['match'], 'preview': digest, 'reason': note.strip()}, sort_keys=True)),
            )
    return {'action': action, 'event_ids': [row['id'] for row in report['events']]}


def main():
    parser = argparse.ArgumentParser(description='Preview and reconcile selected historical WhatsApp receipts without sending messages.')
    parser.add_argument('account')
    parser.add_argument('--event-id', type=int, action='append', required=True)
    parser.add_argument('--apply', choices=('retry', 'ignore'))
    parser.add_argument('--digest')
    parser.add_argument('--note')
    args = parser.parse_args()
    config = settings(load_provider_tokens=False)
    if args.account not in config.accounts or config.accounts[args.account].provider != 'whatsapp':
        parser.error('Select a configured WhatsApp account')
    store = Store(config.database_url.get_secret_value())
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            odoo = Odoo(config, client)
            result = apply(store, odoo, args.account, args.event_id, args.digest, args.apply, args.note) if args.apply else preview(store, odoo, args.account, args.event_id)
        print(json.dumps(result))
    except (ValueError, RuntimeError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
