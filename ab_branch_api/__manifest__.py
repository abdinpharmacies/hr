{
    'name': 'Branch API',
    'version': '19.0.2.0.0',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'hossam elsheikh',
    'depends': ['ab_sales', 'ab_hr', 'rpc'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'views/api_views.xml',
        'views/enrollment_views.xml',
    ],
    'application': False,
    'installable': True,
}
