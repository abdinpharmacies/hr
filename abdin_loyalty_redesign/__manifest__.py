{
    'name': 'Abdin Loyalty Redesign',
    'summary': 'Premium SaaS UI/UX for Coupons, Promotions, Gift Cards & Loyalty',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Abdin Pharmacies',
    'category': 'Website',
    'depends': ['website_sale_loyalty'],
    'data': [
        'views/loyalty_program_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'abdin_loyalty_redesign/static/src/scss/loyalty_redesign.scss',
        ],
    },
    'installable': True,
    'application': False,
}
