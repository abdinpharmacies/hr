{
    'name': 'Customer',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_costcenter', 'ab_store', 'mail'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/ab_customer.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

    'installable': True,
}
