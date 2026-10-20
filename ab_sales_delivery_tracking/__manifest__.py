{
    'name': 'Abdin Callcenter Delivery',
    'version': '19.0.2.0.0',
    'author': 'Abdin Pharmacies',
    'developer': 'hossam elsheikh',
    'license': 'LGPL-3',
    'depends': ['ab_sales'],
    'data': ['views/pos_action.xml'],
    'assets': {'web.assets_backend': [
        'ab_sales_delivery_tracking/static/src/pos/delivery_notification.js',
        'ab_sales_delivery_tracking/static/src/pos/delivery_notification.xml',
    ]},
    'installable': True,
    'application': False,
}
