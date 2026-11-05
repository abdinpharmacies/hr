import hashlib
import json
from datetime import datetime, timezone
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


class Delivery(Base):
    __tablename__ = 'delivery'
    __table_args__ = (UniqueConstraint('source', 'event_id'),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source: Mapped[str] = mapped_column(String(256))
    event_id: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(24))
    payload: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(24), default='pending', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_success: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


@lru_cache
def sessions():
    engine = create_engine(settings().database_url.get_secret_value(), pool_size=3, max_overflow=0, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)


def store_delivery(session, source, event_id, kind, payload):
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    session.execute(insert(Delivery).values(id=str(uuid4()), source=source, event_id=event_id, kind=kind,
        payload=payload, digest=digest, state='pending', attempts=0, next_attempt=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc)).on_conflict_do_nothing(index_elements=['source', 'event_id']))
    delivery = session.scalar(select(Delivery).where(Delivery.source == source, Delivery.event_id == event_id))
    if delivery.digest != digest or delivery.kind != kind:
        raise ValueError('An event identity was reused with different content')
    return delivery
