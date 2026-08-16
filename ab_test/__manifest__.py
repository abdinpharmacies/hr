{
    "name": "AB Sync Test Models",
    "summary": "Relational source models for AB Odoo Sync simulation",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "category": "Tools",
    "author": "Abdin Pharmacies",
    "developer": "Alhassan Hossny",
    "application": True,
    "depends": ["base"],
    "data": [
        "security/security_groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        "views/ab_test_views.xml",
    ],
    "installable": True,
}
