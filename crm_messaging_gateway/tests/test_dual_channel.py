from unittest.mock import Mock

import pytest

from app.config import Account
from app.providers import normalize
from app.whatsapp_check import consistency
from app.worker import Worker
from test_gateway import config, telegram, whatsapp


def test_independent_send_switch_and_telegram_compatibility():
    cfg = config()
    cfg.sending_enabled = True
    assert telegram().sending_enabled
    assert not whatsapp().sending_enabled
    store, odoo = Mock(), Mock()
    store.claim_outgoing.return_value = None
    worker = Worker(cfg, store, odoo, Mock())
    worker.collect('wa')
    odoo.call.assert_not_called()
    worker.dispatch()
    store.claim_outgoing.assert_called_once_with(['tg'])
    cfg.sending_enabled = False
    worker.dispatch()
    assert store.claim_outgoing.call_count == 1


def test_whatsapp_version_is_pinned():
    with pytest.raises(ValueError):
        Account(provider='whatsapp', provider_account='456', token='test', graph_version='v22.0')


def test_opaque_whatsapp_identity_is_retained_for_delivery():
    payload = {'object': 'whatsapp_business_account', 'entry': [{'changes': [{'field': 'messages', 'value': {
        'metadata': {'phone_number_id': '456'},
        'messages': [{'id': 'wamid-opaque', 'from': 'opaque.12:34', 'type': 'text',
                      'timestamp': '1700000000', 'text': {'body': 'Hello'}}],
    }}]}]}
    event = normalize(whatsapp(), payload)[0][2]
    assert event['sender'] == 'opaque.12:34'
    assert 'review_reason' not in event
    assert 'contact' not in event


def test_masked_consistency_does_not_report_secrets():
    account = whatsapp()
    result = consistency(account, {'options': {'whatsapp_phone_number_id': '456',
        'whatsapp_api_version': 'v26.0', 'whatsapp_token': 'test-only'}})
    assert result['business_number_matches']
    assert result['version_explicit_and_matches']
    assert result['token_present_and_matches']
    assert all(type(value) is bool for value in result.values())


def test_whatsapp_uses_dedicated_odoo_credential():
    import httpx
    from app.odoo import Odoo
    calls = []
    def respond(request):
        calls.append(request.headers['authorization'])
        return httpx.Response(200, json={})
    cfg = config()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        Odoo(cfg, client).call('lease_outgoing', 'tg')
        Odoo(cfg, client).call('lease_outgoing', 'wa')
    assert calls == ['Bearer test-only', 'Bearer whatsapp-test-service-key']
    with pytest.raises(ValueError):
        Account(provider='whatsapp', provider_account='456', token='test', enabled=True)
