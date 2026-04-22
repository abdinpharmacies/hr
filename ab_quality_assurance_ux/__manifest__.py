{
    'name': 'Quality Assurance UX Improvements',
    'version': '19.0.1.0.0',
    'category': 'Quality',
    'summary': 'Enhanced UI/UX for Quality Assurance Module',
    'description': """
        This module provides professional UI/UX improvements to the Quality Assurance module.
        - Improved form layouts
        - Modern summary cards
        - Progress bars for scores
        - Kanban views for visits
        - Enhanced list views
    """,
    'author': 'Senior UI/UX Designer & Odoo Developer',
    'depends': ['ab_quality_assurance'],
    'data': [
        'views/ab_quality_assurance_visit_ux_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_quality_assurance_ux/static/src/scss/ab_quality_assurance_ux.scss',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
