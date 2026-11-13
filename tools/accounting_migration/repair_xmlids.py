"""Installed-module alias repair using recorded source-ID copies, never names."""
from collections import Counter, defaultdict
import uuid

from psycopg2 import sql
from common import MigrationError, loads
from csv_plan import table_overrides
from repair_audit import rows

BATCH = 500
CORE_MODELS = {'res.users', 'res.partner'}


def batches(values):
    values = list(values)
    for start in range(0, len(values), BATCH):
        yield values[start:start + BATCH]


def streamed(connection, query, params=()):
    with connection.cursor(name='repair_aliases_' + uuid.uuid4().hex) as cr:
        cr.itersize = BATCH
        cr.execute(query, params)
        while True:
            batch = cr.fetchmany(BATCH)
            if not batch:
                break
            names = [item.name for item in cr.description]
            for record in batch:
                yield dict(zip(names, record))


def model_tables(connection, config=None):
    installed = {r['name'] for r in rows(connection, "SELECT name FROM ir_module_module WHERE state='installed'")}
    overrides = table_overrides(config, installed) if config else {}
    tables = {r['table_name'] for r in rows(connection, """SELECT c.relname AS table_name FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_attribute a ON a.attrelid=c.oid
        WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attname='id'
          AND a.atttypid IN ('int2'::regtype,'int4'::regtype,'int8'::regtype) AND NOT a.attisdropped"""
    )}
    models = {}
    for record in rows(connection, 'SELECT model,transient FROM ir_model ORDER BY model'):
        table = overrides.get(record['model'], record['model'].replace('.', '_'))
        if not record['transient'] and table in tables:
            models[record['model']] = table
    return installed, models


def copy_evidence(connection, identities):
    """Follow the active archive chain oldest-first; count skips prove nothing."""
    with connection.cursor() as cr:
        cr.execute("SELECT to_regclass('csv_replication.checkpoint')")
        if not cr.fetchone()[0]:
            return {}, []
    try:
        records = {r['name']: loads(r['value']) for r in rows(connection,
            "SELECT name,value FROM csv_replication.checkpoint WHERE name='state' OR name LIKE %s", ['archive:%'])}
    except (ValueError, TypeError):
        return {}, [dict(reason='malformed_checkpoint_json')]
    chain, seen, name = [], set(), 'state'
    while name:
        if not isinstance(name, str) or name in seen or name not in records:
            return {}, [dict(reason='invalid_checkpoint_archive_chain')]
        seen.add(name)
        state = records[name]
        if not isinstance(state, dict) or not isinstance(state.get('operations'), dict):
            return {}, [dict(reason='invalid_checkpoint_operations')]
        chain.append((name, state))
        name = state.get('previous_checkpoint')
    evidence = {}
    for name, state in reversed(chain):
        for table, operation in state['operations'].items():
            if not isinstance(operation, dict) or not operation.get('success'):
                continue
            status = operation.get('status')
            if status == 'verified_existing':
                continue
            copied = operation.get('rows')
            fingerprint = operation.get('fingerprint')
            legacy = (state.get('format') == 3 and status is None and type(copied) is int and copied > 0
                      and isinstance(fingerprint, str) and len(fingerprint) == 64
                      and all(c in '0123456789abcdef' for c in fingerprint))
            replacement = operation.get('mode') == 'replace' and (legacy or status in ('copied', 'forced_copy'))
            if not replacement:
                # Unknown successful replacements must not inherit older proof.
                if operation.get('mode') == 'replace' and status != 'm2m_replaced':
                    evidence.pop(table, None)
                continue
            evidence.pop(table, None)
            valid_counts = (type(copied) is int and type(operation.get('expected')) is int
                            and type(operation.get('target_count')) is int and copied >= 0 and copied == operation.get('expected')
                            and copied == operation.get('target_count'))
            if (identities and state.get('format') in (3, 4) and state.get('identities') == identities and valid_counts):
                evidence[table] = dict(checkpoint=name, format=state['format'], rows=copied,
                                       policy='committed_source_id_replacement')
    return evidence, []


def existing_ids(connection, table, ids):
    found = set()
    for batch in batches(sorted({value for value in ids if type(value) is int})):
        found.update(r['id'] for r in rows(connection, sql.SQL('SELECT id FROM {} WHERE id=ANY(%s)').format(
            sql.Identifier('public', table)), [batch]))
    return found


def one(connection, query, params):
    result = rows(connection, query, params)
    if len(result) != 1:
        raise MigrationError('Core identity is missing or ambiguous')
    return result[0]


def verify_core(source, target, alias):
    rid = alias['res_id']
    if alias['model'] == 'res.users':
        original = one(source, 'SELECT id,login,partner_id FROM res_users WHERE id=%s', [rid])
        if one(target, 'SELECT id,login,partner_id FROM res_users WHERE id=%s', [rid]) != original:
            raise MigrationError('Core user ID/login/partner association differs')
    else:
        one(source, 'SELECT id FROM res_partner WHERE id=%s', [rid])
        one(target, 'SELECT id FROM res_partner WHERE id=%s', [rid])
        users = rows(source, 'SELECT id,login,partner_id FROM res_users WHERE partner_id=%s', [rid])
        companies = rows(source, 'SELECT id,partner_id FROM res_company WHERE partner_id=%s', [rid])
        if not users and not companies:
            raise MigrationError('Core partner has no verified user/company association')
        for record in users:
            if one(target, 'SELECT id,login,partner_id FROM res_users WHERE id=%s', [record['id']]) != record:
                raise MigrationError('Core partner user association differs')
        for record in companies:
            if one(target, 'SELECT id,partner_id FROM res_company WHERE id=%s', [record['id']]) != record:
                raise MigrationError('Core partner company association differs')
    return dict(policy='verified_core_identity')


def build(source, target, context=None):
    context = context or {}
    installed, target_models = model_tables(target, context.get('target_config'))
    _, source_models = model_tables(source, context.get('source_config'))
    installed = sorted(name for name in installed if not name.startswith('__'))
    evidence, history_issues = copy_evidence(target, context.get('identities'))
    columns = 'module,name,model,res_id,noupdate'
    query = f'SELECT {columns} FROM ir_model_data WHERE module=ANY(%s) ORDER BY model,module,name'
    originals = list(streamed(source, query, [installed]))
    current = {(r['module'], r['name']): r for r in streamed(target, 'SELECT id,' + query[7:], [installed])}
    source_keys = {(r['module'], r['name']) for r in originals}
    grouped = defaultdict(list)
    for alias in originals:
        grouped[alias['model']].append(alias)
    report = dict(changes=[], unresolved=list(history_issues), skipped=[], modules={},
                  installed_modules=len(installed), installed_module_names=installed,
                  source_aliases=len(originals), target_aliases=len(current))
    counts = defaultdict(Counter)
    verified_portal = None

    def finding(alias, reason, *, skip=False):
        report['skipped' if skip else 'unresolved'].append(dict(module=alias['module'], name=alias['name'],
                                                              model=alias['model'], source_id=alias['res_id'], reason=reason))
        counts[alias['module']]['skipped' if skip else 'unresolved'] += 1

    for model, aliases in sorted(grouped.items()):
        src_table, dst_table = source_models.get(model), target_models.get(model)
        source_ids = existing_ids(source, src_table, [a['res_id'] for a in aliases]) if src_table else set()
        target_ids = existing_ids(target, dst_table, [a['res_id'] for a in aliases]) if dst_table else set()
        for alias in aliases:
            counts[alias['module']]['checked'] += 1
            before = current.get((alias['module'], alias['name']))
            same = bool(before and before['model'] == model and before['res_id'] == alias['res_id'])
            if before and before['model'] != model:
                finding(alias, 'xmlid_model_conflict')
                continue
            if not src_table or not dst_table or src_table != dst_table:
                finding(alias, 'model_table_unavailable_or_changed', skip=same)
                continue
            core = alias['module'] == 'base' and model in CORE_MODELS
            if not core and not same and src_table not in evidence:
                finding(alias, 'no_verified_source_id_copy')
                continue
            if alias['res_id'] not in source_ids:
                finding(alias, 'source_record_missing')
                continue
            if alias['res_id'] not in target_ids:
                finding(alias, 'target_destination_missing')
                continue
            if core:
                try:
                    proof = verify_core(source, target, alias)
                except MigrationError as exc:
                    finding(alias, str(exc))
                    continue
                if model == 'res.users' and alias['name'] == 'template_portal_user_id':
                    verified_portal = alias['res_id']
            elif same:
                counts[alias['module']]['unchanged'] += 1
                continue
            else:
                proof = evidence.get(src_table)
                if not proof:
                    finding(alias, 'no_verified_source_id_copy')
                    continue
            if same:
                counts[alias['module']]['unchanged'] += 1
            else:
                after = dict(alias, noupdate=before['noupdate']) if before else alias
                report['changes'].append(dict(kind='alias', group_model=model, before=before, after=after, evidence=proof))
                counts[alias['module']]['repairs'] += 1
    for alias_key, alias in sorted(current.items()):
        if alias_key not in source_keys:
            finding(alias, 'source_alias_missing_target_preserved')
    if verified_portal is not None:
        user = one(target, 'SELECT id,login,active FROM res_users WHERE id=%s', [verified_portal])
        if user['login'] == 'portaltemplate' and not user['active']:
            configs = rows(target, 'SELECT id,key,value FROM ir_config_parameter WHERE key=%s', ['base.template_portal_user_id'])
            if len(configs) > 1:
                report['unresolved'].append(dict(model='res.users', reason='ambiguous_portal_configuration'))
            elif not configs or configs[0]['value'] != str(verified_portal):
                report['changes'].append(dict(kind='config', group_model='res.users', before=configs[0] if configs else None,
                                             after=dict(key='base.template_portal_user_id', value=str(verified_portal))))
        else:
            report['unresolved'].append(dict(model='res.users', reason='portal_template_identity_changed'))
    report['modules'] = {module: dict(values) for module, values in sorted(counts.items())}
    report['model_changes'] = dict(Counter(c['group_model'] for c in report['changes']))
    return report
