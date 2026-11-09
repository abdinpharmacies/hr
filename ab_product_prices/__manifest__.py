{
    'version': '19.0.1.0.0',
    'name': 'Product Price editing',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_store', 'ab_product', 'ab_management_tools', 'ab_product_source', 'ab_hr', 'ab_purchase'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_product_price_editing.xml',
        'views/ab_action_server.xml'
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
