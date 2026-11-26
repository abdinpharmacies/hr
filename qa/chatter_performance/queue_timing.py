import argparse
from collections import Counter
import json
from pathlib import Path
import resource
import sys
import tempfile
import threading
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'crm_messaging_gateway'))

from app.config import Account, Settings
from app.storage import Store
from app.worker import Worker


def percentiles(values):
    ordered = sorted(values)
    return {f'p{p}': ordered[min(len(ordered) - 1, max(0, (len(ordered) * p + 99) // 100 - 1))]
            for p in (50, 95, 99)} if ordered else {}


def run(seconds, interval):
    with tempfile.TemporaryDirectory(prefix='chatter-queue-') as directory:
        store = Store('sqlite://' + str(Path(directory) / 'queue.db'))
        store.migrate()
        counters = Counter()
        connect = store.connect
        def counted_connect(*args, **kwargs):
            counters['connections'] += 1
            connection = connect(*args, **kwargs)
            execute = connection.execute
            def counted_execute(*args, **kwargs):
                counters['application_sql_statements'] += 1
                return execute(*args, **kwargs)
            connection.execute = counted_execute
            return connection
        store.connect = counted_connect
        config = Settings(database_url='sqlite://' + str(Path(directory) / 'queue.db'),
            encrypted_storage_confirmed=True, odoo_url='https://mock.invalid', odoo_database='synthetic',
            odoo_key='synthetic', accounts={'mock': Account(provider='telegram', provider_account='123',
                token='123:synthetic', webhook_secret='synthetic-test-secret', enabled=True)})
        received, durable, claimed, committed = {}, {}, {}, {}
        samples, failures = [], []
        operations = Counter()
        class OdooMock:
            def call(self, method, account, **values):
                operations[method] += 1
                if method == 'receive_event':
                    correlation = values['event']['id']
                    claimed[correlation] = time.perf_counter()
                    committed[correlation] = time.perf_counter()
                return {'media_required': False}
        worker = Worker(config, store, OdooMock(), None)
        stop = threading.Event()
        def consume():
            try:
                while not stop.is_set():
                    if not worker.tick():
                        stop.wait(interval)
            except BaseException as error:
                failures.append(type(error).__name__)
        cpu = time.process_time()
        began = time.perf_counter()
        consumer = threading.Thread(target=consume)
        consumer.start()
        next_due = began
        backlog = []
        try:
            while time.perf_counter() - began < seconds:
                elapsed = time.perf_counter() - began
                rate = 20 if seconds >= 60 and 30 <= elapsed < 40 else 5
                time.sleep(max(0, next_due - time.perf_counter()))
                correlation = str(uuid4())
                received[correlation] = time.perf_counter()
                store.ingest('mock', [(correlation, 'incoming', {'id': correlation})])
                durable[correlation] = time.perf_counter()
                next_due += 1 / rate
                backlog.append({'elapsed_seconds': elapsed, 'pending': len(received) - len(committed)})
            deadline = time.perf_counter() + 30
            while len(committed) < len(received) and time.perf_counter() < deadline and not failures:
                stop.wait(0.02)
        finally:
            stop.set()
            consumer.join(timeout=5)
        if consumer.is_alive() or failures or len(committed) != len(received):
            raise RuntimeError('Worker did not drain the synthetic durable queue')
        for correlation in received:
            samples.append({'correlation_id': correlation,
                'reception_to_durable_ms': (durable[correlation] - received[correlation]) * 1000,
                'durable_to_mock_commit_ms': (committed[correlation] - durable[correlation]) * 1000,
                'worker_claim_to_mock_commit_ms': (committed[correlation] - claimed[correlation]) * 1000})
        burst = [correlation for correlation, at in received.items() if 30 <= at - began < 40]
        burst_drain = max(0, max((committed[correlation] for correlation in burst), default=began + 40) - began - 40)
        return {'interval_seconds': interval, 'duration_seconds': time.perf_counter() - began,
            'cpu_seconds': time.process_time() - cpu, 'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'database': dict(counters), 'burst_drain_seconds': burst_drain if burst else None,
            'overlapping_claims': sum(sample['durable_to_mock_commit_ms'] < 0 for sample in samples),
            'messages': len(received), 'remaining': len(received) - len(committed), 'operations': dict(operations),
            'queue_wait_ms': percentiles([max(0, item['durable_to_mock_commit_ms']) for item in samples]),
            'backlog': backlog, 'samples': samples,
            'limits': 'Real durable SQLite and bounded Worker; Odoo commit mocked. No provider, HTTP, bus or browser timing. Durable boundary is ingest return; overlapping claims count as zero wait. SQL counts exclude connection setup PRAGMAs.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=300)
    parser.add_argument('--interval', type=float, choices=[0.1, 0.25, 0.5, 1, 2], required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 5 <= args.seconds <= 300:
        parser.error('Use 5 to 300 seconds')
    args.output.write_text(json.dumps(run(args.seconds, args.interval), indent=2) + '\n')


if __name__ == '__main__':
    main()
