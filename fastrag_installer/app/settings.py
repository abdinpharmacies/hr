from pathlib import Path
import os
from typing import Literal
from ipaddress import ip_address

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
import yaml


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OdooSettings(Section):
    url: str = "http://127.0.0.1:8069"
    database: str = ""
    api_key: SecretStr = SecretStr("")
    timeout_seconds: float = Field(default=60, ge=1, le=300)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value):
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Use an http(s) Odoo URL without embedded credentials")
        if parsed.query or parsed.fragment:
            raise ValueError("Odoo URL must not include query parameters or fragments")
        return value.rstrip("/")


class GeminiSettings(Section):
    api_key: SecretStr = SecretStr("")
    embedding_model: str = "gemini-embedding-2"
    generation_model: str = "gemini-2.5-flash"
    dimensions: int = Field(default=1536, ge=1, le=3072)
    timeout_seconds: float = Field(default=60, ge=1, le=300)


class ServerSettings(Section):
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1024, le=65535)
    api_key: SecretStr = SecretStr("")
    auth_mode: Literal["bearer", "loopback"] = "bearer"

    @model_validator(mode="after")
    def loopback_binding(self):
        if self.auth_mode == "loopback":
            try:
                valid = ip_address(self.host).is_loopback
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("Loopback mode requires a literal loopback bind address")
        return self


class WorkerSettings(Section):
    enabled: bool = True
    poll_seconds: float = Field(default=3, ge=1, le=60)


class RagSettings(Section):
    chunk_chars: int = Field(default=3000, ge=200, le=8000)
    overlap_chars: int = Field(default=300, ge=0)
    top_k: int = Field(default=5, ge=1, le=20)
    min_similarity: float = Field(default=0.2, ge=-1, le=1)
    max_upload_mb: int = Field(default=20, ge=1, le=20)
    max_text_chars: int = Field(default=1_000_000, ge=1000, le=1_000_000)
    max_chunks: int = Field(default=500, ge=1, le=500)

    @model_validator(mode="after")
    def valid_overlap(self):
        if self.overlap_chars >= self.chunk_chars:
            raise ValueError("overlap_chars must be smaller than chunk_chars")
        return self


class DatabaseSettings(Section):
    dsn: SecretStr = SecretStr("")
    requests_per_minute: int = Field(default=300, ge=10, le=6000)


class Settings(Section):
    storage: Literal["odoo", "pgvector"] = "odoo"
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    odoo: OdooSettings = Field(default_factory=OdooSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    rag: RagSettings = Field(default_factory=RagSettings)

    def require_credentials(self):
        if self.storage == "pgvector":
            self.require_database()
            secret = self.gemini.api_key.get_secret_value()
            if not secret or secret.startswith("CHANGE_ME"):
                raise ValueError("Configure gemini.api_key")
            if self.server.auth_mode != "bearer":
                raise ValueError("pgvector requires bearer authentication")
            return
        missing = []
        required = [("odoo.database", self.odoo.database),
                             ("odoo.api_key", self.odoo.api_key.get_secret_value()),
                             ("gemini.api_key", self.gemini.api_key.get_secret_value())]
        if self.server.auth_mode == "bearer":
            required.append(("server.api_key", self.server.api_key.get_secret_value()))
        for label, value in required:
            if not value or value.startswith("CHANGE_ME"):
                missing.append(label)
        if missing:
            raise ValueError("Configure " + ", ".join(missing))
        if self.server.auth_mode == "bearer" and len(self.server.api_key.get_secret_value()) < 32:
            raise ValueError("server.api_key must contain at least 32 characters")

    def require_database(self):
        if self.storage != "pgvector" or not self.database.dsn.get_secret_value():
            raise ValueError("Configure storage: pgvector and database.dsn")


def config_path():
    return Path(os.environ.get("FASTRAG_CONFIG", Path(__file__).resolve().parent.parent / "config/config.yaml"))


def load_settings(path=None):
    path = Path(path) if path else config_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for env, section, key in (("FASTRAG_ODOO_URL", "odoo", "url"),
                              ("FASTRAG_ODOO_DATABASE", "odoo", "database"),
                              ("FASTRAG_ODOO_API_KEY", "odoo", "api_key"),
                              ("FASTRAG_GEMINI_API_KEY", "gemini", "api_key"),
                              ("FASTRAG_API_KEY", "server", "api_key"),
                              ("FASTRAG_DATABASE_DSN", "database", "dsn")):
        if env in os.environ:
            data.setdefault(section, {})[key] = os.environ[env]
    return Settings.model_validate(data)
