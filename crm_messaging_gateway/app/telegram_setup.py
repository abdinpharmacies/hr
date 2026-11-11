import argparse
import json
import logging
from urllib.parse import urlsplit

import httpx

from .config import settings


class TelegramVerificationError(RuntimeError):
    def __init__(self, category):
        self.category = category
        super().__init__('Telegram verification failed: ' + category)


def checked_response(response):
    if response.status_code in (401, 403, 404):
        raise TelegramVerificationError('invalid_credentials')
    if response.status_code == 409:
        try:
            description = response.json().get('description', '')
        except (ValueError, AttributeError):
            description = ''
        category = 'active_webhook' if isinstance(description, str) and 'webhook' in description.lower() else 'competing_receiver'
        raise TelegramVerificationError(category)
    if response.status_code == 429 or response.status_code >= 500:
        raise TelegramVerificationError('provider_unavailable')
    try:
        data = response.json()
        if response.status_code != 200 or not isinstance(data, dict) or data.get('ok') is not True:
            raise ValueError()
        return data
    except (ValueError, TypeError):
        raise TelegramVerificationError('malformed_response') from None


def configure(client, account, webhook_url=None, polling=False, expected_webhook=None):
    if account.provider != 'telegram':
        raise ValueError('Select a Telegram account')
    origin = 'https://api.telegram.org/bot' + account.token.get_secret_value()
    try:
        response = client.post(origin + '/getMe')
        data = checked_response(response)
        identity = data.get('result', {})
        if (
            response.status_code != 200
            or data.get('ok') is not True
            or identity.get('is_bot') is not True
            or str(identity.get('id')) != account.provider_account
        ):
            raise TelegramVerificationError('identity_mismatch')
        result = {
            'verified': True,
            'bot_id': str(identity['id']),
            'username': identity.get('username', ''),
        }
        response = client.post(origin + '/getWebhookInfo')
        status = checked_response(response)
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
                    'allowed_updates': ['message', 'edited_message', 'message_reaction'],
                    'drop_pending_updates': False,
                },
            )
            if response.status_code != 200 or response.json().get('ok') is not True:
                raise ValueError('Webhook registration failed')
            result['webhook_registered'] = True
        return result
    except TelegramVerificationError:
        raise
    except httpx.HTTPError:
        raise TelegramVerificationError('network_failure') from None
    except (KeyError, TypeError, ValueError, AttributeError):
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
