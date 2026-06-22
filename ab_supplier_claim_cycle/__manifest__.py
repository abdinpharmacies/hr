{
    'name': 'Supplier Claim Cycle',
    'application': True,
    'depends': ['base', 'mail','ab_supplier','ab_management_tools'],

    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'views/menus.xml',
        'views/ab_supplier_claim_cycle.xml',

    ]


}
