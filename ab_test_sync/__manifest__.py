{
    "name": "AB Sync Test Mirrors",
    "summary": "Typed MAIN staging models for AB Odoo Sync simulation",
    "version": "19.0.1.1.0",
    "license": "LGPL-3",
    "category": "Tools",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "application": True,
    "depends": ["ab_odoo_sync", "ab_test"],
    "data": [
        "security/security_groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "data/sync_profiles.xml",
        "views/ab_test_sync_views.xml",
    ],
    "installable": True,
}
