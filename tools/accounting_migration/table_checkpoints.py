"""Independent live-table transactions. Deliberately no partial-run recovery."""
from contextlib import contextmanager
from psycopg2 import sql, errorcodes

from common import MigrationError, save_json
from prepared_importer import WORK, ident
from prepared_snapshot import SCHEMA
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
        self.accepted = validate_exceptions(engine.rules)
        self.committed = []
        self.report_errors = set()
        self.write_reports()

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

    def unit(self, table, operation, action):
        """The live operation and its success marker have exactly one commit."""
        progress.begin(operation, table=table, operation=operation, monitor=True)
        try:
            rows = action()
            entry = dict(table=table, operation=operation, rows=rows, success=True)
            self.checkpoint(self.con, 'table:' + operation + ':' + table, entry)
            self.con.commit()
        except Exception as exc:
            self.con.rollback()
            entry = dict(table=table, operation=operation, success=False, **safe_error(exc))
            self.failed_tables.append(entry)
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

    def setup(self):
        """Commit captures, original constraints, and the partial-run guard together."""
        e = self.engine
        tables = sorted({e.target[m]['table'] for m in self.all_models} |
                        {p['table'] for p in self.all_relations})
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
        for table, name, definition, parent, columns, referenced in e.cr.fetchall():
            statement = sql.SQL('ALTER TABLE public.{} ADD CONSTRAINT {} {}').format(
                ident(table), ident(name), sql.SQL(definition)).as_string(self.con)
            self.constraints.append(dict(table=table, constraint=name, definition=definition,
                                         referenced_table=parent, columns=columns,
                                         referenced_columns=referenced, restore_sql=statement))
        for index, (table, columns) in enumerate(sorted(e.incoming_scalars.items())):
            captured = ['id', *columns] if 'id' in e.physical[table] else list(e.physical[table])
            name = 'captured_' + str(index)
            e.execute(sql.SQL('CREATE TABLE {} AS SELECT {} FROM public.{}').format(
                ident(WORK, name), sql.SQL(',').join(map(ident, captured)), ident(table)))
            self.captures.append(dict(table=table, capture=name, columns=columns))
        setup = dict(constraints=self.constraints, captures=self.captures, started=True)
        save_json(e.stage / 'table-setup.json', setup)
        for item in self.constraints:
            e.execute(sql.SQL('ALTER TABLE public.{} DROP CONSTRAINT {}').format(
                ident(item['table']), ident(item['constraint'])))
        self.checkpoint(self.con, 'table_setup', setup)
        self.con.commit()

    def copy_model(self, model):
        e = self.engine
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

    def restore_dynamic(self, table, entries):
        e = self.engine
        rows = 0
        for _, column, discriminator in entries:
            value = sql.SQL('t.{}').format(ident(column))
            model = sql.SQL('t.{}').format(ident(discriminator)) if discriminator else sql.SQL("split_part({},',',1)").format(value)
            rid = value if discriminator else sql.SQL("nullif(split_part({},',',2),'')::bigint").format(value)
            mapped = e.incoming_value(model, rid)
            expression = mapped if discriminator else sql.SQL("{}||','||{}::text").format(model, mapped)
            e.execute(sql.SQL('UPDATE public.{} t SET {}={} WHERE {}=ANY(%s) AND {} IS NOT NULL').format(
                ident(table), ident(column), expression, model, value), [sorted(self.successful)])
            rows += e.cr.rowcount
        return rows

    def restore_constraints(self):
        self.con.rollback()
        for item in self.constraints:
            try:
                self.engine.execute(sql.SQL(item['restore_sql']))
                self.checkpoint(self.con, 'fk:' + item['table'] + ':' + item['constraint'], dict(success=True))
                self.con.commit()
            except Exception as exc:
                self.con.rollback()
                reason = self.accepted.get((item['table'], item['constraint']))
                failure = dict(item, **safe_error(exc), accepted=reason is not None, accepted_reason=reason)
                self.failed_fks.append(failure)
                self.checkpoint(self.con, 'fk:' + item['table'] + ':' + item['constraint'], failure)
                self.con.commit()
                self.write_reports()
                if reason is None:
                    print(f'Foreign key not restored: {item["table"]}.{item["constraint"]}; see failed_foreign_keys.json', flush=True)
        self.write_reports()

    def eligible_relations(self):
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
        e.execute(sql.SQL('DELETE FROM public.{}').format(ident(table)))
        with self.scope(self.successful, plans):
            for phase in ('custom', 'external', 'attachments'):
                e.load_relations(phase)
        return e.scalar(sql.SQL('SELECT count(*) FROM public.{}').format(ident(table)))

    def run(self, source_root, target_root, validate_orm=None):
        e = self.engine
        self.setup()
        try:
            for model in sorted(self.all_models):
                if self.unit(e.target[model]['table'], 'copy', lambda m=model: self.copy_model(m)):
                    self.successful.add(model)
            for item in self.captures:
                self.unit(item['table'], 'incoming', lambda item=item: self.restore_incoming(item))
            for table in sorted({p[0] for p in e.dynamic}):
                self.unit(table, 'incoming_dynamic', lambda t=table: self.restore_dynamic(t, [p for p in e.dynamic if p[0] == t]))
            for model in sorted(self.successful):
                def external(model=model):
                    with self.scope([model]):
                        e.external()
                    return None
                self.unit(e.target[model]['table'], 'external', external)
            relations = self.eligible_relations()
            with self.scope(self.successful, relations):
                e.prepare_attachment_scope(excluded_owners=self.all_models - self.successful)
                self.con.commit()
                attached = self.unit('ir_attachment', 'attachments', lambda: e.attachments(
                    source_root, target_root, restore_links=False))
            if attached:
                for model in sorted(self.successful):
                    self.unit(e.target[model]['table'], 'attachment_links', lambda m=model: e.restore_attachment_links(m))
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
                        e.validate_values()
                    return None
                self.unit(e.target[model]['table'], 'validation', validate)
            for table in sorted({p['table'] for p in loaded_relations}):
                def validate_relation(table=table):
                    with self.scope([], [p for p in loaded_relations if p['table'] == table]):
                        e.validate_values()
                    return None
                self.unit(table, 'validation', validate_relation)
        finally:
            # Controlled interruption still attempts every original constraint.
            self.restore_constraints()
        if validate_orm:
            self.unit('registry', 'validation', lambda: validate_orm(sorted(self.successful)))
        errors = bool(self.failed_tables or self.report_errors or any(not f['accepted'] for f in self.failed_fks))
        status = 'finished_with_errors' if errors else 'finished_with_exceptions' if self.failed_fks else 'complete'
        result = dict(passed=not errors, status=status, complete=True, committed=self.committed,
                      successful_models=sorted(self.successful), failed_tables=self.failed_tables,
                      failed_foreign_keys=self.failed_fks, report=e.report,
                      report_errors=sorted(self.report_errors), source_access='read_only', stage=str(e.stage))
        self.checkpoint(self.con, 'table_result', result)
        self.con.commit()
        self.write_reports()
        save_json(e.stage / 'verification.json', result)
        print(f'{status}: {len(self.successful)} custom tables committed; '
              f'{len(self.failed_tables)} failed operations; {len(self.failed_fks)} missing foreign keys. '
              f'Reports: {e.stage}/failed_tables.json and {e.stage}/failed_foreign_keys.json', flush=True)
        return result
