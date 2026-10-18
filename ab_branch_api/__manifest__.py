{
    'name': 'Branch API',
    'description': 'Authenticated branch API for sales, returns, stock and customer operations.',
    'version': '19.0.5.5.3',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'hossam elsheikh',
    'depends': ['ab_sales', 'ab_customer', 'ab_hr', 'rpc'],
    'data': [
        'security/ir.model.access.csv',
        'views/api_views.xml',
    ],
    'application': False,
    'installable': True,
}
