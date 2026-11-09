import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

TABLES = ('incoming_event', 'outgoing_operation', 'operator_audit', 'telegram_polling')
MAX_BYTES = 512 * 1024 * 1024
MAX_RECORDS = 1000000


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def normalize(row):
    return {
        key: value.timestamp() if isinstance(value, datetime) else value
        for key, value in row.items()
    }


def snapshot(conn):
    for table in TABLES:
        key = 'provider_account' if table == 'telegram_polling' else 'id'
        last = None
        placeholder = '?' if hasattr(conn, 'store') else '%s'
        while True:
            where = f'WHERE {key} > {placeholder}' if last is not None else ''
            rows = conn.execute(
                f'SELECT * FROM {table} {where} ORDER BY {key} LIMIT 1',
                (last,) if last is not None else (),
            ).fetchall()
            if not rows:
                break
            row = rows[0]
            yield {'table': table, 'row': normalize(row)}
            last = row[key]


def digest_records(records):
    digests = {table: hashlib.sha256() for table in TABLES}
    counts = dict.fromkeys(TABLES, 0)
    for item in records:
        table = item['table']
        counts[table] += 1
        digests[table].update((canonical(item['row']) + '\n').encode())
    return {
        table: {'count': counts[table], 'sha256': digests[table].hexdigest()}
        for table in TABLES
    }


def export_queue(store, destination, *, quiesced=False):
    if not quiesced:
        raise ValueError(
            'Stop all messaging processes and explicitly confirm quiescence'
        )
    path = Path(destination)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('Export and backup directories must be private (0700)')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w') as output, store.connect() as conn:
            if not store.database_url.startswith('sqlite:'):
                conn.execute(
                    'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
                )
            output.write(canonical({'format': 'crm-queue-v1'}) + '\n')
            size = 0
            count = 0

            def records():
                nonlocal size, count
                for item in snapshot(conn):
                    line = canonical(item) + '\n'
                    size += len(line.encode())
                    count += 1
                    if size > MAX_BYTES or count > MAX_RECORDS:
                        raise ValueError('Bounded export limit exceeded')
                    output.write(line)
                    yield item

            summary = digest_records(records())
            output.write(canonical({'summary': summary}) + '\n')
            output.flush()
            os.fsync(output.fileno())
        sync_directory(path.parent)
        return summary
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def read_export(source):
    path = Path(source)
    if path.stat().st_size > MAX_BYTES + 10000 or path.stat().st_mode & 0o077:
        raise ValueError('Export must be private and within the size limit')
    with path.open() as stream:
        if json.loads(stream.readline()) != {'format': 'crm-queue-v1'}:
            raise ValueError('Unsupported queue export')
        count = 0
        summary = None
        for line in stream:
            item = json.loads(line)
            if summary is not None:
                raise ValueError('Trailing export data')
            if 'summary' in item:
                summary = item['summary']
                continue
            count += 1
            if (
                count > MAX_RECORDS
                or item.get('table') not in TABLES
                or not isinstance(item.get('row'), dict)
            ):
                raise ValueError('Invalid queue export')
            yield item
        if summary is None:
            raise ValueError('Incomplete queue export')
        return summary


def import_queue(store, source):
    if not store.database_url.startswith('sqlite:'):
        raise ValueError('Import destination must be a fresh SQLite queue')
    store.migrate()
    with store.connect() as conn:
        if any(
            conn.execute(f'SELECT count(*) AS count FROM {table}').fetchone()['count']
            for table in TABLES
        ):
            raise ValueError('Import requires an empty queue')
        iterator = read_export(source)
        digests = {table: hashlib.sha256() for table in TABLES}
        counts = dict.fromkeys(TABLES, 0)
        while True:
            try:
                item = next(iterator)
            except StopIteration as end:
                expected = end.value
                break
            table, row = item['table'], item['row']
            columns = {
                r['name']
                for r in conn.execute(f'PRAGMA table_info({table})').fetchall()
            }
            if set(row) != columns:
                raise ValueError('Queue columns do not match')
            counts[table] += 1
            digests[table].update((canonical(row) + '\n').encode())
            values = [
                (
                    canonical(value)
                    if key in ('payload', 'outcome') and value is not None
                    else value
                )
                for key, value in row.items()
            ]
            conn.execute(
                f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
                values,
            )
        actual = {
            table: {'count': counts[table], 'sha256': digests[table].hexdigest()}
            for table in TABLES
        }
        if expected != actual or digest_records(snapshot(conn)) != expected:
            raise ValueError('Queue counts or record digests do not match')
        if conn.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Queue references are invalid')
        return actual


def backup_queue(store, destination):
    import apsw

    if not store.database_url.startswith('sqlite:'):
        raise ValueError('Online backup requires SQLite')
    path = Path(destination)
    if path.parent.stat().st_mode & 0o077:
        raise ValueError('Export and backup directories must be private (0700)')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    started = time.monotonic()
    try:
        with store.connect(transaction=False) as source:
            target = apsw.Connection(str(path))
            try:
                with target.backup('main', source.raw, 'main') as backup:
                    while not backup.done:
                        if time.monotonic() - started > 60:
                            raise TimeoutError('Backup exceeded its bounded duration')
                        try:
                            backup.step(256)
                        except (apsw.BusyError, apsw.LockedError):
                            time.sleep(0.05)
                if target.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise ValueError('Backup integrity check failed')
            finally:
                target.close()
        with path.open('rb') as result:
            os.fsync(result.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    sync_directory(path.parent)
    return {'backup': str(path), 'seconds': time.monotonic() - started}
