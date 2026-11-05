import argparse
import json
import logging
from urllib.parse import urlsplit

import httpx

from .config import settings


def configure(client, account, webhook_url=None, polling=False, expected_webhook=None):
    if account.provider != 'telegram':
        raise ValueError('Select a Telegram account')
    origin = 'https://api.telegram.org/bot' + account.token.get_secret_value()
    try:
        response = client.post(origin + '/getMe')
        data = response.json()
        identity = data.get('result', {})
        if (
            response.status_code != 200
            or data.get('ok') is not True
            or identity.get('is_bot') is not True
            or str(identity.get('id')) != account.provider_account
        ):
            raise ValueError('Bot identity verification failed')
        result = {
            'verified': True,
            'bot_id': str(identity['id']),
            'username': identity.get('username', ''),
        }
        response = client.post(origin + '/getWebhookInfo')
        status = response.json()
        if (
            response.status_code != 200
            or status.get('ok') is not True
            or not isinstance(status.get('result'), dict)
        ):
            raise ValueError('Webhook inspection failed')
        current_webhook = status['result'].get('url', '')
        result['webhook_present'] = bool(current_webhook)
        result['pending_updates'] = status['result'].get('pending_update_count', 0)
        if (
            current_webhook
            and (webhook_url or polling)
            and current_webhook != expected_webhook
        ):
            raise ValueError('Existing webhook ownership was not confirmed')
        if polling:
            if account.reception != 'polling':
                raise ValueError('Polling configuration is required')
            if current_webhook:
                response = client.post(
                    origin + '/deleteWebhook', json={'drop_pending_updates': False}
                )
                if response.status_code != 200 or response.json().get('ok') is not True:
                    raise ValueError('Webhook removal failed')
            result['polling_ready'] = True
        if webhook_url:
            if account.reception != 'webhook':
                raise ValueError('Webhook configuration is required')
            url = urlsplit(webhook_url)
            if (
                url.scheme != 'https'
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError('A public HTTPS webhook URL is required')
            response = client.post(
                origin + '/setWebhook',
                json={
                    'url': webhook_url,
                    'secret_token': account.webhook_secret.get_secret_value(),
                    'allowed_updates': ['message', 'message_reaction'],
                    'drop_pending_updates': False,
                },
            )
            if response.status_code != 200 or response.json().get('ok') is not True:
                raise ValueError('Webhook registration failed')
            result['webhook_registered'] = True
        return result
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        raise RuntimeError(
            'Telegram setup failed; inspect protected configuration and retry verification.'
        ) from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('account')
    parser.add_argument('--webhook-url')
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--polling', action='store_true')
    parser.add_argument('--expected-webhook')
    args = parser.parse_args()
    if (bool(args.webhook_url) + bool(args.polling) != int(args.activate)) or (
        args.expected_webhook and not args.activate
    ):
        parser.error('Select --webhook-url or --polling with explicit --activate')
    config = settings()
    if args.account not in config.accounts:
        parser.error('Unknown account')
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        print(
            json.dumps(
                configure(
                    client,
                    config.accounts[args.account],
                    args.webhook_url,
                    args.polling,
                    args.expected_webhook,
                )
            )
        )


if __name__ == '__main__':
    main()
