{
    'name': 'ab_odoo_replication_upload',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_odoo_connect', 'queue_job'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

    'installable': True,
}
