"""Set-based ID resolution for explicit and identity mapping strategies."""
from psycopg2 import sql
from common import MigrationError, LOOKUPS
from progress import current

MIXED_MAPPING_VERSION = 3


class MappingStrategies:
    def identity_model(self, model):
        return getattr(self, 'mapping_modes', {}).get(model) == 'identity'

    def identity_source(self, model):
        if model in getattr(self, 'quarantine_models', set()):
            return self.src(model)
        return sql.Identifier('accounting_migration_source', self.models[model]['table'])

    def mapping_relation(self, model):
        if self.identity_model(model):
            return sql.SQL('SELECT id source_id,id target_id FROM {}').format(
                self.identity_source(model))
        return sql.SQL('SELECT source_id,target_id FROM accounting_migration.record_map WHERE model={}').format(sql.Literal(model))

    def mapped_expression(self, model_expr, value):
        def explicit():
            return sql.SQL('(SELECT m.target_id FROM accounting_migration.record_map m WHERE m.model={} AND m.source_id={})').format(model_expr, value)
        def identity(model):
            return sql.SQL('(SELECT m.id FROM {} m WHERE m.id={})').format(
                self.identity_source(model), value)
        if isinstance(model_expr, sql.Literal):
            return identity(model_expr.wrapped) if self.identity_model(model_expr.wrapped) else explicit()
        branches = [sql.SQL('WHEN {}={} THEN {}').format(model_expr, sql.Literal(model), identity(model))
                    for model in sorted(getattr(self, 'mapping_modes', {})) if self.identity_model(model)]
        if not branches:
            return explicit()
        return sql.SQL('(CASE {} ELSE {} END)').format(sql.SQL(' ').join(branches), explicit())

    def mapping_exists(self, model_expr, value):
        def explicit():
            return sql.SQL('EXISTS(SELECT 1 FROM accounting_migration.record_map m WHERE m.model={} AND m.source_id={})').format(model_expr, value)
        def identity(model):
            return sql.SQL('EXISTS(SELECT 1 FROM {} m WHERE m.id={})').format(
                self.identity_source(model), value)
        if isinstance(model_expr, sql.Literal):
            return identity(model_expr.wrapped) if self.identity_model(model_expr.wrapped) else explicit()
        branches = [sql.SQL('WHEN {}={} THEN {}').format(model_expr, sql.Literal(model), identity(model))
                    for model in sorted(getattr(self, 'mapping_modes', {})) if self.identity_model(model)]
        if not branches:
            return explicit()
        return sql.SQL('(CASE {} ELSE {} END)').format(sql.SQL(' ').join(branches), explicit())

    def create_model_plan(self):
        self.mapping_format = MIXED_MAPPING_VERSION
        self.mapping_modes = {model: 'explicit' for model in self.models}
        self.execute('CREATE TABLE accounting_migration.model_plan ('
                     'model text PRIMARY KEY,strategy text NOT NULL CHECK(strategy IN (\'identity\',\'explicit\')),'
                     'source_table text NOT NULL,target_table text,source_rows bigint NOT NULL,'
                     'format integer NOT NULL,status text NOT NULL)')

    def plan_records(self):
        return [dict(model=model, strategy=self.mapping_modes[model], source_table=meta['table'],
                     target_table=self.schema.get(model, {}).get('table'),
                     source_rows=self.manifest['tables'][meta['table']]['rows'], format=MIXED_MAPPING_VERSION)
                for model, meta in sorted(self.models.items())]

    def persist_model_plan(self):
        for record in self.plan_records():
            self.execute('INSERT INTO accounting_migration.model_plan '
                         '(model,strategy,source_table,target_table,source_rows,format,status) VALUES (%s,%s,%s,%s,%s,%s,\'mapped\')',
                         [record[k] for k in ('model','strategy','source_table','target_table','source_rows','format')])

    def restore_model_plan(self, saved):
        if self.mapping_format == 1:
            self.mapping_modes = {}
            return
        self.execute('SELECT model,strategy,source_table,target_table,source_rows,format FROM accounting_migration.model_plan ORDER BY model')
        records = [dict(zip(('model','strategy','source_table','target_table','source_rows','format'), row)) for row in self.cr.fetchall()]
        # PostgreSQL locale collation is not Python's Unicode ordering.
        records.sort(key=lambda r: r['model'])
        if records != saved.get('plans'):
            raise MigrationError('Mapping model plan differs from its committed checkpoint')
        self.mapping_modes = {r['model']: r['strategy'] for r in records}
        if set(self.mapping_modes) != set(self.models) or any(
                mode not in ('identity', 'explicit') or (mode == 'identity' and model in LOOKUPS) or (mode == 'explicit' and model not in LOOKUPS)
                for model, mode in self.mapping_modes.items()):
            raise MigrationError('Invalid mapping strategies in checkpoint')
        if records != self.plan_records():
            raise MigrationError('Mapping model plan metadata differs from the extraction/schema')

    def select_mapping_format(self, checkpoint):
        version = checkpoint.get('format', 1) if checkpoint is not None else MIXED_MAPPING_VERSION
        if version != MIXED_MAPPING_VERSION:
            raise MigrationError(f'Unsupported mapping checkpoint format: {version}')
        self.mapping_format = version

