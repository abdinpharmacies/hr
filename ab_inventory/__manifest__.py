{
    'name': 'Abdin Inventory',
    'license': 'LGPL-3',
    'depends': ['base', 'ab_product_source', 'ab_store'],
    'category': 'AbdinSupplyChain',
    'data': ['security/ir.model.access.csv',
             'views/menus.xml',
             'views/ab_inventory_header.xml',
             'views/ab_product_source_inherit.xml',
             'views/ab_product_source_pending.xml',
             ],
}
