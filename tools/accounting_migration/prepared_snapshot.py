"""Immutable source extraction for the prepared-target workflow."""
import os
from pathlib import Path
from psycopg2 import sql
from bulk import catalog, CopyWriter, copy_column_order
from common import MigrationError, save_json, digest, settings
from importer import FRAMEWORK_FIELDS
from source import inventory
import prepared_progress as progress

FORMAT = 1
SCHEMA = 'prepared_migration_source'


def select_models(info, target):
    source = {m for m, v in info['models'].items() if m.startswith('ab') and
              not v['transient'] and v['table_kind'] in ('r', 'p')}
    selected = sorted(source & target.keys())
    if not selected:
        raise MigrationError('No persistent shared custom models')
    return selected, sorted(source - target.keys())


def export(connection, config, database, stage, target, rules, conversions=None):
    stage = Path(stage)
    conversions=conversions or {}
    info = inventory(connection, settings(config).get('addons_path', '').split(','), prepared=True)
    selected, omitted = select_models(info, target)
    physical = catalog(connection)
    tables, relations = {}, []
    for model in selected:
        table = info['models'][model]['table']
        if table in tables:
            raise MigrationError('Multiple selected models share one physical table; explicit adapter required')
        tables[table] = None
        for name, f in info['models'][model].get('fields', {}).items():
            if name in FRAMEWORK_FIELDS or f.get('related'):
                continue
            if f['ttype'] == 'many2many' and f.get('relation_table') in physical:
                target_name=conversions.get('fields',{}).get(model,{}).get(name,name)
                tf = target[model]['fields'].get(target_name, {})
                if not tf or tf.get('store') is False or tf.get('related'):
                    continue
                if tf.get('type') != 'many2many':
                    raise MigrationError(f'Incompatible shared M2M field: {model}.{name}')
                related=conversions.get('source_aliases',{}).get(f['relation'],f['relation'])
                relations.append(dict(model=model, field=target_name, related=related,
                    table=f['relation_table'], column1=f['column1'], column2=f['column2']))
                tables[f['relation_table']] = None
    # These are read-only source metadata/ID lists, never public target imports.
    queries = {'res_users': sql.SQL('SELECT id FROM public.res_users'),
               'res_partner': sql.SQL('SELECT id FROM public.res_partner')}
    projections={'res_users':['id'],'res_partner':['id']}
    if 'res_company' in physical:
        queries['res_company']=sql.SQL('SELECT id FROM public.res_company')
        projections['res_company']=['id']
    for table in ('ir_model_data', 'ir_model_fields', 'ir_model', 'ir_translation', 'ir_property'):
        if table in physical:
            tables[table] = None
    for model, key in rules.get('stable_keys', {}).items():
        if model in ('res.users','res.partner','res.groups','ir.attachment'):
            raise MigrationError(f'Stable-key override forbidden: {model}')
        meta = info['models'].get(model)
        if meta and model not in selected and key in physical.get(meta['table'], {}):
            table = meta['table']
            queries[table] = sql.SQL('SELECT id,{} FROM public.{}').format(
                sql.Identifier(key), sql.Identifier(table))
            projections[table]=['id',key]
    tables.update({t: None for t in queries})
    owners = sql.SQL('res_model=ANY({})').format(sql.Literal(selected))
    links = []
    for model in selected:
        meta = info['models'][model]
        for name, f in meta.get('fields', {}).items():
            dest=conversions.get('fields',{}).get(model,{}).get(name,name)
            tf=target[model]['fields'].get(dest,{})
            if (tf and tf.get('store') is not False and tf.get('relation')=='ir.attachment'
                    and name in physical[meta['table']]):
                links.append(sql.SQL('SELECT {} id FROM public.{} WHERE {} IS NOT NULL').format(
                    sql.Identifier(name), sql.Identifier(meta['table']), sql.Identifier(name)))
    for r in relations:
        if r['related'] == 'ir.attachment':
            links.append(sql.SQL('SELECT {} id FROM public.{}').format(
                sql.Identifier(r['column2']), sql.Identifier(r['table'])))
    if links:
        owners = sql.SQL('({}) OR id IN ({})').format(owners, sql.SQL(' UNION ').join(links))
    queries['ir_attachment'] = sql.SQL('SELECT * FROM public.ir_attachment WHERE {}').format(owners)
    tables['ir_attachment'] = None
    with connection.cursor() as cr:
        cr.execute('SELECT transaction_timestamp(),txid_current_snapshot()')
        stamp, snapshot = cr.fetchone()
        cr.execute("SELECT count(*) FROM mail_activity WHERE res_model=ANY(%s)", [selected])
        activity_count = cr.fetchone()[0]
    manifest = dict(format=FORMAT, complete=False, source_db=database, source_version=info['source_version'], selected=selected,
        omitted=omitted, models=info['models'], relations=relations, tables={},
        snapshot_time=str(stamp), snapshot=str(snapshot), activities=activity_count)
    directory = stage / 'tables'
    directory.mkdir(mode=0o700)
    for table in sorted(tables):
        progress.begin('extract',table=table,operation='Read source into retained COPY file')
        columns = physical[table]
        query = queries.get(table)
        if query is not None:
            # Explicitly select projected columns in their SQL order.
            if table in projections:
                columns = {name: columns[name] for name in projections[table]}
        else:
            query = sql.SQL('SELECT {} FROM public.{}').format(
                sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(table))
        meta = dict(columns=columns, column_order=list(columns))
        copy_column_order(table, meta)
        print(f'Extract {table}', flush=True)
        with connection.cursor() as cr, open(directory / (table + '.copy'), 'xb') as file:
            writer = progress.OutputCounter(CopyWriter(file, table))
            cr.copy_expert(sql.SQL("COPY ({}) TO STDOUT WITH (FORMAT text, ENCODING 'UTF8')").format(
                query).as_string(connection), writer)
            file.flush()
            os.fsync(file.fileno())
            meta.update(rows=cr.rowcount, bytes=writer.wrapped.bytes, sha256=writer.wrapped.hash.hexdigest())
        progress.finish('extracted; file durable')
        manifest['tables'][table] = meta
        save_json(stage / 'snapshot.json', manifest)
    manifest['complete'] = True
    save_json(stage / 'snapshot.json', manifest)
    return manifest


def verify(stage, manifest):
    progress.begin('verify extraction',operation='Verify retained COPY checksums')
    if manifest.get('format') != FORMAT or not manifest.get('complete'):
        raise MigrationError('Prepared extraction incomplete or incompatible')
    for table, meta in manifest['tables'].items():
        copy_column_order(table, meta)
        path = Path(stage) / 'tables' / (table + '.copy')
        if not path.is_file() or path.stat().st_size != meta['bytes'] or digest(path) != meta['sha256']:
            raise MigrationError(f'Extraction checksum mismatch: {table}')
    progress.finish('extraction verified')


def stage_tables(connection, stage, manifest):
    """Caller owns the transaction; staging and checkpoint 1 commit together."""
    with connection.cursor() as cr:
        cr.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(SCHEMA)))
        cr.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(SCHEMA)))
        for index,(table, meta) in enumerate(manifest['tables'].items(),1):
            columns = meta['column_order']
            if table in ('res_users','res_partner'):
                cr.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(SCHEMA,table)))
            cr.execute(sql.SQL('CREATE TABLE {} ({})').format(sql.Identifier(SCHEMA, table),
                sql.SQL(',').join(sql.SQL('{} {}').format(sql.Identifier(c), sql.SQL(meta['columns'][c]['type']))
                                 for c in columns)))
            with open(Path(stage) / 'tables' / (table + '.copy'), 'rb') as file:
                progress.begin('staging COPY',table=table,total=meta['rows'],operation='COPY FROM',monitor=True,
                               table_index=index,table_count=len(manifest['tables']),bytes_total=meta['bytes'])
                cr.copy_expert(sql.SQL('COPY {} ({}) FROM STDIN').format(sql.Identifier(SCHEMA, table),
                    sql.SQL(',').join(map(sql.Identifier, columns))).as_string(connection), progress.InputCounter(file))
            progress.update(processed=meta['rows'],bytes=meta['bytes'])
            progress.finish('copied; pending commit')
            if 'id' in columns:
                progress.begin('index',table=table,operation='Create staging primary key',monitor=True)
                cr.execute(sql.SQL('ALTER TABLE {} ADD PRIMARY KEY (id)').format(sql.Identifier(SCHEMA, table)))
                progress.finish('indexed; pending commit')
            progress.begin('validate staging',table=table,operation='Validate COPY row count',monitor=True)
            cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(SCHEMA, table)))
            if cr.fetchone()[0] != meta['rows']:
                raise MigrationError(f'Staging COPY count mismatch: {table}')
            progress.finish('row count verified; pending commit')
