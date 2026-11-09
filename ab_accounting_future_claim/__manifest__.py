{
    'name': "Accounting Future Claim",

    'summary': """
        Accounting Future Claim
        """,

    'description': """
        Add Future Interface to Claim  
    """,

    'author': "emadco88",
    'website': "https://www.abdinpharmacies.com",
    'license': 'LGPL-3',
    'category': 'Accounting',
    'version': '19.0.0.1',
    'application': True,
    'depends': ['ab_purchase', 'ab_accounting_future'],
    'data': [
        'security/security_groups.xml',
        'security/security_rules.xml',
        'security/ir.model.access.csv',
        'views/ab_purchase_claim_inherit.xml',
    ],
}
# -*- coding: utf-8 -*-
