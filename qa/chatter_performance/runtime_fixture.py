import argparse
import ast
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.database.startswith('callcenter_timing_') or args.output.exists():
        parser.error('Use a disposable timing database and a new private output path')
    os.umask(0o077)
    password = secrets.token_urlsafe(24)
    sys.path.insert(0, '/opt/odoo19/server')
    import odoo.init
    from odoo import api, fields, SUPERUSER_ID
    from odoo.modules import initialize_sys_path
    from odoo.modules.registry import Registry
    from odoo.service import server
    from odoo.tools import config
    config.parse_config(['-c', args.config, '-d', args.database, '--no-http',
        '--http-port=5085', '--gevent-port=5086', '--workers=0', '--max-cron-threads=0'])
    initialize_sys_path()
    server.load_server_wide_modules()
    if config['db_name'] not in ([args.database], args.database):
        raise ValueError('The disposable database must be selected exactly')
    registry = Registry(args.database)
    with registry.cursor() as cursor:
        environment = api.Environment(cursor, SUPERUSER_ID, {})
        if environment['res.users'].search_count([('login', '=', 'workspace-agent')]):
            raise ValueError('The synthetic fixture already exists')
        root = Path(__file__).resolve().parents[2]
        source = ast.parse((root / 'ab_crm_sales_workspace/tests/test_workspace.py').read_text())
        test_class = next(node for node in source.body
            if isinstance(node, ast.ClassDef) and node.name == 'TestWorkspace')
        setup = next(node for node in test_class.body
            if isinstance(node, ast.FunctionDef) and node.name == 'setUpClass')
        setup.decorator_list = []
        setup.body = setup.body[1:]
        module = ast.Module(body=[setup], type_ignores=[])
        ast.fix_missing_locations(module)
        namespace = {'fields': fields}
        exec(compile(module, '<synthetic-fixture>', 'exec'), namespace)
        fixture = SimpleNamespace(env=environment)
        namespace['setUpClass'](fixture)
        gateway = environment['ab_crm_messaging_api'].with_user(fixture.service)
        result = gateway.receive_event('workspace-bot', '900000234', {
            'id': 'initial', 'sender': '12345', 'body': 'Synthetic initial',
            'timestamp': '2026-01-01 12:00:00', 'unsupported': False, 'source_digest': 'b' * 64})
        conversation = environment['ab_crm_message'].browse(result['message_id']).conversation_id
        agents = []
        for index in range(10):
            if index == 0:
                user, employee, profile = fixture.staff, fixture.employee, fixture.profile
            else:
                user = fixture.staff.copy({'name': f'Timing Agent {index}', 'login': f'timing-agent-{index}'})
                employee = fixture.employee.copy({'name': f'Timing Employee {index}',
                    'barcode': f'TIMING-{index}', 'user_id': user.id})
                profile = fixture.profile.copy({'employee_id': employee.id, 'pos_pin': '1234'})
                fixture.branch.write({'user_ids': [fields.Command.link(user.id)]})
            user.password = password
            session = environment['ab_crm_chatter_api'].with_user(user).employee_login(
                profile.id, '1234', f'timing-{index}')
            if 'token' not in session:
                raise ValueError('Synthetic employee login failed')
            agents.append({'login': user.login, 'session': session})
        key = environment['res.users.apikeys'].with_user(fixture.service).sudo()._generate(
            'rpc', 'Synthetic timing', datetime.now() + timedelta(hours=4))
        cursor.commit()
        args.output.write_text(json.dumps({'database': args.database, 'password': password,
            'webhook_secret': secrets.token_urlsafe(24), 'agents': agents,
            'odoo_key': key, 'conversation_id': conversation.id}))
    print('Committed synthetic fixture with ten authorized agents')


if __name__ == '__main__':
    main()
