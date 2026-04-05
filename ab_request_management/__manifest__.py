{
    'name': 'Request Management',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'mail', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'data/ab_request_sequence.xml',
        'views/ab_request_type_views.xml',
        'views/ab_request_ticket_views.xml',
        'views/menus.xml',
    ],
}
