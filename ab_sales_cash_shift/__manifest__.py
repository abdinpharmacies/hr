{
    'name': 'Abdin Cash Shift Handover',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_sales_inventory', 'ab_employee_access_sales', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/cash_shift.xml',
        'wizard/operations.xml',
    ],
    'assets': {'web.assets_backend': [
        'ab_sales_cash_shift/static/src/cashier.js',
        'ab_sales_cash_shift/static/src/cashier.xml',
    ]},
    'installable': True,
}
