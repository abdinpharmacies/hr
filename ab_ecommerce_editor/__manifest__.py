{
    'name': 'Abdin eCommerce Editor',
    'summary': 'Visual content studio with safe previews and versioned publishing',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Website/eCommerce',
    'author': 'Abdin Pharmacies',
    'developer': 'Mohamed Fawzy',
    'application': True,
    'depends': ['ab_core_ui', 'ab_ecommerce_storefront'],
    'data': [
        'security/security_groups.xml',
        'security/record_rules.xml',
        'security/ir.model.access.csv',
        'views/editor_views.xml',
        'views/editor_templates.xml',
        'data/scheduled_publish.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ab_ecommerce_editor/static/src/editor_workspace.js',
            'ab_ecommerce_editor/static/src/editor_workspace.xml',
            'ab_ecommerce_editor/static/src/editor_workspace.scss',
        ],
        'web.assets_frontend': [
            'ab_ecommerce_editor/static/src/editor_public.scss',
        ],
    },
    'installable': True,
}
