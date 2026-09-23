{
    'name': 'ab_purchase_ob',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'mail', 'ab_purchase', 'ab_product_source', 'ab_inventory'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/opening_balance_header.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
