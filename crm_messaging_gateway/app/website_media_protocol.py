import hashlib
import math

LIMIT = 20 * 1024 * 1024


def validate_attachments(attachments):
    if not isinstance(attachments, list) or len(attachments) > 4:
        raise ValueError('Invalid website media')
    identities = set()
    for item in attachments:
        if not isinstance(item, dict) or set(item) != {'id', 'name', 'mimetype', 'size', 'digest', 'kind', 'duration'}:
            raise ValueError('Invalid website media')
        if (not isinstance(item['id'], str) or not 1 <= len(item['id']) <= 128
                or not item['id'].isascii() or not all(c.isalnum() or c in '_-' for c in item['id'])
                or item['id'] in identities or not isinstance(item['name'], str)
                or not 1 <= len(item['name']) <= 255 or '/' in item['name'] or '\\' in item['name']
                or not isinstance(item['mimetype'], str) or not 1 <= len(item['mimetype']) <= 128
                or any(c in item['mimetype'] for c in '\r\n')
                or type(item['size']) is not int or not 0 < item['size'] <= LIMIT
                or not isinstance(item['digest'], str) or len(item['digest']) != 64
                or any(c not in '0123456789abcdef' for c in item['digest'])
                or item['kind'] not in ('image', 'audio', 'voice', 'video', 'document')
                or type(item['duration']) not in (int, float) or not math.isfinite(item['duration'])
                or not 0 <= item['duration'] <= 300):
            raise ValueError('Invalid website media')
        if ((item['kind'] == 'image' and item['mimetype'] not in ('image/jpeg', 'image/png', 'image/gif', 'image/webp'))
                or (item['kind'] in ('voice', 'audio') and not item['mimetype'].startswith('audio/'))
                or (item['kind'] == 'video' and item['mimetype'] not in ('video/mp4', 'video/webm'))):
            raise ValueError('Invalid website media')
        identities.add(item['id'])
    return attachments


def check_bytes(item, raw):
    validate_attachments([item])
    if len(raw) != item['size'] or hashlib.sha256(raw).hexdigest() != item['digest']:
        raise ValueError('Invalid website media bytes')
    return raw
