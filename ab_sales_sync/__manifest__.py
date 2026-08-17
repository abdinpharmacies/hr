{
    "name": "Abdin Sales Sync",
    "summary": "MAIN staging models for branch sales operations uploaded by AB Odoo Sync",
    "version": "19.0.1.0.0",
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
        "views/ab_sales_sync_views.xml",
    ],
    "installable": True,
}
