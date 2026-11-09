{
    'version': '19.0.1.0.0',
    'name': 'ab_archive_purchase (Archive Purchase)',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_archive', 'ab_purchase', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/ab_archive.xml',
        'views/ab_purchase_notice_header_inherit.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
