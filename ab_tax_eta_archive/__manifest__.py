{
    'name': 'ETA Tax Archive',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'author': 'Abdin Pharmacies',
    'developer': 'yahyazakaria22',
    'application': True,
    'depends': ['base', 'web'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/eta_views.xml',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_tax_eta_archive/static/src/js/eta_dashboard.js',
            'ab_tax_eta_archive/static/src/xml/eta_dashboard.xml',
            'ab_tax_eta_archive/static/src/scss/eta_dashboard.scss',
        ],
    },
    'installable': True,
}
