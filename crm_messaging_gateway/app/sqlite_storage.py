import fcntl
import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

import apsw

from .storage import Conflict


def encode(value):
    return json.dumps(value, sort_keys=True)


def row_factory(cursor, values):
    row = dict(zip((column[0] for column in cursor.get_description()), values))
    for key in ('payload', 'outcome'):
        if key in row and row[key] is not None:
            row[key] = json.loads(row[key])
    return row


class Result:
    def __init__(self, rows):
        self.rows = iter(rows)

    def fetchone(self):
        return next(self.rows, None)

    def fetchall(self):
        return list(self.rows)


class Connection:
    def __init__(self, store, transaction):
        self.store = store
        self.closed = False
        self.broken = False
        self.automatic_transaction = transaction
        self.raw = apsw.Connection(str(store.path))
        try:
            self.raw.set_busy_timeout(store.busy_timeout)
            self.raw.create_scalar_function('now', time.time, 0)
            if self.raw.execute('PRAGMA journal_mode=WAL').fetchone()[0] != 'wal':
                raise RuntimeError('WAL mode is required')
            self.raw.execute('PRAGMA foreign_keys=ON')
            self.raw.execute('PRAGMA synchronous=FULL')
            self.raw.set_row_trace(row_factory)
        except BaseException:
            self.raw.close()
            self.closed = True
            raise

    def execute(self, sql, parameters=()):
        return Result(list(self.raw.execute(sql, parameters)))

    def begin(self):
        for attempt in range(self.store.retries + 1):
            try:
                self.execute('BEGIN IMMEDIATE')
                return
            except apsw.BusyError:
                logging.warning('SQLite writer contention attempt=%s', attempt + 1)
                if attempt == self.store.retries:
                    raise
                time.sleep(min(0.25, 0.01 * 2**attempt))

    def commit(self):
        if not self.raw.get_autocommit():
            self.execute('COMMIT')

    def rollback(self):
        if not self.raw.get_autocommit():
            self.execute('ROLLBACK')

    @contextmanager
    def transaction(self):
        self.begin()
        try:
            yield self
            self.commit()
        except BaseException:
            self.rollback()
            raise

    def __enter__(self):
        try:
            if self.automatic_transaction:
                self.begin()
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, kind, value, traceback):
        try:
            if kind:
                self.rollback()
            else:
                self.commit()
        finally:
            self.close()

    def close(self):
        self.raw.close()
        self.closed = True


class SQLiteStore:
    def __init__(self, database_url):
        if tuple(map(int, apsw.sqlitelibversion().split('.'))) < (3, 51, 3):
            raise RuntimeError('SQLite 3.51.3 or later is required')
        self.database_url = database_url
        url = urlsplit(database_url)
        self.path = Path(unquote(url.path))
        options = parse_qs(url.query)
        if (
            url.netloc
            or not self.path.is_absolute()
            or self.path.name in ('', ':memory:')
        ):
            raise ValueError('A local absolute SQLite file path is required')
        if options.keys() - {'busy_timeout_ms', 'contention_retries'}:
            raise ValueError('Unsupported SQLite options')
        self.busy_timeout = int(options.get('busy_timeout_ms', ['1000'])[0])
        self.retries = int(options.get('contention_retries', ['3'])[0])
        if not 1 <= self.busy_timeout <= 10000 or not 0 <= self.retries <= 8:
            raise ValueError('Invalid SQLite contention limits')
        if not self.path.parent.is_dir() or self.path.parent.stat().st_mode & 0o077:
            raise RuntimeError(
                'SQLite requires an existing private persistent directory (0700)'
            )
        if self.path.is_symlink() or (
            self.path.exists() and self.path.stat().st_mode & 0o077
        ):
            raise RuntimeError('SQLite database must be a private regular file')

    def connect(self, transaction=True):
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        return Connection(self, transaction)

    def migrate(self):
        with self.connect(transaction=False) as conn:
            mode = conn.execute('PRAGMA journal_mode=WAL').fetchone()
            if next(iter(mode.values())) != 'wal':
                raise RuntimeError('WAL mode is required')
            with conn.transaction():
                conn.execute(
                    Path(__file__)
                    .parents[1]
                    .joinpath('migrations/sqlite.sql')
                    .read_text()
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
                'INSERT INTO incoming_event(account,event_key,kind,fingerprint,payload,state) VALUES (?,?,?,?,?,?) ON CONFLICT DO NOTHING',
                (
                    account,
                    key,
                    kind,
                    digest,
                    encode(payload),
                    'ignored' if kind == 'ignored' else 'pending',
                ),
            )
            row = conn.execute(
                'SELECT fingerprint FROM incoming_event WHERE account=? AND event_key=?',
                (account, key),
            ).fetchone()
            if row['fingerprint'] != digest:
                raise Conflict('Conflicting event identity')

    @contextmanager
    def receiver(self, provider_account):
        key = hashlib.sha256(('telegram:' + provider_account).encode()).hexdigest()
        path = self.path.parent / ('receiver-' + key + '.lock')
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Conflict('A receiver already owns this bot') from None
            with self.connect(transaction=False) as conn:
                yield conn
        finally:
            os.close(descriptor)

    def polling_offset(self, conn, provider_account):
        row = conn.execute(
            'SELECT next_offset FROM telegram_polling WHERE provider_account=?',
            (provider_account,),
        ).fetchone()
        conn.commit()
        return row['next_offset'] if row else 0

    def persist_poll(self, conn, code, provider_account, events, next_offset):
        with conn.transaction():
            self._ingest(conn, code, events)
            conn.execute(
                'INSERT INTO telegram_polling(provider_account,next_offset) VALUES (?,?) ON CONFLICT(provider_account) DO UPDATE SET next_offset=MAX(telegram_polling.next_offset,EXCLUDED.next_offset),updated_at=now()',
                (provider_account, next_offset),
            )

    def claim_incoming(self):
        with self.connect() as conn:
            return conn.execute(
                """UPDATE incoming_event SET state='processing', lease_until=now()+60, attempts=attempts+1
                WHERE id=(SELECT candidate.id FROM incoming_event candidate WHERE ((candidate.state='pending' AND candidate.available_at<=now())
                    OR (candidate.state='processing' AND candidate.lease_until<now()))
                    AND NOT EXISTS (SELECT 1 FROM incoming_event earlier WHERE earlier.account=candidate.account
                        AND COALESCE(earlier.payload->>'sender',earlier.payload->>'destination','')=COALESCE(candidate.payload->>'sender',candidate.payload->>'destination','')
                        AND earlier.id<candidate.id AND earlier.state NOT IN ('done','ignored'))
                    ORDER BY candidate.id LIMIT 1) RETURNING *"""
            ).fetchone()

    def finish_incoming(self, row, success):
        with self.connect() as conn:
            conn.execute(
                """UPDATE incoming_event SET state=?, error=?, available_at=now()+?, lease_until=NULL
                WHERE id=? AND attempts=? AND lease_until=? AND state='processing'""",
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
                error='odoo_unavailable', available_at=now()+30, lease_until=NULL
                WHERE id=? AND attempts=? AND lease_until=? AND state='processing'""",
                (row['id'], row['attempts'], row['lease_until']),
            )

    def persist_outgoing(self, account, payload):
        frozen = {key: value for key, value in payload.items() if key != 'lease'}
        with self.connect() as conn:
            conn.execute(
                'INSERT INTO outgoing_operation(account,token,attempt,receipt,payload) VALUES (?,?,?,?,?) ON CONFLICT DO NOTHING',
                (
                    account,
                    payload['token'],
                    payload['attempt'],
                    str(uuid4()),
                    encode(frozen),
                ),
            )
            row = conn.execute(
                'SELECT * FROM outgoing_operation WHERE account=? AND token=? AND attempt=?',
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
                "UPDATE outgoing_operation SET state='ready', sends=sends-1, available_at=now()+30 WHERE id=? AND state='sending' AND sends=?",
                (row['id'], row['sends']),
            )

    def mark_ready(self, row):
        with self.connect() as conn:
            conn.execute(
                "UPDATE outgoing_operation SET state='ready' WHERE id=? AND state='stored'",
                (row['id'],),
            )

    def recover_sending(self):
        with self.connect() as conn:
            conn.execute(
                """UPDATE outgoing_operation SET state='report', outcome=?
                WHERE state='sending' AND lease_until<now()""",
                (encode({'status': 'review', 'reference': '', 'error': 'ambiguous'}),),
            )

    def claim_outgoing(self, accounts):
        with self.connect() as conn:
            return conn.execute(
                """UPDATE outgoing_operation SET state='sending', sends=sends+1, lease_until=now()+120
                WHERE id=(SELECT candidate.id FROM outgoing_operation candidate WHERE candidate.state='ready' AND candidate.available_at<=now() AND candidate.account IN (SELECT value FROM json_each(?))
                AND NOT EXISTS (SELECT 1 FROM outgoing_operation earlier WHERE earlier.account=candidate.account
                    AND earlier.payload->>'destination'=candidate.payload->>'destination' AND earlier.id<candidate.id
                    AND (earlier.state!='done' OR earlier.outcome->>'status'='review'))
                ORDER BY candidate.id LIMIT 1) RETURNING *""",
                (encode(accounts),),
            ).fetchone()

    def outcome(self, row, outcome):
        retry = (
            outcome['status'] == 'failed'
            and outcome['error'] in ('rate_limit', 'unavailable')
            and row['sends'] < 5
        )
        with self.connect() as conn:
            conn.execute(
                """UPDATE outgoing_operation SET state=?, outcome=?, available_at=now()+?
                WHERE id=? AND state='sending' AND sends=?""",
                (
                    'ready' if retry else 'report',
                    encode(outcome),
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
                "UPDATE outgoing_operation SET state='done' WHERE id=? AND state='report'",
                (row['id'],),
            )
