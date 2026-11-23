import base64
import hashlib
import json
from unittest.mock import Mock
from uuid import uuid4

import httpx
import pytest

from app.odoo import OdooUnavailable
from app.website import WebsiteWorker, send_reply
from app.website_media_protocol import check_bytes, validate_attachments
from app.storage import Store
from test_gateway import config
from test_website import website


def descriptor(raw=b'website media'):
    return {'id': 'file1', 'name': 'test.pdf', 'mimetype': 'application/pdf', 'kind': 'document',
            'size': len(raw), 'digest': hashlib.sha256(raw).hexdigest(), 'duration': 0}


@pytest.mark.parametrize('kind,mime,name', [('image', 'image/png', 'image.png'), ('voice', 'audio/webm', 'voice.webm'),
    ('audio', 'audio/mpeg', 'music.mp3'), ('video', 'video/mp4', 'video.mp4'), ('video', 'video/webm', 'video.webm'),
    ('document', 'application/pdf', 'file.pdf'), ('document', 'application/zip', 'archive.zip')])
def test_outgoing_media_uses_bounded_upload_before_receive(kind, mime, name):
    raw = b'website media'
    item = dict(descriptor(raw), kind=kind, mimetype=mime, name=name)
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.url.path.endswith('capabilities'):
            return httpx.Response(200, json={'version': 4})
        if request.url.path.endswith('/media'):
            assert request.content == raw
            assert json.loads(request.headers['X-Website-Media'])['attachment']['digest'] == item['digest']
            return httpx.Response(200, json={'digest': item['digest']})
        values = json.loads(request.content)
        assert 'data' not in values['attachments'][0]
        assert values['attachments'][0]['digest'] == item['digest']
        return httpx.Response(200, json={'reference': 'stable'})
    operation = {'token': 'stable', 'body': '', 'website_destination': {'kind': 'livechat', 'uuid': str(uuid4())},
                 'media': [{key: value for key, value in item.items() if key not in ('id', 'digest')} | {'data': base64.b64encode(raw).decode()}]}
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert send_reply(client, website(), operation)['status'] == 'accepted'
    assert [path.rsplit('/', 1)[1] for path in calls] == ['capabilities', 'media', 'receive']


@pytest.mark.parametrize('field,value', [('size', 0), ('size', 21 * 1024 * 1024), ('duration', float('nan')),
                                         ('id', '../file'), ('digest', 'bad'), ('kind', 'script')])
def test_rejects_malformed_media(field, value):
    item = descriptor()
    item[field] = value
    with pytest.raises(ValueError):
        validate_attachments([item])


def test_rejects_corruption_and_duplicates():
    item = descriptor()
    with pytest.raises(ValueError):
        check_bytes(item, b'corrupt')
    with pytest.raises(ValueError):
        validate_attachments([item, item])


def test_incoming_media_never_acknowledges_before_durable_delivery(tmp_path):
    cfg = config()
    cfg.accounts['web'] = website()
    queue = Store('sqlite://' + str(tmp_path / 'media.db'))
    queue.migrate()
    event = {'version': 4, 'source': cfg.accounts['web'].provider_account, 'event_uuid': str(uuid4()),
             'destination': {'kind': 'livechat', 'uuid': str(uuid4())}, 'attachments': [descriptor()], 'fingerprint': 'f' * 64}
    queue.ingest('web', [(event['event_uuid'], 'incoming', {'website_event': event, 'version': 4, 'sender': event['destination']['uuid']})])
    calls = []
    def respond(request):
        calls.append(request.url.path)
        if request.method == 'GET':
            return httpx.Response(200, content=b'website media')
        return httpx.Response(503)
    odoo = Mock()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        WebsiteWorker(cfg, queue, odoo, client, accounts=['web']).ingest()
    odoo.call.assert_not_called()
    assert not any(path.endswith('acknowledge') for path in calls)
    with queue.connect() as conn:
        assert conn.execute('SELECT state FROM incoming_event').fetchone()['state'] == 'pending'


def test_unsupported_peer_reports_media_unavailable():
    item = descriptor()
    operation = {'token': 'stable', 'body': '', 'website_destination': {'kind': 'livechat', 'uuid': str(uuid4())},
        'media': [{key: value for key, value in item.items() if key not in ('id', 'digest')} | {'data': base64.b64encode(b'website media').decode()}]}
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404))) as client:
        result = send_reply(client, website(), operation)
    assert result['status'] == 'review'
    assert result['website_failure'] == 'media_unavailable'


def test_outgoing_worker_fetches_binary_without_queue_base64(tmp_path):
    cfg = config()
    cfg.accounts['web'] = website()
    queue = Store('sqlite://' + str(tmp_path / 'outgoing-binary.db'))
    queue.migrate()
    item = descriptor()
    row = {'account': 'web', 'attempt': 1, 'receipt': 'durable', 'payload': {'token': 'stable', 'body': '',
        'website_destination': {'kind': 'livechat', 'uuid': str(uuid4())}, 'media': [item]}}
    paths = []
    def respond(request):
        paths.append(request.url.path)
        if request.method == 'GET':
            assert request.headers['Authorization'] == 'Bearer target-test-key'
            return httpx.Response(200, content=b'website media')
        if request.url.path.endswith('capabilities'):
            return httpx.Response(200, json={'version': 4})
        if request.url.path.endswith('/media'):
            return httpx.Response(200, json={'digest': item['digest']})
        assert 'data' not in json.loads(request.content)['attachments'][0]
        return httpx.Response(200, json={'reference': 'stable'})
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        worker = WebsiteWorker(cfg, queue, Mock(), client, accounts=['web'])
        assert worker._send_operation(row)['status'] == 'accepted'
    assert paths[0].startswith('/crm/website/v4/media/')
    assert 'data' not in row['payload']['media'][0]


def test_four_maximum_size_descriptors_and_five_file_rejection():
    files = [dict(descriptor(), id=str(index), size=20 * 1024 * 1024) for index in range(4)]
    assert validate_attachments(files) == files
    with pytest.raises(ValueError):
        validate_attachments(files + [dict(descriptor(), id='fifth')])


def test_incoming_acknowledges_only_after_all_binary_uploads_and_message(tmp_path):
    cfg = config()
    cfg.accounts['web'] = website()
    queue = Store('sqlite://' + str(tmp_path / 'incoming-binary.db'))
    queue.migrate()
    event = {'version': 4, 'source': cfg.accounts['web'].provider_account, 'event_uuid': str(uuid4()),
        'destination': {'kind': 'livechat', 'uuid': str(uuid4())}, 'fingerprint': 'f' * 64,
        'attachments': [descriptor(), dict(descriptor(), id='file2')]}
    queue.ingest('web', [(event['event_uuid'], 'incoming', {'website_event': event, 'version': 4, 'sender': event['destination']['uuid']})])
    order = []
    def respond(request):
        if request.method == 'GET':
            order.append('download')
            return httpx.Response(200, content=b'website media')
        if request.url.path.endswith('/media'):
            order.append('upload')
            return httpx.Response(200, json={'digest': descriptor()['digest']})
        order.append('acknowledge')
        return httpx.Response(200, json=True)
    odoo = Mock()
    def receive(*args, **kwargs):
        order.append('durable_message')
        return {'received': True, 'event_uuid': event['event_uuid']}
    odoo.call.side_effect = receive
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        WebsiteWorker(cfg, queue, odoo, client, accounts=['web']).ingest()
    assert order == ['download', 'upload', 'download', 'upload', 'durable_message', 'acknowledge']
