{
    'name': 'Abdin Cash Shift Handover',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_sales_cashier', 'ab_employee_access_sales_cashier', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/cash_shift.xml',
        'wizard/operations.xml',
        'reports/cash_wallet_report.xml',
    ],
    'installable': True,
}
