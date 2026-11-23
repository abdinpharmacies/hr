from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from app.config import Account
from app.storage import Store
from app.website import WebsiteWorker, send_reply
from test_storage import store as postgres_store
from test_sqlite_storage import store as sqlite_store
from test_gateway import config


def website():
    return Account(
        provider='website',
        provider_account=str(uuid4()),
        token='source-test-key',
        odoo_key='target-test-key',
        website_url='https://shop.example',
        website_database='shop',
        reception='disabled',
        enabled=True,
        sending_enabled=True,
    )


@pytest.mark.parametrize('queue', ['sqlite_store', 'postgres_store'])
def test_account_scoped_claim_recovery_reporting(queue, request):
    store = request.getfixturevalue(queue)
    for code in ('web', 'tg', 'wa'):
        store.ingest(code, [('event', 'incoming', {'sender': 'same'})])
        store.persist_outgoing(
            code,
            {'token': 'token', 'attempt': 1, 'lease': 'lease', 'destination': 'order'},
        )
    assert store.claim_incoming([]) is None
    assert store.claim_incoming(['web'])['account'] == 'web'
    assert store.claim_incoming(['web']) is None
    assert store.claim_incoming(['wa'])['account'] == 'wa'
    assert [row['account'] for row in store.stored(['web'])] == ['web']
    assert store.stored([]) == []
    for row in store.stored():
        store.mark_ready(row)
    for code in ('web', 'tg', 'wa'):
        assert store.claim_outgoing([code])['account'] == code
    with store.connect() as conn:
        conn.execute(
            "UPDATE outgoing_operation SET lease_until="
            + (
                "now()-interval '1000 seconds'"
                if queue == "postgres_store"
                else "now()-1000"
            )
        )
    store.recover_sending(['web'])
    assert [row['account'] for row in store.reports(['web'])] == ['web']
    assert store.reports(['tg']) == [] and store.reports([]) == []
    store.recover_sending(['tg'])
    assert [row['account'] for row in store.reports(['tg'])] == ['tg']
    with store.connect() as conn:
        assert (
            conn.execute(
                "SELECT state FROM outgoing_operation WHERE account='wa'"
            ).fetchone()['state']
            == 'sending'
        )


def test_website_credentials_and_https():
    good = website().model_dump()
    for changes in (
        {'website_url': 'http://shop.example'},
        {'reception': 'polling'},
        {'odoo_key': None},
        {'token': None},
        {'provider_account': '123'},
    ):
        with pytest.raises(ValueError):
            Account(**dict(good, **changes))


def test_restart_after_commit_before_ack(tmp_path):
    cfg = config()
    account = website()
    cfg.accounts['web'] = account
    store = Store('sqlite://' + str(tmp_path / 'website.db'))
    store.migrate()
    event = {
        'source': account.provider_account,
        'event_uuid': str(uuid4()),
        'order_uuid': str(uuid4()),
        'fingerprint': 'f' * 64,
    }
    store.ingest(
        'web',
        [
            (
                event['event_uuid'],
                'incoming',
                {'website_event': event, 'sender': event['order_uuid']},
            )
        ],
    )
    store.ingest('tg', [('other', 'incoming', {'body': 'untouched'})])
    committed = set()

    def receive(method, code, **values):
        committed.add(values['event']['event_uuid'])
        return {'received': True, 'event_uuid': event['event_uuid']}

    odoo = Mock()
    odoo.call.side_effect = receive
    replies = [httpx.Response(503), httpx.Response(200, json=True)]
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: replies.pop(0))
    ) as client:
        WebsiteWorker(cfg, store, odoo, client, accounts=['web']).ingest()
        assert len(committed) == 1
        with store.connect() as conn:
            assert (
                conn.execute(
                    "SELECT state FROM incoming_event WHERE account='web'"
                ).fetchone()['state']
                == 'pending'
            )
            conn.execute(
                "UPDATE incoming_event SET available_at=now() WHERE account='web'"
            )
        WebsiteWorker(cfg, store, odoo, client, accounts=['web']).ingest()
    assert len(committed) == 1 and odoo.call.call_count == 2
    with store.connect() as conn:
        assert (
            conn.execute(
                "SELECT state FROM incoming_event WHERE account='web'"
            ).fetchone()['state']
            == 'done'
        )
        assert (
            conn.execute(
                "SELECT attempts FROM incoming_event WHERE account='tg'"
            ).fetchone()['attempts']
            == 0
        )


def test_reply_receipt_and_uncertain_delivery():
    account = website()
    operation = {'destination': str(uuid4()), 'token': str(uuid4()), 'body': 'reply',
                 'website_destination': {'kind': 'livechat', 'uuid': str(uuid4())}}

    def receive(req):
        assert req.headers['authorization'] == 'Bearer source-test-key'
        assert req.url.path == '/storefront-callcenter/v2/receive'
        import json
        values = json.loads(req.content)
        assert values['destination_kind'] == 'livechat'
        assert values['destination_uuid'] == operation['website_destination']['uuid']
        assert values['source'] == account.provider_account
        return httpx.Response(200, json={'reference': operation['token']})

    with httpx.Client(transport=httpx.MockTransport(receive)) as client:
        assert send_reply(client, account, operation)['status'] == 'accepted'
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(503))
    ) as client:
        assert send_reply(client, account, operation) == {
            'status': 'failed',
            'reference': '',
            'error': 'unavailable',
            'website_failure': 'transient',
        }


def test_credential_loading_is_account_scoped():
    from app.config import load_odoo_tokens

    cfg = config()
    cfg.accounts['tg'].token_source = 'odoo'
    cfg.accounts['tg'].token = None
    odoo = Mock()
    load_odoo_tokens(cfg, odoo, accounts=['wa'])
    odoo.call.assert_not_called()


def test_historical_reply_is_never_sent():
    account = website()
    operation = {'destination': str(uuid4()), 'token': str(uuid4()), 'body': 'reply'}
    with httpx.Client(transport=httpx.MockTransport(lambda req: pytest.fail('Historical send'))) as client:
        assert send_reply(client, account, operation)['status'] == 'review'


def test_both_sources_keep_overlapping_chat_ids_separate(tmp_path):
    cfg = config()
    cfg.accounts['local'], cfg.accounts['production'] = website(), website()
    store = Store('sqlite://' + str(tmp_path / 'both-sources.db'))
    store.migrate()
    message, session = str(uuid4()), str(uuid4())

    def response(req):
        import json
        values = json.loads(req.content)
        if '/v1/' in req.url.path:
            return httpx.Response(200, json=[])
        return httpx.Response(200, json=[{
            'version': 2, 'source': values['source'], 'event_uuid': message,
            'destination': {'kind': 'livechat', 'uuid': session}, 'body': 'Hello',
            'fingerprint': 'f' * 64,
        }])

    with httpx.Client(transport=httpx.MockTransport(response)) as client:
        worker = WebsiteWorker(cfg, store, Mock(), client, accounts=['local', 'production'])
        worker.fetch('local')
        worker.fetch('production')
    local, production = store.claim_incoming(['local']), store.claim_incoming(['production'])
    assert local['payload']['website_event']['source'] == cfg.accounts['local'].provider_account
    assert production['payload']['website_event']['source'] == cfg.accounts['production'].provider_account
    assert local['payload']['sender'] == production['payload']['sender'] == session


def test_v1_order_intake_survives_source_without_chat_v2(tmp_path):
    cfg = config()
    cfg.accounts['web'] = website()
    store = Store('sqlite://' + str(tmp_path / 'v1-source.db'))
    store.migrate()
    event = {'source': cfg.accounts['web'].provider_account, 'event_uuid': str(uuid4()), 'order_uuid': str(uuid4())}
    store.ingest('web', [(event['event_uuid'], 'incoming',
                          {'website_event': event, 'sender': event['order_uuid']})])
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(
            200, json=[event]) if '/v1/' in req.url.path else httpx.Response(404))) as client:
        worker = WebsiteWorker(cfg, store, Mock(), client, accounts=['web'])
        worker.fetch('web')
        assert ('web', 2) in worker.chat_unavailable
        worker.fetch('web')
    assert store.claim_incoming(['web'])['payload']['website_event'] == event


@pytest.mark.parametrize('queue', ['sqlite_store', 'postgres_store'])
def test_website_eight_attempts_and_expired_lease_recovery(queue, request):
    store = request.getfixturevalue(queue)
    operation = {'token': 'stable', 'attempt': 1, 'lease': 'lease', 'destination': 'customer',
                 'provider': 'website', 'body': 'Frozen reply',
                 'website_destination': {'kind': 'livechat', 'uuid': str(uuid4())}}
    stored = store.persist_outgoing('web', operation)
    store.mark_ready(stored)
    for attempt in range(1, 9):
        row = store.claim_outgoing(['web'])
        assert row['sends'] == attempt
        assert row['payload']['body'] == 'Frozen reply'
        assert row['token'] == 'stable'
        if attempt == 2:
            with store.connect() as conn:
                conn.execute("UPDATE outgoing_operation SET lease_until=" +
                    ("now()-interval '1000 seconds'" if queue == 'postgres_store' else 'now()-1000'))
            store.recover_website_sending(['web'])
        else:
            store.outcome(row, {'status': 'failed', 'reference': '', 'error': 'unavailable'})
        with store.connect() as conn:
            current = conn.execute('SELECT * FROM outgoing_operation').fetchone()
            assert current['state'] == ('ready' if attempt < 8 else 'report')
            if attempt < 8:
                conn.execute('UPDATE outgoing_operation SET available_at=now()')
    report = store.reports(['web'])[0]
    assert report['outcome']['status'] == 'review'
    store.reported(report)
    operation['attempt'] = 2
    store.mark_ready(store.persist_outgoing('web', operation))
    retry = store.claim_outgoing(['web'])
    assert retry['token'] == 'stable' and retry['attempt'] == 2
    assert retry['payload']['website_destination'] == operation['website_destination']


@pytest.mark.parametrize('status,category', [(401, 'authentication'), (403, 'authentication'),
    (400, 'validation'), (410, 'ended'), (404, 'transient'), (409, 'transient'),
    (429, 'transient'), (503, 'transient')])
def test_website_error_classification(status, category):
    operation = {'token': 'stable', 'body': 'Reply',
                 'website_destination': {'kind': 'order', 'uuid': str(uuid4())}}
    with httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(status))) as client:
        result = send_reply(client, website(), operation)
    assert result['website_failure'] == category
    assert result['status'] == ('failed' if category == 'transient' else 'review')


def test_independent_fetch_and_capability_reprobe(tmp_path, monkeypatch):
    cfg = config()
    cfg.accounts['web'] = website()
    store = Store('sqlite://' + str(tmp_path / 'reprobe.db'))
    store.migrate()
    calls = []
    clock = [0]
    monkeypatch.setattr('app.website.time.monotonic', lambda: clock[0])
    def respond(req):
        calls.append(req.url.path)
        return httpx.Response(503) if '/v1/' in req.url.path else httpx.Response(404 if clock[0] < 60 else 200, json=[])
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        worker = WebsiteWorker(cfg, store, Mock(), client, accounts=['web'])
        worker.fetch('web')
        worker.fetch('web')
        assert len([path for path in calls if '/v2/' in path]) == 1
        clock[0] = 61
        worker.fetch('web')
        assert len([path for path in calls if '/v2/' in path]) == 2
        assert not worker.chat_unavailable


@pytest.mark.parametrize('queue', ['sqlite_store', 'postgres_store'])
def test_destination_ordering_and_other_customer_progress(queue, request):
    store = request.getfixturevalue(queue)
    for token, customer, destination in [('first', 'one', 'target-one'), ('second', 'one', 'target-one'), ('other', 'two', 'target-two')]:
        row = store.persist_outgoing('web', {'token': token, 'attempt': 1, 'lease': 'lease',
            'provider': 'website', 'destination': customer, 'website_destination': destination})
        store.mark_ready(row)
    first = store.claim_outgoing(['web'])
    store.outcome(first, {'status': 'review', 'reference': '', 'error': 'rejected'})
    other = store.claim_outgoing(['web'])
    assert other['token'] == 'other'
    assert store.claim_outgoing(['web']) is None


def test_website_queue_age_and_review_blockage():
    from app.health import website_queue_health
    rows = [dict(account='web', destination='first', state='done', outcome_status='review', created_at=10, sends=8),
            dict(account='web', destination='first', state='ready', outcome_status='failed', created_at=30, sends=1),
            dict(account='web', destination='other', state='ready', outcome_status=None, created_at=40, sends=0)]
    assert website_queue_health(rows, now=100) == {'oldest_pending_age_seconds': 70, 'blocked_streams': 1, 'retrying': 1}


def test_poison_and_conflicting_event_do_not_starve_other_customers(tmp_path):
    cfg = config()
    cfg.accounts['web'] = website()
    store = Store('sqlite://' + str(tmp_path / 'poison.db'))
    store.migrate()
    worker = WebsiteWorker(cfg, store, Mock(), Mock(), accounts=['web'])
    valid = {'source': cfg.accounts['web'].provider_account, 'event_uuid': str(uuid4()), 'order_uuid': str(uuid4()), 'body': 'Original'}
    worker._store_events('web', [valid, {'bad': True}], 1)
    worker._store_events('web', [dict(valid, body='Conflict'), dict(valid, event_uuid=str(uuid4()), order_uuid=str(uuid4()))], 1)
    with store.connect() as conn:
        rows = conn.execute('SELECT state FROM incoming_event').fetchall()
    assert [row['state'] for row in rows].count('review') == 2
    assert [row['state'] for row in rows].count('pending') == 2
