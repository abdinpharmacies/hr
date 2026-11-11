import argparse
from datetime import datetime, timezone
import logging
import time

import httpx

from .config import settings
from .observability import logger
from .providers import normalize
from .storage import Store, Conflict
from .telegram_setup import configure, checked_response, TelegramVerificationError


class ReceiverStopped(Exception):
    pass


class ReceiverRetryable(Exception):
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
        try:
            data = checked_response(response)
        except TelegramVerificationError as error:
            if error.category in ('invalid_credentials', 'competing_receiver', 'active_webhook'):
                raise ReceiverStopped(error.category) from None
            raise ReceiverRetryable(error.category) from None
        updates = data.get('result')
        if not isinstance(updates, list):
            raise ReceiverStopped('malformed_event')
        events = []
        for update in updates:
            if not isinstance(update, dict):
                raise ReceiverStopped('malformed_event')
            update_id = update.get('update_id')
            if type(update_id) is not int or update_id < offset:
                raise ReceiverStopped('malformed_event')
            try:
                events.extend(normalize(self.account, update))
            except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
                raise ReceiverStopped('malformed_event') from None
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
            verified = False
            failures = 0
            while True:
                try:
                    if not verified:
                        identity = configure(self.client, self.account)
                        if identity['webhook_present']:
                            raise ReceiverStopped('active_webhook')
                        verified = True
                    self.tick(conn)
                    failures = 0
                except (ReceiverStopped, Conflict):
                    raise
                except Exception as error:
                    category = (
                        error.category if isinstance(error, TelegramVerificationError)
                        else 'network_failure' if isinstance(error, httpx.HTTPError)
                        else str(error) if isinstance(error, ReceiverRetryable)
                        else 'dependency_failure'
                    )
                    if category in ('invalid_credentials', 'identity_mismatch', 'competing_receiver', 'active_webhook'):
                        raise ReceiverStopped(category) from None
                    if conn.closed or conn.broken:
                        raise ReceiverRetryable('receiver_lock_lost') from None
                    conn.rollback()
                    failures += 1
                    if failures >= 8:
                        raise ReceiverRetryable(category) from None
                    logging.warning('Polling deferred category=%s attempt=%s/8', category, failures)
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
    except Conflict:
        parser.exit(78, 'receiver_or_event_conflict\n')
    except ReceiverStopped as error:
        parser.exit(78, str(error) + '\n')
    except ReceiverRetryable as error:
        parser.exit(75, 'Receiver retryable: ' + str(error) + '\n')
    except Exception:
        parser.exit(75, 'Receiver dependency unavailable; retry initialization.\n')


if __name__ == '__main__':
    main()
