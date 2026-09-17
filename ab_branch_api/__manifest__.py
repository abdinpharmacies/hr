{
    'name': 'Branch API',
    'version': '19.0.5.3.2',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'hossam elsheikh',
    'depends': ['ab_sales', 'ab_hr', 'rpc'],
    'data': [
        'security/ir.model.access.csv',
        'views/api_views.xml',
    ],
    'application': False,
    'installable': True,
}
