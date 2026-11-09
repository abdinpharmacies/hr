# -*- coding: utf-8 -*-
{
    'name': "ab_fixed_asset",
    'license': 'LGPL-3',

    'summary': """Abdin Fixed Assets
""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '19.0.0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail', 'ab_store', 'ab_accounting', 'abdin_telegram'],

    # always loaded
    'data': [
        'data/ab_accounting_account_guide.xml',
        'security/security.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_fixed_asset_assets_inventory.xml',
        'views/ab_fixed_asset_inventory_line.xml',
        'views/views.xml',
        'views/ab_fixed_asset_inventory_standards.xml',
        'views/account_je.xml',
        'views/ab_accounting_je_line_qry.xml',
        'views/ab_fixed_asset_move_wizard.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # '/ab_fixed_asset/static/src/js/fixed_assets_alert.js',
            # '/ab_fixed_asset/static/src/css/fixed_assets_alert.css',
        ],
    },

    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
}
