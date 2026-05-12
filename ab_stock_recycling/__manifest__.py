# -*- coding: utf-8 -*-
{
    'name': "ab_stock_recycling",

    'summary': """
        ab_stock_recycling
    """,

    'description': """
        ab_stock_recycling
    """,
    'application': True,

    'author': "emadco88@gmail.com",
    'website': "https://www.abdinpharmacies.com",

    'category': 'Inventory/Inventory',
    'version': '19.0.1.0.0',

    'depends': ['base', 'ab_eplus_connect', 'ab_data_from_excel', 'abdin_et', 'report_xlsx', 'ab_store',
                'ab_product'],
    'license': 'LGPL-3',
    'installable': True,
    'assets': {
        'web.assets_backend': [
            'ab_stock_recycling/static/src/scss/ab_stock_recycling.scss',
        ],
    },
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/00_menus.xml',
        'views/res_users.xml',
        'views/ab_stock_recycling_header.xml',
        'views/ab_stock_recycling_line.xml',
        'views/ab_stock_recycling_need.xml',
        'views/ab_stock_recycling_dist.xml',
        'views/ab_stock_recycling_excluded_item.xml',
        'views/abdin_eplus_ab_supplier.xml',
        'views/ab_stock_recycling_to_cycle.xml',
        'templates/ab_stock_recycling_excluded_item_report.xml',
        'reports/xlsx_overstock_no_need.xml',

    ],
}
