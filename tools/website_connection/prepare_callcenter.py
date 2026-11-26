import json
import os
from uuid import UUID


def prepare(env, base_code, target_code, source, apply=False, expected_base_source=None):
    if env.cr.dbname != 'callcenter' and not env.cr.dbname.startswith('two_server_qa_'):
        raise ValueError('Only the local callcenter or a dedicated QA database is supported')
    if not (env.su or env.user.has_group('base.group_system')):
        raise ValueError('A system administrator is required')
    if str(UUID(source)) != source or base_code == target_code:
        raise ValueError('Invalid connection identity')
    accounts = env['ab_crm_messaging_account']
    base = accounts.search([('code', '=', base_code)], limit=1)
    if not base or base.provider != 'website':
        raise ValueError('The existing Website connection was not found')
    if expected_base_source and base.provider_account != expected_base_source:
        raise ValueError('The existing source mapping changed; review before proceeding')
    if base.provider_account == source:
        raise ValueError('The existing connection already uses this source')
    base._check_mapping()
    if not base.legacy_worker_disabled:
        raise ValueError('The previous worker must already be disabled')
    before = base.read(['code', 'provider_account', 'channel_id', 'service_user_id',
        'branch_id', 'company_id', 'active', 'enabled', 'outgoing_enabled'])[0]
    accounts = accounts.with_context(allowed_company_ids=base.company_id.ids)
    account = accounts.search([('provider', '=', 'website'), ('provider_account', '=', source)], limit=1)
    by_code = accounts.search([('code', '=', target_code)], limit=1)
    if by_code and by_code != account:
        raise ValueError('The requested code already belongs to a different source')
    channel = env['ab_crm_channel'].with_context(allowed_company_ids=base.company_id.ids).search([
        ('code', '=', target_code)], limit=1)
    if channel and (channel.provider != 'website' or channel.branch_id != base.branch_id
            or channel.company_id != base.company_id):
        raise ValueError('The channel scope does not match the existing connection')
    if account and (account.code != target_code or account.branch_id != base.branch_id
            or account.company_id != base.company_id or account.service_user_id != base.service_user_id
            or account.channel_id != channel):
        raise ValueError('The existing source requires a separate reviewed configuration')
    created = False
    if not account and apply:
        if not channel:
            channel = env['ab_crm_channel'].with_context(allowed_company_ids=base.company_id.ids).create({
                'name': 'Production Website (current)', 'code': target_code, 'provider': 'website',
                'branch_id': base.branch_id.id, 'company_id': base.company_id.id})
        account = accounts.create({'name': 'Production Website (current)', 'code': target_code,
            'provider': 'website', 'provider_account': source, 'channel_id': channel.id,
            'branch_id': base.branch_id.id, 'company_id': base.company_id.id,
            'service_user_id': base.service_user_id.id, 'active': True, 'enabled': False,
            'outgoing_enabled': False, 'legacy_worker_disabled': True})
        created = True
    if account:
        account._check_mapping()
    assert base.read(list(before.keys() - {'id'}))[0] == before
    return {'account_code': target_code, 'source': source, 'created': created,
        'present': bool(account), 'enabled': bool(account.enabled) if account else False,
        'outgoing_enabled': bool(account.outgoing_enabled) if account else False,
        'base_account_unchanged': True, 'company': base.company_id.name,
        'branch': base.branch_id.name, 'service_user': base.service_user_id.name}


if 'env' in globals():
    apply = os.environ.get('WEBSITE_CONNECTION_APPLY') == '1'
    result = prepare(env, os.environ.get('WEBSITE_BASE_ACCOUNT', 'website-production'),
        os.environ.get('WEBSITE_NEW_ACCOUNT', 'website-production-reinstalled'),
        os.environ.get('WEBSITE_SOURCE_UUID', '62c18ac9-3a5b-472d-a75c-86d8edb575f5'),
        apply=apply, expected_base_source=os.environ.get('WEBSITE_BASE_SOURCE',
            'a4e63f7a-c5d5-4d13-927b-0a40c287253f'))
    if apply:
        env.cr.commit()
    print(json.dumps(result, indent=2))
