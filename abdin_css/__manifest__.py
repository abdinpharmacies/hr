{
    'name': 'Abdin CSS.',
    'summary': 'This is Abdin Pharmacies CSS. ',
    'description': """
        Abdin Pharmacies CSS For Website.
    """,
    'author': "Emad Abdin",
    'category': 'Abdin',
    'version': '19.0.1.0.0',
    'depends': ["web"],
    'assets': {
        'web.assets_backend': [
            'abdin_css/static/src/scss/abdin.scss',
            # 'abdin_css/static/src/scss/sticky_list_view_headers.css',
            # "abdin_css/static/src/css/pivot.css",
        ],
        'web.assets_qweb': [
            # 'abdin_css/static/src/xml/pivot.xml',
        ],

    },
    'data': [
        # 'views/template.xml',
    ],
    'support': 'emadco88@gmail.com',
    'license': 'LGPL-3',
    'installable': True,
}
