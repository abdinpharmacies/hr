# -*- coding: utf-8 -*-

{
    'name': "abdin_pl",
    'license': 'LGPL-3',

    'summary': """
        P&amp;L Module""",

    'description': """
        Generate P_and_L
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Abdin',
    'version': '19.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'ab_store', 'ab_accounting', 'abdin_eplus'],

    # always loaded
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/cron_repl.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
