import copy
import getpass
import os


class SetupCancelled(Exception):
    pass


def read_credentials(suite, interactive=True, read_secret=getpass.getpass, environ=None):
    environ = os.environ if environ is None else environ
    values = {}
    for field, setting, label in [('password', 'password_env', 'Odoo password'), ('pin', 'employee_pin_env', 'Employee PIN')]:
        value = environ.get(suite['credentials'][setting])
        while not value:
            if not interactive:
                raise ValueError(f"Set {suite['credentials'][setting]} when unattended")
            try:
                value = read_secret(label + ': ')
            except (EOFError, KeyboardInterrupt):
                raise SetupCancelled('Credential entry cancelled') from None
        values[field] = value
    return values


def ask(label, default=None, validate=None, interactive=True, read=input, write=print):
    if not interactive:
        if default is None or default == '':
            raise ValueError(f'{label} is required when unattended; supply the corresponding option or suite value')
        return validate(default) if validate else default
    while True:
        try:
            answer = read(label + (f' [{default}]' if default not in (None, '') else '') + ': ').strip()
        except (EOFError, KeyboardInterrupt):
            raise SetupCancelled('Setup cancelled; no test run started') from None
        if answer.lower() in ('q', 'quit'):
            raise SetupCancelled('Setup cancelled; no test run started')
        value = answer or default
        if value is None or value == '':
            write('A value is required. Enter q to cancel.')
            continue
        try:
            return validate(value) if validate else value
        except ValueError as error:
            write(str(error))


def pick(label, find, current=None, interactive=True, read=input, write=print):
    existing = find(str(current)) if current else []
    default = current if len(existing) == 1 else None
    if not interactive:
        if default is None:
            raise ValueError(f'{label} is missing or invalid in the supplied suite; run interactively to select it')
        return existing[0]
    choices = find('')
    write('\n' + label)
    for choice in choices:
        write(f"  {choice['id']}: {choice['label']}")
    if default is None and len(choices) == 1:
        default = choices[0]['id']
    while True:
        text = ask('Record ID or search text', default, interactive=True, read=read, write=write)
        matches = find(str(text))
        if str(text).isdigit() and len(matches) == 1:
            return matches[0]
        if not matches:
            write('No matching record. Try another ID or search, or enter q to cancel.')
        else:
            for choice in matches:
                write(f"  {choice['id']}: {choice['label']}")


def resolve_suite(env, suite, database, interactive=True, preparation=False, read=input, write=print):
    from odoo import fields

    result = copy.deepcopy(suite)
    records = result['records']
    if not interactive and result.get('qa_database') != database:
        raise ValueError('qa_database in the unattended suite must match --db')
    result['qa_database'] = database
    login_default = result['credentials'].get('login')
    while True:
        login = ask('Odoo login', login_default, interactive=interactive, read=read, write=write)
        user = env['res.users'].search(fields.Domain('login', '=', login) & fields.Domain('active', '=', True), limit=1)
        if user and (preparation or user.has_group('ab_sales.group_call_center')):
            break
        message = 'Login is inactive, missing, or does not have Callcenter access.'
        if not interactive:
            raise ValueError(message)
        write(message)
        login_default = None
    result['credentials']['login'] = login
    records['user_id'] = user.id

    def select(label, model, domain, current=None, describe=None):
        def find(text):
            extra = fields.Domain.TRUE
            if text:
                extra = fields.Domain('id', '=', int(text)) if text.isdigit() else fields.Domain('display_name', 'ilike', text)
            rows = env[model].search(domain & extra, order='id', limit=12)
            return [{'id': row.id, 'label': describe(row) if describe else row.display_name, 'record': row} for row in rows]
        return pick(label, find, current, interactive, read, write)['record']

    profile_domain = fields.Domain('pos_allow_login', '=', True)
    if not preparation:
        profile_domain &= fields.Domain('employee_id.name', 'ilike', '[TEST]')
    profile = select('Employee / POS access profile', 'ab_employee_access', profile_domain,
                     records.get('employee_access_id'),
                     lambda row: f'{row.employee_id.display_name} (employee {row.employee_id.id}, profile {row.id})')
    records.update(employee_id=profile.employee_id.id, employee_access_id=profile.id)
    store_domain = fields.Domain('allow_sale', '=', True)
    if profile.pos_allowed_store_ids:
        store_domain &= fields.Domain('id', 'in', profile.pos_allowed_store_ids.ids)
    if not user.has_group('base.group_system'):
        store_domain &= fields.Domain('pos_service_user_id', '=', False) | fields.Domain('pos_service_user_id', '=', user.id)
    if not preparation:
        connections = env['ab_sales_branch_rpc_config'].search(
            fields.Domain('active', '=', True) & fields.Domain('enrollment_state', '=', 'ready') & fields.Domain('can_post', '=', True))
        store_domain &= fields.Domain('id', 'in', connections.store_id.ids)
    store = select('Branch', 'ab_store', store_domain, records.get('store_id'),
                   lambda row: f'{row.display_name} (code {row.code}, external serial {row.eplus_serial})')
    if store.id != records.get('store_id'):
        records.update(store_code=store.code, store_eplus_serial=store.eplus_serial)
    else:
        records['store_code'] = records.get('store_code') or store.code
        records['store_eplus_serial'] = records.get('store_eplus_serial') or store.eplus_serial
    records['store_id'] = store.id
    labelled = fields.Domain.TRUE if preparation else fields.Domain('name', 'ilike', '[TEST]')
    customer = select('Customer', 'ab_customer', labelled, records.get('customer_id'))
    if customer.id != records.get('customer_id') or not records.get('customer_code'):
        records['customer_code'] = customer.code
    records['customer_id'] = customer.id
    for alias, product in records['products'].items():
        domain = fields.Domain('active', '=', True)
        if not preparation:
            domain &= fields.Domain('product_card_id.name', 'ilike', '[TEST]')
            domain &= fields.Domain('default_price', '=', product['unit_price'])
            domain &= fields.Domain('product_card_id.origin', '=', product['origin'])
        row = select(f"Product {alias} (expected price {product['unit_price']})", 'ab_product', domain, product.get('id'),
                     lambda row: f'{row.name} (code {row.code}, price {row.default_price})')
        values = {'code': row.code, 'eplus_serial': row.eplus_serial, 'uom_id': row.uom_id.id}
        for key, value in values.items():
            if row.id != product.get('id') or not product.get(key):
                product[key] = value
        product['id'] = row.id
    selected_contracts = []
    for alias, contract in records['contracts'].items():
        domain = labelled & fields.Domain('id', 'not in', selected_contracts)
        if not preparation:
            for field, value in result['fixtures']['contracts'][alias].items():
                domain &= fields.Domain(field, '=', value)
            domain &= fields.Domain('allowed_store_ids', '=', False) | fields.Domain('allowed_store_ids', 'in', store.ids)
        row = select(f'Contract {alias}', 'ab_contract', domain, contract.get('id'))
        contract['id'] = row.id
        selected_contracts.append(row.id)
    promotion_domain = labelled & fields.Domain('active', '=', True)
    if not preparation:
        for field, value in result['fixtures']['promotion'].items():
            promotion_domain &= fields.Domain(field, '=', value)
        promotion_domain &= fields.Domain('product_ids', 'in', [records['products']['promo']['id']])
        promotion_domain &= fields.Domain('product_ids', 'not in', [records['products']['base']['id']])
        promotion_domain &= fields.Domain('store_ids', '=', False) | fields.Domain('store_ids', 'in', store.ids)
        promotion_domain &= fields.Domain('partner_ids', '=', False) | fields.Domain('partner_ids', 'in', customer.ids)
    promotion = select('Promotion', 'ab_promo_program', promotion_domain, records.get('promotion_id'))
    records['promotion_id'] = promotion.id
    return result
