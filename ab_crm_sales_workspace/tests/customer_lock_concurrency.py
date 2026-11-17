import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from types import MethodType, SimpleNamespace

from odoo import api, fields
from odoo.exceptions import ConcurrencyError, UserError
from odoo.service.model import retrying

from .test_workspace import TestWorkspace


def run(env):
    if env.cr.dbname != 'callcenter_customer_lock_race_20261116':
        raise ValueError('Use the dedicated customer lock concurrency database.')
    source = ast.parse(Path(__file__).with_name('test_workspace.py').read_text())
    fixture = next(node for node in ast.walk(source)
                   if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass')
    cls = SimpleNamespace(env=env)
    exec(compile(ast.Module(body=fixture.body[1:], type_ignores=[]), '<lock-fixture>', 'exec'))
    cls.receive = MethodType(TestWorkspace.receive, cls)
    cls.conversation = MethodType(TestWorkspace.conversation, cls)
    contact = cls.chatter_api.contact_save(cls.session_token, {
        'name': 'Concurrent lock customer', 'phone': '01012345678', 'address': '',
    }, branch_id=cls.branch.id)
    first = cls.conversation()
    received = env['ab_crm_messaging_api'].with_user(cls.service).receive_event(
        cls.account.code, cls.account.provider_account, {
            'id': 'lock-second', 'sender': '54321', 'body': 'Second stream',
            'timestamp': fields.Datetime.to_string(fields.Datetime.now()),
            'unsupported': False, 'source_digest': 'd' * 64,
        })
    second_id = env['ab_crm_message'].browse(received['message_id']).conversation_id.id
    account_id, conversation_id, customer_id = cls.account.id, first.id, contact['id']
    context = {'allowed_company_ids': cls.branch.company_id.ids, 'ab_chatter_session_token': cls.session_token}
    registry, uid = env.registry, cls.staff.id
    env.cr.commit()

    def staff_call(method, record_id, *args):
        with registry.cursor() as cursor:
            current = api.Environment(cursor, uid, context)
            result = getattr(current['ab_crm_conversation'].browse(record_id), method)(*args)
            cursor.commit()
            return result

    def refresh():
        with registry.cursor() as cursor:
            current = api.Environment(cursor, uid, context)
            conversation = current['ab_crm_conversation'].browse(conversation_id)
            assert conversation.workspace_detail()['messages']
            assert conversation.workspace_customer_inbox()['items']
            assert current['ab_crm_chatter_api'].notifications(cls.session_token)['items']
            assert not conversation.customer_id
            cursor.commit()

    with registry.cursor() as locker:
        locking = api.Environment(locker, env.uid, {'allowed_company_ids': cls.branch.company_id.ids})
        locking['ab_crm_messaging_account'].browse(account_id).lock_for_update()
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(refresh).result(timeout=20)
        locker.rollback()
    print('Real account contention: detail, inbox and notifications completed without a lock error or partial link.')

    def overlapping_request(method, preview, expect_stale=False):
        first_conflict = Event()
        attempts = []
        def request():
            with registry.cursor() as cursor:
                current = api.Environment(cursor, uid, context)
                conversation = current['ab_crm_conversation'].browse(conversation_id)
                def deliver():
                    attempts.append(True)
                    try:
                        return getattr(conversation, method)(customer_id, preview['fingerprint'])
                    except ConcurrencyError:
                        first_conflict.set()
                        raise
                result = retrying(deliver, current)
                cursor.commit()
                return result
        with registry.cursor() as locker:
            locking = api.Environment(locker, env.uid, {'allowed_company_ids': cls.branch.company_id.ids})
            account = locking['ab_crm_messaging_account'].browse(account_id)
            account.lock_for_update()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(request)
                try:
                    assert first_conflict.wait(timeout=10), 'The real account lock was not retried.'
                    if expect_stale:
                        account.write({'name': 'Changed account during request retry'})
                        locker.commit()
                finally:
                    locker.rollback()
                if expect_stale:
                    try:
                        future.result(timeout=30)
                    except UserError as error:
                        assert 'Preview it again' in str(error)
                    else:
                        raise AssertionError('A changed preview was accepted after retry.')
                else:
                    future.result(timeout=30)
        assert len(attempts) >= 2
        return len(attempts)

    preview = staff_call('action_preview_customer_link', conversation_id, customer_id)
    link_attempts = overlapping_request('action_confirm_customer_link', preview)
    preview = staff_call('action_preview_customer_link', second_id, customer_id)
    staff_call('action_confirm_customer_link', second_id, customer_id, preview['fingerprint'])
    preview = staff_call('action_preview_customer_unlink', conversation_id, customer_id)
    unlink_attempts = overlapping_request('action_unlink_customer', preview)

    with registry.cursor() as locker:
        locking = api.Environment(locker, env.uid, {'allowed_company_ids': cls.branch.company_id.ids})
        branch = locking['ab_crm_branch'].browse(cls.branch.id)
        branch.lock_for_update()
        original_date = branch.write_date
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(refresh).result(timeout=20)
        branch.invalidate_recordset()
        assert branch.write_date == original_date
        locker.rollback()
    preview = staff_call('action_preview_customer_link', conversation_id, customer_id)
    stale_attempts = overlapping_request('action_confirm_customer_link', preview, expect_stale=True)
    with registry.cursor() as cursor:
        current = api.Environment(cursor, env.uid, {'allowed_company_ids': cls.branch.company_id.ids})
        streams = current['ab_crm_conversation'].browse([conversation_id, second_id])
        assert not streams.customer_id
        identities = current['ab_crm_identity'].with_context(active_test=False).search([
            ('channel_id', '=', cls.channel.id), ('external_key', 'in', streams.mapped('external_key'))])
        assert len(identities) == 2 and not any(identities.mapped('active'))
        audits = current['ab_crm_workspace_audit'].search([('conversation_id', 'in', streams.ids)])
        assert len(audits.filtered(lambda audit: audit.action == 'unlink_customer')) == 2
        assert len(audits.filtered(lambda audit: audit.action in ('auto_link_customer', 'review_customer_link'))) == 2
    print('Real lock retry attempts:', {'link': link_attempts, 'unlink': unlink_attempts, 'stale_preview': stale_attempts})
    print('Unlinked refresh skipped a held branch lock; stale preview was rejected; identities and audits stayed consistent.')
