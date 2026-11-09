{
    'name': "Accounting Reconciliation",

    'summary': """
        Accounting Reconciliation
        """,

    'description': """
        Reconciliation Module For Accounts need reconciliation (e.g Banks Accounts)
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
        'views/ab_accounting_je_inherit.xml',
        'views/ab_accounting_reconcile.xml',
        'views/xlsx_account_statement.xml',
    ],
}
# -*- coding: utf-8 -*-
