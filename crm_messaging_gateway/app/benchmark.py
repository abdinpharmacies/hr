import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from pathlib import Path
import statistics
import time
from uuid import uuid4

from .storage import Store


def cycle(args):
    url, number = args
    started = time.perf_counter()
    store = Store(url)
    key = str(number)
    store.ingest(
        'benchmark', [(key, 'incoming', {'sender': key, 'body': 'Synthetic benchmark'})]
    )
    row = store.claim_incoming()
    if row:
        store.finish_incoming(row, True)
    row = store.persist_outgoing(
        'benchmark',
        {'token': key, 'attempt': 1, 'destination': key, 'body': 'Synthetic benchmark'},
    )
    store.mark_ready(row)
    row = store.claim_outgoing(['benchmark'])
    if row:
        store.outcome(row, {'status': 'accepted', 'reference': key, 'error': 'none'})
        store.reported(row)
    return time.perf_counter() - started


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--peak-events-per-second', required=True, type=float)
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--processes', type=int, default=4)
    args = parser.parse_args()
    if (
        not 0 < args.peak_events_per_second <= 1000
        or not 1 <= args.seconds <= 600
        or not 2 <= args.processes <= 16
    ):
        parser.error('Use bounded positive peak, duration and process counts')
    count = int(args.peak_events_per_second * 2 * args.seconds)
    if not 1 <= count <= 100000:
        parser.error('The bounded benchmark supports 1 to 100000 cycles')
    directory = Path(args.directory) / ('benchmark-' + str(uuid4()))
    directory.mkdir(mode=0o700, parents=True)
    url = 'sqlite://' + str(directory.resolve() / 'queue.db')
    Store(url).migrate()
    started = time.perf_counter()
    with Store(url).connect(transaction=False), ProcessPoolExecutor(
        max_workers=args.processes
    ) as pool:
        futures = []
        for number in range(count):
            due = started + number / (args.peak_events_per_second * 2)
            time.sleep(max(0, due - time.perf_counter()))
            futures.append(pool.submit(cycle, (url, number)))
        durations = [future.result() for future in futures]
    elapsed = time.perf_counter() - started
    with Store(url).connect() as conn:
        for table in ('incoming_event', 'outgoing_operation'):
            if conn.execute(
                f"SELECT count(*) AS count FROM {table} WHERE state != 'done'"
            ).fetchone()['count']:
                raise RuntimeError('Synthetic benchmark left unfinished operations')
    report = {
        'sqlite_queue': str(directory),
        'reference_peak': args.peak_events_per_second,
        'target_cycles_per_second': args.peak_events_per_second * 2,
        'cycles': count,
        'elapsed_seconds': elapsed,
        'cycles_per_second': count / elapsed,
        'p95_cycle_seconds': sorted(durations)[int(len(durations) * 0.95)],
        'mean_cycle_seconds': statistics.mean(durations),
        'production_capacity_approved': False,
    }
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
