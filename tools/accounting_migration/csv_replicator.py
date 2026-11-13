"""CSV-only controller: direct COPY and typed XML-ID references, without ORM."""
import copy
import os
from pathlib import Path
import signal
import time
import uuid

from psycopg2 import sql
from availability import DatabaseGate, recover_target, target_offline
from common import MigrationError, connect, dumps, loads, save_json, ensure_backup, private_dir
from resume import fingerprint
from csv_plan import database_identity, discover, read_plan
from csv_copy import extract, verify_files, copy_table, restart_sequence
from csv_actions import ACTIONS, choose_actions, filestore_roots
from csv_relations import plan_operations, MappingContext, capture_target, endpoints, POLICY
from csv_relations import verified_path
from csv_verify import compare, verify_after, target_count
from csv_cleanup import delete_orphan_links
import prepared_progress as progress

SCHEMA = 'csv_replication'
FORMAT = 4


def read_state(connection):
    with connection.cursor() as cr:
        cr.execute('SELECT to_regnamespace(%s)', [SCHEMA])
        if cr.fetchone()[0] is None:
            return None
        cr.execute(sql.SQL('SELECT value FROM {} WHERE name=%s').format(sql.Identifier(SCHEMA, 'checkpoint')), ['state'])
        row = cr.fetchone()
        if row is None:
            raise MigrationError('CSV checkpoint schema has no owning run')
        return loads(row[0])


def save_state(connection, state):
    with connection.cursor() as cr:
        cr.execute(sql.SQL('INSERT INTO {} (name,value) VALUES (%s,%s) '
                           'ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value').format(sql.Identifier(SCHEMA, 'checkpoint')),
                   ['state', dumps(state)])


def initialize(connection, plan, state):
    old = read_state(connection)
    if old is not None:
        validate_history(old)
        if (old.get('format') == FORMAT and old.get('plan_id') == plan['plan_id']
                and old.get('identities') == plan['identities'] and old.get('stage') == state.get('stage')):
            return old
        key = 'archive:' + uuid.uuid4().hex
        with connection.cursor() as cr:
            cr.execute(sql.SQL('INSERT INTO {} (name,value) VALUES (%s,%s)').format(sql.Identifier(SCHEMA, 'checkpoint')),
                       [key, dumps(old)])
        state['previous_checkpoint'] = key
        state['constraints'] = copy.deepcopy(old['constraints'])
    else:
        with connection.cursor() as cr:
            cr.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(SCHEMA)))
            cr.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(SCHEMA)))
            cr.execute(sql.SQL('CREATE TABLE {} (name text PRIMARY KEY,value text NOT NULL)').format(sql.Identifier(SCHEMA, 'checkpoint')))
    save_state(connection, state)
    connection.commit()
    return state


def validate_history(state):
    required = {'source_schema', 'source_table', 'referenced_schema', 'referenced_table', 'name', 'definition'}
    if (not isinstance(state, dict) or state.get('format') not in (3, FORMAT) or not isinstance(state.get('operations'), dict)
            or not isinstance(state.get('constraints'), list)
            or any(not isinstance(item, dict) or not required <= item.keys()
                   or any(not isinstance(item[key], str) or not item[key] for key in required)
                   for item in state['constraints'])):
        raise MigrationError('Saved CSV recovery metadata is malformed or unsupported; retain it for repair')


def schema_signature(meta):
    # Registry rows may themselves be selected. Schema binding must not turn
    # their deliberate replacement into an impossible resume requirement.
    return fingerprint(dict(columns=meta['columns'], primary=meta['primary']))


def error_record(exc):
    result = dict(error_type=type(exc).__name__)
    if type(exc) is MigrationError:
        result['reason'] = str(exc)  # Our own messages contain identifiers, never row values.
    if getattr(exc, 'pgcode', None):
        result['sqlstate'] = exc.pgcode
    diag = getattr(exc, 'diag', None)
    for name in ('table_name', 'column_name', 'constraint_name'):
        if diag and getattr(diag, name, None):
            result[name] = getattr(diag, name)
    # Do not copy exception text: PostgreSQL DETAIL includes row payloads.
    return result


def exclusion_lines(exclusions):
    lines = []
    for item in exclusions:
        detail = item['reason'].replace('_', ' ')
        if item.get('endpoints'):
            detail += ': ' + ', '.join(f"{endpoint['table']} ({endpoint['reason'].replace('_', ' ')})"
                                       for endpoint in item['endpoints'])
        lines.append(f"- `{item['table']}`: skipped; {detail}")
    return lines


class CSVRunner:
    def __init__(self, connection, stage, plan, manifest, operations, state, exclusions=None):
        self.con, self.stage, self.plan = connection, Path(stage), plan
        self.manifest, self.operations, self.state = manifest, operations, state
        self.results = []
        self.exclusions = exclusions or []

    def persist(self):
        save_state(self.con, self.state)

    def validate_resume(self):
        # Legacy content-verification artifacts are deliberately not read.
        # Every current operation is checked again using row counts only.
        self.con.rollback()

    def capture_constraints(self, fks):
        captured = {(item['source_schema'], item['source_table'], item['name']): item
                    for item in self.state['constraints']}
        for item in fks:
            scope = getattr(self, 'write_tables', self.operations)
            touches = (item['source_schema'] == 'public' and item['source_table'] in scope) or (
                item['referenced_schema'] == 'public' and item['referenced_table'] in scope)
            if touches:
                key = (item['source_schema'], item['source_table'], item['name'])
                captured.setdefault(key, {**item, 'removed': False, 'restored': True})
        self.state['constraints'] = list(captured.values())
        self.persist()
        self.con.commit()  # Definitions must survive a kill before any DROP.

    def constraint(self, item):
        with self.con.cursor() as cr:
            cr.execute("SELECT pg_get_constraintdef(k.oid) FROM pg_constraint k "
                       "JOIN pg_class t ON t.oid=k.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace "
                       "WHERE n.nspname=%s AND t.relname=%s AND k.conname=%s",
                       [item['source_schema'], item['source_table'], item['name']])
            row = cr.fetchone()
            return row[0] if row else None

    def drop_constraints(self):
        blocked = set()
        for item in self.state['constraints']:
            pending = any(table in self.write_tables if hasattr(self, 'write_tables') else
                          table in self.operations and not self.state['operations'].get(table, {}).get('success')
                          for table in (item['source_table'], item['referenced_table']))
            if not pending:
                continue
            try:
                definition = self.constraint(item)
                if definition is not None and definition != item['definition']:
                    raise MigrationError('Saved FK definition changed')
                with self.con.cursor() as cr:
                    cr.execute("SET LOCAL lock_timeout='5s'")
                    if definition is not None:
                        cr.execute(sql.SQL('ALTER TABLE {} DROP CONSTRAINT {}').format(
                            sql.Identifier(item['source_schema'], item['source_table']), sql.Identifier(item['name'])))
                item.update(removed=True, restored=False)
                item.pop('drop_error', None)
                self.persist()
                self.con.commit()
            except Exception as exc:
                self.con.rollback()
                item['drop_error'] = error_record(exc)
                blocked.update((item['source_table'], item['referenced_table']))
                self.persist()
                self.con.commit()
        return blocked

    def restore_constraints(self):
        for item in self.state['constraints']:
            if not item.get('removed'):
                continue
            try:
                existing = self.constraint(item)
                if existing is None:
                    with self.con.cursor() as cr:
                        cr.execute("SET LOCAL lock_timeout='5s'")
                        cr.execute(sql.SQL('ALTER TABLE {} ADD CONSTRAINT {} {}').format(
                            sql.Identifier(item['source_schema'], item['source_table']), sql.Identifier(item['name']),
                            sql.SQL(item['definition'])))
                elif existing != item['definition']:
                    raise MigrationError('Restored FK definition differs')
                item.update(restored=True)
                item.pop('restore_error', None)
                self.persist()
                self.con.commit()
            except Exception as exc:
                self.con.rollback()
                item.update(restored=False, restore_error=error_record(exc))
                self.persist()
                self.con.commit()

    def mapper(self, table, check_records=False):
        spec = self.operations[table]
        if any(name not in spec['constants'] for name in spec.get('references', {})):
            return MappingContext(self.con, self.stage, self.manifest['xmlids'], self.target_mapping,
                                  table, spec, self.manifest['tables'][table]['columns'], check_records=check_records)
        return None

    def prepare(self):
        self.prepared, self.completed, self.copied, self.write_tables = {}, set(), set(), set()
        for table, spec in self.operations.items():
            started = time.monotonic()
            progress.begin('verify', table=table, operation='Compare source and target row counts',
                           total=self.manifest['tables'][table]['rows'], monitor=True)
            item = {}
            try:
                item['verification'] = compare(self.con, self.stage, table, self.manifest['tables'][table],
                                               self.plan['target']['columns'][table], spec)
                if spec.get('relation') or spec.get('force_copy') or not item['verification']['matches']:
                    self.write_tables.add(table)
            except Exception as exc:
                self.con.rollback()
                item['error'] = error_record(exc)
            item['verification_seconds'] = time.monotonic() - started
            self.prepared[table] = item
            progress.update(processed=item.get('verification', {}).get('actual', {}).get('rows'))
            progress.finish('row-count verification finished')
        # Replacing an endpoint can invalidate equal-count old links. Replay the
        # existing relation operation after those endpoint copies, without hashes.
        for table, spec in self.operations.items():
            if any(parent in self.write_tables for parent in spec.get('dependencies', [])):
                self.write_tables.add(table)

    def unit(self, table, blocked):
        if not hasattr(self, 'prepared'):
            self.target_mapping = capture_target(self.con, self.stage, self.manifest['xmlids'], self.operations)
            self.prepare()
        spec = self.operations[table]
        prepared = self.prepared[table]
        started = time.monotonic()
        file_meta = self.manifest['tables'][table]
        before = copy.deepcopy(self.state)
        mapper = None
        mapping = prepared.get('mapping')
        relation_counts = {} if spec.get('relation') else None
        verification = prepared.get('verification')
        progress.begin('copy', table=table, operation='Replace mapped M2M links' if spec.get('relation')
                       else 'Verify or copy current operation', total=file_meta['rows'], monitor=True)
        try:
            if 'error' in prepared:
                entry = dict(success=False, expected=file_meta['rows'], **prepared['error'])
                if mapping:
                    entry['mapping'] = mapping
                entry['verification_seconds'] = prepared['verification_seconds']
                self.state['operations'][table] = entry
                self.persist()
                self.con.commit()
                self.results.append(dict(table=table, status='failed', **entry))
                return
            if any(parent not in self.completed for parent in spec.get('dependencies', [])):
                raise MigrationError('Selected M2M endpoint copy did not commit')
            endpoint_copied = any(parent in self.copied for parent in spec.get('dependencies', []))
            matched = (verification['matches'] and not spec.get('force_copy')
                       and not spec.get('relation') and not endpoint_copied)
            if not matched:
                if table in blocked:
                    raise MigrationError('Required FK removal failed')
                mapper = self.mapper(table)
                rows = copy_table(self.con, self.stage, table, file_meta, self.plan['target']['columns'][table],
                                  spec['constants'], spec['mode'], mapper,
                                  relation=endpoints(self.plan['target'], table) if spec.get('relation') else None,
                                  relation_counts=relation_counts)
                if mapper:
                    mapping = mapper.finish()
                verification = verify_after(self.con, self.stage, table, self.plan['target']['columns'][table], spec, verification, copied_rows=rows)
                if not verification['matches']:
                    raise MigrationError('Copied table row count does not match expected count; operation rolled back')
            else:
                rows = 0
            columns = self.plan['target']['columns'][table]
            restart_sequence(self.con, table, columns, only_advance=matched)
            count = verification['actual']['rows']
            status = ('m2m_replaced' if spec.get('relation') else 'verified_existing' if matched
                      else 'forced_copy' if spec.get('force_copy') else 'copied')
            entry = dict(success=True, rows=rows, target_count=count, status=status,
                         force_copy=bool(spec.get('force_copy')),
                         copy_reason='m2m_replace' if spec.get('relation') else 'replicate_override' if spec.get('force_copy') else 'selected_endpoint_copied'
                         if endpoint_copied else 'count_differs' if not matched else None,
                         specification=fingerprint(spec), expected=file_meta['rows'], mode=spec['mode'],
                         seconds=time.monotonic() - started, verification_seconds=prepared['verification_seconds'],
                         verification=verification, comparison=prepared['verification'])
            if mapping:
                entry['mapping'] = mapping
            if relation_counts is not None:
                entry.update(relation_policy=spec['relation_policy'], relation_counts=relation_counts)
            self.state['operations'][table] = entry
            self.persist()
            self.con.commit()
            self.completed.add(table)
            if not matched:
                self.copied.add(table)
            self.results.append(dict(table=table, **entry))
            progress.finish('CSV table verified and checkpoint committed')
        except BaseException as exc:
            self.con.rollback()
            self.state = read_state(self.con) or before
            if mapper and not mapper.closed:
                mapping = mapper.finish()
            if not isinstance(exc, Exception):
                raise
            entry = dict(success=False, expected=file_meta['rows'], seconds=time.monotonic() - started,
                         force_copy=bool(spec.get('force_copy')), **error_record(exc))
            if mapping:
                entry['mapping'] = mapping
            if relation_counts is not None:
                entry['relation_counts'] = relation_counts
            if verification:
                entry['verification'] = verification
            self.state['operations'][table] = entry
            self.persist()
            self.con.commit()
            self.results.append(dict(table=table, status='failed', **entry))
            progress.finish('CSV copy failed; table rolled back')

    def cleanup_m2m(self):
        history = self.state.setdefault('m2m_cleanup', {})
        audit_history = self.state.setdefault('m2m_cleanup_history', [])
        if not isinstance(history, dict) or not isinstance(audit_history, list):
            raise MigrationError('Saved M2M cleanup metadata is malformed')
        registered = set(self.plan['source']['models'].values()) | set(self.plan['target']['models'].values())
        for table, spec in sorted(self.operations.items()):
            if not spec.get('relation'):
                continue
            started = time.monotonic()
            before = copy.deepcopy(self.state)
            outcome = None
            updated_count = None
            progress.begin('cleanup M2M', table=table, operation='Remove orphan links; pending commit', monitor=True)
            try:
                if not spec.get('dependencies') or any(parent not in self.completed for parent in spec['dependencies']):
                    entry = dict(success=True, status='skipped', reason='selected_endpoint_not_successful', deleted_links=0)
                else:
                    bindings = endpoints(self.plan['target'], table)
                    if (table in registered or len(bindings) != 2
                            or not set(bindings) <= self.plan['target']['columns'][table].keys()
                            or any(binding['table'] not in self.plan[side]['columns']
                                   for binding in bindings.values() for side in ('source', 'target'))):
                        raise MigrationError(f'Unsafe or ambiguous M2M cleanup binding: {table}')
                    outcome = delete_orphan_links(self.con, self.stage, table, bindings)
                    entry = dict(success=True, status='cleaned' if outcome['deleted_links'] else 'no_orphans', **outcome)
                    if outcome['deleted_links']:
                        updated_count = target_count(self.con, table)
                        entry['remaining_rows'] = updated_count
                        operation = self.state['operations'].get(table, {})
                        operation.update(target_count=updated_count, cleanup_deleted_links=outcome['deleted_links'])
                entry.update(attempt=self.state['attempt'], seconds=time.monotonic() - started)
                self.state['m2m_cleanup'][table] = entry
                if entry['deleted_links']:
                    self.state['m2m_cleanup_history'].append(dict(table=table, **entry))
                self.persist()
                self.con.commit()
                if updated_count is not None:
                    for result in self.results:
                        if result['table'] == table:
                            result.update(target_count=updated_count, cleanup_deleted_links=outcome['deleted_links'])
                progress.finish('M2M cleanup checkpoint committed')
            except BaseException as exc:
                self.con.rollback()
                self.state = read_state(self.con) or before
                if outcome and outcome.get('deleted_ids_file'):
                    (self.stage / outcome['deleted_ids_file']).unlink(missing_ok=True)
                if not isinstance(exc, Exception):
                    raise
                self.state.setdefault('m2m_cleanup', {})[table] = dict(
                    success=False, status='failed', deleted_links=0, attempt=self.state['attempt'],
                    seconds=time.monotonic() - started, **error_record(exc))
                self.persist()
                self.con.commit()
                progress.finish('M2M cleanup failed; deletions rolled back')

    def reports(self):
        failures = [dict(table=table, **entry) for table, entry in self.state['operations'].items()
                    if table in self.operations and not entry.get('success')]
        fks = []
        for item in self.state['constraints']:
            if item.get('removed') and not item.get('restored'):
                query = sql.SQL('ALTER TABLE {} ADD CONSTRAINT {} {}').format(
                    sql.Identifier(item['source_schema'], item['source_table']), sql.Identifier(item['name']), sql.SQL(item['definition']))
                fks.append({**item, 'restore_sql': query.as_string(self.con)})
        action_errors = [name for name, value in self.state.get('actions', {}).items() if not value.get('success')]
        successful = sum(bool(entry.get('success')) for table, entry in self.state['operations'].items() if table in self.operations)
        mapping_summary = {table: entry['mapping'] for table, entry in self.state['operations'].items()
                           if table in self.operations and entry.get('mapping')}
        skipped_links = sum(value['stats']['skipped_links'] for value in mapping_summary.values())
        cleanup = {table: entry for table, entry in self.state.get('m2m_cleanup', {}).items()
                   if self.operations.get(table, {}).get('relation') and entry.get('attempt') == self.state['attempt']}
        cleanup_errors = [dict(table=table, **entry) for table, entry in cleanup.items() if not entry.get('success')]
        deleted_links = sum(entry['deleted_links'] for entry in cleanup.values())
        status = 'finished_with_errors' if failures or action_errors or cleanup_errors else 'complete_with_warnings' if fks or skipped_links or self.exclusions or deleted_links else 'complete'
        result = dict(status=status, format=FORMAT, operations=self.results, failed_tables=failures,
                      failed_foreign_keys=fks, committed_tables=successful, actions=self.state.get('actions', {}),
                      attempt=self.state['attempt'], constraints=self.state['constraints'])
        result['ignored_tables'] = sorted(set(self.plan['tables']) - self.operations.keys())
        result['mapping'] = mapping_summary
        result['skipped_links'] = skipped_links
        result['excluded_tables'] = self.exclusions
        result.update(m2m_cleanup=cleanup, failed_m2m_cleanup=cleanup_errors, deleted_m2m_links=deleted_links)
        result['m2m_cleanup_history'] = [entry for entry in self.state.get('m2m_cleanup_history', [])
                                       if self.operations.get(entry['table'], {}).get('relation')]
        result['operation_counts'] = {name: sum(item.get('status') == name for item in self.results)
                                      for name in ('verified_existing', 'copied', 'forced_copy', 'm2m_replaced', 'failed')}
        result['m2m_replacements'] = {
            table: {key: entry[key] for key in ('success', 'status', 'relation_policy', 'relation_counts', 'seconds') if key in entry}
            for table, entry in self.state['operations'].items() if self.operations.get(table, {}).get('relation')}
        save_json(self.stage / 'mapping_report.json', mapping_summary)
        save_json(self.stage / 'm2m_cleanup_report.json', cleanup)
        save_json(self.stage / 'm2m_replacement_report.json', result['m2m_replacements'])
        save_json(self.stage / 'excluded_tables.json', self.exclusions)
        save_json(self.stage / 'verification_report.json', {
            table: {key: entry[key] for key in ('status', 'verification', 'comparison', 'verification_seconds') if key in entry}
            for table, entry in self.state['operations'].items() if table in self.operations})
        for name, data in (('csv-result.json', result), ('failed_tables.json', failures), ('failed_foreign_keys.json', fks)):
            save_json(self.stage / name, data)
        lines = ['# CSV replication report', '', f'Status: **{status}**',
                 f'Committed tables/relations: {successful}', f'Failed operations: {len(failures)}',
                 f'Foreign keys left absent: {len(fks)}', '', 'Operation outcomes: ' + dumps(result['operation_counts']), '',
                 '| Table | Outcome | Mode | Expected | Copied | Target count | Verify seconds | Write seconds |',
                 '|---|---|---|---:|---:|---:|---:|---:|']
        for table, entry in sorted(self.state['operations'].items()):
            if table not in self.operations:
                continue
            lines.append(f"| {table} | {entry.get('status', 'failed')} | {entry.get('mode', '')} | {entry.get('expected', '')} | {entry.get('rows', '')} | {entry.get('target_count', '')} | {entry.get('verification_seconds', 0):.3f} | {entry.get('seconds', 0):.3f} |")
        lines += ['', 'Ignored model tables: ' + ', '.join(result['ignored_tables']),
                  'FK definitions and repair SQL: `failed_foreign_keys.json`.',
                  f'M2M links skipped for missing XML-ID matches: {skipped_links}.',
                  'Typed mapping details: `mapping_report.json` and private SQLite artifacts.',
                  'Row-count verification details: `verification_report.json` (no content hashing).',
                  'M2M source/inserted/skipped/deduplicated counts: `m2m_replacement_report.json`.',
                  f'Orphan M2M links deleted: {deleted_links}; cleanup failures: {len(cleanup_errors)}.',
                  'M2M cleanup details and deleted endpoint ID files: `m2m_cleanup_report.json`.',
                  'No broad identity, relationship, or ORM audit was performed.']
        if self.exclusions:
            lines += ['', 'Tables/relations excluded because they do not exist on both sides:', ''] + exclusion_lines(self.exclusions)
        (self.stage / 'migration_report.md').write_text('\n'.join(lines) + '\n')
        self.state['result'] = dict(status=status, committed_tables=successful)
        self.persist()
        self.con.commit()
        save_json(self.stage / f'attempt-{self.state["attempt"]}.json', result)
        return result

    def run(self, fks, args=None, actions=()):
        self.results = []
        self.validate_resume()
        if not self.manifest.get('xmlids'):
            raise MigrationError('Retained source XML-ID snapshot is required; use a fresh CSV run')
        if (self.state['operations'].get('ir_model_data', {}).get('success')
                and 'ir_model_data' in self.operations):
            self.target_mapping = self.state.get('prepared_target_xmlids')
            if self.target_mapping is None:
                raise MigrationError('Prepared XML-ID snapshot absent after metadata replacement; use a fresh extraction generation')
            verified_path(self.stage, self.target_mapping)
        else:
            self.target_mapping = capture_target(self.con, self.stage, self.manifest['xmlids'], self.operations)
            if 'ir_model_data' in self.operations:
                self.state['prepared_target_xmlids'] = self.target_mapping
        self.prepare()
        self.state['attempt'] += 1
        self.capture_constraints(fks)
        try:
            blocked = self.drop_constraints()
            for table in sorted(self.operations, key=lambda name: (name not in self.plan['tables'], name)):
                self.unit(table, blocked)
            self.cleanup_m2m()
            for name in actions:
                marker = self.state['actions'].get(name, {})
                if marker.get('success'):
                    continue
                if not self.state['operations'].get('ir_attachment', {}).get('success'):
                    self.state['actions'][name] = dict(success=False, reason='Attachment table did not commit')
                    continue
                try:
                    file_state = self.stage / 'filestore-progress.json'
                    completed = loads(file_state.read_text()) if file_state.exists() else {}
                    outcome = ACTIONS[name](args, completed, lambda: save_json(file_state, completed))
                    self.state['actions'][name] = dict(success=True, **outcome)
                except Exception as exc:
                    self.state['actions'][name] = dict(success=False, **error_record(exc))
                self.persist()
                self.con.commit()
        finally:
            # Roll back before restoring: an interrupt must not commit COPY rows
            # merely because ALTER CONSTRAINT succeeds in the same transaction.
            self.con.rollback()
            self.restore_constraints()
        return self.reports()


def extraction_stage(base):
    pointer = base / 'active-extraction.json'
    if not pointer.exists():
        return base
    stage = (base / loads(pointer.read_text())['directory']).resolve()
    if not stage.is_relative_to(base.resolve()) or not stage.is_dir():
        raise MigrationError('Invalid CSV extraction generation pointer')
    return stage


def recover_csv_target(gate, stage, root):
    if not gate.online():
        candidates = []
        for pattern in ('csv_*/availability.json', 'csv_*/generation_*/availability.json'):
            for path in Path(root).glob(pattern):
                marker = loads(path.read_text())
                if marker.get('offline') and marker.get('database') == gate.database and marker.get('oid') == gate.oid:
                    candidates.append(path.parent)
        if len(candidates) != 1:
            raise MigrationError('Target offline: cannot uniquely identify CSV recovery marker; retain run artifacts for repair')
        recover_target(gate, candidates[0])
    else:
        recover_target(gate, stage)


def run(args, root):
    os.umask(0o077)
    exclusions = []
    plan, selected = read_plan(args.table_plan, exclusions)
    model_exclusions = list(exclusions)
    base = private_dir(Path(root) / ('csv_' + plan['plan_id']))
    stage = extraction_stage(base)
    actions = choose_actions(getattr(args, 'extra_actions', None), selected)
    if actions:
        filestore_roots(args)
    operations = {table: dict(mode='replace', constants=constants) for table, constants in selected.items()}
    gate, target, source = None, None, None
    previous_handler = signal.getsignal(signal.SIGTERM)

    def interrupted(*unused):
        raise KeyboardInterrupt()

    signal.signal(signal.SIGTERM, interrupted)
    progress.start(stage, args.target_config)
    try:
        gate = DatabaseGate(args.target_config, args.target_db)
        recover_csv_target(gate, stage, root)
        target = connect(args.target_config, args.target_db, readonly=False)
        progress.bind(target, gate)
        if database_identity(target, args.target_config) != plan['identities']['target']:
            raise MigrationError('CSV target database identity differs')
        old = read_state(target)
        if old:
            validate_history(old)
        same_run = bool(old and old.get('format') == FORMAT and old.get('plan_id') == plan['plan_id']
                        and old.get('identities') == plan['identities'] and old.get('stage') == str(stage.resolve()))
        target_meta = discover(target, args.target_config)
        if schema_signature(target_meta) != schema_signature(plan['target']):
            raise MigrationError('Target schema differs from CSV export; re-export the plan')
        target.rollback()
        if same_run and getattr(args, 'extra_actions', None) is None:
            actions = old.get('requested_actions', [])
        if same_run and actions != old.get('requested_actions', []):
            raise MigrationError('Extra actions differ from the saved CSV run')
        if actions:
            filestore_roots(args)
        if not operations:
            print('CSV plan selects no tables; no backup, downtime, or database writes.', flush=True)
            result = dict(status='complete_with_warnings' if exclusions else 'complete', committed_tables=0,
                          failed_tables=[], failed_foreign_keys=[], operations=[], excluded_tables=exclusions)
            save_json(stage / 'excluded_tables.json', exclusions)
            save_json(stage / 'csv-result.json', result)
            (stage / 'migration_report.md').write_text('\n'.join([
                '# CSV replication report', '', 'Status: **' + result['status'] + '**', '',
                'No eligible tables selected; no backup, downtime, or database writes.', '', *exclusion_lines(exclusions)]) + '\n')
            for line in exclusion_lines(exclusions):
                print(line, flush=True)
            return result
        extraction = stage / 'csv-extraction.json'
        manifest = loads(extraction.read_text()) if extraction.exists() else None
        source = connect(args.source_config, args.source_db, readonly=True)
        if database_identity(source, args.source_config) != plan['identities']['source']:
            raise MigrationError('CSV source database identity differs')
        compatible = bool(manifest and manifest.get('complete') and manifest.get('mapping_policy') == POLICY
                          and manifest.get('relation_metadata') and manifest.get('xmlids'))
        if compatible:
            plan = {**plan, **{name: {**plan[name], **meta} for name, meta in manifest['relation_metadata'].items()}}
            exclusions[:] = model_exclusions
            operations = plan_operations(plan['source'], plan['target'], selected, exclusions, plan['force_tables'])
            required_models = {ref['source_model'] for op in operations.values() for ref in op.get('references', {}).values()}
            compatible = set(operations) <= manifest['tables'].keys() and required_models <= set(manifest['xmlids']['models'])
        if not compatible:
            source_meta = discover(source, args.source_config)
            if schema_signature(source_meta) != schema_signature(plan['source']):
                raise MigrationError('Source schema differs from CSV export; re-export the plan')
            plan = {**plan, 'source': source_meta, 'target': target_meta}
            exclusions[:] = model_exclusions
            operations = plan_operations(source_meta, target_meta, selected, exclusions, plan['force_tables'])
            if manifest is not None or old is not None or (stage / 'tables').exists():
                stage = private_dir(base / ('generation_' + uuid.uuid4().hex))
                same_run = False
                progress.stop()
                progress.start(stage, args.target_config)
                progress.bind(target, gate)
            manifest = extract(source, stage / 'tables', operations, plan['source'], plan['target'])
            save_json(base / 'active-extraction.json', dict(directory=stage.relative_to(base).as_posix()))
        source.close()
        source = None
        if any(table not in manifest['tables'] for table in operations):
            raise MigrationError('New selection has no retained source data; use a fresh run')
        verify_files(stage, manifest)
        state = old if same_run else dict(format=FORMAT, plan_id=plan['plan_id'], identities=plan['identities'],
                            stage=str(stage.resolve()),
                            operations={}, constraints=[], actions={}, requested_actions=actions, attempt=0)
        runner = CSVRunner(target, stage, plan, manifest, operations, state, exclusions)
        if same_run:
            runner.validate_resume()
        for name, entry in state['actions'].items():
            if entry.get('success') and name not in actions:
                raise MigrationError('Cannot remove a committed extra action on resume')
        print(f'CSV replication run: {stage}\nSelected model tables: {len(selected)}; derived M2M: {len(operations) - len(selected)}', flush=True)
        for line in exclusion_lines(exclusions):
            print(line, flush=True)
        ensure_backup(args.target_config, args.target_db, stage, progress=progress)
        with target_offline(gate, target, stage):
            # Metadata read before extraction/backup can become stale while the
            # target is online. Capture current incoming FKs only after gating,
            # otherwise a newly added CASCADE could affect ignored rows.
            live_meta = discover(target, args.target_config)
            if schema_signature(live_meta) != schema_signature(plan['target']):
                raise MigrationError('Target schema changed before exclusive access')
            state = initialize(target, plan, state)
            runner = CSVRunner(target, stage, plan, manifest, operations, state, exclusions)
            result = runner.run(live_meta['fks'], args, actions)
        print(f'CSV replication finished: {result["status"]}. Reports: {stage}', flush=True)
        return result
    finally:
        if source is not None:
            source.close()
        if target is not None:
            target.close()
        if gate is not None:
            gate.close()
        progress.stop()
        signal.signal(signal.SIGTERM, previous_handler)
