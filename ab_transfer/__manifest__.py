{
    'name': 'Abdin Transfer',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'application': True,
    'depends': ['base', 'ab_store', 'mail', 'ab_product', 'ab_hr', 'ab_eplus_connect', 'ab_widgets'],
    'category': 'AbdinSupplyChain',
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/menus.xml',
        'views/pos_action.xml',
        'views/ab_transfer_request.xml',
        'views/ab_transfer_request_report.xml',
        'views/ab_transfer_request_pos_action.xml',
        'views/ab_transfer_request_loader_cleanup.xml',
        'views/ab_transfer_header.xml',
        'views/ab_transfer_line.xml',
        'views/ab_transfer_receive.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_transfer/static/src/dashboard/**/*.js',
            'ab_transfer/static/src/dashboard/**/*.xml',
            'ab_transfer/static/src/dashboard/**/*.scss',
            'ab_transfer/static/src/pos/**/*.js',
            'ab_transfer/static/src/pos/**/*.xml',
            'ab_transfer/static/src/pos/**/*.scss',
        ],
    },

    'installable': True,
}
