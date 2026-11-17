{
    'name': 'Storefront Callcenter Adapter',
    'version': '19.0.1.0.1',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_ecommerce_storefront'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'assets': {
        'web.assets_frontend': ['ab_storefront_callcenter_adapter/static/src/*']
    },
}
