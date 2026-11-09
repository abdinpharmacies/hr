{
    'version': '19.0.1.0.0',
    'name': 'Custody Cycle',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_hr', 'ab_costcenter', 'ab_store', 'ab_accounting', 'abdin_telegram'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules_ab_custody_request_header.xml',
        'security/record_rules_ab_custody_request_line.xml',
        'security/ir.model.access.csv',
        'data/template_custody_request_email.xml',
        'views/menus.xml',
        'views/ab_custody_request_header.xml',
        'views/ab_custody_request_account.xml',
        'views/ab_custody_request_config.xml',
        'views/ab_custody_employee_data.xml'

    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
