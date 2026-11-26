"""Bearer-authenticated /v1 API for Odoo and other integrations."""

import asyncio
from contextlib import asynccontextmanager, suppress
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import re
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg import Error
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .documents import SUPPORTED
from .engine import GeminiProvider, ProviderError
from .pg_runtime import IMAGES, Runtime
from .pg_store import Store, StoreError, digest


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("*")
    @classmethod
    def valid_text(cls, value):
        def check(item):
            if isinstance(item, str):
                item.encode("utf-8")
                if "\x00" in item:
                    raise ValueError("NUL not allowed")
            elif isinstance(item, dict):
                for k, v in item.items():
                    check(k)
                    check(v)
            elif isinstance(item, list):
                for v in item:
                    check(v)
        check(value)
        return value


class Record(Input):
    source_id: str | None = Field(default=None, min_length=1, max_length=512)
    title: str = Field(min_length=1, max_length=512)
    text: str = Field(default="", max_length=1_000_000)
    metadata: dict = Field(default_factory=dict)
    public: bool = False


class Change(Input):
    title: str = Field(default="", min_length=1, max_length=512)
    text: str = Field(default="", max_length=1_000_000)
    metadata: dict = Field(default_factory=dict)
    public: bool = False
    archived: bool = False


class Question(Input):
    question: str = Field(min_length=1, max_length=8000)


def create_app(cfg, store=None, provider=None):
    db = store or Store(cfg.database.dsn.get_secret_value())

    @asynccontextmanager
    async def lifespan(app):
        ai = provider or GeminiProvider(cfg.gemini)
        await db.pool.open()
        app.state.rag = Runtime(cfg, db, ai)
        task = asyncio.create_task(app.state.rag.run()) if cfg.worker.enabled else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            await db.pool.close()
            if provider is None:
                await ai.close()

    app = FastAPI(title="FastRAG pgvector", version="1.0", lifespan=lifespan)

    @app.middleware("http")
    async def headers(request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        request_id = str(uuid4())
        # Starlette may spool multipart to disk before a route sees UploadFile.
        # Limit the raw stream as well as the validated file length.
        maximum = (cfg.rag.max_upload_mb * 1024 * 1024 + 65536
                   if request.url.path.endswith("/attachments") else 8 * 1024 * 1024)
        declared = request.headers.get("content-length")
        if declared and (not declared.isdecimal() or len(declared) > 12 or int(declared) > maximum):
            response = JSONResponse({"detail": "Request body too large"}, status_code=413)
        else:
            received = 0
            original = request.receive
            exceeded = False

            async def bounded_receive():
                nonlocal received, exceeded
                message = await original()
                received += len(message.get("body", b""))
                if received > maximum:
                    exceeded = True
                    raise HTTPException(413, "Request body too large")
                return message

            response = await call_next(Request(request.scope, bounded_receive))
            if exceeded:
                response = JSONResponse({"detail": "Request body too large"}, status_code=413)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(StoreError)
    async def store_error(request, exc):
        return JSONResponse({"detail": exc.message}, status_code=exc.status)

    @app.exception_handler(Error)
    @app.exception_handler(PoolTimeout)
    async def db_error(request, exc):
        return JSONResponse({"detail": "FastRAG database unavailable"}, status_code=503)

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": "AI provider request failed"}, status_code=502)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    async def identity(request: Request, creds: HTTPAuthorizationCredentials | None = Depends(HTTPBearer(auto_error=False))):
        if creds and re.fullmatch(r"[A-Za-z0-9_-]{32,128}", creds.credentials):
            rag = request.app.state.rag
            key_digest = digest(creds.credentials)
            found = rag.keys.get(key_digest)
            if found is None:
                found = await db.get_key(key_digest)
                if found is not None:
                    rag.keys.put(key_digest, found)
            if found is not None:
                if not rag.consume(key_digest):
                    raise HTTPException(429, "API key request limit reached",
                                        headers={"Retry-After": str(ceil(60 / cfg.database.requests_per_minute))})
                return found
        raise HTTPException(401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})

    def permit(permission):
        async def allowed(auth=Depends(identity)):
            if permission not in auth["permissions"]:
                raise HTTPException(403, "Permission denied")
            return auth
        return Depends(allowed)

    async def replay(auth, name, key, payload, action):
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        async with db.pool.connection() as conn:
            async with db.replay(conn, auth["collection"], name, key, digest(serialized)) as reply:
                if "value" not in reply:
                    reply["value"] = jsonable_encoder(await action(conn, auth["collection"]))
                return reply["value"]

    @app.get("/healthz")
    async def health():
        return {"ok": True}

    @app.get("/readyz")
    async def ready(auth=Depends(identity)):
        await db.ready()
        return {"ready": True, "api_version": "v1"}

    @app.get("/v1/connection")
    async def connection(auth=Depends(identity)):
        await db.ready()
        return {"api_version": "v1", **auth}

    @app.get("/v1/records")
    async def list_records(after: UUID | None = None, limit: int = Query(50, ge=1, le=100),
                           source_id: str | None = Query(None, max_length=512), auth=permit("read")):
        if source_id is not None and "\x00" in source_id:
            raise HTTPException(422, "Invalid source ID")
        records = await db.list_records(auth["collection"], after, limit + 1, source_id)
        return {"records": records[:limit], "next_cursor": records[limit - 1]["id"] if len(records) > limit else None}

    def check_payload(data):
        try:
            if len(json.dumps(data.get("metadata", {}), allow_nan=False)) > 32768:
                raise HTTPException(413, "Metadata too large")
        except (ValueError, RecursionError):
            raise HTTPException(422, "Invalid metadata") from None
        if len(data.get("text", "")) > cfg.rag.max_text_chars:
            raise HTTPException(413, "Record text too large")

    @app.post("/v1/records", status_code=201)
    async def create_record(body: Record, idempotency_key: UUID | None = Header(None), auth=permit("write")):
        data = body.model_dump()
        check_payload(data)
        return await replay(auth, "create", idempotency_key, data, lambda conn, col: db.create(conn, col, data))

    @app.get("/v1/records/{rid}")
    async def get_record(rid: UUID, auth=permit("read")):
        return await db.get_record(auth["collection"], rid)

    @app.patch("/v1/records/{rid}")
    async def update_record(rid: UUID, body: Change, auth=permit("write")):
        data = body.model_dump(exclude_unset=True)
        check_payload(data)
        async with db.pool.connection() as conn:
            return await db.update(conn, auth["collection"], rid, data)

    @app.post("/v1/records/{rid}/attachments", status_code=201)
    async def upload(rid: UUID, file: UploadFile = File(...), caption: str = Form("", max_length=8000),
                     idempotency_key: UUID | None = Header(None), auth=permit("write")):
        filename = Path((file.filename or "").replace("\\", "/")).name
        if len(filename) > 255 or any(ord(c) < 32 for c in filename) or "\x00" in caption:
            raise HTTPException(422, "Invalid filename or caption")
        if Path(filename).suffix.lower() not in SUPPORTED | IMAGES:
            raise HTTPException(415, "Unsupported attachment type")
        limit = cfg.rag.max_upload_mb * 1024 * 1024
        content = await file.read(limit + 1)
        if len(content) > limit:
            raise HTTPException(413, "Attachment too large")
        if not content:
            raise HTTPException(422, "Empty attachment")
        data = [str(rid), filename, caption, sha256(content).hexdigest()]
        return await replay(auth, "upload", idempotency_key, data,
                            lambda conn, col: db.add_file(conn, col, rid, filename, caption, content))

    @app.get("/v1/records/{rid}/attachments/{fid}")
    async def download(rid: UUID, fid: UUID, auth=permit("read")):
        item = await db.get_file(auth["collection"], rid, fid)
        return Response(item["content"], media_type="application/octet-stream",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(item['filename'], safe='')}",
                                 "X-Content-Type-Options": "nosniff"})

    @app.delete("/v1/records/{rid}/attachments/{fid}", status_code=204)
    async def remove(rid: UUID, fid: UUID, auth=permit("write")):
        async with db.pool.connection() as conn:
            await db.remove_file(conn, auth["collection"], rid, fid)

    @app.post("/v1/records/{rid}/index", status_code=202)
    async def index(request: Request, rid: UUID, idempotency_key: UUID | None = Header(None), auth=permit("write")):
        profile = request.app.state.rag.job_profile
        return await replay(auth, "index", idempotency_key, [str(rid)],
                            lambda conn, col: db.enqueue(conn, col, rid, profile))

    @app.get("/v1/jobs/{jid}")
    async def job(jid: UUID, auth=permit("read")):
        return await db.get_job(auth["collection"], jid)

    async def search(rag, auth, question):
        vec = await rag.embed(auth["collection"], question, query=True)
        return await db.search(auth["collection"], auth["public_only"], rag.job_profile,
                               vec, cfg.rag.top_k, cfg.rag.min_similarity)

    async def run_query(rag, auth, body, answer=False):
        if rag.query_gate.locked():
            raise HTTPException(429, "Query capacity reached", headers={"Retry-After": "2"})
        async with rag.query_gate:
            matches = await search(rag, auth, body.question)
            if not answer:
                return {"matches": matches}
            if not matches:
                return {"answer": "No matching information was found in the indexed documents.", "citations": []}
            async with rag.provider_gate:
                generated = await rag.provider.answer(body.question, matches)
            if not await db.still_visible(auth["collection"], auth["public_only"], rag.job_profile, matches):
                raise HTTPException(409, "Knowledge changed while answering; retry the question")
            found = {int(n) for n in re.findall(r"\[([0-9]{1,3})\]", generated)}
            citations = [{k: v for k, v in m.items() if k not in {"content", "revision"}}
                         | {"reference": i} for i, m in enumerate(matches, 1) if i in found]
            if not citations or found - set(range(1, len(matches) + 1)):
                return {"answer": "No supported answer was found in the indexed documents.", "citations": []}
            return {"answer": generated, "citations": citations}

    @app.post("/v1/search")
    async def search_records(request: Request, body: Question, auth=permit("query")):
        return await run_query(request.app.state.rag, auth, body)

    @app.post("/v1/answers")
    async def ask(request: Request, body: Question, auth=permit("query")):
        return await run_query(request.app.state.rag, auth, body, answer=True)

    return app
