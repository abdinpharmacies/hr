{
    'name': 'Abdin Sales Promo',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': False,
    'depends': ['ab_sales', 'ab_promo_program'],
    'data': [
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_sales_header_promo_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_sales_promo/static/src/pos/**/*.js',
            'ab_sales_promo/static/src/pos/**/*.xml',
            'ab_sales_promo/static/src/pos/**/*.scss',
        ],
    },
    'installable': True,
}
