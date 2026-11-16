import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth_config import AuthSettings, AuthSource
from app.auth_receiver import create_app
from app.auth_worker import AuthWorker
from app.config import Account, Settings


SOURCE, DELIVERY, LEASE = str(uuid4()), str(uuid4()), 'a' * 43


def configuration():
    account = Account(provider='whatsapp', provider_account='123', token='provider-test-token',
                      odoo_key='staff-test-key', enabled=True, sending_enabled=True,
                      reception='webhook', webhook_secret='test-secret-123456', verify_token='test-verify')
    config = Settings(database_url='postgresql://localhost/gateway_test',
                      odoo_url='https://staff.example', odoo_database='staff', odoo_key='staff-key',
                      accounts={'wa': account}, sending_enabled=True)
    auth = AuthSettings(enabled=True, sources={SOURCE: AuthSource(
        url='https://shop.example', database='shop', token='dedicated-auth-test-key',
        account='wa', sender='123', templates={'en_US': 'authentication_en', 'ar': 'authentication_ar'})})
    return config, auth


def job():
    return {'delivery': DELIVERY, 'sender': '123', 'destination': '201001234567', 'code': '123456',
            'template': 'authentication_en', 'language': 'en_US',
            'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=4)).strftime('%Y-%m-%d %H:%M:%S')}


def sender_client(outcome='accepted', invalid_job=None):
    calls = []

    def handle(request):
        data = json.loads(request.content)
        calls.append((str(request.url), data))
        if request.url.path.endswith('/lease'):
            return httpx.Response(200, json={'delivery': DELIVERY, 'lease': LEASE})
        if request.url.path.endswith('/dispatch'):
            return httpx.Response(200, json=invalid_job or job())
        if request.url.path.endswith('/report'):
            return httpx.Response(200, json=True)
        if request.url.host == 'graph.facebook.com':
            if outcome == 'timeout':
                raise httpx.ReadTimeout('ambiguous')
            if outcome == 'connect':
                raise httpx.ConnectError('unavailable')
            if outcome == 'rejected':
                return httpx.Response(400, json={'error': {'message': 'rejected'}})
            return httpx.Response(200, json={'messages': [{'id': 'wamid.test'}]})
        raise AssertionError('Unexpected URL')

    return httpx.Client(transport=httpx.MockTransport(handle)), calls


def test_authentication_uses_both_code_parameters_and_callback():
    config, auth = configuration()
    client, calls = sender_client()
    with client:
        AuthWorker(config, auth, Mock(), client).deliver(SOURCE, auth.sources[SOURCE])
    url, payload = next(item for item in calls if 'graph.facebook.com' in item[0])
    assert '/v26.0/123/messages' in url
    assert payload['type'] == 'template' and 'text' not in payload
    assert payload['biz_opaque_callback_data'] == f'ab-auth:{SOURCE}:{DELIVERY}'
    components = payload['template']['components']
    assert components[0]['parameters'][0]['text'] == '123456'
    assert components[1] == {'type': 'button', 'sub_type': 'url', 'index': '0', 'parameters': [{'type': 'text', 'text': '123456'}]}
    assert calls[-1][1]['status'] == 'accepted' and 'code' not in calls[-1][1]


@pytest.mark.parametrize('outcome,expected', [('timeout', 'unknown'), ('connect', 'transient'), ('rejected', 'rejected')])
def test_send_outcomes(outcome, expected):
    config, auth = configuration()
    client, calls = sender_client(outcome)
    with client:
        AuthWorker(config, auth, Mock(), client).deliver(SOURCE, auth.sources[SOURCE])
    assert calls[-1][1]['status'] == expected


@pytest.mark.parametrize('field,value', [('template', 'free_form'), ('language', 'xx'), ('sender', '999'), ('code', 'bad'), ('destination', 'bad')])
def test_forged_scope_and_template_fail_closed(field, value):
    config, auth = configuration()
    client, calls = sender_client(invalid_job=dict(job(), **{field: value}))
    with client:
        AuthWorker(config, auth, Mock(), client).deliver(SOURCE, auth.sources[SOURCE])
    assert not any('graph.facebook.com' in url for url, data in calls)
    assert calls[-1][1]['status'] == 'rejected'


def test_disabled_worker_does_not_poll_or_send():
    config, auth = configuration()
    auth.enabled = False
    client, calls = sender_client()
    with client:
        AuthWorker(config, auth, Mock(), client).deliver(SOURCE, auth.sources[SOURCE])
    assert calls == []


def status_payload():
    return {'object': 'whatsapp_business_account', 'entry': [{'changes': [{'field': 'messages', 'value': {
        'metadata': {'phone_number_id': '123'}, 'statuses': [
            {'id': 'wamid.auth', 'recipient_id': '201001234567', 'status': 'delivered', 'timestamp': '1700000000',
             'biz_opaque_callback_data': f'ab-auth:{SOURCE}:{DELIVERY}'},
            {'id': 'wamid.staff', 'recipient_id': '201001234568', 'status': 'sent', 'timestamp': '1700000001'},
        ],
    }}]}]}


def test_signed_callbacks_routed_away_from_staff_and_duplicate_replayed():
    config, auth = configuration()
    store = Mock()
    payload = json.dumps(status_payload()).encode()
    signature = 'sha256=' + hmac.new(b'test-secret-123456', payload, hashlib.sha256).hexdigest()
    with TestClient(create_app(config, auth, store)) as client:
        for index in range(2):
            assert client.post('/webhooks/whatsapp/wa', content=payload, headers={'X-Hub-Signature-256': signature}).status_code == 200
    rows = [call.args for call in store.ingest.call_args_list]
    auth_rows = [events for code, events in rows if code == 'auth:' + SOURCE]
    staff_rows = [events for code, events in rows if code == 'wa']
    assert len(auth_rows) == len(staff_rows) == 2
    assert auth_rows[0][0][2]['delivery'] == DELIVERY
    assert staff_rows[0][0][2]['reference'] == 'wamid.staff'
    assert all('code' not in event[2] for row in auth_rows for event in row)


def test_forged_webhook_does_not_persist():
    config, auth = configuration()
    store = Mock()
    with TestClient(create_app(config, auth, store)) as client:
        response = client.post('/webhooks/whatsapp/wa', json=status_payload(), headers={'X-Hub-Signature-256': 'sha256=forged'})
    assert response.status_code == 403
    store.ingest.assert_not_called()


def test_receipt_outage_defers_without_provider_send():
    config, auth = configuration()
    store = Mock()
    row = {'account': 'auth:' + SOURCE, 'payload': {'delivery': DELIVERY, 'reference': 'wamid.auth', 'status': 'delivered'}}
    store.claim_incoming.return_value = row
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(503))) as client:
        AuthWorker(config, auth, store, client).receipts()
    store.defer_incoming.assert_called_once_with(row)


def test_auth_source_rejects_insecure_origin():
    with pytest.raises(ValueError):
        AuthSource(url='http://shop.example', database='shop', token='test', account='wa', sender='123', templates={'en_US': 'auth'})
