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
    operation = {'destination': str(uuid4()), 'token': str(uuid4()), 'body': 'reply'}

    def receive(req):
        assert req.headers['authorization'] == 'Bearer source-test-key'
        assert req.url.path == '/storefront-callcenter/v1/receive'
        return httpx.Response(200, json={'reference': operation['token']})

    with httpx.Client(transport=httpx.MockTransport(receive)) as client:
        assert send_reply(client, account, operation)['status'] == 'accepted'
    with httpx.Client(
        transport=httpx.MockTransport(lambda req: httpx.Response(503))
    ) as client:
        assert send_reply(client, account, operation) == {
            'status': 'review',
            'reference': '',
            'error': 'ambiguous',
        }


def test_credential_loading_is_account_scoped():
    from app.config import load_odoo_tokens

    cfg = config()
    cfg.accounts['tg'].token_source = 'odoo'
    cfg.accounts['tg'].token = None
    odoo = Mock()
    load_odoo_tokens(cfg, odoo, accounts=['wa'])
    odoo.call.assert_not_called()
