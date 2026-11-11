"""Read-only PostgreSQL inventory and consistent, resumable-at-import export."""
import os
import shutil
import sqlite3
import uuid
from pathlib import Path
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from common import (EXCLUDED, LOOKUPS, NATIVE, MigrationError, connect,
                    digest, downstream, dumps, loads, manifests, private_dir,
                    safe_attachment_path, save_json, settings, property_blockers)


def staging_db(path):
    """Allow progress readers without interrupting the source snapshot export."""
    db = sqlite3.connect(path, timeout=60)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA busy_timeout=60000')
    return db


def inventory(con, addon_paths=(), prepared=False):
    with con.cursor(cursor_factory=RealDictCursor) as cr:
        cr.execute("SELECT m.name,d.name AS dependency FROM ir_module_module m JOIN "
                   "ir_module_module_dependency d ON d.module_id=m.id WHERE m.state='installed'")
        deps = {}
        for r in cr:
            deps.setdefault(r['name'], []).append(r['dependency'])
        selected = sorted(m for m in deps if m.startswith('ab')) if prepared else downstream(deps)
        required = set(selected)
        while True:
            expanded = required | {d for m in required for d in deps.get(m, [])}
            if expanded == required: break
            required = expanded
        available = manifests()
        missing = sorted(set(selected) - set(available))
        if missing and not prepared:
            raise MigrationError(f'Missing target addons: {missing}')
        cr.execute("SELECT m.model,m.transient, array_agg(DISTINCT d.module) AS modules "
                   "FROM ir_model m LEFT JOIN ir_model_data d ON d.model='ir.model' AND d.res_id=m.id "
                   "GROUP BY m.model,m.transient")
        models = {r['model']: dict(r) for r in cr}
        cr.execute("SELECT c.relname,c.relkind,c.reltuples::bigint AS estimate FROM pg_class c "
                   "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public'")
        tables = {r['relname']: dict(r) for r in cr}
        cr.execute("SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public'")
        columns = {}
        for r in cr:
            columns.setdefault(r['table_name'], {})[r['column_name']] = r['data_type']
        cr.execute("SELECT model,name,ttype,relation,relation_field,relation_table,column1,column2,"
                   "required,readonly,store,related,translate FROM ir_model_fields ORDER BY model,name")
        for r in cr:
            if r['model'] in models:
                models[r['model']].setdefault('fields', {})[r['name']] = dict(r)
        # Explicit _table overrides are resolved without loading the production registry.
        import ast
        overrides = {}
        seen_addons = set()
        candidates = (addon for root in addon_paths for addon in Path(root.strip()).glob('*'))
        for addon in candidates:
            if addon.name not in deps or addon.name in seen_addons or not addon.is_dir():
                continue
            seen_addons.add(addon.name)
            for p in addon.rglob('*.py'):
                try:
                    tree = ast.parse(p.read_text())
                except (SyntaxError, UnicodeError):
                    continue
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        attrs = {}
                        for item in node.body:
                            if isinstance(item, ast.Assign):
                                for target in item.targets:
                                    if isinstance(target, ast.Name) and target.id in ('_name', '_table', '_inherit'):
                                        try: attrs[target.id] = ast.literal_eval(item.value)
                                        except (ValueError, TypeError): pass
                        name = attrs.get('_name', attrs.get('_inherit'))
                        if isinstance(name, str) and attrs.get('_table'):
                            overrides[name] = attrs['_table']
        for name, model in models.items():
            table = overrides.get(name, name.replace('.', '_'))
            model['table'] = table
            model['columns'] = columns.get(table, {})
            model['table_kind'] = tables.get(table, {}).get('relkind')
            model['estimated_rows'] = tables.get(table, {}).get('estimate', 0)
        roots = sorted(n for n, m in models.items() if set(m['modules']) & set(selected)
                       and not m['transient'] and m['table_kind'] == 'r' and n not in EXCLUDED)
        cr.execute("SELECT latest_version FROM ir_module_module WHERE name='base'")
        version = cr.fetchone()['latest_version']
        if not version.startswith('15.'):
            raise MigrationError('Source must be Odoo 15')
        return {'source_version': version, 'modules': selected, 'required_modules': sorted(required), 'roots': roots, 'models': models}


def inspect(config, database, output):
    con = connect(config, database)
    try:
        info = inventory(con, settings(config).get('addons_path', '').split(','))
        save_json(output, info)
        return {'modules': info['modules'], 'root_models': len(info['roots']), 'report': str(output)}
    finally:
        con.close()


def export(config, database, stage, filestore=None, frozen=False, sample=0):
    stage = private_dir(stage)
    if (stage / 'records.sqlite').exists():
        raise MigrationError('Export directory already contains data; use a new directory for a new snapshot')
    if sample < 0 or (sample and frozen):
        raise MigrationError('Sample exports cannot be marked frozen')
    con = connect(config, database)
    db = staging_db(stage / 'records.sqlite')
    os.chmod(stage / 'records.sqlite', 0o600)
    db.executescript('''
    CREATE TABLE records(model TEXT, source_id INTEGER, payload TEXT NOT NULL, PRIMARY KEY(model,source_id));
    CREATE TABLE needed(model TEXT, source_id INTEGER, PRIMARY KEY(model,source_id));
    CREATE TABLE xmlids(model TEXT, source_id INTEGER, xmlid TEXT UNIQUE);
    CREATE INDEX xmlids_record ON xmlids(model,source_id);
    CREATE TABLE groups(user_id INTEGER, group_id INTEGER, PRIMARY KEY(user_id,group_id));
    CREATE TABLE attachments(source_id INTEGER PRIMARY KEY, sha256 TEXT, size INTEGER);
    CREATE TABLE translations(model TEXT,source_id INTEGER,field TEXT,lang TEXT,value TEXT, PRIMARY KEY(model,source_id,field,lang));
    ''')
    blockers = set()
    try:
        info = inventory(con, settings(config).get('addons_path', '').split(','))
        info.update({'source_db': database, 'snapshot_id': str(uuid.uuid4()), 'frozen': frozen,
                     'format_version': 1, 'complete': False, 'sample_per_model': sample})
        with con.cursor() as cr:
            cr.execute('SELECT transaction_timestamp(), txid_current_snapshot()')
            stamp, snap = cr.fetchone()
            info.update(snapshot_time=str(stamp), postgres_snapshot=snap)
        save_json(stage / 'manifest.json', info)
        models = info['models']
        mapping = loads((Path(__file__).with_name('mappings.json')).read_text())
        rootset = set(info['roots']) | {'res.users', 'res.company'}
        need_buffer = set()
        def flush_needed():
            if need_buffer:
                db.executemany('INSERT OR IGNORE INTO needed SELECT ?,? WHERE NOT EXISTS '
                               '(SELECT 1 FROM records WHERE model=? AND source_id=?)',
                               [(m, i, m, i) for m, i in sorted(need_buffer)])
                need_buffer.clear()
        def need(model, ids):
            model = mapping.get('source_aliases', {}).get(model, model)
            ids = {int(x) for x in ids if x}
            if not ids or model in EXCLUDED:
                return
            if model not in models:
                blockers.add(f'Unknown related model: {model}')
                return
            if models[model]['transient']:
                blockers.add(f'Persistent record references transient model: {model}')
                return
            need_buffer.update((model, x) for x in ids)
            if len(need_buffer) >= 10000: flush_needed()

        def read_batch(model, after=None, ids=None, limit=2000):
            meta = models[model]
            if meta['table_kind'] != 'r':
                blockers.add(f'Reference to non-table model: {model}')
                return 0
            if not (model in rootset or model in NATIVE or model in LOOKUPS or any(
                    (mod or '').startswith('ab') for mod in meta['modules'])):
                blockers.add(f'Unsupported prerequisite model: {model}')
                return 0
            # Native runtime secrets and settings are intentionally not exported.
            names = list(meta['columns'])
            if model == 'ir.attachment':
                names = [n for n in names if n != 'access_token']
            if model == 'res.users':
                names = [n for n in names if n not in {'totp_secret', 'notification_type', 'signature'}]
                if 'password' not in names: names.append('password')
            query = sql.SQL('SELECT {} FROM {} WHERE {} ORDER BY id LIMIT %s').format(
                sql.SQL(',').join(map(sql.Identifier, names)), sql.Identifier(meta['table']),
                sql.SQL('id = ANY(%s)') if ids is not None else sql.SQL('id > %s'))
            with con.cursor(cursor_factory=RealDictCursor) as cr:
                cr.execute(query, [ids if ids is not None else after or 0, limit])
                rows = [dict(r) for r in cr]
            if not rows:
                return 0
            rowids = [r['id'] for r in rows]
            for child, inverse in mapping.get('inverse_links', {}).get(model, {}).items():
                with con.cursor() as cr:
                    cr.execute(sql.SQL('SELECT id FROM {} WHERE {}=ANY(%s)').format(
                        sql.Identifier(models[child]['table']), sql.Identifier(inverse)), [rowids])
                    need(child, [r[0] for r in cr])
            m2m = {}
            for fn, f in ([] if model in LOOKUPS else meta['fields'].items()):
                if f['ttype'] == 'many2many' and f['relation_table'] and not f['related']:
                    if f['relation'] in EXCLUDED or (model == 'res.users' and f['relation'] == 'res.groups'):
                        continue
                    with con.cursor() as cr:
                        cr.execute(sql.SQL('SELECT {},{} FROM {} WHERE {} = ANY(%s)').format(
                            sql.Identifier(f['column1']), sql.Identifier(f['column2']),
                            sql.Identifier(f['relation_table']), sql.Identifier(f['column1'])), [rowids])
                        for a, b in cr:
                            m2m.setdefault(a, {}).setdefault(fn, []).append(b)
            for row in rows:
                if model in ('ir.sequence', 'ir.sequence.date_range'):
                    with con.cursor() as cr:
                        parent = row['id'] if model == 'ir.sequence' else row['sequence_id']
                        cr.execute('SELECT implementation,number_increment FROM ir_sequence WHERE id=%s', [parent])
                        impl, increment = cr.fetchone()
                        if impl == 'standard':
                            seqname = ('ir_sequence_%03d' % parent) + (('_%03d' % row['id']) if model == 'ir.sequence.date_range' else '')
                            cr.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(seqname)))
                            last, called = cr.fetchone()
                            row['number_next'] = last + increment if called else last
                row['_m2m'] = {fn: m2m.get(row['id'], {}).get(fn, [])
                    for fn, f in meta['fields'].items() if model not in LOOKUPS
                    and f['ttype'] == 'many2many' and f['relation_table'] and not f['related']
                    and f['relation'] not in EXCLUDED
                    and not (model == 'res.users' and f['relation'] == 'res.groups')}
                for fn, f in ([] if model in LOOKUPS else meta['fields'].items()):
                    if f['ttype'] == 'many2one': need(f['relation'], [row.get(fn)])
                    elif f['ttype'] == 'many2many': need(f['relation'], row['_m2m'].get(fn, []))
                    elif f['ttype'] == 'reference' and row.get(fn):
                        try:
                            rm, ri = row[fn].rsplit(',', 1); need(rm, [int(ri)])
                        except (ValueError, AttributeError): blockers.add(f'Malformed reference: {model}.{fn}')
                for idfield, modelfield in mapping['polymorphic'].get(model, {}).items():
                    if row.get(idfield) and row.get(modelfield): need(row[modelfield], [row[idfield]])
                for fn, related in mapping.get('integer_links', {}).get(model, {}).items():
                    need(related, [row.get(fn)])
                if model == 'ab_accounting_tracking' and row.get('field_diff_json'):
                    try:
                        for changes in loads(row['field_diff_json']).values():
                            if isinstance(changes, list):
                                for item in changes:
                                    if isinstance(item, dict): need('res.users', [item.get('user_id')])
                    except (ValueError, AttributeError): blockers.add(f'Invalid accounting tracking JSON: {row["id"]}')
                db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?)', (model, row['id'], dumps(row)))
            # Copy XML identities even for seeded records and native metadata lookups.
            with con.cursor() as cr:
                cr.execute("SELECT res_id,module||'.'||name FROM ir_model_data WHERE model=%s AND res_id=ANY(%s)", [model, rowids])
                db.executemany('INSERT OR IGNORE INTO xmlids VALUES (?,?,?)', [(model, r, x) for r, x in cr])
                if model == 'res.users':
                    cr.execute('SELECT uid,gid FROM res_groups_users_rel WHERE uid=ANY(%s)', [rowids])
                    gs = list(cr)
                    db.executemany('INSERT OR IGNORE INTO groups VALUES (?,?)', gs)
                    need('res.groups', [g for _, g in gs])
            flush_needed()
            db.executemany('DELETE FROM needed WHERE model=? AND source_id=?', [(model, rid) for rid in rowids])
            db.commit()
            return max(rowids)

        with con.cursor() as cr:
            cr.execute("SELECT res_id FROM ir_model_data WHERE model='ir.sequence' AND module=ANY(%s)", [info['required_modules']])
            seqids = [r[0] for r in cr]
            need('ir.sequence', seqids)
            cr.execute('SELECT id FROM ir_sequence_date_range WHERE sequence_id=ANY(%s)', [seqids])
            need('ir.sequence.date_range', [r[0] for r in cr])
        for model in sorted(rootset):
            last = 0
            while True:
                nxt = read_batch(model, after=last, limit=sample or 2000)
                if not nxt or sample: break
                last = nxt
            print(f'Exported {model}', flush=True)
        flush_needed()
        while True:
            pending = db.execute('SELECT n.model,n.source_id FROM needed n LEFT JOIN records r '
                                 'ON r.model=n.model AND r.source_id=n.source_id WHERE r.source_id IS NULL LIMIT 2000').fetchall()
            if not pending: break
            grouped = {}
            for model, rid in pending: grouped.setdefault(model, []).append(rid)
            for model, ids in grouped.items():
                read_batch(model, ids=ids)
                for rid in ids:
                    if not db.execute('SELECT 1 FROM records WHERE model=? AND source_id=?', (model, rid)).fetchone():
                        blockers.add(f'Missing/unsupported related record: {model}:{rid}')
                        db.execute('DELETE FROM needed WHERE model=? AND source_id=?', (model, rid))
            db.commit()
        # Include attachments owned by the selected records, even without an explicit relation.
        for model, in db.execute('SELECT DISTINCT model FROM records').fetchall():
            if model in LOOKUPS or model == 'ir.attachment': continue
            with con.cursor(name='attachment_owners') as cr:
                cr.itersize = 2000
                cr.execute('SELECT id,res_id FROM ir_attachment WHERE res_model=%s', [model])
                ids = []
                for i, r in cr:
                    if db.execute('SELECT 1 FROM records WHERE model=? AND source_id=?', (model, r)).fetchone(): ids.append(i)
                    if len(ids) == 2000:
                        read_batch('ir.attachment', ids=ids)
                        ids.clear()
                if ids: read_batch('ir.attachment', ids=ids)
        flush_needed()
        while True:
            pending = db.execute('SELECT n.model,n.source_id FROM needed n LEFT JOIN records r '
                                 'ON r.model=n.model AND r.source_id=n.source_id WHERE r.source_id IS NULL LIMIT 2000').fetchall()
            if not pending: break
            grouped = {}
            for model, rid in pending: grouped.setdefault(model, []).append(rid)
            for model, ids in grouped.items():
                read_batch(model, ids=ids)
                for rid in ids:
                    if not db.execute('SELECT 1 FROM records WHERE model=? AND source_id=?', (model, rid)).fetchone():
                        blockers.add(f'Missing/unsupported related record: {model}:{rid}')
                        db.execute('DELETE FROM needed WHERE model=? AND source_id=?', (model, rid))
            db.commit()
        for model, in db.execute('SELECT DISTINCT model FROM records').fetchall():
            trans_fields = [n for n, f in models[model]['fields'].items() if f['translate'] and n in models[model]['columns']]
            if not trans_fields: continue
            with con.cursor(name='migration_translations') as cr:
                cr.itersize = 2000
                cr.execute("SELECT name,res_id,lang,value FROM ir_translation WHERE type='model' AND name=ANY(%s) AND value IS NOT NULL",
                           [[model + ',' + f for f in trans_fields]])
                for name, rid, lang, value in cr:
                    if db.execute('SELECT 1 FROM records WHERE model=? AND source_id=?', (model, rid)).fetchone():
                        db.execute('INSERT OR REPLACE INTO translations VALUES (?,?,?,?,?)', (model, rid, name.split(',', 1)[1], lang, value))
            db.commit()
        filestore = Path(filestore) if filestore else Path(settings(config).get('data_dir', '')) / 'filestore' / database
        blobs = private_dir(stage / 'blobs')
        for rid, data in db.execute("SELECT source_id,payload FROM records WHERE model='ir.attachment'"):
            row = loads(data)
            if row.get('type') == 'url': continue
            dest = blobs / str(rid)
            if row.get('store_fname'):
                src = safe_attachment_path(filestore, row['store_fname'])
                if not src.is_file():
                    blockers.add(f'Missing attachment file: ir.attachment:{rid}'); continue
                shutil.copyfile(src, dest)
            elif row.get('db_datas') is not None:
                dest.write_bytes(row['db_datas'])
            else:
                dest.write_bytes(b'')
            os.chmod(dest, 0o600)
            # Odoo 15 db_datas and filestore both hold raw bytes.
            if row.get('checksum') and digest(dest, 'sha1') != row['checksum']:
                blockers.add(f'Attachment source checksum mismatch: ir.attachment:{rid}')
            db.execute('INSERT INTO attachments VALUES (?,?,?)', (rid, digest(dest), dest.stat().st_size))
        db.commit()
        info['counts'] = dict(db.execute('SELECT model,count(*) FROM records GROUP BY model'))
        blockers.update(property_blockers(con, info['counts']))
        info['blockers'] = sorted(blockers)
        info['complete'] = False  # Final checkpoint and checksum must succeed first.
        save_json(stage / 'manifest.json', info)
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise MigrationError('Staging readers prevented final checkpoint; close readers before exporting again')
        db.close()
        info['records_sha256'] = digest(stage / 'records.sqlite')
        info['complete'] = not blockers
        save_json(stage / 'manifest.json', info)
        return {'complete': info['complete'], 'counts': info['counts'], 'blocker_count': len(info['blockers']),
                'blockers': info['blockers'][:20], 'report': str(stage / 'manifest.json')}
    finally:
        con.rollback(); con.close(); db.close()


def recover_files(stage, filestore):
    """Recover original bytes without changing the exported source snapshot."""
    info = loads((stage / 'manifest.json').read_text())
    if digest(stage / 'records.sqlite') != info.get('records_sha256'):
        raise MigrationError('Export is unfinished or changed; cannot recover files')
    # Never rewrite an export that is already complete or has entered an import.
    if info.get('complete') or (stage / 'before_import.dump').exists():
        raise MigrationError('Recovery is only allowed for incomplete, unimported exports')
    blockers = {b for b in info['blockers'] if not b.startswith(('Missing attachment file:', 'Attachment source checksum mismatch:'))}
    db = staging_db(stage / 'records.sqlite')
    try:
        for rid, payload in db.execute("SELECT source_id,payload FROM records WHERE model='ir.attachment'"):
            row = loads(payload)
            if row.get('type') == 'url': continue
            dest = stage / 'blobs' / str(rid)
            if row.get('store_fname'):
                src = safe_attachment_path(filestore, row['store_fname'])
                if not src.is_file():
                    blockers.add(f'Missing attachment file: ir.attachment:{rid}'); continue
                if row.get('checksum') and digest(src, 'sha1') != row['checksum']:
                    blockers.add(f'Attachment source checksum mismatch: ir.attachment:{rid}'); continue
                shutil.copyfile(src, dest)
                os.chmod(dest, 0o600)
            if not dest.is_file():
                blockers.add(f'Missing attachment file: ir.attachment:{rid}'); continue
            db.execute('INSERT OR REPLACE INTO attachments VALUES (?,?,?)', (rid, digest(dest), dest.stat().st_size))
        db.commit()
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise MigrationError('Staging readers prevented file recovery checkpoint')
    finally: db.close()
    info.update(blockers=sorted(blockers), complete=not blockers, records_sha256=digest(stage / 'records.sqlite'))
    save_json(stage / 'manifest.json', info)
    return {'complete': info['complete'], 'blocker_count': len(info['blockers']), 'blockers': info['blockers'][:20], 'report': str(stage / 'manifest.json')}


def supplement_inventory(config, database, stage, allow_source_defects=False):
    """Extend an older export with integer-linked headers visible in its snapshot.

    Never blend newer source row versions into the existing snapshot. Any changed,
    deleted, or unexported prerequisite requires a fresh export instead.
    """
    info = loads((stage / 'manifest.json').read_text())
    if info['source_db'] != database or (stage / 'before_import.dump').exists():
        raise MigrationError('Inventory extension requires the matching, unimported source export')
    if digest(stage / 'records.sqlite') != info.get('records_sha256'):
        raise MigrationError('Export must finish and pass its checksum before inventory extension')
    snapshot = info['postgres_snapshot']
    if int(snapshot.split(':')[1]) >= 2**32:
        raise MigrationError('Snapshot transaction epoch requires a fresh export with current mappings')
    db = staging_db(stage / 'records.sqlite')
    con = connect(config, database)
    added = 0
    try:
        ids = [r[0] for r in db.execute("SELECT DISTINCT json_extract(payload,'$.header_id') FROM records WHERE model='ab_inventory' AND json_extract(payload,'$.header_id')>0")]
        meta = info['models']['ab_inventory_header']
        for offset in range(0, len(ids), 2000):
            batch = ids[offset:offset+2000]
            with con.cursor(cursor_factory=RealDictCursor) as cr:
                cr.execute('SELECT *, txid_visible_in_snapshot(xmin::text::bigint,%s::txid_snapshot) AS snapshot_visible '
                           'FROM ab_inventory_header WHERE id=ANY(%s)', [snapshot, batch])
                rows = [dict(r) for r in cr]
            if len(rows) != len(batch): raise MigrationError('An inventory header was removed; a fresh export is required')
            for row in rows:
                if not row.pop('snapshot_visible'):
                    raise MigrationError('An inventory header changed since export; a fresh export is required')
                for fn, f in meta['fields'].items():
                    if f['ttype'] == 'many2one' and row.get(fn) and not db.execute(
                        'SELECT 1 FROM records WHERE model=? AND source_id=?', (f['relation'], row[fn])).fetchone():
                        raise MigrationError(f'Inventory header prerequisite missing: {f["relation"]}:{row[fn]}')
                if not allow_source_defects and row.get('res_id') and not db.execute('SELECT 1 FROM records WHERE model=? AND source_id=?',
                                                       (row['model_ref'], row['res_id'])).fetchone():
                    raise MigrationError('Inventory header references an unexported document; use a fresh export')
                row['_m2m'] = {}
                added += db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?)',
                                    ('ab_inventory_header', row['id'], dumps(row))).rowcount
            with con.cursor() as cr:
                cr.execute("SELECT res_id,module||'.'||name,txid_visible_in_snapshot(xmin::text::bigint,%s::txid_snapshot) "
                           "FROM ir_model_data WHERE model='ab_inventory_header' AND res_id=ANY(%s)", [snapshot, batch])
                for rid, xid, visible in cr:
                    if visible: db.execute('INSERT OR IGNORE INTO xmlids VALUES (?,?,?)', ('ab_inventory_header', rid, xid))
        db.commit()
        if db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()[0]:
            raise MigrationError('Readers prevented inventory extension checkpoint')
        info['counts']['ab_inventory_header'] = db.execute("SELECT count(*) FROM records WHERE model='ab_inventory_header'").fetchone()[0]
        info.setdefault('snapshot_extensions', []).append({'model': 'ab_inventory_header', 'added': added,
                    'validation': 'All source row versions visible in original PostgreSQL snapshot'})
        info['records_sha256'] = digest(stage / 'records.sqlite')
        save_json(stage / 'manifest.json', info)
        return {'added': added, 'snapshot_id': info['snapshot_id']}
    finally:
        db.close(); con.close()
