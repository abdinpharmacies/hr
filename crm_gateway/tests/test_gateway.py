import hashlib
import hmac
import json
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import worker
from app.config import settings
from app.main import app
from app.storage import Delivery, sessions, store_delivery


@pytest.fixture(autouse=True)
def rollback_deliveries():
    yield
    with sessions()() as session, session.begin():
        for row in session.scalars(select(Delivery).where(Delivery.source.like('test%'))):
            session.delete(row)


def test_durable_deduplication():
    with sessions()() as session, session.begin():
        first = store_delivery(session, 'test-store', 'one', 'website', {'revision': 1})
        second = store_delivery(session, 'test-store', 'one', 'website', {'revision': 1})
        assert first.id == second.id
    with sessions()() as session:
        assert session.get(Delivery, first.id).state == 'pending'


def test_event_identity_rejects_changed_content():
    with sessions()() as session, session.begin():
        store_delivery(session, 'test-store', 'one', 'website', {'revision': 1})
        with pytest.raises(ValueError):
            store_delivery(session, 'test-store', 'one', 'website', {'revision': 2})


def test_telegram_authentication_and_persistence():
    client = TestClient(app)
    event = {'update_id': 71, 'message': {'chat': {'id': 42}, 'text': 'Hello'}}
    assert client.post('/webhooks/test-telegram', json=event).status_code == 403
    response = client.post('/webhooks/test-telegram', json=event,
                           headers={'x-telegram-bot-api-secret-token': settings().channels['test-telegram'].secret.get_secret_value()})
    assert response.status_code == 200
    with sessions()() as session:
        assert session.scalar(select(Delivery).where(Delivery.source == 'test-telegram')).payload == event


def test_whatsapp_signature():
    raw = json.dumps({'entry': []}).encode()
    signature = 'sha256=' + hmac.new(settings().channels['test-whatsapp'].secret.get_secret_value().encode(), raw, hashlib.sha256).hexdigest()
    client = TestClient(app)
    assert client.post('/webhooks/test-whatsapp', content=raw, headers={'x-hub-signature-256': 'wrong'}).status_code == 403
    assert client.post('/webhooks/test-whatsapp', content=raw, headers={'x-hub-signature-256': signature}).status_code == 200


def test_failure_keeps_pending_and_backoff():
    with sessions()() as session, session.begin():
        row = store_delivery(session, 'test-site', 'failure', 'website', {'revision': 1})
    with patch.object(worker, 'rpc', side_effect=httpx.ConnectError('offline')):
        worker.deliver_pending()
    with sessions()() as session:
        row = session.get(Delivery, row.id)
        assert row.state == 'pending'
        assert row.attempts == 1
        assert row.error == 'ConnectError'
        assert row.last_success is None


def test_website_ack_after_commit():
    event = {'event_id': 'receipt', 'source': 'test-site', 'reference': 'R', 'revision': 1}
    calls = []
    def fake_rpc(peer, model, method, values):
        calls.append(method)
        if method == 'pending_events':
            return [{'id': 11, 'event': event}]
        if method == 'acknowledge':
            with sessions()() as session:
                assert session.scalar(select(Delivery).where(Delivery.event_id == 'receipt')) is not None
            return True
        return []
    with patch.object(worker, 'rpc', side_effect=fake_rpc):
        worker.sync_website()
    assert calls[:2] == ['pending_events', 'acknowledge']


def test_body_limit():
    assert TestClient(app).post('/webhooks/test-telegram', content=b'x' * 1_000_001).status_code == 413


def test_unknown_outbound_is_not_retried():
    with sessions()() as session, session.begin():
        row = store_delivery(session, 'test-reply', 'unknown', 'reply', {'body': 'Do not repeat'})
        row.state = 'unknown'
    with patch.object(worker, 'rpc') as rpc:
        worker.deliver_pending()
        worker.report_confirmed_replies()
        rpc.assert_not_called()
