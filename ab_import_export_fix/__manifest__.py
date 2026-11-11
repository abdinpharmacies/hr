# -*- coding: utf-8 -*-
{
    'name': "AB Import Export Fix",

    'summary': """Import and export fixes for Abdin custom workflows.""",

    'description': """
        Disables XLSX text wrapping and exposes Database ID in import mappings.
    """,

    'author': "Emad Abdin",
    'website': "https://www.abdinpharmacies.com",
    'license': 'LGPL-3',

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/13.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Abdin',
    'version': '19.0.1.0.0',

    # any module necessary for this one to work correctly
    'depends': ['base_import'],

    # always loaded
    'data': [
    ],
    # only loaded in demonstration mode
    'demo': [
        # 'demo/demo.xml',
    ],
    'installable': True,
}
