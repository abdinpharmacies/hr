{
    "name": "Abdin Sales Sync",
    "summary": "MAIN staging models for branch sales operations uploaded by AB Odoo Sync",
    "version": "19.0.1.2.0",
    "license": "LGPL-3",
    "category": "AbdinSupplyChain",
    "author": "Abdin Pharmacies",
    "developer": "hossam elsheikh",
    "application": True,
    "depends": ["ab_odoo_sync", "ab_sales", "ab_hr"],
    "data": [
        "security/security_groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "data/sync_profiles.xml",
        "data/sync_profile_updates.xml",
        "data/sync_profiles_extra.xml",
        "views/ab_sales_sync_views.xml",
        "views/ab_sales_sync_extra_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "ab_sales_sync/static/src/fields/pretty_json/pretty_json_field.js",
            "ab_sales_sync/static/src/fields/pretty_json/pretty_json_field.xml",
            "ab_sales_sync/static/src/fields/pretty_json/pretty_json_field.scss",
        ],
    },
    "installable": True,
}
