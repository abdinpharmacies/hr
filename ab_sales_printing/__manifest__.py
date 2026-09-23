{
    'name': 'Abdin Sales Printing',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'hagerYasser',
    'summary': 'Connect the Sales bill wizard to shared CUPS printing',
    'depends': ['ab_sales', 'ab_printing'],
    'assets': {
        'web.assets_backend': [
            'ab_sales_printing/static/src/bill_wizard/cups_print_dialog.js',
            'ab_sales_printing/static/src/bill_wizard/cups_print_dialog.xml',
            'ab_sales_printing/static/src/bill_wizard/bill_wizard_action.js',
        ],
    },
    'application': False,
    'auto_install': False,
    'installable': True,
}
