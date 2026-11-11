"""Strict source-ID policy and bounded, transactional target-seed relocation."""
import uuid
import json
from psycopg2 import sql
from common import LOOKUPS, MigrationError, save_json
from resume import fingerprint, get_checkpoint
from progress import current
from action_seeds import action_references
from seed_metadata import DESCRIPTIVE_FIELDS, MARKUP_FIELDS, inspect_metadata

STRICT_FORMAT = 3
STRICT_POLICY = 'preserve_business_ids_v1'
SEED_ADAPTER_VERSION = 4
STABLE_KEYS = {'res.country': 'code', 'res.currency': 'name', 'res.lang': 'code', 'res.users': 'login'}
CONFIG_LINKS = {
    'auth_signup.template_user_id': 'res.users',
    'base.template_portal_user_id': 'res.users',
}
# Reviewed against Odoo 19 base/mail consumers: sizes, counts, durations and
# a Boolean flag, never record IDs. Keep unknown numeric settings fail-closed.
CONFIG_SCALARS = frozenset({
    'base.default_max_email_size',
    'base.login_cooldown_after',
    'base.login_cooldown_duration',
    'mail.activity.gc.delete_overdue_years',
    'mail.restrict.template.rendering',
})


def require_strict(checkpoint, required=False):
    if required and not checkpoint:
        raise MigrationError('Strict-ID business checkpoint is missing')
    if checkpoint and checkpoint.get('id_policy') != STRICT_POLICY:
        raise MigrationError('Business/runtime data committed under the old ID policy. Automatic resume is refused; use a new target or a separately reviewed recovery.')


def relocation_plan(model, target_ids, source_max, overlapping_ids, matches):
    """Only seed-sized inputs; never enumerate all source IDs in Python."""
    by_source, by_target = {}, {}
    for source_id, target_id in matches:
        if source_id in by_source and by_source[source_id] != target_id:
            raise MigrationError(f'Contradictory seed identities: {model}')
        if target_id in by_target and by_target[target_id] != source_id:
            raise MigrationError(f'Ambiguous seed identity: {model}')
        by_source[source_id], by_target[target_id] = target_id, source_id
    if not set(by_target).issubset(target_ids):
        raise MigrationError(f'Matched target seed is missing: {model}')
    if model == 'res.users' and (1 not in target_ids or by_target.get(1) != 1):
        raise MigrationError('Protected superuser must match source user ID 1')
    high = max([source_max, 0, *target_ids])
    destinations = {}
    for old in sorted(target_ids):
        if old in by_target:
            destinations[old] = by_target[old]
        elif old in overlapping_ids:
            high += 1
            destinations[old] = high
        else:
            destinations[old] = old
    if len(set(destinations.values())) != len(destinations):
        raise MigrationError(f'Non-unique seed relocation: {model}')
    changed = [(old, new) for old, new in destinations.items() if old != new]
    # Temporary IDs cannot overlap source, original target, or final seed IDs.
    temporary = max([high, *destinations.values()])
    if temporary + len(changed) > 2147483647:
        raise MigrationError(f'Insufficient safe integer ID space for target seeds: {model}')
    return [dict(model=model, old_id=old, temp_id=temporary+i+1, new_id=new,
                 reason='matched source identity' if old in by_target else 'unrelated target seed collision')
            for i, (old, new) in enumerate(changed)]


class StrictSeeds:
    def archive_old_mapping(self, saved):
        if not saved or saved.get('format', 1) == STRICT_FORMAT:
            return
        if saved.get('format', 1) not in (1, 2):
            raise MigrationError('Unsupported old mapping format')
        require_strict(get_checkpoint(self.cr, 'business'))
        require_strict(get_checkpoint(self.cr, 'runtime'))
        archive = 'accounting_migration_archive_' + uuid.uuid4().hex[:12]
        self.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(archive)))
        for table in ('record_map', 'model_plan', 'xml_data'):
            self.execute('SELECT to_regclass(%s)', ['accounting_migration.' + table])
            if self.cr.fetchone()[0]:
                self.execute(sql.SQL('ALTER TABLE {} SET SCHEMA {}').format(
                    sql.Identifier('accounting_migration', table), sql.Identifier(archive)))
        self.execute(sql.SQL("CREATE TABLE {} AS SELECT * FROM accounting_migration.checkpoint WHERE name='mapping'").format(
            sql.Identifier(archive, 'checkpoint')))
        self.execute("DELETE FROM accounting_migration.checkpoint WHERE name='mapping'")
        self.execute('CREATE TABLE accounting_migration.record_map (model text,source_id bigint,target_model text NOT NULL,'
                     'target_id bigint NOT NULL,phase text NOT NULL,PRIMARY KEY(model,source_id),UNIQUE(target_model,target_id))')
        self.cr.commit()
        current().log('Archived old mapping metadata in ' + archive + '; committed COPY tables retained')

    def start_seed_plan(self):
        self.seed_moves, self.seed_fingerprints, self.seed_surplus = [], {}, {}
        self.execute('CREATE TABLE accounting_migration.seed_move (model text,old_id bigint,temp_id bigint,new_id bigint,'
                     'reason text,PRIMARY KEY(model,old_id),UNIQUE(model,temp_id),UNIQUE(model,new_id))')

    def target_seed_fingerprint(self, model):
        self.execute(sql.SQL("SELECT md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' ORDER BY id),'')) FROM {} t").format(self.dst(model)))
        return self.cr.fetchone()[0]

    def plan_identity(self, model, candidates):
        current().operation('plan preserved IDs and initialized target records')
        for schema, table in [('accounting_migration_source', self.models[model]['table']), ('public', self.schema[model]['table'])]:
            self.execute("SELECT EXISTS(SELECT 1 FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey) "
                         "WHERE i.indrelid=to_regclass(%s) AND i.indisprimary AND i.indisvalid AND i.indnkeyatts=1 AND a.attname='id')", [schema+'.'+table])
            if not self.cr.fetchone()[0]:
                raise MigrationError(f'Strict IDs require an id primary key: {model}')
        self.seed_fingerprints[model] = self.target_seed_fingerprint(model)
        self.execute(sql.SQL('SELECT id FROM {} ORDER BY id').format(self.dst(model)))
        target_ids = {r[0] for r in self.cr.fetchall()}
        self.execute(candidates, [model, model])
        matches = list(self.cr.fetchall())
        key = STABLE_KEYS.get(model)
        if key:
            self.execute(sql.SQL('SELECT s.id,t.id FROM {} s JOIN {} t ON s.{}=t.{} WHERE s.{} IS NOT NULL').format(
                self.src(model), self.dst(model), sql.Identifier(key), sql.Identifier(key), sql.Identifier(key)))
            matches.extend(self.cr.fetchall())
        self.execute(sql.SQL('SELECT t.id FROM {} t JOIN {} s ON s.id=t.id').format(self.dst(model), self.src(model)))
        overlaps = {r[0] for r in self.cr.fetchall()}
        source_max = self.count(sql.SQL('SELECT coalesce(max(id),0) FROM {}').format(self.src(model)))
        moves = relocation_plan(model, target_ids, source_max, overlaps, matches)
        for move in moves:
            self.execute('INSERT INTO accounting_migration.seed_move(model,old_id,temp_id,new_id,reason) VALUES (%s,%s,%s,%s,%s)',
                         [move[k] for k in ('model','old_id','temp_id','new_id','reason')])
        self.seed_moves.extend(moves)
        self.seed_surplus[model] = len(target_ids) - len({target for source, target in matches})
        self.mapping_modes[model] = 'identity'
        current().update(strategy='identity', represented_rows=self.manifest['tables'][self.models[model]['table']]['rows'], mapping_rows_written=0)
        current().finish(f'IDs preserved; {len(moves)} target seed relocations planned; pending commit')

    def seed_plan_identity(self):
        return fingerprint(dict(moves=self.seed_moves, fingerprints=self.seed_fingerprints, surplus=self.seed_surplus, references=self.seed_references))

    def check_seed_state(self, saved):
        for model, expected in saved['seed_fingerprints'].items():
            if self.target_seed_fingerprint(model) != expected:
                raise MigrationError(f'Initialized target changed after strict-ID planning: {model}')
        self.seed_moves = saved['seed_moves']
        self.execute('SELECT model,old_id,temp_id,new_id,reason FROM accounting_migration.seed_move ORDER BY model,old_id')
        actual = [dict(zip(('model','old_id','temp_id','new_id','reason'), r)) for r in self.cr.fetchall()]
        actual.sort(key=lambda r: (r['model'], r['old_id']))
        if actual != sorted(self.seed_moves, key=lambda r: (r['model'], r['old_id'])):
            raise MigrationError('Seed relocation table differs from committed plan')
        self.seed_fingerprints = saved['seed_fingerprints']
        self.seed_surplus = saved['seed_surplus']
        expected_refs = saved['seed_references']
        self.discover_seed_references()
        if self.seed_plan_identity() != saved.get('seed_plan_identity'):
            raise MigrationError('Seed plan fingerprint mismatch')
        if fingerprint(self.seed_references) != fingerprint(expected_refs):
            raise MigrationError('Seed reference metadata changed after planning')

    def discover_seed_references(self):
        """Whitelist typed reference shapes; reject potentially affected unknown IDs."""
        moved = {r['model'] for r in self.seed_moves}
        table_models = {self.schema[m]['table']: m for m in moved}
        refs, covered, blockers = set(), set(), []
        def add(kind, table, column, model='', extra=''):
            if table not in self.physical or column not in self.physical[table]:
                return
            refs.add((kind, table, column, model, extra))
            covered.add((table, column))
        self.execute("SELECT s.relname,a.attname,t.relname,b.attname,k.confupdtype,array_length(k.conkey,1),k.conname "
                     "FROM pg_constraint k JOIN pg_class s ON s.oid=k.conrelid JOIN pg_namespace n ON n.oid=s.relnamespace "
                     "JOIN pg_class t ON t.oid=k.confrelid JOIN pg_attribute a ON a.attrelid=s.oid AND a.attnum=k.conkey[1] "
                     "JOIN pg_attribute b ON b.attrelid=t.oid AND b.attnum=k.confkey[1] WHERE k.contype='f' AND n.nspname='public' AND t.relnamespace='public'::regnamespace")
        for table, column, target, key, action, length, name in self.cr.fetchall():
            # A typed FK to an unmoved model is known, not an unknown integer link.
            covered.add((table, column))
            if target not in table_models:
                continue
            if action not in ('a', 'c') or length != 1 or key != 'id':
                blockers.append(dict(table=table, field=column, reason='Unsupported FK update action/composite key', constraint=name))
            else:
                add('scalar', table, column, table_models[target])
        for model, meta in self.schema.items():
            table = meta['table']
            for field, f in meta['fields'].items():
                related = f.get('relation')
                if f.get('type') == 'many2one' and f.get('store'):
                    covered.add((table, field))
                if f.get('company_dependent'):
                    covered.add((table, field))
                    if 'res.company' in moved or related in moved:
                        add('company_json', table, field, related if related in moved else '')
                elif f.get('type') == 'many2one' and related in moved and f.get('store'):
                    add('scalar', table, field, related)
                elif f.get('type') == 'many2many':
                    covered.add((f.get('relation_table'), f.get('column1')))
                    covered.add((f.get('relation_table'), f.get('column2')))
                    if model in moved:
                        add('scalar', f.get('relation_table'), f.get('column1'), model)
                    if related in moved:
                        add('scalar', f.get('relation_table'), f.get('column2'), related)
                elif f.get('type') == 'reference' and f.get('store'):
                    add('reference', table, field)
                elif f.get('type') == 'many2one_reference' and f.get('store'):
                    discriminator = f.get('model_field')
                    if discriminator in self.physical.get(table, {}):
                        add('polymorphic', table, field, '', discriminator)
            for field, related in self.rules.get('integer_links', {}).get(model, {}).items():
                covered.add((table, field))
                if related in moved: add('scalar', table, field, related)
            for field, discriminator in self.rules.get('polymorphic', {}).get(model, {}).items():
                add('polymorphic', table, field, '', discriminator)
            if 'parent_path' in self.physical.get(table, {}) and model in moved:
                add('parent_path', table, 'parent_path', model)
        for table, columns in self.physical.items():
            if 'res_id' in columns:
                if 'res_model' in columns: add('polymorphic', table, 'res_id', '', 'res_model')
                elif 'res_model_id' in columns: add('model_reference', table, 'res_id', '', 'res_model_id')
        add('polymorphic', 'ir_model_data', 'res_id', '', 'model')
        # JSON defaults are typed by ir.model.fields, rather than guessed by value.
        add('defaults', 'ir_default', 'json_value')
        add('config', 'ir_config_parameter', 'value')
        if moved:
            for table, columns in self.physical.items():
                for column, meta in columns.items():
                    if column == 'id' or (table, column) in covered or not column.endswith('_id') or meta['type'] not in ('integer', 'bigint'):
                        continue
                    self.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} t JOIN accounting_migration.seed_move m ON t.{}=m.old_id)').format(
                        sql.Identifier(table), sql.Identifier(column)))
                    if self.cr.fetchone()[0]:
                        blockers.append(dict(table=table, field=column, reason='Unclassified populated integer reference; needs a reviewed adapter'))
        if moved:
            if 'ir_default' in self.physical:
                self.fail_if("SELECT count(*) FROM ir_default d JOIN ir_model_fields f ON f.id=d.field_id WHERE f.ttype IN ('many2many','one2many') AND f.relation IN (SELECT model FROM accounting_migration.seed_move) AND d.json_value NOT IN ('false','null','[]')", None, 'Relational default commands need a reviewed seed adapter')
            if 'ir_config_parameter' in self.physical:
                self.check_config_seed_references('old_id')
            for kind, table, column, model, extra in refs:
                if kind == 'company_json':
                    self.fail_if(sql.SQL("SELECT count(*) FROM {} WHERE {} IS NOT NULL AND jsonb_typeof({})<>'object'").format(
                        sql.Identifier(table), sql.Identifier(column), sql.Identifier(column)), None, f'Unsupported company JSON shape: {table}.{column}')
        if moved:
            action_plans = []
            if {'id', 'res_model', 'context', 'domain'}.issubset(self.physical.get('ir_act_window', {})):
                self.execute('SELECT id,res_model,domain,context FROM ir_act_window ORDER BY id')
                actions = self.cr.fetchall()
                for record_id, action_model, domain, context in actions:
                    for column, value in [('domain', domain), ('context', context)]:
                        temporary, findings = action_references(value, column, action_model, self.schema, self.seed_moves)
                        if findings:
                            self.execute("SELECT module||'.'||name FROM ir_model_data WHERE model='ir.actions.act_window' AND res_id=%s ORDER BY module,name", [record_id])
                            blockers.append(dict(table='ir_act_window', field=column, record_id=record_id,
                                                 xmlids=[r[0] for r in self.cr.fetchall()], findings=findings,
                                                 reason='Action reference needs reviewed adapter'))
                        elif temporary != value:
                            final, errors = action_references(temporary, column, action_model, self.schema, self.seed_moves, 'temp_id', 'new_id')
                            if errors:
                                raise MigrationError('Action default temporary relocation could not be validated')
                            action_plans.append(dict(id=record_id, model=action_model, original=value, temporary=temporary, final=final))
                covered.update({('ir_act_window', 'context'), ('ir_act_window', 'domain')})
                if action_plans:
                    refs.add(('action_context', 'ir_act_window', 'context', '', json.dumps(action_plans, sort_keys=True)))
            markers = sorted(moved | {field for meta in self.schema.values() for field, f in meta['fields'].items() if f.get('relation') in moved})
            old_ids = {r['old_id'] for r in self.seed_moves}
            table_models_all = {meta['table']: model for model, meta in self.schema.items()}
            for table, columns in self.physical.items():
                for column, meta in columns.items():
                    if (table, column) in covered or (table, column) in DESCRIPTIVE_FIELDS:
                        continue
                    if meta['type'] not in ('jsonb', 'json', 'text', 'character varying'):
                        continue
                    if column not in ('domain', 'domain_force', 'context') and (table, column) not in MARKUP_FIELDS and meta['type'] not in ('jsonb', 'json'):
                        continue
                    # Markup is inspected without the old model-name prefilter:
                    # links and domains may carry an ID with an implicit model.
                    self.execute(sql.SQL('SELECT {},{} FROM {} WHERE {} IS NOT NULL').format(
                        sql.Identifier('id') if 'id' in columns else sql.SQL('NULL'),
                        sql.Identifier(column), sql.Identifier(table), sql.Identifier(column)))
                    rows = self.cr.fetchall()
                    for record_id, value in rows:
                        findings = inspect_metadata(value, table, column, markers, old_ids)
                        if not findings:
                            continue
                        self.execute("SELECT module||'.'||name FROM ir_model_data WHERE model=%s AND res_id=%s ORDER BY module,name",
                                     [table_models_all.get(table, table.replace('_', '.')), record_id])
                        xmlids = [r[0] for r in self.cr.fetchall()]
                        blockers.append(dict(table=table, field=column, record_id=record_id, xmlids=xmlids,
                                             reason='Potential embedded seed reference; needs reviewed adapter', findings=findings))
        self.seed_references = sorted(refs)
        save_json(self.stage / 'seed-reference-blockers.json', blockers)
        if blockers:
            raise MigrationError(f'{len(blockers)} unsupported seed reference patterns; see seed-reference-blockers.json')

    def check_config_seed_references(self, id_column):
        self.execute(sql.SQL(
            'SELECT DISTINCT t.key FROM ir_config_parameter t '
            'JOIN accounting_migration.seed_move m ON t.value=m.{}::text '
            'WHERE NOT (t.key=ANY(%s)) ORDER BY t.key'
        ).format(sql.Identifier(id_column)), [sorted(set(CONFIG_LINKS) | CONFIG_SCALARS)])
        keys = [row[0] for row in self.cr.fetchall()]
        if keys:
            # Keys only: configuration values may contain sensitive information.
            raise MigrationError('Numeric configuration reference needs a reviewed seed adapter: ' + ', '.join(keys))

    def relocate_seeds(self):
        if not self.seed_moves:
            return
        current().begin('seed relocation', operation='move initialized records through temporary IDs')
        self.env.flush_all()
        for before, after in [('old_id', 'temp_id'), ('temp_id', 'new_id')]:
            for model in sorted({r['model'] for r in self.seed_moves}):
                self.execute(sql.SQL('UPDATE {} t SET id=m.{} FROM accounting_migration.seed_move m WHERE m.model=%s AND t.id=m.{}').format(
                    self.dst(model), sql.Identifier(after), sql.Identifier(before)), [model])
            for reference in self.seed_references:
                self.rewrite_seed_reference(reference, before, after)
        self.env.invalidate_all()
        self.env.registry.clear_cache()
        current().finish('seed relocation applied; pending business commit')

    def rewrite_seed_reference(self, descriptor, before, after):
        kind, table, column, model, extra = descriptor
        t, c, old, new = sql.Identifier(table), sql.Identifier(column), sql.Identifier(before), sql.Identifier(after)
        if kind == 'action_context':
            keys = {'old_id': 'original', 'temp_id': 'temporary', 'new_id': 'final'}
            for plan in json.loads(extra):
                self.execute('UPDATE ir_act_window SET context=%s WHERE id=%s AND res_model=%s AND context=%s',
                             [plan[keys[after]], plan['id'], plan['model'], plan[keys[before]]])
                if self.cr.rowcount != 1:
                    raise MigrationError(f"Action context changed after seed planning: ir_act_window {plan['id']}")
        elif kind == 'scalar':
            self.execute(sql.SQL('UPDATE {} t SET {}=m.{} FROM accounting_migration.seed_move m WHERE m.model=%s AND t.{}=m.{}').format(t,c,new,c,old), [model])
        elif kind in ('polymorphic', 'model_reference'):
            discriminator = sql.SQL('t.{}').format(sql.Identifier(extra)) if kind == 'polymorphic' else sql.SQL('(SELECT model FROM ir_model WHERE id=t.{})').format(sql.Identifier(extra))
            self.execute(sql.SQL('UPDATE {} t SET {}=m.{} FROM accounting_migration.seed_move m WHERE {}=m.model AND t.{}=m.{}').format(t,c,new,discriminator,c,old))
        elif kind == 'reference':
            self.execute(sql.SQL("UPDATE {} t SET {}=m.model||','||m.{}::text FROM accounting_migration.seed_move m WHERE t.{}=m.model||','||m.{}::text").format(t,c,new,c,old))
        elif kind == 'parent_path':
            self.execute(sql.SQL("UPDATE {} t SET {}=(SELECT string_agg(coalesce(m.{}::text,p.id),'/' ORDER BY p.n) FROM regexp_split_to_table(t.{},'/') WITH ORDINALITY p(id,n) LEFT JOIN accounting_migration.seed_move m ON m.model=%s AND m.{}::text=p.id) WHERE t.{} IS NOT NULL").format(t,c,new,c,old,c), [model])
        elif kind == 'company_json':
            self.execute(sql.SQL("UPDATE {} t SET {}=(SELECT jsonb_object_agg(coalesce(k.{}::text,e.key),CASE WHEN v.{} IS NOT NULL THEN to_jsonb(v.{}) ELSE e.value END) FROM jsonb_each(t.{}) e LEFT JOIN accounting_migration.seed_move k ON k.model='res.company' AND k.{}::text=e.key LEFT JOIN accounting_migration.seed_move v ON v.model=%s AND to_jsonb(v.{})=e.value) WHERE t.{} IS NOT NULL").format(t,c,new,new,new,c,old,old,c), [model])
        elif kind == 'defaults':
            self.execute(sql.SQL("UPDATE ir_default d SET json_value=to_jsonb(m.{})::text FROM ir_model_fields f,accounting_migration.seed_move m WHERE d.field_id=f.id AND f.ttype='many2one' AND f.relation=m.model AND d.json_value::jsonb=to_jsonb(m.{})").format(new,old))
            self.execute(sql.SQL("UPDATE ir_default d SET json_value=to_jsonb(m.model||','||m.{}::text)::text FROM ir_model_fields f,accounting_migration.seed_move m WHERE d.field_id=f.id AND f.ttype='reference' AND d.json_value::jsonb=to_jsonb(m.model||','||m.{}::text)").format(new,old))
            self.fail_if("SELECT count(*) FROM ir_default d JOIN ir_model_fields f ON f.id=d.field_id WHERE f.ttype IN ('many2many','one2many') AND f.relation IN (SELECT model FROM accounting_migration.seed_move) AND d.json_value NOT IN ('false','null','[]')", None, 'Relational default commands need a reviewed seed adapter')
        elif kind == 'config':
            for key, related in CONFIG_LINKS.items():
                self.execute(sql.SQL('UPDATE ir_config_parameter t SET value=m.{}::text FROM accounting_migration.seed_move m WHERE t.key=%s AND m.model=%s AND t.value=m.{}::text').format(new,old), [key,related])
            self.check_config_seed_references(before)
        else:
            raise MigrationError('Unsupported seed reference adapter')

    def restore_business_xmlids(self):
        current().begin('XML IDs', operation='restore scoped business XML IDs')
        self.execute('CREATE TABLE accounting_migration_work.business_xmlids (module text,name text,model text,res_id bigint,source_noupdate boolean)')
        for model in sorted(self.models):
            if model in LOOKUPS:
                continue
            aliases = [model] + [old for old, new in self.rules.get('source_aliases', {}).items() if new == model]
            # Original aliases and reviewed canonical aliases are both retained.
            for source in (sql.Identifier('accounting_migration_source', 'ir_model_data'), sql.Identifier('accounting_migration', 'xml_data')):
                self.execute(sql.SQL('INSERT INTO accounting_migration_work.business_xmlids '
                    'SELECT DISTINCT x.module,x.name,%s,s.id,x.noupdate FROM {} x JOIN {} s ON s.id=x.res_id '
                    'WHERE x.model=ANY(%s)').format(source, self.src(model)), [model, aliases])
        self.fail_if("SELECT count(*) FROM accounting_migration_work.business_xmlids WHERE module IS NULL OR name IS NULL OR module='' OR name=''", None, 'Invalid source business XML ID')
        self.fail_if("SELECT count(*) FROM (SELECT module,name FROM accounting_migration_work.business_xmlids GROUP BY module,name HAVING count(DISTINCT (model,res_id))>1) q", None, 'Conflicting business XML-ID aliases')
        self.fail_if("SELECT count(*) FROM accounting_migration_work.business_xmlids s JOIN ir_model_data t USING(module,name) WHERE t.model<>s.model OR t.res_id<>s.res_id", None, 'Business XML ID conflicts with installed target identity')
        self.execute("INSERT INTO ir_model_data(module,name,model,res_id,noupdate) SELECT DISTINCT s.module,s.name,s.model,s.res_id,true "
                     "FROM accounting_migration_work.business_xmlids s WHERE NOT EXISTS (SELECT 1 FROM ir_model_data t WHERE t.module=s.module AND t.name=s.name)")
        self.report['restored_business_xmlids'] = self.cr.rowcount
        self.report['xmlid_policy'] = 'Existing target noupdate flags retained; newly restored source-only business aliases use noupdate=true; original flags retained in work table/export.'
        self.fail_if("SELECT count(*) FROM accounting_migration_work.business_xmlids s LEFT JOIN ir_model_data t USING(module,name) WHERE t.id IS NULL OR t.model<>s.model OR t.res_id<>s.res_id", None, 'Business XML-ID restoration verification failed')
        self.env.invalidate_all()
        self.env.registry.clear_cache()
        current().finish('business XML IDs restored; pending commit')
