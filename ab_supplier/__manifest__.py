# -*- coding: utf-8 -*-
{
    'name': "ab_supplier",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,
    'license': 'LGPL-3',
    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'AbdinSupplyChain',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'ab_costcenter'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/ab_supplier.xml',
        'views/ab_supplier_contact.xml',
        'views/ab_supplier_bracket.xml',
        'views/ab_supplier_discount.xml',
        'views/templates.xml',
        'views/ab_supplier_note.xml',
        'views/ab_supplier_note_schedule.xml',
        'views/ab_supplier_marketing.xml',
        'views/ab_supplier_compensation.xml',
        'views/ab_supplier_payment_type.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
