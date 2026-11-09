{
    'name': 'Abdin Accounting Base',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['base'],
    'installable': True,
    'auto_install': False,
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'data': [
        'security/ir.model.access.csv',
        'data/account_guide.xml',
        'views/catalog.xml',
    ],
}
