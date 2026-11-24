"""Indexing and bounded process-local caches for the pgvector service."""

import asyncio
from collections import OrderedDict
from contextlib import suppress
from hashlib import sha256
import logging
from pathlib import Path
from time import monotonic

from psycopg import Error
from psycopg_pool import PoolTimeout

from .documents import SUPPORTED, chunks, extract_text
from .engine import ProviderError

IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
logger = logging.getLogger(__name__)


class Cache:
    def __init__(self, limit, ttl):
        self.limit, self.ttl = limit, ttl
        self.values = OrderedDict()

    def get(self, key):
        item = self.values.get(key)
        if item is not None:
            deadline, value = item
            if deadline > monotonic():
                self.values.move_to_end(key)
                return value
            del self.values[key]

    def put(self, key, value):
        self.values[key] = (monotonic() + self.ttl, value)
        self.values.move_to_end(key)
        if len(self.values) > self.limit:
            self.values.popitem(last=False)


def extract(rec, files, cfg):
    remaining = cfg.max_text_chars
    parts = []
    for file in [None, *files]:
        if file is None:
            fid, text = None, f"{rec['title']}\n{rec['text']}".strip()
        else:
            fid, text = file["id"], file["caption"].strip()
            if Path(file["filename"]).suffix.lower() in SUPPORTED:
                extracted = extract_text(file["filename"], file["content"], remaining)
                text = "\n".join(part for part in (text, extracted) if part)
        if not text:
            continue
        remaining -= len(text)
        if remaining < 0:
            raise ValueError("Extracted text exceeds the configured limit")
        parts.extend((fid, part) for part in chunks(text, cfg.chunk_chars, cfg.overlap_chars, cfg.max_chunks - len(parts)))
    return parts


class Runtime:
    def __init__(self, config, store, provider):
        self.config, self.store, self.provider = config, store, provider
        self.profile = f"{config.gemini.embedding_model}:{config.gemini.dimensions}:v1"
        self.job_profile = f"{self.profile}:{config.rag.chunk_chars}:{config.rag.overlap_chars}"
        self.embeddings = Cache(1024, 600)
        self.keys = Cache(1024, 5)
        self.rates = Cache(4096, 60)
        self.provider_gate = asyncio.Semaphore(2)
        self.query_gate = asyncio.Semaphore(4)

    def consume(self, key):
        capacity = self.config.database.requests_per_minute
        now = monotonic()
        tokens, last = self.rates.get(key) or (capacity, now)
        tokens = min(capacity, tokens + (now - last) * capacity / 60)
        if tokens < 1:
            return False
        self.rates.put(key, (tokens - 1, now))
        return True

    async def embed(self, collection, text, query=False):
        key = (collection, self.profile, query, sha256(text.encode()).digest())
        async with self.provider_gate:
            vector = self.embeddings.get(key)
            if vector is None:
                vector = await self.provider.embed(text, query=query)
                self.embeddings.put(key, vector)
        return vector

    async def index(self, job):
        async def keep_lease():
            while True:
                await asyncio.sleep(15)
                if not await self.store.renew(job):
                    return

        lease = asyncio.create_task(keep_lease())
        try:
            rec, files = await self.store.snapshot(job)
            parts = await asyncio.to_thread(extract, rec, files, self.config.rag)
            data = [(fid, part, await self.embed(rec["collection"], part)) for fid, part in parts]
            await self.store.finish(job, entries=data)
        except ProviderError:
            await self.store.finish(job, error="Embedding provider request failed", retry=True)
        except (Error, PoolTimeout):
            raise
        except Exception:
            await self.store.finish(job, error="Record changed or its contents could not be indexed")
        finally:
            lease.cancel()
            with suppress(asyncio.CancelledError, Error, PoolTimeout):
                await lease

    async def run(self):
        prune_at = 0
        while True:
            try:
                if monotonic() >= prune_at:
                    await self.store.prune()
                    prune_at = monotonic() + 60
                job = await self.store.claim(self.job_profile)
                if job:
                    await self.index(job)
                    continue
            except (Error, PoolTimeout) as exc:
                logger.warning("Indexing database operation failed (%s)", type(exc).__name__)
            await asyncio.sleep(self.config.worker.poll_seconds)
