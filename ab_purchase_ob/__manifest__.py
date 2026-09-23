{
    'name': 'ab_purchase_ob',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'emadco88',
    'application': True,
    'depends': [
        'base',
        'mail',
        'ab_purchase',
        'ab_product_source',
        'ab_inventory',
    ],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/opening_balance_header.xml',
    ],
    'installable': True,
    'auto_install': False,
}
