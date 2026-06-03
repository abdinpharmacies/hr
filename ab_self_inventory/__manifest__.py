{
    'name': 'Self Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Alhassan Hossny',
    'application': True,
    'depends': ['base', 'ab_eplus_connect', 'ab_store', 'ab_product', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/self_inventory_request_views.xml',
        'views/self_inventory_process_views.xml',
    ],
    'installable': True,
}
