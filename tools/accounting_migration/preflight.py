"""Read-only compatibility checks before copying millions of rows."""
from psycopg2 import sql
from common import AUDIT, EXCLUDED, LOOKUPS, TECHNICAL, property_blockers
from importer import ATTACHMENT_INTERNAL, FRAMEWORK_FIELDS, USER_INTERNAL
from adapters import adapted_fields, OBSOLETE, ZERO_ONLY


def compare(con, inventory, target, rules):
    blockers, visited = set(), set()
    pending = list(inventory['roots']) + ['res.users', 'res.company']
    def exists(table, condition, params=()):
        with con.cursor() as cr:
            cr.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} WHERE ').format(sql.Identifier(table)) + condition + sql.SQL(')'), params)
            return cr.fetchone()[0]
    while pending:
        model = pending.pop()
        if model in visited or model in EXCLUDED or model in LOOKUPS: continue
        visited.add(model)
        src = inventory['models'].get(model)
        if not src or src['transient'] or src['table_kind'] != 'r': continue
        if not exists(src['table'], sql.SQL('true')): continue
        dst = target.get(rules['models'].get(model, model))
        if not dst:
            blockers.add(f'Missing target model: {model}'); continue
        for child, inverse in rules.get('inverse_links', {}).get(model, {}).items():
            if child in inventory['models'] and exists(inventory['models'][child]['table'], sql.SQL('{} IS NOT NULL').format(sql.Identifier(inverse))):
                pending.append(child)
        for fn, sf in src['fields'].items():
            if sf.get('relation') in EXCLUDED: continue
            if sf['ttype'] == 'many2one' and fn in src['columns'] and not sf['related']:
                if exists(src['table'], sql.SQL('{} IS NOT NULL').format(sql.Identifier(fn))): pending.append(sf['relation'])
            if sf['ttype'] == 'many2many' and sf.get('relation_table') and not sf['related']:
                if exists(sf['relation_table'], sql.SQL('true')): pending.append(sf['relation'])
            if fn in AUDIT | TECHNICAL | FRAMEWORK_FIELDS: continue
            if model == 'res.users' and fn in USER_INTERNAL: continue
            if model == 'ir.attachment' and fn in ATTACHMENT_INTERNAL: continue
            if rules['ignore_fields'].get(model, {}).get(fn): continue
            if fn in adapted_fields(model): continue
            if fn not in src['columns']: continue
            tn = rules['fields'].get(model, {}).get(fn, fn)
            tf = dst['fields'].get(tn)
            issue = None
            if not tf: issue = f'Missing populated field: {model}.{fn}'
            elif sf['ttype'] != tf['type'] and {sf['ttype'], tf['type']} != {'char', 'text'}:
                issue = f'Field type mismatch: {model}.{fn} ({sf["ttype"]} -> {tf["type"]})'
            if issue and exists(src['table'], sql.SQL('{} IS NOT NULL').format(sql.Identifier(fn))): blockers.add(issue)
    for model, fields in ZERO_ONLY.items():
        for field in fields:
            if exists(inventory['models'][model]['table'], sql.SQL('{} IS NOT NULL AND {} <> 0').format(sql.Identifier(field), sql.Identifier(field))):
                blockers.add(f'Nonzero legacy field needs mapping: {model}.{field}')
    if exists('res_partner', sql.SQL("NULLIF(mobile,'') IS NOT NULL AND NULLIF(phone,'') IS NOT NULL AND mobile <> phone")):
        blockers.add('Conflicting phone/mobile: res.partner')
    if exists('ab_store', sql.SQL('user_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM ab_hr_department d WHERE d.store_id=ab_store.id AND d.user_id=ab_store.user_id)')):
        blockers.add('Store user is not preserved by HR department: ab_store.user_id')
    blockers.update(property_blockers(con, visited))
    return {'checked_models': sorted(visited), 'blockers': sorted(blockers), 'passed': not blockers,
            'excluded_preferences': OBSOLETE, 'conditional_adapters': ['zero-only legacy fields', 'mobile to phone', 'store user via HR department']}
