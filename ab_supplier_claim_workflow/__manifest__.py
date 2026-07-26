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
        'data/portal_tracking.xml',
        'views/ab_supplier_claim_escalation.xml',
        'views/ab_supplier_mapping.xml',
        'views/ab_supplier_claim_cycle.xml',
        'views/ab_claim_error_wizard.xml',
        'views/ab_check_delivery_wizard.xml',
        'views/ab_supplier_claim_issue.xml',
        'views/supplier_claim_tracking_templates.xml',
        'views/menus.xml',
    ],

    'installable': True,
    'auto_install': ['ab_supplier_claim_cycle'],
    'assets': {
        'web.assets_backend': [
            'ab_supplier_claim_workflow/static/src/scss/supplier_claim_cycle.scss',
            'ab_supplier_claim_workflow/static/src/js/mapping_list_controller.js',
            'ab_supplier_claim_workflow/static/src/js/scc_close_error_dialog.js',
            'ab_supplier_claim_workflow/static/src/js/claim_chatter_toggle.js',
            'ab_supplier_claim_workflow/static/src/js/tracking_link_action.js',
        ],
        'web.assets_frontend': [
            'ab_supplier_claim_workflow/static/src/scss/supplier_claim_portal.scss',
            'ab_supplier_claim_workflow/static/src/js/supplier_claim_portal_animations.js',
        ],
    },
}
