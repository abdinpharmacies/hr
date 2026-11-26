import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
import time
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'crm_messaging_gateway'))

from app.config import Account, Settings
from app.storage import Store
from app.worker import Worker
from queue_timing import percentiles


def measure(delay_ms):
    samples = []
    raw = (b'# Synthetic attachment\n' * 5000)[:100 * 1024]
    for repeat in range(3):
        with tempfile.TemporaryDirectory(prefix='chatter-payload-') as directory:
            store = Store('sqlite://' + str(Path(directory) / 'queue.db'))
            store.migrate()
            config = Settings(database_url='sqlite://' + str(Path(directory) / 'queue.db'),
                encrypted_storage_confirmed=True, odoo_url='https://mock.invalid', odoo_database='synthetic',
                odoo_key='synthetic', accounts={'mock': Account(provider='telegram', provider_account='123',
                    token='123:synthetic', webhook_secret='synthetic-test-secret', enabled=True)})
            counters = Counter()
            class OdooMock:
                def call(self, method, account, **values):
                    counters[method] += 1
                    return {'media_required': True}
            def respond(request):
                began = time.perf_counter()
                time.sleep(delay_ms / 1000)
                counters['provider_requests'] += 1
                counters['provider_seconds'] += time.perf_counter() - began
                if request.url.path.endswith('/getFile'):
                    return httpx.Response(200, json={'ok': True, 'result': {'file_path': 'documents/timing.md'}})
                counters['download_bytes'] += len(raw)
                return httpx.Response(200, content=raw)
            with httpx.Client(transport=httpx.MockTransport(respond)) as client:
                worker = Worker(config, store, OdooMock(), client)
                for kind in ('text', 'media', 'receipt'):
                    for index in range(30):
                        correlation = str(uuid4())
                        payload = {'id': correlation, 'sender': '12345', 'body': 'Synthetic timing',
                            'timestamp': '2026-01-01 12:00:00', 'unsupported': False, 'source_digest': 'b' * 64}
                        if kind == 'media':
                            payload['media'] = {'kind': 'document', 'file_id': 'synthetic',
                                'name': 'timing.md', 'mimetype': 'text/markdown', 'size': len(raw)}
                        elif kind == 'receipt':
                            payload = {'reference': '123', 'status': 'read'}
                        before = counters.copy()
                        began = time.perf_counter()
                        store.ingest('mock', [(correlation, 'status' if kind == 'receipt' else 'incoming', payload)])
                        durable = time.perf_counter()
                        worker.ingest()
                        finished = time.perf_counter()
                        with store.connect() as connection:
                            state = connection.execute('SELECT state FROM incoming_event WHERE event_key=?', (correlation,)).fetchone()['state']
                        if state != 'done':
                            raise RuntimeError('Synthetic payload did not complete')
                        samples.append({'correlation_id': correlation, 'kind': kind, 'repeat': repeat,
                            'reception_to_durable_ms': (durable - began) * 1000,
                            'worker_ms': (finished - durable) * 1000,
                            'mock_provider_ms': (counters['provider_seconds'] - before['provider_seconds']) * 1000,
                            'provider_requests': counters['provider_requests'] - before['provider_requests'],
                            'download_bytes': counters['download_bytes'] - before['download_bytes']})
    return {'injected_provider_delay_ms': delay_ms, 'samples': samples,
        'worker_ms': {kind: percentiles([row['worker_ms'] for row in samples if row['kind'] == kind])
            for kind in ('text', 'media', 'receipt')},
        'limits': 'Real durable SQLite and Worker ingest. Provider HTTP uses MockTransport; Odoo and browser are mocked/absent.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--provider-delay-ms', type=int, choices=[0, 50], default=0)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(measure(args.provider_delay_ms), indent=2) + '\n')


if __name__ == '__main__':
    main()
