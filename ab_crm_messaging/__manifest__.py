{
    'name': 'CRM Messaging',
    'version': '19.0.1.12.0',
    'license': 'LGPL-3',
    'category': 'Customer Operations',
    'author': 'Abdin Pharmacies',
    'developer': 'Alhassan Hossny',
    'depends': ['ab_crm_core', 'rpc'],
    'external_dependencies': {'python': ['PIL'], 'bin': ['ffprobe']},
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/views.xml',
    ],
    'installable': True,
    'application': False,
}
