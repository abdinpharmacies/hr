import json
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from PIL import Image


def validate_animation(raw, mime):
    if mime == 'image/gif':
        with Image.open(BytesIO(raw)) as image:
            if image.format != 'GIF' or image.width * image.height > 16777216:
                raise ValueError('Invalid GIF dimensions')
            duration = 0
            for index in range(image.n_frames):
                if index >= 9000 or (index + 1) * image.width * image.height > 500000000:
                    raise ValueError('GIF decoding exceeds limits')
                image.seek(index)
                image.load()
                duration += image.info.get('duration', 100) or 100
            if duration > 300000:
                raise ValueError('GIF exceeds five minutes')
        return
    if mime != 'video/mp4' or raw[4:8] != b'ftyp':
        raise ValueError('Invalid animation')
    with tempfile.TemporaryDirectory(prefix='crm-animation-') as directory:
        source = Path(directory) / 'source.mp4'
        source.write_bytes(raw)
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe', '-f', 'mov',
            '-show_entries', 'format=duration:stream=codec_type,codec_name,width,height',
            '-of', 'json', str(source),
        ], capture_output=True, timeout=15, check=True)
        details = json.loads(result.stdout)
        if not 0 < float(details['format']['duration']) <= 300:
            raise ValueError('Video exceeds five minutes')
        streams = details['streams']
        videos = [stream for stream in streams if stream.get('codec_type') == 'video']
        if len(videos) != 1 or not 0 < videos[0]['width'] * videos[0]['height'] <= 16777216:
            raise ValueError('Invalid video dimensions')
        if any(stream.get('codec_name') not in ('h264', 'aac') for stream in streams):
            raise ValueError('Unsupported video codec')
