import time
from uuid import uuid4

import httpx

from .observability import latency


class OdooUnavailable(RuntimeError):
    pass


class Odoo:
    def __init__(self, config, client):
        self.config = config
        self.client = client

    def call(self, method, code, **values):
        with latency('odoo_http'):
            return self._call(method, code, **values)

    def _call(self, method, code, **values):
        account = self.config.accounts[code]
        correlation = str(uuid4())
        payload = dict(
            account_code=code, provider_account=account.provider_account, **values
        )
        controller = self.config.odoo_transport == 'controller_v1'
        path = '/crm/messaging/v1/' if controller else '/json/2/ab_crm_messaging_api/'
        attempts = 4 if method == 'get_provider_credentials' else 1
        for attempt in range(attempts):
            try:
                response = self.client.post(
                    self.config.odoo_url.rstrip('/') + path + method,
                    headers={
                        'Authorization': 'Bearer '
                        + self.config.odoo_key.get_secret_value(),
                        'X-Odoo-Database': self.config.odoo_database,
                    },
                    json=(
                        {'correlation_id': correlation, 'payload': payload}
                        if controller
                        else payload
                    ),
                )
            except httpx.HTTPError:
                raise OdooUnavailable('Odoo transport unavailable') from None
            if response.status_code >= 500 or response.status_code == 429:
                raise OdooUnavailable('Odoo temporarily unavailable')
            if response.status_code != 409 or attempt == attempts - 1:
                break
            time.sleep(0.2 * (2**attempt))
        if response.status_code != 200:
            raise RuntimeError('Odoo request failed')
        data = response.json()
        if controller:
            if data.get('correlation_id') != correlation or 'result' not in data:
                raise RuntimeError('Invalid Odoo response')
            return data['result']
        return data
