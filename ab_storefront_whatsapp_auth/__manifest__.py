{
    'name': 'Abdin Storefront WhatsApp Authentication',
    'summary': 'Independent WhatsApp phone verification and password recovery',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Website/eCommerce',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_ecommerce_storefront'],
    'data': [
        'security/security.xml',
        'security/service_user.xml',
        'security/ir.model.access.csv',
        'views/transport.xml',
        'views/auth.xml',
    ],
    'assets': {'web.assets_frontend': [
        'ab_storefront_whatsapp_auth/static/src/js/signup.js',
    ]},
    'installable': True,
    'application': False,
}
