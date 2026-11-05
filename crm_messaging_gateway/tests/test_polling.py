import json
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.receiver import Receiver, ReceiverStopped
from app.telegram_setup import configure
from app.worker import Odoo
from test_gateway import config, telegram, update


def polling():
    return telegram().model_copy(update={'reception': 'polling'})


@pytest.mark.parametrize(
    'origin',
    [
        'http://localhost:4092',
        'http://127.0.0.2:4092',
        'http://example.com',
        'http://127.0.0.1.evil.test',
        'http://user@127.0.0.1',
        'http://127.0.0.1/path',
    ],
)
def test_http_exception_is_literal_loopback_only(origin):
    values = config().model_dump()
    values.update(odoo_url=origin, allow_loopback_http=True)
    with pytest.raises(ValueError):
        Settings.model_validate(values)


@pytest.mark.parametrize('origin', ['http://127.0.0.1:4092', 'http://[::1]:4092'])
def test_explicit_development_http(origin):
    values = config().model_dump()
    values.update(odoo_url=origin)
    with pytest.raises(ValueError):
        Settings.model_validate(values)
    assert Settings.model_validate(dict(values, allow_loopback_http=True))


def test_controller_envelope_and_correlation():
    cfg = config().model_copy(update={'odoo_transport': 'controller_v1'})

    def respond(request):
        envelope = json.loads(request.content)
        assert request.url.path == '/crm/messaging/v1/lease_outgoing'
        assert envelope['payload'] == {'account_code': 'tg', 'provider_account': '123'}
        return httpx.Response(
            200, json={'correlation_id': envelope['correlation_id'], 'result': False}
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert Odoo(cfg, client).call('lease_outgoing', 'tg') is False


def test_credential_lock_conflict_retries_without_repeating_other_operations(monkeypatch):
    sleeps = []
    monkeypatch.setattr('app.odoo.time.sleep', sleeps.append)
    client = Mock()
    client.post.side_effect = [httpx.Response(409), httpx.Response(200, json={'token': 'protected'})]
    assert Odoo(config(), client).call('get_provider_credentials', 'tg') == {'token': 'protected'}
    assert sleeps == [0.2]
    assert client.post.call_count == 2
    client.reset_mock(side_effect=True)
    client.post.return_value = httpx.Response(409)
    with pytest.raises(RuntimeError):
        Odoo(config(), client).call('receive_event', 'tg', event={})
    assert client.post.call_count == 1


def test_credential_lock_retries_are_bounded(monkeypatch):
    sleeps = []
    monkeypatch.setattr('app.odoo.time.sleep', sleeps.append)
    client = Mock()
    client.post.return_value = httpx.Response(409)
    with pytest.raises(RuntimeError):
        Odoo(config(), client).call('get_provider_credentials', 'tg')
    assert client.post.call_count == 4
    assert sleeps == [0.2, 0.4, 0.8]


def test_receiver_credential_startup_failure_is_retryable(monkeypatch):
    def unavailable():
        raise RuntimeError('Credentials unavailable')

    monkeypatch.setattr('app.receiver.settings', unavailable)
    monkeypatch.setattr('sys.argv', ['receiver', 'tg'])
    from app.receiver import main

    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 75


@pytest.mark.parametrize('status', [429, 500, 502, 503])
def test_odoo_http_outage_has_retryable_classification(status):
    from app.odoo import OdooUnavailable

    client = Mock()
    client.post.return_value = httpx.Response(status)
    with pytest.raises(OdooUnavailable):
        Odoo(config(), client).call('receive_event', 'tg', event={})


def test_odoo_transport_outage_has_retryable_classification():
    from app.odoo import OdooUnavailable

    client = Mock()
    client.post.side_effect = httpx.ConnectError('offline')
    with pytest.raises(OdooUnavailable):
        Odoo(config(), client).call('receive_event', 'tg', event={})


def test_polling_account_rejects_webhook():
    cfg = config()
    cfg.accounts['tg'] = polling()
    store = Mock()
    response = TestClient(create_app(cfg, store)).post(
        '/webhooks/telegram/tg',
        json=update(),
        headers={'X-Telegram-Bot-Api-Secret-Token': 'test-secret-123456'},
    )
    assert response.status_code == 409
    store.ingest.assert_not_called()


def test_receiver_persists_before_next_offset_and_replays_after_failure():
    store, client, conn = Mock(), Mock(), Mock()
    store.polling_offset.return_value = 0
    client.post.return_value = httpx.Response(
        200, json={'ok': True, 'result': [update()]}
    )
    receiver = Receiver('tg', polling(), store, client)
    store.persist_poll.side_effect = RuntimeError('queue down')
    with pytest.raises(RuntimeError):
        receiver.tick(conn)
    assert client.post.call_args.kwargs['json']['offset'] == 0
    store.persist_poll.side_effect = None
    assert receiver.tick(conn) == 1
    assert client.post.call_args.kwargs['json']['offset'] == 0
    assert store.persist_poll.call_args.args[-1] == 2
    store.polling_offset.return_value = 2
    client.post.return_value = httpx.Response(200, json={'ok': True, 'result': []})
    assert receiver.tick(conn) == 0
    assert client.post.call_args.kwargs['json']['offset'] == 2


@pytest.mark.parametrize('status', [401, 403, 409])
def test_receiver_does_not_compete_or_retry_revoked_bot(status):
    store, client = Mock(), Mock()
    store.polling_offset.return_value = 0
    client.post.return_value = httpx.Response(status, json={})
    with pytest.raises(ReceiverStopped):
        Receiver('tg', polling(), store, client).tick(Mock())
    store.persist_poll.assert_not_called()


def test_setup_refuses_foreign_webhook_and_preserves_pending_when_authorized():
    client = Mock()
    identity = httpx.Response(
        200,
        json={
            'ok': True,
            'result': {'id': 123, 'is_bot': True, 'username': 'test_bot'},
        },
    )
    webhook = httpx.Response(
        200,
        json={
            'ok': True,
            'result': {'url': 'https://owned.invalid/hook', 'pending_update_count': 3},
        },
    )
    client.post.side_effect = [identity, webhook]
    with pytest.raises(RuntimeError):
        configure(client, polling(), polling=True)
    assert client.post.call_count == 2
    client.reset_mock()
    client.post.side_effect = [
        identity,
        webhook,
        httpx.Response(200, json={'ok': True}),
    ]
    assert configure(
        client, polling(), polling=True, expected_webhook='https://owned.invalid/hook'
    )['polling_ready']
    assert client.post.call_args.kwargs['json'] == {'drop_pending_updates': False}


@pytest.mark.parametrize(
    'dsn',
    [
        'postgresql://localhost/%6fdoo_test',
        'postgresql://localhost/queue?dbname=odoo_test',
        'postgresql://localhost/queue?service=odoo',
        'postgresql://localhost/',
    ],
)
def test_queue_database_cannot_be_aliased_to_odoo(dsn):
    values = config().model_dump()
    values['database_url'] = dsn
    with pytest.raises(ValueError):
        Settings.model_validate(values)


def test_odoo_managed_token_loaded_without_configuration_copy():
    from app.config import Account, load_odoo_tokens

    cfg = config()
    cfg.accounts = {'tg': Account(provider='telegram', provider_account='123', token_source='odoo', webhook_secret='test-secret-123456')}
    odoo = Mock()
    odoo.call.return_value = {'provider': 'telegram', 'provider_account': '123', 'token': '123:protected-value'}
    load_odoo_tokens(cfg, odoo)
    assert cfg.accounts['tg'].token.get_secret_value() == '123:protected-value'
    assert 'protected-value' not in repr(cfg)
    odoo.call.assert_called_once_with('get_provider_credentials', 'tg')
    odoo.call.return_value = {'provider': 'telegram', 'provider_account': '999', 'token': '999:wrong'}
    with pytest.raises(RuntimeError):
        load_odoo_tokens(cfg, odoo)
    with pytest.raises(ValueError):
        Account(provider='telegram', provider_account='123', token_source='odoo', token='123:copied', webhook_secret='test-secret-123456')
