{
    'name': 'Abdin Product Source',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'depends': ['base', 'ab_taxes', 'ab_product'],
    'data': [
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_product_source.xml',
    ],
    'installable': True,
}
