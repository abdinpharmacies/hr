{
    'version': '19.0.1.0.0',
    'name': 'ab_eplus_replication',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base',
                'ab_eplus_connect',
                'ab_product',
                'ab_store',
                'ab_supplier',
                'ab_customer',
                'queue_job',
                'web_progress',
                ],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_product_view_inherit.xml',
        'views/ab_store_inherit.xml',
        # 'views/ab_customer_inherit.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
