import argparse
import getpass
import json
import logging
import os
import secrets
import tempfile
import sys
from pathlib import Path

import httpx

from .config import Settings, load_odoo_tokens
from .odoo import Odoo
from .telegram_setup import configure


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('config', type=Path)
    parser.add_argument('--username', required=True)
    parser.add_argument('--bootstrap', type=Path)
    parser.add_argument('--from-odoo', action='store_true')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        parser.error('Run setup in a local terminal with masked input')
    if args.config.exists():
        parser.error(
            'Configuration already exists; preserve it and use telegram_setup for verification'
        )
    logging.getLogger('httpx').setLevel(logging.CRITICAL)
    logging.getLogger('httpcore').setLevel(logging.CRITICAL)
    token = None if args.from_odoo else getpass.getpass('BotFather token (hidden): ')
    bot_id = (
        input('Bot ID shown in Odoo Telegram Connection: ').strip()
        if args.from_odoo
        else token.split(':')[0]
    )
    bootstrap = {}
    if args.bootstrap:
        if args.bootstrap.stat().st_mode & 0o077:
            parser.error('Bootstrap credentials must have mode 0600')
        bootstrap = json.loads(args.bootstrap.read_text())
    key = bootstrap.get('odoo_key') or getpass.getpass(
        'Dedicated Odoo service API key (hidden): '
    )
    dsn = bootstrap.get('database_url') or getpass.getpass(
        'Separate gateway PostgreSQL DSN (hidden): '
    )
    account_code = (
        bootstrap.get('account_code') or input('Odoo messaging account code: ').strip()
    )
    values = {
        'database_url': dsn,
        'odoo_url': 'http://127.0.0.1:4092',
        'odoo_database': 'callcenter',
        'odoo_key': key,
        'allow_loopback_http': True,
        'odoo_transport': 'controller_v1',
        'sending_enabled': False,
        'accounts': {
            account_code: {
                'provider': 'telegram',
                'provider_account': bot_id,
                'token_source': 'odoo' if args.from_odoo else 'config',
                'token': token,
                'webhook_secret': secrets.token_urlsafe(32),
                'enabled': False,
                'reception': 'polling',
            }
        },
    }
    try:
        config = Settings.model_validate(values)
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            load_odoo_tokens(config, Odoo(config, client))
            identity = configure(client, config.accounts[account_code])
        if identity['username'].lower() != args.username.lstrip('@').lower():
            raise ValueError('Bot username mismatch')
        args.config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=args.config.parent, prefix='.messaging-'
        )
        try:
            with os.fdopen(descriptor, 'w') as stream:
                json.dump(values, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, args.config)
        finally:
            os.unlink(temporary)
    except Exception:
        parser.exit(
            1,
            'Setup failed. Check private inputs and connectivity; no activation was performed.\n',
        )
    print(json.dumps(identity))
    print(
        'Protected configuration saved with mode 0600. Reception and sending remain disabled.'
    )


if __name__ == '__main__':
    main()
