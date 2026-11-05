import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.storage import Conflict, Store


@pytest.fixture
def store():
    path = os.environ.get('MESSAGING_TEST_DSN_FILE')
    if not path:
        pytest.skip(
            'Set MESSAGING_TEST_DSN_FILE to an isolated PostgreSQL test database DSN file'
        )
    dsn = Path(path).read_text()
    instance = Store(dsn)
    with instance.connect() as conn:
        database = conn.execute('SELECT current_database() AS name').fetchone()['name']
        if 'test' not in database:
            raise RuntimeError('Only a dedicated test database may be reset')
    instance.migrate()
    with instance.connect() as conn:
        conn.execute(
            'TRUNCATE telegram_polling, operator_audit, incoming_event, outgoing_operation RESTART IDENTITY'
        )
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
    store.ingest('tg', [('first', 'incoming', {'sender': '1'}), ('second', 'incoming', {'sender': '1'})])
    first = store.claim_incoming()
    store.defer_incoming(first)
    assert store.claim_incoming() is None
    with store.connect() as conn:
        conn.execute("UPDATE incoming_event SET available_at=now() WHERE id=%s", (first['id'],))
    second = store.claim_incoming()
    assert first['id'] == second['id'] and first['attempts'] == second['attempts']
    assert first['lease_until'] != second['lease_until']
    store.finish_incoming(first, True)
    store.defer_incoming(first)
    with store.connect() as conn:
        assert conn.execute('SELECT state FROM incoming_event WHERE id=%s', (second['id'],)).fetchone()['state'] == 'processing'
    store.defer_incoming(second)
    for unused in range(9):
        with store.connect() as conn:
            conn.execute("UPDATE incoming_event SET available_at=now() WHERE id=%s", (first['id'],))
        current = store.claim_incoming()
        assert current['id'] == first['id'] and current['attempts'] == 1
        store.defer_incoming(current)
    with store.connect() as conn:
        row = conn.execute('SELECT state,attempts FROM incoming_event WHERE id=%s', (first['id'],)).fetchone()
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
        conn.execute(
            "UPDATE outgoing_operation SET lease_until=now()-interval '1 second'"
        )
    store.recover_sending()
    assert store.claim_outgoing(['tg']) is None
    assert store.reports()[0]['outcome']['status'] == 'review'


def test_incoming_crash_recovery_and_bounded_review(store):
    store.ingest('tg', event())
    first = store.claim_incoming()
    with store.connect() as conn:
        conn.execute("UPDATE incoming_event SET lease_until=now()-interval '1 second'")
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
            store.persist_poll(conn, 'tg', '123', [('event1', 'incoming', {'body': 'conflict'})], 3)
        assert store.polling_offset(conn, '123') == 2
    with store.receiver('123') as conn:
        assert store.polling_offset(conn, '123') == 2


def test_incoming_order_blocks_delayed_and_reviewed_conversation_only(store):
    store.ingest('tg', [('first', 'incoming', {'sender': '1'}), ('second', 'incoming', {'sender': '1'}), ('other', 'incoming', {'sender': '2'})])
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
    other = store.persist_outgoing('tg', dict(payload(), token='other', destination='456'))
    for row in [first, second, other]:
        store.mark_ready(row)
    row = store.claim_outgoing(['tg'])
    store.outcome(row, {'status': 'review', 'reference': '', 'error': 'ambiguous'})
    store.reported(store.reports()[0])
    assert store.claim_outgoing(['tg'])['token'] == 'other'
    assert store.claim_outgoing(['tg']) is None
