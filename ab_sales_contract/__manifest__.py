{
    'name': 'Abdin Sales Contract',
    'application': True,
    'depends': ['ab_sales'],

    'data': [
        'security/ir.model.access.csv',
        'views/ab_sales_contract_views.xml',
        'views/ab_customer_inherit.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_sales_contract/static/src/pos/**/*.js',
            'ab_sales_contract/static/src/pos/**/*.xml',
        ],
    },


}
