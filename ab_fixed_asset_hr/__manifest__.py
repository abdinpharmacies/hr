{
    'version': '19.0.1.0.0',
    'name': 'Fixed Asset - HR Link',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_hr', 'ab_fixed_asset'],
    'data': [
        'security/record_rules.xml',
        'security/ir.model.access.csv',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
