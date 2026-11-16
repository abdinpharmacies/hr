import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from psycopg2 import OperationalError
from odoo import api, SUPERUSER_ID
from odoo.exceptions import UserError


def run(registry):
    phone = '+201009987654'
    browser = secrets.token_urlsafe(32)
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {'lang': 'en_US'})
        website = env['website'].search([], limit=1)
        worker = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Race worker', 'login': 'wa.race.' + secrets.token_hex(8),
            'group_ids': [(6, 0, [env.ref('base.group_user').id, env.ref('ab_storefront_whatsapp_auth.group_auth_transport').id])],
        })
        env['ab_storefront_whatsapp_transport'].create({
            'name': 'Race sender', 'website_id': website.id, 'service_user_id': worker.id,
            'sender': '123456', 'template_en': 'race_en', 'template_ar': 'race_ar', 'enabled': True,
        })
        env['ir.config_parameter'].set_param('auth_signup.invitation_scope', 'b2c')
        service = env['ab_storefront_auth_service'].with_context(website_id=website.id)
        token = service._request_whatsapp_signup(phone, browser, '192.0.2.2')
        challenge = service._find(token, ['phone_signup'], browser)
        event = env['ab_storefront_auth_event'].search([('challenge_id', '=', challenge.id), ('channel', '=', 'whatsapp')])
        code = json.loads(service._cipher().decrypt(event.payload.encode()).decode())['code']
        assert service._verify_whatsapp_signup(token, browser, code)
        website_id = website.id
        cr.commit()
    barrier = Barrier(2)

    def complete(index):
        barrier.wait(timeout=10)
        for attempt in range(3):
            try:
                with registry.cursor() as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {'lang': 'en_US', 'website_id': website_id})
                    env['ab_storefront_auth_service']._finish_phone_signup(token, browser, {'name': 'Race customer', 'password': 'Strong9!Pass'})
                    cr.commit()
                    return 'created'
            except OperationalError:
                continue
            except UserError:
                return 'rejected'
        return 'retry-exhausted'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(complete, (1, 2)))
    assert sorted(results) == ['created', 'rejected'], results
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        assert env['res.users'].search_count([('login', '=', phone)]) == 1
    print('Concurrent completion: one account created; second completion rejected')
