import hashlib
import json
from pathlib import Path
from contextlib import contextmanager
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class Conflict(Exception):
    pass


class Store:
    def __new__(cls, database_url):
        if database_url.startswith('sqlite:'):
            from .sqlite_storage import SQLiteStore

            return SQLiteStore(database_url)
        return super().__new__(cls)

    def __init__(self, database_url):
        self.database_url = database_url

    def connect(self):
        return psycopg.connect(
            self.database_url, row_factory=dict_row, connect_timeout=5
        )

    def migrate(self):
        with self.connect() as conn:
            conn.execute(
                Path(__file__).parents[1].joinpath('migrations/0001.sql').read_text()
            )

    def ingest(self, account, events):
        with self.connect() as conn:
            self._ingest(conn, account, events)

    def _ingest(self, conn, account, events):
        for key, kind, payload in events:
            digest = hashlib.sha256(
                json.dumps([kind, payload], sort_keys=True).encode()
            ).hexdigest()
            conn.execute(
                'INSERT INTO incoming_event(account,event_key,kind,fingerprint,payload,state) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (
                    account,
                    key,
                    kind,
                    digest,
                    Jsonb(payload),
                    'ignored' if kind == 'ignored' else 'pending',
                ),
            )
            row = conn.execute(
                'SELECT fingerprint FROM incoming_event WHERE account=%s AND event_key=%s',
                (account, key),
            ).fetchone()
            if row['fingerprint'] != digest:
                raise Conflict('Conflicting event identity')

    @contextmanager
    def receiver(self, provider_account):
        key = int.from_bytes(
            hashlib.sha256(('telegram:' + provider_account).encode()).digest()[:8],
            'big',
            signed=True,
        )
        with self.connect() as conn:
            locked = conn.execute(
                'SELECT pg_try_advisory_lock(%s) AS locked', (key,)
            ).fetchone()['locked']
            conn.commit()
            if not locked:
                raise Conflict('A receiver already owns this bot')
            try:
                yield conn
            finally:
                conn.close()

    def polling_offset(self, conn, provider_account):
        row = conn.execute(
            'SELECT next_offset FROM telegram_polling WHERE provider_account=%s',
            (provider_account,),
        ).fetchone()
        conn.commit()
        return row['next_offset'] if row else 0

    def persist_poll(self, conn, code, provider_account, events, next_offset):
        with conn.transaction():
            self._ingest(conn, code, events)
            conn.execute(
                'INSERT INTO telegram_polling(provider_account,next_offset) VALUES (%s,%s) ON CONFLICT(provider_account) DO UPDATE SET next_offset=GREATEST(telegram_polling.next_offset,EXCLUDED.next_offset),updated_at=now()',
                (provider_account, next_offset),
            )

    def claim_incoming(self):
        with self.connect() as conn:
            return conn.execute(
                """UPDATE incoming_event SET state='processing', lease_until=now()+interval '60 seconds', attempts=attempts+1
                WHERE id=(SELECT candidate.id FROM incoming_event candidate WHERE ((candidate.state='pending' AND candidate.available_at<=now())
                    OR (candidate.state='processing' AND candidate.lease_until<now()))
                    AND NOT EXISTS (SELECT 1 FROM incoming_event earlier WHERE earlier.account=candidate.account
                        AND COALESCE(earlier.payload->>'sender',earlier.payload->>'destination','')=COALESCE(candidate.payload->>'sender',candidate.payload->>'destination','')
                        AND earlier.id<candidate.id AND earlier.state NOT IN ('done','ignored'))
                    ORDER BY candidate.id FOR UPDATE OF candidate SKIP LOCKED LIMIT 1) RETURNING *"""
            ).fetchone()

    def finish_incoming(self, row, success):
        with self.connect() as conn:
            conn.execute(
                """UPDATE incoming_event SET state=%s, error=%s, available_at=now()+(%s * interval '1 second'), lease_until=NULL
                WHERE id=%s AND attempts=%s AND lease_until=%s AND state='processing'""",
                (
                    (
                        'done'
                        if success
                        else ('review' if row['attempts'] >= 8 else 'pending')
                    ),
                    None if success else 'odoo_rejected_or_unavailable',
                    min(3600, 2 ** row['attempts']),
                    row['id'],
                    row['attempts'],
                    row['lease_until'],
                ),
            )

    def defer_incoming(self, row):
        with self.connect() as conn:
            conn.execute(
                """UPDATE incoming_event SET state='pending', attempts=attempts-1,
                error='odoo_unavailable', available_at=now()+interval '30 seconds', lease_until=NULL
                WHERE id=%s AND attempts=%s AND lease_until=%s AND state='processing'""",
                (row['id'], row['attempts'], row['lease_until']),
            )

    def persist_outgoing(self, account, payload):
        frozen = {key: value for key, value in payload.items() if key != 'lease'}
        with self.connect() as conn:
            conn.execute(
                'INSERT INTO outgoing_operation(account,token,attempt,receipt,payload) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                (
                    account,
                    payload['token'],
                    payload['attempt'],
                    str(uuid4()),
                    Jsonb(frozen),
                ),
            )
            row = conn.execute(
                'SELECT * FROM outgoing_operation WHERE account=%s AND token=%s AND attempt=%s',
                (account, payload['token'], payload['attempt']),
            ).fetchone()
            if row['payload'] != frozen:
                raise Conflict('Conflicting outgoing operation')
            return row

    def stored(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM outgoing_operation WHERE state='stored' ORDER BY id LIMIT 50"
            ).fetchall()

    def defer_send(self, row):
        with self.connect() as conn:
            conn.execute(
                "UPDATE outgoing_operation SET state='ready', sends=sends-1, available_at=now()+interval '30 seconds' WHERE id=%s AND state='sending' AND sends=%s",
                (row['id'], row['sends']),
            )

    def mark_ready(self, row):
        with self.connect() as conn:
            conn.execute(
                "UPDATE outgoing_operation SET state='ready' WHERE id=%s AND state='stored'",
                (row['id'],),
            )

    def recover_sending(self):
        with self.connect() as conn:
            conn.execute(
                """UPDATE outgoing_operation SET state='report', outcome=%s
                WHERE state='sending' AND lease_until<now()""",
                (Jsonb({'status': 'review', 'reference': '', 'error': 'ambiguous'}),),
            )

    def claim_outgoing(self, accounts):
        with self.connect() as conn:
            return conn.execute(
                """UPDATE outgoing_operation SET state='sending', sends=sends+1, lease_until=now()+interval '120 seconds'
                WHERE id=(SELECT candidate.id FROM outgoing_operation candidate WHERE candidate.state='ready' AND candidate.available_at<=now() AND candidate.account=ANY(%s)
                AND NOT EXISTS (SELECT 1 FROM outgoing_operation earlier WHERE earlier.account=candidate.account
                    AND earlier.payload->>'destination'=candidate.payload->>'destination' AND earlier.id<candidate.id
                    AND (earlier.state!='done' OR earlier.outcome->>'status'='review'))
                ORDER BY candidate.id FOR UPDATE OF candidate SKIP LOCKED LIMIT 1) RETURNING *""",
                (accounts,),
            ).fetchone()

    def outcome(self, row, outcome):
        retry = (
            outcome['status'] == 'failed'
            and outcome['error'] in ('rate_limit', 'unavailable')
            and row['sends'] < 5
        )
        with self.connect() as conn:
            conn.execute(
                """UPDATE outgoing_operation SET state=%s, outcome=%s, available_at=now()+(%s * interval '1 second')
                WHERE id=%s AND state='sending' AND sends=%s""",
                (
                    'ready' if retry else 'report',
                    Jsonb(outcome),
                    outcome.get('retry_after', 30),
                    row['id'],
                    row['sends'],
                ),
            )

    def reports(self):
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM outgoing_operation WHERE state='report' ORDER BY id LIMIT 50"
            ).fetchall()

    def reported(self, row):
        with self.connect() as conn:
            conn.execute(
                "UPDATE outgoing_operation SET state='done' WHERE id=%s AND state='report'",
                (row['id'],),
            )
