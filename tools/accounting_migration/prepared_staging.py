"""Transaction-coupled staging checkpoints, independent of live-table setup."""
import hashlib
from pathlib import Path
from psycopg2 import sql, errorcodes

from bulk import copy_column_order
from common import MigrationError, save_json
from prepared_checkpoints import META, read_all, write_checkpoint
from resume import fingerprint
import prepared_progress as progress

SCHEMA = 'prepared_migration_source'
VERSION = 1
IDENTITY_TABLES = {'res_users', 'res_partner'}


class HashStream:
    def __init__(self, file=None):
        self.file = file
        self.hash = hashlib.sha256()
        self.bytes = 0

    def write(self, value):
        if isinstance(value, str):
            value = value.encode('utf-8')
        self.hash.update(value)
        self.bytes += len(value)

    def read(self, size=-1):
        value = self.file.read(size)
        self.write(value)
        return value


class StagingLoader:
    def __init__(self, connection, stage, manifest, legacy_setup=None):
        self.con, self.stage, self.manifest = connection, Path(stage), manifest
        self.records = read_all(connection)
        if not self.records.get('run'):
            raise MigrationError('Owned run metadata is required before staging')
        if not manifest.get('complete') or not manifest.get('tables'):
            raise MigrationError('Complete original extraction is required for staging')
        self.binding = dict(version=VERSION, run=fingerprint(self.records['run']), snapshot=fingerprint(manifest))
        self.legacy_setup = legacy_setup
        self.report = dict(loaded=[], skipped=[], adopted=[], failed=[], passed=False)
        self.attempt = self.records.get('staging_attempt', {}).get('number', 0) + 1
        for table, meta in manifest['tables'].items():
            copy_column_order(table, meta)

    def source_identity(self, table):
        meta = self.manifest['tables'][table]
        return dict(binding=self.binding, table=table, sha256=meta['sha256'], bytes=meta['bytes'],
                    rows=meta['rows'], columns=[(c, meta['columns'][c]['type']) for c in meta['column_order']])

    def inspect(self, table):
        """Validate physical shape/count/index and fingerprint normalized rows."""
        meta = self.manifest['tables'][table]
        columns = meta['column_order']
        with self.con.cursor() as cr:
            cr.execute("SELECT a.attname,format_type(a.atttypid,a.atttypmod),a.attnotnull "
                       "FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid "
                       "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname=%s AND t.relname=%s "
                       "AND t.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum", [SCHEMA, table])
            layout = cr.fetchall()
            expected = [(c, meta['columns'][c]['type']) for c in columns]
            if [(name, typ) for name, typ, _ in layout] != expected:
                raise MigrationError(f'Staging schema missing or changed: {table}')
            cr.execute("SELECT array_agg(a.attname ORDER BY u.o) FROM pg_constraint k "
                       "JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
                       "JOIN pg_index i ON i.indexrelid=k.conindid "
                       "CROSS JOIN LATERAL unnest(k.conkey) WITH ORDINALITY u(num,o) "
                       "JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=u.num "
                       "WHERE n.nspname=%s AND t.relname=%s AND k.contype='p' "
                       "AND i.indisvalid AND i.indisready AND k.convalidated GROUP BY k.oid", [SCHEMA, table])
            primary_keys = [row[0] for row in cr.fetchall()]
            if primary_keys != ([['id']] if 'id' in columns else []):
                raise MigrationError(f'Staging primary key missing or changed: {table}')
            cr.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(SCHEMA, table)))
            count = cr.fetchone()[0]
            if count != meta['rows']:
                raise MigrationError(f'Staging row count mismatch: {table}')
            order = sql.Identifier('id') if 'id' in columns else sql.SQL(',').join(
                sql.SQL('{}::text COLLATE "C"').format(sql.Identifier(c)) for c in columns)
            query = sql.SQL("COPY (SELECT {} FROM {} ORDER BY {}) TO STDOUT WITH (FORMAT text, ENCODING 'UTF8')").format(
                sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(SCHEMA, table), order)
            output = HashStream()
            cr.copy_expert(query.as_string(self.con), output)
        return dict(schema=fingerprint(layout), content=output.hash.hexdigest(), rows=count)

    def verify_committed(self, table, marker):
        if marker.get('source') != self.source_identity(table):
            # JSON stores tuples as arrays; compare canonical fingerprints.
            if fingerprint(marker.get('source')) != fingerprint(self.source_identity(table)):
                raise MigrationError(f'Staging checkpoint belongs to different extraction: {table}')
        progress.begin('verify staging', table=table, operation='Verify committed staging checkpoint', monitor=True)
        if self.inspect(table) != marker.get('verified'):
            raise MigrationError(f'Committed staging data changed: {table}; no automatic replacement attempted')
        progress.finish('staging checkpoint verified; COPY skipped')

    def build_index(self, cr, table, columns):
        if 'id' in columns:
            progress.begin('index staging', table=table, operation='Create staging primary key', monitor=True)
            cr.execute(sql.SQL('ALTER TABLE {} ADD PRIMARY KEY (id)').format(sql.Identifier(SCHEMA, table)))

    def load(self, table, index):
        meta = self.manifest['tables'][table]
        columns = meta['column_order']
        file = self.stage / 'tables' / (table + '.copy')
        if file.resolve().parent != (self.stage / 'tables').resolve():
            raise MigrationError(f'Unsafe staging source path: {table}')
        with self.con.cursor() as cr:
            if table in IDENTITY_TABLES:
                cr.execute(sql.SQL('DROP TABLE IF EXISTS {}').format(sql.Identifier(SCHEMA, table)))
            cr.execute(sql.SQL('CREATE TABLE {} ({})').format(sql.Identifier(SCHEMA, table),
                sql.SQL(',').join(sql.SQL('{} {}').format(sql.Identifier(c), sql.SQL(meta['columns'][c]['type'])) for c in columns)))
            with file.open('rb') as data:
                stream = HashStream(data)
                progress.begin('staging COPY', table=table, operation='COPY FROM', monitor=True,
                               total=meta['rows'], bytes_total=meta['bytes'], table_index=index,
                               table_count=len(self.manifest['tables']))
                cr.copy_expert(sql.SQL('COPY {} ({}) FROM STDIN').format(sql.Identifier(SCHEMA, table),
                    sql.SQL(',').join(map(sql.Identifier, columns))).as_string(self.con), progress.InputCounter(stream))
                if stream.hash.hexdigest() != meta['sha256'] or stream.bytes != meta['bytes']:
                    raise MigrationError(f'Staging source file changed: {table}')
            progress.finish('COPY finished; pending staging commit')
            self.build_index(cr, table, columns)
        progress.begin('validate staging', table=table, operation='Validate staging table', monitor=True)
        return self.inspect(table)

    def report_progress(self):
        report = dict(self.report, attempt=self.attempt, binding=self.binding,
                      counts={name: len(self.report[name]) for name in ('loaded','skipped','adopted','failed')})
        save_json(self.stage / 'staging.json', report)

    def run(self):
        expected = dict(binding=self.binding, tables=sorted(self.manifest['tables']))
        saved = self.records.get('staging_run')
        if saved and saved != expected:
            raise MigrationError('Staging run snapshot/ownership metadata differs; original extraction is required')
        if self.legacy_setup and self.legacy_setup.get('snapshot') not in (None, self.binding['snapshot']):
            raise MigrationError('Legacy staging setup snapshot differs from original extraction')
        with self.con.cursor() as cr:
            cr.execute("SELECT t.relname FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace "
                       "WHERE n.nspname=%s AND t.relkind IN ('r','p','v','m','f')", [SCHEMA])
            existing = {row[0] for row in cr.fetchall()}
        allowed = set(self.manifest['tables']) | IDENTITY_TABLES
        if existing - allowed:
            raise MigrationError('Unexplained tables in private staging schema: ' + ', '.join(sorted(existing - allowed)))
        for table in existing:
            if self.records.get('staging:' + table):
                continue
            if self.legacy_setup:
                continue
            if table not in IDENTITY_TABLES or not self.records.get('identities'):
                raise MigrationError(f'Staging table has no success marker or committed setup evidence: {table}')
        # Verify all existing checkpoints before creating any new staging data.
        for table in self.manifest['tables']:
            marker = self.records.get('staging:' + table)
            if marker:
                self.verify_committed(table, marker)
        with self.con.cursor() as cr:
            cr.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(SCHEMA)))
            cr.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(SCHEMA)))
        write_checkpoint(self.con, 'staging_run', expected)
        write_checkpoint(self.con, 'staging_attempt', dict(number=self.attempt))
        self.con.commit()
        for index, table in enumerate(self.manifest['tables'], 1):
            if self.records.get('staging:' + table):
                self.report['skipped'].append(table)
                print(f'Skip committed staging table: {table}', flush=True)
                self.report_progress()
                continue
            if self.legacy_setup:
                # Legacy setup committed all source tables atomically. Verify
                # and adopt that evidence; never recopy after live changes.
                verified = self.inspect(table)
                action = 'adopted'
            else:
                try:
                    verified = self.load(table, index)
                    action = 'loaded'
                except Exception as exc:
                    self.con.rollback()
                    code = getattr(exc, 'pgcode', None)
                    failure = dict(table=table, binding=self.binding, error_type=type(exc).__name__,
                                   sqlstate=code, reason=errorcodes.lookup(code) if code else 'Staging COPY/index/validation failed')
                    write_checkpoint(self.con, 'staging_failure:' + table, failure)
                    write_checkpoint(self.con, f'staging_history:{self.attempt}:{table}', dict(failure, success=False))
                    self.con.commit()
                    self.report['failed'].append(failure)
                    self.report_progress()
                    progress.finish('staging table failed; transaction rolled back')
                    print(f'Staging failed: {table}; continuing other staging tables. See staging.json', flush=True)
                    continue
            marker = dict(source=self.source_identity(table), verified=verified, success=True)
            write_checkpoint(self.con, 'staging:' + table, marker)
            write_checkpoint(self.con, f'staging_history:{self.attempt}:{table}', dict(table=table, success=True, action=action))
            with self.con.cursor() as cr:
                cr.execute(sql.SQL('DELETE FROM {} WHERE name=%s').format(sql.Identifier(META, 'checkpoint')),
                           ['staging_failure:' + table])
            self.con.commit()
            self.report[action].append(table)
            progress.finish('staging checkpoint committed')
            self.report_progress()
        if self.report['failed']:
            self.report_progress()
            raise MigrationError('Staging incomplete; committed staging tables are retained. Rerun to retry failed tables; live copying has not started')
        write_checkpoint(self.con, 'staging_complete', expected)
        self.con.commit()
        self.report['passed'] = True
        self.report_progress()
        print(f'Staging complete: {len(self.report["loaded"])} loaded, {len(self.report["skipped"])} skipped, '
              f'{len(self.report["adopted"])} adopted; live-table copying follows successful preflight.', flush=True)
        return self.report
