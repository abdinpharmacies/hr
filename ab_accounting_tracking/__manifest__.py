{
    'name': "Accounting Tracking",

    'summary': """
        Accounting Tracking
        """,

    'description': """
        Tracking system for JEs changes after posted.
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
        'views/ab_accounting_tracking_header.xml',
        'views/ab_accounting_tracking.xml',
    ],
}
# -*- coding: utf-8 -*-
