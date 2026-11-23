import base64
import hashlib
import json
import logging
import time
from uuid import UUID

import httpx

from .config import settings
from .odoo import Odoo, OdooUnavailable
from .storage import Conflict, Store
from .worker import Worker
from .website_media_protocol import check_bytes, validate_attachments


class WebsiteChatUnavailable(OdooUnavailable):
    pass


class WebsiteExchangeError(OdooUnavailable):
    def __init__(self, category):
        self.category = category
        super().__init__('Website exchange unavailable')


def exchange(client, account, operation, version=1, **values):
    try:
        response = client.post(
            account.website_url.rstrip('/') + f'/storefront-callcenter/v{version}/' + operation,
            headers={
                'Authorization': 'Bearer ' + account.token.get_secret_value(),
                'X-Odoo-Database': account.website_database,
            },
            json={'source': account.provider_account, **values},
        )
        if version == 4 and operation == 'capabilities' and response.status_code == 404:
            return {'version': 0}
        if version > 1 and operation == 'fetch' and response.status_code == 404:
            raise WebsiteChatUnavailable('Website chat exchange is not installed')
        if response.status_code != 200:
            category = ('authentication' if response.status_code in (401, 403) else
                        'ended' if response.status_code == 410 else
                        'transient' if response.status_code in (404, 408, 409, 425, 429) or response.status_code >= 500 else
                        'validation')
            raise WebsiteExchangeError(category)
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise WebsiteExchangeError('transient') from None


def upload_media(client, url, database, token, path, metadata, raw):
    try:
        response = client.post(url.rstrip('/') + path, headers={
            'Authorization': 'Bearer ' + token, 'X-Odoo-Database': database,
            'Content-Type': 'application/octet-stream', 'X-Website-Media': json.dumps(metadata, ensure_ascii=True),
        }, content=raw)
        if response.status_code != 200:
            category = 'authentication' if response.status_code in (401, 403) else 'transient' if response.status_code >= 500 or response.status_code in (408, 409, 425, 429) else 'validation'
            raise WebsiteExchangeError(category)
        if response.json() != {'digest': metadata['attachment']['digest']}:
            raise OdooUnavailable('Invalid website media receipt')
    except (httpx.HTTPError, ValueError):
        raise OdooUnavailable('Website media upload unavailable') from None


def send_reply(client, account, operation):
    try:
        destination = operation.get('website_destination')
        if not isinstance(destination, dict) or set(destination) != {'kind', 'uuid'} or destination['kind'] not in ('order', 'livechat'):
            return {'status': 'review', 'reference': '', 'error': 'ambiguous'}
        try:
            if str(UUID(destination['uuid'])) != destination['uuid']:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            return {'status': 'review', 'reference': '', 'error': 'ambiguous'}
        media = operation.get('media') or []
        descriptors = []
        if not isinstance(media, list) or len(media) > 4:
            return {'status': 'review', 'reference': '', 'error': 'media', 'website_failure': 'validation'}
        if media:
            try:
                capable = exchange(client, account, 'capabilities', version=4) == {'version': 4}
            except WebsiteExchangeError as error:
                if error.category == 'transient':
                    raise
                capable = False
            if not capable:
                return {'status': 'review', 'reference': '', 'error': 'media', 'website_failure': 'media_unavailable'}
            for index, item in enumerate(media):
                if not isinstance(item.get('data'), str) or len(item['data']) > 28 * 1024 * 1024:
                    raise ValueError('Invalid website media size')
                raw = base64.b64decode(item['data'], validate=True)
                descriptor = {key: item[key] for key in ('name', 'mimetype', 'size', 'kind')}
                descriptor.update(id=str(index), digest=hashlib.sha256(raw).hexdigest(), duration=item.get('duration', 0))
                check_bytes(descriptor, raw)
                descriptors.append(descriptor)
                upload_media(client, account.website_url, account.website_database, account.token.get_secret_value(),
                    '/storefront-callcenter/v4/media',
                    {'source': account.provider_account, 'kind': destination['kind'], 'destination': destination['uuid'],
                     'token': operation['token'], 'attachment': descriptor}, raw)
        result = exchange(
            client,
            account,
            'receive',
            version=4 if media else 2,
            **({'attachments': descriptors} if media else {}),
            destination_kind=destination['kind'],
            destination_uuid=destination['uuid'],
            token=operation['token'],
            body=operation['body'],
        )
        if result != {'reference': operation['token']}:
            raise OdooUnavailable('Invalid website receipt')
        return {'status': 'accepted', 'reference': operation['token'], 'error': 'none'}
    except (ValueError, KeyError, TypeError):
        return {'status': 'review', 'reference': '', 'error': 'media', 'website_failure': 'validation'}
    except WebsiteExchangeError as error:
        return {'status': 'failed' if error.category == 'transient' else 'review',
                'reference': '', 'error': {'transient': 'unavailable', 'authentication': 'rejected',
                                         'validation': 'rejected', 'ended': 'rejected'}[error.category],
                'website_failure': error.category}
    except OdooUnavailable:
        return {'status': 'failed', 'reference': '', 'error': 'unavailable', 'website_failure': 'uncertain'}


class WebsiteWorker(Worker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_unavailable = {}
        self.lifecycle_capability = {}

    def fetch(self, code):
        account = self.config.accounts[code]
        if not account.enabled:
            return
        now = time.monotonic()
        capability = self.lifecycle_capability.get(code)
        if capability is None or now >= capability[1]:
            try:
                result = self.odoo.call('website_capabilities', code)
                supported = result.get('version', 0) if isinstance(result, dict) else 0
                if type(supported) is not int or supported not in (3, 4):
                    supported = 0
            except Exception:
                supported = 0
            self.lifecycle_capability[code] = (supported, now + 60)
        capability_version = self.lifecycle_capability[code][0]
        for version in ((1, 3, 4, 2) if capability_version >= 4 else (1, 3, 2) if capability_version >= 3 else (1, 2)):
            if version > 1 and time.monotonic() < self.chat_unavailable.get((code, version), 0):
                continue
            try:
                events = exchange(self.client, account, 'fetch', version=version)
                self._store_events(code, events, version)
                if version > 1:
                    self.chat_unavailable.pop((code, version), None)
            except WebsiteChatUnavailable:
                self.chat_unavailable[(code, version)] = time.monotonic() + 60
            except Exception:
                logging.warning('Website fetch deferred account=%s version=%s', code, version)

    def _store_events(self, code, events, version):
        account = self.config.accounts[code]
        if not isinstance(events, list) or len(events) > 50:
            raise ValueError('Invalid website event batch')
        rows = []
        for event in events:
            try:
                if not isinstance(event, dict) or event.get('source') != account.provider_account:
                    raise ValueError('Invalid website source')
                key = event['event_uuid']
                if not isinstance(key, str) or str(UUID(key)) != key:
                    raise ValueError('Invalid website event')
                sender = event['order_uuid'] if version == 1 else event['destination']['uuid']
                if not isinstance(sender, str) or str(UUID(sender)) != sender:
                    raise ValueError('Invalid website destination')
                if version == 3 and event['destination']['kind'] == 'livechat':
                    sender += ':lifecycle'
                payload = {'website_event': event, 'sender': sender}
                if version > 1:
                    payload['version'] = version
            except (ValueError, TypeError, KeyError, AttributeError):
                digest = hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
                key = 'invalid:' + digest
                payload = {'website_event': event, 'sender': key, 'review_reason': 'invalid_website_event'}
            rows.append((key, 'incoming', payload))
        for row in rows:
            try:
                self.store.ingest(code, [row])
            except Conflict:
                digest = hashlib.sha256(json.dumps(row[2], sort_keys=True).encode()).hexdigest()
                self.store.ingest(code, [('conflict:' + digest, 'incoming', dict(row[2], review_reason='conflicting_website_event'))])

    def ingest(self):
        row = self.store.claim_incoming(self.accounts)
        if not row:
            return
        try:
            event = row['payload']['website_event']
            if event.get('version') == 4:
                self.transfer_media(row['account'], event)
            result = self.odoo.call(
                {1: 'receive_website_event', 2: 'receive_website_chat', 3: 'receive_website_lifecycle', 4: 'receive_website_chat'}[row['payload'].get('version', 1)], row['account'], event=event
            )
            if result != {'received': True, 'event_uuid': event['event_uuid']}:
                raise ValueError('Invalid destination receipt')
            acknowledged = exchange(
                self.client,
                self.config.accounts[row['account']],
                'acknowledge',
                version=row['payload'].get('version', 1),
                event_uuid=event['event_uuid'],
                fingerprint=event['fingerprint'],
            )
            if acknowledged is not True:
                raise OdooUnavailable('Invalid website acknowledgement')
        except OdooUnavailable:
            self.store.defer_incoming(row)
            return
        except Exception:
            self.store.finish_incoming(row, False)
            return
        self.store.finish_incoming(row, True)

    def _send_operation(self, row):
        from urllib.parse import quote
        account = self.config.accounts[row['account']]
        operation = dict(row['payload'])
        try:
            media = operation.get('media') or []
            if media and all('data' not in item for item in media):
                validate_attachments(media)
                downloaded = []
                for item in media:
                    path = '/crm/website/v4/media/' + quote(row['account'], safe='') + '/' + quote(operation['token'], safe='') + '/' + item['id']
                    with self.client.stream('GET', self.config.odoo_url.rstrip('/') + path, headers={
                        'Authorization': 'Bearer ' + (account.odoo_key or self.config.odoo_key).get_secret_value(),
                        'X-Odoo-Database': self.config.odoo_database,
                    }, params={'provider_account': account.provider_account, 'attempt': row['attempt'], 'receipt': row['receipt']}) as response:
                        if response.status_code != 200:
                            category = 'transient' if response.status_code >= 500 or response.status_code in (408, 429) else 'validation'
                            raise WebsiteExchangeError(category)
                        raw = bytearray()
                        for chunk in response.iter_bytes():
                            raw.extend(chunk)
                            if len(raw) > item['size']:
                                raise ValueError('Website media exceeds declared size')
                    check_bytes(item, raw)
                    downloaded.append({key: value for key, value in item.items() if key not in ('id', 'digest')} |
                        {'data': base64.b64encode(raw).decode()})
                operation['media'] = downloaded
            return send_reply(self.client, account, operation)
        except (ValueError, TypeError, KeyError):
            return {'status': 'review', 'reference': '', 'error': 'media', 'website_failure': 'validation'}
        except WebsiteExchangeError as error:
            return {'status': 'failed' if error.category == 'transient' else 'review',
                'reference': '', 'error': 'unavailable' if error.category == 'transient' else 'media', 'website_failure': error.category}
        except (httpx.HTTPError, OdooUnavailable):
            return {'status': 'failed', 'reference': '', 'error': 'unavailable', 'website_failure': 'transient'}

    def transfer_media(self, code, event):
        account = self.config.accounts[code]
        for item in validate_attachments(event['attachments']):
            url = account.website_url.rstrip('/') + f"/storefront-callcenter/v4/media/{account.provider_account}/{event['event_uuid']}/{item['id']}"
            with self.client.stream('GET', url, headers={
                'Authorization': 'Bearer ' + account.token.get_secret_value(), 'X-Odoo-Database': account.website_database,
            }) as response:
                if response.status_code != 200:
                    raise OdooUnavailable('Website media unavailable')
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > item['size']:
                        raise ValueError('Website media exceeds declared size')
            check_bytes(item, raw)
            upload_media(self.client, self.config.odoo_url, self.config.odoo_database,
                (account.odoo_key or self.config.odoo_key).get_secret_value(), '/crm/website/v4/media',
                {'account_code': code, 'provider_account': account.provider_account,
                 'event_uuid': event['event_uuid'], 'attachment': item}, bytes(raw))

    def tick(self):
        self.store.recover_website_sending(self.accounts)
        for code in self.accounts:
            try:
                self.fetch(code)
            except Exception:
                logging.warning('Website fetch deferred account=%s', code)
        super().tick()

    def read_receipts(self, code):
        return


def main():
    config = settings(load_provider_tokens=False)
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    accounts = [
        code
        for code, account in config.accounts.items()
        if account.provider == 'website' and account.enabled
    ]
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        worker = WebsiteWorker(
            config,
            Store(config.database_url.get_secret_value()),
            Odoo(config, client),
            client,
            accounts=accounts,
        )
        while True:
            try:
                worker.tick()
            except Exception:
                logging.warning('Website worker cycle deferred')
            time.sleep(2)


if __name__ == '__main__':
    main()
