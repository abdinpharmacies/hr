"""Public write boundaries: standard business rows and definitions are immutable."""
from psycopg2 import sql
from common import MigrationError


def custom_name(name):
    return isinstance(name,str) and name.startswith('ab')


class StandardProtection:
    technical_data={'ir_attachment':{'attachments'},'ir_model_data':{'xmlids'}}

    def __init__(self, engine):
        self.e=engine
        standard={meta['table'] for model,meta in engine.target.items() if not custom_name(model)}
        # Protect core identities even if malformed metadata omits their models.
        standard.update(('res_users','res_partner','res_company','res_groups','ir_model','ir_model_fields',
                         'res_groups_users_rel','ir_attachment','ir_model_data'))
        standard_relations=set()
        for model,meta in engine.target.items():
            if custom_name(model):
                continue
            for field in meta['fields'].values():
                table=field.get('relation_table')
                if field.get('type')=='many2many' and table and not custom_name(field.get('module')):
                    standard_relations.add(table)
        candidates={engine.target[m]['table'] for m in engine.selected}
        relations={p['table'] for p in engine.relations}
        self.mutable=(candidates|relations)-standard-standard_relations

    def can_alter(self, table):
        return table in self.mutable

    def require_write(self, table, operation):
        if table in self.mutable:
            return
        if operation in self.technical_data.get(table,set()):
            return
        raise MigrationError(f'Protected standard/public table cannot be modified: {table} ({operation})')

    def protect_incoming(self, constraints):
        """Any existing protected child row must survive parent replacement."""
        blocked={}
        e=self.e
        for item in constraints:
            item['protected']=not self.can_alter(item['table'])
            if not item['protected'] or item['referenced_table'] not in self.mutable:
                continue
            if item['table'] not in e.physical or item['referenced_table'] not in e.physical:
                continue
            pairs=list(zip(item['columns'],item['referenced_columns']))
            join=sql.SQL(' AND ').join(sql.SQL('s.{}=t.{}').format(sql.Identifier(a),sql.Identifier(b)) for a,b in pairs)
            e.execute(sql.SQL('SELECT EXISTS(SELECT 1 FROM public.{} s JOIN public.{} t ON {})').format(
                sql.Identifier(item['table']),sql.Identifier(item['referenced_table']),join))
            if e.cr.fetchone()[0]:
                blocked.setdefault(item['referenced_table'],[]).append(dict(
                    table=item['table'],constraint=item['constraint'],reason='Protected incoming reference must remain unchanged'))
        return blocked
