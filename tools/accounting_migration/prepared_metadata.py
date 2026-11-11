"""Read-only Odoo 19 registry metadata/smoke subprocess; no installs or upgrades."""
import argparse
import json
import fnmatch
import sys
from pathlib import Path
from common import MigrationError, save_json, loads


def wait_for_import(rollback, clear_cache, backend_pid, input_stream=None, output_stream=None):
    """Wait with an open connection, but no transaction or cached record values."""
    rollback()
    clear_cache()
    source=sys.stdin if input_stream is None else input_stream
    output=sys.stdout if output_stream is None else output_stream
    print('@PREPARED_READY@'+json.dumps({'pid':backend_pid()}),file=output,flush=True)
    if source.readline().strip()!='GO':
        raise MigrationError('Smoke worker cancelled before exclusive access')
    clear_cache()


def main():
    p = argparse.ArgumentParser()
    for name in ('config', 'database', 'server', 'output'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--manifest')
    p.add_argument('--wait',action='store_true')
    p.add_argument('--rules',default=str(Path(__file__).with_name('prepared_rules.json')))
    args = p.parse_args()
    from worker import isolate, registry_metadata
    isolate(args.config, args.database)
    import psycopg2
    original = psycopg2.connect
    def read_only(*a, **kw):
        con = original(*a, **kw)
        con.set_session(readonly=True)
        return con
    psycopg2.connect = read_only
    sys.path.insert(0, args.server)
    import odoo
    from odoo.tools import config
    config.parse_config(['-c', args.config, '-d', args.database, '--no-http',
                         '--max-cron-threads=0', '--logfile='])
    import logging
    logging.getLogger('odoo.sql_db').disabled = True
    odoo.modules.module.initialize_sys_path()
    registry = odoo.modules.registry.Registry.new(args.database, update_module=False)
    with registry.cursor() as cr:
        env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {'active_test': False, 'lang': 'en_US'})
        metadata = registry_metadata(env)
        manager_rules=loads(Path(args.rules).read_text()).get('branch_manager_xmlids',{})
        for pattern,xmlids in manager_rules.items():
            if not any(fnmatch.fnmatchcase(name,pattern) for name in metadata):
                continue
            for xmlid in xmlids:
                module,name=xmlid.split('.',1)
                if not env['ir.model.data'].search_count([('module','=',module),('name','=',name),('model','=','res.groups')]):
                    raise MigrationError('Configured branch manager group is absent: '+xmlid)
        if args.manifest:
            if args.wait:
                wait_for_import(cr.rollback,lambda:env.invalidate_all(flush=False),cr._cnx.get_backend_pid)
                env=odoo.api.Environment(cr,odoo.SUPERUSER_ID,{'active_test':False,'lang':'en_US'})
            from psycopg2 import sql
            manifest = loads(Path(args.manifest).read_text())
            for model in manifest['selected']:
                print('Read-only ORM smoke: '+model,file=sys.stderr,flush=True)
                cr.execute(sql.SQL('SELECT id FROM {} ORDER BY id LIMIT 3').format(
                    sql.Identifier(metadata[model]['table'])))
                records = env[model].browse([r[0] for r in cr.fetchall()])
                records.read(['display_name'])
            # Exercise actual ACLs and branch rules, including an inherited admin.
            checked = []
            for model, field in {'ab_hr_department': 'store_id', 'ab_store': 'id'}.items():
                if model not in metadata:
                    continue
                if model == 'ab_store':
                    continue
                if not {'user_id', field}.issubset(metadata[model]['fields']):
                    continue
                departments = env[model].search([('user_id', '!=', False)], limit=8)
                for department in departments:
                    user = department.user_id
                    if not user.active or user.has_group('base.group_system'):
                        continue
                    for name in manifest['selected']:
                        managers={xmlid for pattern,xmlids in manager_rules.items() if fnmatch.fnmatchcase(name,pattern) for xmlid in xmlids}
                        if any(user.has_group(xmlid) for xmlid in managers):
                            continue
                        fields = metadata[name]['fields']
                        branch = next((f for f in ('store_id', 'branch_id') if f in fields and
                                       fields[f].get('relation') == 'ab_store' and fields[f].get('store')), None)
                        if not branch or not env[name].with_user(user).has_access('read'):
                            continue
                        other = env[name].with_user(user).search_count([
                            (branch, '!=', False), (branch, '!=', department[field].id)])
                        if other:
                            raise MigrationError(f'Branch visibility requires review: {name}')
                        checked.append(name)
            save_json(Path(args.output), {'passed': True, 'smoke_models': manifest['selected'],
                                         'branch_models_checked': sorted(set(checked))})
        else:
            save_json(Path(args.output), metadata)
        cr.rollback()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        message=str(exc) if isinstance(exc,MigrationError) else type(exc).__name__
        print(f'Metadata/smoke worker failed: {message}', file=sys.stderr)
        sys.exit(2)
