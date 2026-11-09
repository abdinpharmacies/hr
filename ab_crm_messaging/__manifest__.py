{
    'name': 'CRM Messaging',
    'version': '19.0.1.8.0',
    'license': 'LGPL-3',
    'category': 'Customer Operations',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_crm_core', 'rpc'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
}
