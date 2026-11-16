import json
import re
from contextvars import ContextVar

from starlette.responses import Response

from .auth_config import auth_settings
from .config import settings
from .main import create_app as base_app
from .providers import verify_signature
from .storage import Store


_auth_receipts = ContextVar('auth_receipts', default=None)
_CORRELATION = re.compile(r'^ab-auth:([0-9a-f-]{36}):([0-9a-f-]{36})$')


class AuthRoutingStore:
    def __init__(self, store):
        self.store = store

    def __getattr__(self, name):
        return getattr(self.store, name)

    def ingest(self, account, events):
        receipts = _auth_receipts.get() or {}
        normal = []
        grouped = {}
        for key, kind, event in events:
            receipt = receipts.get(event.get('reference')) if kind == 'status' else None
            if receipt:
                source, delivery = receipt
                grouped.setdefault(source, []).append((key, 'incoming', {
                    'delivery': delivery, 'reference': event['reference'], 'status': event['status'],
                }))
            else:
                normal.append((key, kind, event))
        for source, rows in grouped.items():
            self.store.ingest('auth:' + source, rows)
        if normal:
            self.store.ingest(account, normal)


def create_app(config=None, auth=None, store=None):
    config = config or settings(load_provider_tokens=False)
    auth = auth or auth_settings()
    app = base_app(config, AuthRoutingStore(store or Store(config.database_url.get_secret_value())))

    @app.middleware('http')
    async def correlate(request, call_next):
        receipts = {}
        path = request.url.path
        if request.method == 'POST' and path.startswith('/webhooks/whatsapp/'):
            account_code = path.rsplit('/', 1)[-1]
            account = config.accounts.get(account_code)
            if account and account.enabled and account.reception == 'webhook':
                raw = bytearray()
                async for chunk in request.stream():
                    raw.extend(chunk)
                    if len(raw) > 1048576:
                        return Response(status_code=413)
                request._body = bytes(raw)
                if verify_signature(account, raw, request.headers):
                    try:
                        payload = json.loads(raw)
                        for entry in payload.get('entry', []):
                            for change in entry.get('changes', []):
                                value = change.get('value', {})
                                if str(value.get('metadata', {}).get('phone_number_id')) != account.provider_account:
                                    continue
                                for status in value.get('statuses', []):
                                    match = _CORRELATION.fullmatch(status.get('biz_opaque_callback_data', ''))
                                    if match:
                                        source_id, delivery = match.groups()
                                        source = auth.sources.get(source_id)
                                        if source and source.account == account_code and source.sender == account.provider_account:
                                            receipts[status['id']] = (source_id, delivery)
                                        else:
                                            return Response(status_code=503)
                    except (ValueError, TypeError, AttributeError, KeyError):
                        pass
        token = _auth_receipts.set(receipts)
        try:
            return await call_next(request)
        finally:
            _auth_receipts.reset(token)

    return app
