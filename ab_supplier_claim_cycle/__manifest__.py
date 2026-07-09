{
    'name': 'Supplier Claim Cycle',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'application': True,
    'depends': ['base', 'mail', 'ab_supplier', 'ab_costcenter'],

    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/sequence.xml',
        'data/cron_escalation.xml',
        'views/menus.xml',
        'views/ab_supplier_claim_escalation.xml',
        'views/ab_supplier_claim_cycle.xml',
        'views/ab_supplier_claim_issue.xml',
    ],

    'installable': True,
    'assets': {
        'web.assets_backend': [
            'ab_supplier_claim_cycle/static/src/scss/supplier_claim_cycle.scss',
        ],
    },
}
