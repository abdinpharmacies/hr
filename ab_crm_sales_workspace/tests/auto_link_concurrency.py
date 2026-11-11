import ast
from pathlib import Path
from types import SimpleNamespace

from psycopg2.errors import SerializationFailure

from odoo import api, fields
from odoo.addons.ab_crm_whatsapp_workspace.models.common import bridge_mutation


def run(env):
    if env.cr.dbname != 'callcenter_auto_phone_link_race_test_20261110_final':
        raise ValueError('Use the isolated automatic-link concurrency database.')
    source = ast.parse(Path(__file__).parents[2].joinpath('ab_crm_whatsapp_workspace/tests/test_bridge.py').read_text())
    fixture = next(node for node in ast.walk(source) if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass')
    cls = SimpleNamespace(env=env)
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<automatic-link-fixture>', 'exec'))
    contact = cls.chatter_api.contact_save(cls.session_token,
        {'name': 'Concurrent customer', 'phone': '01012345678', 'address': ''}, branch_id=cls.branch.id)
    cls.wa_account.whatsapp_webhook_enabled = True
    cls.gateway.receive_event(cls.wa_account.code, cls.wa_account.provider_account, {
        'id': 'concurrent-inbound', 'sender': cls.wa.external_key, 'body': 'Synthetic inbound',
        'timestamp': fields.Datetime.to_string(fields.Datetime.now()), 'unsupported': False,
        'source_digest': 'a' * 64,
    })
    uid, token, conversation_id = cls.staff.id, cls.session_token, cls.wa.id
    context = {'allowed_company_ids': cls.staff.company_id.ids, 'ab_chatter_session_token': token}
    env.cr.commit()
    with env.registry.cursor() as first_cursor, env.registry.cursor() as second_cursor:
        first = api.Environment(first_cursor, uid, context)['ab_crm_conversation'].browse(conversation_id)
        second = api.Environment(second_cursor, uid, context)['ab_crm_conversation'].browse(conversation_id)
        assert not second.customer_id
        first._auto_link_matching_customer()
        first_cursor.commit()
        try:
            second._auto_link_matching_customer()
        except SerializationFailure:
            second_cursor.rollback()
        else:
            raise AssertionError('The stale matching transaction was not rejected.')
    with env.registry.cursor() as cursor:
        current = api.Environment(cursor, uid, context)
        conversation = current['ab_crm_conversation'].browse(conversation_id)
        assert not conversation._auto_link_matching_customer()
        assert conversation.customer_id.id == contact['id']
        assert current['ab_crm_identity'].search_count([('channel_id', '=', conversation.channel_id.id), ('external_key', '=', conversation.external_key)]) == 1
        assert current['ab_crm_workspace_audit'].sudo().search_count([('conversation_id', '=', conversation_id), ('action', '=', 'auto_link_customer')]) == 1
    print('Concurrent automatic matching: stale transaction rejected; retry retains one identity and one audit.')
