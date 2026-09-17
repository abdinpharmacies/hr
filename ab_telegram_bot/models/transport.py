"""Bot API transport: never expose request URLs, tokens, or raw error bodies."""
import json
import re
from urllib.parse import quote

import requests


class TelegramFailure(Exception):
    def __init__(self, kind, code=0, retry_after=0):
        super().__init__(kind)
        self.kind, self.code, self.retry_after = kind, code, retry_after


def request(token, method, payload, files=None):
    if not token:
        raise TelegramFailure('configuration')
    url = 'https://api.telegram.org/bot' + token + '/' + method
    data = {k: json.dumps(v) if isinstance(v, (dict, list, bool)) else v
            for k, v in payload.items() if v is not None}
    try:
        response = requests.post(url, data=data, files=files, timeout=(10, 60), allow_redirects=False)
    except requests.exceptions.ConnectTimeout:
        raise TelegramFailure('retry') from None
    except requests.exceptions.RequestException:
        # A connection/read failure can occur after Telegram accepted the request.
        raise TelegramFailure('unknown') from None
    try:
        body = response.json()
    except (ValueError, TypeError):
        raise TelegramFailure('unknown', response.status_code) from None
    if not isinstance(body, dict):
        raise TelegramFailure('unknown', response.status_code)
    if body.get('ok') is True:
        return body.get('result')
    code = int(body.get('error_code') or response.status_code)
    if code == 429:
        delay = (body.get('parameters') or {}).get('retry_after', 30)
        raise TelegramFailure('retry', code, max(1, int(delay)))
    if code >= 500:
        raise TelegramFailure('retry', code)
    raise TelegramFailure('rejected', code)


def download(token, path):
    if not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_./-]+', path) or '..' in path:
        raise TelegramFailure('configuration')
    try:
        with requests.get('https://api.telegram.org/file/bot' + token + '/' + quote(path, safe='/'),
                          timeout=(10, 60), stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise TelegramFailure('rejected', response.status_code)
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 20 * 1024 * 1024:
                    raise TelegramFailure('size')
                chunks.append(chunk)
            return b''.join(chunks)
    except requests.exceptions.RequestException:
        raise TelegramFailure('unknown') from None
