{
    'name': "Accounting Future",

    'summary': """
        Accounting Future
        """,

    'description': """
        Future JE for Accounting, Due and Other JEs
    """,

    'author': "emadco88",
    'website': "https://www.abdinpharmacies.com",
    'license': 'LGPL-3',
    'category': 'Accounting',
    'version': '19.0.0.1',
    'application': True,
    'depends': ['ab_accounting'],
    'data': [
        'security/security_groups.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_accounting_future_header.xml',
        'views/ab_accounting_future.xml',
    ],
}
# -*- coding: utf-8 -*-
