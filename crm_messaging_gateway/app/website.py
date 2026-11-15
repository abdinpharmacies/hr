import logging
import time

import httpx

from .config import settings
from .odoo import Odoo, OdooUnavailable
from .storage import Store
from .worker import Worker


def exchange(client, account, operation, **values):
    try:
        response = client.post(
            account.website_url.rstrip('/') + '/storefront-callcenter/v1/' + operation,
            headers={
                'Authorization': 'Bearer ' + account.token.get_secret_value(),
                'X-Odoo-Database': account.website_database,
            },
            json={'source': account.provider_account, **values},
        )
        if response.status_code != 200:
            raise OdooUnavailable('Website exchange unavailable')
        return response.json()
    except (httpx.HTTPError, ValueError):
        raise OdooUnavailable('Website exchange unavailable') from None


def send_reply(client, account, operation):
    try:
        result = exchange(
            client,
            account,
            'receive',
            order_uuid=operation['destination'],
            token=operation['token'],
            body=operation['body'],
        )
        if result != {'reference': operation['token']}:
            raise OdooUnavailable('Invalid website receipt')
        return {'status': 'accepted', 'reference': operation['token'], 'error': 'none'}
    except OdooUnavailable:
        return {'status': 'review', 'reference': '', 'error': 'ambiguous'}


class WebsiteWorker(Worker):
    def fetch(self, code):
        account = self.config.accounts[code]
        if not account.enabled:
            return
        events = exchange(self.client, account, 'fetch')
        if not isinstance(events, list) or len(events) > 50:
            raise ValueError('Invalid website event batch')
        rows = []
        for event in events:
            if (
                not isinstance(event, dict)
                or event.get('source') != account.provider_account
            ):
                raise ValueError('Invalid website source')
            rows.append(
                (
                    event['event_uuid'],
                    'incoming',
                    {'website_event': event, 'sender': event['order_uuid']},
                )
            )
        self.store.ingest(code, rows)

    def ingest(self):
        row = self.store.claim_incoming(self.accounts)
        if not row:
            return
        try:
            event = row['payload']['website_event']
            result = self.odoo.call(
                'receive_website_event', row['account'], event=event
            )
            if result != {'received': True, 'event_uuid': event['event_uuid']}:
                raise ValueError('Invalid destination receipt')
            acknowledged = exchange(
                self.client,
                self.config.accounts[row['account']],
                'acknowledge',
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

    def tick(self):
        for code in self.accounts:
            try:
                self.fetch(code)
            except Exception:
                logging.warning('Website fetch deferred')
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
