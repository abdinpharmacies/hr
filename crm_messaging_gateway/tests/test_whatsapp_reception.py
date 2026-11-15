import base64
import hashlib
from unittest.mock import Mock

import httpx
import pytest

from app.media import download
from app.providers import normalize, verify_signature
from app.worker import Worker
from test_gateway import whatsapp, config


def payload(kind, content, message_id='wamid.incoming', timestamp='1700000000'):
    return {'object': 'whatsapp_business_account', 'entry': [{'changes': [{
        'field': 'messages', 'value': {
            'metadata': {'phone_number_id': '456'},
            'contacts': [{'wa_id': '201014763233', 'profile': {'name': 'Sender'}}],
            'messages': [{'id': message_id, 'from': '201014763233', 'timestamp': timestamp,
                          'type': kind, kind: content, 'context': {'id': 'wamid.original'}}],
        },
    }]}]}


def event(kind, content, **kwargs):
    return normalize(whatsapp(), payload(kind, content, **kwargs))[0][2]


@pytest.mark.parametrize('sender', ['201099999999', '447700900123', '15551234567', 'opaque:customer-42'])
def test_incoming_sender_does_not_require_phone_or_saved_identity(sender):
    data = payload('text', {'body': 'Unknown customer'})
    value = data['entry'][0]['changes'][0]['value']
    value['messages'][0]['from'] = sender
    value.pop('contacts')
    result = normalize(whatsapp(), data)[0][2]
    assert result['sender'] == sender
    assert result['body'] == 'Unknown customer'
    assert 'review_reason' not in result


@pytest.mark.parametrize('kind,mime,expected', [
    ('image', 'image/jpeg', 'image'), ('image', 'image/png', 'image'),
    ('image', 'image/webp', 'image'), ('document', 'image/webp', 'image'),
    ('sticker', 'image/webp', 'image'), ('document', 'application/pdf', 'document'),
    ('document', 'text/plain', 'document'), ('audio', 'audio/mpeg', 'audio'),
    ('audio', 'audio/ogg', 'audio'), ('video', 'video/mp4', 'video'),
    ('document', 'audio/ogg', 'audio'), ('document', 'audio/mpeg', 'audio'),
])
def test_media_contract(kind, mime, expected):
    result = event(kind, {'id': '1234', 'mime_type': mime, 'caption': 'Caption', 'animated': True})
    assert result['media']['kind'] == expected
    assert result['body'] == 'Caption'
    assert result['reply_reference'] == 'wamid.original'
    assert result['whatsapp']['profile_name'] == 'Sender'
    assert result['whatsapp']['type'] == kind
    assert not result['unsupported']
    assert 'profile' not in result and 'contact' not in result


def test_voice_contacts_reactions_and_unknown():
    assert event('audio', {'id': '1234', 'mime_type': 'audio/ogg', 'voice': True})['media']['kind'] == 'voice'
    cards = [{'name': {'formatted_name': 'Other person'}, 'phones': [{'phone': '+201011111111'}]},
             {'name': {'formatted_name': 'Second person'}, 'emails': [{'email': 'test@example.invalid'}]}]
    assert event('contacts', cards)['whatsapp']['cards'] == cards
    for emoji in ('👍', '❤', ''):
        result = event('reaction', {'message_id': 'wamid.target', 'emoji': emoji})
        assert result['reaction'] == emoji
        assert result['reply_reference'] == 'wamid.target'
        assert result == event('reaction', {'message_id': 'wamid.target', 'emoji': emoji})
    assert event('unknown', {})['unsupported']
    assert event('document', {'id': '1234', 'mime_type': 'application/x-msdownload'})['unsupported']


def test_account_signature_and_profile_isolation():
    data = payload('text', {'body': 'Text'})
    data['entry'][0]['changes'][0]['value']['metadata']['phone_number_id'] = '789'
    with pytest.raises(ValueError, match='account mismatch'):
        normalize(whatsapp(), data)
    assert not verify_signature(whatsapp(), b'{}', {'x-hub-signature-256': 'sha256=wrong'})


def media_transport(raw, *, url='https://lookaside.fbsbx.com/media', expired=False):
    def respond(request):
        assert request.headers['Authorization'] == 'Bearer test-only'
        if request.url.host == 'graph.facebook.com':
            assert request.url.params['phone_number_id'] == '456'
            return httpx.Response(200, json={'url': url, 'mime_type': 'application/pdf',
                'file_size': len(raw), 'sha256': base64.b64encode(hashlib.sha256(raw).digest()).decode()})
        return httpx.Response(410 if expired else 200, content=raw)
    return httpx.MockTransport(respond)


def test_authenticated_media_retrieval_and_content_validation():
    metadata = event('document', {'id': '1234', 'mime_type': 'application/pdf'})['media']
    with httpx.Client(transport=media_transport(b'%PDF-test')) as client:
        assert base64.b64decode(download(client, whatsapp(), metadata)) == b'%PDF-test'
    with httpx.Client(transport=media_transport(b'not a PDF')) as client, pytest.raises(ValueError):
        download(client, whatsapp(), metadata)
    with httpx.Client(transport=media_transport(b'%PDF-test', url='https://attacker.invalid/file')) as client, pytest.raises(ValueError):
        download(client, whatsapp(), metadata)
    with httpx.Client(transport=media_transport(b'%PDF-test', expired=True)) as client, pytest.raises(httpx.HTTPStatusError):
        download(client, whatsapp(), metadata)


def test_failed_download_retries_then_records_failure():
    store, odoo = Mock(), Mock()
    row = {'id': 1, 'account': 'wa', 'kind': 'incoming', 'attempts': 1,
           'payload': event('document', {'id': '1234', 'mime_type': 'application/pdf'})}
    store.claim_incoming.return_value = row
    with httpx.Client(transport=media_transport(b'%PDF-test', expired=True)) as client:
        worker = Worker(config(), store, odoo, client)
        worker.ingest()
        store.finish_incoming.assert_called_with(row, False)
        row['attempts'] = 8
        worker.ingest()
        store.finish_incoming.assert_called_with(row, True)
        assert odoo.call.call_args.kwargs['failed'] == 'download'


@pytest.mark.parametrize('kind,mime,raw,codec', [
    ('audio', 'audio/ogg', b'OggSdata', 'opus'),
    ('audio', 'audio/mpeg', b'ID3data', 'mp3'),
    ('audio', 'audio/aac', b'\xff\xf1data', 'aac'),
    ('audio', 'audio/amr', b'#!AMR\ndata', 'amr_nb'),
    ('video', 'video/mp4', b'\x00\x00\x00\x18ftypmp42', 'h264'),
])
def test_audio_video_duration_and_codec_validation(monkeypatch, kind, mime, raw, codec):
    import json
    from app.media import validate_whatsapp_content
    metadata = event(kind, {'id': '1234', 'mime_type': mime})['media']
    probe = {'format': {'duration': '12'}, 'streams': [{'codec_type': kind, 'codec_name': codec}]}
    monkeypatch.setattr('app.media.subprocess.run', lambda *args, **kwargs: Mock(stdout=json.dumps(probe)))
    validate_whatsapp_content(metadata, raw)
    probe['format']['duration'] = '301'
    with pytest.raises(ValueError, match='duration'):
        validate_whatsapp_content(metadata, raw)


def test_sticker_limits_and_malformed_contact_cards():
    assert event('sticker', {'id': '1234', 'mime_type': 'image/webp', 'file_size': 200 * 1024})['unsupported']
    assert not event('sticker', {'id': '1234', 'mime_type': 'image/webp', 'file_size': 200 * 1024, 'animated': True})['unsupported']
    with pytest.raises(ValueError, match='contact cards'):
        event('contacts', [{'name': None}])


def test_missing_codec_retains_media_for_retry(monkeypatch, caplog):
    from app.media import MediaDependencyUnavailable, run_media_tool
    def unavailable(*args, **kwargs):
        raise FileNotFoundError('private-local-path')
    monkeypatch.setattr('app.media.subprocess.run', unavailable)
    with pytest.raises(MediaDependencyUnavailable):
        run_media_tool(['ffprobe'])
    monkeypatch.setattr('app.worker.download', lambda *args: run_media_tool(['ffprobe']))
    store, odoo = Mock(), Mock()
    row = {'id': 1, 'account': 'wa', 'kind': 'incoming', 'attempts': 1,
           'payload': event('audio', {'id': '1234', 'mime_type': 'audio/ogg', 'voice': True})}
    store.claim_incoming.return_value = row
    worker = Worker(config(), store, odoo, Mock())
    worker.ingest()
    store.defer_incoming.assert_called_once_with(row)
    store.finish_incoming.assert_not_called()
    assert all(call.args[0] != 'receive_media' for call in odoo.call.call_args_list)
    assert 'codec_unavailable' in caplog.text
    assert 'private-local-path' not in caplog.text


@pytest.mark.parametrize('provider', ['whatsapp', 'telegram'])
def test_missing_codec_does_not_send_or_permanently_reject(monkeypatch, provider):
    from app.media import MediaDependencyUnavailable
    from app.providers import send
    from test_gateway import telegram
    def unavailable(*args):
        raise MediaDependencyUnavailable('Media codec tools are unavailable')
    monkeypatch.setattr('app.providers.prepare_whatsapp' if provider == 'whatsapp' else 'app.providers.prepare', unavailable)
    operation = {'body': '', 'destination': '12345', 'media': [{'kind': 'voice', 'mimetype': 'audio/webm'}]}
    with httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail('Unexpected provider call'))) as client:
        result = send(client, whatsapp() if provider == 'whatsapp' else telegram(), operation)
    assert result == {'status': 'failed', 'reference': '', 'error': 'unavailable'}



def test_contact_rejection_diagnostic_excludes_contact_data():
    from app.providers import ContactCardsError
    cards = [{'name': {'formatted_name': 'Private contact', 'last_name': None},
              'phones': [{'phone': '+201099999999'}], 'org': None}]
    with pytest.raises(ContactCardsError) as caught:
        event('contacts', cards)
    assert caught.value.category == 'null_container,null_value'
    assert 'Private contact' not in str(caught.value)
    assert '+201099999999' not in str(caught.value)


def test_contact_provider_extensions_do_not_discard_supported_fields():
    import copy
    cards = [{'name': {'formatted_name': 'Shared person'}, 'phones': [{'phone': '+201011111111'}],
              'provider_extension': {'private': 'Not retained'}}]
    original = copy.deepcopy(cards)
    result = event('contacts', cards)
    assert cards == original
    assert result['whatsapp']['cards'] == [{'name': cards[0]['name'], 'phones': cards[0]['phones']}]
    assert not result['unsupported']
    assert 'contact' not in result
    assert result['source_digest'] != event('contacts', result['whatsapp']['cards'])['source_digest']
    assert 'Not retained' not in str(result)


@pytest.mark.parametrize('cards', [None, [], [{}], [{'provider_extension': 'only'}],
    [{'name': {'formatted_name': 42}, 'provider_extension': 'ignored'}]])
def test_contact_extensions_do_not_bypass_structure_checks(cards):
    with pytest.raises(ValueError, match='contact cards'):
        event('contacts', cards)


def test_signed_contact_callback_normalizes_before_durable_ingestion():
    import hmac
    import json
    from fastapi.testclient import TestClient
    from app.main import create_app
    cards = [{'name': {'formatted_name': 'Shared person'}, 'phones': [{'phone': '+201011111111'}],
              'provider_extension': 'opaque metadata'}]
    raw = json.dumps(payload('contacts', cards)).encode()
    signature = hmac.new(b'test-secret-123456', raw, hashlib.sha256).hexdigest()
    store = Mock()
    with TestClient(create_app(config(), store)) as client:
        response = client.post('/webhooks/whatsapp/wa', content=raw,
                               headers={'x-hub-signature-256': 'sha256=' + signature})
    assert response.status_code == 200
    account, events = store.ingest.call_args.args
    assert account == 'wa'
    normalized = events[0][2]
    assert normalized['whatsapp']['cards'] == [{'name': cards[0]['name'], 'phones': cards[0]['phones']}]
    assert 'contact' not in normalized
