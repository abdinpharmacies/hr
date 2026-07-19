{
    'name': 'Supplier Claim Workflow',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'category': 'AbdinClaimCycle',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'application': True,
    'depends': ['ab_supplier_claim_cycle', 'ab_hr'],

    'data': [
        'security/groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/sequence.xml',
        'data/cron_escalation.xml',
        'data/cron_telegram_updates.xml',
        'data/auto_import_managers.xml',
        'views/ab_supplier_claim_escalation.xml',
        'views/ab_supplier_claim_cycle.xml',
        'views/ab_check_delivery_wizard.xml',
        'views/ab_supplier_type_wizard.xml',
        'views/ab_supplier_claim_issue.xml',
        'views/ab_supplier_claim_telegram_registration_views.xml',
        'views/menus.xml',
        'views/telegram_managers_action.xml',
    ],

    'installable': True,
    'assets': {
        'web.assets_backend': [
            'ab_supplier_claim_workflow/static/src/scss/supplier_claim_cycle.scss',
            'ab_supplier_claim_workflow/static/src/js/telegram_managers.js',
            'ab_supplier_claim_workflow/static/src/xml/telegram_managers.xml',
        ],
    },
}
