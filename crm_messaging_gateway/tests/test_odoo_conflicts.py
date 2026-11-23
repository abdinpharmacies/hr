import json

import httpx
import pytest

from app.odoo import Odoo, OdooUnavailable
from app.storage import Store
from app.website import WebsiteWorker
from uuid import uuid4
from test_gateway import config
from test_website import website


def website_config():
    result = config()
    result.accounts['web'] = website()
    return result


@pytest.mark.parametrize('method', ['authorize_send', 'lease_outgoing', 'report_delivery',
    'receive_website_event', 'receive_website_chat', 'receive_website_lifecycle', 'website_capabilities'])
@pytest.mark.parametrize('transport', ['json2', 'controller_v1'])
def test_transaction_conflicts_retry_identical_request(method, transport, monkeypatch):
    configuration = website_config()
    configuration.odoo_transport = transport
    calls = []
    delays = []
    monkeypatch.setattr('app.odoo.time.sleep', delays.append)

    def handle(request):
        body = json.loads(request.content)
        calls.append((str(request.url), dict(request.headers), body))
        if len(calls) < 4:
            return httpx.Response(409)
        return httpx.Response(200, json={'correlation_id': body['correlation_id'], 'result': True}
            if 'correlation_id' in body else True)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        assert Odoo(configuration, client).call(method, 'web', token='stable-token') is True
    assert len(calls) == 4 and all(item == calls[0] for item in calls)
    assert delays == [0.2, 0.4, 0.8]


def test_exhausted_conflicts_remain_transient(monkeypatch):
    calls = []
    monkeypatch.setattr('app.odoo.time.sleep', lambda delay: None)

    def handle(request):
        calls.append(request)
        return httpx.Response(409)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(OdooUnavailable, match='transaction conflict'):
            Odoo(website_config(), client).call('authorize_send', 'web')
    assert len(calls) == 4


@pytest.mark.parametrize('status', [400, 401, 403, 404, 429, 500, 503])
def test_other_failures_are_not_replayed(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        with pytest.raises(RuntimeError):
            Odoo(website_config(), client).call('authorize_send', 'web')
    assert len(calls) == 1


def test_exhausted_conflict_defers_accepted_incoming_event(tmp_path, monkeypatch):
    configuration = website_config()
    store = Store('sqlite://' + str(tmp_path / 'conflicts.db'))
    store.migrate()
    event = {'source': configuration.accounts['web'].provider_account,
             'event_uuid': str(uuid4()), 'order_uuid': str(uuid4())}
    store.ingest('web', [(event['event_uuid'], 'incoming',
        {'website_event': event, 'sender': event['order_uuid']})])
    calls = []
    monkeypatch.setattr('app.odoo.time.sleep', lambda delay: None)

    def handle(request):
        calls.append(request)
        return httpx.Response(409)

    with httpx.Client(transport=httpx.MockTransport(handle)) as client:
        WebsiteWorker(configuration, store, Odoo(configuration, client), client, accounts=['web']).ingest()
    assert len(calls) == 4
    with store.connect() as connection:
        row = connection.execute('SELECT state, attempts FROM incoming_event').fetchone()
    assert row['state'] == 'pending' and row['attempts'] == 0
