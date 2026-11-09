import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from .config import settings
from .observability import latency
from .providers import normalize, verify_signature
from .storage import Conflict, Store


def create_app(config=None, store=None):
    config = config or settings(load_provider_tokens=False)
    store = store or Store(config.database_url.get_secret_value())
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware('http')
    async def measure_request(request, call_next):
        with latency('gateway_http'):
            return await call_next(request)

    def account_for(provider, code):
        account = config.accounts.get(code)
        if not account or account.provider != provider or not account.enabled:
            raise HTTPException(404, 'Account unavailable')
        return account

    @app.get('/health')
    def health():
        return {'status': 'ok'}

    @app.get('/ready')
    def ready():
        try:
            with store.connect() as conn:
                if not conn.execute(
                    'SELECT version FROM messaging_schema WHERE version=1'
                ).fetchone():
                    raise RuntimeError('Queue schema unavailable')
        except Exception:
            raise HTTPException(503, 'Durable queue unavailable') from None
        return {'status': 'ok'}

    @app.get('/webhooks/whatsapp/{code}', response_class=PlainTextResponse)
    async def verify(code: str, request: Request):
        import hmac

        account = account_for('whatsapp', code)
        if account.reception != 'webhook':
            raise HTTPException(409, 'Webhook reception is disabled')
        query = request.query_params
        if query.get('hub.mode') != 'subscribe' or not hmac.compare_digest(
            query.get('hub.verify_token', '').encode(),
            account.verify_token.get_secret_value().encode(),
        ):
            raise HTTPException(403, 'Verification failed')
        return query.get('hub.challenge', '')

    @app.post('/webhooks/{provider}/{code}')
    async def webhook(provider: str, code: str, request: Request):
        account = account_for(provider, code)
        if account.reception != 'webhook':
            raise HTTPException(409, 'Webhook reception is disabled')
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 1048576:
                raise HTTPException(413, 'Payload too large')
        if not verify_signature(account, raw, request.headers):
            raise HTTPException(403, 'Verification failed')
        try:
            events = normalize(account, json.loads(raw))
        except (
            ValueError,
            TypeError,
            KeyError,
            IndexError,
            AttributeError,
            OverflowError,
        ):
            raise HTTPException(400, 'Invalid webhook') from None
        try:
            await run_in_threadpool(store.ingest, code, events)
        except Conflict:
            raise HTTPException(409, 'Conflicting event identity') from None
        except Exception:
            raise HTTPException(503, 'Durable queue unavailable') from None
        return {'received': True}

    return app
