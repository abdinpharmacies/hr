"""Remove dangling links from explicitly eligible M2M relations only."""
import os
from pathlib import Path
import uuid

from psycopg2 import sql
from psycopg2.extras import execute_values
from common import MigrationError, dumps
import prepared_progress as progress

BATCH = 1000


def delete_orphan_links(connection, stage, table, bindings):
    """Caller owns the transaction and commits the checkpoint with these deletes.

    A server cursor finds candidates once. Each bounded DELETE rechecks both
    endpoints and returns only the IDs actually removed for the private audit.
    tableoid + ctid identifies rows safely even on partitioned relation tables.
    """
    columns = sorted(bindings)
    relation = sql.Identifier('public', table)
    with connection.cursor() as cr:
        cr.execute("SELECT conname FROM pg_constraint WHERE contype='f' AND confrelid=%s::regclass "
                   "AND confdeltype IN ('c','n','d') LIMIT 1", [relation.as_string(connection)])
        if cr.fetchone():
            raise MigrationError(f'Incoming cascading FK prevents M2M-only cleanup: {table}')
    orphan = sql.SQL(' OR ').join(
        sql.SQL('NOT EXISTS (SELECT 1 FROM {} e WHERE e.id=r.{})').format(
            sql.Identifier('public', bindings[column]['table']), sql.Identifier(column))
        for column in columns)
    candidates = sql.SQL('SELECT r.tableoid::bigint,r.ctid::text FROM {} r WHERE ({})').format(relation, orphan)
    delete = sql.SQL('DELETE FROM {} r USING (VALUES %s) v(table_oid,row_tid) '
                     'WHERE r.tableoid=v.table_oid AND r.ctid=v.row_tid AND ({}) RETURNING {}').format(
        relation, orphan, sql.SQL(',').join(sql.SQL('r.{}').format(sql.Identifier(column)) for column in columns))
    root = Path(stage) / 'm2m_cleanup'
    root.mkdir(mode=0o700, exist_ok=True)
    path = root / (uuid.uuid4().hex + '.jsonl')
    deleted = 0
    try:
        with open(path, 'w', encoding='utf-8', opener=lambda p, f: os.open(p, f, 0o600)) as audit, \
                connection.cursor(name='csv_orphans_' + uuid.uuid4().hex) as scan:
            scan.itersize = BATCH
            scan.execute(candidates)
            while True:
                batch = scan.fetchmany(BATCH)
                if not batch:
                    break
                with connection.cursor() as cr:
                    rows = execute_values(cr, delete.as_string(connection), batch,
                                          template='(%s::oid,%s::tid)', page_size=BATCH, fetch=True)
                for row in rows:
                    audit.write(dumps(dict(zip(columns, row))) + '\n')
                deleted += len(rows)
                progress.update(processed=deleted)
            if deleted:
                audit.flush()
                os.fsync(audit.fileno())
        result = dict(deleted_links=deleted, endpoints=bindings)
        if deleted:
            result['deleted_ids_file'] = path.relative_to(stage).as_posix()
        else:
            path.unlink()
        return result
    except BaseException:
        path.unlink(missing_ok=True)
        raise
