{
    'name': 'Abdin Employee Cashier Access',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_employee_access_sales', 'ab_sales_cashier'],
    'assets': {
        'web.assets_backend': [
            'ab_employee_access_sales_cashier/static/src/cashier/**/*.js',
            'ab_employee_access_sales_cashier/static/src/cashier/**/*.xml',
            'ab_employee_access_sales_cashier/static/src/cashier/**/*.scss',
        ],
    },
    'installable': True,
    'auto_install': True,
    'application': False,
}
