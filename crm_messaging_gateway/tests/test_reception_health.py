from contextlib import contextmanager
from unittest.mock import Mock

import httpx
import pytest

from app.health import reception_health
from app.receiver import Receiver, ReceiverRetryable, ReceiverStopped
from test_gateway import config
from test_polling import polling


@pytest.mark.parametrize('status,category', [(401, 'invalid_credentials'), (403, 'invalid_credentials'), (409, 'competing_receiver')])
def test_sanitized_stops(status, category):
    store = Mock()
    store.polling_offset.return_value = 0
    client = Mock()
    client.post.return_value = httpx.Response(status, json={'description': 'secret-token message-body'})
    with pytest.raises(ReceiverStopped, match=category) as error:
        Receiver('tg', polling(), store, client).tick(Mock())
    assert 'secret' not in str(error.value)
    store.persist_poll.assert_not_called()


def receiver_with_lock():
    store, conn = Mock(), Mock(closed=False, broken=False)

    @contextmanager
    def locked(account):
        yield conn

    store.receiver = locked
    return Receiver('tg', polling(), store, Mock()), conn


def test_temporary_failure_exits_retryable_after_bounded_backoff(monkeypatch, caplog):
    receiver, conn = receiver_with_lock()
    monkeypatch.setattr('app.receiver.configure', lambda *args: {'webhook_present': False})
    receiver.tick = Mock(side_effect=httpx.ConnectError('secret-token message-body'))
    waits = []
    monkeypatch.setattr('app.receiver.time.sleep', waits.append)
    with pytest.raises(ReceiverRetryable, match='network_failure'):
        receiver.run()
    assert receiver.tick.call_count == 8
    assert waits == [2, 4, 8, 16, 32, 60, 60]
    assert 'secret-token' not in caplog.text
    assert conn.rollback.call_count == 8


def test_transient_recovery_resets_failure_counter(monkeypatch):
    receiver, conn = receiver_with_lock()
    monkeypatch.setattr('app.receiver.configure', lambda *args: {'webhook_present': False})
    receiver.tick = Mock(side_effect=[httpx.ConnectError('private'), 0, httpx.ConnectError('private'), ReceiverStopped('stop')])
    waits = []
    monkeypatch.setattr('app.receiver.time.sleep', waits.append)
    with pytest.raises(ReceiverStopped):
        receiver.run()
    assert waits == [2, 2]


def test_webhook_never_polled(monkeypatch):
    receiver, conn = receiver_with_lock()
    monkeypatch.setattr('app.receiver.configure', lambda *args: {'webhook_present': True})
    receiver.tick = Mock()
    with pytest.raises(ReceiverStopped, match='active_webhook'):
        receiver.run()
    receiver.tick.assert_not_called()


def test_health_includes_missing_stale_and_disabled_accounts():
    cfg = config()
    cfg.accounts = {key: polling().model_copy(update={'provider_account': value, 'enabled': key != 'disabled'}) for key, value in [('fresh', '123'), ('stale', '456'), ('missing', '789'), ('disabled', '999')]}
    result = reception_health(cfg, [{'provider_account': '123', 'updated_at': 900}, {'provider_account': '456', 'updated_at': 879}], [{'account': 'stale', 'oldest': 500}], now=1000)
    assert result['fresh']['healthy'] is True
    assert result['stale']['healthy'] is False
    assert result['missing']['healthy'] is False
    assert result['disabled']['healthy'] is None
    assert result['stale']['backlog_age_seconds'] == 500


def test_webhook_conflict_is_distinct_and_sanitized():
    store, client = Mock(), Mock()
    store.polling_offset.return_value = 0
    client.post.return_value = httpx.Response(409, json={'description': 'webhook active secret-token'})
    with pytest.raises(ReceiverStopped, match='active_webhook') as error:
        Receiver('tg', polling(), store, client).tick(Mock())
    assert 'secret-token' not in str(error.value)


def test_malformed_event_does_not_advance_offset():
    store, client = Mock(), Mock()
    store.polling_offset.return_value = 0
    client.post.return_value = httpx.Response(200, json={'ok': True, 'result': [None]})
    with pytest.raises(ReceiverStopped, match='malformed_event'):
        Receiver('tg', polling(), store, client).tick(Mock())
    store.persist_poll.assert_not_called()
