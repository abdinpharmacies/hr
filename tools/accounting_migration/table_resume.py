"""Durable operation coverage and compatibility checks for format-2 runs."""
from psycopg2 import sql

from common import MigrationError, loads
from prepared_importer import META, WORK, HashWriter, ident
from resume import fingerprint


def records(connection):
    with connection.cursor() as cr:
        cr.execute(sql.SQL('SELECT name,value FROM {}').format(ident(META, 'checkpoint')))
        return {name: loads(value) for name, value in cr.fetchall()}


class ResumeState:
    VERSION = 1

    def __init__(self, engine, checkpoint):
        self.e, self.checkpoint = engine, checkpoint
        self.records = records(engine.con)
        self.setup = self.records.get('table_setup')
        self.state = self.records.get('resume_state', {})
        if self.state and self.state.get('version') != self.VERSION:
            raise MigrationError('Unsupported table resume metadata version')
        self.state.setdefault('version', self.VERSION)
        self.state.setdefault('checks', {})
        self.state.setdefault('definitions', {})
        self.original_models = {m for m in engine.selected
            if self.records.get('table:copy:' + engine.target[m]['table'], {}).get('success')}
        self.attempt = self.state.get('attempt', 0) + 1

    def marker(self, table, operation):
        return self.records.get('table:' + operation + ':' + table, {})

    def coverage(self, table, operation):
        marker = self.marker(table, operation)
        if not marker.get('success'):
            return set()
        # Old format-2 operations ran after all copy attempts. This is the set
        # they could have covered, not copies that succeed in the new attempt.
        return set(marker.get('coverage', {}).get('models', self.original_models))

    def definition(self, model, metadata=None):
        e = self.e
        metadata = e.target if metadata is None else metadata
        fields = set().union(*(e.plans[model][k] for k in ('expressions', 'deferred', 'attachments')))
        return fingerprint(dict(table=metadata[model]['table'], fields={name: {
            k: v for k, v in metadata[model]['fields'].get(name, {}).items()
            if k not in ('default', 'selection', 'string', 'help')}
            for name in sorted(fields)}))

    def digest(self, table, descriptor):
        e = self.e
        columns = descriptor['columns']
        query = sql.SQL('SELECT {} FROM public.{} t').format(
            sql.SQL(',').join(sql.SQL('t.{}').format(ident(c)) for c in columns), ident(table))
        if descriptor.get('attachment_map'):
            query += sql.SQL(' WHERE t.id IN (SELECT target_id FROM {})').format(ident(META, 'attachment_map'))
        elif descriptor.get('capture') and 'id' in columns:
            query += sql.SQL(' WHERE t.id IN (SELECT id FROM {})').format(ident(WORK, descriptor['capture']))
        query += sql.SQL(' ORDER BY {}').format(sql.SQL(',').join(map(ident, columns)))
        out = HashWriter()
        e.cr.copy_expert(sql.SQL('COPY ({}) TO STDOUT').format(query).as_string(e.con), out)
        return out.hash.hexdigest()

    def remember(self, table, operation):
        e = self.e
        if table not in e.physical or operation == 'validation':
            return
        for key, previous in self.state['checks'].items():
            if previous.get('table', key) == table:
                previous['hash'] = self.digest(table, previous)
        descriptor = dict(table=table, columns=list(e.physical[table]))
        if table == 'ir_attachment' and operation == 'attachments':
            descriptor['attachment_map'] = True
        elif operation in ('incoming', 'incoming_dynamic'):
            columns = set(e.incoming_scalars.get(table, {}))
            for t, column, discriminator in e.dynamic:
                if t == table:
                    columns.add(column)
                    if discriminator:
                        columns.add(discriminator)
            if 'id' in e.physical[table]:
                columns.add('id')
            descriptor['columns'] = sorted(columns)
            # Dynamic captures can cover different rows, so do not narrow them
            # to the scalar capture's IDs when both operations share a table.
            if not any(t == table for t, _, _ in e.dynamic):
                item = next((x for x in (self.setup or {}).get('captures', []) if x['table'] == table), None)
                if item:
                    descriptor['capture'] = item['capture']
        descriptor['hash'] = self.digest(table, descriptor)
        key = table + ':owned' if descriptor.get('attachment_map') else table
        self.state['checks'][key] = descriptor

    def save(self):
        self.state.update(attempt=self.attempt, revision=fingerprint([self.e.rules, self.e.conversions]),
                          rules=self.e.rules, conversions=self.e.conversions)
        self.checkpoint(self.e.con, 'resume_state', self.state)

    def check_values(self, model):
        e = self.e
        table = e.target[model]['table']
        fields = dict(e.plans[model]['expressions'])
        if self.marker(table, 'external').get('success'):
            fields.update(e.plans[model]['deferred'])
        if self.marker(table, 'attachment_links').get('success'):
            fields.update(e.plans[model]['attachments'])
        conditions = sql.SQL(' OR ').join(sql.SQL('t.{} IS DISTINCT FROM ({})::{}').format(
            ident(name), value, sql.SQL(e.physical[table][name]['type'])) for name, value in fields.items())
        e.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s FULL JOIN {} t USING(id) '
                      'WHERE s.id IS NULL OR t.id IS NULL OR {})').format(e.src(model), e.dst(model), conditions),
               f'Resume would change committed data or mappings: {model}; fix pending work without altering this table')
        if getattr(e,'relationship_policy',None):
            return  # XML-ID relationship conflicts belong in the audit report.
        e.fail(sql.SQL("SELECT EXISTS(SELECT 1 FROM {} s LEFT JOIN public.ir_model_data t USING(module,name) "
                      "WHERE s.model=%s AND s.module<>'__export__' "
                      'AND (t.id IS NULL OR t.model<>s.model OR t.res_id<>s.res_id))').format(ident('prepared_migration_source','ir_model_data')),
               f'Committed XML IDs changed: {model}', [model])

    def validate(self):
        e = self.e
        if self.setup and self.setup.get('snapshot') and self.setup['snapshot'] != fingerprint(e.manifest):
            raise MigrationError('Saved source snapshot differs from committed table setup')
        for model, table in (self.setup or {}).get('tables', {}).items():
            if model not in e.target or e.target[model]['table'] != table:
                raise MigrationError(f'Resume cannot change physical table identity: {model}')
        original = self.records.get('run', {}).get('rules')
        raw=bool(getattr(e,'relationship_policy',None))
        if not raw and self.original_models and not self.records.get('resume_state') and original and original != fingerprint([e.rules, e.conversions]):
            raise MigrationError('Existing format-2 run has no saved mapping baseline. Rerun once with its original '
                                 'mapping files to establish resume metadata, then apply failed-table corrections; no reset is needed')
        for key, descriptor in self.state['checks'].items():
            table = descriptor.get('table', key)
            if table not in e.physical or any(c not in e.physical[table] for c in descriptor['columns']):
                raise MigrationError(f'Committed table schema changed: {table}')
            if self.digest(table, descriptor) != descriptor['hash']:
                raise MigrationError(f'Committed table data changed outside migration: {table}; refusing to overwrite it')
        for model in sorted(self.original_models):
            if raw and self.marker(e.target[model]['table'],'copy').get('policy','mapped_references_v1') != e.relationship_policy:
                e.audit.add('previous_policy_preserved',model=model,table=e.target[model]['table'])
                continue
            definition = self.definition(model)
            old = self.state['definitions'].get(model)
            original_metadata = e.stage / 'target-schema.json'
            if not old and original_metadata.exists():
                metadata = loads(original_metadata.read_text())
                if model not in metadata:
                    raise MigrationError(f'Original schema metadata missing for committed table: {model}')
                old = self.definition(model, metadata)
            if old and old != definition:
                raise MigrationError(f'Mapping or model-definition change affects committed table: {model}')
            self.check_values(model)
            self.state['definitions'][model] = definition
        # Completed relation mappings must still produce the same associations.
        if raw:
            return
        previous = e.selected, e.relations
        try:
            e.selected = set(self.original_models)
            e.relations = [p for p in e.relations if self.marker(p['table'], 'relations').get('success')]
            e.prepare_attachment_scope(excluded_owners=set(previous[0]) - self.original_models)
            e.selected = set()
            e.validate_values(check_attachments=self.marker('ir_attachment', 'attachments').get('success', False))
        finally:
            e.selected, e.relations = previous

    def remap_incoming(self):
        e = self.e
        for model, mapping in e.rules.get('incoming_ids', {}).items():
            for old, new in mapping.items():
                e.execute(sql.SQL('SELECT new_id FROM {} WHERE model=%s AND old_id=%s').format(
                    ident(META, 'incoming_map')), [model, int(old)])
                row = e.cr.fetchone()
                if row and row[0] == int(new):
                    continue
                if not row:
                    raise MigrationError(f'Incoming correction has no original captured identity: {model}:{old}')
                for key in self.records:
                    if key.startswith(('table:incoming:', 'table:incoming_dynamic:')):
                        operation, table = key.split(':', 2)[1:]
                        if model in self.coverage(table, operation):
                            raise MigrationError(f'Incoming correction affects completed operation: {table} -> {model}')
                e.fail(sql.SQL('SELECT NOT EXISTS(SELECT 1 FROM {} WHERE id=%s)').format(e.src(model)),
                       f'Incoming correction source record absent: {model}', [int(new)])
                e.execute(sql.SQL('UPDATE {} SET new_id=%s WHERE model=%s AND old_id=%s').format(
                    ident(META, 'incoming_map')), [int(new), model, int(old)])

    def begin(self):
        self.validate()
        if self.setup and not getattr(self.e,'relationship_policy',None):
            self.remap_incoming()
        self.save()
        self.checkpoint(self.e.con, 'attempt:' + str(self.attempt), dict(status='running'))
        if self.setup:
            self.e.con.commit()

    def history(self, operation, table, entry):
        self.checkpoint(self.e.con, f'attempt:{self.attempt}:{operation}:{table}', entry)

    def finish(self, result):
        self.checkpoint(self.e.con, 'attempt:' + str(self.attempt), result)
