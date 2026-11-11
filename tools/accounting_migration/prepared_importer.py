"""Set-based prepared-target replacement. Only the controller commits transactions."""
import hashlib
import os
from pathlib import Path
import shutil
import uuid
from psycopg2 import sql
from bulk import catalog
from common import MigrationError, digest, save_json, safe_attachment_path
from importer import FRAMEWORK_FIELDS
from prepared_snapshot import SCHEMA
import prepared_progress as progress

META = 'prepared_custom_migration'
WORK = 'prepared_migration_work'
MIN_MATCHED_ID = 7


def missing_identity_query(source, target):
    return sql.SQL('SELECT s.id FROM {} s LEFT JOIN {} t USING(id) '
                   'WHERE t.id IS NULL AND s.id >= {} ORDER BY s.id').format(
                       source,target,sql.Literal(MIN_MATCHED_ID))


def ident(*parts):
    return sql.Identifier(*parts)


class HashWriter:
    def __init__(self):
        self.hash = hashlib.sha256()
        self.bytes=0
    def write(self, value):
        if isinstance(value, str):
            value = value.encode()
        self.hash.update(value)
        self.bytes+=len(value)
        progress.update(bytes=self.bytes)
        return len(value)


class PreparedImporter:
    def __init__(self, connection, stage, manifest, target, rules, conversions):
        self.con, self.stage, self.manifest = connection, Path(stage), manifest
        self.cr = connection.cursor()
        self.target, self.rules, self.conversions = target, rules, conversions
        self.selected = set(manifest['selected'])
        self.custom_models = set(self.selected)
        self.models = manifest['models']
        self.physical = catalog(connection)
        self.report = dict(omitted_models=manifest['omitted'], ignored_fields=[], skipped_fields=[],missing_files=[],
                           activities='skipped', activity_count=manifest['activities'])
        self.plans = {}

    def skip_field(self, model, name, target_name=None, reason='No stored target field/column'):
        entry=dict(model=model,field=name,target_field=target_name or name,reason=reason)
        if entry not in self.report['skipped_fields']:
            self.report['skipped_fields'].append(entry)

    def stored_destination(self, model, name):
        f=self.target[model]['fields'].get(name,{})
        return bool(f) and f.get('store') is not False and name in self.physical[self.target[model]['table']]

    def execute(self, query, params=None):
        self.cr.execute(query, params)

    def scalar(self, query, params=None):
        self.execute(query, params)
        return self.cr.fetchone()[0]

    def fail(self, query, message, params=None):
        if self.scalar(query, params):
            raise MigrationError(message)

    def src(self, model):
        return ident(SCHEMA, self.models[model]['table'])

    def dst(self, model):
        return ident('public', self.target[model]['table'])

    def normalize_model(self, value):
        for old, new in self.conversions.get('source_aliases', {}).items():
            value = sql.SQL('CASE WHEN {}={} THEN {} ELSE {} END').format(
                value, sql.Literal(old), sql.Literal(new), value)
        return value

    def mapped(self, model, value):
        if isinstance(model, str):
            if model in self.custom_models:
                return sql.SQL('(SELECT id FROM {} WHERE id={})').format(self.src(model), value)
            return sql.SQL('(SELECT target_id FROM {} WHERE model={} AND source_id={})').format(
                ident(META,'record_map'),sql.Literal(model),value)
        # Dynamic model fields can refer to either selected or standard models.
        cases = [sql.SQL('WHEN {}={} THEN (SELECT id FROM {} WHERE id={})').format(
            model, sql.Literal(m), self.src(m), value) for m in sorted(self.custom_models)]
        return sql.SQL('(CASE {} ELSE (SELECT target_id FROM {} WHERE model={} AND source_id={}) END)').format(
            sql.SQL(' ').join(cases), ident(META, 'record_map'), model, value)

    def validate_ids(self):
        report = {}
        for table in ('res_users', 'res_partner'):
            query = missing_identity_query(ident(SCHEMA, table), ident('public', table))
            self.execute(query)
            missing = [r[0] for r in self.cr]
            self.execute(sql.SQL('SELECT count(*),count(*) FILTER(WHERE id >= {}) FROM {}').format(
                sql.Literal(MIN_MATCHED_ID),ident(SCHEMA,table)))
            total,checked=self.cr.fetchone()
            report[table] = dict(source_count=total,checked_count=checked,skipped_count=total-checked,
                                 missing_count=len(missing),missing_ids=missing)
        save_json(self.stage / 'id-validation.json', report)
        if any(r['missing_count'] for r in report.values()):
            raise MigrationError('Source user/partner IDs >= 7 missing in target; see id-validation.json. IDs below 7 are skipped; extra target IDs are allowed.')
        return report

    def build_maps(self):
        self.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (model text,source_id bigint,target_id bigint,'
                             'PRIMARY KEY(model,source_id))').format(ident(META, 'record_map')))
        self.execute(sql.SQL('DELETE FROM {}').format(ident(META, 'record_map')))
        self.execute(sql.SQL('CREATE TEMP TABLE mapping_candidates(model text,source_id bigint,target_id bigint) ON COMMIT DROP'))
        self.execute(sql.SQL('INSERT INTO mapping_candidates SELECT s.model,s.res_id,t.res_id FROM {} s '
            'JOIN public.ir_model_data t USING(module,name) WHERE s.model=t.model AND NOT(s.model=ANY(%s)) '
            "AND s.model<>'ir.attachment' AND s.module<>'__export__'").format(ident(SCHEMA, 'ir_model_data')), [sorted(self.selected)])
        for old, new in self.conversions.get('xmlids', {}).items():
            sm, sn = old.split('.', 1)
            tm, tn = new.split('.', 1)
            self.execute(sql.SQL('INSERT INTO mapping_candidates SELECT s.model,s.res_id,t.res_id FROM {} s '
                'CROSS JOIN public.ir_model_data t WHERE s.module=%s AND s.name=%s AND t.module=%s AND t.name=%s '
                'AND s.model=t.model').format(ident(SCHEMA, 'ir_model_data')), [sm, sn, tm, tn])
        self.execute(sql.SQL("INSERT INTO mapping_candidates SELECT 'ir.model',s.id,t.id FROM {} s "
            'JOIN public.ir_model t ON t.model={}').format(ident(SCHEMA, 'ir_model'), self.normalize_model(sql.SQL('s.model'))))
        field_name=sql.SQL("CASE WHEN s.model='res.users' AND s.name='groups_id' THEN 'group_ids' ELSE s.name END")
        for source_model,fields in self.conversions.get('fields',{}).items():
            for old,new in fields.items():
                field_name=sql.SQL('CASE WHEN s.model={} AND s.name={} THEN {} ELSE {} END').format(
                    sql.Literal(source_model),sql.Literal(old),sql.Literal(new),field_name)
        self.execute(sql.SQL("INSERT INTO mapping_candidates SELECT 'ir.model.fields',s.id,t.id FROM {} s "
            'JOIN public.ir_model_fields t ON t.model={} AND t.name={}').format(
                ident(SCHEMA, 'ir_model_fields'), self.normalize_model(sql.SQL('s.model')),field_name))
        for model, key in self.rules.get('stable_keys', {}).items():
            if model == 'res.groups':
                raise MigrationError('Security groups cannot use stable-key guessing')
            if model in self.selected or model not in self.models or model not in self.target:
                continue
            table = self.models[model]['table']
            if table not in self.manifest['tables'] or key not in self.physical.get(self.target[model]['table'], {}):
                continue
            for relation in (self.src(model), self.dst(model)):
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} WHERE {} IS NOT NULL GROUP BY {} HAVING count(*)>1)').format(
                    relation, ident(key), ident(key)), f'Ambiguous stable key: {model}.{key}')
            self.execute(sql.SQL('INSERT INTO mapping_candidates SELECT %s,s.id,t.id FROM {} s JOIN {} t ON s.{}=t.{} '
                                 'WHERE s.{} IS NOT NULL').format(self.src(model), self.dst(model), ident(key), ident(key), ident(key)), [model])
        for model, values in self.rules.get('external_ids', {}).items():
            for source_id in values:
                self.execute('DELETE FROM mapping_candidates WHERE model=%s AND source_id=%s',[model,int(source_id)])
        self.fail('SELECT EXISTS(SELECT 1 FROM mapping_candidates GROUP BY model,source_id HAVING count(DISTINCT target_id)>1)',
                  'Conflicting external identities; add reviewed external_ids override')
        self.execute(sql.SQL('INSERT INTO {} SELECT model,source_id,min(target_id) FROM mapping_candidates GROUP BY model,source_id').format(
            ident(META, 'record_map')))
        for model, values in self.rules.get('external_ids', {}).items():
            if model in self.selected or model in ('res.users', 'res.partner', 'ir.attachment'):
                raise MigrationError(f'External ID override forbidden: {model}')
            for source_id, target_id in values.items():
                self.fail(sql.SQL('SELECT NOT EXISTS(SELECT 1 FROM {} WHERE id=%s)').format(self.dst(model)),
                          f'Explicit target mapping absent: {model}', [int(target_id)])
                self.execute(sql.SQL('INSERT INTO {} VALUES (%s,%s,%s) ON CONFLICT(model,source_id) '
                    'DO UPDATE SET target_id=EXCLUDED.target_id').format(ident(META, 'record_map')),
                    [model, int(source_id), int(target_id)])
        for model, table in (('res.users', 'res_users'), ('res.partner', 'res_partner')):
            self.execute(sql.SQL('INSERT INTO {} SELECT %s,s.id,s.id FROM {} s JOIN {} t USING(id) '
                'ON CONFLICT(model,source_id) DO UPDATE SET target_id=EXCLUDED.target_id').format(
                ident(META, 'record_map'), ident(SCHEMA, table), ident('public', table)), [model])
        if self.scalar('SELECT to_regclass(%s)',[META+'.attachment_map']):
            self.execute(sql.SQL("INSERT INTO {} SELECT 'ir.attachment',source_id,target_id FROM {} "
                'ON CONFLICT(model,source_id) DO UPDATE SET target_id=EXCLUDED.target_id').format(
                    ident(META,'record_map'),ident(META,'attachment_map')))

    def check_link(self, model, field, value, mapped, relation):
        self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND {} IS NULL)').format(
            self.src(model), value, mapped), f'Unresolved relationship: {model}.{field} -> {relation}')
        if relation in self.target and relation not in self.selected:
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND NOT EXISTS '
                '(SELECT 1 FROM {} t WHERE t.id={}))').format(self.src(model),value,self.dst(relation),mapped),
                f'Mapped target record is missing: {model}.{field} -> {relation}')

    def validate_targets(self, from_clause, model, value, condition=sql.SQL('true')):
        self.execute(sql.SQL('SELECT DISTINCT {} FROM {} WHERE {} AND {} IS NOT NULL').format(
            model,from_clause,condition,value))
        for (related,) in self.cr.fetchall():
            if related in self.selected:
                continue  # Existence in the immutable custom source was checked separately.
            if related not in self.target:
                raise MigrationError(f'Unsupported populated target model: {related}')
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} WHERE {} AND {}={} AND {} IS NOT NULL '
                'AND NOT EXISTS(SELECT 1 FROM {} checked WHERE checked.id={}))').format(
                    from_clause,condition,model,sql.Literal(related),value,self.dst(related),self.mapped(related,value)),
                f'Mapped target record absent: {related}')

    def plan_model(self, model):
        progress.begin('preflight',model=model,operation='Validate shared fields and references',monitor=True)
        meta = self.models[model]
        source = self.manifest['tables'][meta['table']]['columns']
        target = self.target[model]
        physical = self.physical[target['table']]
        expressions, deferred, attachments = {'id': sql.SQL('s.id')}, {}, {}
        for name, column in source.items():
            if name == 'id':
                continue
            sf = meta.get('fields', {}).get(name, {})
            target_name = self.conversions.get('fields', {}).get(model, {}).get(name, name)
            tf = target['fields'].get(target_name, {})
            ignored = self.rules.get('ignore_fields', {}).get(model, {}).get(name)
            if ignored:
                self.report['ignored_fields'].append(dict(model=model, field=name, reason=ignored))
                continue
            if name in FRAMEWORK_FIELDS and name != 'message_main_attachment_id':
                continue
            if not self.stored_destination(model,target_name):
                self.skip_field(model,name,target_name)
                continue
            value = sql.SQL('s.{}').format(ident(name))
            selections=self.conversions.get('selections',{}).get(model,{}).get(name,{})
            if selections:
                cases=sql.SQL(' ').join(sql.SQL('WHEN {} THEN {}').format(sql.Literal(str(old)),
                    sql.Literal(None if new is None else str(new))) for old,new in selections.items())
                value=sql.SQL('(CASE {}::text {} ELSE {}::text END)::{}').format(value,cases,value,
                    sql.SQL(physical[target_name]['type']))
            if not sf and name not in ('create_uid', 'write_uid', 'create_date', 'write_date', 'parent_path'):
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} WHERE {} IS NOT NULL)').format(self.src(model), ident(name)),
                          f'Unclassified stored column: {model}.{name}')
            relation = ('res.users' if name in ('create_uid', 'write_uid') else
                        tf.get('relation') if tf.get('type') == 'many2one' else
                        sf.get('relation') if sf.get('ttype') == 'many2one' else None)
            source_relation=sf.get('relation') if sf.get('ttype')=='many2one' else None
            source_relation=self.conversions.get('source_aliases',{}).get(source_relation,source_relation)
            if source_relation and relation and source_relation!=relation:
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL)').format(self.src(model),value),
                          f'Relationship model changed; explicit adapter required: {model}.{name}')
            relation = self.conversions.get('integer_links', {}).get(model, {}).get(name, relation)
            poly = self.conversions.get('polymorphic', {}).get(model, {}).get(name)
            if tf.get('type') == 'many2one_reference':
                poly = tf.get('model_field')
            if tf.get('company_dependent'):
                # Construct Odoo 19 company-keyed JSON after company mapping.
                value = self.property_value(model, name, tf)
                deferred[target_name] = value
            elif relation:
                mapped = self.mapped(relation, value)
                if relation == 'ir.attachment':
                    self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND NOT EXISTS '
                        '(SELECT 1 FROM {} a WHERE a.id={}))').format(self.src(model),value,ident(SCHEMA,'ir_attachment'),value),
                        f'Source attachment record is missing: {model}.{name}')
                    attachments[target_name] = mapped
                else:
                    self.check_link(model, name, value, mapped, relation)
                    if relation in self.selected or relation in ('res.users', 'res.partner'):
                        value = mapped
                    else:
                        deferred[target_name] = mapped
            elif poly or sf.get('ttype') == 'reference' or tf.get('type') == 'reference':
                if poly:
                    rel = self.normalize_model(sql.SQL('s.{}').format(ident(poly)))
                    ref_id = value
                else:
                    self.fail(sql.SQL("SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND {} !~ '^[^,]+,[0-9]+$')").format(
                        self.src(model), value, value), f'Invalid reference value: {model}.{name}')
                    rel = self.normalize_model(sql.SQL("split_part({},',',1)").format(value))
                    ref_id = sql.SQL("nullif(split_part({},',',2),'')::bigint").format(value)
                mapped = self.mapped(rel, ref_id)
                self.check_link(model, name, ref_id, mapped, 'dynamic model')
                self.validate_targets(sql.SQL('{} s').format(self.src(model)),rel,ref_id)
                deferred[target_name] = (mapped if poly else sql.SQL("CASE WHEN {} IS NULL THEN NULL ELSE {}||','||{}::text END").format(
                    value, rel, mapped))
            old_type, new_type = column['type'], physical[target_name]['type']
            if not tf.get('company_dependent') and not selections and old_type != new_type:
                if new_type == 'jsonb' and tf.get('translate'):
                    value = sql.SQL("CASE WHEN {} IS NULL THEN NULL ELSE jsonb_build_object('en_US',{}) END").format(value, value)
                    if 'ir_translation' in self.manifest['tables']:
                        value = sql.SQL("CASE WHEN s.{} IS NULL THEN NULL ELSE coalesce({},'{{}}'::jsonb)||coalesce((SELECT jsonb_object_agg(tr.lang,tr.value ORDER BY tr.id) "
                            "FROM {} tr WHERE tr.type='model' AND tr.name={} AND tr.res_id=s.id AND tr.value IS NOT NULL),'{{}}'::jsonb) END").format(
                                ident(name),
                                value, ident(SCHEMA, 'ir_translation'), sql.Literal(model + ',' + name))
                elif (old_type, new_type) in {('integer','bigint'), ('bigint','integer'), ('double precision','numeric'),
                                              ('character varying','text'), ('text','character varying')}:
                    value = sql.SQL('({})::{}').format(value, sql.SQL(new_type))
                else:
                    raise MigrationError(f'Unsupported type conversion: {model}.{name}: {old_type} -> {new_type}')
            if target_name in deferred or target_name in attachments:
                if physical[target_name]['required']:
                    raise MigrationError(f'Required external field cannot be deferred: {model}.{target_name}')
                expressions[target_name] = sql.SQL('NULL::{}').format(sql.SQL(new_type))
            else:
                expressions[target_name] = value
            if tf.get('selection'):
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND NOT({}=ANY(%s)))').format(
                    self.src(model), value, value), f'Unsupported selection: {model}.{name}', [tf['selection']])
        for name, col in physical.items():
            if name in expressions:
                continue
            tf = target['fields'].get(name, {})
            source_name=next((old for old,new in self.conversions.get('fields',{}).get(model,{}).items() if new==name),name)
            if tf.get('company_dependent') and source_name in meta.get('fields',{}):
                deferred[name] = self.property_value(model, source_name, tf)
                if col['required']:
                    raise MigrationError(f'Required company field cannot be deferred: {model}.{name}')
                expressions[name] = sql.SQL('NULL::jsonb')
            elif col['required'] and not col['default']:
                default = target.get('defaults', {}).get(name)
                if default is not None and not tf.get('relation'):
                    expressions[name] = sql.Literal(default)
                else:
                    raise MigrationError(f'Required target-only field needs adapter: {model}.{name}')
        for name, value in expressions.items():
            if physical[name]['required']:
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NULL)').format(self.src(model), value),
                          f'Invalid required value: {model}.{name}')
        for discriminator in self.conversions.get('polymorphic',{}).get(model,{}).values():
            if discriminator in expressions:
                expressions[discriminator]=self.normalize_model(expressions[discriminator])
        for name,sf in meta.get('fields',{}).items():
            if sf.get('ttype')=='many2many' and name not in FRAMEWORK_FIELDS:
                dest=self.conversions.get('fields',{}).get(model,{}).get(name,name)
                tf=target['fields'].get(dest,{})
                if not tf or tf.get('store') is False or tf.get('related'):
                    self.skip_field(model,name,dest)
        progress.finish('shared fields validated')
        return dict(expressions=expressions, deferred=deferred, attachments=attachments)

    def property_value(self, model, name, field):
        if 'ir_property' not in self.manifest['tables']:
            return sql.SQL('NULL::jsonb')
        properties=ident(SCHEMA,'ir_property')
        source_fields=ident(SCHEMA,'ir_model_fields')
        if not self.scalar(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} p JOIN {} f ON f.id=p.fields_id WHERE f.model=%s AND f.name=%s)').format(
                properties,source_fields),[model,name]):
            return sql.SQL('NULL::jsonb')
        if 'res_company' not in self.manifest['tables']:
            raise MigrationError(f'Source company ID list required for property defaults: {model}.{name}')
        self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} c WHERE {} IS NULL)').format(
            ident(SCHEMA,'res_company'),self.mapped('res.company',sql.SQL('c.id'))),
            f'Unmapped source company for property defaults: {model}.{name}')
        typ = field['type']
        column = {'float':'value_float', 'monetary':'value_float', 'integer':'value_integer', 'boolean':'value_integer',
                  'char':'value_text', 'text':'value_text', 'selection':'value_text', 'date':'value_datetime',
                  'datetime':'value_datetime', 'many2one':'value_reference'}.get(typ)
        if not column:
            raise MigrationError(f'Unsupported company-dependent field: {model}.{name}')
        value = sql.SQL('p.{}').format(ident(column))
        if typ == 'many2one':
            rel = self.normalize_model(sql.SQL("split_part(p.value_reference,',',1)"))
            rid = sql.SQL("nullif(split_part(p.value_reference,',',2),'')::bigint")
            mapped = self.mapped(rel, rid)
            if field.get('relation'):
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} p JOIN {} f ON f.id=p.fields_id '
                    'WHERE f.model=%s AND f.name=%s AND p.value_reference IS NOT NULL AND {}<>%s)').format(
                        properties,source_fields,rel),f'Property relationship model changed: {model}.{name}',
                        [model,name,field['relation']])
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} p JOIN {} f ON f.id=p.fields_id '
                'WHERE f.model=%s AND f.name=%s AND p.value_reference IS NOT NULL AND {} IS NULL)').format(
                    ident(SCHEMA,'ir_property'), ident(SCHEMA,'ir_model_fields'), mapped),
                    f'Unmapped company property: {model}.{name}', [model,name])
            value = mapped
            self.validate_targets(sql.SQL('{} p JOIN {} f ON f.id=p.fields_id').format(properties,source_fields),rel,rid,
                sql.SQL('f.model={} AND f.name={}').format(sql.Literal(model),sql.Literal(name)))
        elif typ == 'boolean':
            value = sql.SQL('({}<>0)').format(value)
        elif typ in ('date','datetime'):
            value = sql.SQL('to_char({}, {})').format(value,sql.Literal(
                'YYYY-MM-DD' if typ=='date' else 'YYYY-MM-DD HH24:MI:SS'))
        # Every source company used by these properties must already map.
        self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} p JOIN {} f ON f.id=p.fields_id '
            'WHERE f.model=%s AND f.name=%s AND p.company_id IS NOT NULL AND {} IS NULL)').format(
                ident(SCHEMA,'ir_property'),ident(SCHEMA,'ir_model_fields'),self.mapped('res.company',sql.SQL('p.company_id'))),
                f'Unmapped property company: {model}.{name}', [model,name])
        self.validate_targets(sql.SQL('{} c').format(ident(SCHEMA,'res_company')),sql.Literal('res.company'),sql.SQL('c.id'))
        return sql.SQL("(SELECT jsonb_object_agg(c.target_id::text,p.value) FROM {} c CROSS JOIN LATERAL "
            '(SELECT {} value FROM {} p JOIN {} f ON f.id=p.fields_id WHERE f.model={} AND f.name={} '
            'AND (p.res_id IS NULL OR p.res_id={}||s.id::text) AND (p.company_id IS NULL OR p.company_id=c.source_id) '
            'ORDER BY (p.res_id IS NOT NULL) DESC,(p.company_id IS NOT NULL) DESC,p.id DESC LIMIT 1) p '
            "WHERE c.model='res.company')").format(ident(META,'record_map'),value,ident(SCHEMA,'ir_property'),
                ident(SCHEMA,'ir_model_fields'),sql.Literal(model),sql.Literal(name),sql.Literal(model+','))

    def relation_plans(self):
        plans = []
        for r in self.manifest['relations']:
            f = self.target[r['model']]['fields'].get(r['field'],{})
            if not f or f.get('store') is False or f.get('related'):
                self.skip_field(r['model'],r['field'])
                continue
            if f.get('type')!='many2many':
                raise MigrationError(f'Incompatible shared M2M field: {r["model"]}.{r["field"]}')
            if f.get('relation')!=r['related']:
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {})').format(ident(SCHEMA,r['table'])),
                          f'M2M relationship model changed: {r["model"]}.{r["field"]}')
            if f.get('related') or (f.get('compute') and not f.get('store')):
                continue
            table = f['relation_table']
            if table not in self.physical or len(self.physical[table]) != 2:
                raise MigrationError(f'Unsupported relation table: {table}')
            a = self.mapped(r['model'], sql.SQL('s.{}').format(ident(r['column1'])))
            b = self.mapped(r['related'], sql.SQL('s.{}').format(ident(r['column2'])))
            if r['related'] != 'ir.attachment':
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NULL OR {} IS NULL)').format(
                    ident(SCHEMA,r['table']),a,b), f'Unresolved M2M: {r["model"]}.{r["field"]}')
                self.validate_targets(sql.SQL('{} s').format(ident(SCHEMA,r['table'])),sql.Literal(r['related']),
                                      sql.SQL('s.{}').format(ident(r['column2'])))
            else:
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE NOT EXISTS(SELECT 1 FROM {} a WHERE a.id=s.{}))').format(
                    ident(SCHEMA,r['table']),ident(SCHEMA,'ir_attachment'),ident(r['column2'])),
                    f'Source attachment M2M record missing: {r["model"]}.{r["field"]}')
            plans.append(dict(source=r, table=table, columns=[f['column1'],f['column2']], values=[a,b],
                phase='attachments' if r['related']=='ir.attachment' else
                      'custom' if r['related'] in self.selected or r['related'] in ('res.users','res.partner') else 'external'))
        return plans

    def fingerprint_table(self, table):
        progress.begin('fingerprint',table=table,operation='Verify imported table contents',monitor=True)
        columns = list(self.physical[table])
        order = ['id'] if 'id' in columns else columns
        writer = HashWriter()
        self.cr.copy_expert(sql.SQL('COPY (SELECT * FROM public.{} ORDER BY {}) TO STDOUT').format(
            ident(table),sql.SQL(',').join(map(ident,order))).as_string(self.con),writer)
        progress.finish('table fingerprinted')
        return writer.hash.hexdigest()

    def mapping_fingerprint(self):
        progress.begin('fingerprint',operation='Verify lookup identities',monitor=True)
        writer=HashWriter()
        self.cr.copy_expert(sql.SQL("COPY (SELECT model,source_id,target_id FROM {} WHERE model<>'ir.attachment' "
            'ORDER BY model,source_id) TO STDOUT').format(ident(META,'record_map')).as_string(self.con),writer)
        progress.finish('lookup map fingerprinted')
        return writer.hash.hexdigest()

    def fingerprints(self):
        tables = {self.target[m]['table'] for m in self.selected}
        tables.update(p['table'] for p in self.relations)
        return {table:self.fingerprint_table(table) for table in sorted(tables)}

    def verify_fingerprints(self, expected):
        actual = self.fingerprints()
        if actual != expected:
            changed = sorted(t for t in set(actual)|set(expected) if actual.get(t)!=expected.get(t))
            raise MigrationError('Target changed between checkpoints: ' + ', '.join(changed))

    def preflight(self, replacing=True):
        progress.begin('mapping',operation='Resolve existing target identities',monitor=True)
        self.build_maps()
        self.plans = {m:self.plan_model(m) for m in sorted(self.selected)}
        for model in sorted(self.selected):
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} d WHERE d.model=%s AND d.module<>%s '
                'AND NOT EXISTS(SELECT 1 FROM {} s WHERE s.id=d.res_id))').format(
                    ident(SCHEMA,'ir_model_data'),self.src(model)),
                    f'Source XML ID points to a missing custom record: {model}',[model,'__export__'])
        self.relations = self.relation_plans()
        self.prepare_attachment_scope()
        if replacing:
            progress.begin('preflight',operation='Validate incoming target references',monitor=True)
            self.prepare_incoming()
        save_json(self.stage/'preflight.json', dict(passed=True, selected=sorted(self.selected),
            omitted=self.manifest['omitted'], ignored_fields=self.report['ignored_fields'],skipped_fields=self.report['skipped_fields'],
            deferred={m:sorted(p['deferred']) for m,p in self.plans.items()},
            attachment_fields={m:sorted(p['attachments']) for m,p in self.plans.items()}))
        progress.log(f'Shared-field preflight: {len(self.report["skipped_fields"])} source-only/nonstored fields skipped; see preflight.json')
        progress.finish('preflight passed')

    def attachment_source(self):
        return ident(WORK,'selected_attachments')

    def prepare_attachment_scope(self, excluded_owners=()):
        """Filter cached snapshots too; raw extraction is never rewritten."""
        owners=self.normalize_model(sql.SQL('a.res_model'))
        owner=sql.SQL('({}=ANY({}) AND {} IS NOT NULL)').format(owners,sql.Literal(sorted(self.selected)),
                    self.mapped(owners,sql.SQL('a.res_id')))
        links=[]
        for model,plan in self.plans.items():
            if model not in self.selected:
                continue
            for name in self.manifest['tables'][self.models[model]['table']]['columns']:
                dest=self.conversions.get('fields',{}).get(model,{}).get(name,name)
                if dest in plan['attachments']:
                    links.append(sql.SQL('SELECT {} FROM {}').format(ident(name),self.src(model)))
        for p in self.relations:
            if p['phase']=='attachments':
                links.append(sql.SQL('SELECT {} FROM {}').format(ident(p['source']['column2']),ident(SCHEMA,p['source']['table'])))
        if links:
            owner=sql.SQL('{} OR a.id IN ({})').format(owner,sql.SQL(' UNION ').join(links))
        if excluded_owners:
            owner=sql.SQL('({}) AND NOT coalesce({}=ANY({}),false)').format(
                owner,owners,sql.Literal(sorted(excluded_owners)))
        self.execute(sql.SQL('CREATE OR REPLACE VIEW {} AS SELECT a.* FROM {} a WHERE {}').format(
            self.attachment_source(),ident(SCHEMA,'ir_attachment'),owner))
        for name in self.manifest['tables']['ir_attachment']['columns']:
            if name!='id' and not self.stored_destination('ir.attachment',name):
                self.skip_field('ir.attachment',name)

    def incoming_value(self, model, value):
        return sql.SQL('(SELECT new_id FROM {} WHERE model={} AND old_id={})').format(
            ident(META,'incoming_map'), sql.Literal(model) if isinstance(model,str) else model, value)

    def prepare_incoming(self):
        self.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (model text,old_id bigint,new_id bigint,PRIMARY KEY(model,old_id))').format(
            ident(META,'incoming_map')))
        self.execute(sql.SQL('DELETE FROM {}').format(ident(META,'incoming_map')))
        self.execute('CREATE TEMP TABLE incoming_candidates(model text,old_id bigint,new_id bigint) ON COMMIT DROP')
        self.execute(sql.SQL('INSERT INTO incoming_candidates SELECT t.model,t.res_id,s.res_id FROM public.ir_model_data t '
            'JOIN {} s USING(module,name) WHERE s.model=t.model AND t.model=ANY(%s) AND s.module<>%s').format(
                ident(SCHEMA,'ir_model_data')), [sorted(self.selected),'__export__'])
        for model,key in self.rules.get('stable_keys',{}).items():
            if model not in self.selected:
                continue
            for rel in (self.src(model),self.dst(model)):
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} WHERE {} IS NOT NULL GROUP BY {} HAVING count(*)>1)').format(
                    rel,ident(key),ident(key)), f'Ambiguous custom stable key: {model}.{key}')
            self.execute(sql.SQL('INSERT INTO incoming_candidates SELECT %s,t.id,s.id FROM {} t JOIN {} s ON t.{}=s.{} '
                'WHERE t.{} IS NOT NULL').format(self.dst(model),self.src(model),ident(key),ident(key),ident(key)),[model])
        for model,entries in self.rules.get('incoming_ids',{}).items():
            if model not in self.selected:
                raise MigrationError(f'Incoming mapping outside selected models: {model}')
            for old,new in entries.items():
                self.fail(sql.SQL('SELECT NOT EXISTS(SELECT 1 FROM {} WHERE id=%s)').format(self.dst(model)),
                          f'Old custom mapping record absent: {model}',[int(old)])
                self.fail(sql.SQL('SELECT NOT EXISTS(SELECT 1 FROM {} WHERE id=%s)').format(self.src(model)),
                          f'Replacement mapping record absent: {model}',[int(new)])
                self.execute('DELETE FROM incoming_candidates WHERE model=%s AND old_id=%s',[model,int(old)])
                self.execute('INSERT INTO incoming_candidates VALUES (%s,%s,%s)',[model,int(old),int(new)])
        self.fail('SELECT EXISTS(SELECT 1 FROM incoming_candidates GROUP BY model,old_id HAVING count(DISTINCT new_id)>1)',
                  'Ambiguous incoming custom identities')
        self.execute(sql.SQL('INSERT INTO {} SELECT model,old_id,min(new_id) FROM incoming_candidates GROUP BY model,old_id').format(
            ident(META,'incoming_map')))
        self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.ir_model_data t WHERE t.model=ANY(%s) AND {} IS NULL)').format(
            self.incoming_value(sql.SQL('t.model'),sql.SQL('t.res_id'))),
            'Existing target custom XML ID has no proven replacement', [sorted(self.selected)])
        self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s JOIN public.ir_model_data t USING(module,name) '
            'WHERE s.model=ANY(%s) AND s.module<>%s AND t.model<>s.model)').format(ident(SCHEMA,'ir_model_data')),
            'Custom XML-ID model conflict', [sorted(self.selected),'__export__'])
        selected_tables = {self.target[m]['table']:m for m in self.selected}
        owned = {p['table'] for p in self.relations}
        scalars, dynamic, fks, shared_owned = {}, set(), [], {}
        def add(table,column,model):
            if table in selected_tables or table in owned or column not in self.physical.get(table,{}):
                return
            if column=='id':
                raise MigrationError(f'Incoming primary-key dependency needs an adapter: {table}')
            if self.physical[table][column]['type']=='jsonb':
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.{} WHERE {} IS NOT NULL)').format(ident(table),ident(column)),
                          f'Incoming company-dependent reference requires adapter: {table}.{column}')
                return
            previous = scalars.setdefault(table,{}).get(column)
            if previous and previous!=model:
                raise MigrationError(f'Conflicting incoming relation metadata: {table}.{column}')
            scalars[table][column]=model
        self.execute("SELECT s.relname,k.conname,pg_get_constraintdef(k.oid),t.relname,a.attname,b.attname,"
            "array_length(k.conkey,1) FROM pg_constraint k JOIN pg_class s ON s.oid=k.conrelid "
            "JOIN pg_class t ON t.oid=k.confrelid JOIN pg_namespace n ON n.oid=s.relnamespace "
            "JOIN pg_namespace tn ON tn.oid=t.relnamespace "
            "JOIN pg_attribute a ON a.attrelid=s.oid AND a.attnum=k.conkey[1] "
            "JOIN pg_attribute b ON b.attrelid=t.oid AND b.attnum=k.confkey[1] WHERE k.contype='f' AND n.nspname='public' AND tn.nspname='public'")
        for table,name,definition,parent,column,key,size in self.cr.fetchall():
            if parent not in selected_tables:
                continue
            if size!=1 or key!='id':
                raise MigrationError(f'Unsupported incoming composite FK: {table}.{name}')
            fks.append((table,name,definition))
            add(table,column,selected_tables[parent])
        for model,meta in self.target.items():
            table=meta['table']
            for name,f in meta['fields'].items():
                related=f.get('relation')
                if f.get('type')=='many2one' and f.get('store') and related in self.selected:
                    add(table,name,related)
                elif f.get('type')=='many2many':
                    if model not in self.selected and related in self.selected and f.get('relation_table') in owned:
                        shared_owned.setdefault(f['relation_table'],{})[f['column2']]=related
                    if model in self.selected:
                        add(f.get('relation_table'),f.get('column1'),model)
                    if related in self.selected:
                        add(f.get('relation_table'),f.get('column2'),related)
                elif f.get('store') and f.get('type')=='reference' and table not in selected_tables and name in self.physical.get(table,{}):
                    dynamic.add((table,name,None))
        for table,columns in self.physical.items():
            if table in selected_tables or table in owned or table=='ir_model_data':
                continue
            if {'res_model','res_id'}.issubset(columns):
                dynamic.add((table,'res_id','res_model'))
            elif {'res_model_id','res_id'}.issubset(columns):
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.{} t JOIN public.ir_model m ON m.id=t.res_model_id '
                    'WHERE m.model=ANY(%s) AND t.res_id IS NOT NULL AND t.res_id<>0)').format(ident(table)),
                    f'Incoming res_model_id reference requires adapter: {table}', [sorted(self.selected)])
        for table,custom_columns in shared_owned.items():
            columns=list(self.physical[table])
            actual_values=[]
            for column in columns:
                value=sql.SQL('t.{}').format(ident(column))
                if column in custom_columns:
                    mapped=self.incoming_value(custom_columns[column],value)
                    self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.{} t WHERE {} IS NOT NULL AND {} IS NULL)').format(
                        ident(table),value,mapped),f'Shared incoming M2M identity missing: {table}.{column}')
                    value=mapped
                actual_values.append(value)
            expected=[]
            for plan in self.relations:
                if plan['table']==table:
                    values=dict(zip(plan['columns'],plan['values']))
                    expected.append(sql.SQL('SELECT {} FROM {} s').format(
                        sql.SQL(',').join(values[c] for c in columns),ident(SCHEMA,plan['source']['table'])))
            self.fail(sql.SQL('SELECT EXISTS(SELECT {} FROM public.{} t EXCEPT SELECT * FROM ({}) expected_links)').format(
                sql.SQL(',').join(actual_values),ident(table),sql.SQL(' UNION ').join(expected)),
                f'Replacement would erase prepared standard/target-only associations in shared relation table: {table}')
        for table,columns in scalars.items():
            for column,model in columns.items():
                value=sql.SQL('t.{}').format(ident(column))
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.{} t WHERE {} IS NOT NULL AND {} IS NULL)').format(
                    ident(table),value,self.incoming_value(model,value)),
                    f'Incoming reference has no proven replacement: {table}.{column} -> {model}')
        self.dynamic=[]
        for table,column,discriminator in sorted(dynamic,key=str):
            value=sql.SQL('t.{}').format(ident(column))
            model=(sql.SQL('t.{}').format(ident(discriminator)) if discriminator else sql.SQL("split_part({},',',1)").format(value))
            rid=value if discriminator else sql.SQL("nullif(split_part({},',',2),'')::bigint").format(value)
            where=sql.SQL('{}=ANY(%s) AND {} IS NOT NULL').format(model,value)
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.{} t WHERE {} AND {} IS NULL)').format(
                ident(table),where,self.incoming_value(model,rid)),
                f'Incoming dynamic reference has no proven replacement: {table}.{column}', [sorted(self.selected)])
            self.dynamic.append((table,column,discriminator))
        # Relational defaults are not ORM fields on ir.default itself.
        if 'ir_default' in self.physical:
            self.fail("SELECT EXISTS(SELECT 1 FROM public.ir_default d JOIN public.ir_model_fields f ON f.id=d.field_id "
                      "WHERE f.relation=ANY(%s) AND d.json_value NOT IN ('false','null','[]'))",
                      'Incoming relational defaults require an explicit adapter', [sorted(self.selected)])
        self.incoming_scalars,self.incoming_fks=scalars,fks

    def replace(self):
        print('DELETE + COPY + XML-ID repair: one transaction',flush=True)
        # All incoming FKs are restored verbatim and validated before COMMIT.
        # Dropping them transactionally prevents ON DELETE actions on standard data.
        for table,name,_ in self.incoming_fks:
            progress.begin('constraints',table=table,operation='Temporarily remove incoming FK',monitor=True)
            self.execute(sql.SQL('ALTER TABLE public.{} DROP CONSTRAINT {}').format(ident(table),ident(name)))
        pending=[]
        for table,columns in self.incoming_scalars.items():
            if not columns:
                continue
            conditions=sql.SQL(' OR ').join(sql.SQL('{} IS NOT NULL').format(ident(c)) for c in columns)
            temp='incoming_'+str(len(pending))
            captured=['id',*columns] if 'id' in self.physical[table] else list(self.physical[table])
            self.execute(sql.SQL('CREATE TABLE {} AS SELECT {} FROM public.{} WHERE {}').format(
                ident(WORK,temp),sql.SQL(',').join(map(ident,captured)),ident(table),conditions))
            if 'id' not in self.physical[table]:
                self.execute(sql.SQL('DELETE FROM public.{} WHERE {}').format(ident(table),conditions))
            pending.append((table,temp,columns))
        for table in sorted({p['table'] for p in self.relations}):
            self.execute(sql.SQL('DELETE FROM public.{}').format(ident(table)))
        for model in sorted(self.selected):
            progress.begin('delete custom',model=model,operation='DELETE selected custom records',monitor=True)
            self.execute(sql.SQL('DELETE FROM {}').format(self.dst(model)))
        for model in sorted(self.selected):
            print(f'Load custom model {model}',flush=True)
            expressions=self.plans[model]['expressions']
            expected=self.manifest['tables'][self.models[model]['table']]['rows']
            progress.begin('load custom',model=model,operation='INSERT SELECT',monitor=True,expected_rows=expected)
            self.execute(sql.SQL('INSERT INTO {} ({}) SELECT {} FROM {} s').format(self.dst(model),
                sql.SQL(',').join(map(ident,expressions)),sql.SQL(',').join(expressions.values()),self.src(model)))
            expected=self.manifest['tables'][self.models[model]['table']]['rows']
            if self.cr.rowcount!=expected:
                raise MigrationError(f'Custom row count mismatch: {model}')
            progress.update(processed=self.cr.rowcount,total=expected)
            progress.finish('loaded; pending commit')
        self.load_relations('custom')
        for table,temp,columns in pending:
            expressions={c:(self.incoming_value(columns[c],sql.SQL('s.{}').format(ident(c))) if c in columns else
                            sql.SQL('s.{}').format(ident(c))) for c in
                         (columns if 'id' in self.physical[table] else self.physical[table])}
            if 'id' in self.physical[table]:
                assignments=sql.SQL(',').join(sql.SQL('{}={}').format(ident(c),expressions[c]) for c in columns)
                self.execute(sql.SQL('UPDATE public.{} t SET {} FROM {} s WHERE t.id=s.id').format(
                    ident(table),assignments,ident(WORK,temp)))
            else:
                self.execute(sql.SQL('INSERT INTO public.{} ({}) SELECT {} FROM {} s').format(ident(table),
                    sql.SQL(',').join(map(ident,expressions)),sql.SQL(',').join(expressions.values()),ident(WORK,temp)))
        for table,column,discriminator in self.dynamic:
            value=sql.SQL('t.{}').format(ident(column))
            model=sql.SQL('t.{}').format(ident(discriminator)) if discriminator else sql.SQL("split_part({},',',1)").format(value)
            rid=value if discriminator else sql.SQL("nullif(split_part({},',',2),'')::bigint").format(value)
            mapped=self.incoming_value(model,rid)
            expression=mapped if discriminator else sql.SQL("{}||','||{}::text").format(model,mapped)
            self.execute(sql.SQL('UPDATE public.{} t SET {}={} WHERE {}=ANY(%s) AND {} IS NOT NULL').format(
                ident(table),ident(column),expression,model,value),[sorted(self.selected)])
        progress.begin('XML IDs',operation='Repair custom XML-ID destinations',monitor=True)
        self.repair_xmlids()
        for table,name,definition in self.incoming_fks:
            progress.begin('constraints',table=table,operation='Restore and validate incoming FK',monitor=True)
            self.execute(sql.SQL('ALTER TABLE public.{} ADD CONSTRAINT {} {}').format(ident(table),ident(name),sql.SQL(definition)))
        for model in sorted(self.selected):
            self.reset_sequence(self.target[model]['table'])
        self.validate_custom()

    def repair_xmlids(self):
        self.execute(sql.SQL('UPDATE public.ir_model_data t SET res_id={} WHERE t.model=ANY(%s)').format(
            self.incoming_value(sql.SQL('t.model'),sql.SQL('t.res_id'))),[sorted(self.selected)])
        self.execute(sql.SQL("INSERT INTO public.ir_model_data(module,name,model,res_id,noupdate) "
            'SELECT s.module,s.name,s.model,s.res_id,true FROM {} s WHERE s.model=ANY(%s) AND s.module<>%s '
            'ON CONFLICT(module,name) DO UPDATE SET res_id=EXCLUDED.res_id').format(ident(SCHEMA,'ir_model_data')),
            [sorted(self.selected),'__export__'])
        self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s LEFT JOIN public.ir_model_data t USING(module,name) '
            'WHERE s.model=ANY(%s) AND s.module<>%s AND (t.id IS NULL OR t.model<>s.model OR t.res_id<>s.res_id))').format(
                ident(SCHEMA,'ir_model_data')),'Custom XML-ID validation failed',[sorted(self.selected),'__export__'])

    def load_relations(self, phase):
        visited=set()
        for p in self.relations:
            if p['phase']!=phase:
                continue
            r=p['source']
            key=(p['table'],tuple(p['columns']))
            if key in visited:
                continue
            visited.add(key)
            progress.begin('relationships',model=r['model'],table=p['table'],operation='Insert '+phase+' links',monitor=True)
            self.execute(sql.SQL('INSERT INTO public.{} ({}) SELECT DISTINCT {},{} FROM {} s ON CONFLICT DO NOTHING').format(
                ident(p['table']),sql.SQL(',').join(map(ident,p['columns'])),*p['values'],ident(SCHEMA,r['table'])))

    def reset_sequence(self, table):
        sequence=self.scalar('SELECT pg_get_serial_sequence(%s,%s)',['public.'+table,'id'])
        if sequence:
            self.execute(sql.SQL('SELECT setval(%s::regclass,greatest(coalesce(max(id),0)+1,1),false) FROM public.{}').format(
                ident(table)),[sequence])

    def validate_custom(self):
        for model in sorted(self.selected):
            self.fail(sql.SQL('SELECT EXISTS((SELECT id FROM {} EXCEPT SELECT id FROM {}) UNION ALL '
                '(SELECT id FROM {} EXCEPT SELECT id FROM {}))').format(self.src(model),self.dst(model),self.dst(model),self.src(model)),
                f'Custom IDs differ from source: {model}')

    def external(self):
        for model in sorted(self.selected):
            fields=self.plans[model]['deferred']
            if fields:
                progress.begin('map references',model=model,operation='Update shared external fields',monitor=True)
                self.execute(sql.SQL('UPDATE {} t SET {} FROM {} s WHERE t.id=s.id').format(self.dst(model),
                    sql.SQL(',').join(sql.SQL('{}={}').format(ident(n),v) for n,v in fields.items()),self.src(model)))
        self.load_relations('external')

    def validate_values(self, check_attachments=True):
        """Compare actual values/links, not only counts or map existence."""
        for model in sorted(self.selected):
            plan=self.plans[model]
            expected={**plan['expressions'],**plan['deferred'],**plan['attachments']}
            conditions=sql.SQL(' OR ').join(sql.SQL('t.{} IS DISTINCT FROM ({})::{}').format(
                ident(name),value,sql.SQL(self.physical[self.target[model]['table']][name]['type']))
                for name,value in expected.items())
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s JOIN {} t USING(id) WHERE {})').format(
                self.src(model),self.dst(model),conditions),f'Imported field values differ from source/mapping: {model}')
        for table in sorted({p['table'] for p in self.relations}):
            columns=list(self.physical[table])
            selects=[]
            for p in self.relations:
                if p['table']!=table:
                    continue
                values=dict(zip(p['columns'],p['values']))
                selects.append(sql.SQL('SELECT {},{} FROM {} s').format(
                    values[columns[0]],values[columns[1]],ident(SCHEMA,p['source']['table'])))
            expected=sql.SQL(' UNION ').join(selects)
            expected=sql.SQL('SELECT * FROM ({}) expected_links').format(expected)
            actual=sql.SQL('SELECT {} FROM public.{}').format(sql.SQL(',').join(map(ident,columns)),ident(table))
            self.fail(sql.SQL('SELECT EXISTS(({} EXCEPT {}) UNION ALL ({} EXCEPT {}))').format(
                actual,expected,expected,actual),f'Imported relationship values differ: {table}')
        if check_attachments and self.scalar('SELECT to_regclass(%s)',[META+'.attachment_map']):
            self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s LEFT JOIN {} m ON m.source_id=s.id '
                'LEFT JOIN public.ir_attachment t ON t.id=m.target_id WHERE t.id IS NULL OR '
                't.res_id IS DISTINCT FROM CASE WHEN s.res_model IS NULL OR s.res_id=0 THEN s.res_id ELSE {} END '
                'OR t.res_model IS DISTINCT FROM {} OR t.store_fname IS DISTINCT FROM s.store_fname '
                'OR t.db_datas IS DISTINCT FROM s.db_datas)').format(self.attachment_source(),
                    ident(META,'attachment_map'),self.mapped(self.normalize_model(sql.SQL('s.res_model')),sql.SQL('s.res_id')),
                    self.normalize_model(sql.SQL('s.res_model'))),'Attachment payload/owner/link validation failed')

    def attachments(self, source_root, target_root, restore_links=True, incremental=False):
        progress.begin('attachments',operation='Import scoped attachment metadata',monitor=True)
        source=self.attachment_source()
        cols=self.manifest['tables']['ir_attachment']['columns']
        target_cols=self.physical['ir_attachment']
        self.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (source_id bigint PRIMARY KEY,target_id bigint UNIQUE NOT NULL)').format(
            ident(META,'attachment_map')))
        self.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM {})').format(ident(META,'attachment_map')))
        if self.cr.fetchone()[0] and not incremental:
            raise MigrationError('Uncheckpointed attachment mapping exists')
        if incremental:
            self.execute(sql.SQL('CREATE TEMP TABLE pending_attachment_rows ON COMMIT DROP AS '
                'SELECT s.* FROM {} s WHERE NOT EXISTS(SELECT 1 FROM {} m WHERE m.source_id=s.id)').format(
                    source,ident(META,'attachment_map')))
            source=ident('pg_temp','pending_attachment_rows')
        self.execute("SELECT pg_get_serial_sequence('public.ir_attachment','id')")
        seq=self.cr.fetchone()[0]
        if not seq:
            raise MigrationError('Attachment ID sequence is missing')
        self.reset_sequence('ir_attachment')
        self.execute(sql.SQL('INSERT INTO {} SELECT id,nextval(%s::regclass) FROM {} ORDER BY id').format(
            ident(META,'attachment_map'),source),[seq])
        self.execute(sql.SQL("INSERT INTO {} SELECT 'ir.attachment',source_id,target_id FROM {} "
                            'ON CONFLICT(model,source_id) DO UPDATE SET target_id=EXCLUDED.target_id').format(
            ident(META,'record_map'),ident(META,'attachment_map')))
        expressions={'id':self.mapped('ir.attachment',sql.SQL('s.id'))}
        for name in cols:
            if name=='id':
                continue
            if not self.stored_destination('ir.attachment',name):
                self.skip_field('ir.attachment',name)
                continue
            if name=='access_token':
                continue
            value=sql.SQL('s.{}').format(ident(name))
            if name in ('create_uid','write_uid'):
                mapped=self.mapped('res.users',value)
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND {} IS NULL)').format(source,value,mapped),
                          f'Attachment user missing: {name}')
                value=mapped
            elif name=='company_id':
                mapped=self.mapped('res.company',value)
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NOT NULL AND {} IS NULL)').format(source,value,mapped),
                          'Attachment company mapping missing')
                value=mapped
            elif name=='res_id':
                rel=self.normalize_model(sql.SQL('s.res_model'))
                mapped=self.mapped(rel,value)
                self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE s.res_model IS NOT NULL AND '
                    's.res_id IS NOT NULL AND s.res_id<>0 AND {} IS NULL)').format(source,mapped),
                    'Attachment owner mapping missing')
                value=sql.SQL('CASE WHEN s.res_model IS NULL OR s.res_id=0 THEN s.res_id ELSE {} END').format(mapped)
            elif name=='res_model':
                value=self.normalize_model(value)
            expressions[name]=value
        for name,col in target_cols.items():
            if name not in expressions and col['required'] and not col['default']:
                raise MigrationError(f'Required target attachment field needs adapter: {name}')
        self.execute(sql.SQL('INSERT INTO public.ir_attachment ({}) SELECT {} FROM {} s').format(
            sql.SQL(',').join(map(ident,expressions)),sql.SQL(',').join(expressions.values()),source))
        copied=set()
        examined,copied_bytes=0,0
        progress.begin('attachment files',operation='Copy and verify available files')
        cursor=self.con.cursor(name='prepared_attachment_files')
        cursor.itersize=1000
        cursor.execute(sql.SQL('SELECT id,store_fname,checksum,file_size FROM {} WHERE store_fname IS NOT NULL ORDER BY id').format(source))
        for source_id,name,checksum,size in cursor:
            examined+=1
            progress.update(files_examined=examined)
            if name in copied:
                continue
            src=safe_attachment_path(source_root,name)
            dst=safe_attachment_path(target_root,name)
            if not src.is_file():
                self.report['missing_files'].append(dict(source_id=source_id,path=name))
                progress.update(missing=len(self.report['missing_files']))
                continue
            sha=digest(src,'sha1')
            if (checksum and sha!=checksum) or (size is not None and src.stat().st_size!=size):
                raise MigrationError(f'Source attachment checksum/size mismatch: {source_id}')
            dst.parent.mkdir(parents=True,exist_ok=True)
            if dst.exists():
                if digest(dst,'sha1')!=sha:
                    raise MigrationError(f'Target attachment content collision: {source_id}')
            else:
                temp=dst.with_name(dst.name+'.migration-'+uuid.uuid4().hex)
                try:
                    with open(src,'rb') as inp,open(temp,'xb') as out:
                        shutil.copyfileobj(inp,out,1024*1024)
                        out.flush()
                        os.fsync(out.fileno())
                    temp.chmod(0o600)
                    if digest(temp,'sha1')!=sha:
                        raise MigrationError(f'Copied attachment checksum mismatch: {source_id}')
                    try:
                        os.link(temp,dst)  # Atomic publication without overwriting a racing file.
                    except FileExistsError:
                        if digest(dst,'sha1')!=sha:
                            raise MigrationError(f'Target attachment content collision: {source_id}')
                    directory_fd=os.open(dst.parent,os.O_RDONLY|os.O_DIRECTORY)
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                finally:
                    temp.unlink(missing_ok=True)
            copied.add(name)
            copied_bytes+=src.stat().st_size
            progress.update(copied=len(copied),bytes=copied_bytes)
        cursor.close()
        if restore_links:
            for model in sorted(self.selected):
                self.restore_attachment_links(model)
            for p in self.relations:
                if p['phase']=='attachments':
                    self.fail(sql.SQL('SELECT EXISTS(SELECT 1 FROM {} s WHERE {} IS NULL OR {} IS NULL)').format(
                        ident(SCHEMA,p['source']['table']),*p['values']), 'Unmapped attachment relationship')
            self.load_relations('attachments')
        self.reset_sequence('ir_attachment')
        self.report['copied_files']=self.report.get('copied_files',0)+len(copied)
        save_json(self.stage/'attachments.json',dict(missing_files=self.report['missing_files'],copied_files=len(copied)))
        progress.finish('attachments imported; pending commit')

    def restore_attachment_links(self, model):
        fields=self.plans[model]['attachments']
        for name,value in fields.items():
            # The map now exists; verify every deferred attachment reference.
            source_name=next((n for n in self.manifest['tables'][self.models[model]['table']]['columns']
                if self.conversions.get('fields',{}).get(model,{}).get(n,n)==name),name)
            self.check_link(model,source_name,sql.SQL('s.{}').format(ident(source_name)),value,'ir.attachment')
        if fields:
            self.execute(sql.SQL('UPDATE {} t SET {} FROM {} s WHERE t.id=s.id').format(self.dst(model),
                sql.SQL(',').join(sql.SQL('{}={}').format(ident(n),v) for n,v in fields.items()),self.src(model)))
        return self.cr.rowcount if fields else 0
