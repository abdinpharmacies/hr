{
    'name': 'Manpower Need',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Abdin',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'summary': 'Manpower need per hour planning',
    'depends': ['ab_hr'],
    'data': ['security/security_groups.xml',
             'security/ir.model.access.csv',
             'views/manpower_hour_need_views.xml',
             ],
    'assets': {
        'web.assets_backend': [
            'ab_manpower_need/static/src/scss/manpower_hour_need_dashboard.scss',
        ],
    },
    'application': False,
    'installable': True,
}
