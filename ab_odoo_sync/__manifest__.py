{
    "name": "AB Odoo Sync Core",
    "summary": "Shared contracts and rules for branch upload synchronization",
    "description": "Technical core shared by AB Odoo Sync upload and mapping runtimes.",
    "author": "Abdin Pharmacies",
    "developer": "emadco88",
    "website": "https://www.abdinpharmacies.com",
    "license": "LGPL-3",
    "category": "Tools",
    "version": "19.0.3.0.0",
    "depends": ["base", "web"],
    "data": [
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_odoo_sync/static/src/fields/pretty_json/pretty_json_field.js",
            "ab_odoo_sync/static/src/fields/pretty_json/pretty_json_field.xml",
            "ab_odoo_sync/static/src/fields/pretty_json/pretty_json_field.scss",
        ],
    },
    "installable": True,
    "application": False,
}
