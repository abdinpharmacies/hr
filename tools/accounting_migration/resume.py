"""Owned-run discovery and transaction-coupled recovery checkpoints."""
import hashlib
import json
from pathlib import Path
from common import MigrationError, loads, digest
from progress import current

FORMAT = 1
MAPPING_VERSION = 1
BUSINESS_VERSION = 1


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def endpoint(config):
    from common import settings
    opts = settings(config)
    return {k: opts.get(k, '') for k in ('db_host', 'db_port', 'db_user')}


def find_run(root, source, target, comment):
    candidates = []
    for path in Path(root).glob('*/target.json'):
        marker = loads(path.read_text())
        if marker.get('database') == target and marker.get('source') == source:
            candidates.append((path.parent, marker))
    if len(candidates) != 1:
        raise MigrationError('Target already exists: expected exactly one matching owned migration run')
    stage, marker = candidates[0]
    if not marker.get('ownership_token') or comment != 'accounting_migration:' + marker['ownership_token']:
        raise MigrationError('Existing target ownership token does not match its migration run')
    return stage, marker


def assert_exclusive(cursor, database):
    cursor.execute("SELECT pid FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid() "
                   "AND backend_type='client backend'", [database])
    if cursor.fetchall():
        raise MigrationError('Other sessions are connected to the target; close them before resuming. No sessions were terminated.')


def get_checkpoint(cr, name):
    cr.execute('SELECT value FROM accounting_migration.checkpoint WHERE name=%s', [name])
    row = cr.fetchone()
    return loads(row[0]) if row else None


def put_checkpoint(cr, name, value):
    # Caller commits this write together with the data it describes.
    cr.execute('INSERT INTO accounting_migration.checkpoint(name,value) VALUES (%s,%s) '
               'ON CONFLICT (name) DO UPDATE SET value=EXCLUDED.value', [name, json.dumps(value, sort_keys=True)])


def require_compatible(saved, expected, name):
    if saved is not None and saved.get('identity') != expected:
        raise MigrationError(f'Incompatible {name} checkpoint; retained data was not changed. Use a new target or review an explicit recovery adapter.')
    return saved is not None


def verify_files(stage, manifest):
    for table, meta in manifest['tables'].items():
        current().begin('resume verification', table=table, operation='verify extraction checksum')
        path = Path(stage) / 'tables' / (table + '.copy')
        if not path.is_file() or path.stat().st_size != meta['bytes'] or digest(path) != meta['sha256']:
            raise MigrationError(f'Extraction checksum mismatch: {table}')


def verify_staged(cr, table, meta, count_rows=True):
    from psycopg2 import sql
    cr.execute("SELECT a.attname,format_type(a.atttypid,a.atttypmod) FROM pg_attribute a "
               "WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum",
               ['accounting_migration_source.' + table])
    actual = cr.fetchall()
    expected = [(name, meta['columns'][name]['type']) for name in meta['column_order']]
    if actual != expected:
        raise MigrationError(f'Staging schema mismatch: {table}')
    if count_rows:
        cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier('accounting_migration_source', table)))
        if cr.fetchone()[0] != meta['rows']:
            raise MigrationError(f'Staging row count mismatch: {table}')
    if 'id' in meta['columns']:
        cr.execute("SELECT EXISTS(SELECT 1 FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid "
                   "AND a.attnum=ANY(i.indkey) WHERE i.indrelid=to_regclass(%s) AND i.indisprimary "
                   "AND i.indisvalid AND i.indnkeyatts=1 AND a.attname='id')", ['accounting_migration_source.' + table])
        if not cr.fetchone()[0]:
            raise MigrationError(f'Staging primary index missing: {table}')


def bind_manifest(cr, manifest):
    identity = fingerprint(manifest)
    saved = get_checkpoint(cr, 'manifest')
    if not require_compatible(saved, identity, 'extraction'):
        put_checkpoint(cr, 'manifest', {'identity': identity, 'format': FORMAT})
        cr.execute('UPDATE accounting_migration.run SET snapshot_id=%s WHERE id', [identity])
    return identity


def legacy_evidence(stage, manifest, cr):
    """Only adopt the known, pre-checkpoint schema-validation failure shape."""
    report = None
    for directory in [Path(stage), *sorted((Path(stage) / 'attempts').glob('*'), reverse=True)]:
        error_path, report_path = directory / 'bulk-error.json', directory / 'verification.json'
        if not error_path.exists() or not report_path.exists():
            continue
        error, candidate = loads(error_path.read_text()), loads(report_path.read_text())
        if (error.get('phase') == 'schema adaptation' and not candidate.get('passed')
                and all(candidate.get('tables', {}).get(name, {}).get('source_rows') == meta['rows']
                        for name, meta in manifest['tables'].items())):
            report = candidate
            break
    if report is None:
        raise MigrationError('Uncheckpointed staging has no compatible failure evidence')
    cr.execute('SELECT count(*) FROM accounting_migration.record_map')
    if cr.fetchone()[0]:
        raise MigrationError('Legacy staging has unexpected committed identity mappings')
    for name, meta in manifest['tables'].items():
        if report.get('tables', {}).get(name, {}).get('source_rows') != meta['rows']:
            raise MigrationError(f'Legacy COPY evidence is incomplete: {name}')
    return report
