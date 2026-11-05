import base64
import json
from pathlib import Path
import re
import subprocess
import tempfile

LIMIT = 20 * 1024 * 1024
MIMES = {
    'image/jpeg',
    'image/png',
    'image/webp',
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
    kind, source = next(
        (
            (kind, message[key])
            for key, kind in [
                ('photo', 'image'),
                ('document', 'document'),
                ('voice', 'voice'),
                ('audio', 'audio'),
            ]
            if message.get(key)
        ),
        (None, None),
    )
    if source is None:
        return None
    if kind == 'image':
        source = source[-1]
    mime = source.get(
        'mime_type',
        (
            'image/jpeg'
            if kind == 'image'
            else 'audio/ogg' if kind == 'voice' else 'application/octet-stream'
        ),
    )
    return {
        'kind': kind,
        'file_id': str(source['file_id']),
        'size': source.get('file_size', 0),
        'duration': source.get('duration', 0),
        'mimetype': mime,
        'name': Path(
            source.get('file_name')
            or (
                'image.jpg'
                if kind == 'image'
                else 'voice.ogg' if kind == 'voice' else 'attachment'
            )
        ).name[:255],
    }


def supported(metadata):
    return (
        metadata['mimetype'] in MIMES
        and 0
        <= metadata['size']
        <= (10 * 1024 * 1024 if metadata['kind'] == 'image' else LIMIT)
        and 0 <= metadata['duration'] <= 300
    )


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
