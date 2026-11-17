import ast
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace, MethodType
from uuid import uuid4


from odoo import api, fields
from odoo.service.model import retrying
from .test_contact_groups import TestWebsiteContactGroups
from ..protocol import fingerprint


def run(env):
    if env.cr.dbname != 'website_customer_race_20261116':
        raise ValueError('Use the isolated website customer validation database.')
    source = ast.parse(Path(__file__).parents[2].joinpath(
        'ab_crm_sales_workspace/tests/test_workspace.py').read_text())
    fixture = next(node for node in ast.walk(source)
                   if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass')
    cls = SimpleNamespace(env=env)
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<workspace-fixture>', 'exec'))
    source = ast.parse(Path(__file__).with_name('test_contact_groups.py').read_text())
    fixture = next(node for node in ast.walk(source)
                   if isinstance(node, ast.FunctionDef) and node.name == 'setUp')
    self = cls
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<website-fixture>', 'exec'))
    cls.website_order = MethodType(TestWebsiteContactGroups.website_order, cls)
    first = cls.website_order()
    envelope = env['ab_crm_website_event'].search([
        ('account_id', '=', cls.website_account.id)], limit=1).envelope
    events = []
    for reference in ('CONCURRENT-ONE', 'CONCURRENT-TWO'):
        event = deepcopy(envelope)
        event.update(order_uuid=str(uuid4()), event_uuid=str(uuid4()))
        event['payload']['reference'] = reference
        event['fingerprint'] = fingerprint(event)
        events.append(event)
    account_id, service_id = cls.website_account.id, cls.service.id
    account_code, provider = cls.website_account.code, cls.website_account.provider_account
    company_ids = cls.website_account.company_id.ids
    registry = env.registry
    env.cr.commit()
    barrier = Barrier(3)

    def receive(event):
        barrier.wait(timeout=20)
        with registry.cursor() as cursor:
            worker = api.Environment(cursor, service_id, {'allowed_company_ids': company_ids})
            attempts = []
            def deliver():
                attempts.append(True)
                return worker['ab_crm_messaging_api'].receive_website_event(account_code, provider, event)
            retrying(deliver, worker)
            cursor.commit()
            return len(attempts) - 1

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(receive, event) for event in [events[0], events[1], events[0]]]
        retries = [future.result(timeout=60) for future in futures]
    env.invalidate_all()
    orders = env['ab_crm_website_order'].search([('account_id', '=', account_id)])
    assert len(orders) == 3
    assert len(orders.conversation_id) == 1
    assert len(orders.website_customer_id) == 1
    assert len(orders.conversation_id.message_ids) == 3
    assert orders.conversation_id.id == first.id
    print('Concurrent orders and duplicate delivery: 3 orders, 1 identity, 1 chat, 3 messages; retry counts:', retries)
