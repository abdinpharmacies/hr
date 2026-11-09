import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Account, Settings
from app.main import create_app
from app.providers import normalize, send, verify_signature
from app.storage import Conflict
from app.worker import Worker
from app.odoo import OdooUnavailable


def telegram():
    return Account(
        provider='telegram',
        provider_account='123',
        token='123:test-only',
        webhook_secret='test-secret-123456',
        enabled=True,
    )


def whatsapp():
    return Account(
        provider='whatsapp',
        provider_account='456',
        token='test-only',
        webhook_secret='test-secret-123456',
        verify_token='test-verify',
        reception='webhook',
        enabled=True,
    )


def config():
    return Settings(
        database_url='postgresql://localhost/gateway_test',
        odoo_url='https://odoo.invalid',
        odoo_database='odoo_test',
        odoo_key='test-only',
        accounts={'tg': telegram(), 'wa': whatsapp()},
    )


def update(chat_type='private', text='Hello'):
    return {
        'update_id': 1,
        'message': {
            'message_id': 2,
            'chat': {'id': 1234, 'type': chat_type},
            'date': 1700000000,
            'text': text,
        },
    }


def test_api_starts_and_accepts_webhooks_without_odoo(tmp_path, monkeypatch):
    cfg = config()
    cfg.accounts = {
        'tg': Account(
            provider='telegram',
            provider_account='123',
            token_source='odoo',
            webhook_secret='test-secret-123456',
            enabled=True,
        )
    }
    path = tmp_path / 'config.json'
    path.write_text(
        json.dumps(cfg.model_dump(), default=lambda value: value.get_secret_value())
    )
    path.chmod(0o600)
    monkeypatch.setenv('CRM_MESSAGING_CONFIG', str(path))
    credential_loader = Mock(
        side_effect=AssertionError('API must not request Odoo credentials')
    )
    monkeypatch.setattr('app.config.load_odoo_tokens', credential_loader)
    store = Mock()
    store.connect.side_effect = RuntimeError('Queue unavailable')
    client = TestClient(create_app(store=store))
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.get('/ready').status_code == 503
    response = client.post(
        '/webhooks/telegram/tg',
        json=update(),
        headers={
            'X-Telegram-Bot-Api-Secret-Token': 'test-secret-123456',
        },
    )
    assert response.status_code == 200
    store.ingest.assert_called_once()
    credential_loader.assert_not_called()


def test_odoo_outage_defers_incoming_without_using_rejection_attempts():
    store, odoo = Mock(), Mock()
    row = {'kind': 'incoming', 'account': 'tg', 'payload': {}}
    store.claim_incoming.return_value = row
    odoo.call.side_effect = OdooUnavailable('Temporarily unavailable')
    Worker(config(), store, odoo, Mock()).ingest()
    store.defer_incoming.assert_called_once_with(row)
    store.finish_incoming.assert_not_called()


def test_incoming_worker_starts_without_loading_provider_credentials(monkeypatch):
    from app.worker import main

    settings_loader = Mock(return_value=config())
    credential_loader = Mock(
        side_effect=AssertionError('Incoming worker must not need provider credentials')
    )
    worker = Mock()
    worker.tick.side_effect = KeyboardInterrupt
    monkeypatch.setattr('app.worker.settings', settings_loader)
    monkeypatch.setattr('app.worker.load_odoo_tokens', credential_loader)
    monkeypatch.setattr('app.worker.Worker', Mock(return_value=worker))
    with pytest.raises(KeyboardInterrupt):
        main()
    settings_loader.assert_called_once_with(load_provider_tokens=False)
    credential_loader.assert_not_called()


def test_signature_exact_raw_bytes():
    account = whatsapp()
    body = b'{"object": "whatsapp_business_account"}'
    signature = (
        'sha256='
        + hmac.new(
            account.webhook_secret.get_secret_value().encode(), body, hashlib.sha256
        ).hexdigest()
    )
    assert verify_signature(account, body, {'x-hub-signature-256': signature})
    assert not verify_signature(
        account, body + b' ', {'x-hub-signature-256': signature}
    )
    assert not verify_signature(account, body, {})


def test_telegram_secret_and_private_chat():
    account = telegram()
    assert verify_signature(
        account, b'', {'x-telegram-bot-api-secret-token': 'test-secret-123456'}
    )
    assert not verify_signature(
        account, b'', {'x-telegram-bot-api-secret-token': 'wrong'}
    )
    assert normalize(account, update())[0][1] == 'incoming'
    assert normalize(account, update('group'))[0][1] == 'ignored'
    assert normalize(account, {'update_id': 2, 'channel_post': {}})[0][1] == 'ignored'


def test_attachment_no_download():
    payload = update()
    del payload['message']['text']
    payload['message']['photo'] = [{'file_id': 'do-not-download'}]
    event = normalize(telegram(), payload)[0][2]
    assert not event['unsupported'] and event['body'] == 'Attachment'
    assert event['media']['file_id'] == 'do-not-download'
    assert 'data' not in event['media']


def test_account_mismatch():
    payload = {
        'object': 'whatsapp_business_account',
        'entry': [
            {
                'changes': [
                    {
                        'field': 'messages',
                        'value': {
                            'metadata': {'phone_number_id': 'wrong'},
                            'messages': [],
                        },
                    }
                ]
            }
        ],
    }
    with pytest.raises(ValueError, match='mismatch'):
        normalize(whatsapp(), payload)


def test_webhook_durability_and_conflict():
    store = Mock()
    client = TestClient(create_app(config(), store))
    headers = {'X-Telegram-Bot-Api-Secret-Token': 'test-secret-123456'}
    assert (
        client.post('/webhooks/telegram/tg', json=update(), headers=headers).status_code
        == 200
    )
    store.ingest.assert_called_once()
    store.ingest.side_effect = RuntimeError('database unavailable')
    assert (
        client.post('/webhooks/telegram/tg', json=update(), headers=headers).status_code
        == 503
    )
    store.ingest.side_effect = Conflict()
    assert (
        client.post('/webhooks/telegram/tg', json=update(), headers=headers).status_code
        == 409
    )
    assert client.post('/webhooks/telegram/tg', json=update()).status_code == 403
    assert (
        client.post('/webhooks/telegram/wa', json=update(), headers=headers).status_code
        == 404
    )


def test_whatsapp_verification():
    client = TestClient(create_app(config(), Mock()))
    response = client.get(
        '/webhooks/whatsapp/wa',
        params={
            'hub.mode': 'subscribe',
            'hub.verify_token': 'test-verify',
            'hub.challenge': '42',
        },
    )
    assert response.status_code == 200 and response.text == '42'
    assert client.get('/webhooks/whatsapp/wa').status_code == 403


def operation():
    return {'body': 'Reply', 'destination': '12345', 'expires_at': False}


@pytest.mark.parametrize(
    'error,expected',
    [
        (httpx.ReadTimeout('timeout'), 'review'),
        (httpx.WriteError('broken'), 'review'),
        (httpx.ConnectError('unavailable'), 'failed'),
    ],
)
def test_transport_classification(error, expected):
    client = Mock()
    client.post.side_effect = error
    assert send(client, telegram(), operation())['status'] == expected


@pytest.mark.parametrize(
    'status,data,expected',
    [
        (200, {'ok': True, 'result': {'message_id': 5}}, 'accepted'),
        (200, {'ok': False}, 'review'),
        (500, {}, 'review'),
        (408, {}, 'review'),
        (403, {}, 'failed'),
        (429, {'parameters': {'retry_after': 100}}, 'failed'),
    ],
)
def test_provider_evidence(status, data, expected):
    client = Mock()
    client.post.return_value = httpx.Response(status, json=data)
    result = send(client, telegram(), operation())
    assert result['status'] == expected
    if status == 429:
        assert result['retry_after'] == 100 and result['error'] == 'rate_limit'


def test_whatsapp_expiration_before_http():
    client = Mock()
    payload = operation()
    payload['expires_at'] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).strftime('%Y-%m-%d %H:%M:%S')
    assert send(client, whatsapp(), payload)['error'] == 'window'
    client.post.assert_not_called()


def test_receipt_recovery_after_acknowledgment_crash():
    store, odoo = Mock(), Mock()
    row = {'account': 'tg', 'token': 'token', 'attempt': 1, 'receipt': 'receipt'}
    store.stored.return_value = [row]
    Worker(config(), store, odoo, Mock()).recover_receipts()
    odoo.call.assert_called_once_with(
        'acknowledge_receipt',
        'tg',
        token='token',
        attempt=1,
        lease='',
        receipt='receipt',
    )
    store.mark_ready.assert_called_once_with(row)


def test_send_requires_fresh_odoo_permission():
    store, odoo, client = Mock(), Mock(), Mock()
    row = {
        'account': 'tg',
        'token': 'token',
        'attempt': 1,
        'receipt': 'receipt',
        'payload': operation(),
    }
    store.claim_outgoing.return_value = row
    odoo.call.return_value = False
    Worker(config(), store, odoo, client).dispatch()
    client.post.assert_not_called()
    store.defer_send.assert_called_once_with(row)


def test_config_rejects_identity_and_database_reuse():
    with pytest.raises(ValueError):
        Account(
            provider='telegram',
            provider_account='456',
            token='123:wrong',
            webhook_secret='test-secret-123456',
        )
    with pytest.raises(ValueError):
        Settings(
            database_url='postgresql://localhost/same',
            odoo_url='https://odoo.invalid',
            odoo_database='same',
            odoo_key='x',
            accounts={},
        )


def test_whatsapp_webhook_signature_and_normalization():
    store = Mock()
    payload = {
        'object': 'whatsapp_business_account',
        'entry': [
            {
                'changes': [
                    {
                        'field': 'messages',
                        'value': {
                            'metadata': {'phone_number_id': '456'},
                            'messages': [
                                {
                                    'id': 'wa-message',
                                    'from': '201234',
                                    'type': 'text',
                                    'text': {'body': 'Hello'},
                                    'timestamp': '1700000000',
                                }
                            ],
                            'statuses': [
                                {
                                    'id': 'wa-sent',
                                    'recipient_id': '201234',
                                    'status': 'read',
                                    'timestamp': '1700000001',
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode()
    signature = (
        'sha256=' + hmac.new(b'test-secret-123456', raw, hashlib.sha256).hexdigest()
    )
    client = TestClient(create_app(config(), store))
    result = client.post(
        '/webhooks/whatsapp/wa', content=raw, headers={'X-Hub-Signature-256': signature}
    )
    assert result.status_code == 200
    events = store.ingest.call_args.args[1]
    assert events[0][2]['body'] == 'Hello'
    assert events[1][2]['status'] == 'read'
    assert (
        client.post(
            '/webhooks/whatsapp/wa',
            content=raw + b' ',
            headers={'X-Hub-Signature-256': signature},
        ).status_code
        == 403
    )


def test_attachment_conflicting_reuse_has_distinct_digest():
    first = update()
    del first['message']['text']
    first['message']['photo'] = [{'file_id': 'first'}]
    event = normalize(telegram(), first)[0][2]
    first['message']['photo'] = [{'file_id': 'second'}]
    changed = normalize(telegram(), first)[0][2]
    assert event['source_digest'] != changed['source_digest']


def test_body_limit_rejected_before_storage():
    store = Mock()
    client = TestClient(create_app(config(), store))
    assert (
        client.post('/webhooks/telegram/tg', content=b'x' * 1048577).status_code == 413
    )
    store.ingest.assert_not_called()


def test_contact_owner_and_third_party_are_distinct():
    payload = update()
    payload['message'].pop('text')
    payload['message']['from'] = {'id': 1234}
    payload['message']['contact'] = {'phone_number': '+201012345678', 'user_id': 1234}
    event = normalize(telegram(), payload)[0][2]
    assert event['contact'] == {
        'phone': '+201012345678',
        'user_id': '1234',
        'sender_id': '1234',
    }
    assert not event['unsupported']
    payload['message']['contact']['user_id'] = 5555
    event = normalize(telegram(), payload)[0][2]
    assert event['contact']['user_id'] != event['sender']
    payload['message']['from']['id'] = 5555
    with pytest.raises(ValueError):
        normalize(telegram(), payload)


def test_telegram_message_ids_are_scoped_to_chat():
    first = update()
    second = update()
    second['message']['chat']['id'] = 5678
    assert (
        normalize(telegram(), first)[0][2]['id']
        != normalize(telegram(), second)[0][2]['id']
    )


def test_contact_keyboard_uses_official_request_contact():
    client = Mock()
    client.post.return_value = httpx.Response(
        200, json={'ok': True, 'result': {'message_id': 99}}
    )
    result = send(
        client,
        telegram(),
        {
            'destination': '1234',
            'body': 'Share contact',
            'contact_button': 'Share contact',
        },
    )
    assert result['status'] == 'accepted'
    payload = client.post.call_args.kwargs['json']
    assert payload['reply_markup']['keyboard'][0][0]['request_contact'] is True
    assert payload['reply_markup']['one_time_keyboard'] is True


def test_setup_verifies_identity_before_webhook():
    from app.telegram_setup import configure

    client = Mock()
    client.post.side_effect = [
        httpx.Response(
            200,
            json={
                'ok': True,
                'result': {'id': 123, 'is_bot': True, 'username': 'test_bot'},
            },
        ),
        httpx.Response(200, json={'ok': True, 'result': {'url': ''}}),
        httpx.Response(200, json={'ok': True}),
    ]
    result = configure(
        client, telegram(), 'https://gateway.invalid/webhooks/telegram/tg'
    )
    assert result['verified'] and result['webhook_registered']
    assert client.post.call_args_list[0].args[0].endswith('/getMe')
    assert client.post.call_args_list[2].kwargs['json']['drop_pending_updates'] is False
    client.reset_mock()
    client.post.side_effect = [
        httpx.Response(200, json={'ok': True, 'result': {'id': 999, 'is_bot': True}})
    ]
    with pytest.raises(RuntimeError):
        configure(client, telegram(), 'https://gateway.invalid/webhooks/telegram/tg')
    assert client.post.call_count == 1


def test_profile_quote_and_media_metadata():
    payload = update()
    payload['message']['from'] = {
        'id': 12345,
        'first_name': 'Test',
        'username': 'tester',
    }
    payload['message']['reply_to_message'] = {'message_id': 9}
    payload['message']['document'] = {
        'file_id': 'pdf',
        'file_size': 200,
        'mime_type': 'application/pdf',
        'file_name': 'test.pdf',
    }
    event = normalize(telegram(), payload)[0][2]
    assert event['profile'] == {'name': 'Test', 'username': 'tester'}
    assert event['reply_reference'] == '9'
    assert event['media']['name'] == 'test.pdf'


def test_media_limits_and_reaction_evidence():
    from app.media import supported

    assert not supported(
        {
            'kind': 'image',
            'size': 11 * 1024 * 1024,
            'duration': 0,
            'mimetype': 'image/jpeg',
        }
    )
    assert not supported(
        {'kind': 'voice', 'size': 10, 'duration': 301, 'mimetype': 'audio/ogg'}
    )

    def respond(request):
        assert request.url.path.endswith('/setMessageReaction')
        assert json.loads(request.content)['message_id'] == 9
        return httpx.Response(200, json={'ok': True, 'result': True})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = send(
            client,
            telegram(),
            {
                'body': '👍',
                'destination': '12345',
                'reaction': '👍',
                'reply_reference': '9',
            },
        )
    assert result == {'status': 'accepted', 'reference': '9', 'error': 'none'}


def test_document_send_uses_multipart_and_quote():
    import base64

    raw = b'%PDF-1.4\nTest'

    def respond(request):
        assert request.url.path.endswith('/sendDocument')
        assert b'reply_parameters' in request.content
        assert raw in request.content
        return httpx.Response(200, json={'ok': True, 'result': {'message_id': 20}})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = send(
            client,
            telegram(),
            {
                'body': 'PDF',
                'destination': '12345',
                'reply_reference': '9',
                'media': [
                    {
                        'kind': 'document',
                        'size': len(raw),
                        'duration': 0,
                        'mimetype': 'application/pdf',
                        'name': 'test.pdf',
                        'data': base64.b64encode(raw).decode(),
                    }
                ],
            },
        )
    assert result['status'] == 'accepted'


def test_download_uses_fixed_provider_origin_and_bounded_bytes():
    from app.media import download

    metadata = {
        'kind': 'document',
        'size': 4,
        'duration': 0,
        'mimetype': 'application/pdf',
        'file_id': 'file',
    }

    def respond(request):
        assert request.url.host == 'api.telegram.org'
        if request.url.path.endswith('/getFile'):
            return httpx.Response(
                200, json={'ok': True, 'result': {'file_path': '../secret'}}
            )
        raise AssertionError('Unsafe path was downloaded')

    with httpx.Client(transport=httpx.MockTransport(respond)) as client, pytest.raises(
        ValueError
    ):
        download(client, telegram(), metadata)


def test_voice_duration_and_conversion(tmp_path):
    import base64
    import shutil
    import subprocess
    from app.media import prepare

    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg worker dependency is not installed')
    voice = tmp_path / 'voice.webm'
    subprocess.run(
        [
            'ffmpeg',
            '-nostdin',
            '-v',
            'error',
            '-f',
            'lavfi',
            '-i',
            'sine=frequency=440:duration=1',
            '-c:a',
            'libopus',
            str(voice),
        ],
        check=True,
    )
    raw = voice.read_bytes()
    metadata = {
        'kind': 'voice',
        'name': 'voice.webm',
        'mimetype': 'audio/webm',
        'duration': 1,
        'size': len(raw),
        'data': base64.b64encode(raw).decode(),
    }
    name, converted, mime = prepare(metadata)
    assert name == 'voice.ogg' and mime == 'audio/ogg' and converted.startswith(b'OggS')
    too_long = tmp_path / 'long.webm'
    subprocess.run(
        [
            'ffmpeg',
            '-nostdin',
            '-v',
            'error',
            '-f',
            'lavfi',
            '-i',
            'anullsrc=r=8000:cl=mono',
            '-t',
            '301',
            '-c:a',
            'libopus',
            str(too_long),
        ],
        check=True,
    )
    raw = too_long.read_bytes()
    with pytest.raises(ValueError, match='five minutes'):
        prepare(
            dict(
                metadata, size=len(raw), data=base64.b64encode(raw).decode(), duration=1
            )
        )


def test_reaction_normalization_and_worker_media_persistence_order():
    payload = {
        'update_id': 20,
        'message_reaction': {
            'chat': {'id': 12345, 'type': 'private'},
            'user': {'id': 12345},
            'message_id': 10,
            'date': 1735689600,
            'new_reaction': [{'type': 'emoji', 'emoji': '👍'}],
        },
    }
    event = normalize(telegram(), payload)[0][2]
    assert event['reaction'] == '👍' and event['reply_reference'] == '10'
    store, odoo = Mock(), Mock()
    store.claim_incoming.return_value = {
        'id': 1,
        'account': 'tg',
        'kind': 'incoming',
        'payload': {
            'id': '12345:1',
            'media': {
                'kind': 'document',
                'file_id': 'pdf',
                'name': 'test.pdf',
                'mimetype': 'application/pdf',
                'size': 9,
                'duration': 0,
            },
        },
    }

    def respond(request):
        assert odoo.call.call_args_list[0].args[0] == 'receive_event'
        if request.url.path.endswith('/getFile'):
            return httpx.Response(
                200, json={'ok': True, 'result': {'file_path': 'documents/test.pdf'}}
            )
        return httpx.Response(200, content=b'%PDF-test')

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        Worker(config(), store, odoo, client).ingest()
    assert [call.args[0] for call in odoo.call.call_args_list] == [
        'receive_event',
        'receive_media',
    ]
    store.finish_incoming.assert_called_once_with(
        store.claim_incoming.return_value, True
    )


def test_invalid_voice_is_rejected_before_provider_submission():
    import base64

    client = Mock()
    raw = b'not a recording'
    operation = {
        'body': 'Recording',
        'destination': '12345',
        'media': [
            {
                'kind': 'voice',
                'name': 'test.webm',
                'mimetype': 'audio/webm',
                'size': len(raw),
                'duration': 1,
                'data': base64.b64encode(raw).decode(),
            }
        ],
    }
    result = send(client, telegram(), operation)
    assert result == {'status': 'failed', 'reference': '', 'error': 'media'}
    client.post.assert_not_called()


def test_rejected_download_content_is_shown_as_failed():
    store, odoo = Mock(), Mock()
    store.claim_incoming.return_value = {
        'id': 1,
        'account': 'tg',
        'kind': 'incoming',
        'payload': {
            'id': '12345:1',
            'media': {
                'kind': 'document',
                'file_id': 'pdf',
                'name': 'test.pdf',
                'mimetype': 'application/pdf',
                'size': 7,
                'duration': 0,
            },
        },
    }
    odoo.call.side_effect = [True, RuntimeError('Rejected content'), True]

    def respond(request):
        if request.url.path.endswith('/getFile'):
            return httpx.Response(
                200, json={'ok': True, 'result': {'file_path': 'documents/test.pdf'}}
            )
        return httpx.Response(200, content=b'invalid')

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        Worker(config(), store, odoo, client).ingest()
    assert odoo.call.call_args.kwargs['failed'] == 'invalid'
    store.finish_incoming.assert_called_once_with(
        store.claim_incoming.return_value, True
    )


def test_outgoing_only_whatsapp_rejects_webhooks():
    account = Account(
        provider='whatsapp', provider_account='456', token='test-only', enabled=True
    )
    assert account.reception == 'disabled'
    cfg = config()
    cfg.accounts['wa'] = account
    store = Mock()
    client = TestClient(create_app(cfg, store))
    assert client.get('/webhooks/whatsapp/wa').status_code == 409
    assert client.post('/webhooks/whatsapp/wa', json={}).status_code == 409
    store.ingest.assert_not_called()


def test_sqlite_configuration_requires_encrypted_storage(tmp_path):
    values = config().model_dump()
    values['database_url'] = 'sqlite://' + str(tmp_path / 'queue.db')
    with pytest.raises(ValueError, match='Encrypted'):
        Settings(**values)
    assert (
        Settings(**dict(values, encrypted_storage_confirmed=True))
        .database_url.get_secret_value()
        .startswith('sqlite:')
    )


@pytest.mark.parametrize(
    'content,expected',
    [
        ({'template': {'name': 'welcome', 'language': {'code': 'en_US'}}}, 'template'),
        ({'reaction': '👍', 'reply_reference': 'wamid-target'}, 'reaction'),
        ({'reply_reference': 'wamid-target'}, 'text'),
    ],
)
def test_whatsapp_content_payload(content, expected):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'messages': [{'id': 'wamid-result'}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        outcome = send(
            client, whatsapp(), {'destination': '1234', 'body': 'Hello', **content}
        )
    assert outcome['status'] == 'accepted'
    assert captured[0]['type'] == expected
    if expected == 'text':
        assert captured[0]['context']['message_id'] == 'wamid-target'


def test_whatsapp_media_upload_and_ambiguous_send():
    import base64

    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith('/media'):
            return httpx.Response(200, json={'id': 'media-1'})
        payload = json.loads(request.content)
        assert payload['document']['id'] == 'media-1'
        raise httpx.ReadTimeout('Lost response', request=request)

    raw = b'%PDF-test'
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        outcome = send(
            client,
            whatsapp(),
            {
                'destination': '1234',
                'body': 'File',
                'media': [
                    {
                        'kind': 'document',
                        'name': 'test.pdf',
                        'size': len(raw),
                        'duration': 0,
                        'mimetype': 'application/pdf',
                        'data': base64.b64encode(raw).decode(),
                    }
                ],
            },
        )
    assert len(requests) == 2
    assert outcome == {'status': 'review', 'reference': '', 'error': 'ambiguous'}


def test_dispatch_terminal_authorization_never_contacts_provider():
    cfg, store, odoo, client = config(), Mock(), Mock(), Mock()
    store.claim_outgoing.return_value = {
        'id': 1,
        'account': 'wa',
        'token': 'x',
        'attempt': 1,
        'receipt': 'r',
        'sends': 1,
    }
    odoo.call.return_value = {'allowed': False, 'terminal': True, 'error': 'rejected'}
    Worker(cfg, store, odoo, client).dispatch()
    client.post.assert_not_called()
    assert store.outcome.call_args.args[1]['error'] == 'rejected'


def test_whatsapp_text_document_payload():
    import base64

    captured = []

    def handler(request):
        if request.url.path.endswith('/media'):
            return httpx.Response(200, json={'id': 'uploaded'})
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={'messages': [{'id': 'sent-document'}]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = send(
            client,
            whatsapp(),
            {
                'destination': '1234',
                'body': 'Notes',
                'media': [
                    {
                        'kind': 'document',
                        'mimetype': 'text/plain',
                        'name': 'notes.txt',
                        'size': 5,
                        'duration': 0,
                        'data': base64.b64encode(b'notes').decode(),
                    }
                ],
            },
        )
    assert result['status'] == 'accepted'
    assert captured[0]['document'] == {
        'id': 'uploaded',
        'caption': 'Notes',
        'filename': 'notes.txt',
    }


def test_whatsapp_video_codec_validation(monkeypatch):
    import base64
    from types import SimpleNamespace
    from app.media import prepare_whatsapp

    metadata = {
        'kind': 'video',
        'mimetype': 'video/mp4',
        'name': 'clip.mp4',
        'size': 12,
        'data': base64.b64encode(b'\x00\x00\x00\x0cftypisom').decode(),
    }
    monkeypatch.setattr(
        'app.media.subprocess.run',
        lambda *a, **k: SimpleNamespace(
            stdout=json.dumps(
                {'streams': [{'codec_type': 'video', 'codec_name': 'h264'}]}
            )
        ),
    )
    assert prepare_whatsapp(metadata)[2] == 'video/mp4'
    monkeypatch.setattr(
        'app.media.subprocess.run',
        lambda *a, **k: SimpleNamespace(
            stdout=json.dumps(
                {'streams': [{'codec_type': 'video', 'codec_name': 'hevc'}]}
            )
        ),
    )
    with pytest.raises(ValueError, match='codecs'):
        prepare_whatsapp(metadata)


def test_telegram_video_sends_private_upload_and_preserves_reply(monkeypatch):
    import base64
    from types import SimpleNamespace

    monkeypatch.setattr('app.media.subprocess.run', lambda *a, **k: SimpleNamespace(
        stdout=json.dumps({'streams': [{'codec_type': 'video', 'codec_name': 'h264'}]})
    ))
    metadata = {'kind': 'video', 'mimetype': 'video/mp4', 'name': 'clip.mp4',
                'size': 12, 'data': base64.b64encode(b'\x00\x00\x00\x0cftypisom').decode()}
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'ok': True, 'result': {'message_id': 123}})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    operation = {'destination': '1234', 'body': 'Caption', 'reply_reference': '7', 'media': [metadata]}
    result = send(client, telegram(), operation)
    assert result['status'] == 'accepted'
    assert requests[0].url.path.endswith('/sendVideo')
    assert b'name="video"; filename="clip.mp4"' in requests[0].content
    assert b'{"message_id": 7}' in requests[0].content
    assert b'Caption' in requests[0].content
    for change in ({'size': 17 * 1024 * 1024}, {'mimetype': 'video/webm'}, {'data': 'invalid'}):
        operation['media'] = [dict(metadata, **change)]
        assert send(client, telegram(), operation)['error'] == 'media'
    assert len(requests) == 1
