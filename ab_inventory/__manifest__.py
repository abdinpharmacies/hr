{
    'name': 'Abdin Inventory',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base', 'ab_product_source', 'ab_store'],
    'category': 'AbdinSupplyChain',
    'data': [
        'data/inventory_action_data.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_inventory_header.xml',
        'views/ab_inventory_action.xml',
        'views/ab_product_source_inherit.xml',
        'views/ab_product_source_pending.xml',
    ],
    'installable': True,
}
