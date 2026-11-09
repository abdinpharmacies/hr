{
    'external_dependencies': {'python': ['pandas']},
    'version': '19.0.1.0.0',
    'name': 'ePlus Odoo Replication Purchase',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base',
                'ab_eplus_replication',
                'ab_purchase',
                'ab_purchase_ob',
                ],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_purchase_inherit.xml',
        'views/ab_eplus_replication_server_act.xml',
        'views/ab_purchase_claim_inherit.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
