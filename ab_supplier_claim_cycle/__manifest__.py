{
    'name': 'Supplier Claim Cycle',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'mail', 'ab_supplier', 'ab_costcenter'],
    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'views/menus.xml',
        'views/ab_supplier_claim_cycle.xml',
        'data/install_extensions.xml',

    ],
    'installable': True,


}
