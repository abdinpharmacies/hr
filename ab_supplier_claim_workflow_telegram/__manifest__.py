{
    'name': 'Supplier Claim Workflow Telegram',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinClaimCycle',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'application': False,
    'depends': ['ab_supplier_claim_workflow', 'ab_telegram_webhook'],
    'pre_init_hook': 'pre_init_hook',
    'data': [
        'security/ir.model.access.csv',
        'data/cron_telegram_updates.xml',
        'data/auto_import_managers.xml',
        'views/ab_supplier_claim_cycle_views.xml',
        'views/ab_supplier_claim_escalation_views.xml',
        'views/ab_supplier_claim_telegram_registration_views.xml',
        'views/telegram_managers_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_supplier_claim_workflow_telegram/static/src/scss/supplier_claim_workflow_telegram.scss',
            'ab_supplier_claim_workflow_telegram/static/src/js/telegram_managers.js',
            'ab_supplier_claim_workflow_telegram/static/src/xml/telegram_managers.xml',
        ],
    },
    'auto_install': ['ab_supplier_claim_workflow'],
    'installable': True,
}
