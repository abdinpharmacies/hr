# -*- coding: utf-8 -*-

{
    'name': "abdin_eplus",
    'license': 'LGPL-3',

    'summary': """
        BCONNECT Module""",

    'description': """
        Generate P_and_L
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '19.0.0.1',
    'application': True,

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'web_progress', 'ab_eplus_connect'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/00_parent_menus.xml',
        'wizards/replicate_sales.xml',
        'wizards/replicate_config_tables.xml',
        'wizards/replicate_purchase_tables.xml',
        'wizards/replicate_trans_table.xml',
        'views/config_tables.xml',
        'views/r_sales_trans_h.xml',
        'views/pur_trans_h.xml',
        'views/pur_trans_d.xml',
        'views/abdin_eplus_store_trans_h.xml',
        'views/store_trans_h.xml',
        'views/templates.xml',
        'views/cron_repl.xml',
    ],

    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}
