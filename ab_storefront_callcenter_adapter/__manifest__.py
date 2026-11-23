{
    'name': 'Storefront Callcenter Adapter',
    'version': '19.0.1.5.2',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_ecommerce_storefront', 'website_livechat', 'im_livechat'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'assets': {
        'web.assets_frontend': [
            'ab_storefront_callcenter_adapter/static/src/chat.js',
            'ab_storefront_callcenter_adapter/static/src/native.js',
            'ab_storefront_callcenter_adapter/static/src/native_history.js',
            'ab_storefront_callcenter_adapter/static/src/native_history.xml',
        ],
        'portal.assets_chatter': [
            'ab_storefront_callcenter_adapter/static/src/portal_refresh.js',
            'ab_storefront_callcenter_adapter/static/src/portal_refresh.xml',
        ]
    },
}
