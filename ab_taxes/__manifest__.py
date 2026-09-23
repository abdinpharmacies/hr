{
    'name': 'ab_taxes',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'emadco88',
    'application': False,
    'depends': [
        'base',
    ],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/ab_taxes.xml',
        'data/taxes.xml',
    ],
    'installable': True,
    'auto_install': False,
}
