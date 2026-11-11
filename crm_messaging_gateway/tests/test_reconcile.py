from unittest.mock import Mock

import pytest

from app.reconcile import apply, preview
from app.storage import Store
from test_storage import store as postgres_store


@pytest.fixture(params=['sqlite', 'postgres'])
def queue(request, tmp_path):
    if request.param == 'postgres':
        return request.getfixturevalue('postgres_store')
    store = Store('sqlite://' + str(tmp_path / 'queue.db'))
    store.migrate()
    return store


def seed(queue):
    queue.ingest('wa', [(str(i), 'status', {'reference': 'ref', 'destination': 'private', 'status': status}) for i, status in enumerate(('delivered', 'read'))])
    row = queue.claim_incoming()
    with queue.connect() as conn:
        conn.execute("UPDATE incoming_event SET state='review',lease_until=NULL")
        rows = conn.execute('SELECT * FROM incoming_event ORDER BY id').fetchall()
    return rows


def test_preview_retry_preserves_payload_and_order_and_never_sends(queue):
    rows = seed(queue)
    ids = [row['id'] for row in rows]
    odoo = Mock()
    odoo.call.return_value = {'match': 'historical'}
    report = preview(queue, odoo, 'wa', ids)
    assert 'private' not in str(report)
    result = apply(queue, odoo, 'wa', ids, report['digest'], 'retry', 'Verified history')
    assert result['event_ids'] == ids
    first = queue.claim_incoming()
    assert first['id'] == ids[0]
    assert queue.claim_incoming() is None
    queue.finish_incoming(first, True)
    assert queue.claim_incoming()['id'] == ids[1]
    with queue.connect() as conn:
        after = conn.execute('SELECT * FROM incoming_event ORDER BY id').fetchall()
        assert [(r['fingerprint'],r['payload']) for r in rows] == [(r['fingerprint'],r['payload']) for r in after]
        assert conn.execute('SELECT count(*) AS n FROM operator_audit').fetchone()['n'] == 2
        assert conn.execute('SELECT count(*) AS n FROM outgoing_operation').fetchone()['n'] == 0
    assert {call.args[0] for call in odoo.call.call_args_list} == {'preview_status'}


def test_ignore_orphan_releases_following_receipt_and_audits(queue):
    rows = seed(queue)
    odoo = Mock()
    odoo.call.return_value = {'match': 'orphan'}
    ids = [rows[0]['id']]
    report = preview(queue, odoo, 'wa', ids)
    with pytest.raises(ValueError):
        apply(queue, odoo, 'wa', ids, report['digest'], 'ignore', ' ')
    apply(queue, odoo, 'wa', ids, report['digest'], 'ignore', 'Confirmed missing historical message')
    with queue.connect() as conn:
        result = conn.execute('SELECT * FROM incoming_event ORDER BY id').fetchall()
        assert result[0]['state'] == 'ignored'
        assert result[1]['state'] == 'review'
        assert result[0]['payload'] == rows[0]['payload']
        assert result[0]['fingerprint'] == rows[0]['fingerprint']
        assert conn.execute('SELECT note FROM operator_audit').fetchone()['note']


@pytest.mark.parametrize('match,action', [('ambiguous','ignore'),('unverified','retry'),('historical','ignore'),('orphan','retry')])
def test_invalid_dispositions_are_atomic(queue, match, action):
    rows = seed(queue)
    ids = [r['id'] for r in rows]
    odoo = Mock()
    odoo.call.return_value = {'match':match}
    report = preview(queue, odoo, 'wa', ids)
    with pytest.raises(ValueError):
        apply(queue, odoo, 'wa', ids, report['digest'], action, 'Reviewed')
    with pytest.raises(ValueError):
        preview(queue, odoo, 'another-account', ids)
    with queue.connect() as conn:
        assert conn.execute('SELECT count(*) AS n FROM operator_audit').fetchone()['n'] == 0


def test_stale_preview_refused(queue):
    rows = seed(queue)
    ids = [r['id'] for r in rows]
    odoo = Mock()
    odoo.call.return_value = {'match':'historical'}
    report = preview(queue, odoo, 'wa', ids)
    with queue.connect() as conn:
        conn.execute("UPDATE incoming_event SET state='pending'")
    with pytest.raises(ValueError, match='Preview changed'):
        apply(queue, odoo, 'wa', ids, report['digest'], 'retry', 'Reviewed')
