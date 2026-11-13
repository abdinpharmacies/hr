"""Bounded repair plans. None of these handlers are called by the importer."""
from psycopg2 import sql
from psycopg2.extras import Json

from common import MigrationError
from repair_audit import rows, constraints, key, saved_definition, audit_fk

LABELS = {'identities': 'Installed-module XML IDs and portal configuration',
          'payments': 'HR payment types (IDs 1–4)', 'reports': 'HR report field references',
          'discuss': 'Dangling Discuss membership 1538', 'foreign_keys': 'Restore missing foreign keys'}


def fetch(connection, query, params=()):
    found = rows(connection, query, params)
    if len(found) != 1:
        raise MigrationError('Repair identity is missing or ambiguous')
    return found[0]


def identities(source, target, context=None):
    from repair_xmlids import build
    return build(source, target, context)


def payments(source, target):
    original = rows(source, 'SELECT id,name FROM ab_hr_payment_type ORDER BY id')
    if [r['id'] for r in original] != [1, 2, 3, 4] or any(not isinstance(r['name'], str) for r in original):
        raise MigrationError('Payment-type source differs from the reviewed four-record repair')
    types = rows(target, "SELECT data_type FROM information_schema.columns WHERE table_schema='public' "
                 "AND table_name='ab_hr_payment_type' AND column_name='name'")
    if types != [{'data_type': 'jsonb'}]:
        raise MigrationError('Payment-type target name is not translated JSONB')
    changes = []
    for record in original:
        current = rows(target, 'SELECT id,name FROM ab_hr_payment_type WHERE id=%s', [record['id']])
        before = current[0] if current else None
        if before and (not isinstance(before['name'], dict) or before['name'].get('en_US') not in (None, record['name'])):
            raise MigrationError('Payment-type ID has a conflicting name; manual review required')
        name = dict(before['name'] if before else {}, en_US=record['name'])
        after = dict(id=record['id'], name=name)
        if before != after:
            changes.append(dict(kind='payment', before=before, after=after))
    return changes


def mapped_field(source, target, source_id):
    original = fetch(source, 'SELECT model,name FROM ir_model_fields WHERE id=%s', [source_id])
    if original['model'] != 'ab_hr_emp_history' or original['name'] not in ('action_date', 'notes'):
        raise MigrationError('Report field is outside the reviewed repair')
    aliases = rows(source, "SELECT module,name FROM ir_model_data WHERE model='ir.model.fields' AND res_id=%s", [source_id])
    candidates = set()
    for alias in aliases:
        matches = rows(target, "SELECT d.res_id,f.model,f.name FROM ir_model_data d JOIN ir_model_fields f ON f.id=d.res_id "
                       "WHERE d.module=%s AND d.name=%s AND d.model='ir.model.fields'", [alias['module'], alias['name']])
        for match in matches:
            if match['model'] != original['model'] or match['name'] != original['name']:
                raise MigrationError('Report field XML-ID points to a different field')
            candidates.add(match['res_id'])
    if len(candidates) != 1:
        raise MigrationError('Report field has no unambiguous shared XML-ID mapping')
    return candidates.pop(), original


def reports(source, target):
    original = rows(source, 'SELECT id,target_field_id FROM ab_hr_report_model WHERE target_field_id IS NOT NULL ORDER BY id')
    changes = []
    for record in original:
        current = fetch(target, 'SELECT id,target_field_id FROM ab_hr_report_model WHERE id=%s', [record['id']])
        mapped, field = mapped_field(source, target, record['target_field_id'])
        if current['target_field_id'] == mapped:
            continue
        if current['target_field_id'] != record['target_field_id']:
            raise MigrationError('Report reference changed since import; manual review required')
        changes.append(dict(kind='report', before=current, after=dict(id=record['id'], target_field_id=mapped), field=field))
    return changes


def discuss(source, target):
    current = rows(target, 'SELECT * FROM discuss_channel_member WHERE id=1538')
    if not current:
        return []
    record = current[0]
    if record['partner_id'] != 9429:
        raise MigrationError('Discuss membership no longer matches the reviewed orphan')
    for connection in (source, target):
        if rows(connection, 'SELECT id FROM res_partner WHERE id=9429'):
            raise MigrationError('Discuss partner now exists; membership will be preserved')
    # Even CASCADE/SET NULL must not change another row. An unused incoming
    # constraint is harmless; an actual referencing row blocks this repair.
    incoming = rows(target, """SELECT n.nspname AS schema,t.relname AS table,
        ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY u(num,ord)
              JOIN pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=u.num ORDER BY ord) AS columns,
        ARRAY(SELECT a.attname FROM unnest(k.confkey) WITH ORDINALITY u(num,ord)
              JOIN pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=u.num ORDER BY ord) AS parent_columns
        FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE k.contype='f' AND k.confrelid='discuss_channel_member'::regclass"""
    )
    for item in incoming:
        predicate = sql.SQL(' AND ').join(sql.SQL('{}=%s').format(sql.Identifier(c)) for c in item['columns'])
        if rows(target, sql.SQL('SELECT 1 FROM {} WHERE {} LIMIT 1').format(
                sql.Identifier(item['schema'], item['table']), predicate), [record[c] for c in item['parent_columns']]):
            raise MigrationError('Discuss membership has referencing rows; cascading changes are forbidden')
    return [dict(kind='discuss', before=record, after=None)]


PLANNERS = dict(identities=identities, payments=payments, reports=reports, discuss=discuss)


def plan_fixes(source, target, audit, context=None):
    result = {}
    for name, planner in PLANNERS.items():
        with target.cursor() as tc, source.cursor() as sc:
            tc.execute('SAVEPOINT plan_fix')
            sc.execute('SAVEPOINT plan_fix')
            try:
                result[name] = planner(source, target, context) if name == 'identities' else dict(changes=planner(source, target))
            except Exception as exc:
                tc.execute('ROLLBACK TO SAVEPOINT plan_fix')
                sc.execute('ROLLBACK TO SAVEPOINT plan_fix')
                result[name] = dict(error=str(exc) if isinstance(exc, MigrationError) else type(exc).__name__)
            finally:
                tc.execute('RELEASE SAVEPOINT plan_fix')
                sc.execute('RELEASE SAVEPOINT plan_fix')
    result['foreign_keys'] = dict(changes=[dict(kind='foreign_key', before=None, after=item)
                                          for item in audit['constraints'] if item['missing']])
    return result


def apply_data(connection, changes):
    with connection.cursor() as cr:
        for change in changes:
            before, after, kind = change['before'], change['after'], change['kind']
            if kind == 'alias':
                if before:
                    cr.execute('UPDATE ir_model_data SET res_id=%s WHERE id=%s AND module=%s AND name=%s AND model=%s AND res_id=%s AND noupdate IS NOT DISTINCT FROM %s',
                               [after['res_id']] + [before[k] for k in ('id','module','name','model','res_id','noupdate')])
                else:
                    cr.execute('INSERT INTO ir_model_data(module,name,model,res_id,noupdate) VALUES(%s,%s,%s,%s,%s)',
                               [after[k] for k in ('module', 'name', 'model', 'res_id', 'noupdate')])
            elif kind == 'config':
                if before:
                    cr.execute('UPDATE ir_config_parameter SET value=%s WHERE id=%s', [after['value'], before['id']])
                else:
                    cr.execute('INSERT INTO ir_config_parameter(key,value) VALUES(%s,%s)', [after['key'], after['value']])
            elif kind == 'payment':
                if before:
                    cr.execute('UPDATE ab_hr_payment_type SET name=%s WHERE id=%s', [Json(after['name']), after['id']])
                else:
                    cr.execute('INSERT INTO ab_hr_payment_type(id,name) VALUES(%s,%s)', [after['id'], Json(after['name'])])
            elif kind == 'report':
                cr.execute('UPDATE ab_hr_report_model SET target_field_id=%s WHERE id=%s', [after['target_field_id'], after['id']])
            elif kind == 'discuss':
                cr.execute('DELETE FROM discuss_channel_member WHERE id=%s AND partner_id=%s', [before['id'], before['partner_id']])
            else:
                raise MigrationError('Unsupported repair operation')
            if cr.rowcount != 1:
                raise MigrationError('Repair affected an unexpected number of rows')
    if any(c['kind'] == 'payment' for c in changes):
        from csv_copy import restart_sequence
        with connection.cursor() as cr:
            cr.execute("SELECT pg_get_serial_sequence('public.ab_hr_payment_type','id')")
            sequence = cr.fetchone()[0]
        restart_sequence(connection, 'ab_hr_payment_type', {'id': {'sequence': sequence}}, only_advance=True)


def restore_fk(connection, item):
    parsed = saved_definition(item)
    current = {key(i): i for i in constraints(connection)}.get(key(item))
    if not current or current['definition'] != item['definition'] or current.get('definition_changed'):
        raise MigrationError('FK definition changed since preview')
    if not current['missing']:
        return
    checked = audit_fk(connection, parsed)
    if checked['orphan_rows']:
        raise MigrationError('FK restoration blocked by remaining orphan references')
    with connection.cursor() as cr:
        cr.execute("SET LOCAL lock_timeout='5s'")
        cr.execute(sql.SQL('ALTER TABLE {} ADD CONSTRAINT {} {}').format(
            sql.Identifier(item['source_schema'], item['source_table']), sql.Identifier(item['name']),
            sql.SQL(parsed['definition'])))
