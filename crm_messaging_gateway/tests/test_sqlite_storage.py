import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.storage import Conflict, Store


@pytest.fixture
def store(tmp_path):
    instance = Store('sqlite://' + str(tmp_path / 'queue.db'))
    instance.migrate()
    return instance


def event():
    return [('event1', 'incoming', {'body': 'Hi'})]


def payload():
    return {
        'token': 'token',
        'attempt': 1,
        'body': 'Reply',
        'lease': 'lease',
        'destination': '123',
    }


def test_atomic_deduplication(store):
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda unused: store.ingest('tg', event()), range(8)))
    row = store.claim_incoming()
    assert row and store.claim_incoming() is None
    with pytest.raises(Conflict):
        store.ingest('tg', [('event1', 'incoming', {'body': 'different'})])
    store.ingest('other-account', event())
    assert store.claim_incoming()['account'] == 'other-account'


def test_concurrent_workers_lease_once(store):
    row = store.persist_outgoing('tg', payload())
    store.mark_ready(row)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda unused: store.claim_outgoing(['tg']), range(4)))
    assert sum(result is not None for result in results) == 1


def test_odoo_outage_preserves_queue_and_fences_stale_claims(store):
    store.ingest(
        'tg',
        [
            ('first', 'incoming', {'sender': '1'}),
            ('second', 'incoming', {'sender': '1'}),
        ],
    )
    first = store.claim_incoming()
    store.defer_incoming(first)
    assert store.claim_incoming() is None
    with store.connect() as conn:
        conn.execute(
            "UPDATE incoming_event SET available_at=now() WHERE id=?", (first['id'],)
        )
    second = store.claim_incoming()
    assert first['id'] == second['id'] and first['attempts'] == second['attempts']
    assert first['lease_until'] != second['lease_until']
    store.finish_incoming(first, True)
    store.defer_incoming(first)
    with store.connect() as conn:
        assert (
            conn.execute(
                'SELECT state FROM incoming_event WHERE id=?', (second['id'],)
            ).fetchone()['state']
            == 'processing'
        )
    store.defer_incoming(second)
    for unused in range(9):
        with store.connect() as conn:
            conn.execute(
                "UPDATE incoming_event SET available_at=now() WHERE id=?",
                (first['id'],),
            )
        current = store.claim_incoming()
        assert current['id'] == first['id'] and current['attempts'] == 1
        store.defer_incoming(current)
    with store.connect() as conn:
        row = conn.execute(
            'SELECT state,attempts FROM incoming_event WHERE id=?', (first['id'],)
        ).fetchone()
        assert row == {'state': 'pending', 'attempts': 0}


def test_outgoing_snapshot_and_receipt_stability(store):
    row = store.persist_outgoing('tg', payload())
    assert (
        store.persist_outgoing('tg', dict(payload(), lease='renewed'))['receipt']
        == row['receipt']
    )
    with pytest.raises(Conflict):
        store.persist_outgoing('tg', dict(payload(), body='Changed'))


def test_crash_after_send_is_review_never_retried(store):
    row = store.persist_outgoing('tg', payload())
    store.mark_ready(row)
    store.claim_outgoing(['tg'])
    with store.connect() as conn:
        conn.execute("UPDATE outgoing_operation SET lease_until=now()-1")
    store.recover_sending()
    assert store.claim_outgoing(['tg']) is None
    assert store.reports()[0]['outcome']['status'] == 'review'


def test_incoming_crash_recovery_and_bounded_review(store):
    store.ingest('tg', event())
    first = store.claim_incoming()
    with store.connect() as conn:
        conn.execute("UPDATE incoming_event SET lease_until=now()-1")
    second = store.claim_incoming()
    assert first['id'] == second['id'] and second['attempts'] == 2
    store.finish_incoming(first, True)
    with store.connect() as conn:
        assert (
            conn.execute('SELECT state FROM incoming_event').fetchone()['state']
            == 'processing'
        )
        conn.execute('UPDATE incoming_event SET attempts=8')
    second['attempts'] = 8
    store.finish_incoming(second, False)
    with store.connect() as conn:
        assert (
            conn.execute('SELECT state FROM incoming_event').fetchone()['state']
            == 'review'
        )


def test_retryable_send_is_bounded(store):
    store.mark_ready(store.persist_outgoing('tg', payload()))
    for attempt in range(5):
        row = store.claim_outgoing(['tg'])
        assert row['sends'] == attempt + 1
        store.outcome(
            row,
            {
                'status': 'failed',
                'reference': '',
                'error': 'rate_limit',
                'retry_after': 0,
            },
        )
    assert store.claim_outgoing(['tg']) is None
    assert store.reports()[0]['outcome']['error'] == 'rate_limit'


def test_ambiguous_never_auto_retries(store):
    store.mark_ready(store.persist_outgoing('tg', payload()))
    row = store.claim_outgoing(['tg'])
    store.outcome(row, {'status': 'review', 'reference': '', 'error': 'ambiguous'})
    assert store.claim_outgoing(['tg']) is None
    assert store.reports()[0]['outcome']['status'] == 'review'


def test_poll_offset_atomicity_and_receiver_exclusion(store):
    with store.receiver('123') as conn:
        assert store.polling_offset(conn, '123') == 0
        with pytest.raises(Conflict):
            with store.receiver('123'):
                pass
        store.persist_poll(conn, 'tg', '123', event(), 2)
        assert store.polling_offset(conn, '123') == 2
        with pytest.raises(Conflict):
            store.persist_poll(
                conn, 'tg', '123', [('event1', 'incoming', {'body': 'conflict'})], 3
            )
        assert store.polling_offset(conn, '123') == 2
    with store.receiver('123') as conn:
        assert store.polling_offset(conn, '123') == 2


def test_incoming_order_blocks_delayed_and_reviewed_conversation_only(store):
    store.ingest(
        'tg',
        [
            ('first', 'incoming', {'sender': '1'}),
            ('second', 'incoming', {'sender': '1'}),
            ('other', 'incoming', {'sender': '2'}),
        ],
    )
    first = store.claim_incoming()
    assert first['event_key'] == 'first'
    assert store.claim_incoming()['event_key'] == 'other'
    store.finish_incoming(first, False)
    assert store.claim_incoming() is None
    with store.connect() as conn:
        conn.execute("UPDATE incoming_event SET state='review' WHERE event_key='first'")
    assert store.claim_incoming() is None
    with store.connect() as conn:
        conn.execute("UPDATE incoming_event SET state='done' WHERE event_key='first'")
    assert store.claim_incoming()['event_key'] == 'second'


def test_uncertain_send_blocks_later_same_destination(store):
    first = store.persist_outgoing('tg', payload())
    second = store.persist_outgoing('tg', dict(payload(), token='second'))
    other = store.persist_outgoing(
        'tg', dict(payload(), token='other', destination='456')
    )
    for row in [first, second, other]:
        store.mark_ready(row)
    row = store.claim_outgoing(['tg'])
    store.outcome(row, {'status': 'review', 'reference': '', 'error': 'ambiguous'})
    store.reported(store.reports()[0])
    assert store.claim_outgoing(['tg'])['token'] == 'other'
    assert store.claim_outgoing(['tg']) is None


def ingest_process(url, number):
    instance = Store(url)
    instance.ingest('tg', [('shared', 'incoming', {'sender': 'same'})])
    instance.ingest('tg', [(str(number), 'incoming', {'sender': str(number)})])
    instance.mark_ready(
        instance.persist_outgoing(
            'tg', dict(payload(), token=str(number), destination=str(number))
        )
    )
    return instance.claim_outgoing(['tg'])['id']


def test_real_process_contention(store):
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(ingest_process, [store.database_url] * 40, range(40)))
    assert len(set(ids)) == 40
    with store.connect() as conn:
        assert (
            conn.execute('SELECT count(*) AS count FROM incoming_event').fetchone()[
                'count'
            ]
            == 41
        )
        assert conn.execute('PRAGMA integrity_check').fetchone() == {
            'integrity_check': 'ok'
        }


def test_export_import_and_backup_restore(store, tmp_path):
    from app.queue_transfer import (
        export_queue,
        import_queue,
        backup_queue,
        snapshot,
        digest_records,
    )

    store.ingest('tg', event())
    with store.receiver('123') as conn:
        store.persist_poll(conn, 'tg', '123', event(), 20)
    store.mark_ready(store.persist_outgoing('tg', payload()))
    store.claim_outgoing(['tg'])
    export = tmp_path / 'export.jsonl'
    expected = export_queue(store, export, quiesced=True)
    destination = Store('sqlite://' + str(tmp_path / 'import.db'))
    assert import_queue(destination, export) == expected
    with destination.connect() as conn:
        conn.execute('UPDATE outgoing_operation SET lease_until=now()-1')
    destination.recover_sending()
    assert destination.reports()[0]['outcome']['status'] == 'review'
    backup = tmp_path / 'backup.db'
    backup_queue(destination, backup)
    restored = Store('sqlite://' + str(backup))
    with restored.connect() as conn, destination.connect() as original:
        assert digest_records(snapshot(conn)) == digest_records(snapshot(original))
    assert restored.claim_outgoing(['tg']) is None


def test_corrupt_import_rolls_back(store, tmp_path):
    from app.queue_transfer import export_queue, import_queue

    store.ingest('tg', event())
    path = tmp_path / 'export.jsonl'
    export_queue(store, path, quiesced=True)
    path.write_text(path.read_text().replace('Hi', 'Corrupted'))
    target = Store('sqlite://' + str(tmp_path / 'import.db'))
    with pytest.raises(ValueError, match='digests'):
        import_queue(target, path)
    with target.connect() as conn:
        assert (
            conn.execute('SELECT count(*) AS count FROM incoming_event').fetchone()[
                'count'
            ]
            == 0
        )


def test_busy_is_bounded(store):
    import apsw
    import time

    contender = Store(store.database_url + '?busy_timeout_ms=10&contention_retries=2')
    with store.connect():
        started = time.monotonic()
        with pytest.raises(apsw.BusyError):
            contender.ingest('tg', event())
        assert time.monotonic() - started < 1
    contender.ingest('tg', event())


def test_disk_full_rolls_back_poll_and_offset(store):
    import apsw

    with store.receiver('123') as conn:
        count = conn.execute('PRAGMA page_count').fetchone()['page_count']
        conn.execute(f'PRAGMA max_page_count={count}')
        with pytest.raises(apsw.FullError):
            store.persist_poll(
                conn, 'tg', '123', [('large', 'incoming', {'body': 'x' * 100000})], 100
            )
        assert store.polling_offset(conn, '123') == 0
        assert (
            conn.execute('SELECT count(*) AS count FROM incoming_event').fetchone()[
                'count'
            ]
            == 0
        )


def hold_receiver(url, ready):
    import time

    with Store(url).receiver('123') as conn:
        Store(url).persist_poll(conn, 'tg', '123', event(), 30)
        ready.set()
        time.sleep(30)


def test_receiver_process_crash_releases_lock_preserves_offset(store):
    import multiprocessing

    context = multiprocessing.get_context('spawn')
    ready = context.Event()
    process = context.Process(target=hold_receiver, args=(store.database_url, ready))
    process.start()
    try:
        assert ready.wait(10)
        with pytest.raises(Conflict):
            with store.receiver('123'):
                pass
    finally:
        process.terminate()
        process.join(10)
    assert not process.is_alive()
    with store.receiver('123') as conn:
        assert store.polling_offset(conn, '123') == 30
    assert store.claim_incoming()['event_key'] == 'event1'


def test_runtime_and_durability_guards(store, monkeypatch):
    with store.connect() as conn:
        assert conn.execute('PRAGMA journal_mode').fetchone()['journal_mode'] == 'wal'
        assert conn.execute('PRAGMA synchronous').fetchone()['synchronous'] == 2
        assert conn.execute('PRAGMA foreign_keys').fetchone()['foreign_keys'] == 1
    monkeypatch.setattr('app.sqlite_storage.apsw.sqlitelibversion', lambda: '3.45.1')
    with pytest.raises(RuntimeError, match='3.51.3'):
        Store(store.database_url)


def test_location_payload_is_frozen_across_duplicate_receipts_and_retries(tmp_path):
    store = Store('sqlite://' + str(tmp_path / 'venue.db'))
    store.migrate()
    venue = dict(payload(), location={'latitude': 0, 'longitude': 180, 'name': 'Branch', 'address': 'Street'})
    first = store.persist_outgoing('tg', venue)
    assert store.persist_outgoing('tg', dict(venue, lease='renewed'))['receipt'] == first['receipt']
    with pytest.raises(Conflict):
        store.persist_outgoing('tg', dict(venue, location=dict(venue['location'], address='Changed')))
    retry = store.persist_outgoing('tg', dict(venue, attempt=2, lease='retry'))
    assert retry['payload']['location'] == venue['location']
