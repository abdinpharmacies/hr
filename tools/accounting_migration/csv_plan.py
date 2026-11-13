"""Read-only discovery and editable table plans. No registry or business adapters."""
import ast
import csv
import datetime
import os
from pathlib import Path
import uuid

from psycopg2 import sql
from common import MigrationError, connect, dumps, loads, save_json, settings
from resume import endpoint, fingerprint

VERSION = 3
HEADERS = ('table_name', 'model_type', 'existance', 'available_target_selections_json',
           'source_missing_columns_list', 'target_missing_columns_list',
           'replicate', 'replicate_override', 'column_default_value_json',
           'source_fk_columns_json', 'target_fk_cloumns_json')


def database_identity(connection, config):
    with connection.cursor() as cr:
        cr.execute('SELECT oid FROM pg_database WHERE datname=current_database()')
        return dict(endpoint=endpoint(config), database=connection.info.dbname, oid=cr.fetchone()[0])


def table_overrides(config, installed):
    """Resolve literal _table declarations without starting either Odoo registry."""
    overrides, seen = {}, set()
    for root in settings(config).get('addons_path', '').split(','):
        if not root.strip():
            continue
        for addon in Path(root.strip()).glob('*'):
            if addon.name not in installed or addon.name in seen or not addon.is_dir():
                continue
            seen.add(addon.name)
            for path in addon.rglob('*.py'):
                try:
                    tree = ast.parse(path.read_text())
                except (SyntaxError, UnicodeError, OSError):
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.ClassDef):
                        continue
                    values = {}
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id in ('_name', '_inherit', '_table'):
                                    try:
                                        values[target.id] = ast.literal_eval(item.value)
                                    except (ValueError, TypeError):
                                        pass
                    model = values.get('_name', values.get('_inherit'))
                    if isinstance(model, str) and isinstance(values.get('_table'), str):
                        overrides[model] = values['_table']
    return overrides


def discover(connection, config):
    columns, primary, models, relations, many2one = {}, {}, {}, [], []
    with connection.cursor() as cr:
        cr.execute("SELECT c.relname,a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull,"
                   "pg_get_expr(d.adbin,d.adrelid),a.attgenerated,"
                   "pg_get_serial_sequence(format('%I.%I',n.nspname,c.relname),a.attname) "
                   "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "JOIN pg_attribute a ON a.attrelid=c.oid "
                   "LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum "
                   "WHERE n.nspname='public' AND c.relkind IN ('r','p') "
                   "AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attnum")
        for table, name, kind, required, default, generated, sequence in cr:
            columns.setdefault(table, {})[name] = dict(type=kind, required=required,
                default=default, generated=bool(generated), sequence=sequence)
        cr.execute("SELECT c.relname,array_agg(a.attname ORDER BY u.ordinality) "
                   "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid "
                   "JOIN pg_namespace n ON n.oid=c.relnamespace "
                   "CROSS JOIN LATERAL unnest(k.conkey) WITH ORDINALITY u(num,ordinality) "
                   "JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=u.num "
                   "WHERE k.contype='p' AND n.nspname='public' GROUP BY k.oid,c.relname")
        primary = dict(cr.fetchall())
        cr.execute("SELECT name FROM ir_module_module WHERE state='installed'")
        installed = {row[0] for row in cr}
        overrides = table_overrides(config, installed)
        cr.execute('SELECT model,transient FROM ir_model ORDER BY model')
        for model, transient in cr:
            table = overrides.get(model, model.replace('.', '_'))
            if not transient and table in columns:
                models[model] = table
        cr.execute("SELECT model,name,relation_table,column1,column2,relation FROM ir_model_fields "
                   "WHERE ttype='many2many' AND store AND coalesce(related,'')='' ORDER BY model,name")
        for model, field, table, first, second, related in cr:
            if model in models and table in columns and first and second:
                relations.append(dict(model=model, field=field, table=table, columns=[first, second], related=related))
        cr.execute("SELECT model,name,relation FROM ir_model_fields WHERE ttype='many2one' AND store ORDER BY model,name")
        for model, name, related in cr:
            table = models.get(model)
            if table and name in columns[table]:
                many2one.append(dict(model=model, table=table, column=name, related=related))
        cr.execute("SELECT src.relname,sc.attname,dst.relname,dc.attname,k.conname,"
                   "pg_get_constraintdef(k.oid),sn.nspname,dn.nspname,u.ordinality "
                   "FROM pg_constraint k JOIN pg_class src ON src.oid=k.conrelid "
                   "JOIN pg_namespace sn ON sn.oid=src.relnamespace "
                   "JOIN pg_class dst ON dst.oid=k.confrelid JOIN pg_namespace dn ON dn.oid=dst.relnamespace "
                   "CROSS JOIN LATERAL unnest(k.conkey,k.confkey) WITH ORDINALITY u(s,d,ordinality) "
                   "JOIN pg_attribute sc ON sc.attrelid=src.oid AND sc.attnum=u.s "
                   "JOIN pg_attribute dc ON dc.attrelid=dst.oid AND dc.attnum=u.d "
                   "WHERE k.contype='f' AND (sn.nspname='public' OR dn.nspname='public') "
                   "ORDER BY sn.nspname,src.relname,k.conname,u.ordinality")
        fks = [dict(zip(('source_table', 'source_column', 'referenced_table', 'referenced_column',
                        'name', 'definition', 'source_schema', 'referenced_schema', 'ordinality'), row)) for row in cr]
    result = dict(columns=columns, primary=primary, models=models, relations=relations, many2one=many2one, fks=fks)
    result['signature'] = fingerprint(dict(columns=columns, primary=primary, models=models, relations=relations))
    return result


def target_selection_choices(connection, source, target):
    """Stored technical keys only; missing/dynamic choices remain unresolved."""
    result = {}
    with connection.cursor() as cr:
        cr.execute('SELECT f.model,f.name,s.value FROM public.ir_model_fields f '
                   'LEFT JOIN public.ir_model_fields_selection s ON s.field_id=f.id '
                   "WHERE f.ttype='selection' ORDER BY f.model,f.name,s.sequence,s.id")
        for model, name, value in cr:
            table = target['models'].get(model)
            if (not table or name not in target['columns'][table]
                    or name in source['columns'].get(table, {})):
                continue
            fields = result.setdefault(table, {})
            fields.setdefault(name, None)
            if value is not None:
                if fields[name] is None:
                    fields[name] = []
                if value not in fields[name]:
                    fields[name].append(value)
    return result


def selection_cell(choices, table):
    return dumps({'available_target_selections': choices.get(table, {})})


def table_existance(table, source, target):
    source_has = table in source['columns']
    target_has = table in target['columns']
    if source_has and target_has:
        return 'both'
    if source_has:
        return 'source_only'
    if target_has:
        return 'target_only'
    raise MigrationError(f'Table absent from both bound catalogs: {table}')


def write_plan(path, metadata, rows):
    """Never replace an operator's existing plan or sidecar."""
    path = Path(path).expanduser().resolve()
    sidecar = Path(str(path) + '.metadata.json')
    if path.exists() or sidecar.exists():
        raise MigrationError('CSV or sidecar exists; choose a new export path')
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'x', encoding='utf-8', newline='', opener=lambda p, f: os.open(p, f, 0o600)) as out:
        writer = csv.DictWriter(out, HEADERS)
        writer.writeheader()
        writer.writerows(rows)
        out.flush()
        os.fsync(out.fileno())
    save_json(sidecar, {**metadata, 'version': VERSION})
    return path


def fk_cells(meta, table):
    keys = ('source_table', 'source_column', 'referenced_table', 'referenced_column')
    return [{key: item[key] for key in keys} for item in meta['fks']
            if item['source_schema'] == 'public' and item['source_table'] == table]


def export_plan(args):
    path = Path(args.export_table_plan).expanduser().resolve()
    sidecar = Path(str(path) + '.metadata.json')
    if path.exists() or sidecar.exists():
        raise MigrationError('CSV or sidecar exists; choose a new export path')
    source = connect(args.source_config, args.source_db, readonly=True)
    target = None
    try:
        target = connect(args.target_config, args.target_db, readonly=True)
        identities = dict(source=database_identity(source, args.source_config), target=database_identity(target, args.target_config))
        if (identities['source']['database'], identities['source']['oid']) == (identities['target']['database'], identities['target']['oid']):
            raise MigrationError('Source and target must differ')
        src, dst = discover(source, args.source_config), discover(target, args.target_config)
        choices = target_selection_choices(target, src, dst)
        owners = {}
        for meta in (src, dst):
            for model, table in meta['models'].items():
                owners.setdefault(table, set()).add(model)
        rows = []
        for table in sorted(owners):
            kind = 'custom' if all(model.startswith('ab') for model in owners[table]) else 'odoo'
            sc, tc = src['columns'].get(table, {}), dst['columns'].get(table, {})
            rows.append(dict(zip(HEADERS, [table, kind, table_existance(table, src, dst), selection_cell(choices, table),
                         dumps(sorted(sc.keys() - tc.keys())), dumps(sorted(tc.keys() - sc.keys())),
                         '1' if kind == 'custom' else '0', '0', '{}', dumps(fk_cells(src, table)), dumps(fk_cells(dst, table))])))
        write_plan(path, dict(plan_id=uuid.uuid4().hex, identities=identities,
                               source=src, target=dst, tables=sorted(owners),
                               created=datetime.datetime.now(datetime.timezone.utc).isoformat()), rows)
        print(f'CSV exported: {path}\nMetadata: {sidecar}\nTables: {len(rows)}. Edit selections/constants, then use --table-plan.', flush=True)
        return dict(status='plan_exported', tables=len(rows), csv=str(path))
    finally:
        source.close()
        if target is not None:
            target.close()


def read_rows(path):
    path = Path(path).expanduser().resolve()
    meta = loads(Path(str(path) + '.metadata.json').read_text())
    if meta.get('version') != VERSION:
        raise MigrationError('Unsupported CSV metadata version; export a new CSV and sidecar')
    if 'plan_id' in meta and (not isinstance(meta['plan_id'], str) or len(meta['plan_id']) != 32
                              or any(char not in '0123456789abcdef' for char in meta['plan_id'])):
        raise MigrationError('Invalid CSV plan identity')
    rows, seen = [], set()
    csv.field_size_limit(64 * 1024 * 1024)
    with path.open(encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != HEADERS:
            raise MigrationError('CSV headers/order differ from the exported contract; export a new CSV and sidecar')
        for row in reader:
            table = row['table_name']
            if None in row or any(value is None for value in row.values()) or table in seen or table not in meta['tables']:
                raise MigrationError('Malformed CSV row, duplicate, or unknown table')
            seen.add(table)
            rows.append(row)
    return meta, rows


def present_both(source, target, table, kind, exclusions=None):
    missing = [side for side, meta in (('source', source), ('target', target)) if table not in meta['columns']]
    if not missing:
        return True
    if exclusions is not None:
        exclusions.append(dict(table=table, kind=kind, missing_from=missing,
                               existance='target_only' if missing == ['source'] else 'source_only' if missing == ['target'] else None,
                               reason='missing_' + '_and_'.join(missing) + '_table'))
    return False


def read_plan(path, exclusions=None):
    meta, rows = read_rows(path)
    result = {}
    forced = []
    for row in rows:
        table = row['table_name']
        action = row['replicate'].strip()
        override = row['replicate_override'].strip()
        if action not in ('', '0', '1'):
            raise MigrationError(f'Invalid replicate: {table}')
        if override not in ('', '0', '1'):
            raise MigrationError(f'Invalid replicate_override: {table}')
        selected = action == '1' or override == '1'
        if selected and not present_both(meta['source'], meta['target'], table, 'model', exclusions):
            continue
        try:
            constants = loads(row['column_default_value_json'].strip() or '{}')
        except (ValueError, TypeError):
            raise MigrationError(f'Invalid constant JSON: {table}') from None
        if not isinstance(constants, dict) or 'id' in constants:
            raise MigrationError(f'Constants must be an object without an id override: {table}')
        if selected:
            sc, tc = meta['source']['columns'].get(table, {}), meta['target']['columns'].get(table, {})
            if 'id' not in sc or 'id' not in tc:
                raise MigrationError(f'Selected table must exist on both sides with id: {table}')
            if any(name not in tc or tc[name]['generated'] for name in constants):
                raise MigrationError(f'Unknown or generated constant column: {table}')
            result[table] = constants
            if override == '1':
                forced.append(table)
    return {**meta, 'force_tables': sorted(forced)}, result


def convert_plan(path, output, target_config, target_db):
    """Replace diagnostics while preserving every operational cell and run ID."""
    output = Path(output).expanduser().resolve()
    if output.exists() or Path(str(output) + '.metadata.json').exists():
        raise MigrationError('Converted CSV or sidecar exists; choose a new path')
    meta, rows = read_rows(path)
    connection = connect(target_config, target_db, readonly=True)
    try:
        if database_identity(connection, target_config) != meta['identities']['target']:
            raise MigrationError('Target identity differs from the original plan')
        choices = target_selection_choices(connection, meta['source'], meta['target'])
        converted = []
        for row in rows:
            updated = {**row, 'available_target_selections_json': selection_cell(choices, row['table_name']),
                       'existance': table_existance(row['table_name'], meta['source'], meta['target'])}
            converted.append({key: updated[key] for key in HEADERS})
        return write_plan(output, meta, converted)
    finally:
        connection.close()


def relation_scope(meta, selected):
    from csv_relations import plan_m2m
    return plan_m2m(meta['source'], meta['target'], selected)
