{
    'name': 'Announcements',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'AbdinSupplyChain',
    'application': True,
    'depends': ['base', 'mail', 'ab_hr'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/menus.xml',
        'views/ab_announcement.xml',
        'views/template_announcement.xml',
    ],
    'assets': {
        'web.assets_backend': [
            '/ab_announcement/static/src/scss/announcement.scss']},

    'installable': True,
}
