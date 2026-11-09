import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, unquote, urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Account(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: Literal['whatsapp', 'telegram']
    provider_account: str = Field(pattern=r'^[0-9]+$')
    token: SecretStr | None = None
    token_source: Literal['config', 'odoo'] = 'config'
    webhook_secret: SecretStr | None = None
    verify_token: SecretStr | None = None
    graph_version: str = Field(default='v26.0', pattern=r'^v[0-9]+\.0$')
    enabled: bool = False
    location_enabled: bool = False
    reception: Literal['webhook', 'polling', 'disabled'] = 'webhook'

    @model_validator(mode='before')
    @classmethod
    def reception_default(cls, values):
        if (
            isinstance(values, dict)
            and values.get('provider') == 'whatsapp'
            and 'reception' not in values
        ):
            values = dict(values, reception='disabled')
        return values

    @model_validator(mode='after')
    def credentials(self):
        if (
            self.reception == 'webhook'
            and (
                not self.webhook_secret
                or len(self.webhook_secret.get_secret_value()) < 16
            )
        ) or (
            self.token_source == 'config'
            and (not self.token or not self.token.get_secret_value())
        ):
            raise ValueError('Protected provider credentials are required')
        if self.token_source == 'odoo' and (
            self.provider != 'telegram' or self.token is not None
        ):
            raise ValueError(
                'Odoo-managed Telegram tokens must not be copied into configuration'
            )
        if self.provider != 'telegram' and self.reception == 'polling':
            raise ValueError('Polling is available only for Telegram')
        if (
            self.provider == 'whatsapp'
            and self.reception == 'webhook'
            and not self.verify_token
        ):
            raise ValueError('WhatsApp verification token is required')
        if (
            self.provider == 'telegram'
            and self.token_source == 'config'
            and self.token.get_secret_value().split(':')[0] != self.provider_account
        ):
            raise ValueError('Telegram bot identity does not match its token')
        return self


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    database_url: SecretStr
    odoo_url: str
    odoo_database: str
    odoo_key: SecretStr
    accounts: dict[str, Account]
    encrypted_storage_confirmed: bool = False
    sending_enabled: bool = False
    allow_loopback_http: bool = False
    odoo_transport: Literal['json2', 'controller_v1'] = 'json2'

    @model_validator(mode='after')
    def endpoints(self):
        url = urlsplit(self.odoo_url)
        if (
            not (
                url.scheme == 'https'
                or (
                    self.allow_loopback_http
                    and url.scheme == 'http'
                    and url.hostname in ('127.0.0.1', '::1')
                )
            )
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ('', '/')
        ):
            raise ValueError('An HTTPS Odoo origin is required')
        db = urlsplit(self.database_url.get_secret_value())
        if db.scheme == 'sqlite':
            if not self.encrypted_storage_confirmed:
                raise ValueError(
                    'Encrypted deployment storage must be confirmed for SQLite'
                )
            if (
                db.netloc
                or not db.path.startswith('/')
                or db.path in ('/', '/:memory:')
                or db.fragment
            ):
                raise ValueError('An absolute local SQLite database path is required')
        elif (
            db.scheme != 'postgresql'
            or not db.path.strip('/')
            or unquote(db.path.strip('/')) == self.odoo_database
            or {'dbname', 'service'} & parse_qs(db.query).keys()
        ):
            raise ValueError('A separate PostgreSQL gateway database is required')
        identities = [
            (account.provider, account.provider_account)
            for account in self.accounts.values()
        ]
        if len(set(identities)) != len(identities):
            raise ValueError('Provider accounts must be unique')
        return self


def settings(*, load_provider_tokens=True):
    path = Path(os.environ['CRM_MESSAGING_CONFIG'])
    if path.stat().st_mode & 0o077:
        raise RuntimeError('Gateway configuration must be private (mode 0600)')
    try:
        config = Settings.model_validate(json.loads(path.read_text()))
    except (ValueError, TypeError):
        raise RuntimeError('Invalid protected gateway configuration') from None

    if load_provider_tokens and any(
        account.token_source == 'odoo' for account in config.accounts.values()
    ):
        import logging
        import httpx
        from .odoo import Odoo

        logging.getLogger('httpx').setLevel(logging.CRITICAL)
        logging.getLogger('httpcore').setLevel(logging.CRITICAL)
        try:
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                load_odoo_tokens(config, Odoo(config, client))
        except Exception:
            raise RuntimeError(
                'Odoo-managed Telegram credentials are unavailable'
            ) from None
    return config


def load_odoo_tokens(config, odoo):
    for code, account in config.accounts.items():
        if account.token_source != 'odoo':
            continue
        values = odoo.call('get_provider_credentials', code)
        token = values.get('token')
        if (
            values.get('provider') != 'telegram'
            or values.get('provider_account') != account.provider_account
            or not isinstance(token, str)
            or token.partition(':')[0] != account.provider_account
            or ':' not in token
        ):
            raise RuntimeError('Invalid Odoo-managed Telegram credentials')
        account.token = SecretStr(token)
