"""Retained PostgreSQL text COPY, streaming projection, and durable fingerprints."""
import hashlib
import io
import os
from pathlib import Path

from psycopg2 import sql
from psycopg2.extras import Json
from common import MigrationError, digest, save_json
import prepared_progress as progress


class HashSink:
    def __init__(self, file=None):
        self.file = file
        self.hash = hashlib.sha256()
        self.bytes = 0

    def write(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.hash.update(data)
        self.bytes += len(data)
        if self.file is not None:
            self.file.write(data)


def extract(connection, directory, operations, source, target):
    directory = Path(directory)
    directory.mkdir(mode=0o700, exist_ok=True)
    with connection.cursor() as cr:
        cr.execute('SELECT transaction_timestamp()::text,txid_current_snapshot()::text')
        stamp, snapshot = cr.fetchone()
    manifest = dict(complete=False, snapshot=snapshot, time=stamp, tables={})
    save_json(directory.parent / 'csv-extraction.json', manifest)
    for table in sorted(operations):
        columns = [name for name in source['columns'][table]
                   if name in target['columns'][table] and not target['columns'][table][name]['generated']]
        if not columns:
            raise MigrationError(f'No insertable shared columns: {table}')
        filename = hashlib.sha256(table.encode()).hexdigest() + '.copy'
        progress.begin('extract', table=table, operation='Retain source COPY')
        with connection.cursor() as cr, open(directory / filename, 'wb',
                opener=lambda p, f: os.open(p, f, 0o600)) as file:
            sink = HashSink(file)
            cr.copy_expert(sql.SQL("COPY (SELECT {} FROM public.{}) TO STDOUT WITH (FORMAT text, ENCODING 'UTF8')").format(
                sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(table)).as_string(connection), sink)
            rows = cr.rowcount
            file.flush()
            os.fsync(file.fileno())
        manifest['tables'][table] = dict(file=filename, columns=columns, rows=rows,
                                         bytes=sink.bytes, sha256=sink.hash.hexdigest())
        save_json(directory.parent / 'csv-extraction.json', manifest)
        progress.finish('source file retained')
    manifest['complete'] = True
    from csv_relations import capture_source, POLICY
    manifest['xmlids'] = capture_source(connection, directory.parent, operations)
    manifest['mapping_policy'] = POLICY
    manifest['relation_metadata'] = {
        name: {key: meta.get(key, [] if key != 'models' else {})
               for key in ('models', 'relations', 'many2one', 'fks')}
        for name, meta in (('source', source), ('target', target))}
    save_json(directory.parent / 'csv-extraction.json', manifest)
    return manifest


def verify_files(stage, manifest):
    if not manifest.get('complete'):
        raise MigrationError('Original complete CSV extraction is required')
    root = (Path(stage) / 'tables').resolve()
    for table, meta in manifest['tables'].items():
        path = (root / meta['file']).resolve()
        if path.parent != root or not path.is_file() or path.stat().st_size != meta['bytes'] or digest(path) != meta['sha256']:
            raise MigrationError(f'Retained CSV extraction changed: {table}')
    if manifest.get('xmlids'):
        from csv_relations import verified_path
        verified_path(stage, manifest['xmlids'])


def constant_fields(connection, constants, target):
    if not constants:
        return {}
    names, values, expressions = [], [], []
    for name, value in constants.items():
        names.append(name)
        kind = target[name]['type']
        if kind in ('json', 'jsonb') and value is not None:
            value = Json(value)
        values.append(value)
        # Types come from the bound PostgreSQL catalog, never from CSV cells.
        expressions.append(sql.SQL('%s::{}').format(sql.SQL(kind)))
    query = sql.SQL('COPY (SELECT {}) TO STDOUT').format(sql.SQL(',').join(expressions))
    out = io.BytesIO()
    with connection.cursor() as cr:
        cr.copy_expert(cr.mogrify(query, values).decode('utf-8'), out)
    return dict(zip(names, out.getvalue()[:-1].split(b'\t')))


class ProjectionReader:
    """Preserve COPY escapes byte-for-byte; memory is bounded by one record."""
    def __init__(self, file, source_columns, target_columns, constants, mapper=None):
        self.file, self.hash, self.pending = file, hashlib.sha256(), b''
        indexes = {name: index for index, name in enumerate(source_columns)}
        self.projection = [(None, constants[name]) if name in constants else
                           (indexes[name], None) if name in indexes else (None, b'\\N')
                           for name in target_columns]
        self.width = len(source_columns)
        self.direct = source_columns == target_columns and not constants and mapper is None
        self.records = mapper.rows(self.raw_records()) if mapper is not None else self.raw_records()

    def raw_records(self):
        for line in self.file:
            self.hash.update(line)
            if not line.endswith(b'\n'):
                raise MigrationError('Incomplete retained COPY record')
            fields = line[:-1].split(b'\t')
            if len(fields) != self.width:
                raise MigrationError('Retained COPY column count differs')
            yield fields

    def read(self, size=8192):
        if size < 0:
            size = 65536
        if self.direct:
            data = self.file.read(size)
            self.hash.update(data)
            return data
        output = bytearray()
        while len(output) < size:
            if self.pending:
                take = min(size - len(output), len(self.pending))
                output.extend(self.pending[:take])
                self.pending = self.pending[take:]
                continue
            try:
                fields = next(self.records)
            except StopIteration:
                break
            self.pending = b'\t'.join(value if index is None else fields[index]
                                      for index, value in self.projection) + b'\n'
        return bytes(output)


def copy_table(connection, stage, table, file_meta, columns, constants, mode='replace', mapper=None):
    fields = [name for name, meta in columns.items() if not meta['generated']]
    encoded = constant_fields(connection, constants, columns)
    if file_meta['rows']:
        missing = [name for name in fields if name not in file_meta['columns'] and name not in constants and columns[name]['required']]
        if missing:
            raise MigrationError(f'Target-only NOT NULL columns require CSV constants: {table}')
    with connection.cursor() as cr:
        if mode == 'replace':
            cr.execute(sql.SQL('DELETE FROM public.{}').format(sql.Identifier(table)))
        elif mode != 'add':
            raise MigrationError('Unsupported CSV table operation')
        # For shared M2M tables, COPY into the real table via an insert-only view
        # is not possible with ON CONFLICT. Use bounded multi-row INSERT instead,
        # keeping the retained COPY format and avoiding any staging relation.
        if mode == 'add':
            return add_relations(connection, stage, table, file_meta, fields, columns, mapper)
        with open(Path(stage) / 'tables' / file_meta['file'], 'rb') as file:
            reader = ProjectionReader(file, file_meta['columns'], fields, encoded, mapper)
            cr.copy_expert(sql.SQL("COPY public.{} ({}) FROM STDIN WITH (FORMAT text, ENCODING 'UTF8')").format(
                sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, fields))).as_string(connection), reader)
            rows = cr.rowcount
            if reader.hash.hexdigest() != file_meta['sha256'] or rows != file_meta['rows']:
                raise MigrationError(f'COPY checksum/count mismatch: {table}')
        cr.execute(sql.SQL('SELECT count(*) FROM public.{}').format(sql.Identifier(table)))
        if cr.fetchone()[0] != rows:
            raise MigrationError(f'Target row count differs: {table}')
    return rows


def unescape_copy(value):
    if value == b'\\N':
        return None
    # COPY output escapes control characters/backslashes (not arbitrary codecs).
    escapes = {ord('b'): 8, ord('f'): 12, ord('n'): 10, ord('r'): 13, ord('t'): 9, ord('v'): 11, 92: 92}
    out, index = bytearray(), 0
    while index < len(value):
        char = value[index]
        if char == 92:
            index += 1
            if index >= len(value) or value[index] not in escapes:
                raise MigrationError('Unsupported M2M COPY escape')
            char = escapes[value[index]]
        out.append(char)
        index += 1
    return out.decode('utf-8')


def add_relations(connection, stage, table, meta, fields, columns, mapper=None):
    from psycopg2.extras import execute_values
    if set(fields) != set(meta['columns']):
        raise MigrationError('Additive M2M columns must match')
    indexes = [meta['columns'].index(name) for name in fields]
    template = '(' + ','.join('%s::' + columns[name]['type'] for name in fields) + ')'
    query = sql.SQL('INSERT INTO public.{} ({}) SELECT v.* FROM (VALUES %s) v WHERE NOT EXISTS '
                    '(SELECT 1 FROM public.{} t WHERE {}) ON CONFLICT DO NOTHING').format(
        sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, fields)), sql.Identifier(table),
        sql.SQL(' AND ').join(sql.SQL('t.{} IS NOT DISTINCT FROM v.{}').format(
            sql.Identifier(name), sql.Identifier('column' + str(index + 1))) for index, name in enumerate(fields)))
    query = query.as_string(connection)
    rows, batch = 0, []
    with connection.cursor() as cr, open(Path(stage) / 'tables' / meta['file'], 'rb') as file:
        reader = ProjectionReader(file, meta['columns'], meta['columns'], {})
        records = mapper.rows(reader.raw_records()) if mapper is not None else reader.raw_records()
        for values in records:
            batch.append(tuple(unescape_copy(values[index]) for index in indexes))
            if len(batch) == 1000:
                execute_values(cr, query, list(dict.fromkeys(batch)), template=template, page_size=1000)
                rows += cr.rowcount
                batch = []
        if batch:
            execute_values(cr, query, list(dict.fromkeys(batch)), template=template, page_size=1000)
            rows += cr.rowcount
    if reader.hash.hexdigest() != meta['sha256']:
        raise MigrationError(f'Retained relation COPY checksum differs: {table}')
    return rows


def table_fingerprint(connection, table, columns):
    # Fresh catalog dictionaries use attribute order, JSON sidecars use sorted
    # keys. Hash a canonical order so both produce the same resume fingerprint.
    columns = sorted(columns)
    order = ['id'] if 'id' in columns else list(columns)
    query = sql.SQL('COPY (SELECT {} FROM public.{} ORDER BY {}) TO STDOUT').format(
        sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, order)))
    sink = HashSink()
    with connection.cursor() as cr:
        cr.copy_expert(query.as_string(connection), sink)
    return sink.hash.hexdigest()


def restart_sequence(connection, table, columns, only_advance=False):
    sequence = columns.get('id', {}).get('sequence')
    if not sequence:
        return
    with connection.cursor() as cr:
        cr.execute('SELECT seqstart,seqincrement,seqmax FROM pg_sequence WHERE seqrelid=%s::regclass', [sequence])
        start, increment, maximum = cr.fetchone()
        if increment != 1:
            raise MigrationError(f'Unsupported non-unit ID sequence: {table}')
        cr.execute(sql.SQL('SELECT max(id) FROM public.{}').format(sql.Identifier(table)))
        last = cr.fetchone()[0]
        value = max(start, last + 1) if last is not None else start
        if value > maximum:
            raise MigrationError(f'ID sequence exhausted: {table}')
        cr.execute('SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=%s::regclass', [sequence])
        schema, name = cr.fetchone()
        if only_advance:
            cr.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(schema, name)))
            last_value, called = cr.fetchone()
            if last_value + (1 if called else 0) >= value:
                return
        cr.execute(sql.SQL('ALTER SEQUENCE {} RESTART WITH {}').format(sql.Identifier(schema, name), sql.Literal(value)))
