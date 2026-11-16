import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, SecretStr, model_validator


class AuthSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str
    database: str
    token: SecretStr
    account: str
    sender: str
    templates: dict[str, str]

    @model_validator(mode='after')
    def validate_source(self):
        url = urlsplit(self.url)
        if (url.scheme != 'https' or not url.hostname or url.username or url.password
                or url.path not in ('', '/') or url.query or url.fragment
                or not self.database or not self.token.get_secret_value()
                or not self.sender.isascii() or not self.sender.isdecimal()
                or not self.templates or len(self.templates) > 2):
            raise ValueError('Invalid authentication source')
        return self


class AuthSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = False
    sources: dict[str, AuthSource]

    @model_validator(mode='after')
    def validate_sources(self):
        for source in self.sources:
            if str(UUID(source)) != source:
                raise ValueError('Invalid authentication source identity')
        return self


def auth_settings():
    path = Path(os.environ['CRM_AUTH_CONFIG'])
    if path.stat().st_mode & 0o077:
        raise RuntimeError('Authentication configuration must be private')
    try:
        return AuthSettings.model_validate(json.loads(path.read_text()))
    except (ValueError, TypeError):
        raise RuntimeError('Invalid protected authentication configuration') from None
