{
    'name': 'Website Sales Chatter',
    'version': '19.0.1.15.1',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_crm_sales_workspace', 'ab_hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'assets': {'web.assets_backend': ['ab_crm_website/static/src/*']},
}
