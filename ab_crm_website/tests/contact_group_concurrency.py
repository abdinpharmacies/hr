import ast
from pathlib import Path
from types import SimpleNamespace, MethodType
from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import api, fields
from .test_contact_groups import TestWebsiteContactGroups
from ..protocol import fingerprint


def run(env):
    if env.cr.dbname != 'callcenter_contact_groups_race_20261115':
        raise ValueError('Use the isolated contact grouping concurrency database.')
    source = ast.parse(Path(__file__).parents[2].joinpath(
        'ab_crm_sales_workspace/tests/test_workspace.py').read_text())
    fixture = next(node for node in ast.walk(source)
                   if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass')
    cls = SimpleNamespace(env=env)
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<group-fixture>', 'exec'))
    source = ast.parse(Path(__file__).with_name('test_contact_groups.py').read_text())
    fixture = next(node for node in ast.walk(source)
                   if isinstance(node, ast.FunctionDef) and node.name == 'setUp')
    self = cls
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<website-group-fixture>', 'exec'))
    cls.website_order = MethodType(TestWebsiteContactGroups.website_order, cls)
    first = cls.website_order()
    uid, context = cls.staff.id, first.env.context
    contact_id, conversation_id = cls.contact['id'], first.id
    preview = first.action_preview_customer_link(contact_id)
    env.cr.commit()
    with env.registry.cursor() as cursor:
        stale = api.Environment(cursor, uid, context)['ab_crm_conversation'].browse(conversation_id)
        assert stale.action_preview_customer_link(contact_id)['fingerprint'] == preview['fingerprint']
        second = cls.website_order('WEB-CONCURRENT')
        env.cr.commit()
        try:
            stale.action_confirm_customer_link(contact_id, preview['fingerprint'])
        except SerializationFailure:
            cursor.rollback()
        else:
            raise AssertionError('Concurrent arrival did not reject the stale transaction.')
    with env.registry.cursor() as cursor:
        current = api.Environment(cursor, uid, context)['ab_crm_conversation'].browse(conversation_id)
        preview = current.action_preview_customer_link(contact_id)
        assert set(preview['conversation_ids']) == {first.id, second.id}
        current.action_confirm_customer_link(contact_id, preview['fingerprint'])
        cursor.commit()
    with env.registry.cursor() as cursor:
        current = api.Environment(cursor, uid, context)['ab_crm_conversation'].browse(conversation_id)
        preview = current.action_preview_customer_link(contact_id)
        current.action_confirm_customer_link(contact_id, preview['fingerprint'])
        assert current.env['ab_crm_workspace_audit'].sudo().search_count([
            ('conversation_id', 'in', [first.id, second.id]), ('action', '=', 'review_customer_link')]) == 2
    print('Concurrent arrival rejected stale snapshot; fresh review linked both orders; repeat produced no duplicate audits.')
