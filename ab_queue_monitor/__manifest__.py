{
    'name': 'Queue Monitor',
    'summary': 'Manual background job discovery and read-only execution monitoring',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Administration',
    'author': 'Abdin Pharmacies',
    'developer': 'Mohamed Fawzy',
    'depends': ['web', 'integration_queue_job'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/monitor_views.xml',
    ],
    'assets': {'web.assets_backend': [
        'ab_queue_monitor/static/src/monitor.js',
        'ab_queue_monitor/static/src/monitor.xml',
        'ab_queue_monitor/static/src/monitor.scss',
    ]},
    'application': True,
    'installable': True,
}
