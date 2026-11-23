import json
from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from app import ops
from app.website import WebsiteWorker, send_reply
from test_gateway import config
from test_website import website
from test_storage import store as postgres_store
from test_sqlite_storage import store as sqlite_store


@pytest.mark.parametrize('queue', ['sqlite_store', 'postgres_store'])
def test_status_scopes_every_account_metric(queue, request, monkeypatch, capsys):
    store = request.getfixturevalue(queue)
    cfg = config()
    cfg.accounts['web'] = website()
    cfg.database_url = SecretStr(store.database_url)
    for code in ('web', 'tg'):
        store.ingest(code, [('event', 'incoming', {'sender': 'customer'})])
        store.persist_outgoing(code, {'token': code, 'attempt': 1, 'lease': 'lease',
            'destination': 'customer', 'provider': 'website',
            'website_destination': {'kind': 'order', 'uuid': code}})
    with store.connect() as conn:
        conn.execute("UPDATE outgoing_operation SET state='done',outcome='{\"status\":\"review\"}' WHERE account='tg'")
        conn.execute('INSERT INTO telegram_polling(provider_account,next_offset,updated_at) VALUES (?,0,now())'
                     if queue == 'sqlite_store' else
                     'INSERT INTO telegram_polling(provider_account,next_offset,updated_at) VALUES (%s,0,now())', ('123',))
    monkeypatch.setattr(ops, 'settings', lambda **kwargs: cfg)
    monkeypatch.setattr(ops, 'Store', lambda dsn: store)
    monkeypatch.setattr('sys.argv', ['ops', 'status', '--account', 'web'])
    ops.main()
    result = json.loads(capsys.readouterr().out)
    assert {row['account'] for row in result['incoming']} == {'web'}
    assert {row['account'] for row in result['outgoing']} == {'web'}
    assert {row['account'] for row in result['website_queue']} == {'web'}
    assert set(result['reception_health']) == {'web'}
    assert result['polling'] == []
    assert result['metrics']['uncertain'] == 0
    assert result['metrics']['website']['blocked_streams'] == 0
    monkeypatch.setattr('sys.argv', ['ops', 'status'])
    ops.main()
    result = json.loads(capsys.readouterr().out)
    assert {row['account'] for row in result['incoming']} == {'web', 'tg'}
    assert result['metrics']['uncertain'] == 1
    assert result['metrics']['website']['blocked_streams'] == 1


@pytest.mark.parametrize('args', [['status', '--account', "unknown' OR 1=1"], ['migrate', '--account', 'tg']])
def test_status_rejects_bad_filter_without_opening_database(args, monkeypatch):
    monkeypatch.setattr(ops, 'settings', lambda **kwargs: config())
    store = Mock()
    monkeypatch.setattr(ops, 'Store', store)
    monkeypatch.setattr('sys.argv', ['ops', *args])
    with pytest.raises(SystemExit) as error:
        ops.main()
    assert error.value.code == 2
    store.assert_not_called()


def test_website_failure_logs_are_classified_and_private(caplog):
    cfg = config()
    cfg.accounts['web'] = website()
    client, receiver, store = Mock(), Mock(), Mock()
    receiver.call.return_value = {'version': 4}
    client.post.return_value = httpx.Response(403, json={'body': 'private customer text source-test-key https://private/file'})
    worker = WebsiteWorker(cfg, store, receiver, client, accounts=['web'])
    worker.fetch('web')
    assert 'account=web phase=fetch version=1 status=403 cause=authentication' in caplog.text
    result = send_reply(client, cfg.accounts['web'], {'token': 'token', 'body': 'private customer text',
        'website_destination': {'kind': 'order', 'uuid': cfg.accounts['web'].provider_account}}, account_code='web')
    assert result['website_failure'] == 'authentication'
    assert 'phase=reply version=2 status=403' in caplog.text
    for value in ('private customer text', 'source-test-key', 'https://private/file'):
        assert value not in caplog.text


def test_malformed_response_keeps_available_http_status(caplog):
    account = website()
    client = Mock()
    client.post.return_value = httpx.Response(200, text='private response credentials')
    result = send_reply(client, account, {'token': 'token', 'body': 'private body',
        'website_destination': {'kind': 'order', 'uuid': account.provider_account}}, account_code='web')
    assert result['status'] == 'failed'
    assert 'account=web phase=reply version=2 status=200 cause=transient' in caplog.text
    assert 'private' not in caplog.text
