import logging
import re
import time
from uuid import UUID

import httpx

from .auth_config import auth_settings
from .config import settings
from .odoo import OdooUnavailable
from .providers import send
from .storage import Store


def exchange(client, source, source_id, operation, **values):
    try:
        response = client.post(
            source.url.rstrip('/') + '/ab_storefront/auth/exchange/v1/' + operation,
            headers={'Authorization': 'Bearer ' + source.token.get_secret_value(),
                     'X-Odoo-Database': source.database},
            json={'source': source_id, **values},
        )
        if response.status_code != 200:
            raise OdooUnavailable('Authentication exchange unavailable')
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise OdooUnavailable('Authentication exchange unavailable') from None


class AuthSendClient:
    def __init__(self, client, correlation):
        self.client = client
        self.correlation = correlation

    def post(self, url, **kwargs):
        payload = dict(kwargs['json'], biz_opaque_callback_data=self.correlation)
        return self.client.post(url, **dict(kwargs, json=payload))


class AuthWorker:
    def __init__(self, config, auth, store, client):
        self.config, self.auth, self.store, self.client = config, auth, store, client

    def deliver(self, source_id, source):
        account = self.config.accounts.get(source.account)
        if (not self.auth.enabled or not self.config.sending_enabled
                or not account or not account.enabled or not account.sending_enabled
                or account.provider != 'whatsapp' or account.provider_account != source.sender):
            return
        lease = exchange(self.client, source, source_id, 'lease')
        if not lease:
            return
        if (not isinstance(lease, dict) or set(lease) != {'delivery', 'lease'}
                or str(UUID(lease['delivery'])) != lease['delivery']
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', lease['lease'])):
            raise ValueError('Invalid authentication lease')
        job = exchange(self.client, source, source_id, 'dispatch', **lease)
        if not job:
            return
        if (job.get('delivery') != lease['delivery'] or job.get('sender') != source.sender
                or source.templates.get(job.get('language')) != job.get('template')
                or not re.fullmatch(r'[0-9]{6}', job.get('code', ''))
                or not re.fullmatch(r'[0-9]{7,15}', job.get('destination', ''))):
            exchange(self.client, source, source_id, 'report', **lease, status='rejected')
            return
        operation = {
            'destination': job['destination'], 'body': '', 'expires_at': job['expires_at'],
            'template': {'name': job['template'], 'language': {'code': job['language']},
                         'components': [
                             {'type': 'body', 'parameters': [{'type': 'text', 'text': job['code']}]},
                             {'type': 'button', 'sub_type': 'url', 'index': '0',
                              'parameters': [{'type': 'text', 'text': job['code']}]},
                         ]},
        }
        result = send(AuthSendClient(self.client, f"ab-auth:{source_id}:{lease['delivery']}"), account, operation)
        state = ('accepted' if result['status'] == 'accepted' else
                 'unknown' if result['status'] == 'review' else
                 'transient' if result.get('error') in ('unavailable', 'rate_limit') else 'rejected')
        exchange(self.client, source, source_id, 'report', **lease,
                 status=state, reference=result.get('reference', ''))

    def receipts(self):
        if not self.auth.enabled:
            return
        row = self.store.claim_incoming(['auth:' + key for key in self.auth.sources])
        if not row:
            return
        source_id = row['account'].removeprefix('auth:')
        try:
            exchange(self.client, self.auth.sources[source_id], source_id, 'status', **row['payload'])
        except OdooUnavailable:
            self.store.defer_incoming(row)
        except Exception:
            self.store.finish_incoming(row, False)
        else:
            self.store.finish_incoming(row, True)

    def tick(self):
        for source_id, source in self.auth.sources.items():
            try:
                self.deliver(source_id, source)
            except Exception:
                logging.warning('Authentication delivery cycle deferred')
        self.receipts()


def main():
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    config = settings(load_provider_tokens=False)
    auth = auth_settings()
    with httpx.Client(timeout=10, follow_redirects=False) as client:
        worker = AuthWorker(config, auth, Store(config.database_url.get_secret_value()), client)
        while True:
            try:
                worker.tick()
            except Exception:
                logging.warning('Authentication worker cycle deferred')
            time.sleep(1)


if __name__ == '__main__':
    main()
