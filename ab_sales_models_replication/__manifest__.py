{
    'name': 'ab_sales_models_replication',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_odoo_replication', 'ab_sales'],
    'data': [
        'data/ab_odoo_replication_cron_jobs.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

    'installable': True,
}
