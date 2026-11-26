import asyncio
import base64
from contextlib import asynccontextmanager, suppress
import hmac
from pathlib import Path
import uuid
from ipaddress import ip_address

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .documents import SUPPORTED
from .engine import GeminiProvider, ProviderError, RagEngine
from .odoo_client import BackendError, OdooClient
from .settings import load_settings
from .worker import run_worker
from .contracts import API_VERSION


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=8000)


def create_app(settings=None, backend=None, provider=None):
    cfg = settings

    @asynccontextmanager
    async def lifespan(application):
        nonlocal cfg
        cfg = cfg or load_settings()
        cfg.require_credentials()
        application.state.backend = backend or OdooClient(cfg.odoo)
        application.state.provider = provider or GeminiProvider(cfg.gemini)
        application.state.engine = RagEngine(cfg, application.state.backend, application.state.provider)
        # Backend outages leave liveness available; readiness and work remain blocked.
        task = asyncio.create_task(run_worker(application.state.engine)) if cfg.worker.enabled else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            if backend is None:
                await application.state.backend.close()
            if provider is None:
                await application.state.provider.close()

    application = FastAPI(title="FastRAG", version="1.0", lifespan=lifespan)

    def authenticated(request: Request, authorization: str = Header(default="")):
        if cfg.server.auth_mode == "loopback":
            try:
                local = request.client is not None and ip_address(request.client.host).is_loopback
            except ValueError:
                local = False
            if not local:
                raise HTTPException(403, "Local connections only")
            return
        expected = "Bearer " + cfg.server.api_key.get_secret_value()
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(401, "Invalid API key", headers={"WWW-Authenticate": "Bearer"})

    @application.exception_handler(BackendError)
    async def backend_error(request, exc):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @application.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @application.get("/healthz")
    async def health():
        return {"ok": True}

    @application.get("/readyz", dependencies=[Depends(authenticated)])
    async def ready():
        await application.state.backend.check(cfg.gemini)
        return {"ready": True, "api_version": API_VERSION}

    @application.post("/documents", status_code=202, dependencies=[Depends(authenticated)])
    async def upload(file: UploadFile = File(...), idempotency_key: str | None = Header(default=None)):
        filename = Path((file.filename or "").replace("\\", "/")).name
        if Path(filename).suffix.lower() not in SUPPORTED:
            raise HTTPException(415, "Unsupported document format")
        try:
            key = str(uuid.UUID(idempotency_key)) if idempotency_key else str(uuid.uuid4())
        except ValueError as exc:
            raise HTTPException(400, "Idempotency-Key must be a UUID") from exc
        raw = await file.read(cfg.rag.max_upload_mb * 1024 * 1024 + 1)
        await file.close()
        if not raw:
            raise HTTPException(400, "Empty document")
        if len(raw) > cfg.rag.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "Document is too large")
        return await application.state.backend.call("upload_document", filename=filename,
                    content_base64=base64.b64encode(raw).decode("ascii"), external_key=key)

    @application.get("/jobs/{job_id}", dependencies=[Depends(authenticated)])
    async def job_status(job_id: int):
        result = await application.state.backend.call("job_status", job_id=job_id)
        if not result.get("job"):
            raise HTTPException(404, "Job not found")
        return result["job"]

    @application.post("/ask", dependencies=[Depends(authenticated)])
    async def ask(body: Question, idempotency_key: str | None = Header(default=None)):
        question = body.question.strip()
        if not question:
            raise HTTPException(422, "Question must not be blank")
        try:
            key = str(uuid.UUID(idempotency_key)) if idempotency_key else str(uuid.uuid4())
        except ValueError as exc:
            raise HTTPException(400, "Idempotency-Key must be a UUID") from exc
        result = await application.state.engine.ask(question)
        saved = await application.state.backend.call("save_answer", external_key=key, question=question, **result)
        return saved

    return application
