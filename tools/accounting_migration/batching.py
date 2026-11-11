"""Indexed keyset batches; no commits, OFFSETs, or Python ID lists."""
from psycopg2 import sql
from common import MigrationError

BATCH_SIZE = 500_000


def bounds(alias, lower, upper):
    column = sql.Identifier(alias, 'id')
    high = sql.SQL('{} <= {}').format(column, sql.Literal(upper))
    return high if lower is None else sql.SQL('{} > {} AND {}').format(column, sql.Literal(lower), high)


def id_batches(execute, fetchone, table, size=BATCH_SIZE):
    if size < 1:
        raise ValueError('Batch size must be positive')
    lower = None
    while True:
        where = sql.SQL('') if lower is None else sql.SQL('WHERE id > {}').format(sql.Literal(lower))
        execute(sql.SQL('SELECT max(id),count(*) FROM (SELECT id FROM {} {} ORDER BY id LIMIT {}) batch').format(
            table, where, sql.Literal(size)))
        upper, count = fetchone()
        if not count:
            return
        if upper is None or (lower is not None and upper <= lower):
            raise MigrationError('Keyset batch did not advance')
        yield lower, upper, count
        lower = upper
