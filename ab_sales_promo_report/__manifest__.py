{
    'name': 'Abdin Sales Promo Report',
    'version': '19.0.2.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': False,
    'depends': ['ab_sales_promo'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'views/ab_sales_promo_report_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
}
