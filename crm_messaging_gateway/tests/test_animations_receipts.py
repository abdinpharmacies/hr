import base64
import subprocess
from unittest.mock import Mock

import httpx
import pytest

from app.media import prepare, prepare_whatsapp, MediaDependencyUnavailable
from app.providers import send, send_read_receipt
from app.storage import Store, Conflict
from app.worker import Worker
from test_gateway import config, telegram, whatsapp
from test_incoming_attachments import event


@pytest.mark.parametrize('source,mime,kind', [
    ({'file_name': 'clip.gif', 'mime_type': 'image/gif'}, 'image/gif', 'image'),
    ({'file_name': 'clip.GIF'}, 'image/gif', 'image'),
    ({}, 'video/mp4', 'video'),
])
def test_animation_precedes_duplicate_document(source, mime, kind):
    metadata = dict(source, file_id='animation', file_size=100)
    result = event(animation=metadata, document=dict(metadata, file_id='duplicate'))
    assert not result['unsupported']
    assert result['media']['file_id'] == 'animation'
    assert result['media']['mimetype'] == mime
    assert result['media']['kind'] == kind


def test_gif_document_missing_mime_and_limits():
    assert event(document={'file_id': 'gif', 'file_name': 'clip.gif'})['media']['kind'] == 'image'
    assert event(animation={'file_id': 'gif', 'mime_type': 'image/gif', 'file_size': 10 * 1024 * 1024 + 1})['unsupported']
    assert event(animation={'file_id': 'mp4', 'duration': 301})['unsupported']


@pytest.fixture
def gif(tmp_path):
    path = tmp_path / 'animation.gif'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=red:s=16x16:d=0.2',
                    '-threads', '1', str(path)], check=True, timeout=15)
    raw = path.read_bytes()
    return {'kind': 'image', 'name': 'animation.gif', 'mimetype': 'image/gif',
            'size': len(raw), 'data': base64.b64encode(raw).decode()}


def test_real_gif_preserved_and_converted_to_h264(gif):
    assert prepare(gif)[1] == base64.b64decode(gif['data'])
    name, raw, mime = prepare_whatsapp(gif)
    assert name == 'animation.mp4' and mime == 'video/mp4'
    assert raw[4:8] == b'ftyp'


@pytest.mark.parametrize('provider', ['telegram', 'whatsapp'])
def test_gif_provider_dispatch_captions_replies(gif, provider):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'id': 'upload', 'messages': [{'id': 'wamid.test'}],
                                        'ok': True, 'result': {'message_id': 42}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = send(client, telegram() if provider == 'telegram' else whatsapp(),
                      {'destination': '1234', 'body': 'caption', 'reply_reference': '7', 'media': [gif]})
    assert result['status'] == 'accepted'
    if provider == 'telegram':
        assert requests[0].url.path.endswith('/sendAnimation')
        assert b'name="animation"' in requests[0].content
        assert b'caption' in requests[0].content and b'reply_parameters' in requests[0].content
    else:
        import json
        body = json.loads(requests[-1].content)
        assert body['type'] == 'video'
        assert body['video']['caption'] == 'caption' and body['context']['message_id'] == '7'


def test_invalid_gif_and_missing_codec(gif, monkeypatch):
    with pytest.raises(ValueError):
        prepare(dict(gif, data=base64.b64encode(b'broken').decode(), size=6))
    monkeypatch.setattr('app.media.subprocess.run', Mock(side_effect=FileNotFoundError()))
    with pytest.raises(MediaDependencyUnavailable):
        prepare_whatsapp(gif)


@pytest.mark.parametrize('status,body,result', [
    (200, {'success': True}, 'accepted'), (429, {}, 'retry'),
    (503, {}, 'retry'), (400, {}, 'rejected'), (401, {}, 'retry'),
])
def test_read_receipt_provider_results(status, body, result):
    import json
    def handler(request):
        assert json.loads(request.content) == {'messaging_product': 'whatsapp', 'status': 'read', 'message_id': 'wamid.1'}
        return httpx.Response(status, json=body)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert send_read_receipt(client, whatsapp(), 'wamid.1') == result


def test_read_receipt_restart_reports_acceptance_without_resend(tmp_path):
    store = Store('sqlite://' + str(tmp_path / 'queue.db'))
    store.migrate()
    payload = {'token': 'uuid', 'lease': 'lease', 'reference': 'wamid.1', 'provider': 'whatsapp', 'provider_account': '456'}
    cfg = config()
    cfg.sending_enabled = True
    odoo = Mock()
    odoo.call.side_effect = [payload, RuntimeError('Odoo outage'), dict(payload, lease='new'), True]
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={'success': True})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError):
            Worker(cfg, store, odoo, client).read_receipts('wa')
        Worker(cfg, Store(store.database_url) if hasattr(store, 'database_url') else store, odoo, client).read_receipts('wa')
    assert len(requests) == 1
    with pytest.raises(Conflict):
        store.persist_read_receipt('wa', dict(payload, reference='changed'))
    assert store.persist_read_receipt('other', payload)['result_status'] is None
