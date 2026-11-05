import json
import os
from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, SecretStr, field_validator


class Peer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str
    database: str
    key: SecretStr

    @field_validator('url')
    @classmethod
    def validate_url(cls, value):
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('A trusted HTTPS endpoint is required')
        return value.rstrip('/')


class Channel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str
    secret: SecretStr
    token: SecretStr
    verify_token: SecretStr | None = None
    phone_number_id: str | None = None
    graph_version: str | None = None


class Settings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    database_url: SecretStr
    odoo: Peer
    website: Peer | None = None
    channels: dict[str, Channel] = {}

    @field_validator('database_url')
    @classmethod
    def validate_database(cls, value):
        if not value.get_secret_value().startswith('postgresql+psycopg://'):
            raise ValueError('A separate PostgreSQL database is required')
        return value


@lru_cache
def settings():
    with open(os.environ['CRM_GATEWAY_CONFIG'], encoding='utf-8') as source:
        return Settings.model_validate(json.load(source))
