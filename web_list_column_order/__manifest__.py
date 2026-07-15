{
    'name': 'Web List Column Order',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Tools',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'summary': 'Per-user drag-to-reorder column ordering for list views.',
    'depends': ['web'],
    'data': [
        'security/record_rules.xml',
        'security/ir.model.access.csv',
    ],
    'assets': {
        'web.assets_backend': [
            'web_list_column_order/static/src/js/list_column_order.js',
            'web_list_column_order/static/src/js/list_column_order_cog_menu.js',
            'web_list_column_order/static/src/xml/list_column_order_cog_menu.xml',
            'web_list_column_order/static/src/scss/list_column_order.scss',
        ],
    },
    'installable': True,
}
