import logging
import urllib.request
import urllib.parse
import json

_logger = logging.getLogger(__name__)


def send_message(bot_token, chat_id, text):
    url = 'https://api.telegram.org/bot%s/sendMessage' % bot_token
    data = urllib.parse.urlencode({
        'chat_id': str(chat_id),
        'text': text,
        'parse_mode': 'HTML',
    }).encode()
    try:
        req = urllib.request.Request(url, data=data)
        resp = urllib.request.urlopen(req, timeout=15)
        result = json.loads(resp.read().decode())
        if result.get('ok'):
            _logger.info('Telegram message sent to chat %s', chat_id)
        else:
            _logger.warning('Telegram send failed: %s', result.get('description'))
    except Exception as e:
        _logger.error('Telegram send error: %s', e)


def get_updates(bot_token, offset=None, timeout=10):
    url = 'https://api.telegram.org/bot%s/getUpdates' % bot_token
    params = {'timeout': timeout}
    if offset:
        params['offset'] = offset
    url += '?' + urllib.parse.urlencode(params)
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=timeout + 5)
        result = json.loads(resp.read().decode())
        if result.get('ok'):
            return result.get('result', [])
        _logger.warning('Telegram getUpdates failed: %s', result.get('description'))
    except Exception as e:
        _logger.error('Telegram getUpdates error: %s', e)
    return []
