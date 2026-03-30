{
    'name': 'Abdin Widgets',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Abdin',
    'application': False,
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'ab_widgets/static/src/ab_many2x_patch.js',
            'ab_widgets/static/src/ab_many2x_keyboard_map_patch.js',
            'ab_widgets/static/src/ab_many2one.js',
            'ab_widgets/static/src/ab_many2one_keyboard_context_patch.js',
            'ab_widgets/static/src/ab_many2one.xml',
            'ab_widgets/static/src/ab_many2one_keyboard_context_patch.xml',
            'ab_widgets/static/src/ab_many2one.scss',
            'ab_widgets/static/src/ab_many2many.js',
            'ab_widgets/static/src/ab_many2many.xml',
            'ab_widgets/static/src/ab_many2many.scss',
        ],
    },
    'installable': True,
}
