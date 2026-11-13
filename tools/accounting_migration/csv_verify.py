"""Count-only CSV verification. No row hashes, type projection, or SQLite scans."""
from psycopg2 import sql

POLICY = 'csv_count_v1'


def target_count(connection, table):
    with connection.cursor() as cr:
        cr.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)))
        return cr.fetchone()[0]


def compare(connection, stage, table, file_meta, columns, spec, mapper=None):
    expected = file_meta['rows']
    actual = target_count(connection, table)
    matches = actual == expected
    return dict(policy=POLICY, matches=matches, expected=dict(rows=expected), actual=dict(rows=actual),
                reason='count_matches' if matches else 'count_differs')


def verify_after(connection, stage, table, columns, spec, previous, copied_rows=0):
    expected = copied_rows if spec.get('relation') else previous['expected']['rows']
    actual = target_count(connection, table)
    return dict(policy=POLICY, matches=actual == expected, expected=dict(rows=expected), actual=dict(rows=actual),
                reason='count_matches' if actual == expected else 'count_differs')
