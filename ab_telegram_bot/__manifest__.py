{
    'name': 'Telegram Bots',
    'description': 'Manage multiple Telegram bots, known chats, module subscriptions and queued deliveries.',
    'version': '19.0.1.1.0',
    'license': 'LGPL-3',
    'category': 'Productivity',
    'author': 'Abdin Pharmacies',
    'developer': 'emadco88',
    'application': True,
    'depends': ['base', 'queue_job'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/security_groups.xml', 'security/ir.model.access.csv',
        'security/record_rules.xml', 'data/queue_jobs.xml', 'views/telegram_views.xml', 'views/update_views.xml',
    ],
    'installable': True,
}
