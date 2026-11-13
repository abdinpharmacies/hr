"""Read-only FK auditing, including definitions saved before failed restorations."""
import re

from psycopg2 import sql
from common import MigrationError, loads

IDENTIFIER = r'(?:"(?:[^"]|"")+"|[a-zA-Z_][a-zA-Z_0-9$]*)'
DEFINITION = re.compile(
    rf'^FOREIGN KEY \((?P<columns>.+?)\) REFERENCES (?P<parent>{IDENTIFIER}(?:\.{IDENTIFIER})?)'
    r'\((?P<parent_columns>.+?)\)(?P<options>.*)$')
OPTIONS = re.compile(r'^(?: MATCH (?:FULL|SIMPLE)| ON (?:UPDATE|DELETE) '
                     r'(?:NO ACTION|RESTRICT|CASCADE|SET NULL|SET DEFAULT)(?: \([^()]+\))?'
                     r'| DEFERRABLE| NOT DEFERRABLE| INITIALLY (?:IMMEDIATE|DEFERRED)| NOT VALID)*$')


def rows(connection, query, params=()):
    with connection.cursor() as cr:
        cr.execute(query, params)
        keys = [item.name for item in cr.description]
        return [dict(zip(keys, row)) for row in cr.fetchall()]


def identifier_list(value):
    tokens = re.findall(IDENTIFIER, value)
    if not re.fullmatch(rf'\s*{IDENTIFIER}(?:\s*,\s*{IDENTIFIER})*\s*', value):
        raise MigrationError('Unsupported saved FK column syntax')
    return [token[1:-1].replace('""', '"') if token.startswith('"') else token for token in tokens]


def saved_definition(item):
    match = DEFINITION.fullmatch(item['definition'])
    if not match or not OPTIONS.fullmatch(match['options']):
        raise MigrationError('Unsupported saved FK definition; manual review required')
    parent = [token[1:-1].replace('""', '"') if token.startswith('"') else token
              for token in re.findall(IDENTIFIER, match['parent'])]
    expected = [item['referenced_schema'], item['referenced_table']]
    if parent not in (expected, expected[1:]):
        raise MigrationError('Saved FK parent differs from its recovery metadata')
    columns, parent_columns = identifier_list(match['columns']), identifier_list(match['parent_columns'])
    if len(columns) != len(parent_columns):
        raise MigrationError('Saved FK has inconsistent composite columns')
    return dict(item, columns=columns, parent_columns=parent_columns,
                match='f' if ' MATCH FULL' in match['options'] else 's', validated=' NOT VALID' not in match['options'])


def key(item):
    return item['source_schema'], item['source_table'], item['name']


def constraints(connection):
    active = rows(connection, """
        SELECT n.nspname AS source_schema,t.relname AS source_table,k.conname AS name,
               rn.nspname AS referenced_schema,rt.relname AS referenced_table,
               pg_get_constraintdef(k.oid) AS definition,k.confmatchtype AS match,k.convalidated AS validated,
               ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY u(num,ord)
                     JOIN pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=u.num ORDER BY ord) AS columns,
               ARRAY(SELECT a.attname FROM unnest(k.confkey) WITH ORDINALITY u(num,ord)
                     JOIN pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=u.num ORDER BY ord) AS parent_columns
        FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        JOIN pg_class rt ON rt.oid=k.confrelid JOIN pg_namespace rn ON rn.oid=rt.relnamespace
        WHERE k.contype='f' AND (n.nspname='public' OR rn.nspname='public')
        ORDER BY n.nspname,t.relname,k.conname"""
    )
    result = {key(item): dict(item, missing=False) for item in active}
    with connection.cursor() as cr:
        cr.execute("SELECT to_regclass('csv_replication.checkpoint')")
        if cr.fetchone()[0]:
            cr.execute("SELECT value FROM csv_replication.checkpoint WHERE name='state'")
            row = cr.fetchone()
            if not row:
                raise MigrationError('CSV recovery checkpoint has no state')
            state = loads(row[0])
            for item in state['constraints']:
                if key(item) not in result:
                    result[key(item)] = dict(saved_definition(item), missing=True)
                elif result[key(item)]['definition'] != item['definition']:
                    result[key(item)]['definition_changed'] = True
    return list(result.values())


def orphan_predicate(item):
    columns = item['columns']
    nonnull = sql.SQL(' AND ').join(sql.SQL('s.{} IS NOT NULL').format(sql.Identifier(c)) for c in columns)
    equal = sql.SQL(' AND ').join(sql.SQL('s.{}=p.{}').format(sql.Identifier(a), sql.Identifier(b))
                                for a, b in zip(columns, item['parent_columns']))
    missing = sql.SQL('({}) AND NOT EXISTS (SELECT 1 FROM {} p WHERE {})').format(
        nonnull, sql.Identifier(item['referenced_schema'], item['referenced_table']), equal)
    if item['match'] == 'f':
        any_null = sql.SQL(' OR ').join(sql.SQL('s.{} IS NULL').format(sql.Identifier(c)) for c in columns)
        any_nonnull = sql.SQL(' OR ').join(sql.SQL('s.{} IS NOT NULL').format(sql.Identifier(c)) for c in columns)
        return sql.SQL('({}) OR (({}) AND ({}))').format(missing, any_null, any_nonnull)
    if item['match'] != 's':
        raise MigrationError('Unsupported FK match policy')
    return missing


def audit_fk(connection, item):
    predicate = orphan_predicate(item)
    relation = sql.Identifier(item['source_schema'], item['source_table'])
    with connection.cursor() as cr:
        cr.execute(sql.SQL('SELECT 1 FROM {} s WHERE {} LIMIT 1').format(relation, predicate))
        if not cr.fetchone():
            return dict(item, orphan_rows=0, sample_ids=[])
        cr.execute(sql.SQL('SELECT count(*) FROM {} s WHERE {}').format(relation, predicate))
        count = cr.fetchone()[0]
        cr.execute(sql.SQL('SELECT DISTINCT {} FROM {} s WHERE {} LIMIT 10').format(
            sql.SQL(',').join(sql.SQL('s.{}').format(sql.Identifier(c)) for c in item['columns']), relation, predicate))
        return dict(item, orphan_rows=count, sample_ids=cr.fetchall())


def audit(connection, timeout_ms=60000):
    result = []
    for number, item in enumerate(constraints(connection), 1):
        with connection.cursor() as cr:
            cr.execute('SAVEPOINT repair_audit')
            try:
                cr.execute('SELECT set_config(%s,%s,true)', ['statement_timeout', str(timeout_ms)])
                entry = audit_fk(connection, item)
            except Exception as exc:
                cr.execute('ROLLBACK TO SAVEPOINT repair_audit')
                entry = dict(item, error_type=type(exc).__name__, sqlstate=getattr(exc, 'pgcode', None))
            finally:
                cr.execute('RELEASE SAVEPOINT repair_audit')
        result.append(entry)
        if number % 100 == 0:
            print(f'FK audit: {number} checked', flush=True)
    return dict(checked=len(result), complete=not any('error_type' in item for item in result),
                constraints=result, user_roles=audit_user_types(connection))


def audit_user_types(connection):
    with connection.cursor() as cr:
        cr.execute("SELECT to_regclass('public.res_groups_users_rel')")
        if not cr.fetchone()[0]:
            return dict(checked=False, reason='User-group relation is unavailable')
        cr.execute("SELECT count(DISTINCT name) FROM ir_model_data WHERE module='base' AND model='res.groups' "
                   "AND name IN ('group_user','group_portal','group_public')")
        if cr.fetchone()[0] != 3:
            return dict(checked=False, reason='Core user-type XML IDs are incomplete')
        cr.execute("SELECT count(*) FROM (SELECT r.uid FROM res_groups_users_rel r JOIN ir_model_data d "
                   "ON d.model='res.groups' AND d.res_id=r.gid WHERE d.module='base' "
                   "AND d.name IN ('group_user','group_portal','group_public') "
                   "GROUP BY r.uid HAVING count(DISTINCT r.gid)>1) conflicts")
        return dict(checked=True, conflicting_users=cr.fetchone()[0])
