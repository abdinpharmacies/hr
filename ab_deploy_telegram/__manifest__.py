{
    'name': 'Deployment Telegram Notifications',
    'description': 'Send deployment approval and batch summaries through configured Telegram bots.',
    'version': '19.0.1.2.0',
    'license': 'LGPL-3',
    'category': 'Administration',
    'author': 'Abdin Pharmacies',
    'developer': 'emadco88',
    'application': False,
    'depends': ['ab_deploy', 'ab_telegram_bot'],
    'data': ['security/security.xml', 'views/deployment_views.xml'],
    'installable': True,
}
