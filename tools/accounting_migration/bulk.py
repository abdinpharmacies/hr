"""Fresh snapshot extraction and COPY primitives (no Odoo registry or source writes)."""
import contextlib
import hashlib
import os
from pathlib import Path
import time
from psycopg2 import sql
from progress import current
from common import EXCLUDED, LOOKUPS, NATIVE, MigrationError, save_json

BULK_FORMAT_VERSION = 3


def copy_column_order(table, metadata):
    """COPY is positional; JSON object ordering is never a transfer contract."""
    order = metadata.get('column_order')
    columns = metadata.get('columns')
    if (not isinstance(columns, dict) or not columns or not isinstance(order, list)
            or not all(isinstance(name, str) for name in order)
            or len(order) != len(set(order)) or set(order) != set(columns)):
        raise MigrationError(f'Invalid COPY column_order for table {table}; create a fresh extraction')
    return list(order)


def validate_bulk_manifest(manifest):
    if manifest.get('format_version') != BULK_FORMAT_VERSION:
        raise MigrationError('Unsupported bulk manifest version: explicit COPY column order is required; '
                             'run a fresh migration to a new target database')
    if not manifest.get('complete'):
        raise MigrationError('Fresh bulk extraction is incomplete')
    tables = manifest.get('tables')
    if not isinstance(tables, dict) or not tables:
        raise MigrationError('Bulk manifest contains no tables')
    # Validate every table before the first staging DDL/COPY statement.
    for table, metadata in tables.items():
        if not isinstance(metadata, dict):
            raise MigrationError(f'Invalid COPY metadata for table {table}')
        copy_column_order(table, metadata)


def ident(*names):
    return sql.Identifier(*names)


def catalog(connection):
    with connection.cursor() as cr:
        cr.execute("SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,"
                   "pg_get_expr(d.adbin,d.adrelid) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "JOIN pg_attribute a ON a.attrelid=c.oid LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum "
                   "WHERE n.nspname='public' AND c.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped "
                   "ORDER BY c.relname,a.attnum")
        result = {}
        for table, name, typ, required, default in cr:
            result.setdefault(table, {})[name] = dict(type=typ, required=required, default=default)
        return result


def constraints(connection):
    with connection.cursor() as cr:
        cr.execute("SELECT c.relname,k.conname,k.contype,pg_get_constraintdef(k.oid),k.condeferrable,k.condeferred "
                   "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
                   "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY c.relname,k.conname")
        return [dict(table=t, name=n, kind=k, definition=d, deferrable=f, initially_deferred=i)
                for t,n,k,d,f,i in cr]


@contextlib.contextmanager
def heartbeat(message, interval=5):
    # Reporting is handled by the process-wide background reporter, not SQL threads.
    current().begin('operation', operation=message)
    try:
        yield
    except BaseException:
        current().finish('failed')
        raise
    else:
        current().finish('operation complete')


class CopyWriter:
    def __init__(self, file, label):
        self.file, self.label = file, label
        self.bytes = 0
        self.hash = hashlib.sha256()
        self.start = self.last = time.monotonic()

    def write(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        self.hash.update(data)
        self.bytes += len(data)
        current().update(bytes=self.bytes)
        return self.file.write(data)


def target_field(target, model, name):
    if model == 'res.users' and name == 'groups_id':
        name = 'group_ids'
    return target.get(model, {}).get('fields', {}).get(name)


def choose_models(info, target, rules):
    """Full persistent tables in scope; never traverse into framework/mail tables."""
    models = info['models']
    selected = set(info['roots']) | {'res.users', 'res.company'}
    selected |= {n for n, m in models.items() if 'abdin_eplus' in m['modules']
                 and not m['transient'] and m['table_kind'] == 'r'}
    selected -= EXCLUDED
    pending = list(selected)
    while pending:
        name = pending.pop()
        meta = models.get(name)
        if not meta or meta['table_kind'] != 'r' or meta['transient']:
            raise MigrationError(f'Persistent source table unavailable: {name}')
        if name not in target and name not in LOOKUPS:
            raise MigrationError(f'Missing target model: {name}')
        if name in LOOKUPS:
            continue
        related = set(rules.get('inverse_links', {}).get(name, {}))
        related.update(rules.get('integer_links', {}).get(name, {}).values())
        for field, sf in meta.get('fields', {}).items():
            tf = target_field(target, name, field)
            if field not in {'message_main_attachment_id', 'res_users_settings_ids', 'signature', 'notification_type'} and tf and sf.get('ttype') in ('many2one', 'many2many') and sf.get('relation') and not sf.get('related'):
                related.add(sf['relation'])
        for rel in related - selected - EXCLUDED:
            rm = models.get(rel)
            if not rm or rm['table_kind'] != 'r' or rm['transient']:
                continue  # non-stored/computed relations have no data to copy
            if rel not in NATIVE | LOOKUPS and not any((x or '').startswith('ab') for x in rm['modules']):
                raise MigrationError(f'Unsupported prerequisite model: {rel}')
            selected.add(rel)
            pending.append(rel)
    return sorted(selected)


def export_snapshot(con, stage, info, target, rules):
    """Stream raw PostgreSQL text COPY files with source types and a single snapshot."""
    physical = catalog(con)
    selected = choose_models(info, target, rules)
    # Include dynamic document owners only when they belong to the supported scope.
    for name in list(selected):
        for model_field in rules.get('polymorphic', {}).get(name, {}).values():
            if name == 'ir.attachment' or model_field not in physical[info['models'][name]['table']]:
                continue
            with con.cursor() as cr:
                cr.execute(sql.SQL('SELECT DISTINCT {} FROM {} WHERE {} IS NOT NULL').format(
                    ident(model_field), ident(info['models'][name]['table']), ident(model_field)))
                for (related,) in cr:
                    related = rules.get('source_aliases', {}).get(related, related)
                    if related not in selected:
                        raise MigrationError(f'Unplanned document dependency: {name} -> {related}')
    tables = {info['models'][m]['table'] for m in selected}
    relations = {}
    for model in selected:
        if model in LOOKUPS:
            continue
        for name, field in info['models'][model].get('fields', {}).items():
            tf = target_field(target, model, name)
            if (field['ttype'] == 'many2many' and field.get('relation_table') in physical
                    and not field.get('related') and tf and field['relation'] in selected):
                table = field['relation_table']
                relations.setdefault(table, []).append(dict(model=model, field=name, related=field['relation'],
                    column1=field['column1'], column2=field['column2']))
                tables.add(table)
    tables.update({'ir_model_data', 'ir_model_fields', 'ir_translation', 'ir_property'})
    tables &= physical.keys()
    data = stage / 'tables'
    data.mkdir(mode=0o700)
    with con.cursor() as cr:
        cr.execute('SELECT transaction_timestamp(),txid_current_snapshot()')
        stamp, snapshot = cr.fetchone()
    manifest = dict(format_version=BULK_FORMAT_VERSION, source_db=con.info.dbname, source_version=info['source_version'],
                    snapshot_time=str(stamp), snapshot=str(snapshot), models={m: info['models'][m] for m in selected},
                    relations=relations, tables={}, constraints=constraints(con), complete=False)
    for index, table in enumerate(sorted(tables), 1):
        current().begin('extract', table=table, operation='COPY TO STDOUT', table_index=index, table_count=len(tables))
        table_metadata = dict(columns=physical[table], column_order=list(physical[table]))
        columns = copy_column_order(table, table_metadata)
        query = sql.SQL('COPY {} ({}) TO STDOUT WITH (FORMAT text, ENCODING \'UTF8\')').format(
            ident(table), sql.SQL(',').join(map(ident, columns)))
        if table == 'ir_attachment':
            owners = sorted(set(selected) | set(rules.get('source_aliases', {})))
            query = sql.SQL("COPY (SELECT {} FROM {} WHERE res_model IS NULL OR res_model=ANY({})) TO STDOUT WITH (FORMAT text, ENCODING 'UTF8')").format(
                sql.SQL(',').join(map(ident, columns)), ident(table), sql.Literal(owners))
        path = data / f'{table}.copy'
        with con.cursor() as cr, open(path, 'xb') as file:
            writer = CopyWriter(file, table)
            cr.copy_expert(query.as_string(con), writer)
            rows = cr.rowcount
            file.flush()
            os.fsync(file.fileno())
        manifest['tables'][table] = dict(table_metadata, rows=rows, bytes=writer.bytes,
                                         sha256=writer.hash.hexdigest())
        current().update(processed=rows, total=rows, bytes=writer.bytes)
        current().finish('extracted; file durable')
        save_json(stage / 'bulk-manifest.json', manifest)
    manifest['complete'] = True
    save_json(stage / 'bulk-manifest.json', manifest)
    return manifest
