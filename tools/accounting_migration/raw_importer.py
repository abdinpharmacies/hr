"""Public importer: raw reference values, attachment allocation, report-only audits."""
from psycopg2 import sql

from common import MigrationError, save_json
from prepared_importer import PreparedImporter, META, WORK, ident, missing_identity_query
from prepared_snapshot import SCHEMA
from relationship_policy import RawReferencePolicy, RelationshipAudit


class RawImporter(PreparedImporter):
    relationship_policy = RawReferencePolicy.name

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.audit = RelationshipAudit(self)
        self.plan_errors = {}
        self.relation_errors = []

    def normalize_model(self, value):
        return value

    def mapped(self, model, value):
        if isinstance(model,str) and model!='ir.attachment':
            return RawReferencePolicy.value(value)
        attachment = sql.SQL('coalesce((SELECT target_id FROM {} WHERE source_id={}),{})').format(
            ident(META,'attachment_map'),value,value)
        if isinstance(model,str):
            return attachment
        return sql.SQL("CASE WHEN {}='ir.attachment' THEN {} ELSE {} END").format(model,attachment,value)

    def check_link(self, *args, **kwargs):
        # All existence/model checks run after copy in isolated audit queries.
        return None

    def validate_targets(self, *args, **kwargs):
        return None

    def validate_ids(self):
        report={}
        for table in ('res_users','res_partner'):
            self.execute(missing_identity_query(ident(SCHEMA,table),ident('public',table)))
            missing=[r[0] for r in self.cr]
            self.execute(sql.SQL('SELECT count(*),count(*) FILTER(WHERE id>=7) FROM {}').format(ident(SCHEMA,table)))
            total,checked=self.cr.fetchone()
            report[table]=dict(source_count=total,checked_count=checked,skipped_count=total-checked,
                               missing_count=len(missing),missing_ids=missing)
        save_json(self.stage/'id-validation.json',report)
        self.identity_report=report
        self.report['identity_checks']=report
        return report

    def build_maps(self):
        # The only remapping exception is allocated imported attachment IDs.
        self.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (model text,source_id bigint,target_id bigint,'
            'PRIMARY KEY(model,source_id))').format(ident(META,'record_map')))
        self.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} (source_id bigint PRIMARY KEY,target_id bigint UNIQUE NOT NULL)').format(
            ident(META,'attachment_map')))
        self.execute(sql.SQL("INSERT INTO {} SELECT 'ir.attachment',source_id,target_id FROM {} "
            'ON CONFLICT(model,source_id) DO UPDATE SET target_id=EXCLUDED.target_id').format(
                ident(META,'record_map'),ident(META,'attachment_map')))

    def preflight(self, replacing=True):
        self.audit.ensure()
        self.build_maps()
        for category in ('integer_links','polymorphic','external_ids','incoming_ids','stable_keys','xmlids'):
            config=self.conversions.get(category) or self.rules.get(category)
            if config:
                self.audit.add('ignored_relationship_rules',category=category)
        self.plans={}
        for model in sorted(self.selected):
            self.execute('SAVEPOINT raw_field_plan')
            try:
                self.plans[model]=self.plan_model(model)
            except Exception as exc:
                self.execute('ROLLBACK TO SAVEPOINT raw_field_plan')
                self.plan_errors[model]=dict(error_type=type(exc).__name__,reason='Field conversion plan could not be constructed')
                self.plans[model]=dict(expressions={'id':sql.SQL('s.id')},deferred={},attachments={})
            finally:
                self.execute('RELEASE SAVEPOINT raw_field_plan')
        self.relations=self.relation_plans()
        self.incoming_scalars={}
        self.incoming_fks=[]
        self.dynamic=[]
        self.prepare_attachment_scope()
        for table, report in getattr(self,'identity_report',{}).items():
            for missing in report['missing_ids']:
                self.audit.add('missing_identity',table=table,source_record_id=missing)
        save_json(self.stage/'preflight.json',dict(passed=True,policy=self.relationship_policy,
            selected=sorted(self.selected),omitted=self.manifest['omitted'],plan_errors=self.plan_errors,
            skipped_fields=self.report['skipped_fields'],ignored_fields=self.report['ignored_fields']))

    def plan_model(self, model):
        source=self.manifest['tables'][self.models[model]['table']]['columns']
        target=self.target[model]
        physical=self.physical[target['table']]
        expressions={'id':sql.SQL('s.id')}
        attachments={}
        for name,column in source.items():
            if name=='id':
                continue
            destination=self.conversions.get('fields',{}).get(model,{}).get(name,name)
            if self.rules.get('ignore_fields',{}).get(model,{}).get(name):
                self.report['ignored_fields'].append(dict(model=model,field=name,
                    reason=self.rules['ignore_fields'][model][name]))
                continue
            if not self.stored_destination(model,destination):
                self.skip_field(model,name,destination)
                continue
            field=target['fields'][destination]
            value=sql.SQL('s.{}').format(ident(name))
            if field.get('company_dependent'):
                value=self.property_value(model,name,field)
            elif physical[destination]['type']=='jsonb' and field.get('translate') and column['type']!='jsonb':
                value=sql.SQL("CASE WHEN s.{} IS NULL THEN NULL ELSE jsonb_build_object('en_US',{}) END").format(ident(name),value)
                if 'ir_translation' in self.manifest['tables']:
                    value=sql.SQL("CASE WHEN s.{} IS NULL THEN NULL ELSE coalesce({},'{{}}'::jsonb)||coalesce("
                        "(SELECT jsonb_object_agg(tr.lang,tr.value ORDER BY tr.id) FROM {} tr "
                        "WHERE tr.type='model' AND tr.name={} AND tr.res_id=s.id AND tr.value IS NOT NULL),'{{}}'::jsonb) END").format(
                            ident(name),value,ident(SCHEMA,'ir_translation'),sql.Literal(model+','+name))
            else:
                selections=self.conversions.get('selections',{}).get(model,{}).get(name,{})
                if selections:
                    cases=sql.SQL(' ').join(sql.SQL('WHEN {} THEN {}').format(sql.Literal(str(old)),
                        sql.Literal(None if new is None else str(new))) for old,new in selections.items())
                    value=sql.SQL('(CASE {}::text {} ELSE {}::text END)').format(value,cases,value)
                if selections or column['type']!=physical[destination]['type']:
                    value=sql.SQL('({})::{}').format(value,sql.SQL(physical[destination]['type']))
            expressions[destination]=value
            if field.get('relation')=='ir.attachment':
                attachments[destination]=self.mapped('ir.attachment',sql.SQL('s.{}').format(ident(name)))
        for name,column in physical.items():
            if name in expressions:
                continue
            field=target['fields'].get(name,{})
            source_name=next((old for old,new in self.conversions.get('fields',{}).get(model,{}).items() if new==name),name)
            if field.get('company_dependent') and source_name in self.models[model].get('fields',{}):
                expressions[name]=self.property_value(model,source_name,field)
                continue
            if column['default'] or not column['required']:
                continue
            default=target.get('defaults',{}).get(name)
            if default is not None and not field.get('relation'):
                expressions[name]=sql.Literal(default)
            # Otherwise PostgreSQL's actual NOT NULL constraint fails this table
            # operation; no invented relationship values or preflight blocker.
        return dict(expressions=expressions,deferred={},attachments=attachments)

    def property_value(self, model, name, field):
        if 'ir_property' not in self.manifest['tables']:
            return sql.SQL('NULL::jsonb')
        kind=field['type']
        column={'float':'value_float','monetary':'value_float','integer':'value_integer',
            'boolean':'value_integer','char':'value_text','text':'value_text','selection':'value_text',
            'date':'value_datetime','datetime':'value_datetime','many2one':'value_reference'}.get(kind)
        if column is None:
            raise MigrationError('Unsupported company-dependent SQL conversion')
        value=sql.SQL('p.{}').format(ident(column))
        if kind=='many2one':
            value=sql.SQL("CASE WHEN {} ~ '^[^,]+,[0-9]+$' THEN to_jsonb(split_part({},',',2)::bigint) ELSE to_jsonb({}) END").format(value,value,value)
        elif kind=='boolean':
            value=sql.SQL('to_jsonb({}<>0)').format(value)
        elif kind in ('date','datetime'):
            value=sql.SQL('to_jsonb(to_char({},{}))').format(value,sql.Literal('YYYY-MM-DD' if kind=='date' else 'YYYY-MM-DD HH24:MI:SS'))
        else:
            value=sql.SQL('to_jsonb({})').format(value)
        companies=sql.SQL('SELECT id FROM {}').format(ident(SCHEMA,'res_company')) if 'res_company' in self.manifest['tables'] else sql.SQL('SELECT NULL::integer AS id WHERE false')
        return sql.SQL("(SELECT jsonb_object_agg(c.id::text,v.value) FROM ({} UNION SELECT DISTINCT pp.company_id FROM {} pp "
            'JOIN {} ff ON ff.id=pp.fields_id WHERE pp.company_id IS NOT NULL AND ff.model={} AND ff.name={}) c CROSS JOIN LATERAL '
            '(SELECT {} AS value FROM {} p JOIN {} f ON f.id=p.fields_id WHERE f.model={} AND f.name={} '
            'AND (p.res_id IS NULL OR p.res_id={}||s.id::text) AND (p.company_id IS NULL OR p.company_id=c.id) '
            'ORDER BY (p.res_id IS NOT NULL) DESC,(p.company_id IS NOT NULL) DESC,p.id DESC LIMIT 1) v)').format(
                companies,ident(SCHEMA,'ir_property'),ident(SCHEMA,'ir_model_fields'),sql.Literal(model),sql.Literal(name),
                value,ident(SCHEMA,'ir_property'),ident(SCHEMA,'ir_model_fields'),
                sql.Literal(model),sql.Literal(name),sql.Literal(model+','))

    def relation_plans(self):
        plans=[]
        for reference in self.manifest['relations']:
            model=reference['model']
            name=reference['field']
            field=self.target[model]['fields'].get(name,{})
            if not field or field.get('store') is False or field.get('related'):
                self.skip_field(model,name)
                continue
            table=field.get('relation_table')
            columns=[field.get('column1'),field.get('column2')]
            if table not in self.physical or any(c not in self.physical[table] for c in columns):
                self.relation_errors.append(dict(table=table or reference['table'],operation='relations',success=False,
                                                reason='Target relation table/columns are unavailable'))
                continue
            related=field.get('relation') or reference['related']
            first=sql.SQL('s.{}').format(ident(reference['column1']))
            second=sql.SQL('s.{}').format(ident(reference['column2']))
            if related=='ir.attachment':
                second=self.mapped('ir.attachment',second)
            plans.append(dict(source=reference,table=table,columns=columns,values=[first,second],
                              phase='attachments' if related=='ir.attachment' else 'custom'))
        return plans

    def repair_xmlids(self):
        for model in sorted(self.selected):
            self.execute(sql.SQL('INSERT INTO public.ir_model_data(module,name,model,res_id,noupdate) '
                "SELECT s.module,s.name,s.model,s.res_id,true FROM {} s WHERE s.model=%s AND s.module<>'__export__' "
                'AND NOT EXISTS(SELECT 1 FROM public.ir_model_data t WHERE t.module=s.module AND t.name=s.name AND t.model<>s.model) '
                'ON CONFLICT(module,name) DO UPDATE SET res_id=EXCLUDED.res_id WHERE ir_model_data.model=EXCLUDED.model').format(
                    ident(SCHEMA,'ir_model_data')),[model])

    def validate_values(self, check_attachments=True):
        # Shared scalar/value integrity remains checked. Prepared M2M supersets
        # are intentionally retained, so validate imports by subset elsewhere.
        relations=self.relations
        self.relations=[]
        try:
            super().validate_values(check_attachments=check_attachments)
        finally:
            self.relations=relations
