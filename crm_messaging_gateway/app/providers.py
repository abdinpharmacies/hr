import hashlib
import hmac
import json
import logging
import math
from datetime import datetime, timezone

import httpx
from .media import attachment_diagnostic, telegram_media, supported, prepare, prepare_whatsapp, prepare_video


def verify_signature(account, raw, headers):
    if account.provider == 'whatsapp':
        expected = (
            'sha256='
            + hmac.new(
                account.webhook_secret.get_secret_value().encode(), raw, hashlib.sha256
            ).hexdigest()
        )
        supplied = headers.get('x-hub-signature-256', '')
    else:
        expected = account.webhook_secret.get_secret_value()
        supplied = headers.get('x-telegram-bot-api-secret-token', '')
    return hmac.compare_digest(expected.encode(), supplied.encode())


def identifier(value):
    if (
        not isinstance(value, (str, int))
        or isinstance(value, bool)
        or not 1 <= len(str(value)) <= 256
    ):
        raise ValueError('Invalid event identity')
    return str(value)


def timestamp(value):
    result = datetime.fromtimestamp(int(value), timezone.utc)
    if result.timestamp() > datetime.now(timezone.utc).timestamp() + 300:
        raise ValueError('Invalid event timestamp')
    return result.strftime('%Y-%m-%d %H:%M:%S')


def incoming(message_id, sender, body, date, unsupported, source):
    if not isinstance(body, str) or len(body) > 20000 or (not body and not unsupported):
        raise ValueError('Invalid message text')
    return {
        'id': identifier(message_id),
        'sender': identifier(sender),
        'body': body,
        'timestamp': timestamp(date),
        'unsupported': unsupported,
        'source_digest': hashlib.sha256(
            json.dumps(source, sort_keys=True).encode()
        ).hexdigest(),
    }


def provider_location(value, *, name=None, address=None, live=False):
    if not isinstance(value, dict):
        return None
    latitude, longitude = value.get('latitude'), value.get('longitude')
    if any(type(number) not in (int, float) or abs(number) > bound
           or not math.isfinite(number)
           for number, bound in ((latitude, 90), (longitude, 180))):
        return None
    name = value.get('name', '') if name is None else name
    address = value.get('address', '') if address is None else address
    if not isinstance(name, str) or not isinstance(address, str):
        return None
    return {'latitude': latitude, 'longitude': longitude,
            'name': name[:256], 'address': address[:1024],
            'is_live_snapshot': bool(live)}


def location_text(location):
    return '\n'.join(filter(None, [
        'Location snapshot' if location['is_live_snapshot'] else 'Location',
        location['name'], location['address'],
        f"{location['latitude']}, {location['longitude']}",
    ]))


def normalize(account, payload):
    if not isinstance(payload, dict):
        raise ValueError('Invalid webhook')
    if account.provider == 'telegram':
        update_id = identifier(payload['update_id'])
        reaction = payload.get('message_reaction')
        if reaction and reaction.get('chat', {}).get('type') == 'private':
            sender = identifier(reaction['chat']['id'])
            if identifier(reaction.get('user', {}).get('id')) != sender:
                raise ValueError('Reaction sender mismatch')
            emojis = [
                item['emoji']
                for item in reaction.get('new_reaction', [])
                if item.get('type') == 'emoji'
            ]
            event = incoming(
                'reaction:' + update_id,
                sender,
                'Reaction: ' + (' '.join(emojis) or 'removed'),
                reaction['date'],
                False,
                reaction,
            )
            event['reaction'] = ' '.join(emojis)[:64]
            event['reply_reference'] = identifier(reaction['message_id'])
            return [(update_id, 'incoming', event)]
        edited = 'edited_message' in payload
        message = payload.get('edited_message' if edited else 'message', {})
        if message.get('chat', {}).get('type') != 'private':
            return [
                (
                    update_id,
                    'ignored',
                    {
                        'reason': 'non_private_or_unsupported_update',
                        'source_digest': hashlib.sha256(
                            json.dumps(payload, sort_keys=True).encode()
                        ).hexdigest(),
                    },
                )
            ]
        sender = identifier(message['chat']['id'])
        if not sender.isdecimal():
            raise ValueError('Invalid private chat')
        if edited and identifier(message.get('from', {}).get('id')) != sender:
            raise ValueError('Edited message sender mismatch')
        contact = message.get('contact')
        media = telegram_media(message)
        if media and not supported(media):
            media = None
        venue = message.get('venue')
        location = (
            provider_location(venue.get('location'), name=venue.get('title', ''),
                              address=venue.get('address', ''))
            if isinstance(venue, dict) else provider_location(
                message.get('location'),
                live=bool((message.get('location') or {}).get('live_period'))
                if isinstance(message.get('location'), dict) else False,
            )
        )
        unsupported = 'text' not in message and contact is None and media is None and location is None
        event = incoming(
            'edit:' + update_id if edited else sender + ':' + identifier(message['message_id']),
            sender,
            (
                location_text(location) if location else 'Contact shared'
                if contact is not None
                else message.get(
                    'text', message.get('caption') or ('Attachment' if media else '')
                )
            ),
            message['date'],
            unsupported,
            message,
        )
        if edited:
            event['edit'] = {
                'reference': identifier(message['message_id']),
                'date': timestamp(message['edit_date']),
                'sequence': int(update_id),
            }
            if event['edit']['date'] < event['timestamp']:
                raise ValueError('Invalid edit timestamp')
        if unsupported:
            logging.warning('Unsupported Telegram attachment source=%s metadata=%s',
                            event['source_digest'], json.dumps(attachment_diagnostic(message), sort_keys=True))
        profile = message.get('from', {})
        event['profile'] = {
            'name': ' '.join(
                str(profile.get(k, '')) for k in ('first_name', 'last_name')
            ).strip()[:256],
            'username': str(profile.get('username', ''))[:256],
        }
        if location:
            event['location'] = location
        if media:
            event['media'] = media
        if message.get('reply_to_message'):
            event['reply_reference'] = identifier(
                message['reply_to_message']['message_id']
            )
        if contact is not None:
            if identifier(message.get('from', {}).get('id')) != sender:
                raise ValueError('Contact sender mismatch')
            phone = contact['phone_number']
            if not isinstance(phone, str) or not 1 <= len(phone) <= 64:
                raise ValueError('Invalid contact phone')
            event['contact'] = {
                'phone': phone,
                'user_id': (
                    identifier(contact['user_id']) if 'user_id' in contact else ''
                ),
                'sender_id': sender,
            }
        return [(update_id, 'incoming', event)]
    if payload.get('object') != 'whatsapp_business_account':
        raise ValueError('Invalid WhatsApp object')
    events = []
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            if change.get('field') != 'messages':
                continue
            value = change['value']
            if str(value['metadata']['phone_number_id']) != account.provider_account:
                raise ValueError('Provider account mismatch')
            for message in value.get('messages', []):
                location = provider_location(message.get('location')) if message.get('type') == 'location' else None
                unsupported = message.get('type') != 'text' and location is None
                event = incoming(
                    message['id'],
                    message['from'],
                    location_text(location) if location else '' if unsupported else message['text']['body'],
                    message['timestamp'],
                    unsupported,
                    message,
                )
                if location:
                    event['location'] = location
                events.append(('message:' + event['id'], 'incoming', event))
            for status in value.get('statuses', []):
                state = {
                    'sent': 'accepted',
                    'delivered': 'delivered',
                    'read': 'read',
                    'failed': 'failed',
                }.get(status['status'])
                if state:
                    event = {
                        'reference': identifier(status['id']),
                        'destination': identifier(status['recipient_id']),
                        'status': state,
                    }
                    key = ':'.join(
                        (
                            'status',
                            event['reference'],
                            state,
                            identifier(status['timestamp']),
                        )
                    )
                    events.append((key, 'status', event))
    if not events:
        events.append(
            (
                'ignored:'
                + hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest(),
                'ignored',
                {'reason': 'unsupported_event'},
            )
        )
    return events


def send(client, account, operation):
    venue = operation.get('location')
    if 'location' in operation:
        valid = provider_location(venue)
        if (
            account.provider != 'telegram' or not account.location_enabled
            or not valid or not isinstance(venue, dict)
            or set(venue) != {'latitude', 'longitude', 'name', 'address'}
            or not valid['name'].strip() or not valid['address'].strip()
            or len(venue['name']) > 256 or len(venue['address']) > 1024
            or any(operation.get(key) for key in ('media', 'reaction', 'template', 'contact_button'))
        ):
            return {'status': 'failed', 'reference': '', 'error': 'rejected'}
    if operation.get('expires_at'):
        deadline = datetime.strptime(
            operation['expires_at'], '%Y-%m-%d %H:%M:%S'
        ).replace(tzinfo=timezone.utc)
        if deadline.timestamp() <= datetime.now(timezone.utc).timestamp() + 30:
            return {'status': 'failed', 'reference': '', 'error': 'window'}
    if account.provider == 'whatsapp':
        url = f'https://graph.facebook.com/{account.graph_version}/{account.provider_account}/messages'
        headers = {'Authorization': 'Bearer ' + account.token.get_secret_value()}
        payload = {
            'messaging_product': 'whatsapp',
            'to': operation['destination'],
            'type': 'text',
            'text': {'body': operation['body'], 'preview_url': False},
        }
        if operation.get('template'):
            payload.pop('text')
            payload.update(type='template', template=operation['template'])
        elif operation.get('reaction'):
            payload.pop('text')
            payload.update(
                type='reaction',
                reaction={
                    'message_id': operation['reply_reference'],
                    'emoji': operation['reaction'],
                },
            )
        elif operation.get('media'):
            media = operation['media'][0]
            try:
                filename, raw, mime = prepare_whatsapp(media)
                kind = 'audio' if media['kind'] == 'voice' else media['kind']
                limit = (
                    (5 if kind == 'image' else 16 if kind in ('audio', 'video') else 20)
                    * 1024
                    * 1024
                )
                if (
                    len(raw) > limit
                    or (kind == 'image' and mime not in ('image/jpeg', 'image/png'))
                    or mime in ('audio/webm', 'video/webm')
                ):
                    raise ValueError('Unsupported WhatsApp media')
            except Exception:
                return {'status': 'failed', 'reference': '', 'error': 'media'}
            try:
                upload = client.post(
                    url.rsplit('/', 1)[0] + '/media',
                    headers=headers,
                    data={'messaging_product': 'whatsapp', 'type': mime},
                    files={'file': (filename, raw, mime)},
                )
                if upload.status_code >= 500 or upload.status_code == 429:
                    return {'status': 'failed', 'reference': '', 'error': 'unavailable'}
                if upload.status_code != 200:
                    return {'status': 'failed', 'reference': '', 'error': 'media'}
                media_id = identifier(upload.json()['id'])
            except httpx.HTTPError:
                return {'status': 'failed', 'reference': '', 'error': 'unavailable'}
            except (ValueError, KeyError, TypeError):
                return {'status': 'failed', 'reference': '', 'error': 'media'}
            payload.pop('text')
            payload.update(type=kind)
            payload[kind] = {'id': media_id}
            if kind in ('image', 'document', 'video'):
                payload[kind]['caption'] = operation['body']
            if kind == 'document':
                payload[kind]['filename'] = filename
        if operation.get('reply_reference') and not operation.get('reaction'):
            payload['context'] = {'message_id': operation['reply_reference']}
    else:
        url = (
            'https://api.telegram.org/bot'
            + account.token.get_secret_value()
            + '/sendMessage'
        )
        headers = {}
        payload = {
            'chat_id': operation['destination'],
            'text': operation['body'],
            'link_preview_options': {'is_disabled': True},
        }
        if operation.get('contact_button'):
            payload['reply_markup'] = {
                'keyboard': [
                    [{'text': operation['contact_button'], 'request_contact': True}]
                ],
                'resize_keyboard': True,
                'one_time_keyboard': True,
            }
    files = None
    if account.provider == 'telegram':
        if operation.get('reply_reference'):
            payload['reply_parameters'] = {
                'message_id': int(operation['reply_reference'])
            }
        if venue:
            url = url.rsplit('/', 1)[0] + '/sendVenue'
            payload = {
                'chat_id': operation['destination'],
                'latitude': venue['latitude'], 'longitude': venue['longitude'],
                'title': venue['name'], 'address': venue['address'],
            }
            if operation.get('reply_reference'):
                payload['reply_parameters'] = {'message_id': int(operation['reply_reference'])}
        elif operation.get('reaction'):
            url = url.rsplit('/', 1)[0] + '/setMessageReaction'
            payload = {
                'chat_id': operation['destination'],
                'message_id': int(operation['reply_reference']),
                'reaction': [{'type': 'emoji', 'emoji': operation['reaction']}],
            }
        elif operation.get('media'):
            media = operation['media'][0]
            method, field = {
                'image': ('sendPhoto', 'photo'),
                'document': ('sendDocument', 'document'),
                'audio': ('sendAudio', 'audio'),
                'voice': ('sendVoice', 'voice'),
                'video': ('sendVideo', 'video'),
            }[media['kind']]
            try:
                files = {field: prepare_video(media) if media['kind'] == 'video' else prepare(media)}
            except Exception:
                return {'status': 'failed', 'reference': '', 'error': 'media'}
            url = url.rsplit('/', 1)[0] + '/' + method
            payload = {
                'chat_id': operation['destination'],
                'caption': operation['body'],
            }
            if operation.get('reply_reference'):
                payload['reply_parameters'] = json.dumps(
                    {'message_id': int(operation['reply_reference'])}
                )
    try:
        response = (
            client.post(url, headers=headers, data=payload, files=files)
            if files
            else client.post(url, headers=headers, json=payload)
        )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
        return {
            'status': 'failed',
            'reference': '',
            'error': 'unavailable',
            'retry_after': 30,
        }
    except httpx.HTTPError:
        return {'status': 'review', 'reference': '', 'error': 'ambiguous'}
    try:
        data = response.json()
        if response.status_code == 200:
            if account.provider == 'telegram':
                if data.get('ok') is not True:
                    raise ValueError('No acceptance evidence')
                reference = (
                    identifier(operation['reply_reference'])
                    if operation.get('reaction') and data.get('result') is True
                    else identifier(data['result']['message_id'])
                )
            else:
                reference = identifier(data['messages'][0]['id'])
            return {'status': 'accepted', 'reference': reference, 'error': 'none'}
        if response.status_code == 429:
            retry_after = data.get('parameters', {}).get(
                'retry_after', response.headers.get('Retry-After', 30)
            )
            return {
                'status': 'failed',
                'reference': '',
                'error': 'rate_limit',
                'retry_after': max(1, min(int(retry_after), 86400)),
            }
        if 400 <= response.status_code < 500 and response.status_code != 408:
            return {'status': 'failed', 'reference': '', 'error': 'rejected'}
    except (ValueError, KeyError, TypeError, IndexError):
        pass
    return {'status': 'review', 'reference': '', 'error': 'ambiguous'}
