"""Global raw-reference policy and durable, nonblocking relationship audits."""
import os
import uuid
from pathlib import Path
from psycopg2 import sql
from psycopg2.extras import execute_values

from common import dumps, save_json
from prepared_checkpoints import META
from resume import fingerprint


class RawReferencePolicy:
    name = 'raw_references_report_only_v1'

    @staticmethod
    def value(value):
        return value


class RelationshipAudit:
    def __init__(self, engine):
        self.e = engine
        self.attempt = 1

    def ensure(self):
        self.e.execute(sql.SQL('CREATE TABLE IF NOT EXISTS {} '
            '(attempt integer,issue_id text,detail jsonb NOT NULL,PRIMARY KEY(attempt,issue_id))').format(
                sql.Identifier(META, 'relationship_issue')))
        self.e.execute(sql.SQL('SELECT value FROM {} WHERE name=%s').format(sql.Identifier(META,'checkpoint')), ['resume_state'])
        row = self.e.cr.fetchone()
        from common import loads
        self.attempt = (loads(row[0]).get('attempt', 0) if row else 0) + 1

    def add(self, kind, **detail):
        self.add_many([dict(kind=kind, **detail)])

    def add_many(self, details):
        rows = [(self.attempt, fingerprint(detail), dumps(detail)) for detail in details]
        if rows:
            execute_values(self.e.cr, sql.SQL('INSERT INTO {}(attempt,issue_id,detail) VALUES %s '
                'ON CONFLICT DO NOTHING').format(sql.Identifier(META,'relationship_issue')).as_string(self.e.con),
                rows, template='(%s,%s,%s::jsonb)', page_size=1000)

    def collect(self, query, kind, **context):
        """Audit errors are warnings; SAVEPOINT keeps the current transaction usable."""
        e = self.e
        e.execute('SAVEPOINT relationship_audit')
        try:
            cursor = e.con.cursor(name='relationship_' + uuid.uuid4().hex[:12])
            try:
                cursor.execute(query)
                while True:
                    rows = cursor.fetchmany(1000)
                    if not rows:
                        break
                    self.add_many([dict(kind=kind, source_record_id=record_id,
                                        referenced_model=model, reference_ids=values, **context)
                                   for record_id, model, values in rows])
            finally:
                cursor.close()
        except Exception as exc:
            e.execute('ROLLBACK TO SAVEPOINT relationship_audit')
            self.add('audit_query_failed', error_type=type(exc).__name__, **context)
        finally:
            e.execute('RELEASE SAVEPOINT relationship_audit')

    def row_id(self, table):
        return sql.SQL('s.id') if 'id' in self.e.physical.get(table,{}) else sql.SQL('NULL::bigint')

    def reference(self, model, table, field, related, value=None, condition=sql.SQL('true')):
        e = self.e
        value = value if value is not None else sql.SQL('s.{}').format(sql.Identifier(field))
        target = e.target.get(related,{}).get('table')
        missing = sql.SQL('true') if target not in e.physical else sql.SQL(
            'NOT EXISTS(SELECT 1 FROM public.{} t WHERE t.id={})').format(sql.Identifier(target),value)
        query = sql.SQL('SELECT {},{},jsonb_build_array({}) FROM public.{} s '
                       'WHERE {} AND {} IS NOT NULL AND {}').format(
            self.row_id(table), sql.Literal(related), value, sql.Identifier(table), condition, value, missing)
        self.collect(query, 'missing_reference' if target in e.physical else 'missing_reference_model',
                     model=model, table=table, field=field)

    def dynamic(self, model, table, field, discriminator=None, incoming=False):
        e = self.e
        raw = sql.SQL('s.{}').format(sql.Identifier(field))
        if discriminator:
            if discriminator not in e.physical.get(table,{}):
                self.add('invalid_audit_hint', model=model, table=table, field=field)
                return
            relation = sql.SQL('s.{}').format(sql.Identifier(discriminator))
            value = raw
            valid = sql.SQL('{} IS NOT NULL').format(relation)
            self.collect(sql.SQL('SELECT {},NULL::text,jsonb_build_array({}) FROM public.{} s '
                'WHERE {} IS NOT NULL AND {} IS NULL').format(self.row_id(table),raw,sql.Identifier(table),raw,relation),
                'missing_reference_model',model=model,table=table,field=field)
        else:
            valid = sql.SQL("({} ~ '^[^,]+,[0-9]+$' AND length(split_part({},',',2))<=18)").format(raw,raw)
            relation = sql.SQL("split_part({},',',1)").format(raw)
            value = sql.SQL("CASE WHEN {} THEN split_part({},',',2)::bigint END").format(valid,raw)
            self.collect(sql.SQL('SELECT {},NULL::text,NULL::jsonb FROM public.{} s '
                'WHERE {} IS NOT NULL AND NOT coalesce({},false)').format(
                    self.row_id(table),sql.Identifier(table),raw,valid),
                'malformed_reference',model=model,table=table,field=field)
        e.execute('SAVEPOINT relationship_models')
        try:
            e.execute(sql.SQL('SELECT DISTINCT {} FROM public.{} s WHERE {} IS NOT NULL AND {}').format(
                relation,sql.Identifier(table),raw,valid))
            models = [r[0] for r in e.cr.fetchall()]
        except Exception as exc:
            e.execute('ROLLBACK TO SAVEPOINT relationship_models')
            self.add('audit_query_failed',model=model,table=table,field=field,error_type=type(exc).__name__)
            models=[]
        finally:
            e.execute('RELEASE SAVEPOINT relationship_models')
        for related in models:
            if incoming and related not in e.custom_models:
                continue
            self.reference(model,table,field,related,value,
                           sql.SQL('{} AND {}={}').format(valid,relation,sql.Literal(related)))

    def foreign_keys(self, constraints):
        e = self.e
        for item in constraints:
            table, parent = item['table'], item['referenced_table']
            pairs = list(zip(item['columns'],item['referenced_columns']))
            if table not in e.physical or parent not in e.physical:
                self.add('foreign_key_model_missing',table=table,constraint=item['constraint'])
                continue
            values = [sql.SQL('s.{}').format(sql.Identifier(a)) for a,_ in pairs]
            all_present = sql.SQL(' AND ').join(sql.SQL('{} IS NOT NULL').format(v) for v in values)
            join = sql.SQL(' AND ').join(sql.SQL('t.{}=s.{}').format(sql.Identifier(b),sql.Identifier(a)) for a,b in pairs)
            missing = sql.SQL('NOT EXISTS(SELECT 1 FROM public.{} t WHERE {})').format(sql.Identifier(parent),join)
            condition = sql.SQL('({}) AND ({})').format(all_present,missing)
            if 'MATCH FULL' in item['definition']:
                any_present = sql.SQL(' OR ').join(sql.SQL('{} IS NOT NULL').format(v) for v in values)
                condition = sql.SQL('(({}) AND NOT({})) OR ({})').format(any_present,all_present,condition)
            self.collect(sql.SQL('SELECT {},{},jsonb_build_array({}) FROM public.{} s WHERE {}').format(
                self.row_id(table),sql.Literal(parent),sql.SQL(',').join(values),sql.Identifier(table),condition),
                'foreign_key_orphan',table=table,constraint=item['constraint'],columns=item['columns'])

    def company_values(self, model, table, field, meta):
        document=sql.SQL('s.{}').format(sql.Identifier(field))
        valid_key=sql.SQL("(k.key ~ '^[0-9]+$' AND length(k.key)<=18)")
        company=sql.SQL('CASE WHEN {} THEN k.key::bigint END').format(valid_key)
        company_table=self.e.target.get('res.company',{}).get('table','res_company')
        missing=sql.SQL('true') if company_table not in self.e.physical else sql.SQL(
            'NOT EXISTS(SELECT 1 FROM public.{} t WHERE t.id={})').format(sql.Identifier(company_table),company)
        base=sql.SQL('FROM public.{} s CROSS JOIN LATERAL jsonb_each({}) k').format(sql.Identifier(table),document)
        self.collect(sql.SQL('SELECT s.id,{},jsonb_build_array({}) {} WHERE NOT({}) OR {}').format(
            sql.Literal('res.company'),company,base,valid_key,missing),
            'company_reference_issue',model=model,table=table,field=field)
        if meta.get('type')=='many2one' and meta.get('relation'):
            valid=sql.SQL("(jsonb_typeof(k.value)='number' AND k.value::text ~ '^[0-9]+$' AND length(k.value::text)<=18)")
            value=sql.SQL('CASE WHEN {} THEN k.value::text::bigint END').format(valid)
            target=self.e.target.get(meta['relation'],{}).get('table')
            missing=sql.SQL('true') if target not in self.e.physical else sql.SQL(
                'NOT EXISTS(SELECT 1 FROM public.{} t WHERE t.id={})').format(sql.Identifier(target),value)
            self.collect(sql.SQL("SELECT s.id,{},jsonb_build_array({}) {} WHERE k.value<>'null'::jsonb AND (NOT({}) OR {})").format(
                sql.Literal(meta['relation']),value,base,valid,missing),
                'company_value_reference_issue',model=model,table=table,field=field)

    def run(self, successful, constraints):
        e = self.e
        for model in sorted(successful):
            table = e.target[model]['table']
            for field, meta in e.target[model]['fields'].items():
                if not meta.get('store') or field not in e.physical.get(table,{}):
                    continue
                if meta.get('company_dependent'):
                    self.company_values(model,table,field,meta)
                    continue
                if meta.get('type')=='many2one' and meta.get('relation'):
                    self.reference(model,table,field,meta['relation'])
                elif meta.get('type')=='reference':
                    self.dynamic(model,table,field)
                elif meta.get('type')=='many2one_reference':
                    self.dynamic(model,table,field,meta.get('model_field'))
            def hints_for(category):
                configured=e.conversions.get(category,{})
                configured=configured.get(model,{}) if isinstance(configured,dict) else {}
                if not isinstance(configured,dict):
                    self.add('invalid_audit_hint',model=model,category=category)
                    return {}
                return configured
            hints={**hints_for('polymorphic'),**hints_for('reference_audit_hints')}
            for field, discriminator in hints.items():
                if isinstance(field,str) and isinstance(discriminator,str) and field in e.physical[table]:
                    self.dynamic(model,table,field,discriminator)
            integer_hints={**hints_for('integer_links'),**hints_for('integer_reference_audit_hints')}
            for field, related in integer_hints.items():
                if isinstance(field,str) and isinstance(related,str) and field in e.physical[table]:
                    self.reference(model,table,field,related)
            self.collect(sql.SQL('SELECT s.res_id,s.model,jsonb_build_array(s.module,s.name) '
                'FROM {} s JOIN public.ir_model_data t USING(module,name) WHERE s.model={} '
                "AND s.module<>'__export__' AND t.model<>s.model").format(
                    sql.Identifier('prepared_migration_source','ir_model_data'),sql.Literal(model)),
                'xmlid_model_conflict',model='ir.model.data',table='ir_model_data')
        for plan in e.relations:
            owner=plan['source']['model']
            related=plan['source']['related']
            self.reference(owner,plan['table'],plan['columns'][0],owner)
            self.reference(owner,plan['table'],plan['columns'][1],related)
        if 'ir_attachment' in e.physical:
            e.execute(sql.SQL('SELECT DISTINCT t.res_model FROM public.ir_attachment t JOIN {} m '
                'ON m.target_id=t.id WHERE t.res_model IS NOT NULL').format(sql.Identifier(META,'attachment_map')))
            for (related,) in e.cr.fetchall():
                if related not in e.custom_models:
                    self.reference('ir.attachment','ir_attachment','res_id',related,
                        condition=sql.SQL('s.res_model={} AND s.id IN (SELECT target_id FROM {})').format(
                            sql.Literal(related),sql.Identifier(META,'attachment_map')))
        # Prepared incoming references are inspected, never rewritten.
        for model,meta in e.target.items():
            if model in e.custom_models or meta['table'] not in e.physical:
                continue
            for field,info in meta['fields'].items():
                if field in e.physical[meta['table']] and info.get('store') and info.get('relation') in e.custom_models:
                    self.reference(model,meta['table'],field,info['relation'])
            if {'res_id','res_model'} <= e.physical[meta['table']].keys():
                self.dynamic(model,meta['table'],'res_id','res_model',incoming=True)
        self.foreign_keys(constraints)

    def count(self):
        self.e.execute(sql.SQL('SELECT count(*) FROM {} WHERE attempt=%s').format(
            sql.Identifier(META,'relationship_issue')),[self.attempt])
        return self.e.cr.fetchone()[0]

    def write(self, result):
        e = self.e
        e.execute(sql.SQL("SELECT detail->>'kind',count(*) FROM {} WHERE attempt=%s "
                         "GROUP BY detail->>'kind' ORDER BY 1").format(sql.Identifier(META,'relationship_issue')),[self.attempt])
        counts = dict(e.cr.fetchall())
        summary = dict(policy=RawReferencePolicy.name,attempt=self.attempt,counts=counts,total=sum(counts.values()),
                       status=result['status'],result=result)
        save_json(e.stage/'relationship_report.json',summary)
        details=e.stage/'relationship_issues.jsonl'
        temporary=details.with_suffix('.jsonl.tmp')
        with open(temporary,'w',encoding='utf-8',opener=lambda p,f:os.open(p,f,0o600)) as out:
            cursor=e.con.cursor(name='export_issues_'+uuid.uuid4().hex[:12])
            try:
                cursor.execute(sql.SQL('SELECT detail FROM {} WHERE attempt=%s ORDER BY issue_id').format(
                    sql.Identifier(META,'relationship_issue')),[self.attempt])
                for (detail,) in cursor:
                    out.write(dumps(detail)+'\n')
            finally:
                cursor.close()
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary,details)
        staging=e.stage/'staging.json'
        from common import loads
        staged=loads(staging.read_text()).get('counts',{}) if staging.exists() else {}
        text=['# Migration report','',f'Status: **{result["status"]}**',
              f'Relationship policy: `{RawReferencePolicy.name}`','',
              '## Operations','',f'- Staging: {dumps(staged)}',
              f'- Successful custom tables: {len(result["successful_models"])}',
              f'- Operations committed this attempt: {len(result["committed"])}',
              f'- Operations skipped: {len(result["skipped"])}',
              f'- Technical operation failures: {len(result["failed_tables"])}',
              f'- Foreign keys left unapplied: {len(result["failed_foreign_keys"])}','',
              '## Relationship findings','']
        text.extend(f'- {kind}: {count}' for kind,count in counts.items())
        text.extend(['','## Identity comparisons',''])
        for table,check in getattr(e,'identity_report',{}).items():
            text.append(f'- {table}: {check["checked_count"]} checked; {check["skipped_count"]} below 7 skipped; '
                        f'{check["missing_count"]} missing (report only).')
        text.extend(['','## Details','',
            '- `relationship_issues.jsonl`: every recorded relationship finding, without truncation.',
            '- `relationship_report.json`: machine-readable complete summary.',
            '- `failed_tables.json`: technical operation failures.',
            '- `failed_foreign_keys.json`: all unapplied constraints and restoration SQL.',
            '', 'Standard primary keys and prepared incoming references are preserved. '
            'User/partner IDs below 7 are excluded from identity comparisons; their stored references are unchanged.',''])
        path=e.stage/'migration_report.md'
        with open(path,'w',encoding='utf-8',opener=lambda p,f:os.open(p,f,0o600)) as out:
            out.write('\n'.join(text))
        e.con.commit()
