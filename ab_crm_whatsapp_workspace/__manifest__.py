{
    'name': 'WhatsApp Sales Chatter',
    'version': '19.0.1.2.0',
    'license': 'LGPL-3',
    'category': 'Sales',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': [
        'ab_crm_whatsapp',
        'ab_crm_sales_workspace',
        'ab_whatsapp_api',
        'ab_hr',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'views/account.xml',
    ],
    'assets': {
        'web.assets_backend': ['ab_crm_whatsapp_workspace/static/src/*'],
        'web.assets_unit_tests': ['ab_crm_whatsapp_workspace/static/tests/*.test.js'],
    },
    'installable': True,
    'auto_install': False,
}
