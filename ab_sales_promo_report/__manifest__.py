{
    'name': 'Abdin Sales Promo Report',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': False,
    'depends': ['ab_sales_promo', 'ab_eplus_connect'],
    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'views/ab_sales_promo_report_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
