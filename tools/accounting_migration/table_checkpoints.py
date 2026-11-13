"""Independent live-table transactions with durable, operation-level resume."""
from contextlib import contextmanager
from psycopg2 import sql, errorcodes

from common import MigrationError, save_json
from resume import fingerprint
from prepared_importer import META, WORK, ident
from prepared_snapshot import SCHEMA
from table_resume import ResumeState
from relationship_policy import RawReferencePolicy
from standard_protection import StandardProtection
import prepared_progress as progress


def validate_exceptions(rules):
    entries = rules.get('accepted_foreign_key_failures', [])
    if not isinstance(entries, list):
        raise MigrationError('accepted_foreign_key_failures must be a list')
    for entry in entries:
        if not isinstance(entry, dict) or any(
                not isinstance(entry.get(k), str) or not entry[k].strip()
                for k in ('table', 'constraint', 'reason')):
            raise MigrationError('Each accepted FK failure needs table, constraint, and reason')
    return {(e['table'], e['constraint']): e['reason'] for e in entries}


def safe_error(exc):
    """Never persist PostgreSQL DETAIL or exception text containing row values."""
    result = dict(error_type=type(exc).__name__)
    code = getattr(exc, 'pgcode', None)
    if code:
        result.update(sqlstate=code, reason=errorcodes.lookup(code))
    else:
        result['reason'] = 'Operation failed; inspect the named operation and schema'
    diag = getattr(exc, 'diag', None)
    if diag:
        for key in ('table_name', 'column_name', 'constraint_name'):
            if getattr(diag, key, None):
                result[key] = getattr(diag, key)
    return result


class TableMigration:
    def __init__(self, engine, checkpoint):
        self.engine = engine
        self.con = engine.con
        self.checkpoint = checkpoint
        self.all_models = set(engine.selected)
        self.all_relations = list(engine.relations)
        self.successful = set()
        self.failed_tables = []
        self.failed_fks = []
        self.constraints = []
        self.captures = []
        self.raw = getattr(engine,'relationship_policy',None)==RawReferencePolicy.name
        self.accepted = {} if self.raw else validate_exceptions(engine.rules)
        self.blocked = set()
        self.guard=StandardProtection(engine) if self.raw else None
        self.protected_constraints=[]
        self.committed = []
        self.report_errors = set()
        self.resume = ResumeState(engine, checkpoint)
        self.skipped = []
        previous_report = self.resume.records.get('table_result', {}).get('report', {})
        for name in ('missing_files', 'copied_files'):
            if name in previous_report:
                engine.report[name] = previous_report[name]
        if self.resume.setup and not self.raw:
            self.captures = self.resume.setup['captures']
            engine.incoming_scalars = {x['table']: x['columns'] for x in self.captures}
            engine.dynamic = self.resume.setup.get('dynamic', self.discover_dynamic())
        # Preserve last attempt's reports until compatibility checks pass.


    def write_reports(self):
        for name, value in (('failed_tables.json', self.failed_tables),
                            ('failed_foreign_keys.json', self.failed_fks)):
            try:
                save_json(self.engine.stage / name, value)
            except OSError:
                if name not in self.report_errors:
                    print(f'Could not write {self.engine.stage / name}; inspect database checkpoint records.', flush=True)
                self.report_errors.add(name)

    @contextmanager
    def scope(self, models, relations=()):
        e = self.engine
        previous = e.selected, e.relations
        e.selected, e.relations = set(models), list(relations)
        try:
            yield
        finally:
            e.selected, e.relations = previous

    def unit(self, table, operation, action, coverage=None, force=False, refresh_fingerprint=True):
        """Commit action and marker together; reuse checks only for known no-writes.

        refresh_fingerprint=False concerns this table only. The action still
        runs, including any writes to separately managed metadata/relations.
        """
        key = 'table:' + operation + ':' + table
        saved = self.resume.marker(table, operation)
        previous_coverage = saved.get('coverage')
        if previous_coverage is None and coverage is not None and 'models' in coverage:
            previous_coverage = dict(models=sorted(self.resume.original_models))
        if not force and saved.get('success') and previous_coverage == coverage:
            self.skipped.append(dict(table=table, operation=operation))
            print(f'Skip committed operation: {operation} {table}', flush=True)
            return True
        progress.begin(operation, table=table, operation=operation, monitor=True)
        try:
            if self.raw and operation!='validation':
                actual='ir_model_data' if operation=='xmlids' else table
                self.guard.require_write(actual,operation)
            if self.raw and operation!='validation' and (table in self.blocked or (operation=='xmlids' and 'ir_model_data' in self.blocked)):
                raise MigrationError('Protected reference or foreign-key lock prevents safe modification')
            rows = action()
            entry = dict(table=table, operation=operation, rows=rows, success=True, coverage=coverage, policy=getattr(self.engine,'relationship_policy','mapped_references_v1'))
            if refresh_fingerprint or not self.resume.has_full_fingerprint(table):
                self.resume.remember(table, operation)
            for model in self.all_models:
                if operation == 'copy' and self.engine.target[model]['table'] == table:
                    self.resume.state['definitions'][model] = self.resume.definition(model)
                    self.resume.state.setdefault('policies',{})[model]=entry['policy']
            self.resume.history(operation, table, entry)
            self.resume.save()
            with self.con.cursor() as cr:
                cr.execute(sql.SQL('DELETE FROM {} WHERE name=%s').format(ident(META,'checkpoint')),
                           ['failure:' + operation + ':' + table])
            self.checkpoint(self.con, key, entry)
            self.con.commit()
            self.resume.records[key] = entry
        except Exception as exc:
            self.con.rollback()
            # Failed transactions must not leave in-memory fingerprints ahead
            # of the database's authoritative resume marker.
            from table_resume import records
            self.resume.records = records(self.con)
            self.resume.state = self.resume.records.get('resume_state', self.resume.state)
            entry = dict(table=table, operation=operation, success=False, **safe_error(exc))
            if self.raw and operation!='validation':
                actual='ir_model_data' if operation=='xmlids' else table
                if not self.guard.can_alter(actual) and operation not in self.guard.technical_data.get(actual,set()):
                    entry['reason']='Protected public table: records and definitions must remain unchanged'
                elif table in self.blocked:
                    entry['reason']='Protected incoming reference or unavailable FK lock prevents safe modification'
            self.failed_tables.append(entry)
            self.resume.history(operation, table, entry)
            self.checkpoint(self.con, 'failure:' + operation + ':' + table, entry)
            self.con.commit()
            self.write_reports()
            progress.finish('failed; this table operation rolled back')
            print(f'Table operation failed: {operation} {table}; see failed_tables.json', flush=True)
            return False
        self.committed.append(entry)
        progress.finish('table checkpoint committed')
        self.write_reports()
        return True

    def discover_dynamic(self):
        e = self.engine
        excluded = {e.target[m]['table'] for m in self.all_models} | {p['table'] for p in self.all_relations}
        dynamic = set()
        for model, meta in e.target.items():
            table = meta['table']
            if table in excluded:
                continue
            for name, field in meta['fields'].items():
                if field.get('store') and field.get('type') == 'reference' and name in e.physical.get(table, {}):
                    dynamic.add((table, name, None))
        for table, columns in e.physical.items():
            if table not in excluded and table != 'ir_model_data' and {'res_model','res_id'} <= columns.keys():
                dynamic.add((table, 'res_id', 'res_model'))
        return sorted(dynamic, key=str)

    def collect_constraints(self):
        """Inspect current relevant constraints without touching live data."""
        e = self.engine
        tables = sorted({e.target[m]['table'] for m in self.all_models} |
                        {p['table'] for p in self.all_relations} |
                        ({'ir_attachment','ir_model_data'} & e.physical.keys() if self.raw else set()))
        e.execute("SELECT s.relname,k.conname,pg_get_constraintdef(k.oid),t.relname,"
                  "ARRAY(SELECT a.attname FROM unnest(k.conkey) WITH ORDINALITY u(n,o) "
                  "JOIN pg_attribute a ON a.attrelid=s.oid AND a.attnum=u.n ORDER BY u.o),"
                  "ARRAY(SELECT a.attname FROM unnest(k.confkey) WITH ORDINALITY u(n,o) "
                  "JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=u.n ORDER BY u.o) "
                  "FROM pg_constraint k JOIN pg_class s ON s.oid=k.conrelid "
                  "JOIN pg_class t ON t.oid=k.confrelid "
                  "JOIN pg_namespace n ON n.oid=s.relnamespace "
                  "JOIN pg_namespace tn ON tn.oid=t.relnamespace "
                  "WHERE k.contype='f' AND n.nspname='public' AND tn.nspname='public' "
                  "AND (s.relname=ANY(%s) OR t.relname=ANY(%s)) ORDER BY s.relname,k.conname",
                  [tables, tables])
        found = []
        for table, name, definition, parent, columns, referenced in e.cr.fetchall():
            statement = sql.SQL('ALTER TABLE public.{} ADD CONSTRAINT {} {}').format(
                ident(table), ident(name), sql.SQL(definition)).as_string(self.con)
            found.append(dict(table=table, constraint=name, definition=definition,
                                         referenced_table=parent, columns=columns,
                                         referenced_columns=referenced, restore_sql=statement))
        return found

    def setup(self):
        """Reuse original captures; constraints may be restored between attempts."""
        e = self.engine
        current = self.collect_constraints()
        if self.resume.setup:
            merged = {(x['table'], x['constraint']): x for x in self.resume.setup['constraints']}
            merged.update({(x['table'], x['constraint']): x for x in current})
            self.constraints = list(merged.values())
        else:
            self.constraints = current
        for index, (table, columns) in enumerate(sorted(e.incoming_scalars.items()) if not self.resume.setup else []):
            captured = ['id', *columns] if 'id' in e.physical[table] else list(e.physical[table])
            name = 'captured_' + str(index)
            e.execute(sql.SQL('CREATE TABLE {} AS SELECT {} FROM public.{}').format(
                ident(WORK, name), sql.SQL(',').join(map(ident, captured)), ident(table)))
            self.captures.append(dict(table=table, capture=name, columns=columns))
        self.dynamic_captures = dict((self.resume.setup or {}).get('dynamic_captures', {}))
        for table in sorted({t for t, _, _ in e.dynamic}):
            if table in self.dynamic_captures:
                continue
            if 'id' not in e.physical[table]:
                raise MigrationError(f'Dynamic-reference resume requires a row ID: {table}')
            name = 'dynamic_' + str(len(self.dynamic_captures))
            columns = {'id'}
            for t, column, discriminator in e.dynamic:
                if t == table:
                    columns.add(column)
                    if discriminator:
                        columns.add(discriminator)
            e.execute(sql.SQL('CREATE TABLE {} AS SELECT {} FROM public.{}').format(
                ident(WORK, name), sql.SQL(',').join(map(ident, sorted(columns))), ident(table)))
            self.dynamic_captures[table] = name
        setup = dict(constraints=self.constraints, captures=self.captures, started=True, snapshot=fingerprint(e.manifest),
                     dynamic=e.dynamic, dynamic_captures=self.dynamic_captures,
                     tables={m:e.target[m]['table'] for m in self.all_models})
        save_json(e.stage / 'table-setup.json', setup)
        previous = self.resume.records.get('table_result')
        needs_writes = not previous or bool(previous.get('failed_tables')) or self.resume.original_models != self.all_models
        if self.raw:
            protection=self.guard.protect_incoming(self.constraints)
            self.protected_constraints=[x for x in self.constraints if x.get('protected')]
            self.blocked.update(protection)
            for table,details in protection.items():
                e.audit.add('protected_standard_reference',table=table,references=details)
        if needs_writes:
            for item in current:
                if self.raw and not self.guard.can_alter(item['table']):
                    item['protected']=True
                    continue
                e.execute('SAVEPOINT drop_relationship_constraint')
                try:
                    e.execute("SET LOCAL lock_timeout='5s'")
                    e.execute(sql.SQL('ALTER TABLE public.{} DROP CONSTRAINT {}').format(
                        ident(item['table']), ident(item['constraint'])))
                    item['removed_this_attempt']=True
                except Exception as exc:
                    e.execute('ROLLBACK TO SAVEPOINT drop_relationship_constraint')
                    if not self.raw:
                        raise
                    self.blocked.update((item['table'],item['referenced_table']))
                    self.failed_tables.append(dict(table=item['table'],operation='drop_foreign_key',success=False,
                                                  constraint=item['constraint'],**safe_error(exc)))
                    e.audit.add('foreign_key_removal_failed',table=item['table'],constraint=item['constraint'],**safe_error(exc))
                finally:
                    e.execute('RELEASE SAVEPOINT drop_relationship_constraint')
        self.checkpoint(self.con, 'table_setup', setup)
        self.con.commit()
        self.resume.setup = setup

    def copy_model(self, model):
        e = self.engine
        if self.raw and model in e.plan_errors:
            raise MigrationError('Field conversion plan is unavailable for this table')
        expressions = e.plans[model]['expressions']
        e.execute(sql.SQL('DELETE FROM {}').format(e.dst(model)))
        e.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {} s').format(
            e.dst(model), sql.SQL(',').join(map(ident, expressions)),
            sql.SQL(',').join(expressions.values()), e.src(model)))
        rows = e.cr.rowcount
        if rows != e.manifest['tables'][e.models[model]['table']]['rows']:
            raise MigrationError('Custom table row count mismatch')
        with self.scope([model]):
            e.validate_custom()
            if not self.raw:
                e.repair_xmlids()
        e.reset_sequence(e.target[model]['table'])
        return rows

    def restore_incoming(self, item):
        e = self.engine
        table, columns = item['table'], item['columns']
        expressions = {}
        for column in (columns if 'id' in e.physical[table] else e.physical[table]):
            value = sql.SQL('s.{}').format(ident(column))
            model = columns.get(column)
            expressions[column] = e.incoming_value(model, value) if model in self.successful else value
        if 'id' in e.physical[table]:
            e.execute(sql.SQL('UPDATE public.{} t SET {} FROM {} s WHERE t.id=s.id').format(
                ident(table), sql.SQL(',').join(sql.SQL('{}={}').format(ident(c), v)
                                              for c, v in expressions.items()), ident(WORK, item['capture'])))
        else:
            e.execute(sql.SQL('DELETE FROM public.{}').format(ident(table)))
            e.execute(sql.SQL('INSERT INTO public.{} ({}) SELECT {} FROM {} s').format(
                ident(table), sql.SQL(',').join(map(ident, expressions)),
                sql.SQL(',').join(expressions.values()), ident(WORK, item['capture'])))
        return e.cr.rowcount

    def restore_dynamic(self, table, entries, models=None):
        e = self.engine
        rows = 0
        for _, column, discriminator in entries:
            value = sql.SQL('s.{}').format(ident(column))
            model = sql.SQL('s.{}').format(ident(discriminator)) if discriminator else sql.SQL("split_part({},',',1)").format(value)
            rid = value if discriminator else sql.SQL("nullif(split_part({},',',2),'')::bigint").format(value)
            mapped = e.incoming_value(model, rid)
            expression = mapped if discriminator else sql.SQL("{}||','||{}::text").format(model, mapped)
            e.execute(sql.SQL('UPDATE public.{} t SET {}={} FROM {} s WHERE t.id=s.id AND {}=ANY(%s) AND {} IS NOT NULL').format(
                ident(table), ident(column), expression, ident(WORK,self.dynamic_captures[table]), model, value),
                [sorted(self.successful if models is None else models)])
            rows += e.cr.rowcount
        return rows

    def restore_constraints(self):
        self.con.rollback()
        for item in self.constraints:
            try:
                self.engine.execute("SELECT pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class t ON t.oid=k.conrelid "
                                    "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' AND t.relname=%s AND k.conname=%s",
                                    [item['table'],item['constraint']])
                existing = self.engine.cr.fetchone()
                if self.raw and not self.guard.can_alter(item['table']):
                    item.update(protected=True,restored=bool(existing),definition_unchanged=True)
                    if not existing:
                        self.engine.audit.add('protected_constraint_previously_missing',table=item['table'],constraint=item['constraint'])
                    self.con.commit()
                    continue
                if existing and existing[0] != item['definition']:
                    raise MigrationError('Existing FK definition differs from saved restoration definition')
                if not existing:
                    self.engine.execute("SET LOCAL lock_timeout='5s'")
                    self.engine.execute(sql.SQL(item['restore_sql']))
                item['restored']=True
                self.resume.history('fk', item['table'] + ':' + item['constraint'], dict(success=True))
                self.checkpoint(self.con, 'fk:' + item['table'] + ':' + item['constraint'], dict(success=True))
                self.con.commit()
            except Exception as exc:
                self.con.rollback()
                reason = self.accepted.get((item['table'], item['constraint']))
                failure = dict(item, **safe_error(exc), accepted=reason is not None, accepted_reason=reason)
                if self.raw:
                    failure.update(severity='warning',blocking=False)
                item['restored']=False
                self.failed_fks.append(failure)
                if self.raw:
                    self.engine.audit.add('foreign_key_not_restored',table=item['table'],constraint=item['constraint'],**safe_error(exc))
                self.checkpoint(self.con, 'fk:' + item['table'] + ':' + item['constraint'], failure)
                self.con.commit()
                self.write_reports()
                if reason is None:
                    print(f'Foreign key not restored: {item["table"]}.{item["constraint"]}; see failed_foreign_keys.json', flush=True)
        self.write_reports()

    def eligible_relations(self):
        if self.raw:
            return list(self.all_relations)
        result = []
        tables = {p['table'] for p in self.all_relations}
        for table in sorted(tables):
            plans = [p for p in self.all_relations if p['table'] == table]
            dependencies = {m for p in plans for m in (p['source']['model'], p['source']['related'])
                            if m in self.all_models}
            if dependencies <= self.successful:
                result.extend(plans)
            else:
                self.failed_tables.append(dict(table=table, operation='relations', success=False,
                                              reason='Skipped: related custom table copy failed'))
        return result

    def copy_relation(self, table, plans):
        e = self.engine
        if not self.raw or not self.shared_relation(table):
            e.execute(sql.SQL('DELETE FROM public.{}').format(ident(table)))
        with self.scope(self.all_models if self.raw else self.successful, plans):
            for phase in ('custom', 'external', 'attachments'):
                e.load_relations(phase)
        return e.scalar(sql.SQL('SELECT count(*) FROM public.{}').format(ident(table)))

    def shared_relation(self, table):
        for model,meta in self.engine.target.items():
            if model in self.all_models:
                continue
            if any(f.get('type')=='many2many' and f.get('relation_table')==table for f in meta['fields'].values()):
                return True
        return False

    def run(self, source_root, target_root, validate_orm=None):
        e = self.engine
        self.resume.begin()
        self.setup()
        self.write_reports()
        try:
            for model in sorted(self.all_models):
                if self.unit(e.target[model]['table'], 'copy', lambda m=model: self.copy_model(m)):
                    self.successful.add(model)
            if self.raw:
                self.failed_tables.extend(e.relation_errors)
                for model in sorted(self.successful):
                    def aliases(model=model):
                        with self.scope([model]):
                            e.repair_xmlids()
                        return None
                    self.unit(e.target[model]['table'],'xmlids',aliases, refresh_fingerprint=False)
            for item in self.captures:
                covered = self.successful & set(item['columns'].values())
                self.unit(item['table'], 'incoming', lambda item=item: self.restore_incoming(item), coverage=dict(models=sorted(covered)))
            for table in sorted({p[0] for p in e.dynamic}):
                pending = self.successful - self.resume.coverage(table, 'incoming_dynamic')
                self.unit(table, 'incoming_dynamic', lambda t=table, models=pending: self.restore_dynamic(
                    t, [p for p in e.dynamic if p[0] == t], models), coverage=dict(models=sorted(self.successful)))
            for model in sorted(self.successful):
                def external(model=model):
                    with self.scope([model]):
                        e.external()
                    return None
                self.unit(e.target[model]['table'], 'external', external,
                          refresh_fingerprint=not self.raw or bool(e.plans[model]['deferred']))
            relations = self.eligible_relations()
            owners=self.all_models if self.raw else self.successful
            with self.scope(owners, relations):
                e.prepare_attachment_scope(excluded_owners=() if self.raw else self.all_models - self.successful)
                self.con.commit()
                attached = self.unit('ir_attachment', 'attachments', lambda: e.attachments(
                    source_root, target_root, restore_links=False, incremental=True),
                    coverage=dict(models=sorted(owners)))
            if attached:
                for model in sorted(self.successful):
                    self.unit(e.target[model]['table'], 'attachment_links', lambda m=model: e.restore_attachment_links(m),
                              refresh_fingerprint=not self.raw or bool(e.plans[model]['attachments']))
            loaded_relations = []
            for table in sorted({p['table'] for p in relations}):
                plans = [p for p in relations if p['table'] == table]
                if any(p['phase'] == 'attachments' for p in plans) and not attached:
                    self.failed_tables.append(dict(table=table, operation='relations', success=False,
                                                  reason='Skipped: attachment import failed'))
                    continue
                if self.unit(table, 'relations', lambda t=table, p=plans: self.copy_relation(t, p)):
                    loaded_relations.extend(plans)
            for model in sorted(self.successful):
                def validate(model=model):
                    with self.scope([model]):
                        e.validate_custom()
                        previous_policy=self.resume.marker(e.target[model]['table'],'copy').get('policy','mapped_references_v1')
                        if not self.raw or previous_policy==e.relationship_policy:
                            e.validate_values()
                    return None
                self.unit(e.target[model]['table'], 'validation', validate, force=True)
            for table in sorted({p['table'] for p in loaded_relations}):
                def validate_relation(table=table):
                    with self.scope([], [p for p in loaded_relations if p['table'] == table]):
                        e.validate_values()
                    return None
                self.unit(table, 'validation', validate_relation, force=True)
        finally:
            # Controlled interruption still attempts every original constraint.
            self.restore_constraints()
        if self.raw:
            e.audit.run(self.successful,self.constraints)
            self.con.commit()
        if validate_orm:
            def orm():
                try:
                    validate_orm(sorted(self.successful))
                except Exception as exc:
                    if not self.raw:
                        raise
                    e.audit.add('orm_audit_failed',error_type=type(exc).__name__,report='orm-validation.log')
                return None
            self.unit('registry', 'validation', orm, force=True)
        errors = bool(self.failed_tables or self.report_errors or (not self.raw and any(not f['accepted'] for f in self.failed_fks)))
        warnings = e.audit.count() if self.raw else 0
        status = ('finished_with_errors' if errors else 'complete_with_warnings' if warnings else 'complete') if self.raw else (
            'finished_with_errors' if errors else 'finished_with_exceptions' if self.failed_fks else 'complete')
        result = dict(passed=not errors, status=status, complete=True, committed=self.committed,
                      successful_models=sorted(self.successful), skipped=self.skipped, attempt=self.resume.attempt, failed_tables=self.failed_tables,
                      failed_foreign_keys=self.failed_fks, report=e.report, relationship_warnings=warnings,
                      policy=getattr(e,'relationship_policy','mapped_references_v1'), constraints=self.constraints,
                      report_errors=sorted(self.report_errors), source_access='read_only', stage=str(e.stage))
        if getattr(e, 'backup', None) is not None:
            result['backup'] = e.backup
        self.resume.finish(result)
        self.checkpoint(self.con, 'table_result', result)
        self.con.commit()
        self.write_reports()
        save_json(e.stage / ('attempt-' + str(self.resume.attempt) + '.json'), result)
        save_json(e.stage / 'verification.json', result)
        if self.raw:
            e.audit.write(result)
        print(f'{status}: {len(self.successful)} custom tables committed; '
              f'{len(self.failed_tables)} failed operations; {len(self.failed_fks)} missing foreign keys. '
              f'Reports: {e.stage}/failed_tables.json and {e.stage}/failed_foreign_keys.json', flush=True)
        return result
