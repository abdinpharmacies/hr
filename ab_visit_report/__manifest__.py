{
    'name': 'Visit Report',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_hr', 'ab_store', 'abdin_telegram', 'mail'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/ab_visit_report_views.xml',
        'views/menus.xml',
        'data/legal_documents_note.xml'

    ],
    'assets': {
        'web.assets_backend': [
            'ab_visit_report/static/src/scss/ab_visit_report.scss',
        ],
    },

}
