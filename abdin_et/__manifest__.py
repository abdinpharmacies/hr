# -*- coding: utf-8 -*-
{
    'name': "abdin_et.extra_tools",

    'summary': """
        Extra Tools""",

    'description': """
        Extra tools:
        1-slugify
        2-ab_msg
        3-get_modified_name
        4-

    """,
    'license': 'LGPL-3',

    'author': "Emad Abdin",
    'website': "https://www.abdinpharmacies.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Abdin',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/ab_message_wiz.xml',
        'views/views.xml',
        # 'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
    'installable': True,
}
