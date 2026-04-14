{
    'name': 'Employee Tools',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'ab_hr', 'abdin_telegram'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/tools_type_views.xml',
        'views/inventory_move_views.xml',
        'views/employee_tools_views.xml',
        'views/menus.xml',
    ],
    # 'assets': {
    #     'web.assets_backend': [
    #         '/ab_sales/static/src/js/read_barcode.js']}

}
