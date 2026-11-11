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
