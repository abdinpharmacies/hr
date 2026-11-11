import ast
from pathlib import Path
from types import SimpleNamespace

from psycopg2.errors import SerializationFailure

from odoo import api, fields
from odoo.addons.ab_crm_whatsapp_workspace.models.common import bridge_mutation


def run(env):
    if env.cr.dbname != 'callcenter_unified_contacts_concurrency_test_20261110':
        raise ValueError('Use the isolated contact concurrency database.')
    source = ast.parse(Path(__file__).parents[2].joinpath('ab_crm_whatsapp_workspace/tests/test_bridge.py').read_text())
    fixture = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass')
    cls = SimpleNamespace(env=env)
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<contact-fixture>', 'exec'))
    first = cls.chatter_api.contact_save(cls.session_token,
        {'name': 'Concurrent first', 'phone': '+201014763233', 'address': ''}, branch_id=cls.branch.id)
    second = cls.chatter_api.contact_save(cls.session_token,
        {'name': 'Concurrent second', 'phone': '+201012345678', 'address': ''}, branch_id=cls.branch.id)
    uid, token, company_id = cls.staff.id, cls.session_token, cls.staff.company_id.id
    env.cr.commit()
    with env.registry.cursor() as first_cursor, env.registry.cursor() as second_cursor:
        context = {'allowed_company_ids': [company_id]}
        first_env = api.Environment(first_cursor, uid, context)
        second_env = api.Environment(second_cursor, uid, context)
        second_env['ab_crm_customer'].browse(second['id']).read(['name'])
        first_env['ab_crm_chatter_api'].contact_phone_add(token, first['id'], '+442079460123',
            reason='Confirmed first concurrent association', customer_confirmed=True)
        first_cursor.commit()
        try:
            second_env['ab_crm_chatter_api'].contact_phone_add(token, second['id'], '+442079460123',
                reason='Confirmed second concurrent association', customer_confirmed=True)
        except SerializationFailure:
            second_cursor.rollback()
        else:
            raise AssertionError('A stale transaction accepted a shared number.')
    with env.registry.cursor() as cursor:
        current = api.Environment(cursor, uid, {'allowed_company_ids': [company_id]})
        from odoo.exceptions import AccessError
        try:
            current['ab_crm_chatter_api'].contact_phone_add(token, second['id'], '+442079460123',
                reason='Retry concurrent association', customer_confirmed=True)
        except AccessError:
            pass
        else:
            raise AssertionError('The fresh retry did not require manager review.')
        assert current['ab_crm_contact_phone'].search_count([('number', '=', '+442079460123')]) == 1
    print('Concurrent shared-number edit: stale transaction rejected; fresh retry requires manager review.')
