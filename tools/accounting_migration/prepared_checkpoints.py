"""Shared checkpoint I/O; callers own database transactions."""
from psycopg2 import sql
from common import dumps, loads

META = 'prepared_custom_migration'


def read_checkpoint(connection, name):
    with connection.cursor() as cr:
        cr.execute('SELECT to_regclass(%s)', [META + '.checkpoint'])
        if cr.fetchone()[0] is None:
            return None
        cr.execute(sql.SQL('SELECT value FROM {} WHERE name=%s').format(sql.Identifier(META, 'checkpoint')), [name])
        row = cr.fetchone()
        return loads(row[0]) if row else None


def write_checkpoint(connection, name, value):
    with connection.cursor() as cr:
        cr.execute(sql.SQL('INSERT INTO {} VALUES (%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value').format(
            sql.Identifier(META, 'checkpoint')), [name, dumps(value)])


def read_all(connection):
    if read_checkpoint(connection, 'run') is None:
        return {}
    with connection.cursor() as cr:
        cr.execute(sql.SQL('SELECT name,value FROM {}').format(sql.Identifier(META, 'checkpoint')))
        return {name: loads(value) for name, value in cr.fetchall()}
