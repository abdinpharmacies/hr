import pytest

from app.media import attachment_diagnostic
from app.providers import normalize
from test_gateway import telegram, update


def event(**media):
    payload = update()
    del payload['message']['text']
    payload['message'].update(media)
    return normalize(telegram(), payload)[0][2]


def test_photo_uses_largest_downloadable_size():
    result = event(photo=[{'file_id': 'medium', 'file_size': 1000},
                          {'file_id': 'small', 'file_size': 200},
                          {'file_id': 'too-large', 'file_size': 11 * 1024 * 1024}])
    assert not result['unsupported']
    assert result['media']['file_id'] == 'medium'
    assert result['media']['kind'] == 'image'


def test_photo_missing_size_and_live_photo_still():
    assert event(photo=[{'file_id': 'photo'}])['media']['size'] == 0
    assert event(live_photo={'photo': [{'file_id': 'still'}]})['media']['file_id'] == 'still'


@pytest.mark.parametrize('mime', ['image/jpeg', 'image/png', 'image/webp'])
def test_image_sent_as_document_uses_image_validation(mime):
    result = event(document={'file_id': 'image-file', 'mime_type': mime, 'file_name': 'photo', 'file_size': 100})
    assert result['media']['kind'] == 'image'
    assert result['media']['mimetype'] == mime


def test_static_sticker_and_private_rejection_diagnostics(caplog):
    result = event(sticker={'file_id': 'sticker', 'is_animated': False, 'is_video': False, 'file_size': 100})
    assert result['media']['mimetype'] == 'image/webp'
    assert result['media']['name'] == 'sticker.webp'
    rejected = event(photo=[{'file_id': 'private-file-id', 'file_size': 11 * 1024 * 1024}])
    assert rejected['unsupported']
    assert 'file_size' in caplog.text
    assert 'private-file-id' not in caplog.text
    assert attachment_diagnostic({'document': {'file_name': 'private-name', 'file_id': 'private-id', 'mime_type': 'text/markdown'}}) == {'document': [{'mime_type': 'text/markdown'}]}


@pytest.mark.parametrize('mime', ['text/plain', 'text/markdown', 'text/x-markdown', 'application/octet-stream'])
def test_markdown_is_a_downloadable_document(mime):
    result = event(document={'file_id': 'markdown', 'file_name': 'notes.MD', 'mime_type': mime, 'file_size': 123})
    assert not result['unsupported']
    assert result['media']['kind'] == 'document'
    assert result['media']['mimetype'] == 'text/markdown'
    assert event(document={'file_id': 'exe', 'file_name': 'notes.MD', 'mime_type': 'application/x-msdownload', 'file_size': 123})['unsupported']


@pytest.mark.parametrize('flags,mime,name', [
    ({'is_animated': True}, 'application/x-tgsticker', 'sticker.tgs'),
    ({'is_video': True}, 'video/webm', 'sticker.webm'),
])
def test_animated_and_video_sticker_original_files(flags, mime, name):
    result = event(sticker=dict(flags, file_id='original-sticker', file_size=100))
    assert not result['unsupported']
    assert result['media']['kind'] == 'document'
    assert result['media']['file_id'] == 'original-sticker'
    assert result['media']['mimetype'] == mime
    assert result['media']['name'] == name


def test_markdown_worker_downloads_without_rendering():
    import base64
    import httpx
    from unittest.mock import Mock
    from app.worker import Worker
    from test_gateway import config
    payload = event(document={'file_id': 'markdown', 'file_name': 'notes.md', 'mime_type': 'text/plain', 'file_size': 16})
    raw = b'# Heading\n<script>untrusted</script>'
    store, odoo = Mock(), Mock()
    store.claim_incoming.return_value = {'id': 1, 'account': 'tg', 'kind': 'incoming', 'payload': payload}
    def respond(request):
        if request.url.path.endswith('/getFile'):
            return httpx.Response(200, json={'ok': True, 'result': {'file_path': 'documents/notes.md'}})
        return httpx.Response(200, content=raw)
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        Worker(config(), store, odoo, client).ingest()
    assert [call.args[0] for call in odoo.call.call_args_list] == ['receive_event', 'receive_media']
    assert odoo.call.call_args_list[1].kwargs['data'] == base64.b64encode(raw).decode()
    store.finish_incoming.assert_called_once_with(store.claim_incoming.return_value, True)
