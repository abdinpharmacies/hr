import secrets
from inspect import unwrap

from odoo.http import request
from odoo.addons.ab_ecommerce_api.controllers.api import EcommerceApi, SECRET, TEXT
from odoo.addons.ab_ecommerce_api.controllers.common import body, endpoint, schema


class WhatsAppApi(EcommerceApi):
    @endpoint('/auth/phone/start', 'POST', tag='Authentication', summary='Start verified phone registration', authenticated=False,
              payload=body({'phone': TEXT, 'channel': schema(enum=['telegram', 'whatsapp'])}, ('phone',)))
    def phone_start(self):
        data = request.ab_api_data
        if data.get('channel', 'telegram') == 'telegram':
            return unwrap(EcommerceApi.phone_start)(self)
        browser = secrets.token_urlsafe(32)
        token = self._service()._request_whatsapp_signup(data['phone'], browser, request.httprequest.remote_addr)
        return {'challenge_token': token, 'browser_token': browser, 'verification_url': ''}

    @endpoint('/auth/phone/verify', 'POST', tag='Authentication', summary='Verify WhatsApp phone registration code', authenticated=False,
              payload=body({'challenge_token': SECRET, 'browser_token': SECRET, 'code': SECRET}, ('challenge_token', 'browser_token', 'code')),
              result={'type': 'object', 'properties': {'verified': {'type': 'boolean'}}})
    def phone_verify(self):
        data = request.ab_api_data
        verified = self._service()._verify_whatsapp_signup(data['challenge_token'], data['browser_token'], data['code'])
        return {'verified': verified}

    @endpoint('/auth/recovery', 'POST', tag='Authentication', summary='Request account recovery without revealing account existence', authenticated=False,
              payload=body({'channel': schema(enum=['email', 'telegram', 'whatsapp']), 'identifier': TEXT}, ('channel', 'identifier')))
    def recovery(self):
        return unwrap(EcommerceApi.recovery)(self)
