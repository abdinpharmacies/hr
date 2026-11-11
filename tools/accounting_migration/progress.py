"""Bounded asynchronous progress transport, output sinks, and read-only monitoring.

No output or monitoring I/O is performed by begin/update/advance/log. Database
connections belong exclusively to the monitor thread, never to a SQL worker.
"""
import collections
import contextlib
import json
from pathlib import Path
import sys
import threading
import time
import uuid

PREFIX = '@@MIGRATION_PROGRESS@@'
INTERVAL = 5


class Sink:
    def __init__(self, consume, capacity=1024):
        self.consume, self.capacity = consume, capacity
        self.queue = collections.deque()
        self.condition = threading.Condition()
        self.stopping = False
        self.dropped = 0
        self.failed = None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def put(self, event):
        with self.condition:
            if self.stopping:
                return
            if event.get('kind') == 'progress' and not event.get('important'):
                # Preserve only the newest periodic snapshot for an operation.
                self.queue = collections.deque(e for e in self.queue if not (
                    e.get('kind') == 'progress' and not e.get('important')
                    and e.get('operation_id') == event.get('operation_id')))
            if len(self.queue) >= self.capacity:
                victim = next((i for i, e in enumerate(self.queue) if not e.get('important')), 0)
                del self.queue[victim]
                self.dropped += 1
            self.queue.append(event)
            self.condition.notify()

    def _run(self):
        while True:
            with self.condition:
                while not self.queue and not self.stopping:
                    self.condition.wait(.2)
                if not self.queue:
                    return
                event = self.queue.popleft()
                dropped, self.dropped = self.dropped, 0
            try:
                if dropped:
                    self.consume({'kind': 'log', 'text': f'[LOGGING] dropped {dropped} queued messages; latest status retained',
                                  'important': True, 'time': time.time()})
                self.consume(event)
            except Exception as exc:
                # Do not recursively log through a broken sink.
                self.failed = type(exc).__name__

    def close(self, timeout=1):
        with self.condition:
            self.stopping = True
            self.condition.notify_all()
        self.thread.join(timeout)


def format_event(event):
    if event['kind'] == 'log':
        return event['text']
    parts = [f'[{event.get("phase", "migration").upper()}]']
    for key in ('model', 'table', 'operation', 'strategy', 'status'):
        if event.get(key):
            parts.append(f'{key}={event[key]}')
    if event.get('processed') is not None:
        total = event.get('total')
        parts.append(f'processed={event["processed"]:,}' + (f'/{total:,}' if total is not None else ''))
    for key in ('affected', 'bytes', 'copied', 'missing', 'files_examined', 'committed', 'represented_rows', 'mapping_rows_written'):
        if key in event:
            parts.append(f'{key}={event[key]:,}')
    parts.append(f'elapsed={event.get("elapsed", 0):.0f}s')
    if event.get('rate') is not None:
        parts.append(f'rate={event["rate"]:,.0f} rows/s')
    if event.get('eta') is not None:
        parts.append(f'ETA≈{event["eta"]:.0f}s')
    database = event.get('database', {})
    if database:
        parts.append('database=' + database.get('state', 'monitor unavailable'))
        if database.get('query_seconds') is not None:
            parts.append(f'query_elapsed={database["query_seconds"]:.0f}s')
        if database.get('wait_event'):
            parts.append(f'wait={database.get("wait_type")}/{database["wait_event"]}')
        if database.get('blockers'):
            parts.append(f'blocking_pids={database["blockers"]}')
        for name in ('copy_rows', 'copy_bytes'):
            if name in database:
                parts.append(f'{name}={database[name]:,}')
    if event.get('logging_errors'):
        parts.append('logging_errors=' + ','.join(event['logging_errors']))
    return ' | '.join(parts)


class NullProgress:
    def begin(self, *a, **kw): return None
    def operation(self, *a, **kw): return None
    def update(self, *a, **kw): return None
    def advance(self, *a, **kw): return None
    def finish(self, *a, **kw): return None
    def transaction(self, *a, **kw): return None
    def bind(self, *a, **kw): return None
    def log(self, *a, **kw): return None


_current = NullProgress()


def current():
    return _current


class Reporter:
    def __init__(self, stage=None, stream=None, transport=False, interval=INTERVAL):
        self.stream = stream if stream is not None else sys.stdout
        self.stage = Path(stage) if stage is not None else None
        self.transport, self.interval = transport, interval
        self.lock = threading.Lock()
        self.state = {}
        self.started = time.monotonic()
        self.remote = False
        self.backend = None
        self.stop = threading.Event()
        self.sinks = [Sink(self._console)]
        if self.stage is not None and not transport:
            self.sinks.append(Sink(self._file))
        self.thread = threading.Thread(target=self._report, daemon=True)
        self.thread.start()
        self.monitor = threading.Thread(target=self._monitor, daemon=True)
        self.monitor.start()

    def _console(self, event):
        text = PREFIX + json.dumps(event, ensure_ascii=False) if self.transport else format_event(event)
        self.stream.write(text + '\n')
        self.stream.flush()

    def _file(self, event):
        # This method is called only by the file sink thread.
        with (self.stage / 'progress.jsonl').open('a', encoding='utf-8') as file:
            file.write(json.dumps(event, ensure_ascii=False) + '\n')
        with (self.stage / 'migration.log').open('a', encoding='utf-8') as file:
            file.write(format_event(event) + '\n')
        worker = event.get('worker')
        if worker in {'init-target', 'bulk-import', 'bulk-smoke'}:
            with (self.stage / f'{worker}.log').open('a', encoding='utf-8') as file:
                file.write(format_event(event) + '\n')
        if event['kind'] == 'progress':
            from common import save_json
            save_json(self.stage / 'progress.json', event)

    def publish(self, event):
        for sink in self.sinks:
            sink.put(dict(event))

    def snapshot(self):
        with self.lock:
            event = dict(self.state)
            elapsed = time.monotonic() - self.started
        event.update(kind='progress', time=time.time(), elapsed=elapsed)
        processed = event.get('processed')
        event['rate'] = processed / elapsed if processed is not None and elapsed > 0 else None
        event['eta'] = None
        if event.get('batches', 0) >= 3 and elapsed >= 15 and event.get('total') is not None and event.get('rate', 0):
            event['eta'] = max(0, event['total'] - processed) / event['rate']
        return event

    def begin(self, phase, model=None, table=None, total=None, operation=None, **extra):
        with self.lock:
            self.started = time.monotonic()
            self.remote = False
            self.state = dict(operation_id=uuid.uuid4().hex, phase=phase, model=model, table=table,
                              total=total, processed=0 if total is not None else None, batches=0,
                              operation=operation, status='running', **extra)
            token = self.state['operation_id']
        self.emit(True)
        return token

    def emit(self, important=False):
        event = self.snapshot()
        event['important'] = important
        self.publish(event)

    def update(self, token=None, **values):
        with self.lock:
            if token is not None and token != self.state.get('operation_id'):
                return False
            self.state.update(values)
        return True

    def operation(self, name):
        # A sub-operation change invalidates in-flight database-monitor samples.
        with self.lock:
            self.state.update(operation=name, operation_id=uuid.uuid4().hex)
            self.state.pop('database', None)
        self.emit(True)

    def advance(self, rows=0, affected=0, **values):
        with self.lock:
            self.state['processed'] = (self.state.get('processed') or 0) + rows
            self.state['affected'] = self.state.get('affected', 0) + affected
            self.state['batches'] = self.state.get('batches', 0) + 1
            self.state.update(values)
        self.emit(True)

    def finish(self, status='complete; pending commit'):
        self.update(status=status)
        self.emit(True)

    def transaction(self, state, name):
        # Commit/rollback is a transaction event, never the last model's row count.
        self.begin('transaction', operation=name, status_detail=state)
        self.finish(state)

    def log(self, text, important=False, worker=None):
        if text.strip():
            self.publish(dict(kind='log', text=text.rstrip(), important=important, worker=worker, time=time.time()))

    def accept(self, line, worker):
        if line.startswith(PREFIX):
            try:
                event = json.loads(line[len(PREFIX):])
                if event.get('kind') not in ('log', 'progress'):
                    raise ValueError('Unknown event')
            except (ValueError, TypeError):
                self.log('[LOGGING] invalid worker progress event', important=True, worker=worker)
                return
            event['worker'] = worker
            if event['kind'] == 'progress':
                with self.lock:
                    self.state, self.remote = dict(event), True
            self.publish(event)
        else:
            self.log(line, worker=worker)

    def bind(self, factory, pid):
        with self.lock:
            self.backend = (factory, pid) if factory is not None else None

    def _report(self):
        reported_failures = []
        while not self.stop.wait(self.interval):
            with self.lock:
                active = bool(self.state) and not self.remote
            if active:
                self.emit()
            failed = [sink.failed for sink in self.sinks if sink.failed]
            if failed:
                self.update(logging_errors=failed)
                if failed != reported_failures:
                    self.log('[LOGGING] output sink unavailable: ' + ', '.join(failed), important=True)
                    reported_failures = failed

    def _monitor(self):
        connection, bound = None, None
        while not self.stop.wait(self.interval):
            with self.lock:
                backend = self.backend
                token = self.state.get('operation_id')
            if backend is None:
                if connection:
                    with contextlib.suppress(Exception): connection.close()
                    connection = None
                bound = None
                continue
            try:
                if bound != backend or connection is None:
                    if connection:
                        connection.close()
                    connection = backend[0]()
                    bound = backend
                sample = database_sample(connection, backend[1])
                self.update(token=token, database=sample)
            except Exception as exc:
                self.update(token=token, database={'state': 'monitor unavailable', 'error_type': type(exc).__name__})
                if connection:
                    with contextlib.suppress(Exception): connection.close()
                connection, bound = None, None
        if connection:
            with contextlib.suppress(Exception): connection.close()

    def close(self, timeout=1):
        self.stop.set()
        self.thread.join(timeout)
        self.monitor.join(timeout)
        for sink in self.sinks:
            sink.close(timeout)


class TextStream:
    """Redirect existing print/logging calls into nonblocking event queues."""
    encoding = 'utf-8'
    def __init__(self, reporter): self.reporter = reporter
    def write(self, text):
        self.reporter.log(text)
        return len(text)
    def flush(self): pass
    def isatty(self): return False


@contextlib.contextmanager
def session(stage=None, transport=False):
    global _current
    previous, stdout, stderr = _current, sys.stdout, sys.stderr
    reporter = Reporter(stage, stdout, transport)
    _current = reporter
    sys.stdout = sys.stderr = TextStream(reporter)
    try:
        yield reporter
    finally:
        sys.stdout, sys.stderr, _current = stdout, stderr, previous
        reporter.close()


def monitor_factory(config, database):
    # Created in the SQL owner's thread; connects only inside the monitor thread.
    from common import settings
    opts = settings(config)
    params = {k[3:]: opts[k] for k in ('db_host', 'db_port', 'db_user', 'db_password')
              if opts.get(k) not in (None, '', 'False', 'false')}
    def connect():
        import psycopg2
        connection = psycopg2.connect(dbname=database, connect_timeout=1,
            options='-c statement_timeout=1000 -c default_transaction_read_only=on', **params)
        connection.set_session(readonly=True, autocommit=True)
        return connection
    return connect


def database_sample(connection, pid):
    with connection.cursor() as cursor:
        cursor.execute('SELECT state,wait_event_type,wait_event,extract(epoch FROM clock_timestamp()-query_start),'
                       'pg_blocking_pids(pid) FROM pg_stat_activity WHERE pid=%s', [pid])
        row = cursor.fetchone()
        if not row:
            return {'state': 'backend unavailable'}
        state, wait_type, wait_event, seconds, blockers = row
        result = dict(state=state, wait_type=wait_type, wait_event=wait_event,
                      query_seconds=float(seconds) if seconds is not None else None, blockers=blockers)
        cursor.execute("SELECT to_regclass('pg_catalog.pg_stat_progress_copy') IS NOT NULL")
        if cursor.fetchone()[0]:
            cursor.execute('SELECT tuples_processed,bytes_processed FROM pg_stat_progress_copy WHERE pid=%s', [pid])
            row = cursor.fetchone()
            if row:
                result.update(copy_rows=row[0], copy_bytes=row[1])
        return result
