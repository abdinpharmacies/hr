{
    'name': 'ETA Tax Archive',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Accounting',
    'author': 'Abdin Pharmacies',
    'developer': 'yahyazakaria22',
    'application': True,
    'depends': ['base'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/eta_views.xml',
        'data/cron.xml',
    ],
    'installable': True,
}
