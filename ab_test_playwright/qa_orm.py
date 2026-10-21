import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import getpass
import os
from pathlib import Path
import sys

from common import ROOT, load_suite, positive_id, private_json


CONTRACT_FIELDS = {
    'active', 'paid_percentage', 'paid_amount', 'max_bill_value', 'discount_percentage_rule',
    'allow_total_invoice_discount', 'total_invoice_discount_source', 'local_product_discount',
    'imported_product_discount', 'local_made_product_discount', 'special_import_product_discount',
    'other_product_discount', 'investment_product_discount', 'allow_promotions',
}


def configured_records(suite):
    records = suite['records']
    for key in ['user_id', 'employee_id', 'employee_access_id', 'store_id', 'customer_id', 'promotion_id']:
        positive_id(records[key], key)
    for kind in ['contracts', 'products']:
        ids = [positive_id(value['id'], key) for key, value in records[kind].items()]
        if len(set(ids)) != len(ids):
            raise ValueError(f'{kind} must reference distinct QA records')
    for key, product in records['products'].items():
        positive_id(product['uom_id'], key + '.uom_id')
        if not product['code'] or not product['eplus_serial']:
            raise ValueError('Configure product codes and external serials')
    if not suite['credentials']['login'] or not records['store_code'] or not records['customer_code']:
        raise ValueError('Configure login, store code, and customer code')
    return records


@contextmanager
def environment(config, database, readonly=True):
    sys.path.insert(0, '/opt/odoo19/server')
    import odoo
    from odoo import api
    from odoo.modules.registry import Registry

    odoo.tools.config.parse_config([
        '-c', str(config), '-d', database, '--no-http', '--workers=0', '--max-cron-threads=0',
        '--logfile=/tmp/callcenter-playwright-orm.log', '--data-dir=/tmp/callcenter-playwright-odoo',
    ])
    odoo.netsvc.init_logger()
    with Registry(database).cursor() as cursor:
        if readonly:
            cursor.execute('SET TRANSACTION READ ONLY')
        env = api.Environment(cursor, odoo.SUPERUSER_ID, {'lang': 'en_US'})
        try:
            yield env
        finally:
            cursor.rollback()


def selected(env, model, identifier):
    record = env[model].browse(identifier).exists()
    if len(record) != 1:
        raise ValueError(f'Missing selected QA record: {model} {identifier}')
    return record


def fixture_records(env, suite):
    records = suite['records']
    user = selected(env, 'res.users', records['user_id'])
    store = selected(env, 'ab_store', records['store_id'])
    employee = selected(env, 'ab_hr_employee', records['employee_id'])
    customer = selected(env, 'ab_customer', records['customer_id'])
    promotion = selected(env, 'ab_promo_program', records['promotion_id'])
    contracts = {key: selected(env, 'ab_contract', value['id']) for key, value in records['contracts'].items()}
    products = {key: selected(env, 'ab_product', value['id']) for key, value in records['products'].items()}
    return user, store, employee, customer, promotion, contracts, products


def inspect(env, suite, require_test_context=False):
    from odoo import fields

    records = suite['records']
    user, store, employee, customer, promotion, contracts, products = fixture_records(env, suite)
    profile = selected(env, 'ab_employee_access', records['employee_access_id'])
    if not user.active or user.login != suite['credentials']['login']:
        raise ValueError('Selected Odoo login is inactive or changed')
    if profile.employee_id != employee or not profile.pos_allow_login:
        raise ValueError('Employee/profile identity differs or POS login is disabled')
    permissions = profile._effective_pos_permissions()
    if not permissions.get('allow_pos_screen') or not permissions.get('allow_sale', True):
        raise ValueError('Selected employee role does not permit POS sales')
    if not profile._is_store_allowed_for_pos(store):
        raise ValueError('Selected employee is not allowed at this store')
    if store.code != records['store_code'] or store.eplus_serial != records['store_eplus_serial'] or customer.code != records['customer_code']:
        raise ValueError('Store/customer identity differs from the configured suite')
    if store.pos_service_user_id and store.pos_service_user_id != user and not user.has_group('base.group_system'):
        raise ValueError('Selected branch belongs to another Odoo service user')
    marked = [employee, customer, promotion, *contracts.values()]
    if require_test_context:
        marked.extend([store, user.partner_id])
    if any(not record.name.startswith('[TEST] ') for record in marked):
        raise ValueError('Select explicitly labelled [TEST] QA records; preparation is never automatic')
    for key, product in products.items():
        expected = records['products'][key]
        if not product.product_card_id.name.startswith('[TEST] '):
            raise ValueError('Product card is not labelled [TEST]')
        if (product.code != expected['code'] or product.eplus_serial != expected['eplus_serial']
                or product.uom_id.id != expected['uom_id'] or product.product_card_id.origin != expected['origin']
                or abs(product.default_price - expected['unit_price']) > 0.000001):
            raise ValueError(f'Product {key} identity, price, origin, or unit drifted; review the suite')
        if product.uom_id.factor != 1.0:
            raise ValueError('Reference scenarios require the configured default unit factor to be 1')
    for key, contract in contracts.items():
        for field, expected in suite['fixtures']['contracts'][key].items():
            if contract[field] != expected:
                raise ValueError(f'Contract {key}.{field} differs from the scenario precondition')
        if contract.allowed_store_ids and store not in contract.allowed_store_ids:
            raise ValueError('Contract is not allowed at the selected store')
        if env['ab_contract_product_origin'].search_count(
                fields.Domain('contract_id', '=', contract.id)
                & fields.Domain('product_card_id', 'in', [product.product_card_id.id for product in products.values()])):
            raise ValueError('Product-specific contract rules conflict with the reference scenarios')
    for field, expected in suite['fixtures']['promotion'].items():
        if promotion[field] != expected:
            raise ValueError(f'Promotion {field} differs from the scenario precondition')
    if not promotion.active or products['promo'] not in promotion.product_ids or products['base'] in promotion.product_ids:
        raise ValueError('Promotion product eligibility differs from the reference scenarios')
    if promotion.store_ids and store not in promotion.store_ids:
        raise ValueError('Promotion is not allowed at the selected store')
    if promotion.partner_ids and customer not in promotion.partner_ids:
        raise ValueError('Promotion is not allowed for the selected customer')
    replica = env['ab_replica_db'].get_current_from_config()
    if promotion.replica_db_ids and (not replica or replica not in promotion.replica_db_ids):
        raise ValueError('Promotion is not allowed for this Callcenter replica')
    connection = env['ab_sales_branch_rpc_config'].search(
        fields.Domain('store_id', '=', store.id) & fields.Domain('active', '=', True))
    if len(connection) != 1 or connection.enrollment_state != 'ready' or not connection.can_post:
        raise ValueError('QA Branch connection must be verified and permit posting')
    if not user.has_group('ab_sales.group_call_center'):
        raise ValueError('Selected Odoo user must have the Callcenter role')
    action = env.ref('ab_sales.ab_sales_pos_action')
    return {
        'action_id': action.id,
        'store': {'id': store.id, 'name': store.display_name},
        'customer': {'id': customer.id, 'name': customer.display_name},
        'employee': {'id': employee.id, 'name': employee.display_name},
        'promotion': {'id': promotion.id, 'name': promotion.name},
        'contracts': {key: {'id': record.id, 'name': record.display_name} for key, record in contracts.items()},
        'products': {key: {'id': record.id, 'name': record.name} for key, record in products.items()},
        'branch_database': connection.rpc_db,
        'branch_store_serial': store.eplus_serial,
    }


def prepare(env, suite, operation, apply=False, password=None, backup_dir=None):
    from odoo import fields

    user, store, employee, customer, promotion, contracts, products = fixture_records(env, suite)
    records = suite['records']
    profile = selected(env, 'ab_employee_access', records['employee_access_id'])
    if user.login != suite['credentials']['login'] or profile.employee_id != employee:
        raise ValueError('Selected user or employee profile identity changed')
    if store.code != records['store_code'] or store.eplus_serial != records['store_eplus_serial'] or customer.code != records['customer_code']:
        raise ValueError('Selected branch or customer identity changed')
    for key, product in products.items():
        expected = records['products'][key]
        if product.code != expected['code'] or product.eplus_serial != expected['eplus_serial']:
            raise ValueError('Selected product identity changed')
    changes = []
    if operation == 'labels':
        targets = [user.partner_id, store, employee, customer, promotion, *contracts.values(),
                   *(product.product_card_id for product in products.values())]
        if len({record.product_card_id.id for record in products.values()}) != len(products):
            raise ValueError('Test products must have separate cards')
        for product in products.values():
            if env['ab_product'].search_count(fields.Domain('product_card_id', '=', product.product_card_id.id)) != 1:
                raise ValueError('Refusing to relabel a card shared by other products')
        seen = set()
        for record in targets:
            identity = (record._name, record.id)
            if identity in seen:
                continue
            seen.add(identity)
            if not record.name.startswith('[TEST] '):
                changes.append((record, {'name': '[TEST] ' + (record.name or '')}))
    else:
        for record in [promotion, *contracts.values()]:
            if not record.name.startswith('[TEST] '):
                raise ValueError('Scenario preparation requires existing [TEST] records')
        if products['promo'] not in promotion.product_ids or products['base'] in promotion.product_ids:
            raise ValueError('Configure promotion membership manually; preparation does not broaden eligibility')
        for key, record in contracts.items():
            if env['ab_contract_product_origin'].search_count(
                    fields.Domain('contract_id', '=', record.id)
                    & fields.Domain('product_card_id', 'in', [product.product_card_id.id for product in products.values()])):
                raise ValueError('Product-specific contract overrides conflict with origin discount cases')
            values = suite['fixtures']['contracts'][key]
            if set(values) != CONTRACT_FIELDS:
                raise ValueError('Unexpected or missing contract fixture fields')
            changes.append((record, {field: value for field, value in values.items() if record[field] != value}))
        allowed = {'apply_disc_on', 'fixed_price', 'rule_min_qty', 'max_repetition_per_invoice', 'rule_date_from', 'rule_date_to'}
        values = suite['fixtures']['promotion']
        if set(values) != allowed:
            raise ValueError('Unexpected promotion fixture fields')
        for field in allowed - {'rule_date_from', 'rule_date_to'}:
            if promotion[field] != values[field]:
                raise ValueError(f'Promotion {field} differs from the POS fixture precondition')
        changes.append((promotion, {field: values[field] for field in ('rule_date_from', 'rule_date_to')
                                    if promotion[field] != values[field]}))
    changes = [(record, values) for record, values in changes if values]
    backup = [{'model': record._name, 'id': record.id, 'before': record.read(list(values))[0], 'after': values}
              for record, values in changes]
    encrypted = None
    if password is not None:
        if operation != 'labels' or not apply or not password:
            raise ValueError('Password reset requires label preparation, --apply, and a nonempty password')
        rounds = max(600000, int(env['ir.config_parameter'].sudo().get_param('password.hashing.rounds', 0)))
        crypt = user._crypt_context().copy(pbkdf2_sha512__rounds=rounds)
        encrypted = crypt.hash(password)
        if not crypt.verify(password, encrypted):
            raise ValueError('Password hash verification failed')
        env.cr.execute('SELECT password FROM res_users WHERE id=%s FOR UPDATE', (user.id,))
        original = env.cr.fetchone()[0]
        backup.append({'model': 'res.users', 'id': user.id, 'before': {'password': original}, 'after': {'password': encrypted}})
    if apply:
        directory = backup_dir or ROOT / 'backups'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory.chmod(0o700)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        private_json(directory / f'{operation}-{stamp}.json', {
            'database': env.cr.dbname, 'changed_by': env.uid,
            'changed_at': datetime.now(timezone.utc).isoformat(), 'changes': backup,
        })
        for record, values in changes:
            record.with_context(tracking_disable=True).write(values)
        if encrypted:
            user._set_encrypted_password(user.id, encrypted)
            env.cr.execute('SELECT password FROM res_users WHERE id=%s', (user.id,))
            if env.cr.fetchone()[0] != encrypted:
                raise ValueError('Password update verification failed; transaction rolled back')
        env.flush_all()
        for record, values in changes:
            if any(record[field] != value for field, value in values.items()):
                raise ValueError('Fixture verification failed; transaction rolled back')
        env.cr.commit()
    return {'operation': operation, 'applied': apply, 'changed_records': len(changes),
            'password_reset': bool(encrypted), 'changes': [entry for entry in backup if 'password' not in entry['before']]}


def main(operation=None):
    parser = argparse.ArgumentParser(description='Inspect or explicitly prepare selected Callcenter QA records using Odoo ORM')
    parser.add_argument('--config', type=Path, default=ROOT.parent / 'odoo19-callcenter.conf')
    parser.add_argument('--db')
    parser.add_argument('--suite', type=Path, default=ROOT / 'sales_ui_cases.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--require-test-context', action='store_true')
    parser.add_argument('--reset-password', action='store_true')
    parser.add_argument('--password-env', default='AB_TEST_PASSWORD')
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--operation', choices=['inspect', 'labels', 'scenarios'], default=operation or 'inspect')
    args = parser.parse_args()
    if args.reset_password and (not args.apply or args.operation != 'labels'):
        parser.error('--reset-password requires --apply and label preparation')
    from terminal_setup import ask, resolve_suite
    interactive = sys.stdin.isatty()
    args.db = args.db or ask('QA database name (--db)', interactive=interactive)
    suite = load_suite(args.suite, allow_submit=True)
    if args.apply and args.operation == 'inspect':
        parser.error('Inspection cannot apply changes')
    password = None
    if args.reset_password:
        password = os.environ.get(args.password_env)
        if not password and not interactive:
            parser.error('Set the configured password environment variable when unattended')
        password = password or getpass.getpass('New Odoo test password: ')
        if not password:
            raise ValueError('A nonempty password is required')
    with environment(args.config, args.db, readonly=not args.apply) as env:
        suite = resolve_suite(env, suite, args.db, interactive, preparation=args.operation != 'inspect')
        configured_records(suite)
        result = inspect(env, suite, args.require_test_context) if args.operation == 'inspect' else prepare(
            env, suite, args.operation, args.apply, password=password, backup_dir=args.backup_dir)
    if args.output:
        private_json(args.output, result)
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
