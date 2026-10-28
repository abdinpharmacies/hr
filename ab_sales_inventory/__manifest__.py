{
    'name': 'Abdin Native Sales Inventory',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_stock_integration', 'ab_sales', 'ab_inventory', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/native_sales.xml',
        'views/native_cancel_wizard.xml',
    ],
    'assets': {'web.assets_backend': ['ab_sales_inventory/static/src/returns/native_return.js', 'ab_sales_inventory/static/src/returns/native_return.xml']},
    'installable': True,
    'auto_install': True,
}
