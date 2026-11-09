import base64
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile

LIMIT = 20 * 1024 * 1024
MIMES = {
    'image/jpeg',
    'image/png',
    'image/webp',
    'text/markdown',
    'application/x-tgsticker',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'audio/ogg',
    'audio/mpeg',
    'audio/mp4',
    'audio/webm',
    'video/webm',
}


def telegram_media(message):
    photos = message.get('photo')
    live_photo = message.get('live_photo')
    if not photos and isinstance(live_photo, dict):
        photos = live_photo.get('photo')
    if isinstance(photos, list) and photos:
        candidates = [
            photo for photo in photos
            if isinstance(photo, dict)
            and isinstance(photo.get('file_id'), str)
            and type(photo.get('file_size', 0)) is int
            and 0 <= photo.get('file_size', 0) <= 10 * 1024 * 1024
        ]
        if not candidates:
            return None
        source = max(
            enumerate(candidates),
            key=lambda item: (item[1].get('file_size', 0), item[0]),
        )[1]
        kind, mime, name = 'image', 'image/jpeg', 'image.jpg'
    elif isinstance(message.get('sticker'), dict):
        source = message['sticker']
        if source.get('is_animated'):
            kind, mime, name = 'document', 'application/x-tgsticker', 'sticker.tgs'
        elif source.get('is_video'):
            kind, mime, name = 'document', 'video/webm', 'sticker.webm'
        else:
            kind, mime, name = 'image', 'image/webp', 'sticker.webp'
    else:
        kind, source = next(
            ((kind, message[key]) for key, kind in
             [('document', 'document'), ('voice', 'voice'), ('audio', 'audio')]
             if isinstance(message.get(key), dict)),
            (None, None),
        )
        if source is None:
            return None
        mime = source.get('mime_type') or ('audio/ogg' if kind == 'voice' else 'application/octet-stream')
        name = source.get('file_name') or ('voice.ogg' if kind == 'voice' else 'attachment')
        if kind == 'document' and mime in ('image/jpeg', 'image/png', 'image/webp'):
            kind = 'image'
        elif (
            kind == 'document'
            and isinstance(name, str)
            and Path(name).suffix.lower() in ('.md', '.markdown')
            and mime in ('text/plain', 'text/markdown', 'text/x-markdown', 'application/octet-stream')
        ):
            mime = 'text/markdown'
    if not isinstance(source.get('file_id'), str) or not isinstance(name, str):
        return None
    return {
        'kind': kind,
        'file_id': source['file_id'],
        'size': source.get('file_size', 0),
        'duration': source.get('duration', 0),
        'mimetype': mime,
        'name': Path(name).name[:255],
    }


def supported(metadata):
    size, duration = metadata.get('size'), metadata.get('duration', 0)
    return (
        metadata.get('mimetype') in MIMES
        and type(size) is int
        and 0 <= size <= (10 * 1024 * 1024 if metadata.get('kind') == 'image' else LIMIT)
        and type(duration) in (int, float)
        and 0 <= duration <= 300
        and math.isfinite(duration)
    )


def attachment_diagnostic(message):
    kinds = ('photo', 'live_photo', 'document', 'sticker', 'animation', 'video', 'voice', 'audio')
    result = {}
    for kind in kinds:
        value = message.get(kind)
        if value is None:
            continue
        values = value[:10] if isinstance(value, list) else [value]
        result[kind] = [
            {key: item[key] for key in ('file_size', 'mime_type', 'duration', 'is_animated', 'is_video')
             if key in item and type(item[key]) in (int, float, bool, str)
             and (not isinstance(item[key], str) or len(item[key]) <= 80)}
            if isinstance(item, dict) else {'type': type(item).__name__}
            for item in values
        ]
    return result


def download(client, account, metadata):
    if not supported(metadata):
        raise ValueError('Media exceeds supported limits')
    origin = 'https://api.telegram.org/'
    token = account.token.get_secret_value()
    response = client.post(
        origin + 'bot' + token + '/getFile', json={'file_id': metadata['file_id']}
    )
    response.raise_for_status()
    result = response.json()
    path = result.get('result', {}).get('file_path', '')
    if (
        not result.get('ok')
        or not re.fullmatch(r'[a-zA-Z0-9_./-]+', path)
        or '..' in path
        or path.startswith('/')
    ):
        raise ValueError('Invalid provider file path')
    limit = 10 * 1024 * 1024 if metadata['kind'] == 'image' else LIMIT
    raw = bytearray()
    with client.stream('GET', origin + 'file/bot' + token + '/' + path) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            raw.extend(chunk)
            if len(raw) > limit:
                raise ValueError('Media exceeds supported limits')
    return base64.b64encode(raw).decode()


def prepare(metadata):
    if not supported(metadata):
        raise ValueError('Media exceeds supported limits')
    encoded = metadata.get('data', '')
    if not isinstance(encoded, str) or len(encoded) > LIMIT * 4 // 3 + 8:
        raise ValueError('Invalid media')
    raw = base64.b64decode(encoded, validate=True)
    if not raw or len(raw) != metadata['size']:
        raise ValueError('Invalid media')
    if metadata['kind'] not in ('voice', 'audio'):
        return metadata['name'], raw, metadata['mimetype']
    with tempfile.TemporaryDirectory(prefix='crm-media-') as directory:
        source = Path(directory) / 'source'
        source.write_bytes(raw)
        demuxer = {
            'audio/webm': 'matroska',
            'video/webm': 'matroska',
            'audio/ogg': 'ogg',
            'audio/mpeg': 'mp3',
            'audio/mp4': 'mov',
        }[metadata['mimetype']]
        probe = subprocess.run(
            [
                'ffprobe',
                '-protocol_whitelist',
                'file,pipe',
                '-f',
                demuxer,
                '-v',
                'error',
                '-show_entries',
                'format=duration',
                '-of',
                'json',
                str(source),
            ],
            capture_output=True,
            timeout=15,
            check=True,
        )
        duration = float(json.loads(probe.stdout)['format']['duration'])
        if not 0 < duration <= 300:
            raise ValueError('Recording exceeds five minutes')
        if metadata['kind'] == 'voice':
            target = Path(directory) / 'voice.ogg'
            subprocess.run(
                [
                    'ffmpeg',
                    '-nostdin',
                    '-protocol_whitelist',
                    'file,pipe',
                    '-f',
                    demuxer,
                    '-v',
                    'error',
                    '-i',
                    str(source),
                    '-vn',
                    '-c:a',
                    'libopus',
                    '-b:a',
                    '32k',
                    str(target),
                ],
                capture_output=True,
                timeout=30,
                check=True,
            )
            return 'voice.ogg', target.read_bytes(), 'audio/ogg'
        return metadata['name'], raw, metadata['mimetype']


def _prepare_extended_attachment(metadata):
    mime = metadata['mimetype']
    extra_documents = {
        'text/plain',
        'application/vnd.ms-excel',
        'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    }
    if mime not in extra_documents | {'video/mp4', 'video/3gpp'}:
        return prepare(metadata)
    kind = metadata['kind']
    limit = (16 if kind == 'video' else 20) * 1024 * 1024
    encoded = metadata.get('data', '')
    if not isinstance(encoded, str) or len(encoded) > limit * 4 // 3 + 8:
        raise ValueError('Invalid media')
    raw = base64.b64decode(encoded, validate=True)
    if not 0 < len(raw) <= limit or len(raw) != metadata['size']:
        raise ValueError('Invalid media')
    if mime.startswith('video/'):
        if kind != 'video' or raw[4:8] != b'ftyp':
            raise ValueError('Invalid video')
        with tempfile.TemporaryDirectory(prefix='crm-video-') as directory:
            source = Path(directory) / 'source'
            source.write_bytes(raw)
            probe = subprocess.run(
                [
                    'ffprobe',
                    '-protocol_whitelist',
                    'file,pipe',
                    '-f',
                    'mov',
                    '-v',
                    'error',
                    '-show_entries',
                    'stream=codec_type,codec_name',
                    '-of',
                    'json',
                    str(source),
                ],
                capture_output=True,
                timeout=15,
                check=True,
            )
            streams = json.loads(probe.stdout)['streams']
            if not any(
                s['codec_type'] == 'video' and s['codec_name'] == 'h264'
                for s in streams
            ) or any(
                s.get('codec_type') not in ('video', 'audio')
                or s.get('codec_name') not in ('h264', 'aac')
                for s in streams
            ):
                raise ValueError('Unsupported video codecs')
    elif kind != 'document':
        raise ValueError('Invalid document')
    return metadata['name'], raw, mime


def prepare_whatsapp(metadata):
    return _prepare_extended_attachment(metadata)


def prepare_video(metadata):
    if metadata.get('kind') != 'video' or metadata.get('mimetype') != 'video/mp4':
        raise ValueError('Invalid video')
    return _prepare_extended_attachment(metadata)
