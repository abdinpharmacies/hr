import hashlib
import hmac
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from starlette.concurrency import run_in_threadpool

from .config import settings
from .storage import sessions, store_delivery

app = FastAPI(title='CRM Provider Gateway', docs_url=None, redoc_url=None, openapi_url=None)


def persist(source, event_id, payload):
    with sessions()() as session, session.begin():
        store_delivery(session, source, event_id, 'message', payload)


@app.get('/health')
def health():
    return {'status': 'ok'}


@app.get('/webhooks/{channel}')
def verify(channel: str, request: Request):
    config = settings().channels.get(channel)
    if not config or config.provider != 'whatsapp' or not config.verify_token:
        raise HTTPException(404)
    if request.query_params.get('hub.mode') != 'subscribe' or not hmac.compare_digest(request.query_params.get('hub.verify_token', ''), config.verify_token.get_secret_value()):
        raise HTTPException(403)
    return PlainTextResponse(request.query_params.get('hub.challenge', ''))


@app.post('/webhooks/{channel}')
async def webhook(channel: str, request: Request):
    config = settings().channels.get(channel)
    if not config:
        raise HTTPException(404)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 1_000_000:
            raise HTTPException(413)
    secret = config.secret.get_secret_value()
    if config.provider == 'telegram':
        if not hmac.compare_digest(request.headers.get('x-telegram-bot-api-secret-token', ''), secret):
            raise HTTPException(403)
    elif config.provider == 'whatsapp':
        signature = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, request.headers.get('x-hub-signature-256', '')):
            raise HTTPException(403)
    else:
        raise HTTPException(404)
    try:
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError('Invalid event')
        event_id = str(event['update_id']) if config.provider == 'telegram' else hashlib.sha256(raw).hexdigest()
        await run_in_threadpool(persist, channel, event_id, event)
    except (ValueError, KeyError):
        raise HTTPException(422) from None
    return {'received': True}
