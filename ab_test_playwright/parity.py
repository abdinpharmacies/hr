import copy
import hashlib
import json


CONTRACT_ALIASES = ['contract25', 'contract0', 'contract100', 'contractPromo']


def pos_cases(suite):
    products = {product['id']: alias for alias, product in zip(['base', 'promo'], suite['records']['products'])}
    contracts = dict(zip(suite['records']['contract_ids'], CONTRACT_ALIASES))

    def expected(values):
        result = copy.deepcopy(values)
        if 'contract_id' in result:
            value = result.pop('contract_id')
            result['contract'] = contracts[value] if value else None
        if 'applied_promotion_ids' in result:
            ids = result.pop('applied_promotion_ids')
            if ids not in ([], [suite['records']['promotion_id']]):
                raise ValueError('POS reference contains an unexpected promotion')
            result['promotion'] = bool(ids)
        return result

    result = []
    for case in suite['cases']:
        steps = []
        for step in case['steps']:
            converted = {'action': step['action']}
            if 'product_id' in step:
                converted['product'] = products[step['product_id']]
            if 'id' in step and step['action'] in ('search_product', 'add_product'):
                converted['product'] = products[step['id']]
            if step['action'] == 'select_contract':
                converted['contract'] = contracts[step['id']]
            if 'quantity' in step:
                converted['quantity'] = step['quantity']
            if isinstance(step.get('expected'), dict):
                converted['expected'] = expected(step['expected'])
            steps.append(converted)
        result.append({'id': case['id'], 'name': case['name'],
                       'lines': [{'product': products[line['product_id']], 'qty': line['qty']} for line in case['lines']],
                       'expected': expected(case['expected']), 'steps': steps})
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def case_contracts(cases):
    return {case['id']: digest({key: case[key] for key in ('lines', 'expected', 'steps')}) for case in cases}


def reference_contract(suite, actions):
    contracts = {alias: {key: value for key, value in fixture['values'].items() if key != 'name'}
                 for alias, fixture in zip(CONTRACT_ALIASES, suite['fixtures']['contracts'])}
    return {'actions': actions, 'cases': case_contracts(pos_cases(suite)), 'contracts': contracts,
            'promotion': {**suite['fixtures']['promotion']['required_values'],
                          **{key: value or False for key, value in suite['fixtures']['promotion']['values'].items()}},
            'out_of_stock': suite['out_of_stock'],
            'unit_prices': {alias: product['unit_price'] for alias, product in zip(['base', 'promo'], suite['records']['products'])}}
