"""Typed relation planning and private XML-ID snapshots. No ORM or business writes."""
from collections import defaultdict
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import uuid

from psycopg2 import sql
from psycopg2.extras import execute_values
from common import MigrationError, digest
from resume import fingerprint
from csv_plan import present_both
import prepared_progress as progress

POLICY = 'xmlid_unreplicated_relations_v1'
M2M_POLICY = 'm2m_replace_v1'
BATCH = 1000


def endpoints(meta, table):
    result = {}

    def bind(column, model):
        if model not in meta['models']:
            return
        value = dict(model=model, table=meta['models'][model])
        if column in result and result[column] != value:
            raise MigrationError(f'Ambiguous M2M endpoint model: {table}.{column}')
        result[column] = value

    for relation in meta['relations']:
        if relation['table'] == table:
            bind(relation['columns'][0], relation['model'])
            bind(relation['columns'][1], relation.get('related'))
    # Legacy sidecars do not contain comodel names. Inverse declarations or
    # unambiguous FK/model metadata supply the same physical binding.
    for fk in meta.get('fks', []):
        if fk['source_table'] == table and fk['referenced_column'] == 'id':
            column = fk['source_column']
            if column not in result:
                models = [name for name, physical in meta['models'].items() if physical == fk['referenced_table']]
                if len(models) == 1:
                    bind(column, models[0])
    return result


def reference(source, target):
    return dict(source_model=source['model'], target_model=target['model'], table=target['table'])


def endpoint_tables(meta, table):
    """Collect physical candidates without guessing or validating column roles."""
    result = set()
    for relation in meta['relations']:
        if relation['table'] == table:
            for model in (relation['model'], relation.get('related')):
                if model in meta['models']:
                    result.add(meta['models'][model])
    result.update(fk['referenced_table'] for fk in meta.get('fks', [])
                  if fk['source_table'] == table and fk['referenced_column'] == 'id')
    return result


def plan_m2m(source, target, selected, exclusions=None):
    result = {}
    registered = set(source['models'].values()) | set(target['models'].values())
    target_relations = {r['table'] for r in target['relations']}
    candidates = {r['table'] for meta in (source, target) for r in meta['relations']} - registered
    for table in sorted(candidates):
        physical = endpoint_tables(source, table) | endpoint_tables(target, table)
        if not physical & selected.keys():
            continue
        if not present_both(source, target, table, 'm2m', exclusions):
            continue
        missing = []
        for endpoint in sorted(physical):
            present_both(source, target, endpoint, 'endpoint', missing)
        if missing:
            if exclusions is not None:
                exclusions.append(dict(table=table, kind='m2m', existance='both',
                                       reason='endpoint_table_not_both', endpoints=missing))
            continue
        src, dst = endpoints(source, table), endpoints(target, table)
        if (table not in target_relations or len(src) != 2 or src.keys() != dst.keys()
                or any(src[c]['table'] != dst[c]['table'] for c in src)
                or set(source['columns'][table]) != set(target['columns'].get(table, {}))):
            raise MigrationError(f'M2M physical endpoint binding differs: {table}')
        # Column roles, not field names, identify the relationship. Check the
        # column1 owner declaration too, so reversed roles are never guessed.
        owners = {target['models'][r['model']] for r in target['relations'] if r['table'] == table}
        if not owners & {value['table'] for value in src.values()}:
            raise MigrationError(f'M2M owner binding differs: {table}')
        dependencies = sorted({value['table'] for value in src.values()} & selected.keys())
        refs = {col: reference(value, dst[col]) for col, value in src.items() if value['table'] not in selected}
        result[table] = dict(mode='replace', constants={}, references=refs,
                             dependencies=dependencies, relation=True, mapping_policy=POLICY,
                             relation_policy=M2M_POLICY)
    return result


def plan_operations(source, target, selected, exclusions=None, force_tables=()):
    selected = {table: value for table, value in selected.items()
                if present_both(source, target, table, 'model', exclusions)}
    result = {table: dict(mode='replace', constants=value) for table, value in selected.items()}
    for table in set(force_tables) & result.keys():
        result[table]['force_copy'] = True
    target_fields = {(field['table'], field['column']): field for field in target.get('many2one', [])}
    for field in source.get('many2one', []):
        table, column = field['table'], field['column']
        other = target_fields.get((table, column))
        if table not in selected or other is None:
            continue
        if column in selected[table] or target['columns'][table][column]['generated']:
            continue
        src_table = source['models'].get(field['related'])
        dst_table = target['models'].get(other['related'])
        if not src_table or not dst_table:
            raise MigrationError(f'M2O endpoint model/table unavailable: {table}.{column}')
        if src_table in selected or dst_table in selected:
            if src_table != dst_table:
                raise MigrationError(f'Replicated M2O endpoint table differs: {table}.{column}')
            continue
        ref = dict(source_model=field['related'], target_model=other['related'], table=dst_table)
        previous = result[table].setdefault('references', {}).get(column)
        if previous and previous != ref:
            raise MigrationError(f'Ambiguous M2O binding: {table}.{column}')
        result[table]['references'][column] = ref
        result[table]['mapping_policy'] = POLICY
    result.update(plan_m2m(source, target, selected, exclusions))
    return result


def private_sqlite(path):
    connection = sqlite3.connect(path)
    os.chmod(path, 0o600)
    connection.execute('PRAGMA journal_mode=DELETE')
    connection.execute('PRAGMA synchronous=FULL')
    return connection


def seal(connection, path, stage):
    connection.commit()
    connection.close()
    with open(path, 'rb') as file:
        os.fsync(file.fileno())
    return dict(file=Path(path).relative_to(stage).as_posix(), sha256=digest(path), policy=POLICY)


def verified_path(stage, descriptor):
    root = Path(stage).resolve()
    path = (root / descriptor['file']).resolve()
    if (descriptor.get('policy') != POLICY or not path.is_relative_to(root)
            or not path.is_file() or digest(path) != descriptor['sha256']):
        raise MigrationError('Retained XML-ID artifact missing, changed, or incompatible')
    return path


def capture_source(connection, stage, operations):
    models = sorted({ref['source_model'] for op in operations.values() for ref in op.get('references', {}).values()})
    path = Path(stage) / ('source-xmlids-' + uuid.uuid4().hex + '.sqlite')
    db = private_sqlite(path)
    try:
        progress.begin('extract XML-ID metadata', operation='Retain source relationship identities')
        processed = 0
        db.execute('CREATE TABLE aliases(model text,source_id integer,module text,name text,PRIMARY KEY(model,source_id,module,name))')
        if models:
            with connection.cursor(name='csv_xmlids_' + uuid.uuid4().hex) as cr:
                cr.execute('SELECT model,res_id,module,name FROM public.ir_model_data WHERE model=ANY(%s)', [models])
                while True:
                    rows = cr.fetchmany(BATCH)
                    if not rows:
                        break
                    db.executemany('INSERT OR IGNORE INTO aliases VALUES(?,?,?,?)', rows)
                    processed += len(rows)
                    progress.update(processed=processed)
        result = {**seal(db, path, stage), 'models': models}
        progress.finish('source XML-ID metadata retained')
        return result
    except BaseException:
        db.close()
        path.unlink(missing_ok=True)
        raise


def chunks(rows, size=BATCH):
    rows = iter(rows)
    while True:
        batch = []
        for _ in range(size):
            try:
                batch.append(next(rows))
            except StopIteration:
                break
        if not batch:
            return
        yield batch


def record_batches(rows, byte_limit=4 * 1024 * 1024):
    """Bound payload memory too, not just row count (large reports/binaries)."""
    batch, size = [], 0
    for row in rows:
        width = sum(len(value) for value in row)
        if batch and (len(batch) == BATCH or size + width > byte_limit):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += width
    if batch:
        yield batch


def resolve_batch(connection, source, ref, ids):
    """Return one decision per ID; no numeric/name fallback or target writes."""
    decisions = {value: dict(status='missing_source_xmlid', target_id=None) for value in ids}
    if not ids:
        return decisions
    placeholders = ','.join('?' for _ in ids)
    aliases = source.execute(f'SELECT source_id,module,name FROM aliases WHERE model=? AND source_id IN ({placeholders})',
                             [ref['source_model'], *ids])
    candidates, reasons, seen = defaultdict(set), {}, set()
    query = sql.SQL('SELECT v.column1,d.model,d.res_id,t.id FROM (VALUES %s) v '
                    'LEFT JOIN public.ir_model_data d ON d.module=v.column2 AND d.name=v.column3 '
                    'LEFT JOIN public.{} t ON t.id=d.res_id AND d.model={}').format(
                        sql.Identifier(ref['table']), sql.Literal(ref['target_model'])).as_string(connection)
    for batch in chunks(aliases):
        seen.update(row[0] for row in batch)
        with connection.cursor() as cr:
            rows = execute_values(cr, query, batch, template='(%s::bigint,%s::text,%s::text)', fetch=True)
        for source_id, model, target_id, existing in rows:
            if model == ref['target_model'] and existing is not None:
                candidates[source_id].add(target_id)
            else:
                reasons[source_id] = ('missing_target_xmlid' if model is None else 'model_mismatch'
                                      if model != ref['target_model'] else 'missing_target_record')
    for source_id in seen:
        values = candidates[source_id]
        if len(values) == 1:
            decisions[source_id] = dict(status='resolved', target_id=next(iter(values)))
        elif len(values) > 1:
            decisions[source_id] = dict(status='ambiguous', target_id=None)
        else:
            decisions[source_id] = dict(status=reasons.get(source_id, 'missing_target_xmlid'), target_id=None)
    return decisions


def capture_target(connection, stage, source_descriptor, operations):
    """Freeze prepared-target identities BEFORE any selected metadata copy."""
    refs = {fingerprint(ref): ref for op in operations.values() for ref in op.get('references', {}).values()}
    source_path = verified_path(stage, source_descriptor)
    path = Path(stage) / ('target-xmlids-' + uuid.uuid4().hex + '.sqlite')
    db = private_sqlite(path)
    try:
        db.execute('CREATE TABLE decisions(reference text,source_id integer,target_id integer,status text,PRIMARY KEY(reference,source_id))')
        with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source:
            for key, ref in refs.items():
                if ref['source_model'] not in source_descriptor['models']:
                    raise MigrationError('Required source XML-ID model was not retained; use a fresh run')
                ids = source.execute('SELECT DISTINCT source_id FROM aliases WHERE model=?', [ref['source_model']])
                progress.begin('map references', model=ref['target_model'], table=ref['table'],
                               operation='Resolve prepared XML-ID metadata', monitor=True)
                processed = 0
                for batch in chunks(ids):
                    found = resolve_batch(connection, source, ref, [row[0] for row in batch])
                    db.executemany('INSERT INTO decisions VALUES(?,?,?,?)',
                                   [(key, sid, value['target_id'], value['status']) for sid, value in found.items()])
                    processed += len(batch)
                    progress.update(processed=processed)
                progress.finish('prepared XML-ID matches retained')
        return seal(db, path, stage)
    except BaseException:
        db.close()
        path.unlink(missing_ok=True)
        raise


class MappingContext:
    def __init__(self, connection, stage, source_descriptor, target_descriptor, table, spec, columns, check_records=False):
        self.connection, self.stage, self.table = connection, Path(stage), table
        self.check_records = check_records
        self.spec, self.columns = spec, columns
        self.refs = {name: ref for name, ref in spec.get('references', {}).items() if name not in spec['constants']}
        if not set(ref['source_model'] for ref in self.refs.values()) <= set(source_descriptor['models']):
            raise MigrationError('Required source XML-ID metadata was not retained; use a fresh run')
        path = verified_path(stage, source_descriptor)
        target_path = verified_path(stage, target_descriptor)
        self.source = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        self.target = sqlite3.connect(target_path.as_uri() + '?mode=ro', uri=True)
        self.target_descriptor = target_descriptor
        root = self.stage / 'mappings'
        root.mkdir(mode=0o700, exist_ok=True)
        self.path = root / (hashlib.sha256(table.encode()).hexdigest() + '-' + uuid.uuid4().hex + '.sqlite')
        self.db = private_sqlite(self.path)
        self.db.execute('CREATE TABLE decisions(column_name text,source_id integer,target_id integer,status text,PRIMARY KEY(column_name,source_id))')
        self.db.execute('CREATE TABLE issues(kind text,column_name text,source_id integer,record_id integer)')
        self.stats = dict(resolved_references=0, skipped_links=0, missing_references=0, ambiguous_references=0)
        self.closed = False

    def rows(self, rows):
        indexes = {name: self.columns.index(name) for name in self.refs}
        for batch in record_batches(rows):
            decisions = {}
            for name, ref in self.refs.items():
                ids = {int(row[indexes[name]]) for row in batch if row[indexes[name]] != b'\\N'}
                found = {}
                for ids_batch in chunks(sorted(ids)):
                    placeholders = ','.join('?' for _ in ids_batch)
                    cached = self.db.execute(f'SELECT source_id,target_id,status FROM decisions WHERE column_name=? AND source_id IN ({placeholders})',
                                             [name, *ids_batch]).fetchall()
                    found.update({sid: dict(target_id=tid, status=status) for sid, tid, status in cached})
                    pending = [sid for sid in ids_batch if sid not in found]
                    fresh = {sid: dict(status='missing_source_xmlid', target_id=None) for sid in pending}
                    if pending:
                        marks = ','.join('?' for _ in pending)
                        snapshot = self.target.execute(f'SELECT source_id,target_id,status FROM decisions WHERE reference=? AND source_id IN ({marks})',
                                                       [fingerprint(ref), *pending]).fetchall()
                        fresh.update({sid: dict(target_id=tid, status=status) for sid, tid, status in snapshot})
                    resolved = {value['target_id'] for value in fresh.values() if value['status'] == 'resolved'}
                    if resolved and self.check_records:
                        with self.connection.cursor() as cr:
                            cr.execute(sql.SQL('SELECT id FROM public.{} WHERE id=ANY(%s)').format(sql.Identifier(ref['table'])),
                                       [list(resolved)])
                            existing = {row[0] for row in cr}
                        for value in fresh.values():
                            if value['status'] == 'resolved' and value['target_id'] not in existing:
                                value.update(status='missing_target_record', target_id=None)
                    self.db.executemany('INSERT INTO decisions VALUES(?,?,?,?)',
                                        [(name, sid, value['target_id'], value['status']) for sid, value in fresh.items()])
                    found.update(fresh)
                decisions[name] = found
            for row in batch:
                missing = False
                row = list(row)
                for name, index in indexes.items():
                    raw = row[index]
                    if raw == b'\\N' and not self.spec.get('relation'):
                        continue
                    source_id = int(raw) if raw != b'\\N' else None
                    decision = decisions[name].get(source_id, dict(status='missing_source_id', target_id=None))
                    status = decision['status']
                    if status == 'resolved':
                        row[index] = str(decision['target_id']).encode('ascii')
                        self.stats['resolved_references'] += 1
                        continue
                    record_id = int(row[self.columns.index('id')]) if 'id' in self.columns else None
                    self.db.execute('INSERT INTO issues VALUES(?,?,?,?)', (status, name, source_id, record_id))
                    key = 'ambiguous_references' if status == 'ambiguous' else 'missing_references'
                    self.stats[key] += 1
                    if status == 'ambiguous' or not self.spec.get('relation'):
                        raise MigrationError(f'XML-ID {status}: {self.table}.{name}; see mapping artifact')
                    missing = True
                if missing:
                    self.stats['skipped_links'] += 1
                else:
                    yield row

    def finish(self):
        if self.closed:
            raise MigrationError('Mapping context already sealed')
        self.closed = True
        self.source.close()
        self.target.close()
        issues = dict(self.db.execute('SELECT kind,count(*) FROM issues GROUP BY kind'))
        return dict(artifact=seal(self.db, self.path, self.stage), target_snapshot=self.target_descriptor,
                    references=self.refs, stats=self.stats.copy(), issues=issues, policy=POLICY)


def validate_committed(connection, stage, source_descriptor, mapping, metadata_replaced=False):
    source_path = verified_path(stage, source_descriptor)
    path = verified_path(stage, mapping['artifact'])
    verified_path(stage, mapping['target_snapshot'])
    with closing(sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True)) as source, \
            closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as saved:
        for name, ref in mapping['references'].items():
            cursor = saved.execute("SELECT source_id,target_id FROM decisions WHERE column_name=? AND status='resolved'", [name])
            for batch in chunks(cursor):
                if metadata_replaced:
                    # An explicitly replicated ir_model_data table has replaced
                    # the lookup namespaces intentionally. Freeze old decisions
                    # and validate actual endpoint records, never reinterpret.
                    with connection.cursor() as cr:
                        cr.execute(sql.SQL('SELECT id FROM public.{} WHERE id=ANY(%s)').format(sql.Identifier(ref['table'])),
                                   [[row[1] for row in batch]])
                        existing = {row[0] for row in cr}
                    if any(tid not in existing for _, tid in batch):
                        raise MigrationError('Committed mapping target record disappeared')
                else:
                    current = resolve_batch(connection, source, ref, [row[0] for row in batch])
                    if any(current[sid]['status'] != 'resolved' or current[sid]['target_id'] != tid for sid, tid in batch):
                        raise MigrationError('Committed XML-ID mapping changed; refusing to reinterpret copied values')
