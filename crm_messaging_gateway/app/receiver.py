import argparse
from datetime import datetime, timezone
import logging
import time

import httpx

from .config import settings
from .observability import logger
from .providers import normalize
from .storage import Store, Conflict
from .telegram_setup import configure


class ReceiverStopped(Exception):
    pass


class Receiver:
    def __init__(self, code, account, store, client):
        if (
            account.provider != 'telegram'
            or account.reception != 'polling'
            or not account.enabled
        ):
            raise ReceiverStopped('An enabled Telegram polling account is required')
        self.code, self.account, self.store, self.client = code, account, store, client

    def tick(self, conn):
        offset = self.store.polling_offset(conn, self.account.provider_account)
        response = self.client.post(
            'https://api.telegram.org/bot'
            + self.account.token.get_secret_value()
            + '/getUpdates',
            json={
                'offset': offset,
                'timeout': 30,
                'limit': 100,
                'allowed_updates': ['message', 'edited_message', 'message_reaction'],
            },
        )
        if response.status_code in (401, 403, 409):
            raise ReceiverStopped(
                'Bot unavailable or another receiver/webhook is active'
            )
        if response.status_code != 200:
            raise RuntimeError('Polling unavailable')
        data = response.json()
        updates = data.get('result')
        if data.get('ok') is not True or not isinstance(updates, list):
            raise RuntimeError('Invalid polling response')
        events = []
        for update in updates:
            update_id = update.get('update_id')
            if type(update_id) is not int or update_id < offset:
                raise ReceiverStopped('Invalid polling sequence')
            events.extend(normalize(self.account, update))
            offset = update_id + 1
        self.store.persist_poll(
            conn, self.code, self.account.provider_account, events, offset
        )
        timestamps = [
            (payload.get('edit') or {}).get('date', payload['timestamp'])
            for key, kind, payload in events if kind == 'incoming'
        ]
        if timestamps:
            latest = datetime.strptime(max(timestamps), '%Y-%m-%d %H:%M:%S').replace(
                tzinfo=timezone.utc
            )
            logger.info(
                'polling_lag_seconds=%.3f',
                max(0, datetime.now(timezone.utc).timestamp() - latest.timestamp()),
            )
        return len(updates)

    def run(self):
        with self.store.receiver(self.account.provider_account) as conn:
            identity = configure(self.client, self.account)
            if identity['webhook_present']:
                raise ReceiverStopped('Webhook is active; polling was not started')
            failures = 0
            while True:
                try:
                    self.tick(conn)
                    failures = 0
                except (ReceiverStopped, Conflict):
                    raise
                except Exception:
                    if conn.closed or conn.broken:
                        raise ReceiverStopped('Receiver lock connection lost') from None
                    conn.rollback()
                    failures += 1
                    if failures >= 8:
                        raise ReceiverStopped(
                            'Polling stopped after eight failures; inspect the queue and configuration'
                        ) from None
                    logging.warning('Polling deferred (%s/8)', failures)
                    time.sleep(min(60, 2**failures))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('account')
    args = parser.parse_args()
    try:
        config = settings()
    except RuntimeError:
        parser.exit(
            75,
            'Receiver credentials unavailable during startup; retry initialization.\n',
        )
    if args.account not in config.accounts:
        parser.error('Unknown account')
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    try:
        with httpx.Client(timeout=40, follow_redirects=False) as client:
            Receiver(
                args.account,
                config.accounts[args.account],
                Store(config.database_url.get_secret_value()),
                client,
            ).run()
    except (ReceiverStopped, Conflict) as error:
        parser.exit(78, str(error) + '\n')
    except Exception:
        parser.exit(75, 'Receiver dependency unavailable; retry initialization.\n')


if __name__ == '__main__':
    main()
